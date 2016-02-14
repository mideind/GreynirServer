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

#from multiprocessing.dummy import Pool
from multiprocessing import Pool
from contextlib import closing
from datetime import datetime
from collections import OrderedDict

from settings import Settings, ConfigError
from scraperdb import Scraper_DB, Article
from bindb import BIN_Db, BIN_Meaning

_PROFILING = False

BIN_ORDFL = {
    "no" : { "kk", "kvk", "hk" },
    "so" : { "so" },
    "lo" : { "lo" },
    "fs" : { "fs" },
    "ao" : { "ao" },
    "eo" : { "ao" },
    "eo" : { "ao" },
    "töl" : { "töl", "to" },
    "to" : { "töl", "to" },
    "fn" : { "fn" },
    "pfn" : { "pfn" }
}


class Result:

    """ Container for results that are sent from child nodes to parent nodes.
        This class is instrumented so that it is equivalent to use attribute
        or indexing notation, i.e. r.efliður is the same as r["efliður"].

        (This also sidesteps a bug in the PyPy 2.6.0 which doesn't fully
        support custom handling of attribute identifiers with non-ASCII
        characters in them.)

        Additionally, the class implements lazy evaluation of the r._root
        attribute so that it is only calculated when and if required, and
        then cached. This is an optimization to save database reads.

    """

    def __init__(self, node, state, params):
        self.dict = dict() # Our own custom dict for instance attributes
        self._node = node
        self._state = state
        self._params = params

    def __setattr__(self, key, val):
        if key == "dict" or key == "__dict__":
            super().__setattr__(key, val)
        else:
            self.dict[key] = val

    def __getattr__(self, key):
        if key == "dict" or key == "__dict__":
            return super().__getattr__(key)
        d = self.dict
        if key == "_root" and not "_root" in d:
            # Lazy evaluation of the _root attribute
            # (Note that it can be overridden by setting it directly)
            d[key] = self._node.root(self._state, self._params)
            # At this point we can safely release the params
            del d["_params"]
        if key in d:
            return d[key]
        # Not found in our custom dict:
        # hand off to Python's default attribute resolution mechanism
        return super().__getattr__(key)

    def __contains__(self, key):
        return key in self.dict

    def __getitem__(self, key):
        return self.dict[key]

    def __setitem__(self, key, val):
        self.dict[key] = val

    def __delitem__(self, key):
        del self.dict[key]

    def get(self, key, default = None):
        return self.dict.get(key, default)

    def attribs(self):
        """ Enumerate all attributes, and values, of this result object """
        for key, val in self.dict.items():
            yield (key, val)

    def user_attribs(self):
        """ Enumerate all user-defined attributes and values of this result object """
        for key, val in self.dict.items():
            if isinstance(key, str) and not key.startswith("_") and not callable(val):
                yield (key, val)

    def set(self, key, val):
        """ Set the key to the value, unless it has already been assigned """
        d = self.dict
        if key not in d:
            d[key] = val

    def copy_from(self, p):
        """ Copy all user attributes from p into this result """
        if p is self or p is None:
            return
        d = self.dict
        for key, val in p.user_attribs():
            # Pass all named parameters whose names do not start with an underscore
            # up to the parent, by default
            # We do not overwrite already assigned named parameters
            # This means that we have left-to-right priority, i.e.
            # the leftmost entity wins in case of conflict
            if key not in d:
                d[key] = val

    def del_attribs(self, alist):
        """ Delete the attribs in alist from the result object """
        if isinstance(alist, str):
            alist = (alist, )
        d = self.dict
        for a in alist:
            if a in d:
                del d[a]


class Node:

    """ Base class for terminal and nonterminal nodes reconstructed from
        trees in text format loaded from the scraper database """

    def __init__(self):
        self.child = None
        self.nxt = None

    def set_next(self, n):
        self.nxt = n

    def set_child(self, n):
        self.child = n

    def children(self):
        """ Yield all children of this node """
        c = self.child
        while c:
            yield c
            c = c.nxt

    def descendants(self):
        """ Do a depth-first traversal of all children of this node """
        c = self.child
        while c:
            for cc in c.children():
                yield cc
            yield c
            c = c.nxt

    def string_self(self):
        """ String representation of the name of this node """
        assert False # Should be overridden
        return ""

    def string_rep(self, indent):
        """ Indented representation of this node """
        s = indent + self.string_self()
        if self.child is not None:
            s += " (\n" + self.child.string_rep(indent + "  ") + "\n" + indent + ")"
        if self.nxt is not None:
            s += ",\n" + self.nxt.string_rep(indent)
        return s

    def __str__(self):
        return self.string_rep("")

    def __repr__(self):
        return str(self)


class TerminalNode(Node):

    """ A Node corresponding to a terminal """

    def __init__(self, terminal, token, at_start):
        super().__init__()
        self.terminal = terminal
        self.token = token
        self.text = token[1:-1] # Cut off quotes
        self.at_start = at_start
        elems = terminal.split("_")
        self.cat = elems[0]
        self.variants = set(elems[1:])
        # Cache the root form of this word so that it is only looked up
        # once, even if multiple processors scan this tree
        self.root_cache = None

    def _root(self, bin_db):
        """ Look up the root of the word associated with this terminal """
        # Lookup the token in the BIN database
        w, m = bin_db.lookup_word(self.text, self.at_start)
        if m:
            bin_cat = BIN_ORDFL[self.cat] if self.cat in BIN_ORDFL else set()
            m = [x for x in m if x.ordfl in bin_cat]
        # !!! Add more sophisticated pruning of meanings here
        if m:
            w = m[0].stofn
        return w.replace("-", "")

    def root(self, state, params):
        """ Calculate the root (canonical) form of this node's text """
        if self.root_cache is None:
            bin_db = state["bin_db"]
            self.root_cache = self._root(bin_db)
        return self.root_cache

    def string_self(self):
        return self.terminal + " <" + self.token + ">"

    def process(self, state, params):
        """ Prepare a result object to be passed up to enclosing nonterminals """
        assert not params # A terminal node should not have parameters
        result = Result(self, state, None) # No params
        result._terminal = self.terminal
        result._text = self.text
        result._token = self.token
        return result


class PersonNode(TerminalNode):

    """ Specialized TerminalNode for person terminals """

    _CASES = { "nf", "þf", "þgf", "ef" }

    def _root(self, bin_db):
        """ Calculate the root (canonical) form of this person name """
        # Lookup the token in the BIN database
        gender = "kk" if "kk" in self.variants else "kvk"
        case = "nf"
        for c in PersonNode._CASES:
            if c in self.variants:
                case = c
                break
        case = case.upper()
        # Look up each part of the name
        at_start = self.at_start
        name = []
        for part in self.text.split(" "):
            w, m = bin_db.lookup_word(part, at_start)
            at_start = False
            if m:
                m = [ x for x in m if x.ordfl == gender and case in x.beyging and "ET" in x.beyging ]
            if m:
                w = m[0].stofn
            name.append(w.replace("-", ""))
        return " ".join(name)


class NonterminalNode(Node):

    """ A Node corresponding to a nonterminal """

    def __init__(self, nonterminal):
        super().__init__()
        self.nt = nonterminal
        # Calculate the base name of this nonterminal (without variants)
        self.nt_base = nonterminal.split("_", maxsplit = 1)[0]

    def string_self(self):
        return self.nt

    def root(self, state, params):
        """ The root form of a nonterminal is a sequence of the root forms of its children (parameters) """
        return " ".join(p._root for p in params)

    def process(self, state, params):
        """ Apply any requested processing to this node """
        result = Result(self, state, params)
        result._nonterminal = self.nt
        # Calculate the combined text rep of the children
        result._text = " ".join(p._text for p in params)
        for p in params:
            # Copy all user variables (attributes not starting with an underscore _)
            # coming from the children into the result
            result.copy_from(p)
        # Invoke a processor function for this nonterminal, if
        # present in the given processor module
        processor = state["processor"]
        func = getattr(processor, self.nt_base, None) if processor else None
        if func:
            func(self, params, result)
        return result


class Tree:

    """ A tree corresponding to a single parsed article """

    # A map of terminal types to node constructors
    _TC = {
        "person" : PersonNode
    }

    def __init__(self):
        self.s = OrderedDict() # Sentence dictionary
        self.stack = None
        self.n = None # Index of current sentence
        self.at_start = False # First token of sentence?

    def push(self, n, node):
        """ Add a node into the tree at the right level """
        if n == len(self.stack):
            # First child of parent
            if n:
                self.stack[n-1].set_child(node)
            self.stack.append(node)
        else:
            assert n < len(self.stack)
            # Next child of parent
            self.stack[n].set_next(node)
            self.stack[n] = node
            if n + 1 < len(self.stack):
                self.stack = self.stack[0:n + 1]

    def handle_R(self, n):
        """ Reynir version info """
        pass

    def handle_S(self, n):
        """ Start of sentence """
        self.n = n
        self.stack = []
        self.at_start = True

    def handle_Q(self, n):
        """ End of sentence """
        # Store the root of the sentence tree at the appropriate index
        # in the dictionary
        self.s[self.n] = self.stack[0]
        self.stack = None
        #print("Tree [{0}] is: {1}".format(self.n, self.s[self.n]))

    def handle_T(self, n, terminal, token):
        """ Terminal """
        # Select a terminal constructor based on the first part of the
        # terminal name
        cat = terminal.split("_", maxsplit = 1)[0]
        constructor = Tree._TC.get(cat, TerminalNode)
        self.push(n, constructor(terminal, token, self.at_start))
        self.at_start = False

    def handle_N(self, n, nonterminal):
        """ Nonterminal """
        self.push(n, NonterminalNode(nonterminal))

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

    def visit_children(self, state, node):
        """ Visit the children of node, obtain results from them and pass them to the node """
        return node.process(state, [self.visit_children(state, child) for child in node.children()])

    def process_sentence(self, state, index, tree):
        """ Process a sentence tree """
        assert tree.nxt is None
        result = self.visit_children(state, tree)
        # Sentence processing completed:
        # Invoke a function called 'sentence(result)',
        # if present in the processor
        processor = state["processor"]
        func = getattr(processor, "sentence", None) if processor else None
        if func:
            func(result)

    def process(self, session, processor):
        """ Process a tree for an entire article """
        # For each sentence in turn, do a depth-first traversal,
        # visiting each parent node after visiting its children
        # Initialize the running state that we keep between sentences

        with closing(BIN_Db.get_db()) as bin_db:

            state = { "session": session, "processor": processor, "bin_db": bin_db }
            for index, tree in self.s.items():
                self.process_sentence(state, index, tree)


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

    def __init__(self, module_name):

        Processor._init_class()

        # Dynamically load a processor module
        self.processor = importlib.import_module(module_name)
        if not self.processor:
            print("Unable to load processor module {0}".format(module_name))

    def _process_article(self, url):
        """ Single article processor that will be called by a process within a
            multiprocessing pool """

        print("Processing article {0}".format(url))
        sys.stdout.flush()

        # Load the article
        with closing(self._db.session) as session:

            article = session.query(Article).filter_by(url = url).one()

            if article.tree:
                tree = Tree()
                tree.load(article.tree)
                tree.process(session, self.processor)

            session.commit()

        t1 = time.time()
        sys.stdout.flush()


    def go(self, from_date = None, limit = 0):
        """ Process already parsed articles from the database """

        db = Processor._db

        with closing(db.session) as session:

            def iter_parsed_articles(limit):
                """ Go through parsed articles and process them """
                if from_date is None:
                    q = session.query(Article.url) \
                        .filter(Article.parsed != None).filter(Article.tree != None)
                else:
                    q = session.query(Article.url) \
                        .filter(Article.parsed >= from_date).filter(Article.tree != None)
                if limit > 0:
                    q = q[0:limit]
                for a in q:
                    yield a.url


            if _PROFILING:
                # If profiling, just do a simple map within a single thread and process
                for url in iter_parsed_articles(limit):
                    self._process_article(url)
            else:
                # Use a multiprocessing pool to process the articles
                pool = Pool() # Defaults to using as many processes as there are CPUs
                pool.map(self._process_article, iter_parsed_articles(limit))
                pool.close()
                pool.join()


def process_articles(from_date = None, limit = 0):

    print("------ Reynir starting processing -------")
    ts = "{0}".format(datetime.utcnow())[0:19]
    print("Time: {0}\n".format(ts))

    t0 = time.time()

    try:
        try:
            proc = Processor("processors.default")
            proc.go(from_date, limit = limit)
        #except Exception as e:
        #    print("Processor terminated with exception {0}".format(e))
        #    sys.stdout.flush()
        finally:
            pass # proc.stats()
    finally:
        proc = None
        Processor.cleanup()

    t1 = time.time()

    print("\n------ Processing completed -------")
    print("Total time: {0:.2f} seconds".format(t1 - t0))
    ts = "{0}".format(datetime.utcnow())[0:19]
    print("Time: {0}\n".format(ts))


class Usage(Exception):

    def __init__(self, msg):
        self.msg = msg


def _main(argv = None):
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

        # Process already parsed trees, starting on February 10, 2016
        process_articles(from_date = datetime(year = 2016, month = 1, day = 1), limit = limit)


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
