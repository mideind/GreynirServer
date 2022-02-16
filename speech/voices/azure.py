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

from . import generate_data_uri, strip_markup, mimetype4audiofmt

import azure.cognitiveservices.speech as speechsdk


NAME = "Azure"
VOICES = frozenset(("Gudrun", "Gunnar"))
VOICE_TO_ID = {"Gudrun": "is-IS-GudrunNeural", "Gunnar": "is-IS-GunnarNeural"}
AUDIO_FORMATS = frozenset(("mp3"))


# The Azure Speech API access key
# You must obtain your own key if you want to use this code
# JSON format is the following:
# {
#     "key": ""my_key,
#     "region": "my_region",
# }
#
_AZURE_KEYFILE_NAME = "AzureSpeechServerKey.json"
_AZURE_API_KEY_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "resources", _AZURE_KEYFILE_NAME
)
_AZURE_API_KEY: str = ""
_AZURE_API_REGION: str = ""


def _azure_api_key() -> Tuple:
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
    except FileNotFoundError:
        logging.warning("Unable to read Azure Speech API credentials")

    return (_AZURE_API_KEY, _AZURE_API_REGION)


def _azure_synthesized_text_data(
    text: str,
    text_format: str,
    audio_format: str,
    voice_id: str,
    speed: float = 1.0,
) -> Optional[bytes]:
    """Feeds text to Azure Speech API and returns audio data received from server."""

    # Text only for now, although Azure supports SSML
    text = strip_markup(text)
    text_format = "text"

    try:
        # Configure speech synthesis
        (key, region) = _azure_api_key()
        speech_config = speechsdk.SpeechConfig(subscription=key, region=region)
        speech_config.speech_synthesis_voice_name = VOICE_TO_ID[voice_id]
        # We only support MP3 for now, although the API supports other formats
        fmt = speechsdk.SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3
        speech_config.set_speech_synthesis_output_format(fmt)

        # Init synthesizer and feed it with text
        synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config)
        result = synthesizer.speak_text(text)

        # Read audio from stream into buffer, append to bytearray containing total audio data
        stream = speechsdk.AudioDataStream(result)
        audio_data = bytearray()
        audio_buffer = bytes(32000)  # 32 KB buffer
        filled_size = stream.read_data(audio_buffer)
        while filled_size > 0:
            audio_data += audio_buffer[:filled_size]
            filled_size = stream.read_data(audio_buffer)

        return audio_data
    except Exception as e:
        logging.error(f"Error communicating with Azure Speech API: {e}")


def _azure_synthesized_text_url(
    text: str,
    text_format: str,
    audio_format: str,
    voice_id: str,
    speed: float = 1.0,
) -> Optional[str]:
    """Returns data URL for speech-synthesised text."""

    data = _azure_synthesized_text_data(**locals())
    if not data:
        return None

    # Generate Data URI from the bytes received
    mime_type = mimetype4audiofmt(audio_format)
    data_uri = generate_data_uri(data, mime_type=mime_type)

    return data_uri


def text_to_audio_data(
    text: str,
    text_format: str,
    audio_format: str,
    voice_id: str,
    speed: float,
) -> Optional[bytes]:
    """Returns audio data for speech-synthesised text."""
    # Pass all arguments on to another function
    return _azure_synthesized_text_data(**locals())


def text_to_audio_url(
    text: str,
    text_format: str,
    audio_format: str,
    voice_id: str,
    speed: float,
) -> Optional[str]:
    """Returns URL to audio of speech-synthesised text."""
    # Pass all arguments on to another function
    return _azure_synthesized_text_url(**locals())
