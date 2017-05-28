"""
    Reynir: Natural language processing for Icelandic

    Special scraping module for preloaded local data
    used for entiment analysis experiment

    Copyright (c) 2016 Vilhjalmur Thorsteinsson
    All rights reserved
    See the accompanying README.md file for further licensing and copyright information.

"""

import sys
import os
import platform

import urllib.parse as urlparse
from datetime import datetime

from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, backref
from sqlalchemy import Table, Column, Integer, String, Float, DateTime, Sequence, \
    Boolean, UniqueConstraint, ForeignKey, PrimaryKeyConstraint
from sqlalchemy.exc import SQLAlchemyError as SqlError
from sqlalchemy.exc import IntegrityError as SqlIntegrityError
from sqlalchemy.exc import DataError as SqlDataError
from sqlalchemy import desc as SqlDesc

# Provide access to modules in the parent directory
#sys.path.insert(1, os.path.join(sys.path[0], '..'))

from .default import Metadata, ScrapeHelper

MODULE_NAME = __name__


# Create the SQLAlchemy ORM Base class
Base = declarative_base()


class Reykjanes_DB:

    """ Wrapper around the SQLAlchemy connection, engine and session """

    DB_HOSTNAME = os.environ.get('GREYNIR_DB_HOST', 'localhost')
    DB_PORT = os.environ.get('GREYNIR_DB_PORT', '5432') # Default PostgreSQL port

    def __init__(self):

        """ Initialize the SQLAlchemy connection with the scraper database """

        # Assemble the right connection string for CPython/psycopg2 vs.
        # PyPy/psycopg2cffi, respectively
        is_pypy = platform.python_implementation() == "PyPy"
        conn_str = 'postgresql+{0}://reynir:reynir@{1}:{2}/reykjanes' \
            .format('psycopg2cffi' if is_pypy else 'psycopg2', self.DB_HOSTNAME, self.DB_PORT)
        self._engine = create_engine(conn_str)
        # Create a Session class bound to this engine
        self._Session = sessionmaker(bind = self._engine)

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

    _db = None # Singleton instance of Reykjanes_DB

    @classproperty
    def db(cls):
        if cls._db is None:
            cls._db = Reykjanes_DB()
        return cls._db

    @classmethod
    def cleanup(cls):
        """ Clean up the reference to the singleton Scraper_DB instance """
        cls._db = None

    def __init__(self, session = None, commit = False):

        if session is None:
            # Create a new session that will be automatically committed
            # (if commit == True) and closed upon exit from the context
            db = self.db # Creates a new Reykjanes_DB instance if needed
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


class Doc(Base):
    
    """ Represents a document in the Reykjanes database """

    __tablename__ = 'docs'

    # Primary key
    id = Column(String(16), primary_key=True)

    sentiment = Column(Integer)
    ts = Column(DateTime, index = True)
    heading = Column(String(256))
    summary = Column(String)
    body = Column(String)
    media = Column(String(32))
    type = Column(String(32))

    def __repr__(self):
        return "Doc(id='{0}', heading='{1}')" \
            .format(self.id, self.heading)


class ReykjanesScraper(ScrapeHelper):

    """ Generic scraping helper base class """

    _SENTIMENT_DICT = { -1 : "Neikvæð", 0 : "Hlutlaus", 1 : "Jákvæð" }

    def __init__(self, root):
        super().__init__(root)

    def fetch_url(self, url):
        """ Load the requested document from the database """
        s = urlparse.urlsplit(url)
        docid = dict(urlparse.parse_qsl(s.query)).get("id")
        with SessionContext(commit = True) as session:
            doc = session.query(Doc).filter(Doc.id == docid).one_or_none() if docid else None
            if not doc:
                return "<html><head><title>Fannst ekki</title></head><body><p>Skjal {0} finnst ekki.</p></body></html>".format(docid)

            def clean(txt):
                """ Do basic clean-up of the raw text """
                return txt.replace("\u0084", "„").replace("\u0093", "“").replace("\u0096", "—")

            body = clean(doc.body)
            body = "\n".join("<p>" + pg + "</p>" for pg in body.split("\n"))
            heading = clean(doc.heading)
            return "<html><head>" \
                "<title>{1}</title>" \
                "<meta property='article:published_time' content='{2}'>" \
                "<meta property='article:sentiment' content='{3}'>" \
                "</head><body>{0}</body></html>" \
                .format(body, heading, str(doc.ts)[0:19], doc.sentiment)

    def make_soup(self, doc):
        """ Make a soup object from a document """
        return super().make_soup(doc)

    def get_metadata(self, soup):
        """ Analyze the article HTML soup and return metadata """
        metadata = super().get_metadata(soup)
        metadata.heading = soup.html.head.title.string if soup.html.head.title else "Fyrirsögn"
        sentiment = ScrapeHelper.meta_property(soup, "article:sentiment")
        sentiment = int(sentiment) if sentiment else 0
        metadata.author = self._SENTIMENT_DICT.get(sentiment, "Óþekkt")
        ts = ScrapeHelper.meta_property(soup, "article:published_time")
        if ts:
            metadata.timestamp = datetime(year=int(ts[0:4]), month=int(ts[5:7]), day=int(ts[8:10]),
                hour=int(ts[11:13]), minute=int(ts[14:16]), second=int(ts[17:19]))
        else:
            metadata.timestamp = datetime.utcnow()
        return metadata

    def get_content(self, soup):
        """ Find the actual article content within an HTML soup and return its parent node """
        return soup

    @property
    def scr_module(self):
        """ Return the name of the module for this scraping helper class """
        return MODULE_NAME

