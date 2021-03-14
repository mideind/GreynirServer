"""

    Greynir: Natural language processing for Icelandic

    Scraper database queries

    Copyright (C) 2021 Miðeind ehf.

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


    This module wraps a number of SQLAlchemy SQL queries.

"""

from . import SessionContext


class _BaseQuery:

    _Q = ""

    def __init__(self):
        pass

    def execute_q(self, session, q, **kwargs):
        """ Execute the given query and return the result from fetchall() """
        return session.execute(q, kwargs).fetchall()

    def execute(self, session, **kwargs):
        """ Execute the default query and return the result from fetchall() """
        return session.execute(self._Q, kwargs).fetchall()

    def scalar(self, session, **kwargs):
        """ Execute the query and return the result from scalar() """
        return session.scalar(self._Q, kwargs)


class GenderQuery(_BaseQuery):
    """ A query for gender representation in the persons table """

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
    """ A query for statistics on articles """

    _Q = """
        select r.domain,
            sum(1) as art,
            coalesce(sum(a.num_sentences),0) as sent,
            coalesce(sum(a.num_parsed),0) as parsed
            from articles as a, roots as r
            where a.root_id = r.id and r.visible
            group by r.domain
            order by r.domain;
        """


class ChartsQuery(_BaseQuery):
    """ Statistics on article, sentence and parse count
        for all sources for a given time period """

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
    def period(cls, start, end, enclosing_session=None):
        with SessionContext(session=enclosing_session, commit=False) as session:
            return cls().execute(session, start=start, end=end)


class QueriesQuery(_BaseQuery):
    """ Statistics on the number of queries received over a given time period. """

    _Q = """
        select count(queries.id) from queries
            where timestamp >= :start and timestamp < :end
        """

    @classmethod
    def period(cls, start, end, enclosing_session=None):
        with SessionContext(session=enclosing_session, commit=False) as session:
            return cls().execute(session, start=start, end=end)


class QueryTypesQuery(_BaseQuery):
    """ Stats on the most frequent query types over a given time period. """

    _Q = """
        select count(queries.id), queries.qtype from queries
            where queries.qtype is not NULL and
            timestamp >= :start and timestamp < :end
            group by queries.qtype
            order by queries.count desc
        """

    @classmethod
    def period(cls, start, end, enclosing_session=None):
        with SessionContext(session=enclosing_session, commit=False) as session:
            return cls().execute(session, start=start, end=end)


class BestAuthorsQuery(_BaseQuery):
    """ A query for statistics on authors with the best parse ratios.
        The query only includes authors with at least 10 articles. """

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
        cls, start, end, min_articles=_MIN_ARTICLE_COUNT, enclosing_session=None
    ):
        with SessionContext(session=enclosing_session, commit=False) as session:
            return cls().execute(
                session, start=start, end=end, min_articles=min_articles
            )


class RelatedWordsQuery(_BaseQuery):
    """ A query for word stems commonly occurring in the same articles
        as the given word stem """

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
    def rel(cls, stem, limit=21, enclosing_session=None):
        """ Return a list of (stem, category, count) tuples describing
            word stems that are related to the given stem, in descending
            order of number of appearances. """
        # The default limit is 21 instead of 20 because the original stem
        # is usually included in the result list
        with SessionContext(session=enclosing_session, commit=True) as session:
            return cls().execute(session, root=stem, limit=limit)


class TermTopicsQuery(_BaseQuery):
    """ A query for topic vectors of documents where a given (stem, cat)
        tuple appears. We return the newest articles first, in case the
        query result is limited by a specified limit. """

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
    """ A query yielding the number of articles containing any of the given word stems """

    _Q = """
        select count(*)
            from (
                select distinct article_id
                    from words
                    where stem in :stems
            ) as q;
        """

    @classmethod
    def count(cls, stems, enclosing_session=None):
        """ Return a count of articles containing any of the given word
            stems. stems may be a single string or an iterable. """
        with SessionContext(session=enclosing_session, commit=True) as session:
            return cls().scalar(
                session,
                stems=tuple((stems,)) if isinstance(stems, str) else tuple(stems),
            )


class ArticleListQuery(_BaseQuery):
    """ A query returning a list of the newest articles that contain
        a particular word stem. """

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
    def articles(cls, stem, limit=20, enclosing_session=None):
        """ Return a list of the newest articles containing the given stem. """
        with SessionContext(session=enclosing_session, commit=True) as session:
            if stem == stem.lower():
                # Lower case stem
                return cls().execute_q(session, cls._Q_lower, stem=stem, limit=limit)
            # Upper case stem: include the lower case as well
            return cls().execute_q(
                session, cls._Q_upper, stem=stem, lstem=stem.lower(), limit=limit
            )


class WordFrequencyQuery(_BaseQuery):
    """ A query yielding the number of times a given word occurs in
        articles over a given period of time, broken down by either
        day or week. """

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
    def frequency(cls, stem, cat, start, end, timeunit="day", enclosing_session=None):
        with SessionContext(session=enclosing_session, commit=False) as session:
            assert timeunit in ["week", "day"]
            datefmt = "IYYY-IW" if timeunit == "week" else "YYYY-MM-DD"
            tu = "1 {0}".format(timeunit)
            return cls().execute(
                session,
                stem=stem,
                cat=cat,
                start=start,
                end=end,
                timeunit=tu,
                datefmt=datefmt,
            )
