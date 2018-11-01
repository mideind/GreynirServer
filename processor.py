#!/usr/bin/env python
"""

    Reynir: Natural language processing for Icelandic

    Processor module

    Copyright (C) 2017 Miðeind ehf.

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


    This module controls the processing of parsed articles.

    Processing is extensible and modular. All Python modules found in the processors/
    directory (except those whose names start with an underscore) are imported and their
    processing functions invoked in turn on the sentence trees of each parsed article.

    A multiprocessing pool is employed to process articles in parallel on all available
    CPUs.

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
from scraperdb import Scraper_DB, Article, Person
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
        self.pmodules = None
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
                # Try import before we start
                m = importlib.import_module(modname)
                print("Imported processor module {0}".format(modname))
                # Successful
                # Note: we can't append the module object m directly to the
                # processors list, as it will be shared between processes and
                # CPython 3 can't pickle module references for IPC transfer.
                # (PyPy 3.5 does this without problem, however.)
                # We therefore store just the module names and postpone the
                # actual import until we go_single() on the first article within
                # each child process.
                self.processors.append(modname)
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

        # If first article within a new process, import the processor modules
        if self.pmodules is None:
            self.pmodules = [ importlib.import_module(modname) for modname in self.processors ]

        # Load the article
        with closing(self._db.session) as session:

            try:

                article = session.query(Article).filter_by(url = url).one_or_none()

                if article is None:
                    print("Article not found in scraper database")
                else:
                    if article.tree:
                        tree = Tree(url, article.authority)
                        # print("Tree:\n{0}\n".format(article.tree))
                        tree.load(article.tree)

                        # Run all processors in turn
                        for p in self.pmodules:
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

    def go(self, from_date = None, limit = 0, force = False, update = False, title = None):
        """ Process already parsed articles from the database """

        # noinspection PyComparisonWithNone,PyShadowingNames
        def iter_parsed_articles():

            with closing(self._db.session) as session:
                """ Go through parsed articles and process them """
                if title is not None:
                    # Use a title query on Person to find the URLs to process
                    qtitle = title.lower()
                    if '%' not in qtitle:
                        # Match start of title by default
                        qtitle += '%'
                    q = session.query(Person.article_url).filter(Person.title_lc.like(qtitle))
                    field = lambda x: x.article_url
                else:
                    q = session.query(Article.url).filter(Article.tree != None)
                    field = lambda x: x.url
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
                    q = q.limit(limit)
                for a in q.yield_per(200):
                    yield field(a)

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


def process_articles(from_date = None, limit = 0, force = False,
    update = False, title = None, processor = None):

    print("------ Reynir starting processing -------")
    if from_date:
        print("From date: {0}".format(from_date))
    if limit:
        print("Limit: {0} articles".format(limit))
    if title is not None:
        print("Title LIKE: '{0}'".format(title))
    elif force:
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
        proc.go(from_date, limit = limit, force = force, update = update, title = title)
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
        -l N, --limit=N: Limit processing session to N articles
        -u U, --url=U: Specify a single URL to process
        -p P, --processor=P: Specify a single processor to invoke
        -t T, --title=T: Specify a title pattern in the persons table
                            to select articles to reprocess
        --update: Process files that have been reparsed but not reprocessed

"""

def _main(argv = None):
    """ Guido van Rossum's pattern for a Python main function """

    if argv is None:
        argv = sys.argv
    try:
        try:
            opts, args = getopt.getopt(argv[1:], "hifl:u:p:t:",
                ["help", "init", "force", "update", "limit=", "url=", "processor=", "title="])
        except getopt.error as msg:
             raise Usage(msg)
        limit = 10 # !!! DEBUG default limit on number of articles to parse, unless otherwise specified
        init = False
        url = None
        force = False
        update = False
        title = None # Title pattern
        proc = None # Single processor to invoke
        # Process options
        for o, a in opts:
            if o in ("-h", "--help"):
                print(__doc__)
                return 0
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
            elif o in ("-t", "--title"):
                # Title pattern to match
                title = a
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
                Settings.read("config/Reynir.conf")
                # Don't run the processor in debug mode
                Settings.DEBUG = False
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
                if title:
                    # --title overrides both --force and --update
                    force = False
                    update = False
                from_date = None if update else datetime(year = 2016, month = 3, day = 1)
                process_articles(from_date = from_date,
                    limit = limit, force = force, update = update, title = title, processor = proc)
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
