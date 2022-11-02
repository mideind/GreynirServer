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

import re
from base64 import b64encode


# Mime types and suffixes
BINARY_MIMETYPE = "application/octet-stream"
AUDIOFMT_TO_MIMETYPE = {
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "ogg_vorbis": "audio/ogg",
    "pcm": BINARY_MIMETYPE,
}

AUDIOFMT_TO_SUFFIX = {
    "mp3": "mp3",
    "wav": "wav",
    "ogg_vorbis": "ogg",
    "pcm": "pcm",
}


def mimetype_for_audiofmt(fmt: str) -> str:
    return AUDIOFMT_TO_MIMETYPE.get(fmt, BINARY_MIMETYPE)


def suffix_for_audiofmt(fmt: str) -> str:
    return AUDIOFMT_TO_SUFFIX.get(fmt, "")


def strip_markup(text: str) -> str:
    """Remove SSML markup tags from a string"""
    return re.sub(r"<.*?>", "", text)


def generate_data_uri(data: bytes, mime_type=BINARY_MIMETYPE) -> str:
    """Generate Data URI (RFC2397) from bytes."""
    b64str = b64encode(data).decode("ascii")
    return f"data:{mime_type};base64,{b64str}"
