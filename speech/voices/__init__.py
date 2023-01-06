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


"""

from base64 import b64encode


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
