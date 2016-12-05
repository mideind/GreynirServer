"""

    Reynir: Natural language processing for Icelandic

    Scraper database model

    Copyright (C) 2016 Vilhjálmur Þorsteinsson

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


    This module describes the SQLAlchemy models for the scraper database
    and wraps a number of built-in queries.

"""


import sys
import platform
from time import sleep

from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, backref
from sqlalchemy import Table, Column, Integer, String, Float, DateTime, Sequence, \
    Boolean, UniqueConstraint, ForeignKey, PrimaryKeyConstraint
from sqlalchemy.exc import SQLAlchemyError as SqlError
from sqlalchemy.exc import IntegrityError as SqlIntegrityError
from sqlalchemy.exc import DataError as SqlDataError
from sqlalchemy import desc as SqlDesc
from sqlalchemy.dialects.postgresql import UUID as psql_UUID

from settings import Settings



# Create the SQLAlchemy ORM Base class
Base = declarative_base()

# Allow client use of IntegrityError exception without importing it from sqlalchemy
IntegrityError = SqlIntegrityError
DatabaseError = SqlError
DataError = SqlDataError
# Same for the desc() function
desc = SqlDesc


class Scraper_DB:

    """ Wrapper around the SQLAlchemy connection, engine and session """

    def __init__(self):

        """ Initialize the SQLAlchemy connection with the scraper database """

        # Assemble the right connection string for CPython/psycopg2 vs.
        # PyPy/psycopg2cffi, respectively

        is_pypy = platform.python_implementation() == "PyPy"
        conn_str = 'postgresql+{0}://reynir:reynir@{1}:{2}/scraper' \
            .format('psycopg2cffi' if is_pypy else 'psycopg2', Settings.DB_HOSTNAME, Settings.DB_PORT)
        self._engine = create_engine(conn_str)
        # Create a Session class bound to this engine
        self._Session = sessionmaker(bind = self._engine)

    def create_tables(self):
        """ Create all missing tables in the database """
        Base.metadata.create_all(self._engine)

    def execute(self, sql, **kwargs):
        """ Execute raw SQL directly on the engine """
        return self._engine.execute(sql, **kwargs)

    @property
    def session(self):
        """ Returns a freshly created Session instance from the sessionmaker """
        return self._Session()


class classproperty:
    def __init__(self, f):
        self.f = f
    def __get__(self, obj, owner):
        return self.f(owner)


class SessionContext:

    """ Context manager for database sessions """

    _db = None # Singleton instance of Scraper_DB

    @classproperty
    def db(cls):
        if cls._db is None:
            cls._db = Scraper_DB()
        return cls._db

    @classmethod
    def cleanup(cls):
        """ Clean up the reference to the singleton Scraper_DB instance """
        cls._db = None

    def __init__(self, session = None, commit = False):

        if session is None:
            # Create a new session that will be automatically committed
            # (if commit == True) and closed upon exit from the context
            db = self.db # Creates a new Scraper_DB instance if needed
            self._new_session = True
            self._session = db.session
            self._commit = commit
        else:
            self._new_session = False
            self._session = session
            self._commit = False

    def __enter__(self):
        """ Python context manager protocol """
        # Return the wrapped database session
        return self._session

    # noinspection PyUnusedLocal
    def __exit__(self, exc_type, exc_value, traceback):
        """ Python context manager protocol """
        if self._new_session:
            if self._commit:
                if exc_type is None:
                    # No exception: commit if requested
                    self._session.commit()
                else:
                    self._session.rollback()
            self._session.close()
        # Return False to re-throw exception from the context, if any
        return False


class Root(Base):
    
    """ Represents a scraper root, i.e. a base domain and root URL """

    __tablename__ = 'roots'

    # Primary key
    id = Column(Integer, Sequence('roots_id_seq'), primary_key=True)

    # Domain suffix, root URL, human-readable description
    domain = Column(String, nullable = False)
    url = Column(String, nullable = False)
    description = Column(String)

    # Default author
    author = Column(String)
    # Default authority of this source, 1.0 = most authoritative, 0.0 = least authoritative
    authority = Column(Float)
    # Finish time of last scrape of this root
    scraped = Column(DateTime, index = True)
    # Module to use for scraping
    scr_module = Column(String(80))
    # Class within module to use for scraping
    scr_class = Column(String(80))
    # Are articles of this root visible on the Greynir web?
    visible = Column(Boolean, default = True)
    # Should articles of this root be scraped automatically?
    scrape = Column(Boolean, default = True)

    # The combination of domain + url must be unique
    __table_args__ = (
        UniqueConstraint('domain', 'url'),
    )

    def __repr__(self):
        return "Root(domain='{0}', url='{1}', description='{2}')" \
            .format(self.domain, self.url, self.description)


class Article(Base):

    """ Represents an article from one of the roots, to be scraped or having already been scraped """

    __tablename__ = 'articles'

    # The article URL is the primary key
    url = Column(String, primary_key = True)

    # UUID
    id = Column(psql_UUID(as_uuid = False), index = True, nullable = False, unique = True,
        server_default = text("uuid_generate_v1()"))

    # Foreign key to a root
    root_id = Column(Integer,
        # We don't delete associated articles if the root is deleted
        ForeignKey('roots.id', onupdate="CASCADE", ondelete="SET NULL"))

    # Article heading, if known
    heading = Column(String)
    # Article author, if known
    author = Column(String)
    # Article time stamp, if known
    timestamp = Column(DateTime, index = True)

    # Authority of this article, 1.0 = most authoritative, 0.0 = least authoritative
    authority = Column(Float)
    # Time of the last scrape of this article
    scraped = Column(DateTime, index = True)
    # Time of the last parse of this article
    parsed = Column(DateTime, index = True)
    # Time of the last processing of this article
    processed = Column(DateTime, index = True)
    # Time of the last indexing of this article
    indexed = Column(DateTime, index = True)
    # Module used for scraping
    scr_module = Column(String(80))
    # Class within module used for scraping
    scr_class = Column(String(80))
    # Version of scraper class
    scr_version = Column(String(16))
    # Version of parser/grammar/config
    parser_version = Column(String(32))
    # Parse statistics
    num_sentences = Column(Integer)
    num_parsed = Column(Integer)
    ambiguity = Column(Float)

    # The HTML obtained in the last scrape
    html = Column(String)
    # The parse tree obtained in the last parse
    tree = Column(String)
    # The tokens of the article in JSON string format
    tokens = Column(String)

    # The back-reference to the Root parent of this Article
    root = relationship("Root", foreign_keys="Article.root_id",
        backref=backref('articles', order_by=url))

    def __repr__(self):
        return "Article(url='{0}', heading='{1}', scraped={2})" \
            .format(self.url, self.heading, self.scraped)


class Person(Base):

    """ Represents a person """

    __tablename__ = 'persons'

    # Primary key
    id = Column(Integer, Sequence('persons_id_seq'), primary_key=True)

    # Foreign key to an article
    article_url = Column(String,
        # We don't delete associated persons if the article is deleted
        ForeignKey('articles.url', onupdate="CASCADE", ondelete="SET NULL"),
        index = True, nullable = True)

    # Name
    name = Column(String, index = True)
    
    # Title
    title = Column(String, index = True)
    # Title in all lowercase
    title_lc = Column(String, index = True)

    # Gender
    gender = Column(String(3), index = True)

    # Authority of this fact, 1.0 = most authoritative, 0.0 = least authoritative
    authority = Column(Float)

    # Timestamp of this entry
    timestamp = Column(DateTime)

    # The back-reference to the Article parent of this Person
    article = relationship("Article", backref=backref('persons', order_by=name))

    def __repr__(self):
        return "Person(id='{0}', name='{1}', title={2})" \
            .format(self.id, self.name, self.title)

    @classmethod
    def table(cls):
        return cls.__table__


class Entity(Base):

    """ Represents an entity """

    __tablename__ = 'entities'

    # Primary key
    id = Column(Integer, Sequence('entities_id_seq'), primary_key=True)

    # Foreign key to an article
    article_url = Column(String,
        # We don't delete associated persons if the article is deleted
        ForeignKey('articles.url', onupdate="CASCADE", ondelete="SET NULL"),
        index = True, nullable = True)

    # Name
    name = Column(String, index = True)
    # Verb ('er', 'var', 'sé')
    verb = Column(String, index = True)
    # Entity definition
    definition = Column(String, index = True)

    # Authority of this fact, 1.0 = most authoritative, 0.0 = least authoritative
    authority = Column(Float)

    # Timestamp of this entry
    timestamp = Column(DateTime)

    # The back-reference to the Article parent of this Entity
    article = relationship("Article", backref=backref('entities', order_by=name))

    def __repr__(self):
        return "Entity(id='{0}', name='{1}', verb='{2}', definition='{3}')" \
            .format(self.id, self.name, self.verb, self.definition)

    @classmethod
    def table(cls):
        return cls.__table__


class Word(Base):

    """ Represents a word occurring in an article """

    __tablename__ = 'words'

    # Foreign key to an article
    article_id = Column(psql_UUID(as_uuid = False),
        ForeignKey('articles.id', onupdate="CASCADE", ondelete="CASCADE"),
        nullable = False)

    # The word stem
    stem = Column(String(64), index = True, nullable = False)

    # The word category
    cat = Column(String(16), index = True, nullable = False)

    # Count of occurrences
    cnt = Column(Integer, nullable = False)

    # The back-reference to the Article parent of this Word
    article = relationship("Article", backref=backref('words'))

    __table_args__ = (
        PrimaryKeyConstraint('article_id', 'stem', 'cat', name='words_pkey'),
    )

    def __repr__(self):
        return "Word(stem='{0}', cat='{1}', cnt='{2}')" \
            .format(self.stem, self.cat, self.cnt)

    @classmethod
    def table(cls):
        return cls.__table__


class Topic(Base):

    """ Represents a topic for an article """

    __tablename__ = 'topics'

    id = Column(psql_UUID(as_uuid = False),
        server_default = text("uuid_generate_v1()"), primary_key = True)

    # The topic name
    name = Column(String(128), nullable = False, index = True)

    # An identifier for the topic, such as 'sport', 'business'...
    # The identifier must be usable as a CSS class name.
    identifier = Column(String(32), nullable = False)

    # The topic keywords, in the form word1/cat word2/cat...
    keywords = Column(String, nullable = False)

    # The associated vector, in JSON format
    vector = Column(String) # Is initally NULL

    # The cosine distance threshold to apply for this topic
    threshold = Column(Float)

    def __repr__(self):
        return "Topic(name='{0}')" \
            .format(self.name)

    @classmethod
    def table(cls):
        return cls.__table__


class ArticleTopic(Base):

    """ Represents an article having a topic, a 1:N relationship """

    __tablename__ = 'atopics'

    article_id = Column(psql_UUID(as_uuid = False),
        ForeignKey('articles.id', onupdate="CASCADE", ondelete="CASCADE"),
        nullable = False, index = True)

    topic_id = Column(psql_UUID(as_uuid = False),
        ForeignKey('topics.id', onupdate="CASCADE", ondelete="CASCADE"),
        nullable = False, index = True)

    # The back-reference to the Article parent of this ArticleTopic
    article = relationship("Article", backref=backref('atopics'))
    # The back-reference to the Topic parent of this ArticleTopic
    topic = relationship("Topic", backref=backref('atopics'))

    __table_args__ = (
        PrimaryKeyConstraint('article_id', 'topic_id', name='atopics_pkey'),
    )

    def __repr__(self):
        return "ArticleTopic()"

    @classmethod
    def table(cls):
        return cls.__table__


class Trigram(Base):

    """ Represents a trigram of tokens from a parsed sentence """

    __tablename__ = 'trigrams'

    MAX_WORD_LEN = 64

    # Token 1
    t1 = Column(String(MAX_WORD_LEN), nullable = False)

    # Token 2
    t2 = Column(String(MAX_WORD_LEN), nullable = False)

    # Token 3
    t3 = Column(String(MAX_WORD_LEN), nullable = False)

    # Frequency
    frequency = Column(Integer, default = 0, nullable = False)

    # The "upsert" query (see explanation below)
    _Q = """
        insert into trigrams as tg (t1, t2, t3, frequency) values(:t1, :t2, :t3, 1)
            on conflict (t1, t2, t3)
            do update set frequency = tg.frequency + 1
            where tg.t1 = :t1 and tg.t2 = :t2 and tg.t3 = :t3;
        """

    __table_args__ = (
        PrimaryKeyConstraint('t1', 't2', 't3', name='trigrams_pkey'),
    )

    @staticmethod
    def upsert(session, t1, t2, t3):
        """ Insert a trigram, or increment the frequency count if already present """
        # The following code uses "upsert" functionality (INSERT...ON CONFLICT...DO UPDATE)
        # that was introduced in PostgreSQL 9.5. This means that the upsert runs on the
        # server side and is atomic, either an insert of a new trigram or an update of
        # the frequency count of an existing identical trigram.
        mwl = Trigram.MAX_WORD_LEN
        if len(t1) > mwl:
            t1 = t1[0:mwl]
        if len(t2) > mwl:
            t2 = t2[0:mwl]
        if len(t3) > mwl:
            t3 = t3[0:mwl]
        session.execute(self._Q, dict(t1 = t1, t2 = t2, t3 = t3))

    @staticmethod
    def delete_all(session):
        """ Delete all trigrams """
        session.execute("delete from trigrams;")

    def __repr__(self):
        return "Trigram(t1='{0}', t2='{1}', t3='{2}')" \
            .format(self.t1, self.t2, self.t3)

    @classmethod
    def table(cls):
        return cls.__table__


class Link(Base):

    """ Represents a (content-type, key) to URL mapping,
        usable for instance to cache image searches """

    __tablename__ = 'links'

    __table_args__ = (
        PrimaryKeyConstraint('ctype', 'key', name='links_pkey'),
    )

    # Content type, for instance 'image' or 'text'
    ctype = Column(String(32), nullable = False, index = True)

    # Key, for instance a person name
    key = Column(String(256), nullable = False, index = True)

    # Associated content, often JSON
    content = Column(String)

    # Timestamp of this entry
    timestamp = Column(DateTime, nullable = False)

    def __repr__(self):
        return "Link(ctype='{0}', key='{1}', content='{2}')" \
            .format(self.ctype, self.key, self.content)

    @classmethod
    def table(cls):
        return cls.__table__


class _BaseQuery:

    def __init__(self):
        pass

    def execute(self, session, **kwargs):
        """ Execute the query and return the result from fetchall() """
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
            sum(a.num_sentences) as sent,
            sum(a.num_parsed) as parsed
            from articles as a, roots as r
            where a.root_id = r.id and r.visible
            group by r.domain
            order by r.domain;
        """


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
                group by auth
            ) as q
            where cnt >= {0}
            order by ratio desc;
        """.format(_MIN_ARTICLE_COUNT)


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
    def rel(cls, stem, limit = 20, enclosing_session = None):
        """ Return a list of (stem, category, count) tuples describing
            word stems that are related to the given stem, in descending
            order of number of appearances. """
        with SessionContext(session = enclosing_session, commit = True) as session:
            return cls().execute(session, root = stem, limit = limit)


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
    def count(cls, stems, enclosing_session = None):
        """ Return a count of articles containing any of the given word
            stems. stems may be a single string or an iterable. """
        with SessionContext(session = enclosing_session, commit = True) as session:
            return cls().scalar(session,
                stems = tuple((stems,)) if isinstance(stems, str) else tuple(stems))


class ArticleListQuery(_BaseQuery):

    """ A query returning a list of the newest articles that contain
        a particular word stem """

    _Q = """
        select distinct a.id, a.heading, a.timestamp, r.domain
            from words w, articles a, roots r
            where w.stem = :stem and w.article_id = a.id and a.root_id = r.id and r.visible
            order by a.timestamp desc
            limit :limit;
        """

    @classmethod
    def articles(cls, stem, limit = 20, enclosing_session = None):
        """ Return a list of the newest articles containing the given stem. """
        with SessionContext(session = enclosing_session, commit = True) as session:
            return cls().execute(session, stem = stem, limit = limit)

