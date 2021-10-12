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
from threading import Lock

import cachetools  # type: ignore
import boto3  # type: ignore
from botocore.exceptions import ClientError  # type: ignore

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
_TEXT_FORMATS = frozenset(("text", "ssml"))


def strip_ssml_markup(text: str) -> str:
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
    txt_format: str = _DEFAULT_TEXT_FORMAT,
    audio_format: str = _DEFAULT_AUDIO_FORMAT,
    voice_id: Optional[str] = _DEFAULT_VOICE,
    speed: float = 1.0,
) -> Optional[str]:
    """Returns AWS URL to audio file with speech-synthesised text."""
    client = _initialize_aws_client()  # Set up client lazily
    if client is None:
        logging.warning("Unable to instantiate AWS client")
        return None

    text = text.strip()

    # Special preprocessing for SSML markup
    if txt_format == "ssml":
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
        "TextType": txt_format,
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


def get_synthesized_text_url(
    text: str,
    txt_format: str = _DEFAULT_TEXT_FORMAT,
    audio_format: str = _DEFAULT_AUDIO_FORMAT,
    voice_id: Optional[str] = _DEFAULT_VOICE,
    speed: float = 1.0,
) -> Optional[str]:
    """Returns URL to audio file with speech-synthesised text."""

    # Basic sanity checks
    assert txt_format in _TEXT_FORMATS
    assert audio_format in _SUPPORTED_AUDIO_FORMATS
    assert voice_id in _SUPPORTED_VOICES

    # Clamp speed to 50%-150% range
    speed = max(min(1.5, speed), 0.5)

    if voice_id in _AWS_VOICES:
        # Pass kwargs to function
        return aws_polly_synthesized_text_url(**locals())
    elif voice_id in _TIRO_VOICES:
        pass
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


if __name__ == "__main__":
    """Test speech synthesis through command line invocation."""
    args = sys.argv

    audio_fmt = _DEFAULT_AUDIO_FORMAT
    # Optionally, specify audio format as last argument
    if args[-1] in _SUPPORTED_AUDIO_FORMATS:
        audio_fmt = args[-1]
        args.pop()

    DEFAULT_TEXT = "Góðan daginn og til hamingju með lífið."

    txt = " ".join(args[1:]) if len(args) > 1 else DEFAULT_TEXT
    fn = "_".join([t.lower() for t in txt.split()]) + "." + audio_fmt

    url = get_synthesized_text_url(txt, audio_format=audio_fmt)
    if url:
        import requests

        print(f"Downloading URL {url}")
        r = requests.get(url)

        print(f'Writing to file "{fn}"')
        with open(fn, "wb") as f:
            f.write(r.content)
        _play_audio_file(fn)
    else:
        raise Exception("Error generating speech synthesis URL")
