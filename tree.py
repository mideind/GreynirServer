#!/usr/bin/env python
"""
    Reynir: Natural language processing for Icelandic

    Tree module

    Copyright (c) 2016 Vilhjalmur Thorsteinsson
    All rights reserved
    See the accompanying README.md file for further licensing and copyright information.

    This module implements a data structure for parsed sentence trees that can
    be loaded from text strings and processed by plug-in processing functions.

    A set of provided utility functions allow the extraction of nominative, indefinite
    and canonical (nominative + indefinite + singular) forms of the text within any subtree.

"""

import json
import re

from contextlib import closing
from collections import OrderedDict, namedtuple

from settings import DisallowedNames
from bindb import BIN_Db


BIN_ORDFL = {
    "no" : { "kk", "kvk", "hk" },
    "sérnafn" : { "kk", "kvk", "hk" },
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

        Additionally, the class implements lazy evaluation of the r._root,
        r._nominative and similar built-in attributes so that they are only calculated when
        and if required, and then cached. This is an optimization to save database
        reads.

    """

    def __init__(self, node, state, params):
        self.dict = dict() # Our own custom dict for instance attributes
        self._node = node
        self._state = state
        self._params = params

    def __repr__(self):
        return "Result with {0} params\nDict is: {1}".format(len(self._params) if self._params else 0, self.dict)

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
        if key == "_canonical":
            # Lazy evaluation of the _canonical attribute
            # (Note that it can be overridden by setting it directly)
            d[key] = val = self._node.canonical(self._state, self._params)
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
            for p, c in zip(self._params, self._node.children()):
                if test_f is None or test_f(c):
                    yield (c, p)

    def enum_descendants(self, test_f = None):
        """ Enumerate the descendant parameters of this node, yielding (child_node, result)
            where the child node meets the given test, if any """
        if self._params:
            for p, c in zip(self._params, self._node.children()):
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

    def child_has_nt_base(self, s):
        """ Does the node have a single child with the given nonterminal base name? """
        ch = self.child
        if ch is None:
            # No child
            return False
        if ch.nxt is not None:
            # More than one child
            return False
        return ch.has_nt_base(s)

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


class TerminalDescriptor:

    """ Wraps a terminal specification and is able to select a token meaning
        that matches that specification """

    _CASES = { "nf", "þf", "þgf", "ef" }
    _GENDERS = { "kk", "kvk", "hk" }
    _NUMBERS = { "et", "ft" }
    _PERSONS = { "p1", "p2", "p3" }

    def __init__(self, terminal):
        self.terminal = terminal
        elems = terminal.split("_")
        self.cat = elems[0]
        self.is_literal = self.cat[0] == '"' # Literal terminal, i.e. "sem", "og"
        self.is_stem = self.cat[0] == "'" # Stem terminal, i.e. 'vera'_et_p3
        self.variants = set(elems[1:])

        self.variant_vb = "vb" in self.variants
        self.variant_gr = "gr" in self.variants

        # BIN category set
        self.bin_cat = BIN_ORDFL.get(self.cat, None)

        # Gender of terminal
        self.gender = None
        gender = self.variants & self._GENDERS
        assert 0 <= len(gender) <= 1
        if gender:
            self.gender = next(iter(gender))

        # Case of terminal
        self.case = None
        if self.cat not in { "so", "fs" }:
            # We do not check cases for verbs, except so_lhþt ones
            case = self.variants & self._CASES
            if len(case) > 1:
                print("Many cases detected for terminal {0}, variants {1}".format(terminal, self.variants))
            assert 0 <= len(case) <= 1
            if case:
                self.case = next(iter(case))

        self.case_nf = self.case == "nf"

        # Person of terminal
        self.person = None
        person = self.variants & self._PERSONS
        assert 0 <= len(person) <= 1
        if person:
            self.person = next(iter(person))

        # Number of terminal
        self.number = None
        number = self.variants & self._NUMBERS
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
        if self.gender is not None:
            # Check gender match
            if self.cat == "no":
                if m.ordfl != self.gender:
                    return False
            elif self.gender.upper() not in m.beyging:
                return False
        if self.case is not None:
            # Check case match
            if case_override is not None:
                # Case override: we don't want other cases beside the given one
                for c in TerminalNode._CASES:
                    if c != case_override:
                        if c.upper() in m.beyging:
                            return False
            elif self.case.upper() not in m.beyging:
                return False
        # Check person match
        if self.person is not None:
            person = self.person.upper()
            person = person[1] + person[0] # Turn p3 into 3P
            if person not in m.beyging:
                return False
        # Check number match
        if self.number is not None:
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
        if self.variant_vb:
            if "VB" not in m.beyging:
                return False
        if "sb" in self.variants:
            if "SB" not in m.beyging:
                return False
        # Definite article
        if self.variant_gr:
            if "gr" not in m.beyging:
                return False
        #print("_bin_filter returns True")
        return True

    def stem(self, bindb, word, at_start = False):
        """ Returns the stem of a word matching this terminal """
        if self.is_literal or self.is_stem:
            # A literal or stem terminal only matches a word if it has the given stem
            return self.cat[1:-1]
        if ' ' in word:
            # Multi-word phrase: we return it unchanged
            return word
        _, meanings = bindb.lookup_word(word, at_start)
        if meanings:
            for m in meanings:
                if self._bin_filter(m):
                    # Found a matching meaning: return the stem
                    return m.stofn
        # No meanings found in BÍN: return the word itself as its own stem
        return word


class TerminalNode(Node):

    """ A Node corresponding to a terminal """

    _TD = dict() # Cache of terminal descriptors

    def __init__(self, terminal, token, tokentype, aux, at_start):
        super().__init__()
        td = self._TD.get(terminal)
        if td is None:
            # Not found in cache: make a new one
            td = TerminalDescriptor(terminal)
            self._TD[terminal] = td
        self.td = td
        self.token = token
        self.text = token[1:-1] # Cut off quotes
        self.at_start = at_start
        self.tokentype = tokentype
        self.is_word = tokentype in { "WORD", "PERSON" }
        self.is_literal = td.is_literal
        self.aux = aux # Auxiliary information, originally from token.t2
        # Cache the root form of this word so that it is only looked up
        # once, even if multiple processors scan this tree
        self.root_cache = None
        self.nominative_cache = None
        self.indefinite_cache = None
        self.canonical_cache = None

    def has_t_base(self, s):
        """ Does the node have the given terminal base name? """
        return self.td.has_t_base(s)

    def has_variant(self, s):
        """ Does the node have the given variant? """
        return self.td.has_variant(s)

    def _root(self, bin_db):
        """ Look up the root of the word associated with this terminal """
        # Lookup the token in the BIN database
        if (not self.is_word) or self.is_literal:
            return self.text
        w, m = bin_db.lookup_word(self.text, self.at_start)
        if m:
            # Find the meaning that matches the terminal
            m = next((x for x in m if self.td._bin_filter(x)), None)
        if m:
            w = m.stofn
        return w.replace("-", "")

    def lookup_alternative(self, bin_db, replace_func):
        """ Return a different word form, if available, by altering the beyging
            spec via the given replace_func function """
        #print("_lookup_alternative looking up {0}, cat is {1}".format(self.text, self.cat))
        w, m = bin_db.lookup_word(self.text, self.at_start)
        if m:
            #print("lookup_alternative: meanings are {0}".format(m))
            # Narrow the meanings down to those that are compatible with the terminal
            m = [ x for x in m if self.td._bin_filter(x) ]
        if m:
            #print("Meanings from lookup_word are {0}".format(m))
            # Look up the distinct roots of the word
            result = []
            for x in m:

                # Calculate a new beyging string with the nominative case
                beyging = replace_func(x.beyging)
                #print("Replaced beyging {0} by {1}".format(x.beyging, beyging))

                if beyging is x.beyging:
                    # No replacement made: word form is identical in the nominative case
                    result.append(x)
                else:
                    # Lookup the same word (identified by 'utg') but a different declination
                    prefix = "".join(x.ordmynd.split("-")[0:-1])
                    #print("x.ordmynd is {0}, x.utg is {1}, prefix is {2}".format(x.ordmynd, x.utg, prefix))
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
        #print("_nominative of {0}, token {1}, terminal {2}".format(self.text, self.token, self.terminal))
        if (not self.is_word) or self.td.case_nf or self.is_literal \
            or self.td.cat in { "ao", "eo", "fs", "st", "nhm" }:
            # Not a word, already nominative or not declinable: return it as-is
            return self.text
        if not self.text:
            print("self.text is empty, token is {0}, terminal is {1}".format(self.token, self.td.terminal))
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
        """ Look up the indefinite nominative form of a noun or adjective associated with this terminal """
        # Lookup the token in the BIN database
        #print("indefinite: {0} cat {1} variants {2}".format(self.text, self.cat, self.variants))
        if (not self.is_word) or self.is_literal:
            # Not a word, not a noun or already indefinite: return it as-is
            return self.text
        if self.td.cat not in { "no", "lo" }:
            return self.text
        if self.td.case_nf and ((self.td.cat == "no" and not self.td.variant_gr)
            or (self.td.cat == "lo" and not self.td.variant_vb)):
            # Already in nominative case, and indefinite in the case of a noun
            # or strong declination in the case of an adjective
            return self.text

        if not self.text:
            print("self.text is empty, token is {0}, terminal is {1}".format(self.token, self.td.terminal))
            assert False

        def replace_beyging(b, by_case = "NF"):
            """ Change a beyging string to specify a different case, without the definitive article """
            for case in ("NF", "ÞF", "ÞGF", "EF"):
                if case != by_case and case in b:
                    return b.replace(case, by_case).replace("gr", "").replace("VB", "SB")
            # No case found: shouldn't really happen, but whatever
            return b.replace("gr", "").replace("VB", "SB")

        # Lookup the same word stem but in the nominative case
        w = self.lookup_alternative(bin_db, replace_beyging)

        #print("_indefinite returning {0}".format(w))
        return w

    def _canonical(self, bin_db):
        """ Look up the singular indefinite nominative form of a noun or adjective associated with this terminal """
        # Lookup the token in the BIN database
        #print("indefinite: {0} cat {1} variants {2}".format(self.text, self.cat, self.variants))
        if (not self.is_word) or self.is_literal:
            # Not a word, not a noun or already indefinite: return it as-is
            return self.text
        if self.td.cat not in { "no", "lo" }:
            return self.text
        if self.td.case_nf and self.td.number == "et" and ((self.td.cat == "no" and not self.td.variant_gr)
            or (self.td.cat == "lo" and not self.td.variant_vb)):
            # Already singular, nominative, indefinite (if noun)
            return self.text

        if not self.text:
            print("self.text is empty, token is {0}, terminal is {1}".format(self.token, self.terminal))
            assert False

        def replace_beyging(b, by_case = "NF"):
            """ Change a beyging string to specify a different case, without the definitive article """
            for case in ("NF", "ÞF", "ÞGF", "EF"):
                if case != by_case and case in b:
                    return b.replace(case, by_case).replace("FT", "ET").replace("gr", "").replace("VB", "SB")
            # No case found: shouldn't really happen, but whatever
            return b.replace("FT", "ET").replace("gr", "").replace("VB", "SB")

        # Lookup the same word stem but in the nominative case
        w = self.lookup_alternative(bin_db, replace_beyging)

        #print("_indefinite returning {0}".format(w))
        return w

    def root(self, state, params):
        """ Calculate the root form (stem) of this node's text """
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
        """ Calculate the nominative, indefinite form of this node's text """
        if self.indefinite_cache is None:
            # Not already cached: look up in database
            bin_db = state["bin_db"]
            self.indefinite_cache = self._indefinite(bin_db)
        return self.indefinite_cache

    def canonical(self, state, params):
        """ Calculate the singular, nominative, indefinite form of this node's text """
        if self.canonical_cache is None:
            # Not already cached: look up in database
            bin_db = state["bin_db"]
            self.canonical_cache = self._canonical(bin_db)
        return self.canonical_cache

    def string_self(self):
        return self.td.terminal + " <" + self.token + ">"

    def process(self, state, params):
        """ Prepare a result object to be passed up to enclosing nonterminals """
        assert not params # A terminal node should not have parameters
        result = Result(self, state, None) # No params
        result._terminal = self.td.terminal
        result._text = self.text
        result._token = self.token
        result._tokentype = self.tokentype
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
        # (full name meaning that it includes the patronym/matronym even
        # if it was not present in the original token)
        if self.fullname:
            # print("PersonNode._root: found full name '{0}'".format(self.fullname))
            # !!! TBD: The full name here is constructed by the tokenizer without
            # !!! knowledge of the case of the name - so it may be wrong
            return self.fullname
        # Lookup the token in the BIN database
        case = self.td.case.upper()
        # Look up each part of the name
        at_start = self.at_start
        name = []
        for part in self.text.split(" "):
            w, m = bin_db.lookup_word(part, at_start)
            at_start = False
            if m:
                m = [ x for x in m
                        if x.ordfl == self.td.gender and case in x.beyging and "ET" in x.beyging
                        # Do not accept 'Sigmund' as a valid stem for word forms that
                        # are identical with the stem 'Sigmundur'
                        and (x.stofn not in DisallowedNames.STEMS
                        or self.td.case not in DisallowedNames.STEMS[x.stofn])
                    ]
            if m:
                w = m[0].stofn
            name.append(w.replace("-", ""))
        # print("PersonNode._root: returning '{0}'".format(" ".join(name)))
        return " ".join(name)

    def _nominative(self, bin_db):
        """ The nominative is identical to the root """
        return self._root(bin_db)

    def _indefinite(self, bin_db):
        """ The indefinite is identical to the nominative """
        return self._nominative(bin_db)

    def _canonical(self, bin_db):
        """ The canonical is identical to the nominative """
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

    def canonical(self, state, params):
        """ The canonical form of a nonterminal is a sequence of the canonical forms of its children (parameters) """
        return " ".join(p._canonical for p in params if p._canonical)

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
        if params:
            # Don't invoke if this is an epsilon nonterminal (i.e. has no children)
            processor = state["processor"]
            func = getattr(processor, self.nt_base, None) if processor else None
            if func:
                try:
                    func(self, params, result)
                except TypeError as ex:
                    print("Attempt to call {0}() in processor raised exception {1}"
                        .format(self.nt_base, ex))
                    raise
        return result


class TreeBase:

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

    def __getitem__(self, n):
        """ Allow indexing to get sentence roots from the tree """
        return self.s[n]

    def __contains__(self, n):
        """ Allow query of sentence indices """
        return n in self.s

    def sentences(self):
        """ Enumerate the sentences in this tree """
        for ix, sent in self.s.items():
            yield ix, sent

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

    def handle_E(self, n):
        """ End of sentence with error """
        # Nothing stored
        assert self.n not in self.s
        self.stack = None

    def handle_P(self, n):
        """ Epsilon node: leave the parent nonterminal childless """
        pass

    @staticmethod
    def _parse_T(s):
        """ Parse a T (Terminal) descriptor """
        # The string s contains:
        # terminal "token" [TOKENTYPE] [auxiliary-json]
        # The terminal may itself be a single-quoted string
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
        return (terminal, token, tokentype, aux, cat)

    def handle_T(self, n, s):
        """ Terminal """
        terminal, token, tokentype, aux, cat = self._parse_T(s)
        constructor = self._TC.get(cat, TerminalNode)
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
                if len(a) >= 2:
                    f(n, a[1])
                else:
                    f(n)
            else:
                print("*** No handler for {0}".format(line))


class Tree(TreeBase):

    """ A processable tree corresponding to a single parsed article """

    def __init__(self, url = "", authority = 1.0):
        super().__init__()
        self.url = url
        self.authority = authority

    def visit_children(self, state, node):
        """ Visit the children of node, obtain results from them and pass them to the node """
        return node.process(state, [ self.visit_children(state, child) for child in node.children() ])

    def process_sentence(self, state, tree):
        """ Process a single sentence tree """
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
                "bin_db": bin_db, "url": self.url, "authority": self.authority }
            # Call the article_begin(state) function, if it exists
            if article_begin:
                article_begin(state)
            # Process the (parsed) sentences in the article
            for index, tree in self.s.items():
                self.process_sentence(state, tree)
            # Call the article_end(state) function, if it exists
            if article_end:
                article_end(state)


class TreeGist(TreeBase):

    """ A gist of a tree corresponding to a single parsed article.
        A gist simply knows which sentences are present in the tree
        and what the error token index is for sentences that are not present. """

    def __init__(self):
        super().__init__()
        # Dictionary of error token indices for sentences that weren't successfully parsed
        self._err_index = dict()

    def err_index(self, n):
        """ Return the error token index for an unparsed sentence, if any, or None """
        return self._err_index.get(n)

    def push(self, n, node):
        """ This should not be invoked for a gist """
        assert False

    def handle_Q(self, n):
        """ End of sentence """
        self.s[self.n] = None # Simply note that the sentence is present without storing it
        self.stack = None

    def handle_E(self, n):
        """ End of sentence with error """
        super().handle_E(n)
        self._err_index[self.n] = n # Note the index of the error token

    def handle_T(self, n, s):
        """ Terminal """
        # No need to store anything for gists
        pass

    def handle_N(self, n, nonterminal):
        """ Nonterminal """
        # No need to store anything for gists
        pass


TreeToken = namedtuple('TreeToken', [ 'terminal', 'token', 'tokentype', 'aux', 'cat' ])

class TreeTokenList(TreeBase):

    """ A tree that allows easy iteration of its token/terminal matches """

    def __init__(self):
        super().__init__()

    def handle_Q(self, n):
        """ End of sentence """
        self.s[self.n] = self.stack
        self.stack = None

    def handle_T(self, n, s):
        """ Terminal """
        terminal, token, tokentype, aux, cat = self._parse_T(s)
        # Append to token list for current sentence
        assert self.stack is not None
        self.stack.append(TreeToken(terminal = terminal, token = token, tokentype = tokentype, aux = aux, cat = cat))

    def handle_N(self, n, nonterminal):
        """ Nonterminal """
        # No action required for token lists
        pass

