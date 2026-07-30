"""

    Greynir: Natural language processing for Icelandic

    Shared pytest fixtures.

    Copyright (C) 2026 Miðeind ehf.

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


    Speech synthesis is stubbed out for the whole test suite.

    The query tests exercise voice answers heavily, but every assertion they
    make is about the *text* of the answer -- transcription, number expansion,
    voice_id and voice_locale. Not one of them inspects the synthesised audio;
    routes/api.py only takes the returned path and turns it into a URL. The
    real call nevertheless performed a network round trip to Azure Speech for
    every voice query, which coupled the suite's pass rate to a third party's
    latency.

    That is not hypothetical. On 2026-07-30 all three CI legs failed with 24
    instances of "TTS with Azure failed: Timeout while synthesizing", and a
    rerun failed a completely different random subset of tests with the same
    error. No assertion failures either time. A build that reddens for reasons
    unrelated to the diff trains people to ignore red builds, which is the
    expensive part.

    Set GREYNIR_TEST_REAL_TTS=1 to restore the real Azure/Polly path, e.g. when
    deliberately testing the speech integration itself.

"""

from typing import Any, Iterator

import os
import uuid

import pytest


def _use_real_tts() -> bool:
    return bool(os.environ.get("GREYNIR_TEST_REAL_TTS"))


@pytest.fixture(autouse=True)
def stub_tts(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Replace speech synthesis with a stub returning a plausible file path.

    Patches the name bound in routes.api rather than icespeak itself, so the
    substitution is visible exactly where the application calls it and nothing
    else in icespeak is disturbed.
    """
    if _use_real_tts():
        yield
        return

    # Imported here rather than at module scope, deliberately. Both routes and
    # icespeak are heavy application imports, and icespeak in particular
    # constructs its pydantic Settings at import time. Under pydantic-settings
    # 2.2+ that construction raises if the working directory holds a .env
    # containing any key not prefixed ICESPEAK_ -- an OPENAI_API_KEY in a
    # developer's local .env is enough. Keeping these imports out of conftest's
    # module scope means such a failure cannot break collection of the many
    # tests that never touch speech at all.
    import routes.api
    from icespeak.tts import TTSOutput

    from utility import TTS_AUDIO_DIR

    def _fake_tts_to_file(text: str, *args: Any, **kwargs: Any) -> "TTSOutput":
        # The path is never opened -- routes.api calls .as_uri() on it and
        # rewrites that into an http(s) URL. Keep it under TTS_AUDIO_DIR so the
        # 'static/audio/' rewrite in _audio_file_url_to_host_url still applies,
        # exercising the same code path as a real synthesis would.
        return TTSOutput(file=TTS_AUDIO_DIR / f"{uuid.uuid4()}.mp3", text=text)

    monkeypatch.setattr(routes.api, "tts_to_file", _fake_tts_to_file)
    yield
