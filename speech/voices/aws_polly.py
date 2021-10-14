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


    Icelandic-language text to speech via Amazon Polly.

"""

from typing import Optional, Any, cast

import os
import json
import logging
from threading import Lock

import cachetools  # type: ignore
import boto3  # type: ignore
from botocore.exceptions import ClientError  # type: ignore

from . import generate_data_uri


NAME = "Amazon Polly"
VOICES = frozenset(("Karl", "Dora"))


# The AWS Polly API access keys
# You must obtain your own keys if you want to use this code
# JSON format is the following:
# {
#     "aws_access_key_id": ""my_key,
#     "aws_secret_access_key": "my_secret",
#     "region_name": "my_region"
# }
#
_AWS_KEYFILE_NAME = "aws_polly_keys.mideind.json"
_AWS_API_KEYS_PATH = os.path.join("resources", _AWS_KEYFILE_NAME)
_aws_api_client: Optional[boto3.Session] = None
_aws_api_client_lock = Lock()


def _initialize_aws_client() -> Optional[boto3.Session]:
    """Set up AWS Polly client."""
    global _api_client

    # Make sure that only one thread is messing with the global variable
    with _aws_api_client_lock:
        if _aws_api_client is None:
            # Read AWS Polly API keys from file
            aws_config = {}
            try:
                with open(_AWS_API_KEYS_PATH) as json_file:
                    aws_config = json.load(json_file)
            except FileNotFoundError:
                logging.warning("Unable to read AWS Polly keys")
                return None
            _api_client = boto3.Session(**aws_config).client("polly")
        # Return client instance
        return _api_client


# Time to live (in seconds) for synthesised text URL caching
# Add a safe 30 second margin to ensure that clients are never provided with an
# audio URL that's just about to expire and might do so before playback starts.
_AWS_URL_TTL = 300  # 5 mins in seconds
_AWS_CACHE_TTL = _AWS_URL_TTL - 30  # seconds
_AWS_CACHE_MAXITEMS = 30


@cachetools.cached(cachetools.TTLCache(_AWS_CACHE_MAXITEMS, _AWS_CACHE_TTL))
def _aws_polly_synthesized_text_url(
    text: str,
    text_format: str,
    audio_format: str,
    voice_id: Optional[str],
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


def text_to_audio_data(
    text: str,
    text_format: str,
    audio_format: str,
    voice_id: str,
    speed: float,
) -> bytes:
    return b""


def text_to_audio_url(
    text: str,
    text_format: str,
    audio_format: str,
    voice_id: str,
    speed: float,
) -> Optional[str]:
    return _aws_polly_synthesized_text_url(**locals())
