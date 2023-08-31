#!/usr/bin/env python
"""

    Greynir: Natural language processing for Icelandic

    Copyright (C) 2023 Miðeind ehf.

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

from base64 import b64encode
from utility import STATIC_DIR


# Directory for temporary audio files
AUDIO_SCRATCH_DIR = STATIC_DIR / "audio" / "tmp"


# Mime types and suffixes
BINARY_MIMETYPE = "application/octet-stream"
AUDIOFMT_TO_MIMETYPE = {
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "ogg_vorbis": "audio/ogg",
    "pcm": BINARY_MIMETYPE,
    # Uses an Ogg container. See https://www.rfc-editor.org/rfc/rfc7845
    "opus": "audio/ogg",
}

FALLBACK_SUFFIX = "data"
AUDIOFMT_TO_SUFFIX = {
    "mp3": "mp3",
    "wav": "wav",
    "ogg_vorbis": "ogg",
    "pcm": "pcm",
    # Recommended filename extension for Ogg Opus files is '.opus'.
    "opus": "opus",
}


def mimetype_for_audiofmt(fmt: str) -> str:
    """Returns mime type for the given audio format."""
    return AUDIOFMT_TO_MIMETYPE.get(fmt, BINARY_MIMETYPE)


def suffix_for_audiofmt(fmt: str) -> str:
    """Returns file suffix for the given audio format."""
    return AUDIOFMT_TO_SUFFIX.get(fmt, FALLBACK_SUFFIX)


def generate_data_uri(data: bytes, mime_type: str = BINARY_MIMETYPE) -> str:
    """Generate Data URI (RFC2397) from bytes."""
    b64str = b64encode(data).decode("ascii")
    return f"data:{mime_type};base64,{b64str}"


DEFAULT_LOCALE = "is_IS"


# Map locales to a default voice ID
LOCALE_TO_VOICE_ID = {
    "is_IS": "Gudrun",
    "en_US": "Jenny",
    "en_GB": "Abbi",
    "de_DE": "Amala",
    "fr_FR": "Brigitte",
    "da_DK": "Christel",
    "sv_SE": "Sofie",
    "nb_NO": "Finn",
    "no_NO": "Finn",
    "es_ES": "Abril",
    "pl_PL": "Agnieszka",
}
assert DEFAULT_LOCALE in LOCALE_TO_VOICE_ID


def voice_for_locale(locale: str) -> str:
    """Returns default voice ID for the given locale. If locale is not
    supported, returns the default voice ID for the default locale."""
    vid = LOCALE_TO_VOICE_ID.get(locale)
    return vid or LOCALE_TO_VOICE_ID[DEFAULT_LOCALE]
