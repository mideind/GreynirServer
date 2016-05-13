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
    "pfn" : { "pfn" },
    "st" : { "st" }
}


class Result:

    """ Container for results that are sent from child nodes to parent nodes.
        This class is instrumented so that it is equivalent to use attribute
        or indexing notation, i.e. r.efliður is the same as r["efliður"].

        (This also sidesteps a bug in PyPy 2.6.0 which doesn't fully
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
        """ Fancy attribute setter using our own dict for instance attributes """
        if key == "__dict__" or key == "dict" or key in self.__dict__:
            # Relay to Python's default attribute resolution mechanism
            super().__setattr__(key, val)
        else:
            # Set attribute in our own dict
            self.dict[key] = val

    def __getattr__(self, key):
        """ Fancy attribute getter with special cases for _root and _nominative """
        if key == "__dict__" or key == "dict" or key in self.__dict__:
            # Relay to Python's default attribute resolution mechanism
            return super().__getattr__(key)
        d = self.dict
        if key in d:
            return d[key]
        # Key not found: try lazy evaluation
        if key == "_root":
            # Lazy evaluation of the _root attribute
            # (Note that it can be overridden by setting it directly)
            d[key] = val = self._node.root(self._state, self._params)
            return val
        if key == "_nominative":
            # Lazy evaluation of the _nominative attribute
            # (Note that it can be overridden by setting it directly)
            d[key] = val = self._node.nominative(self._state, self._params)
            return val
        if key == "_indefinite":
            # Lazy evaluation of the _indefinite attribute
            # (Note that it can be overridden by setting it directly)
            d[key] = val = self._node.indefinite(self._state, self._params)
            return val
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

    def enum_children(self, test_f = None):
        """ Enumerate the child parameters of this node, yielding (child_node, result)
            where the child node meets the given test, if any """
        if self._params:
            child_nodes = self._node.children()
            for p in self._params:
                c = next(child_nodes)
                if test_f is None or test_f(c):
                    yield (c, p)

    def enum_descendants(self, test_f = None):
        """ Enumerate the descendant parameters of this node, yielding (child_node, result)
            where the child node meets the given test, if any """
        if self._params:
            child_nodes = self._node.children()
            for p in self._params:
                c = next(child_nodes)
                for d_c, d_p in p.enum_descendants(test_f):
                    yield (d_c, d_p)
                if test_f is None or test_f(c):
                    yield (c, p)

    def find_child(self, **kwargs):
        """ Find a child parameter meeting the criteria given in kwargs """

        def test_f(c):
            for key, val in kwargs.items():
                f = getattr(c, "has_" + key, None)
                if f is None or not f(val):
                    return False
            return True

        for c, p in self.enum_children(test_f):
            # Found a child node meeting the criteria: return its associated param
            return p
        # No child node found: return None
        return None

    def all_children(self, **kwargs):
        """ Return all child parameters meeting the criteria given in kwargs """

        def test_f(c):
            for key, val in kwargs.items():
                f = getattr(c, "has_" + key, None)
                if f is None or not f(val):
                    return False
            return True

        return [p for _, p in self.enum_children(test_f)]

    def find_descendant(self, **kwargs):
        """ Find a descendant parameter meeting the criteria given in kwargs """

        def test_f(c):
            for key, val in kwargs.items():
                f = getattr(c, "has_" + key, None)
                if f is None or not f(val):
                    return False
            return True

        for c, p in self.enum_descendants(test_f):
            # Found a child node meeting the criteria: return its associated param
            return p
        # No child node found: return None
        return None


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

    def has_nt_base(self, s):
        """ Does the node have the given nonterminal base name? """
        return False

    def has_t_base(self, s):
        """ Does the node have the given terminal base name? """
        return False

    def has_variant(self, s):
        """ Does the node have the given variant? """
        return False

    def children(self, test_f = None):
        """ Yield all children of this node (that pass a test function, if given) """
        c = self.child
        while c:
            if test_f is None or test_f(c):
                yield c
            c = c.nxt

    def first_child(self, test_f):
        """ Return the first child of this node that matches a test function, or None """
        c = self.child
        while c:
            if test_f(c):
                return c
            c = c.nxt
        return None

    def descendants(self, test_f = None):
        """ Do a depth-first traversal of all children of this node,
            returning those that pass a test function, if given """
        c = self.child
        while c:
            for cc in c.descendants():
                if test_f is None or test_f(cc):
                    yield cc
            if test_f is None or test_f(c):
                yield c
            c = c.nxt

    def string_self(self):
        """ String representation of the name of this node """
        raise NotImplementedError # Should be overridden

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
        self.is_literal = self.cat[0] == '"' # Literal terminal, i.e. "sem", "og"
        self.variants = set(elems[1:])
        self.tokentype = tokentype
        self.is_word = tokentype == "WORD"
        self.aux = aux # Auxiliary information, originally from token.t2
        # Cache the root form of this word so that it is only looked up
        # once, even if multiple processors scan this tree
        self.root_cache = None
        self.nominative_cache = None
        self.indefinite_cache = None

        # BIN category set
        self.bin_cat = BIN_ORDFL.get(self.cat, None)

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

    def has_t_base(self, s):
        """ Does the node have the given terminal base name? """
        return self.cat == s

    def has_variant(self, s):
        """ Does the node have the given variant? """
        return s in self.variants

    def _bin_filter(self, m, case_override = None):
        """ Return True if the BIN meaning in m matches the variants for this terminal """
        #print("_bin_filter checking meaning {0}".format(m))
        if self.bin_cat is not None and m.ordfl not in self.bin_cat:
            return False
        if self.gender:
            # Check gender match
            if self.cat == "no":
                if m.ordfl != self.gender:
                    return False
            elif self.gender.upper() not in m.beyging:
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
        # Check VB/SB/MST for adjectives
        if "esb" in self.variants:
            if "ESB" not in m.beyging:
                return False
        if "mst" in self.variants:
            if "MST" not in m.beyging:
                return False
        if "vb" in self.variants:
            if "VB" not in m.beyging:
                return False
        if "sb" in self.variants:
            if "SB" not in m.beyging:
                return False
        # Definite article
        if "gr" in self.variants:
            if "gr" not in m.beyging:
                return False
        #print("_bin_filter returns True")
        return True

    def _root(self, bin_db):
        """ Look up the root of the word associated with this terminal """
        # Lookup the token in the BIN database
        if (not self.is_word) or self.is_literal:
            return self.text
        w, m = bin_db.lookup_word(self.text, self.at_start)
        if m:
            m = [ x for x in m if self._bin_filter(x) ]
        if m:
            w = m[0].stofn
        return w.replace("-", "")

    def lookup_alternative(self, bin_db, replace_func):
        """ Return a different word form, if available, by altering the beyging
            spec via the given replace_func function """
        #print("_nominative looking up {0}, cat is {1}".format(self.text, self.cat))
        w, m = bin_db.lookup_word(self.text, self.at_start)
        if m:
            # Narrow the meanings down to those that are compatible with the terminal
            m = [ x for x in m if self._bin_filter(x) ]
        if m:
            #print("Meanings from lookup_word are {0}".format(m))
            # Look up the distinct roots of the word
            result = []
            for x in m:

                # Calculate a new beyging string with the nominative case
                beyging = replace_func(x.beyging)

                if beyging is x.beyging:
                    # No replacement made: word form is identical in the nominative case
                    result.append(x)
                else:
                    # Lookup the same word (identified by 'utg') but a different declination
                    prefix = "".join(x.ordmynd.split("-")[0:-1])
                    wordform = bin_db.lookup_utg(x.utg, beyging = beyging)
                    if wordform:
                        result += bin_db.prefix_meanings(wordform, prefix)

            if result:
                #if len(result) > 1:
                #    print("Choosing first item from meaning list:\n{0}".format(result))
                # There can be more than one word form that matches our spec.
                # We can't choose between them so we simply return the first one.
                w = result[0].ordmynd
        return w.replace("-", "")

    def _nominative(self, bin_db):
        """ Look up the nominative form of the word associated with this terminal """
        # Lookup the token in the BIN database
        if (not self.is_word) or (self.case == "nf") or self.is_literal or self.cat in { "ao", "eo", "fs", "st", "nhm" }:
            # Not a word, already nominative or not declinable: return it as-is
            return self.text
        if not self.text:
            print("self.text is empty, token is {0}, terminal is {1}".format(self.token, self.terminal))
            assert False

        def replace_beyging(b, by_case = "NF"):
            """ Change a beyging string to specify a different case """
            for case in ("NF", "ÞF", "ÞGF", "EF"):
                if case != by_case and case in b:
                    return b.replace(case, by_case)
            return b

        # Lookup the same word stem but in the nominative case
        w = self.lookup_alternative(bin_db, replace_beyging)

        if self.text.isupper():
            # Original word was all upper case: convert result to upper case
            w = w.upper()
        elif self.text[0].isupper():
            # First letter was upper case: convert result accordingly
            w = w[0].upper() + w[1:]
        #print("_nominative returning {0}".format(w))
        return w

    def _indefinite(self, bin_db):
        """ Look up the indefinite nominative form of a noun associated with this terminal """
        # Lookup the token in the BIN database
        if (not self.is_word) or self.is_literal or self.cat != "no" or "gr" not in self.variants:
            # Not a word, not a noun or already indefinite: return it as-is
            return self.text
        if not self.text:
            print("self.text is empty, token is {0}, terminal is {1}".format(self.token, self.terminal))
            assert False

        def replace_beyging(b, by_case = "NF"):
            """ Change a beyging string to specify a different case, without the definitive article """
            for case in ("NF", "ÞF", "ÞGF", "EF"):
                if case != by_case and case in b:
                    return b.replace(case, by_case).replace("gr", "")
            # No case found: shouldn't really happen, but whatever
            return b.replace("gr", "")

        # Lookup the same word stem but in the nominative case
        w = self.lookup_alternative(bin_db, replace_beyging)

        #print("_indefinite returning {0}".format(w))
        return w

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

    def indefinite(self, state, params):
        """ Calculate the nominative form of this node's text """
        if self.indefinite_cache is None:
            # Not already cached: look up in database
            bin_db = state["bin_db"]
            self.indefinite_cache = self._indefinite(bin_db)
        return self.indefinite_cache

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

    def _indefinite(self, bin_db):
        """ The indefinite is identical to the nominative """
        return self._nominative(bin_db)


class NonterminalNode(Node):

    """ A Node corresponding to a nonterminal """

    def __init__(self, nonterminal):
        super().__init__()
        self.nt = nonterminal
        elems = nonterminal.split("_")
        # Calculate the base name of this nonterminal (without variants)
        self.nt_base = elems[0]
        self.variants = set(elems[1:])

    def has_nt_base(self, s):
        """ Does the node have the given nonterminal base name? """
        return self.nt_base == s

    def has_variant(self, s):
        """ Does the node have the given variant? """
        return s in self.variants

    def string_self(self):
        return self.nt

    def root(self, state, params):
        """ The root form of a nonterminal is a sequence of the root forms of its children (parameters) """
        return " ".join(p._root for p in params if p._root)

    def nominative(self, state, params):
        """ The nominative form of a nonterminal is a sequence of the nominative forms of its children (parameters) """
        return " ".join(p._nominative for p in params if p._nominative)

    def indefinite(self, state, params):
        """ The indefinite form of a nonterminal is a sequence of the indefinite forms of its children (parameters) """
        return " ".join(p._indefinite for p in params if p._indefinite)

    def process(self, state, params):
        """ Apply any requested processing to this node """
        result = Result(self, state, params)
        result._nonterminal = self.nt
        # Calculate the combined text rep of the results of the children
        result._text = " ".join(p._text for p in params if p._text)
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

    def __init__(self, url, authority):
        self.s = OrderedDict() # Sentence dictionary
        self.stack = None
        self.n = None # Index of current sentence
        self.at_start = False # First token of sentence?
        # Dictionary of error token indices for sentences that weren't successfully parsed
        self._err_index = dict()
        self._gist = False
        self.url = url
        self.authority = authority

    def __getitem__(self, n):
        """ Allow indexing to get sentence roots from the tree """
        return self.s[n]

    def __contains__(self, n):
        """ Allow query of sentence indices """
        return n in self.s

    def err_index(self, n):
        """ Return the error token index for an unparsed sentence, if any, or None """
        return self._err_index.get(n)

    def push(self, n, node):
        """ Add a node into the tree at the right level """
        assert not self._gist
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
        self.s[self.n] = None if self._gist else self.stack[0]
        self.stack = None
        #print("Tree [{0}] is: {1}".format(self.n, self.s[self.n]))

    def handle_E(self, n):
        """ End of sentence with error """
        # Store the root of the sentence tree at the appropriate index
        # in the dictionary
        assert self.n not in self.s
        self._err_index[self.n] = n # Note the index of the error token
        self.stack = None

    def handle_T(self, n, s):
        """ Terminal """
        # The string s contains:
        # terminal "token" [TOKENTYPE] [auxiliary-json]
        # The terminal may itself be a single-quoted string
        if self._gist:
            return
        if s[0] == "'":
            r = re.match(r'\'[^\']*\'\w*', s)
            terminal = r.group() if r else ""
            s = s[r.end() + 1:] if r else ""
        else:
            a = s.split(' ', maxsplit = 1)
            terminal = a[0]
            s = a[1]
        r = re.match(r'\"[^\"]*\"', s)
        if r is None:
            # Compatibility: older versions used single quotes
            r = re.match(r'\'[^\']*\'', s)
        token = r.group() if r else ""
        s = s[r.end() + 1:] if r else ""
        a = s.split(' ', maxsplit = 1) if s else ["WORD"] # Default token type
        tokentype = a[0]
        aux = a[1] if len(a) > 1 else "" # Auxiliary info (originally token.t2)
        # print("terminal {0} token {1} tokentype {2} aux {3}".format(terminal, token, tokentype, aux))
        # Select a terminal constructor based on the first part of the
        # terminal name
        cat = terminal.split("_", maxsplit = 1)[0]
        constructor = Tree._TC.get(cat, TerminalNode)
        self.push(n, constructor(terminal, token, tokentype, aux, self.at_start))
        self.at_start = False

    def handle_N(self, n, nonterminal):
        """ Nonterminal """
        if self._gist:
            return
        self.push(n, NonterminalNode(nonterminal))

    def _load(self, txt, gist = False):
        """ Loads a tree from the text format stored by the scraper """

        self._gist = gist
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
                if len(a) >= 2:
                    f(n, a[1])
                else:
                    f(n)
            else:
                print("*** No handler for {0}".format(line))

    def load(self, txt):
        """ Load a tree entirely into memory, creating all nodes """
        self._load(txt, gist = False)

    def load_gist(self, txt):
        """ Only load the sentence dictionary in gist form into memory """
        self._load(txt, gist = True)

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

        assert not self._gist # Not applicable to trees that are loaded as gists only

        article_begin = getattr(processor, "article_begin", None) if processor else None
        article_end = getattr(processor, "article_end", None) if processor else None

        with closing(BIN_Db.get_db()) as bin_db:

            state = { "session": session, "processor": processor,
                "bin_db": bin_db, "url": self.url, "authority": self.authority }
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
                print("Exception caught in article {0}, transaction rolled back\nException: {1}".format(url, e))
                #raise

        t1 = time.time()
        sys.stdout.flush()

    def go(self, from_date = None, limit = 0, force = False):
        """ Process already parsed articles from the database """

        db = Processor._db
        with closing(db.session) as session:

            # noinspection PyComparisonWithNone,PyShadowingNames
            def iter_parsed_articles():
                """ Go through parsed articles and process them """
                q = session.query(Article.url).filter(Article.tree != None)
                if not force:
                    # If force = True, re-process articles even if
                    # they have been processed before
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


def process_articles(from_date = None, limit = 0, force = False, processor = None):

    print("------ Reynir starting processing -------")
    if from_date:
        print("From date: {0}".format(from_date))
    if limit:
        print("Limit: {0} articles".format(limit))
    if force:
        print("Force re-processing: Yes")
    if processor:
        print("Invoke single processor: {0}".format(processor))
    ts = "{0}".format(datetime.utcnow())[0:19]
    print("Time: {0}\n".format(ts))

    t0 = time.time()

    try:
        # Run all processors in the processors directory, or the single processor given
        proc = Processor(processor_directory = "processors", single_processor = processor)
        proc.go(from_date, limit = limit, force = force)
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

"""

def _main(argv = None):
    """ Guido van Rossum's pattern for a Python main function """

    if argv is None:
        argv = sys.argv
    try:
        try:
            opts, args = getopt.getopt(argv[1:], "hifl:u:p:", ["help", "init", "force", "limit=", "url=", "processor="])
        except getopt.error as msg:
             raise Usage(msg)
        limit = 10 # !!! DEBUG default limit on number of articles to parse, unless otherwise specified
        init = False
        url = None
        force = False
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
                process_articles(from_date = datetime(year = 2016, month = 3, day = 1),
                    limit = limit, force = force, processor = proc)
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
