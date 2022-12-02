"""

    Greynir: Natural language processing for Icelandic

    Scraper database queries

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


    This module wraps a number of raw SQL queries using SQLAlchemy.

"""

from typing import Any, Iterable, Optional, Tuple, Union, cast

from datetime import datetime

from . import SessionContext, Session


ArticleListItem = Tuple[str, str, datetime, str, str]
ChartQueryItem = Tuple[str, int, int, int]
RelatedWordsItem = Tuple[str, str, int]
BestAuthorsItem = Tuple[str, int, int, int, float]
QueryCountItem = Tuple[int]


class _BaseQuery:

    _Q = ""

    def __init__(self) -> None:
        pass

    def execute_q(self, session: Session, q: str, **kwargs: Any) -> Iterable[Any]:
        """Execute the given query and return the result from fetchall()"""
        return cast(Iterable[Any], cast(Any, session).execute(q, kwargs).fetchall())

    def execute(self, session: Session, **kwargs: Any) -> Iterable[Any]:
        """Execute the default query and return the result from fetchall()"""
        return cast(
            Iterable[Any], cast(Any, session).execute(self._Q, kwargs).fetchall()
        )

    def scalar(self, session: Session, **kwargs: Any) -> Union[int, float]:
        """Execute the query and return the result from scalar()"""
        return cast(Union[int, float], cast(Any, session).scalar(self._Q, kwargs))


class GenderQuery(_BaseQuery):
    """A query for gender representation in the persons table."""

    _Q = """
        select domain,
            sum(case when gender = 'kk' then cnt else 0 end) as kk,
            sum(case when gender = 'kvk' then cnt else 0 end) as kvk,
            sum(case when gender = 'hk' then cnt else 0 end) as hk,
            sum(cnt) as total
            from (
                select r.domain, p.gender, sum(1) as cnt
                    from persons as p, articles as a, roots as r
                    where p.article_url = a.url and a.root_id = r.id and r.visible
                    group by r.domain, p.gender
            ) as q
            group by domain
            order by domain;
        """


class StatsQuery(_BaseQuery):
    """A query for statistics on articles."""

    _Q = """
        select r.domain,
            r.scrape as enabled,
            sum(1) as art,
            coalesce(sum(a.num_sentences),0) as sent,
            coalesce(sum(a.num_parsed),0) as parsed
            from articles as a, roots as r
            where a.root_id = r.id and r.visible
            group by r.domain, r.scrape
            order by r.domain;
        """


class ChartsQuery(_BaseQuery):
    """Statistics on article, sentence and parse count
    for all sources for a given time period."""

    _Q = """
        select r.description AS name,
            count(a.id) AS cnt,
            coalesce(sum(a.num_sentences),0) as sent,
            coalesce(sum(a.num_parsed),0) as parsed
            from roots as r
            left join articles as a on r.id = a.root_id
            and a.timestamp >= :start and a.timestamp < :end
            where r.visible and r.scrape
            group by name
            order by name
        """

    @classmethod
    def period(
        cls, start: datetime, end: datetime, enclosing_session: Optional[Session] = None
    ) -> Iterable[ChartQueryItem]:
        r: Iterable[ChartQueryItem] = []
        with SessionContext(session=enclosing_session, read_only=True) as session:
            r = cast(
                Iterable[ChartQueryItem], cls().execute(session, start=start, end=end)
            )
        return r


class QueryCountQuery(_BaseQuery):
    """Statistics on the number of queries received over a given time period."""

    _Q = """
        select count(queries.id) from queries
            where timestamp >= :start and timestamp < :end
        """

    @classmethod
    def period(
        cls, start: datetime, end: datetime, enclosing_session: Optional[Session] = None
    ) -> Iterable[QueryCountItem]:
        r = cast(Iterable[QueryCountItem], [])
        with SessionContext(session=enclosing_session, read_only=True) as session:
            r = cast(
                Iterable[QueryCountItem], cls().execute(session, start=start, end=end)
            )
        return r


class QueryTypesQuery(_BaseQuery):
    """Stats on the most frequent query types over a given time period."""

    _Q = """
        select count(queries.id), queries.qtype from queries
            where queries.qtype is not NULL and
            timestamp >= :start and timestamp < :end
            group by queries.qtype
            order by queries.count desc
        """

    @classmethod
    def period(
        cls, start: datetime, end: datetime, enclosing_session: Optional[Session] = None
    ) -> Iterable[Any]:
        g: Iterable[Any] = []
        with SessionContext(session=enclosing_session, read_only=True) as session:
            g = cls().execute(session, start=start, end=end)
        return g


class QueryClientTypeQuery(_BaseQuery):
    """Stats on query client type and version (e.g. ios 1.3.0,
    android 1.2.1, etc.) over a given time period."""

    _Q = """
        select client_type, client_version, count(client_type) as freq
        from queries
        where client_type is not NULL and client_type != '' and
        timestamp >= :start and timestamp < :end
        group by client_type, client_version
        order by freq desc
        """

    @classmethod
    def period(
        cls, start: datetime, end: datetime, enclosing_session: Optional[Session] = None
    ) -> Iterable[Any]:
        g: Iterable[Any] = []
        with SessionContext(session=enclosing_session, read_only=True) as session:
            g = cls().execute(session, start=start, end=end)
        return g


class TopUnansweredQueriesQuery(_BaseQuery):
    """Return list of the most frequent *unanswered* queries
    over a given time period."""

    _Q = """
        select question, count(question) as qoccurrence from queries
            where answer is NULL and
            timestamp >= :start and timestamp < :end
            group by question
            order by qoccurrence desc
            limit :count
        """

    _DEFAULT_COUNT = 20

    @classmethod
    def period(
        cls,
        start: datetime,
        end: datetime,
        count: int = _DEFAULT_COUNT,
        enclosing_session: Optional[Session] = None,
    ) -> Iterable[Any]:
        g: Iterable[Any] = []
        with SessionContext(session=enclosing_session, read_only=True) as session:
            g = cls().execute(session, start=start, end=end, count=count)
        return g


class TopAnsweredQueriesQuery(_BaseQuery):
    """Return list of the most frequent *answered* queries
    over a given time period."""

    _Q = """
        select question, count(question) as qoccurrence from queries
            where answer is not NULL and
            timestamp >= :start and timestamp < :end
            group by question
            order by qoccurrence desc
            limit :count
        """

    _DEFAULT_COUNT = 20

    @classmethod
    def period(
        cls,
        start: datetime,
        end: datetime,
        count: int = _DEFAULT_COUNT,
        enclosing_session: Optional[Session] = None,
    ) -> Iterable[Any]:
        g: Iterable[Any] = []
        with SessionContext(session=enclosing_session, read_only=True) as session:
            g = cls().execute(session, start=start, end=end, count=count)
        return g


class BestAuthorsQuery(_BaseQuery):
    """A query for statistics on authors with the best parse ratios.
    The query only includes authors with at least 10 articles."""

    _MIN_ARTICLE_COUNT = 10

    _Q = """
        select * from (
            select trim(author) as auth,
                sum(1) as cnt,
                sum(num_parsed) as sum_parsed,
                sum(num_sentences) as sum_sent,
                (sum(100.0 * num_parsed) / sum(1.0 * num_sentences)) as ratio
                from articles
                where num_sentences > 0
                and articles.timestamp >= :start and articles.timestamp < :end
                group by auth
            ) as q
            where cnt >= :min_articles
            order by ratio desc;
        """

    @classmethod
    def period(
        cls,
        start: datetime,
        end: datetime,
        min_articles: int = _MIN_ARTICLE_COUNT,
        enclosing_session: Optional[Session] = None,
    ) -> Iterable[BestAuthorsItem]:
        r = cast(Iterable[BestAuthorsItem], [])
        with SessionContext(session=enclosing_session, read_only=True) as session:
            r = cast(
                Iterable[BestAuthorsItem],
                cls().execute(session, start=start, end=end, min_articles=min_articles),
            )
        return r


class RelatedWordsQuery(_BaseQuery):
    """A query for word stems commonly occurring in the same articles
    as the given word stem."""

    _Q = """
        select stem, cat, sum(cnt) as c
            from (
                select article_id as aid
                    from words
                    where stem=:root
            ) as src
            join words on src.aid = words.article_id
            group by stem, cat
            order by c desc
            limit :limit;
        """

    @classmethod
    def rel(
        cls, stem: str, limit: int = 21, enclosing_session: Optional[Session] = None
    ) -> Iterable[RelatedWordsItem]:
        """Return a list of (stem, category, count) tuples describing
        word stems that are related to the given stem, in descending
        order of number of appearances."""
        # The default limit is 21 instead of 20 because the original stem
        # is usually included in the result list
        r: Iterable[RelatedWordsItem] = []
        with SessionContext(session=enclosing_session, read_only=True) as session:
            r = cls().execute(session, root=stem, limit=limit)
        return r


class TermTopicsQuery(_BaseQuery):
    """A query for topic vectors of documents where a given (stem, cat)
    tuple appears. We return the newest articles first, in case the
    query result is limited by a specified limit."""

    _Q = """
        select topic_vector, q.cnt
            from (
                select a.id as id, sum(w.cnt) as cnt
                from articles a, words w
                where a.id = w.article_id and w.stem = :stem and w.cat = :cat
                group by a.id
            ) as q
            join articles on q.id = articles.id
            order by articles.timestamp desc
            limit :limit;
        """


class ArticleCountQuery(_BaseQuery):
    """A query yielding the number of articles containing any of the given word stems."""

    _Q = """
        select count(*)
            from (
                select distinct article_id
                    from words
                    where stem in :stems
            ) as q;
        """

    @classmethod
    def count(
        cls,
        stems: Union[str, Iterable[str]],
        enclosing_session: Optional[Session] = None,
    ) -> int:
        """Return a count of articles containing any of the given word
        stems. stems may be a single string or an iterable."""
        cnt = 0
        with SessionContext(session=enclosing_session, read_only=True) as session:
            cnt = int(
                cls().scalar(
                    session,
                    stems=tuple((stems,)) if isinstance(stems, str) else tuple(stems),
                )
            )
        return cnt


class ArticleListQuery(_BaseQuery):
    """A query returning a list of the newest articles that contain
    a particular word stem."""

    _Q_lower = """
        select distinct a.id, a.heading, a.timestamp, r.domain, a.url
            from words w, articles a, roots r
            where w.stem = :stem and w.article_id = a.id and a.root_id = r.id and r.visible
            order by a.timestamp desc
            limit :limit;
        """

    _Q_upper = """
        select distinct a.id, a.heading, a.timestamp, r.domain, a.url
            from words w, articles a, roots r
            where (w.stem = :stem or w.stem = :lstem) and w.article_id = a.id
            and a.root_id = r.id and r.visible
            order by a.timestamp desc
            limit :limit;
        """

    @classmethod
    def articles(
        cls, stem: str, limit: int = 20, enclosing_session: Optional[Session] = None
    ) -> Iterable[ArticleListItem]:
        """Return a list of the newest articles containing the given stem."""
        r: Iterable[ArticleListItem] = []
        with SessionContext(session=enclosing_session, read_only=True) as session:
            if stem == stem.lower():
                # Lower case stem
                r = cast(
                    Iterable[ArticleListItem],
                    cls().execute_q(session, cls._Q_lower, stem=stem, limit=limit),
                )
            # Upper case stem: include the lower case as well
            r = cast(
                Iterable[ArticleListItem],
                cls().execute_q(
                    session, cls._Q_upper, stem=stem, lstem=stem.lower(), limit=limit
                ),
            )
        return r


class WordFrequencyQuery(_BaseQuery):
    """A query yielding the number of times a given word occurs in
    articles over a given period of time, broken down by either
    day or week."""

    _Q = """
        with days as (
            select to_char(d, :datefmt) date
            from generate_series(
                :start,
                :end,
                :timeunit
            ) d
        ),
        appearances as (
            select to_char(a.timestamp, :datefmt) date, sum(w.cnt) cnt
            from words w, articles a
            where w.stem = :stem
            and w.cat = :cat
            and w.article_id = a.id
            and a.timestamp >= :start
            and a.timestamp <= :end
            group by date
            order by date
        )
        select days.date, coalesce(appearances.cnt,0) from days
        left outer join appearances on days.date = appearances.date;
        """

    @classmethod
    def frequency(
        cls,
        stem: str,
        cat: str,
        start: datetime,
        end: datetime,
        timeunit: str = "day",
        enclosing_session: Optional[Session] = None,
    ) -> Iterable[Any]:
        result: Iterable[Any] = []
        with SessionContext(session=enclosing_session, read_only=True) as session:
            assert timeunit in ["week", "day"]
            datefmt = "IYYY-IW" if timeunit == "week" else "YYYY-MM-DD"
            tu = "1 {0}".format(timeunit)
            result = cls().execute(
                session,
                stem=stem,
                cat=cat,
                start=start,
                end=end,
                timeunit=tu,
                datefmt=datefmt,
            )
        return result
