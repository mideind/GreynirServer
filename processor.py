#!/usr/bin/env python
"""
    Reynir: Natural language processing for Icelandic

    Processor module

    Copyright (c) 2015 Vilhjalmur Thorsteinsson
    All rights reserved
    See the accompanying README.md file for further licensing and copyright information.

    This module implements a processing module for parsed articles.

"""

import getopt
import importlib
import json
import sys
import time

import re
#from multiprocessing.dummy import Pool
from multiprocessing import Pool
from contextlib import closing
from datetime import datetime
from collections import OrderedDict

from settings import Settings, ConfigError
from scraperdb import Scraper_DB, Article
from bindb import BIN_Db

_PROFILING = False

BIN_ORDFL = {
    "no" : { "kk", "kvk", "hk" },
    "so" : { "so" },
    "lo" : { "lo" },
    "fs" : { "fs" },
    "ao" : { "ao" },
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
        and r._nominative attributes so that they are only calculated when and
        if required, and then cached. This is an optimization to save database
        reads.

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
        """ Fancy attribute getter with special cases for _root and _nominative """
        if key == "dict" or key == "__dict__":
            return super().__getattr__(key)
        d = self.dict
        if key == "_root" and not "_root" in d:
            # Lazy evaluation of the _root attribute
            # (Note that it can be overridden by setting it directly)
            d[key] = self._node.root(self._state, self._params)
            # At this point we can safely release the params
            del d["_params"]
        elif key == "_nominative" and not "_nominative" in d:
            # Lazy evaluation of the _root attribute
            # (Note that it can be overridden by setting it directly)
            d[key] = self._node.nominative(self._state, self._params)
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
            # Generally we have left-to-right priority, i.e.
            # the leftmost entity wins in case of conflict.
            # However, lists, sets and dictionaries with the same
            # member name are combined.
            if key not in d:
                d[key] = val
            else:
                # Combine lists and dictionaries
                left = d[key]
                if isinstance(left, list) and isinstance(val, list):
                    # Extend lists
                    left.extend(val)
                elif isinstance(left, set) and isinstance(val, set):
                    # Return union of sets
                    left |= val
                elif isinstance(left, dict) and isinstance(val, dict):
                    # Keep the left entries but add any new/additional val entries
                    d[key] = dict(val, **left)

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

    _CASES = { "nf", "þf", "þgf", "ef" }
    _GENDERS = { "kk", "kvk", "hk" }
    _NUMBER = { "et", "ft" }
    _PERSONS = { "p1", "p2", "p3" }

    def __init__(self, terminal, token, tokentype, aux, at_start):
        super().__init__()
        self.terminal = terminal
        self.token = token
        self.text = token[1:-1] # Cut off quotes
        self.at_start = at_start
        elems = terminal.split("_")
        self.cat = elems[0]
        self.variants = set(elems[1:])
        self.tokentype = tokentype
        self.aux = aux # Auxiliary information, originally from token.t2
        # Cache the root form of this word so that it is only looked up
        # once, even if multiple processors scan this tree
        self.root_cache = None
        self.nominative_cache = None

        # BIN category set
        self.bin_cat = BIN_ORDFL[self.cat] if self.cat in BIN_ORDFL else set()

        # Gender of terminal
        self.gender = None
        gender = self.variants & TerminalNode._GENDERS
        assert 0 <= len(gender) <= 1
        if gender:
            self.gender = next(iter(gender))

        # Case of terminal
        self.case = None
        if self.cat != "so":
            # We do not check cases for verbs, except so_lhþt ones
            case = self.variants & TerminalNode._CASES
            if len(case) > 1:
                print("Many cases detected for terminal {0}, variants {1}".format(terminal, self.variants))
            assert 0 <= len(case) <= 1
            if case:
                self.case = next(iter(case))

        # Person of terminal
        self.person = None
        person = self.variants & TerminalNode._PERSONS
        assert 0 <= len(person) <= 1
        if person:
            self.person = next(iter(person))

        # Number of terminal
        self.number = None
        number = self.variants & TerminalNode._NUMBER
        assert 0 <= len(number) <= 1
        if number:
            self.number = next(iter(number))

    def _bin_filter(self, m, case_override = None):
        """ Return True if the BIN meaning in m matches the variants for this terminal """
        #print("_bin_filter checking meaning {0}".format(m))
        if m.ordfl not in self.bin_cat:
            return False
        if self.gender:
            # Check gender match
            if self.cat == "no":
                if m.ordfl != self.gender:
                    return False
            else:
                if self.gender.upper() not in m.beyging:
                    return False
        if self.case:
            # Check case match
            if case_override:
                # Case override: we don't want other cases beside the given one
                for c in TerminalNode._CASES:
                    if c != case_override:
                        if c.upper() in m.beyging:
                            return False
            elif self.case.upper() not in m.beyging:
                return False
        # Check person match
        if self.person:
            person = self.person.upper()
            person = person[1] + person[0] # Turn p3 into 3P
            if person not in m.beyging:
                return False
        # Check number match
        if self.number:
            if self.number.upper() not in m.beyging:
                return False
        # Check lhþt
        if "lhþt" in self.variants:
            if "LHÞT" not in m.beyging:
                return False
        #print("_bin_filter returns True")
        return True

    def _root(self, bin_db):
        """ Look up the root of the word associated with this terminal """
        # Lookup the token in the BIN database
        w, m = bin_db.lookup_word(self.text, self.at_start)
        if m:
            m = [ x for x in m if self._bin_filter(x) ]
        if m:
            w = m[0].stofn
        return w.replace("-", "")

    def _nominative(self, bin_db):
        """ Look up the nominative form of the word associated with this terminal """
        # Lookup the token in the BIN database
        if self.case == "nf":
            # Already a nominative word: return it as-is
            return self.text
        w, m = bin_db.lookup_word(self.text, self.at_start)
        if m:
            m = [ x for x in m if self._bin_filter(x) ]
        if m:
            # Look up the root of the word and find its forms
            stofn = m[0].stofn.replace("-", "")
            root, m = bin_db.lookup_form(stofn, self.at_start)
            # Select the most similar word form, but in nominative case
            m = [ x for x in m if self._bin_filter(x, case_override = "nf") ]
            if m:
                w = m[0].ordmynd
        return w.replace("-", "")

    def root(self, state, params):
        """ Calculate the root (canonical) form of this node's text """
        if self.root_cache is None:
            # Not already cached: look up in database
            bin_db = state["bin_db"]
            self.root_cache = self._root(bin_db)
        return self.root_cache

    def nominative(self, state, params):
        """ Calculate the nominative form of this node's text """
        if self.nominative_cache is None:
            # Not already cached: look up in database
            bin_db = state["bin_db"]
            self.nominative_cache = self._nominative(bin_db)
        return self.nominative_cache

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

    def __init__(self, terminal, token, tokentype, aux, at_start):
        super().__init__(terminal, token, tokentype, aux, at_start)
        # Load the full names from the auxiliary JSON information
        fullnames = json.loads(aux) if aux else None # List of tuples
        firstname = fullnames[0] if fullnames else None # Tuple: name, gender, case
        self.fullname = firstname[0] if firstname else ""

    def _root(self, bin_db):
        """ Calculate the root (canonical) form of this person name """
        # If we already have a full name coming from the tokenizer, use it
        if self.fullname:
            return self.fullname
        # Lookup the token in the BIN database
        case = self.case.upper()
        # Look up each part of the name
        at_start = self.at_start
        name = []
        for part in self.text.split(" "):
            w, m = bin_db.lookup_word(part, at_start)
            at_start = False
            if m:
                m = [ x for x in m if x.ordfl == self.gender and case in x.beyging and "ET" in x.beyging ]
            if m:
                w = m[0].stofn
            name.append(w.replace("-", ""))
        return " ".join(name)

    def _nominative(self, bin_db):
        """ The nominative is identical to the root """
        return self._root(bin_db)


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
        return " ".join(p._root for p in params if p._root)

    def nominative(self, state, params):
        """ The nominative form of a nonterminal is a sequence of the nominative forms of its children (parameters) """
        return " ".join(p._nominative for p in params if p._nominative)

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

    def __init__(self, url):
        self.s = OrderedDict() # Sentence dictionary
        self.stack = None
        self.n = None # Index of current sentence
        self.at_start = False # First token of sentence?
        self.url = url

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

    def handle_T(self, n, s):
        """ Terminal """
        # The string s contains:
        # terminal 'token' [TOKENTYPE] [auxiliary-json]
        a = s.split(' ', maxsplit = 1)
        terminal = a[0]
        s = re.match(r'\'[^\']*\'', a[1])
        token = s.group() if s else ""
        s = a[1][s.end() + 1:] if s else ""
        a = s.split(' ', maxsplit = 1) if s else ["WORD"] # Default token type
        tokentype = a[0]
        aux = a[1] if len(a) > 1 else "" # Auxiliary info (originally token.t2)
        # Select a terminal constructor based on the first part of the
        # terminal name
        cat = terminal.split("_", maxsplit = 1)[0]
        constructor = Tree._TC.get(cat, TerminalNode)
        self.push(n, constructor(terminal, token, tokentype, aux, self.at_start))
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
                # 1) straight Python identifiers (alphabetic+digits+underscore),
                # 2) 'literal'_some_variants where the variants are Python identifiers,
                # 3) "literal"
                # All of the above can be optionally followed by ?, + or *
                if len(a) >= 2:
                    f(n, a[1])
                else:
                    f(n)
            else:
                print("*** No handler for {0}".format(line))

    def visit_children(self, state, node):
        """ Visit the children of node, obtain results from them and pass them to the node """
        return node.process(state, [ self.visit_children(state, child) for child in node.children() ])

    def process_sentence(self, state, index, tree):
        """ Process a sentence tree """
        assert tree.nxt is None
        result = self.visit_children(state, tree)
        # Sentence processing completed:
        # Invoke a function called 'sentence(state, result)',
        # if present in the processor
        processor = state["processor"]
        func = getattr(processor, "sentence", None) if processor else None
        if func:
            func(state, result)

    def process(self, session, processor):
        """ Process a tree for an entire article """
        # For each sentence in turn, do a depth-first traversal,
        # visiting each parent node after visiting its children
        # Initialize the running state that we keep between sentences

        article_begin = getattr(processor, "article_begin", None) if processor else None
        article_end = getattr(processor, "article_end", None) if processor else None

        with closing(BIN_Db.get_db()) as bin_db:

            state = { "session": session, "processor": processor,
                "bin_db": bin_db, "url": self.url }
            # Call the article_begin(state) function, if it exists
            if article_begin:
                article_begin(state)
            # Process the (parsed) sentences in the article
            for index, tree in self.s.items():
                self.process_sentence(state, index, tree)
            # Call the article_end(state) function, if it exists
            if article_end:
                article_end(state)


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

    def __init__(self, processor_directory):

        Processor._init_class()

        # Dynamically load all processor modules
        # (i.e. .py files found in the processor directory, except those
        # with names starting with an underscore)
        self.processors = []
        import os
        for fname in os.listdir(processor_directory):
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
                elif article.tree:
                    tree = Tree(url)
                    tree.load(article.tree)
                    # Run all processors in turn
                    for p in self.processors:
                        tree.process(session, p)

                # So far, so good: commit to the database
                session.commit()

            except Exception as e:
                # If an exception occurred, roll back the transaction
                session.rollback()
                print("Exception caught, transaction rolled back: {0}".format(e))

        t1 = time.time()
        sys.stdout.flush()

    def go(self, from_date = None, limit = 0):
        """ Process already parsed articles from the database """

        db = Processor._db
        with closing(db.session) as session:

            # noinspection PyComparisonWithNone
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
                    self.go_single(url)
            else:
                # Use a multiprocessing pool to process the articles
                pool = Pool() # Defaults to using as many processes as there are CPUs
                pool.map(self.go_single, iter_parsed_articles(limit))
                pool.close()
                pool.join()


def process_articles(from_date = None, limit = 0):

    print("------ Reynir starting processing -------")
    ts = "{0}".format(datetime.utcnow())[0:19]
    print("Time: {0}\n".format(ts))

    t0 = time.time()

    try:
        # Run all processors in the processors directory
        proc = Processor("processors")
        proc.go(from_date, limit = limit)
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


def _main(argv = None):
    """ Guido van Rossum's pattern for a Python main function """

    if argv is None:
        argv = sys.argv
    try:
        try:
            opts, args = getopt.getopt(argv[1:], "hil:u:", ["help", "init", "limit=", "url="])
        except getopt.error as msg:
             raise Usage(msg)
        limit = 10 # !!! DEBUG default limit on number of articles to parse, unless otherwise specified
        init = False
        url = None
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
            elif o in ("-u", "--url"):
                # Single URL to process
                url = a

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
                # Process already parsed trees, starting on January 1, 2016
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
