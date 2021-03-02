#!/usr/bin/env python
"""

    Greynir: Natural language processing for Icelandic

    Processor module

    Copyright (C) 2021 Miðeind ehf.

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

from typing import Optional, List, cast
from types import ModuleType

import getopt
import importlib
import json
import sys
import time
import os

# from multiprocessing.dummy import Pool
from multiprocessing import Pool
from contextlib import closing
from datetime import datetime

from settings import Settings, ConfigError
from db import Scraper_DB
from db.models import Article, Person, Column
from tree import Tree


_PROFILING = False


def modules_in_dir(directory: str) -> List[str]:
    """ Find all python modules in a given directory """
    files = os.listdir(directory)
    modnames: List[str] = list()
    for fname in files:
        if not fname.endswith(".py"):
            continue
        if fname.startswith("_"):  # Skip any files starting with _
            continue
        mod = directory.replace("/", ".") + "." + fname[:-3]  # Cut off .py
        modnames.append(mod)
    return modnames


class TokenContainer:

    """ Class wrapper around tokens """

    def __init__(self, tokens_json, url, authority) -> None:
        self.tokens = json.loads(tokens_json)
        self.url = url
        self.authority = authority

    def process(self, session, processor, **kwargs) -> None:
        """ Process tokens for an entire article.  Iterate over each paragraph,
            sentence and token, calling revelant functions in processor module. """

        assert processor is not None

        if not self.tokens:
            return

        # Get functions from processor module
        article_begin = getattr(processor, "article_begin", None)
        article_end = getattr(processor, "article_end", None)
        paragraph_begin = getattr(processor, "paragraph_begin", None)
        paragraph_end = getattr(processor, "paragraph_end", None)
        sentence_begin = getattr(processor, "sentence_begin", None)
        sentence_end = getattr(processor, "sentence_end", None)
        token_func = getattr(processor, "token", None)

        # Make sure at least one of these functions is is present
        if not any(
            (
                article_begin,
                article_end,
                paragraph_begin,
                paragraph_end,
                sentence_begin,
                sentence_end,
                token_func,
            )
        ):
            print(
                "No functions implemented in processor module {0}".format(
                    str(processor)
                )
            )
            return

        # Initialize state that we keep throughout processing
        state = {
            "session": session,
            "url": self.url,
            "authority": self.authority,
            "processor": processor,
        }

        if article_begin:
            article_begin(state)

        # Paragraphs
        for p in self.tokens:
            if paragraph_begin:
                paragraph_begin(state, p)

            # Sentences
            for s in p:
                if sentence_begin:
                    sentence_begin(state, p, s)

                # Tokens
                if token_func:
                    for idx, t in enumerate(s):
                        token_func(state, p, s, t, idx)

                if sentence_end:
                    sentence_end(state, p, s)

            if paragraph_end:
                paragraph_end(state, p)

        if article_end:
            article_end(state)


class Processor:

    """ The worker class that processes parsed articles """

    _db = None  # type: Optional[Scraper_DB]

    @classmethod
    def _init_class(cls) -> None:
        """ Initialize class attributes """
        if cls._db is None:
            cls._db = Scraper_DB()

    @classmethod
    def cleanup(cls) -> None:
        """ Perform any cleanup """
        cls._db = None

    def __init__(
        self, processor_directory, single_processor=None, num_workers=None
    ) -> None:

        Processor._init_class()
        self.num_workers = num_workers

        self.processors = []
        self.pmodules = None  # type: Optional[List[ModuleType]]

        # Find .py files in the processor directory
        modnames = modules_in_dir(processor_directory)

        if single_processor:
            # Remove all except the single processor specified
            modnames = [m for m in modnames if m.endswith("." + single_processor)]

        # Dynamically load all processor modules
        for modname in modnames:
            try:
                # Try import before we start
                m = importlib.import_module(modname)
                ptype = getattr(m, "PROCESSOR_TYPE")
                if ptype is not None:
                    print("Imported processor module {0} ({1})".format(modname, ptype))
                    # Successful
                    # Note: we can't append the module object m directly to the
                    # processors list, as it will be shared between processes and
                    # CPython 3 can't pickle module references for IPC transfer.
                    # (PyPy 3.6 does this without problem, however.)
                    # We therefore store just the module names and postpone the
                    # actual import until we go_single() on the first article within
                    # each child process.
                    self.processors.append(modname)
            except Exception as e:
                print("Error importing processor module {0}: {1}".format(modname, e))

        if not self.processors:
            if single_processor:
                print(
                    "Processor '{0}' not found in directory {1}".format(
                        single_processor, processor_directory
                    )
                )
            else:
                print(
                    "No processors found in directory {0}".format(processor_directory)
                )

    def go_single(self, url: str) -> None:
        """ Single article processor that will be called by a process within a
            multiprocessing pool """

        assert self._db is not None

        print("Processing article {0}".format(url))
        sys.stdout.flush()

        # If first article within a new process, import the processor modules
        if self.pmodules is None:
            self.pmodules = [
                importlib.import_module(modname) for modname in self.processors
            ]

        # Load the article
        with closing(self._db.session) as session:

            try:
                article = session.query(Article).filter_by(url=url).one_or_none()

                if article is None:
                    print("Article not found in scraper database")
                else:
                    if article.tree and article.tokens:
                        tree = Tree(url, float(article.authority))
                        tree.load(article.tree)

                        token_container = TokenContainer(
                            article.tokens, url, article.authority
                        )

                        # Run all processors in turn
                        for p in self.pmodules:
                            ptype: str = getattr(p, "PROCESSOR_TYPE")
                            if ptype == "tree":
                                tree.process(session, p)
                            elif ptype == "token":
                                token_container.process(session, p)
                            else:
                                assert False, (
                                    "Unknown processor type '{0}'; should be 'tree' or 'token'"
                                    .format(ptype)
                                )

                    # Mark the article as being processed
                    article.processed = datetime.utcnow()  # type: ignore

                # So far, so good: commit to the database
                session.commit()

            except Exception as e:
                # If an exception occurred, roll back the transaction
                session.rollback()
                print(
                    "Exception in article {0}, transaction rolled back\nException: {1}"
                    .format(url, e)
                )
                raise

        sys.stdout.flush()

    def go(
        self, from_date=None, limit=0, force=False, update=False, title=None
    ) -> None:
        """ Process already parsed articles from the database """

        # noinspection PyComparisonWithNone,PyShadowingNames
        def iter_parsed_articles():

            assert self._db is not None

            with closing(self._db.session) as session:
                """ Go through parsed articles and process them """
                if title is not None:
                    # Use a title query on Person to find the URLs to process
                    qtitle = title.lower()
                    if "%" not in qtitle:
                        # Match start of title by default
                        qtitle += "%"
                    q = session.query(Person.article_url).filter(
                        Person.title_lc.like(qtitle)
                    )
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
                            q = q.filter(
                                cast(Column, Article.processed) < cast(Column, Article.parsed)).order_by(
                                Article.processed
                            )
                        else:
                            q = q.filter(Article.processed == None)
                    if from_date is not None:
                        # Only go through articles parsed since the given date
                        q = q.filter(Article.parsed >= from_date).order_by(
                            Article.parsed
                        )
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
            # Defaults to using as many processes as there are CPUs
            with Pool(self.num_workers) as pool:
                for _ in pool.imap_unordered(self.go_single, iter_parsed_articles()):
                    pass
                pool.close()
                pool.join()


def process_articles(
    from_date=None,
    limit=0,
    force=False,
    update=False,
    title=None,
    processor=None,
    num_workers=None,
) -> None:
    """ Process multiple articles according to the given parameters """
    print("------ Greynir starting processing -------")
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
    if num_workers:
        print("Number of workers: {0}".format(num_workers))
    ts = "{0}".format(datetime.utcnow())[0:19]
    print("Time: {0}\n".format(ts))

    t0 = time.time()

    try:
        # Run all processors in the processors directory, or the single processor given
        proc = Processor(
            processor_directory="processors",
            single_processor=processor,
            num_workers=num_workers,
        )
        proc.go(from_date, limit=limit, force=force, update=update, title=title)
    finally:
        del proc
        Processor.cleanup()

    t1 = time.time()

    print("\n------ Processing completed -------")
    print("Total time: {0:.2f} seconds".format(t1 - t0))
    ts = "{0}".format(datetime.utcnow())[0:19]
    print("Time: {0}\n".format(ts))


def process_article(url: str, processor=None) -> None:
    """ Process a single article, eventually with a single processor """
    try:
        proc = Processor(processor_directory="processors", single_processor=processor)
        proc.go_single(url)
    finally:
        del proc
        Processor.cleanup()


class Usage(Exception):
    def __init__(self, msg: str) -> None:
        self.msg = msg


def init_db() -> None:
    """ Initialize the database, to the extent required """
    db = Scraper_DB()
    try:
        db.create_tables()
    except Exception as e:
        print("{0}".format(e))


__doc__ = """

    Greynir - Natural language processing for Icelandic

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


def _main(argv=None) -> int:
    """ Guido van Rossum's pattern for a Python main function """
    if argv is None:
        argv = sys.argv
    try:
        try:
            opts, _ = getopt.getopt(
                argv[1:],
                "hifl:u:p:t:w:",
                [
                    "help",
                    "init",
                    "force",
                    "update",
                    "limit=",
                    "url=",
                    "processor=",
                    "title=",
                    "workers=",
                ],
            )
        except getopt.error as msg:
            raise Usage(str(msg))
        limit = 10  # Default number of articles to parse, unless otherwise specified
        init = False
        url = None
        force = False
        update = False
        title = None  # Title pattern
        proc = None  # Single processor to invoke
        num_workers = None  # Number of workers to run simultaneously
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
                except ValueError:
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
            elif o in ("-w", "--workers"):
                # Limit the number of workers
                num_workers = int(a) if int(a) else None

        if init:
            # Initialize the scraper database
            init_db()
        else:

            # Read the configuration settings file

            try:
                Settings.read("config/Greynir.conf")
                # Don't run the processor in debug mode
                Settings.DEBUG = False
            except ConfigError as e:
                print("Configuration error: {0}".format(e), file=sys.stderr)
                return 2

            if url:
                # Process a single URL
                process_article(url, processor=proc)
            else:
                # Process already parsed trees, starting on March 1, 2016
                if force:
                    # --force overrides --update
                    update = False
                if title:
                    # --title overrides both --force and --update
                    force = False
                    update = False
                from_date = None if update else datetime(year=2016, month=3, day=1)
                process_articles(
                    from_date=from_date,
                    limit=limit,
                    force=force,
                    update=update,
                    title=title,
                    processor=proc,
                    num_workers=num_workers,
                )
                # process_articles(limit = limit)

    except Usage as err:
        print(err.msg, file=sys.stderr)
        print("For help use --help", file=sys.stderr)
        return 2

    # Completed with no error
    return 0


def main() -> None:
    """ Main function to invoke for profiling """
    import cProfile as profile
    import pstats

    global _PROFILING

    _PROFILING = True
    filename = "Processor.profile"
    profile.run("_main()", filename)
    stats = pstats.Stats(filename)
    # Clean up filenames for the report
    stats.strip_dirs()
    # Sort the statistics by the total time spent in the function itself
    stats.sort_stats("tottime")
    stats.print_stats(100)  # Print 100 most significant lines


if __name__ == "__main__":
    # sys.exit(main()) # For profiling
    sys.exit(_main())  # For normal execution
