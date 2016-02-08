#!/usr/bin/env python
"""
    Reynir: Natural language processing for Icelandic

    Processor module

    Copyright (c) 2015 Vilhjalmur Thorsteinsson
    All rights reserved
    See the accompanying README.md file for further licensing and copyright information.

    This module implements a processing module for parsed articles.

"""


import re
import sys
import getopt
import time
import importlib

from multiprocessing.dummy import Pool
#from multiprocessing import Pool

from contextlib import closing
from datetime import datetime

from settings import Settings, ConfigError

from scraperdb import Scraper_DB, Article

class Node:

    def __init__(self, t):
        self.t = t
        self.child = None
        self.next = None

    def set_next(self, n):
        assert n is not self
        assert n is not self.child
        self.next = n

    def set_child(self, n):
        assert n is not self
        assert n is not self.next
        self.child = n

    def string_rep(self, indent):
        return indent + str(self.t) + \
            (" (\n" + self.child.string_rep(indent + "  ") + "\n" + indent + ")" if self.child else "") + \
            (",\n" + self.next.string_rep(indent) if self.next else "")

    def __str__(self):
        return self.string_rep("")

    def __repr__(self):
        return str(self)

class Tree:

    """ A tree corresponding to a single parsed article """

    def __init__(self):
        self.s = { } # Sentence dictionary
        self.stack = None
        self.n = None # Index of current sentence

    def push(self, n, t):
        """ Add a node into the tree at the right level """
        node = Node(t)
        if n == len(self.stack):
            # First child of parent
            if n:
                assert self.stack[n-1].child is None
                self.stack[n-1].set_child(node)
            self.stack.append(node)
            assert n + 1 == len(self.stack)
        else:
            assert n < len(self.stack)
            # Next child of parent
            p = self.stack[n]
            self.stack[n] = node
            assert p.next is None
            p.set_next(node)
            if n + 1 < len(self.stack):
                newstack = [p for p in self.stack[0:n + 1]]
                self.stack = newstack
            assert n + 1 == len(self.stack)
            assert self.stack[n].next is None
            assert self.stack[n].child is None

    def handle_R(self, n):
        """ Reynir version info """
        print("R: n is {0}".format(n))

    def handle_S(self, n):
        """ Start of sentence """
        print("S: n is {0}".format(n))
        self.n = n
        self.s[n] = self.stack = []

    def handle_Q(self, n):
        """ End of sentence """
        print("Q: n is {0}".format(n))
        print("\nTree: {0}".format(self.s[self.n]))

    def handle_T(self, n, terminal, token):
        """ Terminal """
        print("T: n is {0}, terminal {1}, token {2}".format(n, terminal, token))
        self.push(n, (terminal, token))

    def handle_N(self, n, nonterminal):
        """ Nonterminal """
        print("N: n is {0}, nonterminal {1}".format(n, nonterminal))
        self.push(n, (nonterminal))

    def load(self, txt):
        """ Loads a tree from the text format stored by the scraper """

        for line in txt.split("\n"):
            if not line:
                continue
            a = line.split(' ', maxsplit = 1)
            if not a:
                continue
            code = a[0]
            n = int(code[1:])
            f = getattr(self, "handle_" + code[0], None)
            if f:
                # Split the line up into identifiers that can be of three forms:
                # 1) straight Python identifiers (alphabetic+digits+underscore)
                # 2) 'literal'_some_variants where the variants are Python identifiers
                # 3) "literal"
                m = re.findall(r"(?:\w+[\?\+\*]?)|(?:'[^']*'\w*[\?\+\*]?)|(?:\"[^\"]*\")", a[1]) if len(a) > 1 else None
                if m:
                    f(n, *m)
                else:
                    f(n)
            else:
                print("*** No handler for {0}".format(line))

    def process(self, session):
        """ Process a tree """
        pass


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
        pass # Not presently needed

    def __init__(self):

        Processor._init_class()

    def _process_article(self, url):
        """ Single article processor that will be called by a process within a
            multiprocessing pool """

        print("Processing article {0}".format(url))
        sys.stdout.flush()

        t0 = time.time()

        # Load the article
        with closing(self._db.session) as session:

            article = session.query(Article).filter_by(url = url).one()

            if article.tree:
                tree = Tree()
                tree.load(article.tree)
                tree.process(session)

            session.commit()

        t1 = time.time()

        print("Processing completed in {0:.2f} seconds".format(t1 - t0))
        sys.stdout.flush()


    def go(self, limit = 0):
        """ Process already parsed articles from the database """

        db = Processor._db

        with closing(db.session) as session:

            def iter_parsed_articles(limit):
                """ Go through parsed articles and process them """
                q = session.query(Article.url) \
                    .filter(Article.parsed != None).filter(Article.tree != None)
                if limit > 0:
                    q = q[0:limit]
                for a in q:
                    yield a.url

            # Use a multiprocessing pool to process the articles

            pool = Pool(1) # Defaults to using as many processes as there are CPUs
            pool.map(self._process_article, iter_parsed_articles(limit))
            pool.close()
            pool.join()


def process_articles(limit = 0):

    print("\n\n------ Reynir starting processing -------")
    ts = "{0}".format(datetime.utcnow())[0:19]
    print("Time: {0}\n".format(ts))

    try:
        try:
            proc = Processor()
            proc.go(limit = limit)
        #except Exception as e:
        #    print("Processor terminated with exception {0}".format(e))
        #    sys.stdout.flush()
        finally:
            pass # proc.stats()
    finally:
        proc = None
        Processor.cleanup()

    print("\n------ Processing completed -------\n")


class Usage(Exception):

    def __init__(self, msg):
        self.msg = msg


def main(argv = None):
    """ Guido van Rossum's pattern for a Python main function """

    if argv is None:
        argv = sys.argv
    try:
        try:
            opts, args = getopt.getopt(argv[1:], "hl:", ["help", "limit="])
        except getopt.error as msg:
             raise Usage(msg)
        limit = 10 # !!! DEBUG default limit on number of articles to parse, unless otherwise specified
        # Process options
        for o, a in opts:
            if o in ("-h", "--help"):
                print(__doc__)
                sys.exit(0)
            elif o in ("-l", "--limit"):
                # Maximum number of articles to parse
                try:
                    limit = int(a)
                except Exception as e:
                    pass
        # Process arguments
        for arg in args:
            pass

        # Read the configuration settings file

        try:
            Settings.read("Reynir.conf")
        except ConfigError as e:
            print("Configuration error: {0}".format(e), file = sys.stderr)
            return 2

        # Process already parsed trees
        process_articles(limit = limit)


    except Usage as err:
        print(err.msg, file = sys.stderr)
        print("For help use --help", file = sys.stderr)
        return 2

    # Completed with no error
    return 0


if __name__ == "__main__":
    sys.exit(main())
