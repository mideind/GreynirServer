#!/usr/bin/env python
"""

    Greynir: Natural language processing for Icelandic

    Copyright (C) 2021 Miðeind ehf.

       This program is free software: you can redistribute it and/or modify
       it under the terms of the GNU General Public License as published by
       the Free Software Foundation, either version 3 of the License, or
       (at your option) any later version.
       This program is distributed in the hope that it will be useful,
       but WITHOUT ANY WARRANTY; without even the implied warranty of
       MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
       GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see http://www.gnu.org/licenses/.


    Icelandic text to speech via AWS Polly.

"""

from typing import Any, Optional, cast

import sys
import os
import json
import logging
import html
import re
from base64 import b64encode, b64decode
from threading import Lock

import requests
import cachetools  # type: ignore
import boto3  # type: ignore
from botocore.exceptions import ClientError  # type: ignore

from util import icelandic_asciify

# The AWS Polly API access keys (you must obtain your own keys if you want to use this code)
# JSON format is the following:
# {
#     "aws_access_key_id": ""my_key,
#     "aws_secret_access_key": "my_secret",
#     "region_name": "my_region"
# }
#
_API_KEYS_PATH = os.path.join("resources", "aws_polly_keys.mideind.json")
_api_client: Optional[boto3.Session] = None
_api_client_lock = Lock()

# Voices
_DEFAULT_VOICE = "Dora"
_AWS_VOICES = frozenset(("Dora", "Karl"))
_TIRO_VOICES = frozenset(("Dilja", "Alfur"))
_SUPPORTED_VOICES = _AWS_VOICES.union(_TIRO_VOICES)

# Audio formats
_DEFAULT_AUDIO_FORMAT = "mp3"
_SUPPORTED_AUDIO_FORMATS = frozenset(("mp3", "ogg_vorbis", "pcm"))

# Text formats
# For details about SSML markup, see:
# https://developer.amazon.com/en-US/docs/alexa/custom-skills/speech-synthesis-markup-language-ssml-reference.html
_DEFAULT_TEXT_FORMAT = "ssml"
_SUPPORTED_TEXT_FORMATS = frozenset(("text", "ssml"))


_BINARY_MIMETYPE = "application/octet-stream"
_AUDIOFMT_TO_MIMETYPE = {
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "ogg_vorbis": "audio/ogg",
    "pcm": _BINARY_MIMETYPE,
}


def _strip_ssml_markup(text: str) -> str:
    """Remove SSML markup tags from a string"""
    return re.sub(r"<.*?>", "", text)


# Time to live (in seconds) for synthesised text URL caching
# Add a safe 30 second margin to ensure that clients are never provided with an
# audio URL that's just about to expire and might do so before playback starts.
_AWS_URL_TTL = 300  # 5 mins in seconds
_AWS_CACHE_TTL = _AWS_URL_TTL - 30  # seconds
_AWS_CACHE_MAXITEMS = 30


def _initialize_aws_client() -> Optional[boto3.Session]:
    """Set up AWS Polly client"""
    global _api_client

    # Make sure that only one thread is messing with the global variable
    with _api_client_lock:
        if _api_client is None:
            # Read AWS Polly API keys from file
            aws_config = {}
            try:
                with open(_API_KEYS_PATH) as json_file:
                    aws_config = json.load(json_file)
            except FileNotFoundError:
                logging.warning("Unable to read AWS Polly keys")
                return None
            _api_client = boto3.Session(**aws_config).client("polly")
        # Return client instance
        return _api_client


@cachetools.cached(cachetools.TTLCache(_AWS_CACHE_MAXITEMS, _AWS_CACHE_TTL))
def aws_polly_synthesized_text_url(
    text: str,
    text_format: str = _DEFAULT_TEXT_FORMAT,
    audio_format: str = _DEFAULT_AUDIO_FORMAT,
    voice_id: Optional[str] = _DEFAULT_VOICE,
    speed: float = 1.0,
) -> Optional[str]:
    """Returns AWS Polly URL to audio file with speech-synthesised text."""

    # Set up client lazily
    client = _initialize_aws_client()
    if client is None:
        logging.warning("Unable to instantiate AWS client")
        return None

    # Special preprocessing for SSML markup
    if text_format == "ssml":
        # Prevent '&' symbol from breaking markup
        text = text.replace("&", "&amp;")
        # Adjust voice speed as appropriate
        if speed != 1.0:
            perc = int(speed * 100)
            text = f'<prosody rate="{perc}%">{text}</prosody>'
        # Wrap text in the required <speak> tag
        if not text.startswith("<speak>"):
            text = f"<speak>{text}</speak>"

    # Configure query string parameters for AWS request
    params = {
        # The text to synthesize
        "Text": text,
        # mp3 | ogg_vorbis | pcm
        "OutputFormat": audio_format,
        # Dora or Karl
        "VoiceId": voice_id,
        # Valid values for mp3 and ogg_vorbis are "8000", "16000", and "22050".
        # The default value is "22050".
        # "SampleRate": "",
        # "text" or "ssml"
        "TextType": text_format,
        # Only required for bilingual voices
        # "LanguageCode": "is-IS"
    }

    try:
        url = cast(Any, client).generate_presigned_url(
            ClientMethod="synthesize_speech",
            Params=params,
            ExpiresIn=_AWS_URL_TTL,
            HttpMethod="GET",
        )
    except ClientError as e:
        logging.error(e)
        return None

    return url


_TIRO_TTS_URL = "https://tts.tiro.is/v0/speech"


def tiro_synthesized_text_url(
    text: str,
    text_format: str = _DEFAULT_TEXT_FORMAT,
    audio_format: str = _DEFAULT_AUDIO_FORMAT,
    voice_id: Optional[str] = _DEFAULT_VOICE,
    speed: float = 1.0,
) -> Optional[str]:
    """Returns Tiro URL to audio file with speech-synthesised text."""

    assert voice_id in _TIRO_VOICES

    # No proper support for SSML yet
    text = _strip_ssml_markup(text)
    text_format = "text"

    jdict = {
        "Engine": "standard",
        "LanguageCode": "is-IS",
        "OutputFormat": audio_format,
        "SampleRate": "22050",
        "Text": text,
        "TextType": "text",
        "VoiceId": voice_id,
    }

    r = requests.post(_TIRO_TTS_URL, json=jdict)
    if r.status_code != 200:
        raise Exception(f"Received HTTP status code {r.status_code} from Tiro server")

    data: bytes = r.content

    # Generate Data URI (RFC2397) from bytes received
    b64str = b64encode(data).decode("utf-8")

    mime_type = _AUDIOFMT_TO_MIMETYPE.get(audio_format, _BINARY_MIMETYPE)
    data_uri = f"data:{mime_type};{b64str}"

    return data_uri


def get_synthesized_text_url(
    text: str,
    text_format: str = _DEFAULT_TEXT_FORMAT,
    audio_format: str = _DEFAULT_AUDIO_FORMAT,
    voice_id: Optional[str] = _DEFAULT_VOICE,
    speed: float = 1.0,
) -> Optional[str]:
    """Returns URL to audio of speech-synthesised text."""

    text = text.strip()

    # Basic sanity checks
    assert text
    assert text_format in _SUPPORTED_TEXT_FORMATS
    assert audio_format in _SUPPORTED_AUDIO_FORMATS
    assert voice_id in _SUPPORTED_VOICES

    # Clamp speed to 50%-150% range
    speed = max(min(1.5, speed), 0.5)

    # We pass all arguments on to the appropriate function using locals()
    if voice_id in _AWS_VOICES:
        return aws_polly_synthesized_text_url(**locals())
    elif voice_id in _TIRO_VOICES:
        return tiro_synthesized_text_url(**locals())
    else:
        # Shouldn't get here
        raise Exception(f"The voice '{voice_id}' is not supported")


def _play_audio_file(path: str) -> bool:
    """Play audio file at path via command line player. This only
    works on systems with either afplay (macOS) or mpg123 (Linux)."""

    AFPLAY_PATH = "/usr/bin/afplay"
    MPG123_PATH = "/usr/bin/mpg123"

    if os.path.exists(AFPLAY_PATH):
        print(f"Playing file '{path}'")
        os.system(f"{AFPLAY_PATH} {path}")
    elif os.path.exists(MPG123_PATH):
        print(f"Playing file '{path}'")
        os.system(f"{MPG123_PATH} {path}")
    else:
        return False

    return True


_DATA_URI_PREFIX = "data:"


def _is_data_uri(s: str) -> bool:
    """Returns whether a URL is a data URI (RFC2397)."""
    return s.startswith(_DATA_URI_PREFIX)


def _bytes4data_uri(data_uri: str) -> bytes:
    """Returns data in data URI (RFC2397) as bytes."""
    # Format is "data:[mimetype];SUQzBAAAAAAAI1RTU0UAAA..."
    uri = data_uri[len(_DATA_URI_PREFIX) :]
    cmp = uri.split(";")
    b64str = cmp[1] if len(cmp) == 2 else cmp[0]  # Optional mime type
    return b64decode(b64str)


def _fetch_audio_bytes(url: str) -> bytes:
    """Returns bytes of audio file at URL."""
    if _is_data_uri(url):
        return _bytes4data_uri(url)

    r = requests.get(url)
    return r.content


if __name__ == "__main__":
    """Perform speech synthesis of Icelandic text via command line."""
    from argparse import ArgumentParser

    parser = ArgumentParser()

    parser.add_argument(
        "-v",
        "--voice",
        help="specify voice",
        default=_DEFAULT_VOICE,
        choices=list(_SUPPORTED_VOICES),
    )
    parser.add_argument(
        "-f",
        "--audioformat",
        help="select audio format",
        default=_DEFAULT_AUDIO_FORMAT,
        choices=list(_SUPPORTED_AUDIO_FORMATS),
    )
    parser.add_argument(
        "-s",
        "--speed",
        help="set speech speed",
        default=1.0,
        type=float,
    )
    parser.add_argument(
        "-t",
        "--textformat",
        help="set text format",
        default=_DEFAULT_TEXT_FORMAT,
        choices=list(_SUPPORTED_TEXT_FORMATS),
    )
    parser.add_argument(
        "-u", "--url", help="just dump audio URL to stdout", action="store_true"
    )
    parser.add_argument(
        "-n", "--noplay", help="do not play resulting audio file", action="store_true"
    )
    parser.add_argument(
        "text",
        help="text to synthesize",
        default="Góðan daginn og til hamingju með lífið.",
    )

    args = parser.parse_args()

    # Synthesize the text according to CLI options
    url = get_synthesized_text_url(
        args.text,
        text_format=args.textformat,
        audio_format=args.audioformat,
        voice_id=args.voice,
        speed=args.speed,
    )
    if not url:
        print("Error generating speech synthesis URL")
        sys.exit(1)

    if args.url:
        print(url)
        sys.exit(0)

    # Download
    print(f"Downloading URL {url[:200]}")
    data: Optional[bytes] = _fetch_audio_bytes(url)
    if not data:
        raise Exception("Unable to fetch audio data")

    # Write to file system
    fn = "_".join([t.lower() for t in args.text.split()]) + "." + args.audioformat
    fn = icelandic_asciify(fn)
    print(f'Writing to file "{fn}"')
    with open(fn, "wb") as f:
        f.write(data)

    # Play
    if not args.noplay:
        _play_audio_file(fn)
