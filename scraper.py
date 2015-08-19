#!/usr/bin/env python
"""
    Reynir: Natural language processing for Icelandic

    Scraper module

    Author: Vilhjalmur Thorsteinsson

    This software is at a very early development stage.
    While that is the case, it is:
    Copyright (c) 2015 Vilhjalmur Thorsteinsson
    All rights reserved
    See the accompanying README.md file for further licensing and copyright information.

    This module implements a simple web scraper and spider.

    The scraper works from a set of root URLs to periodically scrape child
    URLs from the same parent domain. The root URLs and the
    scraping output are stored in tables in a PostgreSQL database
    called 'scraper', and accessed via SQLAlchemy.

"""

import sys
import platform
import getopt
import codecs
import time
import importlib
import urllib.request
import urllib.parse as urlparse
from urllib.error import HTTPError

from contextlib import closing
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker, relationship, backref
from sqlalchemy import Column, Integer, String, Float, DateTime, Sequence, \
    UniqueConstraint, ForeignKey

from bs4 import BeautifulSoup, NavigableString

from tokenizer import TOK, tokenize
from grammar import Nonterminal, Terminal, Token, Production, Grammar, GrammarError
from parser import Parser, ParseError
from reducer import Reducer
from binparser import BIN_Parser
from settings import Settings, ConfigError

# Create the SQLAlchemy ORM Base class
Base = declarative_base()


class Scraper_DB:

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
    domain = Column(String)
    url = Column(String)
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

    root = relationship("Root", backref=backref('articles', order_by=url))

    def __repr__(self):
        return "Article(url='{0}', heading='{1}', scraped={2})" \
            .format(self.url, self.heading, self.scraped)


class Scraper:

    def __init__(self, db, parser):

        self._db = db
        self._parser = parser

    def children(self, root, soup):
        """ Return a set of child URLs within a HTML soup, relative to the given root """
        # Establish the root URL base parameters
        root_s = urlparse.urlsplit(root.url)
        root_url = urlparse.urlunsplit(root_s)
        root_url_slash = urlparse.urlunsplit((root_s.scheme, root_s.netloc, '/', root_s.query, ''))
        # Collect all interesting <a> tags from the soup and obtain their href-s:
        fetch = set()
        for link in soup.find_all('a'):
            href = link.get('href')
            if not href:
                continue
            # Split the href into its components
            s = urlparse.urlsplit(href)
            if s.scheme and s.scheme not in ['http', 'https']:
                # Not HTTP
                continue
            if s.netloc and not s.netloc.startswith(root.domain):
                # External domain - we're not interested
                continue
            # Seems to be a bug in urllib: fragments are put into the
            # path if there is no canonical path
            newpath = s.path
            if newpath.startswith("#") or newpath.startswith("/#"):
                newpath = ''
            if not newpath and not s.query:
                # No meaningful path info present
                continue
            # Fill in missing stuff from the root URL base parameters
            newurl = (s.scheme or root_s.scheme,
                s.netloc or root_s.netloc, newpath, s.query, '')
            # Make a complete new URL to fetch
            url = urlparse.urlunsplit(newurl)
            if url in [root_url, root_url_slash]:
                # Exclude the root URL
                continue
            # Looks legit: add to the fetch set
            fetch.add(url)
        return fetch

    def scrape_root(self, root):
        """ Scrape a root URL """

        t0 = time.time()
        # Fetch the root URL and scrape all child URLs that refer
        # to the same domain suffix and we haven't seen before
        print("Processing root {0}".format(root.url))

        # Read the HTML document at the root URL
        with closing(urllib.request.urlopen(root.url)) as response:
            html_doc = response.read()

        # Parse the document
        soup = BeautifulSoup(html_doc, "html.parser") # or 'html5lib'

        # Obtain the set of child URLs to fetch
        fetch_set = self.children(root, soup)

        # Add the children whose URLs we don't already have to the
        # scraper articles table
        session = self._db.session
        for url in fetch_set:

            try:
                article = Article(url = url, root_id = root.id)
                # Leave article.scraped as NULL for later retrieval
                session.add(article)
                session.commit()
            except IntegrityError as e:
                # Article URL already exists in database:
                # roll back and continue
                session.rollback()

        t1 = time.time()

        print("Processing completed in {0:.2f} seconds".format(t1 - t0))

    def scrape_article(self, url, helper):
        """ Scrape a single article, retrieving its HTML and metadata """

        t0 = time.time()
        # Fetch the root URL and scrape all child URLs that refer
        # to the same domain suffix and we haven't seen before
        print("Processing article {0}".format(url))

        encoding = 'utf-8'

        # Read the HTML document at the article URL
        try:
            with closing(urllib.request.urlopen(url)) as response:
                if not response:
                    print("No response")
                    return
                ctype = response.getheader("Content-type", "")
                if ';' in ctype:
                    s = ctype.split(';')
                    ctype = s[0]
                    enc = s[1].strip()
                    s = enc.split('=')
                    if s[0] == "charset" and len(s) == 2:
                        encoding = s[1]
                        print("Set encoding to {0}".format(encoding))
                if ctype != "text/html":
                    print("Not a HTML document: {0}".format(ctype))
                    return
                html_doc = response.read() # html_doc is a bytes object
        except HTTPError as e:
            print("HTTPError returned: {0}".format(e))
            return

        # Parse the document
        soup = BeautifulSoup(html_doc, "html.parser") # or 'html5lib'

        # Obtain the set of child URLs to fetch
        #fetch_set = self.children(root, soup)

        # Use the scrape helper to analyze the soup and return
        # metadata
        metadata = helper.analyze(soup)

        # Upate the article info
        session = self._db.session

        article = session.query(Article).filter_by(url = url).one()
        article.heading = metadata.heading
        article.author = metadata.author
        article.timestamp = metadata.timestamp
        article.authority = metadata.authority
        article.scraped = datetime.now()
        article.scr_module = helper.scr_module
        article.scr_class = helper.scr_class
        article.scr_version = helper.scr_version
        try:
            article.html = html_doc.decode(encoding)
        except UnicodeDecodeError as e:
            print("UnicodeDecodeError returned: {0}".format(e))
            session.rollback()
            return

        try:
            session.commit()
        except IntegrityError as e:
            # Roll back and continue
            session.rollback()

        t1 = time.time()

        print("Processing completed in {0:.2f} seconds".format(t1 - t0))

    def parse_article(self, url, helper):
        """ Parse a single article """

        # Scrape the URL, tokenize the text content and return the token list

        t0 = time.time()
        toklist = list(process_url(url))
        tok_time = time.time() - t0

        # Count sentences
        num_sent = 0
        num_parsed_sent = 0
        total_ambig = 0.0
        total_tokens = 0

        sent_begin = 0
        bp = self._parser
        rdc = Reducer() # !!! This will be included in the parser

        t0 = time.time()

        for ix, t in enumerate(toklist):
            if t[0] == TOK.S_BEGIN:
                num_sent += 1
                sent = []
                sent_begin = ix
            elif t[0] == TOK.S_END:
                slen = len(sent)
                # Parse the accumulated sentence
                err_index = None
                try:
                    # Parse the sentence
                    forest = bp.go(sent)
                    # Reduce the resulting forest
                    forest = rdc.go(forest)
                except ParseError as e:
                    forest = None
                    # Obtain the index of the offending token
                    err_index = e.token_index
                num = 0 if forest is None else Parser.num_combinations(forest)
                #print("Parsed sentence of length {0} with {1} combinations{2}".format(slen, num,
                #    "\n" + " ".join(s[1] for s in sent) if num >= 100 else ""))
                if num > 0:
                    num_parsed_sent += 1
                    # Calculate the 'ambiguity factor'
                    ambig_factor = num ** (1 / slen)
                    # Do a weighted average on sentence length
                    total_ambig += ambig_factor * slen
                    total_tokens += slen
                # Mark the sentence beginning with the number of parses
                # and the index of the offending token, if an error occurred
                #toklist[sent_begin] = TOK.Begin_Sentence(num_parses = num, err_index = err_index)

                # Store the parse result in the database

            elif t[0] == TOK.P_BEGIN:
                pass
            elif t[0] == TOK.P_END:
                pass
            else:
                sent.append(t)

        parse_time = time.time() - t0

        # Return the scrape result
        return dict(
            tok_time = tok_time,
            tok_num = len(toklist),
            parse_time = parse_time,
            num_sent = num_sent,
            num_parsed_sent = num_parsed_sent,
            avg_ambig_factor = (total_ambig / total_tokens) if total_tokens > 0 else 1.0
        )

    @classmethod
    def go(cls, db, parser):
        """ Run a scraping pass from all roots in the scraping database """

        # Create a scraper instance that uses the opened database and the given parser
        scraper = cls(db, parser)

        session = db.session

        # Go through the roots and scrape them, inserting into the articles table
        for r in session.query(Root).all():

            print("Scraping root of {0} at {1}...".format(r.description, r.url))

            # Process a single top-level domain and root URL,
            # parsing child URLs that have not been seen before
            result = scraper.scrape_root(r)

        helpers = dict()

        # Go through any unscraped articles and scrape them
        for a in session.query(Article) \
            .filter(Article.scraped == None).filter(Article.root_id != None):

            # Obtain an instance of a scraper helper class for this root
            helper_id = a.root.scr_module + "." + a.root.scr_class
            print("Preparing to scrape article {0}, helper is {1}".format(a.url, helper_id))
            if helper_id in helpers:
                # Already instantiated a helper: get it
                helper = helpers[helper_id]
            else:
                # Dynamically instantiate a new helper class instance
                mod = importlib.import_module(a.root.scr_module)
                print("import_module({0}) yielded {1}".format(a.root.scr_module, mod))
                helper_Class = getattr(mod, a.root.scr_class, None) if mod else None
                helper = helper_Class(a.root) if helper_Class else None
                helpers[helper_id] = helper
                if not helper:
                    print("Unable to instantiate helper {0}".format(helper_id))
            if not helper:
                continue
            # The helper is ready: Go ahead and scrape the article
            scraper.scrape_article(a.url, helper)


def run():

    print("\n\n------ Reynir starting scrape -------\n")

    parser = BIN_Parser(verbose = False) # Don't emit diagnostic messages
    g = parser.grammar
    db = Scraper_DB()

    print("{3} dated {4} has {0} nonterminals, {1} terminals, {2} productions"
        .format(g.num_nonterminals, g.num_terminals, g.num_productions,
            g.file_name, g.file_time))

    Scraper.go(db, parser)

    print("\n------ Scrape completed -------\n")


def init_roots():
    """ Create tables and initialize the scraping roots, if not already present """

    db = Scraper_DB()

    try:

        db.create_tables()
        session = db.session

        ROOTS = [
            # Root URL, top-level domain, description, authority
            ("http://kjarninn.is", "kjarninn.is", "Kjarninn", 1.0, "scrapers.default", "KjarninnScraper"),
            ("http://www.ruv.is", "ruv.is", "RÚV", 1.0, "scrapers.default", "RuvScraper"),
            # ("http://www.visir.is", "visir.is", "Vísir", 0.8, "scrapers.default", "VisirScraper"),
            ("http://www.mbl.is/frettir/", "mbl.is", "Morgunblaðið", 0.6, "scrapers.default", "MblScraper"),
            ("http://eyjan.pressan.is", "eyjan.pressan.is", "Eyjan", 0.4, "scrapers.default", "EyjanScraper")
        ]

        for url, domain, description, authority, scr_module, scr_class in ROOTS:
            r = Root(url = url, domain = domain, description = description, authority = authority,
                scr_module = scr_module, scr_class = scr_class)
            session.add(r)

        try:
            # Commit the inserts
            session.commit()
        except IntegrityError as e:
            # The roots already exist: roll back and continue
            session.rollback()

        rlist = session.query(Root).all()
        print("Roots initialized as follows:")
        for r in rlist:
            print("{0}".format(r))

    except Exception as e:
        print("{0}".format(e))


class Usage(Exception):

    def __init__(self, msg):
        self.msg = msg


def main(argv = None):
    """ Guido van Rossum's pattern for a Python main function """

    if argv is None:
        argv = sys.argv
    try:
        try:
            opts, args = getopt.getopt(argv[1:], "hi", ["help", "init"])
        except getopt.error as msg:
             raise Usage(msg)
        init = False
        # Process options
        for o, a in opts:
            if o in ("-h", "--help"):
                print(__doc__)
                sys.exit(0)
            elif o in ("-i", "--init"):
                init = True
        # Process arguments
        for arg in args:
            pass

        if init:

            # Initialize the scraper database
            init_roots()

        else:

            # Read the configuration settings file

            try:
                Settings.read("Reynir.conf")
            except ConfigError as e:
                print("Configuration error: {0}".format(e), file = sys.stderr)
                return 2

            # Run the scraper
            run()

    except Usage as err:
        print(err.msg, file = sys.stderr)
        print("For help use --help", file = sys.stderr)
        return 2

    # Completed with no error
    return 0


if __name__ == "__main__":
    sys.exit(main())
