#!/usr/bin/env python
"""

    Reynir: Natural language processing for Icelandic

    Copyright (C) 2019 Miðeind ehf.
    Original author: Vilhjálmur Þorsteinsson

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

import sys
import os
import json
import logging
from pprint import pprint

import boto3
from botocore.exceptions import ClientError

# The AWS Polly API access keys (you must obtain your own keys if you want to use this code)
# JSON format is the following:
# {
#     "aws_access_key_id": ""my_key,
#     "aws_secret_access_key": "my_secret",
#     "region_name": "my_region"
# }
#
_API_KEYS_PATH = os.path.join("resources", "aws_polly_keys.json")
_api_client = None

# Voices
_DEFAULT_VOICE = "Dora"  # "Karl"
_VOICES = frozenset(("Dora", "Karl"))

# Audio formats
_DEFAULT_AUDIO_FORMAT = "mp3"
_AUDIO_FORMATS = frozenset(("mp3", "ogg_vorbis", "pcm"))

# Text formats
_DEFAULT_TEXT_FORMAT = "text"
_TEXT_FORMATS = frozenset(("text", "ssml"))

# S3 bucket
_S3_KEY_PREFIX = ""
_S3_BUCKET = "greynir-uswest2"


def _intialize_client():
    """ Set up AWS Polly client """
    global _api_client
    if _api_client:
        return _api_client

    # Read AWS Polly API keys from file
    aws_config = None
    try:
        with open(_API_KEYS_PATH) as json_file:
            aws_config = json.load(json_file)
    except FileNotFoundError:
        logging.warning("Unable to read AWS Polly keys")
        return None

    # Return client instance
    return boto3.Session(**aws_config).client("polly")


def get_synthesized_text_url(text, txt_format="text", voice=_DEFAULT_VOICE):
    """ Returns AWS URL to audio file with speech-synthesised text """

    assert txt_format in _TEXT_FORMATS
    assert voice in _VOICES

    client = _intialize_client()  # Set up client lazily
    if not client:
        logging.warning("Unable to instantiate AWS client")
        return None

    # Configure query string parameters for AWS request
    params = {
        # The text to synthesize
        "Text": text,
        # mp3 | ogg_vorbis | pcm
        "OutputFormat": _DEFAULT_AUDIO_FORMAT,
        # Dora or Karl
        "VoiceId": voice,
        # Valid values for mp3 and ogg_vorbis are "8000", "16000", and "22050".
        # The default value is "22050".
        # "SampleRate": "",
        # "text" or "ssml"
        "TextType": "text",
        # Only required for bilingual voices
        # "LanguageCode": "is-IS"
    }

    try:
        url = client.generate_presigned_url(
            ClientMethod="synthesize_speech",
            Params=params,
            ExpiresIn=600,
            HttpMethod="GET",
        )
    except ClientError as e:
        logging.error(e)
        return None

    return url


if __name__ == "__main__":
    """ Test speech synthesis through command line invocation """
    txt = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Góðan daginn, félagi."

    url = get_synthesized_text_url(txt)
    print(url)
