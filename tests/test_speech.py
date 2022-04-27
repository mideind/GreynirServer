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


    Tests for speech-synthesis-related code in the Greynir repo.

"""

import os
import sys

import requests

from speech import text_to_audio_url


# Shenanigans to enable Pytest to discover modules in the
# main workspace directory (the parent of /tests)
basepath, _ = os.path.split(os.path.realpath(__file__))
mainpath = os.path.join(basepath, "..")
if mainpath not in sys.path:
    sys.path.insert(0, mainpath)


def test_speech_synthesis():
    """Test basic speech synthesis functionality."""

    url = text_to_audio_url(
        "Prufa",
        text_format="text",
        audio_format="mp3",
        voice_id="Dora",
    )

    assert url and url.startswith("http")

    # Make request
    r = requests.get(url)

    # Make sure we're getting an MP3 audio data response
    assert r.headers.get("Content-Type") == "audio/mpeg"

    # Audio data should be at least 1 KB in size
    assert len(r.content) > 1000
