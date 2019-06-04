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


"""

import sys
import json
import logging
from pprint import pprint

import boto3

# The AWS Polly API access keys (you must obtain your own key if you want to use this code)
_API_KEYS_PATH = "resources/aws_polly_keys.json"
_api_client = None

_VOICE_NAME = "Dora"  # "Karl"
_AUDIO_FORMAT = "mp3"
_S3_KEY_PREFIX = ""
_S3_BUCKET = "greynir-uswest2"


def _intialize_client():
    """ Set up AWS Polly client """
    global _api_client
    if _api_client:
        return _api_client
    else:
        # Read AWS Polly API keys from file
        aws_config = None
        try:
            with open(_API_KEYS_PATH) as json_file:
                aws_config = json.load(json_file)
        except FileNotFoundError:
            logging.warning("Unable to read AWS Polly keys")

        # Create client instance
        _api_client = boto3.Session(**aws_config).client("polly")

    return _api_client


def synthesize_text(text):
    """ Returns URL to audio file with speech-synthesised text """
    client = _intialize_client()
    if client:
        try:
            response = client.start_speech_synthesis_task(
                VoiceId=_VOICE_NAME,
                OutputS3BucketName=_S3_BUCKET,
                OutputS3KeyPrefix=_S3_KEY_PREFIX,
                OutputFormat=_AUDIO_FORMAT,
                Text=text,
            )

            task_id = response["SynthesisTask"]["TaskId"]

            task_status = client.get_speech_synthesis_task(TaskId=task_id)
            pprint(task_status)
            return task_status["SynthesisTask"]["OutputUri"]
        except Exception as e:
            logging.warning("Exception synthesizing text: {}".format(e))

    return None


if __name__ == "__main__":
    """ Test speech synthesis through command line invocation """
    txt = sys.argv[1] if len(sys.argv) > 1 else "Góðan daginn, félagi."

    url = synthesize_text(txt)
    print(url)
