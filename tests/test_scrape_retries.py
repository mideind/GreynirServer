"""

    Greynir: Natural language processing for Icelandic

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


    Tests for the retrying of failed article fetches: an article that
    cannot be fetched is attempted again at growing intervals, a bounded
    number of times, and its row is left alone in the meantime.

"""

import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import pytest

# Shenanigans to enable Pytest to discover modules in the
# main workspace directory (the parent of /tests)
basepath, _ = os.path.split(os.path.realpath(__file__))
mainpath = os.path.join(basepath, "..")
if mainpath not in sys.path:
    sys.path.insert(0, mainpath)

from settings import Settings  # noqa
from db import SessionContext  # noqa
from db.models import Article as ArticleRow, Root, ScrapeFailure  # noqa
from fetcher import Fetcher  # noqa
from scraper import (  # noqa
    Scraper,
    SCRAPE_MAX_ATTEMPTS,
    SCRAPE_RETRY_BASE,
    scrape_retry_delay,
)

DOMAIN = "scrape-retries.test"
URL = f"https://{DOMAIN}/frett/1"
URL2 = f"https://{DOMAIN}/frett/2"
HTML = "<html><head><title>Frétt</title></head><body><p>Þetta er frétt.</p></body></html>"

throwaway_db_only = pytest.mark.skipif(
    Settings.DB_PORT == 5432,
    reason="writes to the database; only run against a throwaway cluster",
)


def test_scrape_retry_delay():
    delays = [scrape_retry_delay(n) for n in range(1, SCRAPE_MAX_ATTEMPTS)]
    # The wait doubles after each failed attempt...
    assert delays[0] == SCRAPE_RETRY_BASE
    for shorter, longer in zip(delays, delays[1:]):
        assert shorter is not None and longer is not None
        assert longer == 2 * shorter
    # ...and there is none after the last one
    assert scrape_retry_delay(SCRAPE_MAX_ATTEMPTS) is None
    assert scrape_retry_delay(SCRAPE_MAX_ATTEMPTS + 1) is None
    # The whole effort is bounded: a handful of attempts over a few days
    assert 3 <= SCRAPE_MAX_ATTEMPTS <= 10
    total = sum((d for d in delays if d is not None), timedelta())
    assert timedelta(days=1) < total < timedelta(days=4)
    # The first retry is due at the next half-hourly run of the scraper
    assert SCRAPE_RETRY_BASE <= timedelta(minutes=30)


def _failure(session: Any, url: str = URL) -> Optional[ScrapeFailure]:
    session.expire_all()
    return session.query(ScrapeFailure).filter(ScrapeFailure.url == url).one_or_none()


def _due(session: Any, now: datetime) -> set:
    return {
        a.url
        for a in Scraper.unscraped_articles(session, now)
        if a.url in (URL, URL2)
    }


@throwaway_db_only
def test_failures_are_retried_with_backoff_and_then_given_up():
    t0 = datetime(2026, 11, 11, 12, 0, tzinfo=timezone.utc)
    with SessionContext(commit=False) as session:
        try:
            root = Root(domain=DOMAIN, url=f"https://{DOMAIN}/", description="Prófun")
            session.add(root)
            session.flush()
            session.add(ArticleRow(url=URL, root_id=root.id))
            session.add(ArticleRow(url=URL2, root_id=root.id))
            session.flush()

            # Articles that have never been attempted are due at once
            assert _due(session, t0) == {URL, URL2}

            now = t0
            for attempt in range(1, SCRAPE_MAX_ATTEMPTS):
                next_attempt = Scraper.note_scrape_failure(session, URL, now)
                delay = scrape_retry_delay(attempt)
                assert delay is not None and next_attempt == now + delay
                f = _failure(session)
                assert f is not None
                assert f.attempts == attempt
                assert f.first_failed == t0 and f.last_failed == now
                assert f.next_attempt == next_attempt
                # Not attempted again until the wait is over; the other
                # article is not affected
                assert _due(session, now) == {URL2}
                assert _due(session, next_attempt - timedelta(seconds=1)) == {URL2}
                assert _due(session, next_attempt) == {URL, URL2}
                now = next_attempt + timedelta(minutes=3)

            # After the last attempt, the article is never due again
            assert Scraper.note_scrape_failure(session, URL, now) is None
            f = _failure(session)
            assert f is not None
            assert f.attempts == SCRAPE_MAX_ATTEMPTS and f.next_attempt is None
            assert _due(session, now + timedelta(days=3650)) == {URL2}
            # ...unless its failure row is deleted
            session.delete(f)
            session.flush()
            assert _due(session, now) == {URL, URL2}
        finally:
            session.rollback()


@throwaway_db_only
def test_scrape_article_keeps_the_row_on_failure(monkeypatch: pytest.MonkeyPatch):
    pages: Dict[str, Optional[str]] = {URL: None}
    monkeypatch.setattr(Fetcher, "raw_fetch_url", staticmethod(lambda url: pages[url]))
    helper: Any = Fetcher  # Not used, except for skip_url()
    monkeypatch.setattr(Fetcher, "skip_url", staticmethod(lambda url: False), raising=False)

    def row(session: Any) -> ArticleRow:
        session.expire_all()
        return session.query(ArticleRow).filter(ArticleRow.url == URL).one()

    # scrape_article() commits in its own session, so do the same here
    with SessionContext(commit=True) as session:
        root = Root(
            domain=DOMAIN, url=f"https://{DOMAIN}/", description="Prófun",
            scr_module="scrapers.default", scr_class="ScrapeHelper",
        )
        session.add(root)
        session.flush()
        root_id = root.id
        session.add(ArticleRow(url=URL, root_id=root_id))
    try:
        scraper = Scraper()
        with SessionContext(commit=False) as session:
            # A failed fetch leaves the row as it was, still attached to
            # its root, and is noted for another attempt
            for attempt in (1, 2):
                scraper.scrape_article(URL, helper)
                r = row(session)
                assert r.root_id == root_id and r.scraped is None and r.html is None
                f = _failure(session)
                assert f is not None and f.attempts == attempt
                assert f.next_attempt is not None and f.next_attempt > f.last_failed

            # When the fetch succeeds, the article is stored
            # and the failures are forgotten
            pages[URL] = HTML
            scraper.scrape_article(URL, helper)
            r = row(session)
            assert r.html == HTML and r.scraped is not None
            assert _failure(session) is None
            assert URL not in _due(session, datetime.now(timezone.utc))
    finally:
        with SessionContext(commit=True) as session:
            session.query(ScrapeFailure).filter(ScrapeFailure.url == URL).delete()
            session.query(ArticleRow).filter(ArticleRow.url == URL).delete()
            session.query(Root).filter(Root.domain == DOMAIN).delete()
