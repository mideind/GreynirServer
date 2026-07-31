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


    Tests for the summary authorization tokens that gate paid LLM calls
    behind /summary.api.

"""

import os
import sys
import time
import importlib.util
from datetime import datetime, timedelta, timezone
from types import ModuleType
from typing import Optional


# Shenanigans to enable Pytest to discover modules in the
# main workspace directory (the parent of /tests)
basepath, _ = os.path.split(os.path.realpath(__file__))
mainpath = os.path.join(basepath, "..")
if mainpath not in sys.path:
    sys.path.insert(0, mainpath)


_MODULE_PATH = os.path.join(mainpath, "routes", "summary_token.py")

_UUID = "824d5c50-7000-11ee-a1b2-0242ac120002"
_OTHER_UUID = "c2a328c8-7000-11ee-a1b2-0242ac120002"


def _load(secret: Optional[str], max_age_days: Optional[str] = None) -> ModuleType:
    """Load a fresh copy of the module with the given key in the
    environment. A fresh copy each time because the module caches the key
    in a global after first use, exactly as it does in a live worker.
    Imported by path rather than as routes.summary_token: importing the
    routes package runs "from .api import *", which pulls in icespeak and
    the whole app."""
    if secret is None:
        os.environ.pop("GREYNIR_SUMMARY_SECRET", None)
    else:
        os.environ["GREYNIR_SUMMARY_SECRET"] = secret
    if max_age_days is None:
        os.environ.pop("GREYNIR_SUMMARY_MAX_AGE_DAYS", None)
    else:
        os.environ["GREYNIR_SUMMARY_MAX_AGE_DAYS"] = max_age_days
    spec = importlib.util.spec_from_file_location("summary_token", _MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_summary_token_roundtrip():
    """A freshly minted token authorizes the article it was minted for."""
    m = _load("test-secret")
    token = m.make_summary_token(_UUID)
    assert token, "a token should be minted when a key is configured"
    assert m.check_summary_token(_UUID, token)


def test_summary_token_is_bound_to_one_article():
    """A token scraped from one page must not work on another article."""
    m = _load("test-secret")
    token = m.make_summary_token(_UUID)
    assert not m.check_summary_token(_OTHER_UUID, token)


def test_summary_token_rejects_tampering():
    """Neither half of the token may be edited."""
    m = _load("test-secret")
    expiry, _, signature = m.make_summary_token(_UUID).partition(".")

    # A forged later expiry breaks the MAC, since the expiry is signed
    forged = f"{int(expiry) + 86400}.{signature}"
    assert not m.check_summary_token(_UUID, forged)

    # An edited signature fails too
    flipped = "B" if signature[0] != "B" else "C"
    assert not m.check_summary_token(_UUID, flipped + signature[1:])


def test_summary_token_expires():
    """An expired token is refused."""
    m = _load("test-secret")
    stale_expiry = int(time.time()) - 1
    stale = f"{stale_expiry}.{m._sign(_UUID, stale_expiry, b'test-secret')}"
    # Correctly signed, so this proves expiry is what rejects it
    assert not m.check_summary_token(_UUID, stale)


def test_summary_token_rejects_malformed_input():
    """Garbage on a public endpoint returns False rather than raising."""
    m = _load("test-secret")
    for bad in (None, "", ".", "abc", "abc.def", "..", "9999999999.", "x.y.z"):
        assert not m.check_summary_token(_UUID, bad)


def test_summary_token_fails_closed_without_a_key():
    """With no key configured nothing is minted and nothing validates, so
    summaries are served from cache but never generated."""
    m = _load(None)
    assert m.make_summary_token(_UUID) == ""
    assert not m.check_summary_token(_UUID, "anything")

    # A token minted by a properly configured worker must not validate either
    configured = _load("test-secret")
    token = configured.make_summary_token(_UUID)
    unconfigured = _load(None)
    assert not unconfigured.check_summary_token(_UUID, token)


def _ago(**kwargs) -> datetime:
    """A tz-aware timestamp the given interval in the past."""
    return datetime.now(timezone.utc) - timedelta(**kwargs)


def test_article_age_window():
    """Recent articles may be generated for; older ones may not."""
    m = _load("test-secret")
    assert m.article_is_recent(_ago(hours=1))
    assert m.article_is_recent(_ago(days=6, hours=23))
    assert not m.article_is_recent(_ago(days=7, hours=1))
    assert not m.article_is_recent(_ago(days=400))


def test_article_age_window_is_configurable():
    """The window can be widened or narrowed without a code change."""
    m = _load("test-secret", max_age_days="30")
    assert m.article_is_recent(_ago(days=29))
    assert not m.article_is_recent(_ago(days=31))

    # Zero disables generation entirely - an emergency brake
    m = _load("test-secret", max_age_days="0")
    assert not m.article_is_recent(_ago(hours=1))

    # Garbage falls back to the default rather than crashing or opening up
    m = _load("test-secret", max_age_days="not-a-number")
    assert m.article_is_recent(_ago(days=1))
    assert not m.article_is_recent(_ago(days=8))


def test_article_age_rejects_unknown_timestamp():
    """An article we cannot date is treated as too old, not as recent."""
    m = _load("test-secret")
    assert not m.article_is_recent(None)


def test_article_age_accepts_naive_timestamps():
    """A naive datetime must not raise on comparison. Articles read through
    DateTimeUtc carry UTC, but nothing guarantees that for every caller."""
    m = _load("test-secret")
    naive_recent = datetime.utcnow() - timedelta(hours=1)
    naive_old = datetime.utcnow() - timedelta(days=400)
    assert m.article_is_recent(naive_recent)
    assert not m.article_is_recent(naive_old)


def test_summary_token_requires_matching_key():
    """Workers must share a key; a token from a different key is refused.
    This is why the key comes from the environment rather than being
    generated per process."""
    a = _load("secret-one")
    token = a.make_summary_token(_UUID)
    b = _load("secret-two")
    assert not b.check_summary_token(_UUID, token)
