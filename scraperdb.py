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
from sqlalchemy import Column, Integer, String, Float, DateTime, Sequence, \
    UniqueConstraint, ForeignKey
from sqlalchemy.exc import IntegrityError as SqlIntegrityError

from settings import Settings


# Create the SQLAlchemy ORM Base class
Base = declarative_base()

# Allow client use of IntegrityError exception without importing it from sqlalchemy
IntegrityError = SqlIntegrityError


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

    def execute(self, sql):
        """ Execute raw SQL directly on the engine """
        return self._engine.execute(sql)

    @property
    def session(self):
        """ Returns a freshly created Session instance from the sessionmaker """
        return self._Session()


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
    timestamp = Column(DateTime)

    # Authority of this article, 1.0 = most authoritative, 0.0 = least authoritative
    authority = Column(Float)
    # Time of the last scrape of this article
    scraped = Column(DateTime, index = True, nullable = True)
    # Time of the last parse of this article
    parsed = Column(DateTime, index = True, nullable = True)
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
    root = relationship("Root", backref=backref('articles', order_by=url))

    def __repr__(self):
        return "Article(url='{0}', heading='{1}', scraped={2})" \
            .format(self.url, self.heading, self.scraped)


