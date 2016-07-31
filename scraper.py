#!/usr/bin/env python
"""
    Reynir: Natural language processing for Icelandic

    Scraper module

    Copyright (c) 2016 Vilhjalmur Thorsteinsson
    All rights reserved
    See the accompanying README.md file for further licensing and copyright information.

    This module implements a simple web scraper and spider.

    The scraper works from a set of root URLs to periodically scrape child
    URLs from the same parent domain. The root URLs and the
    scraping output are stored in tables in a PostgreSQL database
    and accessed via SQLAlchemy.

"""

import re
import sys
import getopt
import time
import importlib
#import traceback

#from multiprocessing.dummy import Pool
from multiprocessing import Pool

import requests
import urllib.parse as urlparse
from urllib.error import HTTPError

from contextlib import closing
from datetime import datetime
from collections import OrderedDict

from bs4 import BeautifulSoup, NavigableString

from settings import Settings, ConfigError, UnknownVerbs
from tokenizer import TOK, tokenize
from fastparser import Fast_Parser, ParseError, ParseForestDumper
from reducer import Reducer

from scraperdb import Scraper_DB, SessionContext, Root, Article, Failure, IntegrityError


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

    _WHITESPACE_TAGS = frozenset(["img"]) # <br> was here but now handled separately

    # Cache of instantiated scrape helpers
    _helpers = dict()

    _parser = None

    @classmethod
    def _init_class(cls):
        """ Initialize class attributes """
        if cls._parser is None:
            cls._parser = Fast_Parser(verbose = False) # Don't emit diagnostic messages

    @classmethod
    def cleanup(cls):
        if cls._parser is not None:
            cls._parser.cleanup()
            cls._parser = None

    @classmethod
    def parser_version(cls):
        """ Return the current grammar timestamp + parser version """
        cls._init_class()
        return cls._parser.version

    def __init__(self):

        Scraper._init_class()

        print("Initializing scraper instance")
        g = Scraper._parser.grammar
        print("{3} dated {4} has {0} nonterminals, {1} terminals, {2} productions"
            .format(g.num_nonterminals, g.num_terminals, g.num_productions,
                g.file_name, str(g.file_time)[0:19]))

    class TextList:

        """ Accumulates raw text blocks and eliminates unnecessary nesting indicators """

        def __init__(self):
            self._result = []
            self._nesting = 0

        def append(self, w):
            if self._nesting > 0:
                if w.isspace():
                    # Whitespace is not reason to emit nesting markers
                    return
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

        def insert_break(self):
            """ Used to cut paragraphs at <br> tags """
            if self._nesting == 0:
                self._result.append(" ]] [[ ")

        def result(self):
            """ Return the accumulated result as a string """
            assert self._nesting == 0
            text = "".join(self._result)
            # Eliminate soft hyphen and zero width space characters
            text = re.sub('\u00AD|\u200B', '', text)
            # Eliminate consecutive whitespace
            return re.sub(r'\s+', ' ', text)


    @staticmethod
    def mark_paragraphs(txt):
        """ Insert paragraph markers into plaintext, by newlines """
        return "[[ " + " ]] [[ ".join(txt.split('\n')) + " ]]"


    @staticmethod
    def extract_text(soup, result):
        """ Append the human-readable text found in an HTML soup to the result TextList """
        if soup is None:
            return
        for t in soup.children:
            if type(t) == NavigableString:
                # Text content node
                result.append(t)
            elif isinstance(t, NavigableString):
                # Comment, CDATA or other text data: ignore
                pass
            elif t.name == "br":
                result.insert_break()
            elif t.name in Scraper._WHITESPACE_TAGS:
                # Tags that we interpret as whitespace, such as <img>
                result.append_whitespace()
            elif t.name in Scraper._BLOCK_TAGS:
                # Nested block tag
                result.begin() # Begin block
                Scraper.extract_text(t, result)
                result.end() # End block
            elif t.name not in Scraper._EXCLUDE_TAGS:
                # Non-block tag
                Scraper.extract_text(t, result)


    @staticmethod
    def to_tokens(soup):
        """ Convert an HTML soup root into a parsable token stream """

        # Extract the text content of the HTML into a list
        tlist = Scraper.TextList()
        Scraper.extract_text(soup, tlist)
        text = tlist.result()
        tlist = None # Free memory

        # Tokenize the resulting text, returning a generator
        return tokenize(text)


    @staticmethod
    def tokenize_url(url, info = None):
        """ Open a URL and process the returned response """

        metadata = None
        soup = None

        # Fetch the URL, returning a (metadata, content) tuple or None if error
        if info is None:
            info = Scraper.fetch_url(url)

        if info is not None:
            metadata, soup = info
            if metadata is None:
                if Settings.DEBUG:
                    print("No metadata")
                metadata = dict(heading = "",
                    author = "",
                    timestamp = datetime.utcnow(),
                    authority = 0.0)
            else:
                if Settings.DEBUG:
                    print("Metadata: heading '{0}'".format(metadata.heading))
                    print("Metadata: author '{0}'".format(metadata.author))
                    print("Metadata: timestamp {0}".format(metadata.timestamp))
                    print("Metadata: authority {0:.2f}".format(metadata.authority))
                metadata = vars(metadata) # Convert namedtuple to dict
            metadata["url"] = url

        # Tokenize the resulting text, returning a generator
        # noinspection PyRedundantParentheses
        return (metadata, Scraper.to_tokens(soup))


    @classmethod
    def _fetch_url(cls, url):
        """ Low-level fetch of an URL, returning a decoded string """
        html_doc = None
        try:

            r = requests.get(url)
            if r.status_code == requests.codes.ok:
                html_doc = r.text
            else:
                print("HTTP status {0} for URL {1}".format(r.status_code, url))

        except requests.exceptions.ConnectionError as e:
            print("{0}".format(e))
            html_doc = None
        except requests.exceptions.ChunkedEncodingError as e:
            print("{0}".format(e))
            html_doc = None
        except HTTPError as e:
            print("HTTPError returned: {0}".format(e))
            html_doc = None
        except UnicodeEncodeError as e:
            print("Exception when opening URL {0}: {1}".format(url, e)) # Don't use repr(e) here
            html_doc = None
        except UnicodeDecodeError as e:
            print("Exception when decoding HTML of {0}: {1}".format(url, e)) # Don't use repr(e) here
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


    @staticmethod
    def children(root, soup):
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
            if s.scheme and s.scheme not in { 'http', 'https' }:
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
            if url in { root_url, root_url_slash }:
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
        print("Fetching root {0}".format(root.url))

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
        with SessionContext() as session:

            for url in fetch_set:

                if helper and helper.skip_url(url):
                    # The helper doesn't want this URL
                    continue

                # noinspection PyBroadException
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
                    print("Roll back due to exception in scrape_root: {0}".format(e))
                    session.rollback()

        t1 = time.time()

        print("Root scrape completed in {0:.2f} seconds".format(t1 - t0))


    def scrape_article(self, url, helper):
        """ Scrape a single article, retrieving its HTML and metadata """

        t0 = time.time()
        # Fetch the root URL and scrape all child URLs that refer
        # to the same domain suffix and we haven't seen before
        print("Scraping article {0}".format(url))

        # Read the HTML document at the article URL
        html_doc = None if helper.skip_url(url) else Scraper._fetch_url(url)

        # Parse the HTML document
        soup = BeautifulSoup(html_doc, _HTML_PARSER) if html_doc else None

        # Use the scrape helper to analyze the soup and return
        # metadata
        metadata = helper.get_metadata(soup) if soup else None

        # Upate the article info
        with SessionContext(commit = True) as session:

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

            # The session context automatically commits or rolls back the transaction

        t1 = time.time()

        print("Scraping completed in {0:.2f} seconds".format(t1 - t0))


    def parse_article(self, url, helper):
        """ Parse a single article """

        print("Parsing article {0}".format(url))

        # Load the article
        with SessionContext(commit = True) as session:

            article = session.query(Article).filter_by(url = url).one()

            # Make an HTML soup out of it
            soup = BeautifulSoup(article.html, _HTML_PARSER) if article.html else None

            # Ask the helper to find the actual content to be parsed
            content = helper.get_content(soup) if soup else None

            # Convert the content soup to a token iterable (generator)
            toklist = Scraper.to_tokens(content) if content else None

            # Count sentences
            num_sent = 0
            num_parsed_sent = 0
            total_ambig = 0.0
            total_tokens = 0
            sent = []

            # Dict of parse trees in string dump format,
            # stored by sentence index (1-based)
            trees = OrderedDict()

            # List of sentences that fail to parse
            failures = []

            start_time = time.time()
            bp = Scraper._parser

            if toklist:

                sent_begin = 0
                rdc = Reducer(bp.grammar)

                for ix, t in enumerate(toklist):
                    t0 = t[0]
                    if t0 == TOK.S_BEGIN:
                        sent = []
                        sent_begin = ix
                    elif t0 == TOK.S_END:
                        slen = len(sent)
                        if slen == 0:
                            # Do not include or count zero-length sentences
                            continue
                        # Parse the accumulated sentence
                        num_sent += 1
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
                        else:
                            # Error or no parse: add an error index entry for this sentence
                            trees[num_sent] = "E{0}".format(slen - 1 if err_index is None else err_index)
                            # Add the failing sentence to the list of failures
                            failures.append(" ".join(t.txt for t in sent))

                    elif t0 == TOK.P_BEGIN:
                        pass
                    elif t0 == TOK.P_END:
                        pass
                    else:
                        sent.append(t)

            parse_time = time.time() - start_time

            article.parsed = datetime.utcnow()
            article.parser_version = bp.version
            article.num_sentences = num_sent
            article.num_parsed = num_parsed_sent
            article.ambiguity = (total_ambig / total_tokens) if total_tokens > 0 else 1.0

            # Create a tree representation string out of all the accumulated parse trees
            article.tree = "".join("S{0}\n{1}\n".format(key, val) for key, val in trees.items())

            Scraper.store_failures(session, url, failures)

            # Session is automatically committed

        print("Parsing of {2}/{1} sentences completed in {0:.2f} seconds".format(parse_time, num_sent, num_parsed_sent))

    @classmethod
    def helper_for(cls, session, url):
        """ Return a scrape helper for the root of the given url """
        s = urlparse.urlsplit(url)
        root = None
        # Find which root this URL belongs to, if any
        for r in session.query(Root).all():
            root_s = urlparse.urlsplit(r.url)
            # Find the root of the domain, i.e. www.ruv.is -> ruv.is
            root_domain = '.'.join(root_s.netloc.split('.')[-2:])
            # This URL belongs to a root if the domain (netloc) part
            # ends with the root domain
            if s.netloc == root_domain or s.netloc.endswith('.' + root_domain):
                root = r
                break
        # Obtain a scrape helper for the root, if any
        return cls._get_helper(root) if root else None

    # noinspection PyComparisonWithNone
    @classmethod
    def find_article(cls, url, enclosing_session = None):
        """ Return a scraped article object, if found, else None """
        article = None
        with SessionContext(enclosing_session, commit = True) as session:
            article = session.query(Article).filter_by(url = url) \
                .filter(Article.scraped != None).one_or_none()
        return article

    # noinspection PyComparisonWithNone
    @classmethod
    def is_known_url(cls, url, session = None):
        """ Return True if the URL has already been scraped """
        return cls.find_article(url, session) is not None

    @classmethod
    def store_failures(cls, session, url, failures):
        """ Store sentences that fail to parse """
        assert session is not None
        # Delete previously stored failures for this article
        session.execute(Failure.table().delete().where(Failure.article_url == url))
        # Add the failed sentences to the failure table
        for sentence in failures:
            f = Failure(
                article_url = url,
                sentence = sentence,
                cause = None, # Unknown cause so far
                comment = None, # No comment so far
                timestamp = datetime.utcnow())
            session.add(f)

    # noinspection PyComparisonWithNone
    @classmethod
    def store_parse(cls, url, result, trees, failures, enclosing_session = None):
        """ Store a new parse of an article """

        success = True

        with SessionContext(enclosing_session, commit = True) as session:

            article = session.query(Article).filter_by(url = url) \
                .filter(Article.scraped != None).one_or_none()

            if article:
                article.parsed = datetime.utcnow()
                article.timestamp = result["metadata"]["timestamp"]
                article.parser_version = result["version"]
                article.num_sentences = result["num_sent"]
                article.num_parsed = result["num_parsed_sent"]
                article.ambiguity = result["avg_ambig_factor"]

                # Create a tree representation string out of all the accumulated parse trees
                article.tree = "".join("S{0}\n{1}\n".format(key, val) for key, val in trees.items())

                # Add failures, if any
                Scraper.store_failures(session, url, failures)

            else:
                success = False
                print("Unable to store new parse of url {0}".format(url))

        return success

    @classmethod
    def fetch_url(cls, url, enclosing_session = None):
        """ Fetch a URL using the scraping mechanism, returning
            a tuple (metadata, content) or None if error """

        # Do a straight HTTP fetch
        html_doc = cls._fetch_url(url)
        if not html_doc:
            return None

        with SessionContext(enclosing_session) as session:

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

    @classmethod
    def fetch_article(cls, url, enclosing_session = None):
        """ Fetch a previously scraped article, returning
            a tuple (article, metadata, content) or None if error """

        with SessionContext(enclosing_session) as session:

            article = cls.find_article(url, session)
            if article is None:
                return (None, None, None)

            html_doc = article.html
            if not html_doc:
                return (None, None, None)

            helper = cls.helper_for(session, url)
            # Parse the HTML
            soup = BeautifulSoup(html_doc, _HTML_PARSER)
            if not soup or not soup.html:
                print("Scraper.fetch_article(): No soup or no soup.html")
                return (None, None, None)

            # Obtain the metadata and the content from the resulting soup
            metadata = helper.get_metadata(soup) if helper else None
            content = helper.get_content(soup) if helper else soup.html.body
            return (article, metadata, content)

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
            print("Exception when scraping root at {0}: {1!r}".format(r.url, e))

    def _scrape_single_article(self, d):
        """ Single article scraper that will be called by a process within a
            multiprocessing pool """
        try:
            helper = Scraper._get_helper(d.root)
            if helper:
                self.scrape_article(d.url, helper)
        except Exception as e:
            print("Exception when scraping article at {0}: {1!r}".format(d.url, e))

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
            print("Exception when parsing article at {0}: {1!r}".format(d.url, e))
            #traceback.print_exc()
            #raise e from e


    def go(self, reparse = False, limit = 0, urls = None):
        """ Run a scraping pass from all roots in the scraping database """

        version = Scraper.parser_version()

        # Go through the roots and scrape them, inserting into the articles table
        with SessionContext(commit = True) as session:

            if urls is None and not reparse:

                def iter_roots():
                    """ Iterate the roots """
                    for r in session.query(Root).all():
                        yield r

                # Use a multiprocessing pool to scrape the roots

                pool = Pool(4)
                pool.map(self._scrape_single_root, iter_roots())
                pool.close()
                pool.join()

                # noinspection PyComparisonWithNone
                def iter_unscraped_articles():
                    """ Go through any unscraped articles and scrape them """
                    # Note that the query(Article) below cannot be directly changed
                    # to query(Article.root, Article.url) since Article.root is a joined subrecord
                    for a in session.query(Article) \
                        .filter(Article.scraped == None).filter(Article.root_id != None) \
                        .yield_per(100):
                        yield ArticleDescr(a.root, a.url)

                # Use a multiprocessing pool to scrape the articles

                pool = Pool(8)
                pool.map(self._scrape_single_article, iter_unscraped_articles())
                pool.close()
                pool.join()

            # noinspection PyComparisonWithNone
            def iter_unparsed_articles(reparse, limit):
                """ Go through articles to be parsed """
                # Fetch 100 rows at a time
                # Note that the query(Article) below cannot be directly changed
                # to query(Article.root, Article.url) since Article.root is a joined subrecord
                q = session.query(Article).filter(Article.scraped != None)
                if reparse:
                    # Reparse articles that were originally parsed with an older
                    # grammar and/or parser version
                    q = q.filter(Article.parser_version < version).order_by(Article.parsed)
                else:
                    # Only parse articles that have no parse tree
                    q = q.filter(Article.tree == None)
                q = q.filter(Article.root_id != None).yield_per(100)
                if limit > 0:
                    # Impose a limit on the query, if given
                    q = q.limit(limit)
                for a in q:
                    yield ArticleDescr(a.root, a.url)

            def iter_urls(urls):
                """ Iterate through the text file whose name is given in urls """
                with open(urls, "r") as f:
                    for url in f:
                        url = url.strip()
                        if url:
                            a = session.query(Article).filter(Article.url == url).one_or_none()
                            if a is not None:
                                # Found the article: yield it
                                yield ArticleDescr(a.root, a.url)

            # Use a multiprocessing pool to parse the articles.
            # Let the pool work on chunks of articles, recycling the
            # processes after each chunk to contain memory creep.

            CHUNK_SIZE = 100
            if urls is None:
                g = iter_unparsed_articles(reparse, limit)
            else:
                g = iter_urls(urls)
                limit = 0
            cnt = 0
            while True:
                adlist = []
                lcnt = 0
                for ad in g:
                    adlist.append(ad)
                    lcnt += 1
                    if lcnt == CHUNK_SIZE or (limit > 0 and cnt + lcnt >= limit):
                        break
                if lcnt:
                    # Run garbage collection to minimize common memory footprint
                    import gc
                    gc.collect()
                    print("Parser processes forking, chunk of {0} articles".format(lcnt))
                    pool = Pool() # Defaults to using as many processes as there are CPUs
                    pool.map(self._parse_single_article, adlist)
                    pool.close()
                    pool.join()
                    session.commit()
                    print("Parser processes joined, chunk of {0} articles parsed".format(lcnt))
                    cnt += lcnt
                if lcnt < CHUNK_SIZE:
                    break


    @staticmethod
    def stats():
        """ Return statistics from the scraping database """

        db = SessionContext.db

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

        num_sentences = result[0] or 0 # Result of query can be None
        num_sent_parsed = result[1] or 0

        print ("\nNum_sentences is {0}, num_sent_parsed is {1}, ratio is {2:.1f}%"
            .format(num_sentences, num_sent_parsed, 100.0 * num_sent_parsed / num_sentences))


def scrape_articles(reparse = False, limit = 0, urls = None):

    print("------ Reynir starting scrape -------")
    ts = "{0}".format(datetime.utcnow())[0:19]
    if urls is None:
        print("Time: {0}, limit: {1}, reparse: {2}\n".format(ts, limit, reparse))
    else:
        print("Time: {0}, URLs read from: {1}\n".format(ts, urls))

    try:
        sc = Scraper()
        try:
            sc.go(reparse = reparse, limit = limit, urls = urls)
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

    db = SessionContext.db

    try:

        db.create_tables()

        ROOTS = [
            # Root URL, top-level domain, description, authority
            ("http://kjarninn.is", "kjarninn.is", "Kjarninn", 1.0, "scrapers.default", "KjarninnScraper"),
            ("http://www.ruv.is", "ruv.is", "RÚV", 1.0, "scrapers.default", "RuvScraper"),
            ("http://www.visir.is", "visir.is", "Vísir", 0.8, "scrapers.default", "VisirScraper"),
            ("http://www.mbl.is/frettir/", "mbl.is", "Morgunblaðið", 0.6, "scrapers.default", "MblScraper"),
            ("http://eyjan.pressan.is", "eyjan.pressan.is", "Eyjan", 0.4, "scrapers.default", "EyjanScraper"),
            ("http://kvennabladid.is", "kvennabladid.is", "Kvennablaðið", 0.4, "scrapers.default", "KvennabladidScraper"),
            ("http://stjornlagarad.is", "stjornlagarad.is", "Stjórnlagaráð", 1.0, "scrapers.default", "StjornlagaradScraper"),
            ("https://www.forsaetisraduneyti.is", "forsaetisraduneyti.is", "Forsætisráðuneyti", 1.0, "scrapers.default", "StjornarradScraper"),
            ("https://www.innanrikisraduneyti.is", "innanrikisraduneyti.is", "Innanríkisráðuneyti", 1.0, "scrapers.default", "StjornarradScraper"),
            ("https://www.fjarmalaraduneyti.is", "fjarmalaraduneyti.is", "Fjármálaráðuneyti", 1.0, "scrapers.default", "StjornarradScraper")
        ]

        with SessionContext() as session:
            for url, domain, description, authority, scr_module, scr_class in ROOTS:
                r = Root(url = url, domain = domain, description = description, authority = authority,
                    scr_module = scr_module, scr_class = scr_class)
                session.add(r)
                try:
                    # Commit the insert
                    session.commit()
                except IntegrityError as e:
                    # The root already exist: roll back and continue
                    session.rollback()

            rlist = session.query(Root).all()
            print("Roots initialized as follows:")
            for r in rlist:
                print("{0}".format(r))

    except Exception as e:
        print("{0}".format(e))


__doc__ = """

    Reynir - Natural language processing for Icelandic

    Scraper module

    Usage:
        python scraper.py [options]

    Options:
        -h, --help: Show this help text
        -i, --init: Initialize the scraper database, if required
        -r, --reparse: Reparse the oldest previously parsed articles
        -u filename, --urls=filename: Reparse the URLs listed in the given file
        -l N, --limit=N: Limit parsing session to N articles (default 10)

    If --reparse is not specified, the scraper will read all previously
    unseen articles from the root domains and then proceed to parse any
    unparsed articles (up to a limit, if given).

"""


class Usage(Exception):

    def __init__(self, msg):
        self.msg = msg


def main(argv = None):
    """ Guido van Rossum's pattern for a Python main function """

    if argv is None:
        argv = sys.argv
    try:
        try:
            opts, args = getopt.getopt(argv[1:], "hirl:u:",
                ["help", "init", "reparse", "limit=", "urls="])
        except getopt.error as msg:
             raise Usage(msg)
        init = False
        limit = 10 # !!! DEBUG default limit on number of articles to parse, unless otherwise specified
        reparse = False
        urls = None

        # Process options
        for o, a in opts:
            if o in ("-h", "--help"):
                print(__doc__)
                sys.exit(0)
            elif o in ("-i", "--init"):
                init = True
            elif o in ("-r", "--reparse"):
                reparse = True
            elif o in ("-l", "--limit"):
                # Maximum number of articles to parse
                try:
                    limit = int(a)
                except ValueError:
                    pass
            elif o in ('-u', "--urls"):
                urls = a # Text file with list of URLs

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
            scrape_articles(reparse = reparse, limit = limit, urls = urls)

    except Usage as err:
        print(err.msg, file = sys.stderr)
        print("For help use --help", file = sys.stderr)
        return 2

    finally:
        SessionContext.cleanup()

    # Completed with no error
    return 0


if __name__ == "__main__":
    sys.exit(main())
