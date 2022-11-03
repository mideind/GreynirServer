#!/usr/bin/env python
"""

    Greynir: Natural language processing for Icelandic

    Copyright (C) 2022 Miðeind ehf.

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


    Icelandic-language text to speech via the MS Azure Speech API.

"""

from typing import Optional, Tuple

import os
import logging
import json

import azure.cognitiveservices.speech as speechsdk

from . import generate_data_uri, strip_markup, mimetype_for_audiofmt
from utility import RESOURCES_DIR


NAME = "Azure"
AUDIO_FORMATS = frozenset(("mp3", "pcm", "opus"))
VOICES = frozenset(("Gudrun", "Gunnar"))
_VOICE_TO_ID = {"Gudrun": "is-IS-GudrunNeural", "Gunnar": "is-IS-GunnarNeural"}
_DEFAULT_VOICE_ID = "is-IS-GudrunNeural"


# The Azure Speech API access key
# You must obtain your own key if you want to use this code
# JSON format is the following:
# {
#     "key": ""my_key",
#     "region": "my_region",
# }
#
_AZURE_KEYFILE_NAME = "AzureSpeechServerKey.json"

_AZURE_API_KEY_PATH = str(RESOURCES_DIR / _AZURE_KEYFILE_NAME)

_AZURE_API_KEY = ""
_AZURE_API_REGION = ""


def _azure_api_key() -> Tuple[str, str]:
    """Lazy-load API key and region from JSON and return as tuple."""
    global _AZURE_API_KEY
    global _AZURE_API_REGION

    if _AZURE_API_KEY and _AZURE_API_REGION:
        return (_AZURE_API_KEY, _AZURE_API_REGION)

    try:
        with open(_AZURE_API_KEY_PATH) as json_file:
            js = json.load(json_file)
            _AZURE_API_KEY = js["key"]
            _AZURE_API_REGION = js["region"]
    except Exception as e:
        logging.warning(f"Unable to read Azure Speech API credentials: {e}")

    return (_AZURE_API_KEY, _AZURE_API_REGION)


def text_to_audio_data(
    text: str,
    text_format: str,
    audio_format: str,
    voice_id: str,
    speed: float = 1.0,
) -> Optional[bytes]:
    """Feeds text to Azure Speech API and returns audio data received from server."""

    # Text only for now, although Azure supports SSML
    # text_format = "text"
    if audio_format not in AUDIO_FORMATS:
        logging.warn(
            f"Unsupported audio format for Azure speech synthesis: {audio_format}."
            " Falling back to mp3"
        )
        audio_format = "mp3"

    aof = speechsdk.SpeechSynthesisOutputFormat
    fmt2enum = {
        "mp3": aof.Audio16Khz32KBitRateMonoMp3,
        "pcm": aof.Raw16Khz16BitMonoPcm,
        "opus": aof.Ogg16Khz16BitMonoOpus,
    }

    try:
        # Configure speech synthesis
        (key, region) = _azure_api_key()
        speech_config = speechsdk.SpeechConfig(subscription=key, region=region)
        speech_config.speech_synthesis_voice_name = (
            _VOICE_TO_ID.get(voice_id) or _DEFAULT_VOICE_ID
        )
        fmt = fmt2enum.get(audio_format, aof.Audio16Khz32KBitRateMonoMp3)
        speech_config.set_speech_synthesis_output_format(fmt)

        # Init synthesizer, feed it with text and get result
        synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=speech_config, audio_config=None
        )
        result = synthesizer.speak_text(text)

        # Check result
        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            return result.audio_data
        elif result.reason == speechsdk.ResultReason.Canceled:
            cancellation_details = result.cancellation_details
            logging.error(
                "Speech synthesis canceled: {}".format(cancellation_details.reason)
            )
            if cancellation_details.reason == speechsdk.CancellationReason.Error:
                logging.error(
                    "Azure TTS error: {}".format(cancellation_details.error_details)
                )
    except Exception as e:
        logging.error(f"Error communicating with Azure Speech API: {e}")

    return None


def text_to_audio_url(
    text: str,
    text_format: str,
    audio_format: str,
    voice_id: str,
    speed: float = 1.0,
) -> Optional[str]:
    """Returns data URL for speech-synthesised text."""

    data = text_to_audio_data(**locals())
    if not data:
        return None

    # Generate Data URI from the bytes received
    mime_type = mimetype_for_audiofmt(audio_format)
    data_uri = generate_data_uri(data, mime_type=mime_type)

    return data_uri
