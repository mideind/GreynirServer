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


    Icelandic-language text to speech via Tiro's text to speech API.

"""

from typing import Optional

import logging

from . import generate_data_uri, strip_markup, mimetype4audiofmt

import requests


NAME = "Tiro"
VOICES = frozenset(("Alfur", "Dilja"))
AUDIO_FORMATS = frozenset(("mp3", "pcm"))


_TIRO_TTS_URL = "https://tts.tiro.is/v0/speech"


def _tiro_synthesized_text_data(
    text: str,
    text_format: str,
    audio_format: str,
    voice_id: str,
    speed: float = 1.0,
) -> Optional[bytes]:
    """Feeds text to Tiro's TTS API and returns audio data received from server."""

    # No proper support for SSML yet in Tiro's API
    text = strip_markup(text)
    text_format = "text"

    jdict = {
        "Engine": "standard",
        "LanguageCode": "is-IS",
        "OutputFormat": audio_format,
        # "SampleRate": "22050",
        "Text": text,
        "TextType": "text",
        "VoiceId": voice_id,
    }

    try:
        r = requests.post(_TIRO_TTS_URL, json=jdict)
        if r.status_code != 200:
            raise Exception(
                f"Received HTTP status code {r.status_code} from {NAME} server"
            )
        return r.content
    except Exception as e:
        logging.error(f"Error communicating with Tiro API at {_TIRO_TTS_URL}: {e}")


def _tiro_synthesized_text_url(
    text: str,
    text_format: str,
    audio_format: str,
    voice_id: str,
    speed: float = 1.0,
) -> Optional[str]:
    """Returns Tiro (data) URL for speech-synthesised text."""

    data = _tiro_synthesized_text_data(**locals())
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
    return _tiro_synthesized_text_data(**locals())


def text_to_audio_url(
    text: str,
    text_format: str,
    audio_format: str,
    voice_id: str,
    speed: float,
) -> Optional[str]:
    """Returns URL to audio of speech-synthesised text."""
    # Pass all arguments on to another function
    return _tiro_synthesized_text_url(**locals())
