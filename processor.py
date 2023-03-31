#!/usr/bin/env python
"""

    Greynir: Natural language processing for Icelandic

    Processor module

    Copyright (C) 2023 Miðeind ehf.

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

from typing import TYPE_CHECKING, Any, Callable, Iterable, Optional, List, Union, cast
from types import ModuleType

import getopt
import importlib
import json
import sys
import time

if TYPE_CHECKING:
    from multiprocessing.dummy import Pool
else:
    from multiprocessing import Pool

from contextlib import closing
from datetime import datetime
from pathlib import Path

from settings import Settings, ConfigError
from db import GreynirDB, Session
from db.models import Article, Person, Column, DateTime
from tree import Tree, ProcEnv, TreeStateDict
from treeutil import PgsList
from utility import modules_in_dir


_profiling = False


class TokenContainer:
    """Class wrapper around tokens"""

    def __init__(self, tokens_json: str, url: str, authority: float) -> None:
        self.tokens = cast(PgsList, json.loads(tokens_json))
        self.url = url
        self.authority = authority

    def process(
        self, session: Session, processor: Union[ProcEnv, ModuleType], **kwargs: Any
    ) -> None:
        """Process tokens for an entire article.  Iterate over each paragraph,
        sentence and token, calling revelant functions in processor module."""

        assert processor is not None

        if not self.tokens:
            return

        if isinstance(processor, ModuleType):
            processor = cast(ProcEnv, vars(processor))

        # Get functions from processor module
        article_begin = processor.get("article_begin", None)
        article_end = processor.get("article_end", None)
        paragraph_begin = processor.get("paragraph_begin", None)
        paragraph_end = processor.get("paragraph_end", None)
        sentence_begin = processor.get("sentence_begin", None)
        sentence_end = processor.get("sentence_end", None)
        token_func = processor.get("token", None)

        # Make sure at least one of these functions is present
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
        state = TreeStateDict(
            session=session,
            url=self.url,
            authority=self.authority,
            processor=processor,
        )

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


_PROCESSOR_TYPE_TREE = "tree"
_PROCESSOR_TYPE_TOKEN = "token"
_PROCESSOR_TYPES = frozenset((_PROCESSOR_TYPE_TREE, _PROCESSOR_TYPE_TOKEN))


class Processor:
    """The worker class that processes parsed articles"""

    _db: Optional[GreynirDB] = None

    @classmethod
    def _init_class(cls) -> None:
        """Initialize class attributes"""
        if cls._db is None:
            cls._db = GreynirDB()

    @classmethod
    def cleanup(cls) -> None:
        """Perform any cleanup"""
        cls._db = None

    def __init__(
        self,
        processor_directory: str,
        single_processor: Optional[str] = None,
        num_workers: Optional[int] = None,
    ) -> None:

        Processor._init_class()
        self.num_workers = num_workers

        self.processors: List[str] = []
        self.pmodules: Optional[List[ProcEnv]] = None

        # Find .py files in the processor directory
        modnames = modules_in_dir(Path(processor_directory))

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
                    # (PyPy 3.6+ does this without problem, however.)
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
        """Single article processor that will be called by a process within a
        multiprocessing pool"""

        assert self._db is not None

        print("Processing article {0}".format(url))
        sys.stdout.flush()

        # If first article within a new process, import the processor modules
        if self.pmodules is None:
            self.pmodules = [
                vars(importlib.import_module(modname)) for modname in self.processors
            ]

        # Load the article
        with closing(self._db.session) as session:

            try:
                article = session.query(Article).filter_by(url=url).one_or_none()

                if article is None:
                    print("Article not found in scraper database")
                else:
                    if article.tree and article.tokens:
                        # Create tree object from article
                        tree = Tree(url, float(article.authority))
                        tree.load(article.tree)

                        # Create token container object from article
                        token_container = TokenContainer(
                            article.tokens, url, article.authority
                        )

                        # Run all processors in turn
                        for p in self.pmodules:
                            ptype: str = p.get("PROCESSOR_TYPE", "")
                            assert ptype in _PROCESSOR_TYPES, "Unknown processor type"
                            if ptype == _PROCESSOR_TYPE_TREE:
                                tree.process(session, p)
                            elif ptype == _PROCESSOR_TYPE_TOKEN:
                                token_container.process(session, p)

                    # Mark the article as being processed
                    article.processed = datetime.utcnow()

                # So far, so good: commit to the database
                session.commit()

            except Exception as e:
                # If an exception occurred, roll back the transaction
                session.rollback()
                print(
                    f"Exception in article {url}, transaction rolled back\nException: {e}"
                )
                raise

        sys.stdout.flush()

    def go(
        self,
        from_date: Optional[datetime] = None,
        limit: int = 0,
        force: bool = False,
        update: bool = False,
        title: Optional[str] = None,
    ) -> None:
        """Process already parsed articles from the database"""

        # noinspection PyComparisonWithNone,PyShadowingNames
        def iter_parsed_articles() -> Iterable[str]:

            assert self._db is not None

            with closing(self._db.session) as session:
                """Go through parsed articles and process them"""
                field: Callable[[Any], str]
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
                                cast(Column[DateTime], Article.processed)
                                < cast(Column[DateTime], Article.parsed)
                            ).order_by(Article.processed)
                        else:
                            q = q.filter(Article.processed == None)
                    if from_date is not None:
                        # Only go through articles parsed since the given date
                        q = q.filter(
                            cast(Column[DateTime], Article.parsed) >= from_date
                        ).order_by(Article.parsed)
                if limit > 0:
                    q = q.limit(limit)
                for a in q.yield_per(200):
                    yield field(a)

        if _profiling:
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
    from_date: Optional[datetime] = None,
    limit: int = 0,
    force: bool = False,
    update: bool = False,
    title: Optional[str] = None,
    processor: Optional[str] = None,
    num_workers: Optional[int] = None,
) -> None:
    """Process multiple articles according to the given parameters"""
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

    proc = None
    try:
        # Run all processors in the processors directory, or the single processor given
        proc = Processor(
            processor_directory="processors",
            single_processor=processor,
            num_workers=num_workers,
        )
        proc.go(from_date, limit=limit, force=force, update=update, title=title)
    finally:
        if proc is not None:
            del proc
        Processor.cleanup()

    t1 = time.time()

    print("\n------ Processing completed -------")
    print("Total time: {0:.2f} seconds".format(t1 - t0))
    ts = "{0}".format(datetime.utcnow())[0:19]
    print("Time: {0}\n".format(ts))


def process_article(url: str, processor: Optional[str] = None) -> None:
    """Process a single article, eventually with a single processor"""
    proc = None
    try:
        proc = Processor(processor_directory="processors", single_processor=processor)
        proc.go_single(url)
    finally:
        if proc is not None:
            del proc
        Processor.cleanup()


class Usage(Exception):
    def __init__(self, msg: str) -> None:
        self.msg = msg


def init_db() -> None:
    """Initialize the database, to the extent required"""
    db = GreynirDB()
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


def _main(argv: Optional[List[str]] = None) -> int:
    """Guido van Rossum's pattern for a Python main function"""
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
            # Initialize the database
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
    """Main function to invoke for profiling"""
    import cProfile as profile
    import pstats

    global _profiling

    _profiling = True
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
