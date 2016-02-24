#!/usr/bin/env python
"""
    Reynir: Natural language processing for Icelandic

    Scraper module

    Copyright (c) 2015 Vilhjalmur Thorsteinsson
    All rights reserved
    See the accompanying README.md file for further licensing and copyright information.

    This module implements a simple web scraper and spider.

    The scraper works from a set of root URLs to periodically scrape child
    URLs from the same parent domain. The root URLs and the
    scraping output are stored in tables in a PostgreSQL database
    called 'scraper', and accessed via SQLAlchemy.

"""


import re
import sys
import getopt
import time
import importlib

#from multiprocessing.dummy import Pool
from multiprocessing import Pool

import urllib.request
import urllib.parse as urlparse
from urllib.error import HTTPError

from contextlib import closing
from datetime import datetime
from collections import OrderedDict

from bs4 import BeautifulSoup, NavigableString

from tokenizer import TOK, tokenize
from reducer import Reducer
from fastparser import Fast_Parser, ParseError, ParseForestDumper
from settings import Settings, ConfigError, UnknownVerbs

from scraperdb import Scraper_DB, Root, Article, IntegrityError


# The HTML parser to use with BeautifulSoup
#_HTML_PARSER = "html5lib"
_HTML_PARSER = "html.parser"


class ArticleDescr:

    """ Unit of work descriptor that is shipped between processes """

    def __init__(self, root, url):
        self.root = root
        self.url = url


class Scraper:

    """ The worker class that scrapes the known roots """

    # HTML tags that we explicitly don't want to look at
    _EXCLUDE_TAGS = frozenset(["script", "audio", "video", "style"])

    # HTML tags that typically denote blocks (DIV-like), not inline constructs (SPAN-like)
    _BLOCK_TAGS = frozenset(["p", "h1", "h2", "h3", "h4", "div",
        "main", "article", "header", "section",
        "table", "thead", "tbody", "tr", "td", "ul", "li",
        "form", "option", "input", "label",
        "figure", "figcaption", "footer"])

    _WHITESPACE_TAGS = frozenset(["br", "img"])

    # Cache of instantiated scrape helpers
    _helpers = dict()

    _parser = None
    _db = None

    @classmethod
    def _init_class(cls):
        """ Initialize class attributes """
        if cls._parser is None:
            cls._parser = Fast_Parser(verbose = False) # Don't emit diagnostic messages
            cls._db = Scraper_DB()

    @classmethod
    def cleanup(cls):
        if cls._parser is not None:
            cls._parser.cleanup()
            cls._parser = None

    def __init__(self):

        Scraper._init_class()

        print("Initializing scraper instance")
        g = Scraper._parser.grammar
        print("{3} dated {4} has {0} nonterminals, {1} terminals, {2} productions"
            .format(g.num_nonterminals, g.num_terminals, g.num_productions,
                g.file_name, str(g.file_time)[0:19]))

    class _TextList:

        """ Accumulates raw text blocks and eliminates unnecessary nesting indicators """

        def __init__(self):
            self._result = []
            self._nesting = 0

        def append(self, w):
            if self._nesting > 0:
                self._result.append(" [[ " * self._nesting)
                self._nesting = 0
            self._result.append(w)

        def append_whitespace(self):
            if self._nesting == 0:
                # No need to append whitespace if we're just inside a begin-block
                self._result.append(" ")

        def begin(self):
            self._nesting += 1

        def end(self):
            if self._nesting > 0:
                self._nesting -= 1
            else:
                self._result.append(" ]] ")

        def result(self):
            return "".join(self._result)

    @staticmethod
    def _extract_text(soup, result):
        """ Append the human-readable text found in an HTML soup to the result TextList """
        for t in soup.children:
            if type(t) == NavigableString:
                # Text content node
                result.append(t)
            elif isinstance(t, NavigableString):
                # Comment, CDATA or other text data: ignore
                pass
            elif t.name in Scraper._WHITESPACE_TAGS:
                # Tags that we interpret as whitespace, such as <br> and <img>
                result.append_whitespace()
            elif t.name in Scraper._BLOCK_TAGS:
                # Nested block tag
                result.begin() # Begin block
                Scraper._extract_text(t, result)
                result.end() # End block
            elif t.name not in Scraper._EXCLUDE_TAGS:
                # Non-block tag
                Scraper._extract_text(t, result)

    @staticmethod
    def _to_tokens(soup):
        """ Convert an HTML soup root into a parsable token stream """

        # Extract the text content of the HTML into a list
        tlist = Scraper._TextList()
        Scraper._extract_text(soup, tlist)
        text = tlist.result()
        tlist = None # Free memory

        # Eliminate soft hyphen and zero width space characters
        text = re.sub('\u00AD|\u200B', '', text)
        # Eliminate consecutive whitespace
        text = re.sub(r'\s+', ' ', text)

        # Tokenize the resulting text, returning a generator
        return tokenize(text)


    @classmethod
    def _fetch_url(cls, url):
        """ Low-level fetch of an URL, returning a decoded string """
        encoding = 'utf-8' # Assumed default encoding (should strictly speaking be ISO-8859-1)
        html_doc = None
        try:
            with closing(urllib.request.urlopen(url)) as response:
                if response:
                    # Decode the HTML Content-type header to obtain the
                    # document type and the charset (content encoding), if specified
                    ctype = response.getheader("Content-type", "")
                    if ';' in ctype:
                        s = ctype.split(';')
                        ctype = s[0]
                        enc = s[1].strip()
                        s = enc.split('=')
                        if s[0] == "charset" and len(s) == 2:
                            encoding = s[1]
                    if ctype == "text/html":
                        html_doc = response.read() # html_doc is a bytes object
                        if html_doc:
                            html_doc = html_doc.decode(encoding)
        except HTTPError as e:
            print("HTTPError returned: {0}".format(e))
            html_doc = None
        except UnicodeEncodeError as e:
            print("Exception when opening URL {0}: {1}".format(url, e))
            html_doc = None
        except UnicodeDecodeError as e:
            print("Exception when decoding HTML of {0}: {1}".format(url, e))
            html_doc = None
        return html_doc


    @classmethod
    def _get_helper(cls, root):
        """ Return a scrape helper instance for the given root """
        # Obtain an instance of a scraper helper class for this root
        helper_id = root.scr_module + "." + root.scr_class
        if helper_id in Scraper._helpers:
            # Already instantiated a helper: get it
            helper = Scraper._helpers[helper_id]
        else:
            # Dynamically instantiate a new helper class instance
            mod = importlib.import_module(root.scr_module)
            helper_Class = getattr(mod, root.scr_class, None) if mod else None
            helper = helper_Class(root) if helper_Class else None
            Scraper._helpers[helper_id] = helper
            if not helper:
                print("Unable to instantiate helper {0}".format(helper_id))
        return helper


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
            # Make sure the newpath is properly urlencoded
            if newpath:
               newpath = urlparse.quote(newpath)
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


    def scrape_root(self, root, helper):
        """ Scrape a root URL """

        t0 = time.time()
        # Fetch the root URL and scrape all child URLs that refer
        # to the same domain suffix and we haven't seen before
        print("Processing root {0}".format(root.url))

        # Read the HTML document at the root URL
        html_doc = Scraper._fetch_url(root.url)
        if not html_doc:
            print("Unable to fetch root {0}".format(root.url))
            return

        # Parse the HTML document
        soup = BeautifulSoup(html_doc, _HTML_PARSER)

        # Obtain the set of child URLs to fetch
        fetch_set = self.children(root, soup)

        # Add the children whose URLs we don't already have to the
        # scraper articles table
        with closing (self._db.session) as session:

            for url in fetch_set:

                if helper and helper.skip_url(url):
                    # The helper doesn't want this URL
                    continue

                try:
                    article = Article(url = url, root_id = root.id)
                    # Leave article.scraped as NULL for later retrieval
                    session.add(article)
                    session.commit()
                except IntegrityError as e:
                    # Article URL already exists in database:
                    # roll back and continue
                    session.rollback()
                except Exception as e:
                    session.rollback()

        t1 = time.time()

        print("Processing completed in {0:.2f} seconds".format(t1 - t0))


    def scrape_article(self, url, helper):
        """ Scrape a single article, retrieving its HTML and metadata """

        t0 = time.time()
        # Fetch the root URL and scrape all child URLs that refer
        # to the same domain suffix and we haven't seen before
        print("Processing article {0}".format(url))

        # Read the HTML document at the article URL
        html_doc = None if helper.skip_url(url) else Scraper._fetch_url(url)

        # Parse the HTML document
        soup = BeautifulSoup(html_doc, _HTML_PARSER) if html_doc else None

        # Use the scrape helper to analyze the soup and return
        # metadata
        metadata = helper.get_metadata(soup) if soup else None

        # Upate the article info
        with closing(self._db.session) as session:

            try:

                article = session.query(Article).filter_by(url = url).one_or_none()

                if article:

                    article.scraped = datetime.utcnow()

                    if metadata:
                        article.heading = metadata.heading
                        article.author = metadata.author
                        article.timestamp = metadata.timestamp
                        article.authority = metadata.authority
                        article.scr_module = helper.scr_module
                        article.scr_class = helper.scr_class
                        article.scr_version = helper.scr_version
                        article.html = html_doc
                    else:
                        # No metadata: mark the article as scraped with no HTML
                        article.html = None

                session.commit()

            except IntegrityError as e:
                # Roll back and continue
                session.rollback()

            except Exception as e:
                session.rollback()

        t1 = time.time()

        print("Processing completed in {0:.2f} seconds".format(t1 - t0))


    def parse_article(self, url, helper):
        """ Parse a single article """

        print("Parsing article {0}".format(url))

        # Load the article
        with closing(self._db.session) as session:

            article = session.query(Article).filter_by(url = url).one()

            # Make an HTML soup out of it
            soup = BeautifulSoup(article.html, _HTML_PARSER) if article.html else None

            # Ask the helper to find the actual content to be parsed
            content = helper.get_content(soup) if soup else None

            # Convert the content soup to a token iterable (generator)
            toklist = Scraper._to_tokens(content) if content else None

            # Count sentences
            num_sent = 0
            num_parsed_sent = 0
            total_ambig = 0.0
            total_tokens = 0

            # Dict of parse trees in string dump format,
            # stored by sentence index (1-based)
            trees = OrderedDict()

            t0 = time.time()
            bp = Scraper._parser

            if toklist:

                sent_begin = 0
                rdc = Reducer(bp.grammar)

                for ix, t in enumerate(toklist):
                    if t[0] == TOK.S_BEGIN:
                        num_sent += 1
                        sent = []
                        sent_begin = ix
                    elif t[0] == TOK.S_END:
                        slen = len(sent)
                        # Parse the accumulated sentence
                        err_index = None
                        num = 0
                        try:
                            # Parse the sentence
                            forest = bp.go(sent)
                            if forest is not None:
                                num = Fast_Parser.num_combinations(forest)
                                if num > 0:
                                    # Reduce the resulting forest
                                    forest = rdc.go(forest)
                        except ParseError as e:
                            forest = None
                            # Obtain the index of the offending token
                            err_index = e.token_index
                        if num > 0:
                            num_parsed_sent += 1
                            # Calculate the 'ambiguity factor'
                            ambig_factor = num ** (1 / slen)
                            # Do a weighted average on sentence length
                            total_ambig += ambig_factor * slen
                            total_tokens += slen
                            # Obtain a text representation of the parse tree
                            trees[num_sent] = ParseForestDumper.dump_forest(forest)

                    elif t[0] == TOK.P_BEGIN:
                        pass
                    elif t[0] == TOK.P_END:
                        pass
                    else:
                        sent.append(t)

            parse_time = time.time() - t0

            article.parsed = datetime.utcnow()
            article.parser_version = bp.version
            article.num_sentences = num_sent
            article.num_parsed = num_parsed_sent
            article.ambiguity = (total_ambig / total_tokens) if total_tokens > 0 else 1.0

            # Create a tree representation string out of all the accumulated parse trees
            article.tree = "".join("S{0}\n{1}\n".format(key, val) for key, val in trees.items())

            session.commit()

        print("Parsing of {2}/{1} sentences completed in {0:.2f} seconds".format(parse_time, num_sent, num_parsed_sent))

    @classmethod
    def helper_for(cls, session, url):
        """ Return a scrape helper for the root of the given url """
        s = urlparse.urlsplit(url)
        root = None
        # Find which root this URL belongs to, if any
        for r in session.query(Root).all():
            root_s = urlparse.urlsplit(r.url)
            # This URL belongs to a root if the domain (netloc) part
            # ends with the root domain (netloc)
            if s.netloc.endswith(root_s.netloc):
                root = r
                break
        # Obtain a scrape helper for the root, if any
        return cls._get_helper(root) if root else None

    @classmethod
    def is_known_url(cls, url):
        """ Return True if the URL has already been scraped """

        found = False
        with closing(Scraper_DB().session) as session:

            try:
                article = session.query(Article).filter_by(url = url) \
                    .filter(Article.scraped != None).one_or_none()
                if article:
                    found = True
            except Exception:
                pass

            session.commit()

        return found

    @classmethod
    def store_parse(cls, url, result, trees, session = None):
        """ Store a new parse of an article """

        success = True
        new_session = False
        if not session:
            db = Scraper_DB()
            session = db.session
            new_session = True

        try:

            article = session.query(Article).filter_by(url = url) \
                .filter(Article.scraped != None).one_or_none()

            if article:
                article.parsed = datetime.utcnow()
                article.parser_version = result["version"]
                article.num_sentences = result["num_sent"]
                article.num_parsed = result["num_parsed_sent"]
                article.ambiguity = result["avg_ambig_factor"]

                # Create a tree representation string out of all the accumulated parse trees
                article.tree = "".join("S{0}\n{1}\n".format(key, val) for key, val in trees.items())
            else:
                success = False
                print("Unable to store new parse of url {0}".format(url))

            session.commit()

        except Exception as e:
            success = False
            print("Unable to store new parse of url {0}, exception {1}".format(url, e))

        finally:
            if new_session:
                session.close()

        return success

    @classmethod
    def fetch_url(cls, url, session = None):
        """ Fetch a URL using the scraping mechanism, returning
            a tuple (metadata, content) or None if error """
        html_doc = cls._fetch_url(url)
        if not html_doc:
            return None

        new_session = False
        if not session:
            db = Scraper_DB()
            session = db.session
            new_session = True

        try:
            helper = cls.helper_for(session, url)
            # Parse the HTML
            soup = BeautifulSoup(html_doc, _HTML_PARSER)
            if not soup or not soup.html:
                print("Scraper.fetch_url(): No soup or no soup.html")
                return None

            # Obtain the metadata and the content from the resulting soup
            metadata = helper.get_metadata(soup) if helper else None
            content = helper.get_content(soup) if helper else soup.html.body
            return (metadata, content)

        finally:
            if new_session:
                session.close()

    def _scrape_single_root(self, r):
        """ Single root scraper that will be called by a process within a
            multiprocessing pool """
        try:
            print("Scraping root of {0} at {1}...".format(r.description, r.url))
            # Process a single top-level domain and root URL,
            # parsing child URLs that have not been seen before
            helper = Scraper._get_helper(r)
            if helper:
                self.scrape_root(r, helper)
        except Exception as e:
            print("Exception when scraping root at {0}: {1}".format(r.url, e))

    def _scrape_single_article(self, d):
        """ Single article scraper that will be called by a process within a
            multiprocessing pool """
        try:
            helper = Scraper._get_helper(d.root)
            if helper:
                self.scrape_article(d.url, helper)
        except Exception as e:
            print("Exception when scraping article at {0}: {1}".format(d.url, e))

    def _parse_single_article(self, d):
        """ Single article parser that will be called by a process within a
            multiprocessing pool """
        try:
            helper = Scraper._get_helper(d.root)
            if helper:
                self.parse_article(d.url, helper)
                # Save the unknown verbs accumulated during parsing, if any
                UnknownVerbs.write()
        except Exception as e:
            print("Exception when parsing article at {0}: {1}".format(d.url, e))
            raise e from e


    def go(self, limit = 0):
        """ Run a scraping pass from all roots in the scraping database """

        db = Scraper._db

        # Go through the roots and scrape them, inserting into the articles table
        with closing(db.session) as session:

            def iter_roots():
                """ Iterate the roots """
                for r in session.query(Root).all():
                    yield r

            # Use a multiprocessing pool to scrape the roots

            pool = Pool(4)
            pool.map(self._scrape_single_root, iter_roots())
            pool.close()
            pool.join()

            def iter_unscraped_articles():
                """ Go through any unscraped articles and scrape them """
                for a in session.query(Article) \
                    .filter(Article.scraped == None).filter(Article.root_id != None):
                    yield ArticleDescr(a.root, a.url)

            # Use a multiprocessing pool to scrape the articles

            pool = Pool(8)
            pool.map(self._scrape_single_article, iter_unscraped_articles())
            pool.close()
            pool.join()

            def iter_unparsed_articles(limit):
                """ Go through any unparsed articles and parse them """
                count = 0
                for a in session.query(Article) \
                    .filter(Article.scraped != None).filter(Article.tree == None) \
                    .filter(Article.root_id != None):
                    yield ArticleDescr(a.root, a.url)
                    count += 1
                    if limit > 0 and count >= limit: # !!! DEBUG
                        break

            # Use a multiprocessing pool to parse the articles

            pool = Pool() # Defaults to using as many processes as there are CPUs
            pool.map(self._parse_single_article, iter_unparsed_articles(limit))
            pool.close()
            pool.join()


    def stats(self):
        """ Return statistics from the scraping database """

        db = Scraper._db

        q = "select count(*) from articles;"

        result = db.execute(q).fetchall()[0]

        num_articles = result[0]

        q = "select count(*) from articles where scraped is not null;"

        result = db.execute(q).fetchall()[0]

        num_scraped = result[0]

        q = "select count(*) from articles where tree is not null;"

        result = db.execute(q).fetchall()[0]

        num_parsed = result[0]
        
        q = "select count(*) from articles where tree is not null and num_sentences > 1;"

        result = db.execute(q).fetchall()[0]

        num_parsed_over_1 = result[0]
        
        print ("Num_articles is {0}, scraped {1}, parsed {2}, parsed with >1 sentence {3}"
            .format(num_articles, num_scraped, num_parsed, num_parsed_over_1))

        q = "select sum(num_sentences) as sent, sum(num_parsed) as parsed " \
            "from articles where tree is not null and num_sentences > 1;"

        result = db.execute(q).fetchall()[0]

        num_sentences = result[0]
        num_sent_parsed = result[1]

        print ("Num_sentences is {0}, num_sent_parsed is {1}, ratio is {2:.1f}%"
            .format(num_sentences, num_sent_parsed, 100.0 * num_sent_parsed / num_sentences))


def scrape_articles(limit = 0):

    print("------ Reynir starting scrape -------")
    ts = "{0}".format(datetime.utcnow())[0:19]
    print("Time: {0}, limit: {1}\n".format(ts, limit))

    try:
        try:
            sc = Scraper()
            sc.go(limit = limit)
        except Exception as e:
            print("Scraper terminated with exception {0}".format(e))
        finally:
            sc.stats()
    finally:
        sc = None
        Scraper.cleanup()

    ts = "{0}".format(datetime.utcnow())[0:19]
    print("\nTime: {0}".format(ts))

    print("------ Scrape completed -------")


def init_roots():
    """ Create tables and initialize the scraping roots, if not already present """

    db = Scraper_DB()

    try:

        db.create_tables()

        with closing(db.session) as session:

            ROOTS = [
                # Root URL, top-level domain, description, authority
                ("http://kjarninn.is", "kjarninn.is", "Kjarninn", 1.0, "scrapers.default", "KjarninnScraper"),
                ("http://www.ruv.is", "ruv.is", "RÚV", 1.0, "scrapers.default", "RuvScraper"),
                # ("http://www.visir.is", "visir.is", "Vísir", 0.8, "scrapers.default", "VisirScraper"),
                ("http://www.mbl.is/frettir/", "mbl.is", "Morgunblaðið", 0.6, "scrapers.default", "MblScraper"),
                ("http://eyjan.pressan.is", "eyjan.pressan.is", "Eyjan", 0.4, "scrapers.default", "EyjanScraper"),
                ("http://stjornlagarad.is", "stjornlagarad.is", "Stjórnlagaráð", 1.0, "scrapers.default", "StjornlagaradScraper")
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
            opts, args = getopt.getopt(argv[1:], "hil:", ["help", "init", "limit="])
        except getopt.error as msg:
             raise Usage(msg)
        init = False
        limit = 10 # !!! DEBUG default limit on number of articles to parse, unless otherwise specified
        # Process options
        for o, a in opts:
            if o in ("-h", "--help"):
                print(__doc__)
                sys.exit(0)
            elif o in ("-i", "--init"):
                init = True
            elif o in ("-l", "--limit"):
                # Maximum number of articles to parse
                try:
                    limit = int(a)
                except Exception as e:
                    pass
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
            scrape_articles(limit = limit)

    except Usage as err:
        print(err.msg, file = sys.stderr)
        print("For help use --help", file = sys.stderr)
        return 2

    # Completed with no error
    return 0


if __name__ == "__main__":
    sys.exit(main())
