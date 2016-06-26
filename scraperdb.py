"""
    Reynir: Natural language processing for Icelandic

    Scraper database model

    Copyright (c) 2015 Vilhjalmur Thorsteinsson
    All rights reserved
    See the accompanying README.md file for further licensing and copyright information.

    This module describes the SQLAlchemy models for the scraper database.
    It is used in scraper.py and processor.py.

"""


import sys
import platform

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, backref
from sqlalchemy import Table, Column, Integer, String, Float, DateTime, Sequence, \
    UniqueConstraint, ForeignKey, PrimaryKeyConstraint
from sqlalchemy.exc import SQLAlchemyError as SqlError
from sqlalchemy.exc import IntegrityError as SqlIntegrityError
from sqlalchemy import desc as SqlDesc

from settings import Settings


# Create the SQLAlchemy ORM Base class
Base = declarative_base()

# Allow client use of IntegrityError exception without importing it from sqlalchemy
IntegrityError = SqlIntegrityError
DatabaseError = SqlError
# Same for the desc() function
desc = SqlDesc


class Scraper_DB:

    """ Wrapper around the SQLAlchemy connection, engine and session """

    def __init__(self):

        """ Initialize the SQLAlchemy connection with the scraper database """

        # Assemble the right connection string for CPython/psycopg2 vs.
        # PyPy/psycopg2cffi, respectively
        is_pypy = platform.python_implementation() == "PyPy"
        conn_str = 'postgresql+{0}://reynir:reynir@{1}/scraper' \
            .format('psycopg2cffi' if is_pypy else 'psycopg2', Settings.DB_HOSTNAME)
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
    scraped = Column(DateTime, index = True, nullable = True)
    # Module to use for scraping
    scr_module = Column(String(80))
    # Class within module to use for scraping
    scr_class = Column(String(80))

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

    # Primary key
    url = Column(String, primary_key=True)

    # Foreign key to a root
    root_id = Column(Integer,
        # We don't delete associated articles if the root is deleted
        ForeignKey('roots.id', onupdate="CASCADE", ondelete="SET NULL"), nullable = True)

    # Article heading, if known
    heading = Column(String)
    # Article author, if known
    author = Column(String)
    # Article time stamp, if known
    timestamp = Column(DateTime, index = True, nullable = True)

    # Authority of this article, 1.0 = most authoritative, 0.0 = least authoritative
    authority = Column(Float)
    # Time of the last scrape of this article
    scraped = Column(DateTime, index = True, nullable = True)
    # Time of the last parse of this article
    parsed = Column(DateTime, index = True, nullable = True)
    # Time of the last processing of this article
    processed = Column(DateTime, index = True, nullable = True)
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
    title_lc = Column(String, index = True, nullable = True)

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


class Failure(Base):

    """ Represents a sentence that fails to parse """

    __tablename__ = 'failures'

    # Primary key
    id = Column(Integer, Sequence('failures_id_seq'), primary_key=True)

    # Foreign key to an article
    article_url = Column(String,
        # We don't delete associated failures if the article is deleted
        ForeignKey('articles.url', onupdate="CASCADE", ondelete="SET NULL"),
        index = True, nullable = True)

    # Sentence text
    sentence = Column(String, nullable = False)

    # Cause of failure: NULL = unknown, 'grammar', 'error'...
    cause = Column(String(16), nullable = True, index = True)

    # Comment
    comment = Column(String, nullable = True)

    # Timestamp of this entry
    timestamp = Column(DateTime, nullable = False, index = True)

    # The back-reference to the Article parent of this Failure
    article = relationship("Article", backref=backref('failures'))

    def __repr__(self):
        return "Failure(id='{0}', sentence='{1}', cause='{2}', comment='{3}')" \
            .format(self.id, self.sentence, self.cause, self.comment)

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
        session.execute(
            """
            insert into trigrams as tg (t1, t2, t3, frequency) values(:t1, :t2, :t3, 1)
            on conflict (t1, t2, t3)
            do update set frequency = tg.frequency + 1
            where tg.t1 = :t1 and tg.t2 = :t2 and tg.t3 = :t3;
            """,
            dict(t1 = t1, t2 = t2, t3 = t3)
        )

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

