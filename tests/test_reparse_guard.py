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


    Tests for the reparse guard in Article.parse(): a reparse must never
    replace an existing parse with an empty or far smaller one, which is what
    happens when the current scrape helper no longer matches the stored HTML
    of an older article. A refused reparse leaves the article untouched and
    is recorded in the reparse_refusals table.

"""

import os
import sys
from datetime import datetime, timezone

import pytest

# Shenanigans to enable Pytest to discover modules in the
# main workspace directory (the parent of /tests)
basepath, _ = os.path.split(os.path.realpath(__file__))
mainpath = os.path.join(basepath, "..")
if mainpath not in sys.path:
    sys.path.insert(0, mainpath)

from settings import Settings  # noqa
from db import SessionContext  # noqa
from db.models import Article as ArticleRow, ReparseRefusal  # noqa
from article import Article, REPARSE_MIN_SENTENCE_RATIO  # noqa

URL = "https://reparse-guard.test/frett/1"

GOOD_HTML = """<html><body>
<p>Ríkisstjórnin samþykkti frumvarpið í gær. Ráðherrann sagði að málið væri brýnt.</p>
<p>Seðlabankinn lækkaði vexti í morgun. Verðbólgan hefur minnkað á árinu.</p>
<p>Veðrið var gott í Reykjavík í dag. Margir fóru í sund eftir vinnu.</p>
</body></html>"""

# What an extractor that no longer matches the markup yields: nothing...
EMPTY_HTML = "<html><body></body></html>"
# ...or page chrome that happens to tokenize, and even parse, as a sentence
CHROME_HTML = "<html><body><p>Þetta er forsíðan.</p></body></html>"


def test_reparse_is_degraded():
    deg = Article.reparse_is_degraded
    # An article with nothing parsed has nothing to protect
    assert not deg(0, 0, 0, 0)
    assert not deg(10, 0, 0, 0)
    assert not deg(10, 0, 3, 3)
    # Parsed sentences are never replaced by none at all
    assert deg(10, 8, 0, 0)
    assert deg(10, 8, 10, 0)
    assert deg(1, 1, 0, 0)
    # ...nor by a result with far fewer sentences
    assert deg(10, 8, 4, 4)
    assert deg(40, 35, 3, 3)
    # Ordinary variation between parser versions is fine
    assert not deg(10, 8, 10, 9)
    assert not deg(10, 8, 10, 7)
    assert not deg(10, 8, 9, 8)
    assert not deg(10, 8, 5, 4)
    assert not deg(1, 1, 1, 1)
    assert 0.0 < REPARSE_MIN_SENTENCE_RATIO < 1.0


def _row(session) -> ArticleRow:
    session.expire_all()
    return session.query(ArticleRow).filter(ArticleRow.url == URL).one()


def _set_html(session, html: str) -> None:
    _row(session).html = html
    session.flush()


def _refusal(session):
    session.expire_all()
    return session.query(ReparseRefusal).filter(ReparseRefusal.url == URL).one_or_none()


@pytest.mark.skipif(
    Settings.DB_PORT == 5432,
    reason="writes to the database; only run against a throwaway cluster",
)
def test_reparse_guard():
    with SessionContext(commit=False) as session:
        try:
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            session.add(
                ArticleRow(
                    url=URL, heading="Prófun", author="", timestamp=now,
                    authority=1.0, scraped=now, html=GOOD_HTML,
                )
            )
            session.flush()

            # The first parse has nothing to protect and is stored
            a = Article.load_from_url(URL, session)
            assert a is not None
            assert a.parse(session) is True
            row = _row(session)
            good_tree, good_tokens = row.tree, row.tokens
            good_version, good_parsed_ts = row.parser_version, row.parsed
            good_ns, good_np = row.num_sentences, row.num_parsed
            assert good_ns == 6 and good_np >= 4
            assert good_tree and good_tokens
            assert _refusal(session) is None

            for bad_html in (EMPTY_HTML, CHROME_HTML):
                # The stored HTML now yields (almost) nothing with the
                # current extractor: the reparse must be refused...
                _set_html(session, bad_html)
                a = Article.load_from_url(URL, session)
                assert a is not None
                assert a.parse(session) is False
                # ...leaving the article object as it was...
                assert a.num_sentences == good_ns and a.num_parsed == good_np
                assert a.tree == good_tree and a.tokens == good_tokens
                # ...and the stored article untouched
                row = _row(session)
                assert row.tree == good_tree and row.tokens == good_tokens
                assert row.num_sentences == good_ns and row.num_parsed == good_np
                assert row.parser_version == good_version
                assert row.parsed == good_parsed_ts
                # The refusal is on record, one row per article
                f = _refusal(session)
                assert f is not None
                assert (f.old_sentences, f.old_parsed) == (good_ns, good_np)
                assert f.new_sentences <= 1 and f.new_parsed <= 1
                assert f.new_sentences == (0 if bad_html is EMPTY_HTML else 1)
                # Must equal what scraper.py --reparse compares against,
                # or refused articles are selected again on every run
                assert f.parser_version == Article.parser_version()

            # With HTML that the extractor handles again, the reparse goes
            # through and clears the refusal
            _set_html(session, GOOD_HTML)
            a = Article.load_from_url(URL, session)
            assert a is not None
            assert a.parse(session) is True
            row = _row(session)
            assert row.num_sentences == good_ns and row.num_parsed == good_np
            assert row.parsed >= good_parsed_ts
            assert _refusal(session) is None

            # A forced reparse stores the far smaller result. This is for
            # articles whose existing parse is bloated by page furniture
            # that a corrected scrape helper now leaves out.
            _set_html(session, CHROME_HTML)
            a = Article.load_from_url(URL, session)
            assert a is not None
            assert a.parse(session) is False
            assert _refusal(session) is not None
            a = Article.load_from_url(URL, session)
            assert a is not None
            assert a.parse(session, force=True) is True
            row = _row(session)
            assert row.num_sentences == 1
            assert _refusal(session) is None
        finally:
            session.rollback()
