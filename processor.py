#!/usr/bin/env python
"""
    Reynir: Natural language processing for Icelandic

    Processor module

    Copyright (c) 2016 Vilhjalmur Thorsteinsson
    All rights reserved
    See the accompanying README.md file for further licensing and copyright information.

    This module implements a processing module for parsed articles.

"""

import getopt
import importlib
import sys
import time

#from multiprocessing.dummy import Pool
from multiprocessing import Pool
from contextlib import closing
from datetime import datetime
from collections import OrderedDict

from settings import Settings, ConfigError
from scraperdb import Scraper_DB, Article
from bindb import BIN_Db
from tree import Tree

_PROFILING = False


class Processor:

    """ The worker class that processes parsed articles """

    _db = None

    @classmethod
    def _init_class(cls):
        """ Initialize class attributes """
        if cls._db is None:
            cls._db = Scraper_DB()

    @classmethod
    def cleanup(cls):
        """ Perform any cleanup """
        cls._db = None

    def __init__(self, processor_directory, single_processor = None):

        Processor._init_class()

        # Dynamically load all processor modules
        # (i.e. .py files found in the processor directory, except those
        # with names starting with an underscore)
        self.processors = []
        import os
        files = [ single_processor + ".py" ] if single_processor else os.listdir(processor_directory)
        for fname in files:
            if not isinstance(fname, str):
                continue
            if not fname.endswith(".py"):
                continue
            if fname.startswith("_"):
                continue
            modname = processor_directory + "." + fname[:-3] # Cut off .py
            try:
                m = importlib.import_module(modname)
                print("Imported processor module {0}".format(modname))
                self.processors.append(m)
            except Exception as e:
                print("Error importing processor module {0}: {1}".format(modname, e))

        if not self.processors:
            if single_processor:
                print("Processor {1} not found in directory {0}".format(processor_directory, single_processor))
            else:
                print("No processing modules found in directory {0}".format(processor_directory))

    def go_single(self, url):
        """ Single article processor that will be called by a process within a
            multiprocessing pool """

        print("Processing article {0}".format(url))
        sys.stdout.flush()

        # Load the article
        with closing(self._db.session) as session:

            try:

                article = session.query(Article).filter_by(url = url).first()

                if not article:
                    print("Article not found in scraper database")
                else:
                    if article.tree:
                        tree = Tree(url, article.authority)
                        # print("Tree:\n{0}\n".format(article.tree))
                        tree.load(article.tree)
                        # Run all processors in turn
                        for p in self.processors:
                            tree.process(session, p)
                    # Mark the article as being processed
                    article.processed = datetime.utcnow()

                # So far, so good: commit to the database
                session.commit()

            except Exception as e:
                # If an exception occurred, roll back the transaction
                session.rollback()
                print("Exception in article {0}, transaction rolled back\nException: {1}".format(url, e))
                raise

        sys.stdout.flush()

    def go(self, from_date = None, limit = 0, force = False, update = False):
        """ Process already parsed articles from the database """

        with closing(self._db.session) as session:

            # noinspection PyComparisonWithNone,PyShadowingNames
            def iter_parsed_articles():
                """ Go through parsed articles and process them """
                q = session.query(Article.url).filter(Article.tree != None)
                if not force:
                    # If force = True, re-process articles even if
                    # they have been processed before
                    if update:
                        # If update, we re-process articles that have been parsed
                        # again in the meantime
                        q = q.filter(Article.processed < Article.parsed).order_by(Article.processed)
                    else:
                        q = q.filter(Article.processed == None)
                if from_date is not None:
                    # Only go through articles parsed since the given date
                    q = q.filter(Article.parsed >= from_date).order_by(Article.parsed)
                if limit > 0:
                    q = q[0:limit]
                for a in q:
                    yield a.url

            if _PROFILING:
                # If profiling, just do a simple map within a single thread and process
                for url in iter_parsed_articles():
                    self.go_single(url)
            else:
                # Use a multiprocessing pool to process the articles
                pool = Pool() # Defaults to using as many processes as there are CPUs
                pool.map(self.go_single, iter_parsed_articles())
                pool.close()
                pool.join()


def process_articles(from_date = None, limit = 0, force = False, update = False, processor = None):

    print("------ Reynir starting processing -------")
    if from_date:
        print("From date: {0}".format(from_date))
    if limit:
        print("Limit: {0} articles".format(limit))
    if force:
        print("Force re-processing: Yes")
    elif update:
        print("Update: Yes")
    if processor:
        print("Invoke single processor: {0}".format(processor))
    ts = "{0}".format(datetime.utcnow())[0:19]
    print("Time: {0}\n".format(ts))

    t0 = time.time()

    try:
        # Run all processors in the processors directory, or the single processor given
        proc = Processor(processor_directory = "processors", single_processor = processor)
        proc.go(from_date, limit = limit, force = force, update = update)
    finally:
        proc = None
        Processor.cleanup()

    t1 = time.time()

    print("\n------ Processing completed -------")
    print("Total time: {0:.2f} seconds".format(t1 - t0))
    ts = "{0}".format(datetime.utcnow())[0:19]
    print("Time: {0}\n".format(ts))


def process_article(url):

    try:
        proc = Processor("processors")
        proc.go_single(url)
    finally:
        proc = None
        Processor.cleanup()


class Usage(Exception):

    def __init__(self, msg):
        self.msg = msg


def init_db():
    """ Initialize the database, to the extent required """

    db = Scraper_DB()
    try:
        db.create_tables()
    except Exception as e:
        print("{0}".format(e))


__doc__ = """

    Reynir - Natural language processing for Icelandic

    Processor module

    Usage:
        python processor.py [options]

    Options:
        -h, --help: Show this help text
        -i, --init: Initialize the processor database, if required
        -f, --force: Force re-processing of already processed articles
        -l=N, --limit=N: Limit processing session to N articles
        -u=U, --url=U: Specify a single URL to process
        -p=P, --processor=P: Specify a single processor to invoke
        --update: Process files that have been reparsed but not reprocessed

"""

def _main(argv = None):
    """ Guido van Rossum's pattern for a Python main function """

    if argv is None:
        argv = sys.argv
    try:
        try:
            opts, args = getopt.getopt(argv[1:], "hifl:u:p:",
                ["help", "init", "force", "update", "limit=", "url=", "processor="])
        except getopt.error as msg:
             raise Usage(msg)
        limit = 10 # !!! DEBUG default limit on number of articles to parse, unless otherwise specified
        init = False
        url = None
        force = False
        update = False
        proc = None # Single processor to invoke
        # Process options
        for o, a in opts:
            if o in ("-h", "--help"):
                print(__doc__)
                sys.exit(0)
            elif o in ("-i", "--init"):
                init = True
            elif o in ("-f", "--force"):
                force = True
            elif o == "--update":
                update = True
            elif o in ("-l", "--limit"):
                # Maximum number of articles to parse
                try:
                    limit = int(a)
                except ValueError as e:
                    pass
            elif o in ("-u", "--url"):
                # Single URL to process
                url = a
            elif o in ("-p", "--processor"):
                # Single processor to invoke
                proc = a
                # In the case of a single processor, we force processing
                # of already processed articles instead of processing new ones
                force = True

        # Process arguments
        for arg in args:
            pass

        if init:
            # Initialize the scraper database
            init_db()
        else:

            # Read the configuration settings file

            try:
                Settings.read("Reynir.conf")
            except ConfigError as e:
                print("Configuration error: {0}".format(e), file = sys.stderr)
                return 2

            if url:
                # Process a single URL
                process_article(url)
            else:
                # Process already parsed trees, starting on March 1, 2016
                if force:
                    # --force overrides --update
                    update = False
                from_date = None if update else datetime(year = 2016, month = 3, day = 1)
                process_articles(from_date = from_date,
                    limit = limit, force = force, update = update, processor = proc)
                # process_articles(limit = limit)

    except Usage as err:
        print(err.msg, file = sys.stderr)
        print("For help use --help", file = sys.stderr)
        return 2

    # Completed with no error
    return 0


def main():

    """ Main function to invoke for profiling """

    import cProfile as profile
    import pstats

    global _PROFILING

    _PROFILING = True

    filename = 'Processor.profile'

    profile.run('_main()', filename)

    stats = pstats.Stats(filename)

    # Clean up filenames for the report
    stats.strip_dirs()

    # Sort the statistics by the total time spent in the function itself
    stats.sort_stats('tottime')

    stats.print_stats(100) # Print 100 most significant lines


if __name__ == "__main__":
    #sys.exit(main()) # For profiling
    sys.exit(_main()) # For normal execution
