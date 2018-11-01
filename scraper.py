#!/usr/bin/env python
"""

    Reynir: Natural language processing for Icelandic

    Scraper module

    Copyright (C) 2018 Miðeind ehf.
    Author: Vilhjálmur Þorsteinsson

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


    This module implements a simple web scraper and spider.

    The scraper works from a set of root URLs to periodically scrape child
    URLs from the same parent domain. The root URLs and the
    scraping output are stored in tables in a PostgreSQL database
    and accessed via SQLAlchemy.

"""

import sys
import gc
import getopt
import time
import logging

# import traceback

# from multiprocessing.dummy import Pool, cpu_count
from multiprocessing import Pool, cpu_count

from settings import Settings, ConfigError
from fetcher import Fetcher
from article import Article
from scraperinit import init_roots

from scraperdb import SessionContext, Root, IntegrityError
from scraperdb import Article as ArticleRow


class ArticleDescr:

    """ Unit of work descriptor that is shipped between processes """

    def __init__(self, seq, root, url):
        self.seq = seq  # Sequence number
        self.root = root
        self.url = url


class Scraper:

    """ The worker class that scrapes the known roots """

    def __init__(self):

        logging.info("Initializing scraper instance")

    def scrape_root(self, root, helper):
        """ Scrape a root URL """

        t0 = time.time()
        # Fetch the root URL and scrape all child URLs that refer
        # to the same domain suffix and we haven't seen before
        logging.info("Fetching root {0}".format(root.url))

        # Read the HTML document at the root URL
        html_doc = Fetcher.raw_fetch_url(root.url)
        if not html_doc:
            logging.warning("Unable to fetch root {0}".format(root.url))
            return

        # Parse the HTML document
        soup = Fetcher.make_soup(html_doc)

        # Obtain the set of child URLs to fetch
        fetch_set = Fetcher.children(root, soup)

        # Add the children whose URLs we don't already have to the
        # scraper articles table
        with SessionContext() as session:

            for url in fetch_set:

                if helper and helper.skip_url(url):
                    # The helper doesn't want this URL
                    continue

                # noinspection PyBroadException
                try:
                    article = ArticleRow(url=url, root_id=root.id)
                    # Leave article.scraped as NULL for later retrieval
                    session.add(article)
                    session.commit()
                except IntegrityError as e:
                    # Article URL already exists in database:
                    # roll back and continue
                    session.rollback()
                except Exception as e:
                    logging.warning(
                        "Roll back due to exception in scrape_root: {0}"
                        .format(e)
                    )
                    session.rollback()

        t1 = time.time()

        logging.info("Root scrape completed in {0:.2f} seconds".format(t1 - t0))

    def scrape_article(self, url, helper):
        """ Scrape a single article, retrieving its HTML and metadata """

        if helper.skip_url(url):
            logging.info("Skipping article {0}".format(url))
            return

        # Fetch the root URL and scrape all child URLs that refer
        # to the same domain suffix and we haven't seen before
        logging.info("Scraping article {0}".format(url))
        t0 = time.time()

        with SessionContext(commit=True) as session:

            a = Article.scrape_from_url(url, session)
            if a is not None:
                a.store(session)

        t1 = time.time()
        logging.info("Scraping completed in {0:.2f} seconds".format(t1 - t0))

    def parse_article(self, seq, url, helper):
        """ Parse a single article """

        logging.info("[{1}] Parsing article {0}".format(url, seq))
        t0 = time.time()
        num_sentences = 0
        num_parsed = 0

        # Load the article
        with SessionContext(commit=True) as session:
            a = Article.load_from_url(url, session)
            if a is not None:
                a.parse(session)
                num_sentences = a.num_sentences
                num_parsed = a.num_parsed

        t1 = time.time()
        logging.info(
            "[{3}] Parsing of {2}/{1} sentences completed in {0:.2f} seconds"
            .format(t1 - t0, num_sentences, num_parsed, seq)
        )

    def _scrape_single_root(self, r):
        """ Single root scraper that will be called by a process within a
            multiprocessing pool """
        if r.domain.endswith(".local"):
            # We do not scrape .local roots
            return
        try:
            logging.info("Scraping root of {0} at {1}...".format(r.description, r.url))
            # Process a single top-level domain and root URL,
            # parsing child URLs that have not been seen before
            helper = Fetcher._get_helper(r)
            if helper:
                self.scrape_root(r, helper)
        except Exception as e:
            logging.warning(
                "Exception when scraping root at {0}: {1!r}"
                .format(r.url, e)
            )

    def _scrape_single_article(self, d):
        """ Single article scraper that will be called by a process within a
            multiprocessing pool """
        try:
            helper = Fetcher._get_helper(d.root)
            if helper:
                self.scrape_article(d.url, helper)
        except Exception as e:
            logging.warning(
                "[{2}] Exception when scraping article at {0}: {1!r}"
                .format(d.url, e, d.seq)
            )

    def _parse_single_article(self, d):
        """ Single article parser that will be called by a process within a
            multiprocessing pool """
        try:
            helper = Fetcher._get_helper(d.root)
            if helper:
                self.parse_article(d.seq, d.url, helper)
        except KeyboardInterrupt:
            logging.info("KeyboardInterrupt in _parse_single_article()")
            sys.exit(1)
        except MemoryError:
            # Nothing to do but give up on this process
            sys.exit(1)
        except Exception as e:
            logging.warning(
                "[{2}] Exception when parsing article at {0}: {1!r}"
                .format(d.url, e, d.seq)
            )
            # traceback.print_exc()
            # raise
        return True

    def go(self, reparse=False, limit=0, urls=None):
        """ Run a scraping pass from all roots in the scraping database """

        version = Article.parser_version()

        # Go through the roots and scrape them, inserting into the articles table
        with SessionContext(commit=True) as session:

            if urls is None and not reparse:

                def iter_roots():
                    """ Iterate the roots to be scraped """
                    for r in session.query(Root).filter(Root.scrape == True).all():
                        yield r

                # Use a multiprocessing pool to scrape the roots

                pool = Pool(4)
                pool.imap_unordered(self._scrape_single_root, iter_roots())
                pool.close()
                pool.join()

                # noinspection PyComparisonWithNone
                def iter_unscraped_articles():
                    """ Go through any unscraped articles and scrape them """
                    # Note that the query(ArticleRow) below cannot be directly changed
                    # to query(ArticleRow.root, ArticleRow.url) since ArticleRow.root is a joined subrecord
                    seq = 0
                    for a in (
                        session
                        .query(ArticleRow)
                        .filter(ArticleRow.scraped == None)
                        .filter(ArticleRow.root_id != None)
                        .yield_per(100)
                    ):
                        yield ArticleDescr(seq, a.root, a.url)
                        seq += 1

                # Use a multiprocessing pool to scrape the articles

                pool = Pool(8)
                pool.imap_unordered(
                    self._scrape_single_article, iter_unscraped_articles()
                )
                pool.close()
                pool.join()

            # noinspection PyComparisonWithNone
            def iter_unparsed_articles(reparse, limit):
                """ Go through articles to be parsed """
                # Fetch 100 rows at a time
                # Note that the query(ArticleRow) below cannot be directly changed
                # to query(ArticleRow.root, ArticleRow.url) since ArticleRow.root is a joined subrecord
                q = session.query(ArticleRow).filter(ArticleRow.scraped != None)
                if reparse:
                    # Reparse articles that were originally parsed with an older
                    # grammar and/or parser version
                    q = (
                        q
                        .filter(ArticleRow.parser_version < version)
                        .order_by(ArticleRow.parsed)
                    )
                else:
                    # Only parse articles that have no parse tree
                    q = q.filter(ArticleRow.tree == None)
                q = q.filter(ArticleRow.root_id != None).yield_per(100)
                if limit > 0:
                    # Impose a limit on the query, if given
                    q = q.limit(limit)
                for seq, a in enumerate(q):
                    yield ArticleDescr(seq, a.root, a.url)

            def iter_urls(urls):
                """ Iterate through the text file whose name is given in urls """
                seq = 0
                with open(urls, "r") as f:
                    for url in f:
                        url = url.strip()
                        if url:
                            a = (
                                session
                                .query(ArticleRow)
                                .filter(ArticleRow.url == url)
                                .one_or_none()
                            )
                            if a is not None:
                                # Found the article: yield it
                                yield ArticleDescr(seq, a.root, a.url)
                                seq += 1

            # Use a multiprocessing pool to parse the articles.
            # Let the pool work on chunks of articles, recycling the
            # processes after each chunk to contain memory creep.

            CPU_COUNT = cpu_count()
            # Distribute the load between the CPUs, although never exceeding
            # 100 articles per CPU per process cycle
            if limit > 0:
                CHUNK_SIZE = min(100 * CPU_COUNT, limit)
            else:
                CHUNK_SIZE = 100 * CPU_COUNT
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
                    if lcnt == CHUNK_SIZE or (0 < limit <= cnt + lcnt):
                        break
                if lcnt:
                    # Run garbage collection to minimize common memory footprint
                    gc.collect()
                    logging.info(
                        "Parser processes forking, chunk of {0} articles"
                        .format(lcnt)
                    )
                    # Defaults to using as many processes as there are CPUs
                    pool = Pool()
                    try:
                        pool.imap_unordered(self._parse_single_article, adlist)
                    except Exception as e:
                        logging.warning("Caught exception: {0}".format(e))
                    pool.close()
                    pool.join()
                    cnt += lcnt
                    logging.info(
                        "Parser processes joined, chunk of {0} articles parsed, total {1}"
                        .format(lcnt, cnt)
                    )
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

        logging.info(
            "Num_articles is {0}, scraped {1}, parsed {2}, parsed with >1 sentence {3}"
            .format(num_articles, num_scraped, num_parsed, num_parsed_over_1)
        )

        q = (
            "select sum(num_sentences) as sent, sum(num_parsed) as parsed "
            "from articles where tree is not null and num_sentences > 1;"
        )

        result = db.execute(q).fetchall()[0]

        num_sentences = result[0] or 0  # Result of query can be None
        num_sent_parsed = result[1] or 0

        logging.info(
            "Num_sentences is {0}, num_sent_parsed is {1}, ratio is {2:.1f}%"
            .format(num_sentences, num_sent_parsed, 100.0 * num_sent_parsed / num_sentences)
        )


def scrape_articles(reparse=False, limit=0, urls=None):

    logging.info("------ Reynir starting scrape -------")
    if urls is None:
        logging.info("Limit: {0}, reparse: {1}".format(limit, reparse))
    else:
        logging.info("URLs read from: {0}".format(urls))
    t0 = time.time()

    try:
        sc = Scraper()
        try:
            sc.go(reparse=reparse, limit=limit, urls=urls)
            # Successful finish: print stats
            sc.stats()
        except KeyboardInterrupt:
            # Terminate process upon Ctrl+C
            logging.info("KeyboardInterrupt: exiting process")
            # sys.exit(1)
        except Exception as e:
            logging.warning("Scraper terminated with exception {0}".format(e))
    finally:
        pass

    t1 = time.time()
    logging.info("Elapsed: {0:.1f} minutes".format((t1 - t0) / 60))
    if limit:
        logging.info("Average: {0:.2f} seconds per article".format((t1 - t0) / limit))

    logging.info("------ Scrape completed -------")


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


def main(argv=None):
    """ Guido van Rossum's pattern for a Python main function """

    if argv is None:
        argv = sys.argv
    try:
        try:
            opts, args = getopt.getopt(
                argv[1:], "hirl:u:", ["help", "init", "reparse", "limit=", "urls="]
            )
        except getopt.error as msg:
            raise Usage(msg)
        init = False
        # !!! DEBUG default limit on number of articles to parse, unless otherwise specified
        limit = 10
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
            elif o in ("-u", "--urls"):
                urls = a  # Text file with list of URLs

        # Process arguments
        for _ in args:
            pass

        # Set logging format
        logging.basicConfig(
            format="%(asctime)s %(levelname)s:%(message)s", level=logging.INFO
        )

        # Read the configuration settings file
        try:
            Settings.read("config/Reynir.conf")
            # Don't run the scraper in debug mode
            Settings.DEBUG = False
        except ConfigError as e:
            print("Configuration error: {0}".format(e), file=sys.stderr)
            return 2

        if init:
            # Initialize the scraper database
            init_roots()
        else:
            # Run the scraper
            scrape_articles(reparse=reparse, limit=limit, urls=urls)

    except Usage as err:
        print(err.msg, file=sys.stderr)
        print("For help use --help", file=sys.stderr)
        return 2

    finally:
        SessionContext.cleanup()
        Article.cleanup()

    # Completed with no error
    return 0


if __name__ == "__main__":
    sys.exit(main())
