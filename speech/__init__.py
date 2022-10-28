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


    Icelandic text to speech via TTS web services.

"""

from typing import Iterable, Dict, Any
from types import ModuleType

import logging
from inspect import isfunction
import importlib

from utility import GREYNIR_ROOT_DIR, modules_in_dir


DEFAULT_VOICE = "Dora"
VOICES_DIR = GREYNIR_ROOT_DIR / "speech" / "voices"

# Text formats
# For details about SSML markup, see:
# https://developer.amazon.com/en-US/docs/alexa/custom-skills/speech-synthesis-markup-language-ssml-reference.html
DEFAULT_TEXT_FORMAT = "ssml"
SUPPORTED_TEXT_FORMATS = frozenset(("text", "ssml"))
assert DEFAULT_TEXT_FORMAT in SUPPORTED_TEXT_FORMATS

# Audio formats
DEFAULT_AUDIO_FORMAT = "mp3"
SUPPORTED_AUDIO_FORMATS = frozenset(("mp3", "ogg_vorbis", "pcm"))
assert DEFAULT_AUDIO_FORMAT in SUPPORTED_AUDIO_FORMATS


def load_voice_modules() -> Dict[str, ModuleType]:
    """Dynamically load all voice modules, map voice ID
    strings to the relevant modules."""

    v2m = {}
    for modname in modules_in_dir(VOICES_DIR):
        try:
            # Try to import
            m = importlib.import_module(modname)
            voices: Iterable[str] = getattr(m, "VOICES")
            if not voices:
                continue  # No voices declared, skip
            for v in voices:
                v2m[v] = m
        except Exception as e:
            logging.error(f"Error importing voice module {modname}: {e}")

    return v2m


VOICE_TO_MODULE = load_voice_modules()
SUPPORTED_VOICES = frozenset(VOICE_TO_MODULE.keys())
RECOMMENDED_VOICES = frozenset(("Dora", "Karl"))


def _sanitize_args(args: Dict[str, Any]) -> Dict[str, Any]:
    """Make sure arguments to speech synthesis functions are sane."""
    # Make sure we have a valid voice ID
    voice_id = args["voice_id"].lower().capitalize()
    if voice_id not in SUPPORTED_VOICES:
        logging.warning(
            f"Voice '{voice_id}' not in supported voices, reverting to default ({DEFAULT_VOICE})"
        )
        args["voice_id"] = DEFAULT_VOICE
    else:
        args["voice_id"] = voice_id

    # Clamp speed to 50-150% range
    args["speed"] = max(min(1.5, args["speed"]), 0.5)

    return args


def text_to_audio_data(
    text: str,
    text_format: str = DEFAULT_TEXT_FORMAT,
    audio_format: str = DEFAULT_AUDIO_FORMAT,
    voice_id: str = DEFAULT_VOICE,
    speed: float = 1.0,
) -> bytes:
    """Returns audio data for speech-synthesised text."""
    # Fall back to default voice if voice_id param invalid
    if voice_id not in SUPPORTED_VOICES:
        voice_id = DEFAULT_VOICE
    # Create a copy of all function arguments
    args = locals().copy()
    # Find the module that provides this voice
    module = VOICE_TO_MODULE.get(voice_id)
    assert module is not None
    fn = getattr(module, "text_to_audio_data")
    assert isfunction(fn)
    # Call function in module, passing on the arguments
    return fn(**_sanitize_args(args))


def text_to_audio_url(
    text: str,
    text_format: str = DEFAULT_TEXT_FORMAT,
    audio_format: str = DEFAULT_AUDIO_FORMAT,
    voice_id: str = DEFAULT_VOICE,
    speed: float = 1.0,
) -> str:
    """Returns URL to audio of speech-synthesised text."""
    # Fall back to default voice if voice_id param invalid
    if voice_id not in SUPPORTED_VOICES:
        voice_id = DEFAULT_VOICE
    # Create a copy of all function arguments
    args = locals().copy()
    # Find the module that provides this voice
    module = VOICE_TO_MODULE.get(voice_id)
    assert module is not None
    fn = getattr(module, "text_to_audio_url")
    assert isfunction(fn)
    # Call function in module, passing on the arguments
    return fn(**_sanitize_args(args))
