"""

    Greynir: Natural language processing for Icelandic

    Tree module

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


    This module implements a data structure for parsed sentence trees that can
    be loaded from text strings and processed by plug-in processing functions.

    A set of provided utility functions allow the extraction of nominative,
    indefinite and canonical (nominative + indefinite + singular) forms of
    the text within any subtree.

"""

from __future__ import annotations

from typing import (
    Dict,
    FrozenSet,
    Iterable,
    Mapping,
    MutableMapping,
    Optional,
    List,
    Set,
    Tuple,
    Any,
    Union,
    Callable,
    Iterator,
    NamedTuple,
    cast,
)
from typing_extensions import Required, TypedDict
from types import ModuleType


import json
import re

import abc
from contextlib import contextmanager
from islenska.basics import BinMeaning, make_bin_entry

from sqlalchemy.orm import Session

from tokenizer import BIN_Tuple
from reynir.bindb import GreynirBin
from reynir.binparser import BIN_Token
from reynir.simpletree import SimpleTree, SimpleTreeBuilder, NonterminalMap, IdMap
from reynir.cache import LRU_Cache

# Processing environment
# A mapping of keywords or nonterminal names to functions
# for processing sentence trees or, more specifically, query trees
ProcEnv = MutableMapping[str, Any]


# A location, as returned by the locations module
Loc = NamedTuple("Loc", [("name", str), ("kind", Optional[str])])


class TreeStateDict(TypedDict, total=False):
    session: Required[Session]
    processor: Required[ProcEnv]
    bin_db: GreynirBin
    url: str
    authority: float
    index: int
    locations: Set[Loc]  # A bit of a kludge; only used by the locations module
    _sentence: Optional["SentenceFunction"]
    _visit: Optional["VisitFunction"]
    _default: Optional["NonterminalFunction"]


TreeToken = NamedTuple(
    "TreeToken",
    [
        ("terminal", str),
        ("augmented_terminal", str),
        ("token", str),
        ("tokentype", str),
        ("aux", str),
        ("cat", str),
    ],
)

OptionalNode = Optional["Node"]
FilterFunction = Callable[["Node"], bool]
SentenceFunction = Callable[[TreeStateDict, Optional["Result"]], None]
VisitFunction = Callable[[TreeStateDict, "Node"], bool]
ParamList = List["Result"]
NonterminalFunction = Callable[["NonterminalNode", ParamList, "Result"], None]
ChildTuple = Tuple["Node", "Result"]
LookupSignature = Tuple[str, bool, str]

BIN_ORDFL: Mapping[str, Set[str]] = {
    "no": {"kk", "kvk", "hk"},
    "kk": {"kk"},
    "kvk": {"kvk"},
    "hk": {"hk"},
    "sérnafn": {"kk", "kvk", "hk"},
    "so": {"so"},
    "lo": {"lo"},
    "fs": {"fs"},
    "ao": {"ao"},
    "eo": {"ao"},
    "spao": {"ao"},
    "tao": {"ao"},
    "töl": {"töl", "to"},
    "to": {"töl", "to"},
    "fn": {"fn"},
    "pfn": {"pfn"},
    "st": {"st"},
    "stt": {"st"},
    "abfn": {"abfn"},
    "gr": {"gr"},
    "uh": {"uh"},
    "nhm": {"nhm"},
}

_REPEAT_SUFFIXES: FrozenSet[str] = frozenset(("+", "*", "?"))


class Node(abc.ABC):

    """Base class for terminal and nonterminal nodes reconstructed from
    trees in text format loaded from the scraper database"""

    def __init__(self) -> None:
        self.child: Optional["Node"] = None
        self.nxt: Optional["Node"] = None

    def set_next(self, n: Optional["Node"]) -> None:
        self.nxt = n

    def set_child(self, n: Optional["Node"]) -> None:
        self.child = n

    def has_nt_base(self, s: str) -> bool:
        """Does the node have the given nonterminal base name?"""
        return False

    def has_t_base(self, s: str) -> bool:
        """Does the node have the given terminal base name?"""
        return False

    def has_variant(self, s: str) -> bool:
        """Does the node have the given variant?"""
        return False

    @property
    def at_start(self) -> bool:
        """Return True if this node spans the start of a sentence"""
        # This is overridden in TerminalNode
        return False if self.child is None else self.child.at_start

    def child_has_nt_base(self, s: str) -> bool:
        """Does the node have a single child with the given nonterminal base name?"""
        ch = self.child
        if ch is None:
            # No child
            return False
        if ch.nxt is not None:
            # More than one child
            return False
        return ch.has_nt_base(s)

    def children(self, test_f: Optional[FilterFunction] = None) -> Iterator["Node"]:
        """Yield all children of this node (that pass a test function, if given)"""
        c = self.child
        while c:
            if test_f is None or test_f(c):
                yield c
            c = c.nxt

    def first_child(self, test_f: FilterFunction) -> OptionalNode:
        """Return the first child of this node that matches a test function, or None"""
        c = self.child
        while c is not None:
            if test_f(c):
                return c
            c = c.nxt
        return None

    def descendants(self, test_f: Optional[FilterFunction] = None) -> Iterator["Node"]:
        """Do a depth-first traversal of all children of this node,
        returning those that pass a test function, if given"""
        c = self.child
        while c is not None:
            for cc in c.descendants():
                if test_f is None or test_f(cc):
                    yield cc
            if test_f is None or test_f(c):
                yield c
            c = cast(Node, c.nxt)

    @abc.abstractmethod
    def contained_text(self) -> str:
        """Return a string consisting of the literal text of all
        descendants of this node, in depth-first order"""
        raise NotImplementedError  # Should be overridden

    @abc.abstractmethod
    def string_self(self) -> str:
        """String representation of the name of this node"""
        raise NotImplementedError  # Should be overridden

    @abc.abstractmethod
    def nominative(self, state: TreeStateDict, params: ParamList) -> str:
        raise NotImplementedError  # Should be overridden

    @abc.abstractmethod
    def indefinite(self, state: TreeStateDict, params: ParamList) -> str:
        raise NotImplementedError  # Should be overridden

    @abc.abstractmethod
    def canonical(self, state: TreeStateDict, params: ParamList) -> str:
        raise NotImplementedError  # Should be overridden

    @abc.abstractmethod
    def root(self, state: TreeStateDict, params: ParamList) -> str:
        raise NotImplementedError  # Should be overridden

    @abc.abstractproperty
    def text(self) -> str:
        raise NotImplementedError

    @property
    def contained_number(self) -> Optional[float]:
        """Return the number contained within the tree node, if any"""
        # This is implemented for TerminalNodes associated with number tokens
        return None

    @property
    def contained_amount(self) -> Optional[Tuple[float, str]]:
        """Return the amount contained within the tree node, if any"""
        # This is implemented for TerminalNodes associated with amount tokens
        return None

    def string_rep(self, indent: str) -> str:
        """Indented representation of this node"""
        s = indent + self.string_self()
        if self.child is not None:
            s += " (\n" + self.child.string_rep(indent + "  ") + "\n" + indent + ")"
        if self.nxt is not None:
            s += ",\n" + self.nxt.string_rep(indent)
        return s

    @abc.abstractmethod
    def process(self, state: TreeStateDict, params: ParamList) -> "Result":
        raise NotImplementedError

    def build_simple_tree(self, builder: Any) -> None:
        """Default action: recursively build the child nodes"""
        for child in self.children():
            child.build_simple_tree(builder)

    def __str__(self) -> str:
        return self.string_rep("")

    def __repr__(self) -> str:
        return str(self)


class Result:

    """Container for results that are sent from child nodes to parent nodes.
    This class is instrumented so that it is equivalent to use attribute
    or indexing notation, i.e. r.efliður is the same as r["efliður"].

    Additionally, the class implements lazy evaluation of the r._root,
    r._nominative and similar built-in attributes so that they are only
    calculated when and if required, and then cached. This is an optimization
    to save database reads.

    This class has a mechanism which merges the contents of list, set and dict
    attributes when navigating upwards from child nodes to their parents.
    This means that, for instance, two child nodes of a "+" operator could
    each have an attribute called "operand" containing an operand enclosed
    in a list, like so: [ op ]. When the "+" operator node is processed,
    it will automatically get an "operand" attribute
    containing [ left_op, right_op ].

    """

    def __init__(self, node: Node, state: TreeStateDict, params: ParamList) -> None:
        # Our own custom dict for instance attributes
        self.dict: Dict[str, Any] = dict()
        self._node = node
        self._state: TreeStateDict = state
        self._params = params

    @property
    def node(self) -> Node:
        return self._node

    @property
    def state(self) -> TreeStateDict:
        return self._state

    @property
    def params(self) -> ParamList:
        return self._params

    def __repr__(self):
        return "Result with {0} params\nDict is: {1}".format(
            len(self._params) if self._params else 0, self.dict
        )

    def __setattr__(self, key: str, val: Any) -> None:
        """Fancy attribute setter using our own dict for instance attributes"""
        if key == "__dict__" or key == "dict" or key in self.__dict__:
            # Relay to Python's default attribute resolution mechanism
            super().__setattr__(key, val)
        else:
            # Set attribute in our own dict
            self.dict[key] = val

    def __getattr__(self, key: str) -> Any:
        """Fancy attribute getter with special cases for _root and _nominative"""
        # Note: this is only called for attributes that are not found by 'normal' means
        d = self.dict
        if key in d:
            return d[key]
        # Key not found: try lazy evaluation
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
        if key == "_root":
            # Lazy evaluation of the _root attribute
            # (Note that it can be overridden by setting it directly)
            d[key] = val = self._node.root(self._state, self._params)
            return val
        if key == "_text":
            # Lazy evaluation of the _text attribute
            # (Note that it can be overridden by setting it directly)
            d[key] = val = self._node.contained_text()
            return val
        # Not found in our custom dict
        raise AttributeError("Result object has no attribute named '{0}'".format(key))

    def __contains__(self, key: str) -> bool:
        return key in self.dict

    def __getitem__(self, key: str) -> Any:
        return self.dict[key]

    def __setitem__(self, key: str, val: Any) -> None:
        self.dict[key] = val

    def __delitem__(self, key: str) -> None:
        del self.dict[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.dict.get(key, default)

    def attribs(self) -> Iterator[Tuple[str, Any]]:
        """Enumerate all attributes, and values, of this result object"""
        yield from self.dict.items()

    def user_attribs(self) -> Iterator[Tuple[str, Any]]:
        """Enumerate all user-defined attributes and values of this result object"""
        for key, val in self.dict.items():
            if not key.startswith("_") and not callable(val):
                yield (key, val)

    def copy_from(self, p: Optional[Result]) -> None:
        """Copy all user attributes from p into this result"""
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
                left: Union[List[Any], Set[Any], Dict[str, Any]] = d[key]
                if isinstance(left, list) and isinstance(val, list):
                    # Extend lists
                    left.extend(cast(List[Any], val))
                elif isinstance(left, set) and isinstance(val, set):
                    # Return union of sets
                    left |= val
                elif isinstance(left, dict) and isinstance(val, dict):
                    # Keep the left entries but add any new/additional val entries
                    # (This gives left priority; left.update(val) would give right priority)
                    d[key] = dict(cast(Dict[str, Any], val), **left)

    def del_attribs(self, alist: Union[str, Iterable[str]]) -> None:
        """Delete the attribs in alist from the result object"""
        if isinstance(alist, str):
            alist = (alist,)
        d = self.dict
        for a in alist:
            if a in d:
                del d[a]

    def enum_children(
        self, test_f: Optional[Callable[[Node], bool]] = None
    ) -> Iterator[ChildTuple]:
        """Enumerate the child parameters of this node, yielding (child_node, result)
        where the child node meets the given test, if any"""
        if self._params:
            for p, c in zip(self._params, self._node.children()):
                if test_f is None or test_f(c):
                    yield (c, p)

    def enum_descendants(
        self, test_f: Optional[Callable[[Node], bool]] = None
    ) -> Iterator[ChildTuple]:
        """Enumerate the descendant parameters of this node, yielding (child_node, result)
        where the child node meets the given test, if any"""
        if self._params:
            for p, c in zip(self._params, self._node.children()):
                yield from p.enum_descendants(test_f)
                if test_f is None or test_f(c):
                    yield (c, p)

    def find_child(self, **kwargs: Any) -> Optional["Result"]:
        """Find a child parameter meeting the criteria given in kwargs"""

        def test_f(c: Node) -> bool:
            for key, val in kwargs.items():
                f = getattr(c, "has_" + key, None)
                if f is None or not f(val):
                    return False
            return True

        for _, p in self.enum_children(test_f):
            # Found a child node meeting the criteria: return its associated param
            return p
        # No child node found: return None
        return None

    def all_children(self, **kwargs: Any) -> ParamList:
        """Return all child parameters meeting the criteria given in kwargs"""

        def test_f(c: Node) -> bool:
            for key, val in kwargs.items():
                f = getattr(c, "has_" + key, None)
                if f is None or not f(val):
                    return False
            return True

        return [p for _, p in self.enum_children(test_f)]

    def find_descendant(self, **kwargs: Any) -> Optional["Result"]:
        """Find a descendant parameter meeting the criteria given in kwargs"""

        def test_f(c: Node) -> bool:
            for key, val in kwargs.items():
                f = getattr(c, "has_" + key, None)
                if f is None or not f(val):
                    return False
            return True

        for _, p in self.enum_descendants(test_f):
            # Found a child node meeting the criteria: return its associated param
            return p
        # No child node found: return None
        return None

    @property
    def at_start(self) -> bool:
        """Return True if the associated node spans the start of the sentence"""
        return self._node.at_start

    def has_nt_base(self, s: str) -> bool:
        """Does the associated node have the given nonterminal base name?"""
        return self._node.has_nt_base(s)

    def has_t_base(self, s: str) -> bool:
        """Does the associated node have the given terminal base name?"""
        return self._node.has_t_base(s)

    def has_variant(self, s: str) -> bool:
        """Does the associated node have the given variant?"""
        return self._node.has_variant(s)


class TerminalDescriptor:

    """Wraps a terminal specification and is able to select a token meaning
    that matches that specification"""

    _CASES = {"nf", "þf", "þgf", "ef"}
    _GENDERS = {"kk", "kvk", "hk"}
    _NUMBERS = {"et", "ft"}
    _PERSONS = {"p1", "p2", "p3"}

    def __init__(self, terminal: str) -> None:
        self.terminal = terminal
        self.is_literal = terminal[0] == '"'  # Literal terminal, i.e. "sem", "og"
        self.is_stem = terminal[0] == "'"  # Stem terminal, i.e. 'vera'_et_p3
        if self.is_literal or self.is_stem:
            # Go through hoops since it is conceivable that a
            # literal or stem may contain an underscore ('_')
            endq = terminal.rindex(terminal[0])
            elems = [terminal[0 : endq + 1]] + [
                v for v in terminal[endq + 1 :].split("_") if v
            ]
        else:
            elems = terminal.split("_")
        self.cat = elems[0]
        self.inferred_cat = self.cat
        if self.is_literal or self.is_stem:
            # In the case of a 'stem' or "literal",
            # check whether the category is specified
            # (e.g. 'halda:so'_et_p3)
            if ":" in self.cat:
                self.inferred_cat = self.cat.split(":")[-1][:-1]
        self.is_verb = self.inferred_cat == "so"
        self.varlist = elems[1:]
        self.variants = set(self.varlist)

        self.variant_vb = "vb" in self.variants
        self.variant_gr = "gr" in self.variants

        # BIN category set
        self.bin_cat = BIN_ORDFL.get(self.inferred_cat, None)

        # clean_terminal property cache
        self._clean_terminal: Optional[str] = None

        # clean_cat property cache
        self._clean_cat: Optional[str] = None

        # Gender of terminal
        self.gender: Optional[str] = None
        gender = self.variants & self._GENDERS
        assert 0 <= len(gender) <= 1
        if gender:
            self.gender = next(iter(gender))

        # Case of terminal
        self.case: Optional[str] = None
        if self.inferred_cat not in {"so", "fs"}:
            # We do not check cases for verbs, except so_lhþt ones
            case = self.variants & self._CASES
            assert 0 <= len(case) <= 1
            if case:
                self.case = next(iter(case))

        self.case_nf = self.case == "nf"

        # Person of terminal
        self.person: Optional[str] = None
        person = self.variants & self._PERSONS
        assert 0 <= len(person) <= 1
        if person:
            self.person = next(iter(person))

        # Number of terminal
        self.number: Optional[str] = None
        number = self.variants & self._NUMBERS
        assert 0 <= len(number) <= 1
        if number:
            self.number = next(iter(number))

    _OLD_BUGS: Mapping[str, str] = {
        "'margur'": "lo",
        "'fyrri'": "lo",
        "'seinni'": "lo",
        "'annar'": "fn",
        "'á fætur'": "ao",
        "'á_fætur'": "ao",
        "'né'": "st",
    }

    @property
    def clean_terminal(self) -> str:
        """Return a 'clean' terminal name, having converted literals
        to a corresponding category, if available"""
        if self._clean_terminal is None:
            if self.inferred_cat in self._GENDERS:
                # 'bróðir:kk'_gr_ft_nf becomes no_kk_gr_ft_nf
                self._clean_terminal = "no_" + self.inferred_cat
            elif self.inferred_cat in self._OLD_BUGS:
                # In older parses, we may have literal terminals
                # such as 'margur' that are not marked with a category
                self._clean_terminal = self._OLD_BUGS[self.inferred_cat]
            else:
                # 'halda:so'_et_p3 becomes so_et_p3
                self._clean_terminal = self.inferred_cat
            self._clean_terminal += "".join("_" + v for v in self.varlist)
        return self._clean_terminal

    @property
    def clean_cat(self) -> str:
        """Return the category from the front of the clean terminal name.
        This returns 'no' for all nouns (instead of 'kk', 'kvk', 'hk'),
        and handles stem literals correctly (i.e. the terminal
        'vagn:kk'_nf_et_gr has clean_cat == 'no')"""
        if self._clean_cat is None:
            self._clean_cat = self.clean_terminal.split("_")[0]
        return self._clean_cat

    def has_t_base(self, s: str) -> bool:
        """Does the node have the given terminal base name?"""
        return self.cat == s

    def has_variant(self, s: str) -> bool:
        """Does the node have the given variant?"""
        return s in self.variants

    def _bin_filter(self, m: BIN_Tuple, case_override: Optional[str] = None) -> bool:
        """Return True if the BIN meaning in m matches the variants for this terminal"""
        if self.bin_cat is not None and m.ordfl not in self.bin_cat:
            return False
        if self.gender is not None:
            # Check gender match
            if self.inferred_cat == "pfn":
                # Personal pronouns don't have a gender in BÍN,
                # so don't disqualify on lack of gender
                pass
            elif self.inferred_cat == "no":
                if m.ordfl != self.gender:
                    return False
            elif self.gender.upper() not in m.beyging:
                return False
        if self.case is not None:
            # Check case match
            if case_override is not None:
                # Case override: we don't want other cases beside the given one
                for c in self._CASES:
                    if c != case_override:
                        if c.upper() in m.beyging:
                            return False
            elif self.case.upper() not in m.beyging:
                return False
        # Check number match
        if self.number is not None:
            if self.number.upper() not in m.beyging:
                return False

        if self.is_verb:
            # The following code is parallel to BIN_Token.verb_matches()
            for v in self.varlist:
                # Lookup variant to see if it is one of the required ones for verbs
                assert BIN_Token._VERB_FORMS is not None
                rq = BIN_Token._VERB_FORMS.get(v)
                if rq and rq not in m.beyging:
                    # If this is required variant that is not found in the form we have,
                    # return False
                    return False
            for v in ["sagnb", "lhþt", "bh"]:
                vv = BIN_Token.VARIANT[v]
                if vv and vv in m.beyging and v not in self.variants:
                    return False
            if "bh" in self.variants and "ST" in m.beyging:
                return False
            if self.varlist[0] not in "012":
                # No need for argument check: we're done, unless...
                if "lhþt" in self.variants:
                    # Special check for lhþt: may specify a case
                    # without it being an argument case
                    for c in BIN_Token.CASES:
                        if c in self.variants:
                            vv = BIN_Token.VARIANT[c]
                            if vv and vv not in m.beyging:
                                # The terminal specified a non-argument case
                                # but the token doesn't have it: no match
                                return False
            # We can't check the arguments here, but assume that is not necessary
            # to disambiguate between verbs
            return True

        # Check person (p1/p2/p3) match
        if self.person is not None:
            person = self.person.upper()
            person = person[1] + person[0]  # Turn p3 into 3P
            if person not in m.beyging:
                return False

        # Check VB/SB/MST for adjectives
        if "esb" in self.variants:
            if "ESB" not in m.beyging:
                return False
        if "evb" in self.variants:
            if "EVB" not in m.beyging:
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

        return True

    def stem(self, bindb: GreynirBin, word: str, at_start: bool = False) -> str:
        """Returns the stem of a word matching this terminal"""
        if self.is_literal or self.is_stem:
            # A literal or stem terminal only matches a word if it has the given stem
            w = self.cat[1:-1]
            return w.split(":")[0]
        if " " in word:
            # Multi-word phrase: we return it unchanged
            return word
        _, meanings = bindb.lookup_g(word, at_start)
        if meanings:
            for m in meanings:
                if self._bin_filter(m):
                    # Found a matching meaning: return the stem
                    return m.stofn
        # No meanings found in BÍN: return the word itself as its own stem
        return word


def _root_lookup(text: str, at_start: bool, terminal: str) -> str:
    """Look up the root of a word that isn't found in the cache"""
    mm: Optional[BIN_Tuple] = None
    with GreynirBin.get_db() as bin_db:
        w, m = bin_db.lookup_g(text, at_start)
    if m:
        # Find the meaning that matches the terminal
        td = TerminalNode._TD[terminal]
        mm = next((x for x in m if td._bin_filter(x)), None)
    if mm is not None:
        if mm.fl == "skst":
            # For abbreviations, return the original text as the
            # root (lemma), not the meaning of the abbreviation
            return text
        w = mm.stofn
    return w.replace("-", "")


class TerminalNode(Node):

    """A Node corresponding to a terminal"""

    # Undeclinable terminal categories
    _NOT_DECLINABLE = frozenset(
        ["ao", "eo", "spao", "fs", "st", "stt", "nhm", "uh", "töl"]
    )
    # Cache of terminal descriptors
    _TD: Dict[str, TerminalDescriptor] = dict()

    # Cache of word roots (stems) keyed by (word, at_start, terminal)
    _root_cache = LRU_Cache(_root_lookup, maxsize=16384)

    def __init__(
        self,
        terminal: str,
        augmented_terminal: str,
        token: str,
        tokentype: str,
        aux: str,
        at_start: bool,
    ) -> None:

        super().__init__()

        td = self._TD.get(terminal)
        if td is None:
            # Not found in cache: make a new one
            td = TerminalDescriptor(terminal)
            self._TD[terminal] = td
        self.td: TerminalDescriptor = td
        self.token = token
        self._text = token[1:-1]  # Cut off quotes
        self._at_start = at_start
        self.tokentype = tokentype
        self.is_word = tokentype in {"WORD", "PERSON"}
        self.is_literal = td.is_literal
        self.is_declinable = (not self.is_literal) and (
            td.inferred_cat not in self._NOT_DECLINABLE
        )
        self.augmented_terminal = augmented_terminal
        # Auxiliary information, originally from token.t2 (JSON string)
        self.aux = aux
        # Cached auxiliary information, as a Python object decoded from JSON
        self._aux: Optional[List[Any]] = None
        # Cache the root form of this word so that it is only looked up
        # once, even if multiple processors scan this tree
        self.root_cache: Optional[str] = None
        self.nominative_cache: Optional[str] = None
        self.indefinite_cache: Optional[str] = None
        self.canonical_cache: Optional[str] = None

    @property
    def text(self) -> str:
        return self._text

    @property
    def cat(self) -> str:
        return self.td.inferred_cat

    @property
    def at_start(self) -> bool:
        """Return True if the associated node spans the start of the sentence"""
        return self._at_start

    def has_t_base(self, s: str) -> bool:
        """Does the node have the given terminal base name?"""
        return self.td.has_t_base(s)

    def has_variant(self, s: str) -> bool:
        """Does the node have the given variant?"""
        return self.td.has_variant(s)

    def contained_text(self) -> str:
        """Return a string consisting of the literal text of all
        descendants of this node, in depth-first order"""
        return self.text

    @property
    def contained_number(self) -> Optional[float]:
        """Return a number from the associated token, if any"""
        if self.tokentype != "NUMBER":
            return None
        if self._aux is None:
            self._aux = json.loads(self.aux)
        assert self._aux is not None
        return self._aux[0]

    @property
    def contained_amount(self) -> Optional[Tuple[float, str]]:
        """Return an amount from the associated token, if any,
        as an (amount, currency ISO code) tuple"""
        if self.tokentype != "AMOUNT":
            return None
        if self._aux is None:
            self._aux = json.loads(self.aux)
        assert self._aux is not None
        return self._aux[0], self._aux[1]

    @property
    def contained_date(self) -> Optional[Tuple[int, int, int]]:
        """Return a date from the associated token, if any,
        as a (year, month, day) tuple"""
        if self.tokentype not in ("DATE", "DATEABS", "DATEREL"):
            return None
        if self._aux is None:
            self._aux = json.loads(self.aux)
        assert self._aux is not None
        return self._aux[0], self._aux[1], self._aux[2]

    @property
    def contained_year(self) -> Optional[int]:
        """Return a year from the associated token, if any,
        as an integer"""
        if self.tokentype != "YEAR":
            return None
        if self._aux is None:
            self._aux = json.loads(self.aux)
        return cast(int, self._aux)

    def _root(self, bin_db: GreynirBin) -> str:
        """Look up the root of the word associated with this terminal"""
        # Lookup the token in the BIN database
        if (not self.is_word) or self.is_literal:
            return self.text
        return self._root_cache(self.text, self._at_start, self.td.terminal)

    def _lazy_eval_root(
        self,
    ) -> Union[str, Tuple[Callable[[LookupSignature], str], LookupSignature]]:
        """Return a word root (stem) function object, with arguments, that can be
        used for lazy evaluation of word stems."""
        if (not self.is_word) or self.is_literal:
            return self.text
        return self._root_cache, (self.text, self._at_start, self.td.terminal)

    def lookup_alternative(
        self,
        bin_db: GreynirBin,
        replace_func: Callable[[str], str],
        sort_func: Optional[Callable[[BinMeaning], Union[str, int]]] = None,
    ) -> str:
        """Return a different (but always nominative case) word form, if available,
        by altering the beyging spec via the given replace_func function"""
        w, m = bin_db.lookup_g(self.text, self._at_start)
        if m:
            # Narrow the meanings down to those that are compatible with the terminal
            m = [x for x in m if self.td._bin_filter(x)]
        if m:
            # Look up the distinct roots of the word
            result: List[BinMeaning] = []
            for x in m:

                # Calculate a new 'beyging' string with the nominative case
                beyging = replace_func(x.beyging)

                if beyging is x.beyging:
                    # No replacement made: word form is identical in the nominative case
                    result.append(
                        make_bin_entry(
                            x.stofn, x.utg, x.ordfl, x.fl, x.ordmynd, x.beyging
                        )
                    )
                else:
                    # Lookup the same word (identified by 'utg') but a different declination
                    parts = x.ordmynd.split("-")
                    stofn = x.stofn.rsplit("-", maxsplit=1)[-1]
                    prefix = "".join(parts[0:-1]) if len(parts) > 1 else ""
                    # Go through all nominative forms of this word form until we
                    # find one that matches the meaning ('beyging') that we're
                    # looking for. It also must be the same word category and
                    # have the same lemma. Additionally, if this is not a composite
                    # word, the identifier ('utg') should match.
                    # Note: this call is cached
                    n = bin_db.lookup_raw_nominative(parts[-1])
                    r = [
                        nm
                        for nm in n
                        if nm.ord == stofn
                        and nm.ofl == x.ordfl
                        and (prefix != "" or nm.bin_id == x.utg)
                        and nm.mark == beyging
                    ]
                    if prefix:
                        # Add the word prefix again in front, if any
                        result += bin_db._prefix_meanings(
                            r, prefix, make_bin_entry, insert_hyphen=False
                        )
                    else:
                        result += r
            if result:
                if len(result) > 1 and sort_func is not None:
                    # Sort the result before choosing the matching meaning
                    result.sort(key=sort_func)
                # There can be more than one word form that matches our spec.
                # We can't choose between them so we simply return the first one.
                w = result[0].bmynd
        return w

    def _nominative(self, bin_db: GreynirBin) -> str:
        """Look up the nominative form of the word associated with this terminal"""
        # Lookup the token in the BIN database
        if (not self.is_word) or self.td.case_nf or not self.is_declinable:
            # Not a word, already nominative or not declinable: return it as-is
            return self.text
        if not self.text:
            assert False

        def replace_beyging(b: str, by_case: str = "NF") -> str:
            """Change a beyging string to specify a different case"""
            for case in ("NF", "ÞF", "ÞGF", "EF"):
                if case != by_case and case in b:
                    return b.replace(case, by_case)
            return b

        def sort_by_gr(m: BinMeaning) -> int:
            """Sort meanings having a definite article (greinir) after those that do not"""
            return 1 if "gr" in m.mark else 0

        # If this terminal doesn't have a 'gr' variant, prefer meanings in nominative
        # case that do not include 'gr'
        sort_func = None if self.has_variant("gr") else sort_by_gr

        # Lookup the same word stem but in the nominative case
        w = self.lookup_alternative(bin_db, replace_beyging, sort_func=sort_func)

        if self.text.isupper():
            # Original word was all upper case: convert result to upper case
            w = w.upper()
        elif self.text[0].isupper():
            # First letter was upper case: convert result accordingly
            w = w[0].upper() + w[1:]
        return w

    def _indefinite(self, bin_db: GreynirBin) -> str:
        """Look up the indefinite nominative form of a noun
        or adjective associated with this terminal"""
        # Lookup the token in the BIN database
        if (not self.is_word) or self.is_literal:
            # Not a word, not a noun or already indefinite: return it as-is
            return self.text
        cat = self.td.clean_cat
        if cat not in {"no", "lo"}:
            return self.text
        if self.td.case_nf and (
            (cat == "no" and not self.td.variant_gr)
            or (cat == "lo" and not self.td.variant_vb)
        ):
            # Already in nominative case, and indefinite in the case of a noun
            # or strong declination in the case of an adjective
            return self.text

        if not self.text:
            # print("self.text is empty, token is {0}, terminal is {1}".format(self.token, self.td.terminal))
            assert False

        def replace_beyging(b: str, by_case: str = "NF") -> str:
            """Change a beyging string to specify a different case,
            without the definitive article"""
            for case in ("NF", "ÞF", "ÞGF", "EF"):
                if case != by_case and case in b:
                    return (
                        b.replace(case, by_case).replace("gr", "").replace("VB", "SB")
                    )
            # No case found: shouldn't really happen, but whatever
            return b.replace("gr", "").replace("VB", "SB")

        # Lookup the same word stem but in the nominative case
        w = self.lookup_alternative(bin_db, replace_beyging)
        return w

    def _canonical(self, bin_db: GreynirBin) -> str:
        """Look up the singular indefinite nominative form of a noun
        or adjective associated with this terminal"""
        # Lookup the token in the BIN database
        if (not self.is_word) or self.is_literal:
            # Not a word, not a noun or already indefinite: return it as-is
            return self.text
        cat = self.td.clean_cat
        if cat not in {"no", "lo"}:
            return self.text
        if (
            self.td.case_nf
            and self.td.number == "et"
            and (
                (cat == "no" and not self.td.variant_gr)
                or (cat == "lo" and not self.td.variant_vb)
            )
        ):
            # Already singular, nominative, indefinite (if noun)
            return self.text

        if not self.text:
            # print("self.text is empty, token is {0}, terminal is {1}".format(self.token, self.terminal))
            assert False

        def replace_beyging(b: str, by_case: str = "NF") -> str:
            """Change a 'beyging' string to specify a different case,
            without the definitive article"""
            for case in ("NF", "ÞF", "ÞGF", "EF"):
                if case != by_case and case in b:
                    return (
                        b.replace(case, by_case)
                        .replace("FT", "ET")
                        .replace("gr", "")
                        .replace("VB", "SB")
                    )
            # No case found: shouldn't really happen, but whatever
            return b.replace("FT", "ET").replace("gr", "").replace("VB", "SB")

        # Lookup the same word stem but in the nominative case
        w = self.lookup_alternative(bin_db, replace_beyging)
        return w

    def root(self, state: TreeStateDict, params: ParamList) -> str:
        """Calculate the root form (stem) of this node's text"""
        if self.root_cache is None:
            # Not already cached: look up in database
            bin_db = state.get("bin_db")
            assert bin_db is not None
            self.root_cache = self._root(bin_db)
        return self.root_cache

    def nominative(self, state: TreeStateDict, params: ParamList) -> str:
        """Calculate the nominative form of this node's text"""
        if self.nominative_cache is None:
            # Not already cached: look up in database
            bin_db = state.get("bin_db")
            assert bin_db is not None
            self.nominative_cache = self._nominative(bin_db)
        return self.nominative_cache

    def indefinite(self, state: TreeStateDict, params: ParamList) -> str:
        """Calculate the nominative, indefinite form of this node's text"""
        if self.indefinite_cache is None:
            # Not already cached: look up in database
            bin_db = state.get("bin_db")
            assert bin_db is not None
            self.indefinite_cache = self._indefinite(bin_db)
        return self.indefinite_cache

    def canonical(self, state: TreeStateDict, params: ParamList) -> str:
        """Calculate the singular, nominative, indefinite form of this node's text"""
        if self.canonical_cache is None:
            # Not already cached: look up in database
            bin_db = state.get("bin_db")
            assert bin_db is not None
            self.canonical_cache = self._canonical(bin_db)
        return self.canonical_cache

    def string_self(self) -> str:
        return self.td.terminal + " <" + self.token + ">"

    def process(self, state: TreeStateDict, params: ParamList) -> Result:
        """Prepare a result object to be passed up to enclosing nonterminals"""
        assert not params  # A terminal node should not have parameters
        result = Result(self, state, [])  # No params
        result._terminal = self.td.terminal
        result._text = self.text
        result._token = self.token
        result._tokentype = self.tokentype
        return result

    def build_simple_tree(self, builder: Any) -> None:
        """Create a terminal node in a simple tree for this TerminalNode"""
        d: Dict[str, Any] = dict(x=self.text, k=self.tokentype)
        if self.tokentype != "PUNCTUATION":
            # Terminal
            d["t"] = t = self.td.clean_terminal
            a = self.augmented_terminal
            if a and a != t:
                # We have an augmented terminal and it's different from the
                # pure grammar terminal: store it
                d["a"] = a
            else:
                d["a"] = t
            if t[0] == '"' or t[0] == "'":
                pass
                # assert (
                #    False
                # ), "Wrong terminal: {0}, text is '{1}', token {2}, tokentype {3}".format(
                #    self.td.terminal, self.text, self.token, self.tokentype
                # )
            # Category
            d["c"] = self.cat
            if self.tokentype == "WORD":
                # Stem: Don't evaluate it right away, because we may never
                # need it, and the lookup is expensive. Instead, return a
                # tuple that will be used later to look up the stem if and
                # when needed.
                d["s"] = self._lazy_eval_root()
                # !!! f and b fields missing
        builder.push_terminal(d)


class PersonNode(TerminalNode):

    """Specialized TerminalNode for person terminals"""

    def __init__(
        self,
        terminal: str,
        augmented_terminal: str,
        token: str,
        tokentype: str,
        aux: str,
        at_start: bool,
    ):
        super().__init__(terminal, augmented_terminal, token, tokentype, aux, at_start)
        # Load the full names from the auxiliary JSON information
        gender = self.td.gender or None
        case = self.td.case or None
        # Aux contains a JSON-encoded list of tuples: (name, gender, case)
        self._aux = json.loads(aux) if aux else []
        assert self._aux is not None
        fn_list: List[Tuple[str, str, str]] = self._aux
        # Collect the potential full names that are available in nominative
        # case and match the gender of the terminal
        self.fullnames = [
            fn
            for fn, g, c in fn_list
            if (gender is None or g == gender) and (case is None or c == case)
        ]

    def _root(self, bin_db: GreynirBin) -> str:
        """Calculate the root (canonical) form of this person name"""
        # If we already have a full name coming from the tokenizer, use it
        # (full name meaning that it includes the patronym/matronym even
        # if it was not present in the original token)
        # Start by checking whether we already have a matching full name,
        # i.e. one in nominative case and with the correct gender
        if self.fullnames:
            # We may have more than one matching full name, but we have no means
            # of knowing which one is correct, so we simply return the first one
            return self.fullnames[0]
        if self.td.case is None:
            # We don't have any case information, so we assume that the
            # name is not inflectable
            return self.text
        gender = self.td.gender
        # assert self.td.case is not None
        if not self.td.case:
            case = "NF"
        else:
            case = self.td.case.upper()
        # Lookup the token in the BIN database
        # Look up each part of the name
        at_start = self._at_start
        name: List[str] = []
        for part in self.text.split(" "):
            w, m = bin_db.lookup_g(part, at_start)
            at_start = False
            if m:
                m = [
                    x
                    for x in m
                    if x.ordfl == gender and case in x.beyging and "ET" in x.beyging
                    # Do not accept 'Sigmund' as a valid stem for word forms that
                    # are identical with the stem 'Sigmundur'
                    # and (
                    #     x.stofn not in DisallowedNames.STEMS
                    #     or self.td.case not in DisallowedNames.STEMS[x.stofn]
                    # )
                ]
            if m:
                w = m[0].stofn
            name.append(w.replace("-", ""))
        return " ".join(name)

    def _nominative(self, bin_db: GreynirBin) -> str:
        """The nominative is identical to the root"""
        return self._root(bin_db)

    def _indefinite(self, bin_db: GreynirBin) -> str:
        """The indefinite is identical to the nominative"""
        return self._nominative(bin_db)

    def _canonical(self, bin_db: GreynirBin) -> str:
        """The canonical is identical to the nominative"""
        return self._nominative(bin_db)

    def build_simple_tree(self, builder: Any) -> None:
        """Create a terminal node in a simple tree for this PersonNode"""
        d = dict(x=self.text, k=self.tokentype)
        # Category = gender
        d["c"] = self.td.gender or self.td.cat
        # Stem
        d["s"] = self.root(builder.state, [])
        # Terminal
        d["t"] = self.td.terminal
        builder.push_terminal(d)


class NonterminalNode(Node):

    """A Node corresponding to a nonterminal"""

    def __init__(self, nonterminal: str) -> None:
        super().__init__()
        self.nt = nonterminal
        elems = nonterminal.split("_")
        # Calculate the base name of this nonterminal (without variants)
        self.nt_base = elems[0]
        self.variants = set(elems[1:])
        self.is_repeated = self.nt[-1] in _REPEAT_SUFFIXES

    def build_simple_tree(self, builder: Any) -> None:
        builder.push_nonterminal(self.nt_base)
        # This builds the child nodes
        super().build_simple_tree(builder)
        builder.pop_nonterminal()

    @property
    def text(self) -> str:
        """A nonterminal node has no text of its own"""
        return ""

    def contained_text(self) -> str:
        """Return a string consisting of the literal text of all
        descendants of this node, in depth-first order"""
        return " ".join(d.text for d in self.descendants() if d.text)

    def has_nt_base(self, s: str) -> bool:
        """Does the node have the given nonterminal base name?"""
        return self.nt_base == s

    def has_variant(self, s: str) -> bool:
        """Does the node have the given variant?"""
        return s in self.variants

    def string_self(self) -> str:
        return self.nt

    def root(self, state: TreeStateDict, params: ParamList) -> str:
        """The root form of a nonterminal is a sequence of the root
        forms of its children (parameters)"""
        return " ".join(p._root for p in params if p._root)

    def nominative(self, state: TreeStateDict, params: ParamList) -> str:
        """The nominative form of a nonterminal is a sequence of the
        nominative forms of its children (parameters)"""
        return " ".join(
            p._nominative for p in params if p._nominative
        )

    def indefinite(self, state: TreeStateDict, params: ParamList) -> str:
        """The indefinite form of a nonterminal is a sequence of the
        indefinite forms of its children (parameters)"""
        return " ".join(
            p._indefinite for p in params if p._indefinite
        )

    def canonical(self, state: TreeStateDict, params: ParamList) -> str:
        """The canonical form of a nonterminal is a sequence of the canonical
        forms of its children (parameters)"""
        return " ".join(p._canonical for p in params if p._canonical)

    def process(self, state: TreeStateDict, params: ParamList) -> Result:
        """Apply any requested processing to this node"""
        result = Result(self, state, params)
        result._nonterminal = self.nt
        # Calculate the combined text rep of the results of the children
        result._text = " ".join(p._text for p in params if p._text)
        for p in params:
            # Copy all user variables (attributes not starting with an underscore _)
            # coming from the children into the result
            result.copy_from(p)
        # Invoke a function for this nonterminal, if present
        # in the given processor/processing environment
        # (the current module + the shared utility functions).
        # The check for 'Query' catches a corner case where the
        # processor may have imported the Query class, so it is
        # available as an attribute, but it should not be called!
        if params and not self.is_repeated and self.nt_base != "Query":
            # Don't invoke if this is an epsilon nonterminal (i.e. has no children),
            # or if this is a repetition parent (X?, X* or X+)
            processor = state["processor"]
            func = cast(
                Optional[NonterminalFunction],
                processor.get(self.nt_base, state.get("_default")),
            )
            if func is not None:
                try:
                    func(self, params, result)
                except TypeError as ex:
                    print(
                        "Attempt to call {0}() in processor raised exception {1}".format(
                            func.__qualname__, ex
                        )
                    )
                    raise
        return result


class TreeBase:

    """A tree corresponding to a single parsed article"""

    # A map of terminal types to node constructors
    _TC = {"person": PersonNode}

    def __init__(self) -> None:
        self.s: Dict[int, Optional[Node]] = dict()  # Sentence dictionary
        self.scores: Dict[int, int] = dict()  # Sentence scores
        self.lengths: Dict[int, int] = dict()  # Sentence lengths, in tokens
        self.stack: Optional[List[Node]] = None
        self.n: Optional[int] = None  # Index of current sentence
        self.at_start = False  # First token of sentence?

    def __getitem__(self, n: int) -> Optional[Node]:
        """Allow indexing to get sentence roots from the tree"""
        return self.s[n]

    def __contains__(self, n: int) -> bool:
        """Allow query of sentence indices"""
        return n in self.s

    def sentences(self) -> Iterator[Tuple[int, Optional[Node]]]:
        """Enumerate the sentences in this tree"""
        for ix, sent in self.s.items():
            yield ix, sent

    def score(self, n: int) -> int:
        """Return the score of the sentence with index n, or 0 if unknown"""
        return self.scores.get(n, 0)

    def length(self, n: int) -> int:
        """Return the length of the sentence with index n, in tokens, or 0 if unknown"""
        return self.lengths.get(n, 0)

    def simple_trees(
        self,
        nt_map: Optional[NonterminalMap] = None,
        id_map: Optional[IdMap] = None,
        terminal_map: Optional[Mapping[str, str]] = None,
    ) -> Iterator[Tuple[int, SimpleTree]]:
        """Generate simple trees out of the sentences in this tree"""
        # Hack to allow nodes to access the BIN database
        with GreynirBin.get_db() as bin_db:
            state = dict(bin_db=bin_db)
            for ix, sent in self.s.items():
                if sent is not None:
                    builder = SimpleTreeBuilder(nt_map, id_map, terminal_map)
                    builder.state = state
                    sent.build_simple_tree(builder)
                    yield ix, builder.tree

    def push(self, n: int, node: Node) -> None:
        """Add a node into the tree at the right level"""
        assert self.stack is not None
        if n == len(self.stack):
            # First child of parent
            if n:
                parent = self.stack[n - 1]
                parent.set_child(node)
            self.stack.append(node)
        else:
            assert n < len(self.stack)
            # Next child of parent
            parent = self.stack[n]
            parent.set_next(node)
            self.stack[n] = node
            if n + 1 < len(self.stack):
                self.stack = self.stack[0 : n + 1]

    def handle_R(self, n: int) -> None:
        """Greynir version info"""
        pass

    def handle_C(self, n: int) -> None:
        """Sentence score"""
        assert self.n is not None
        assert self.n not in self.scores
        self.scores[self.n] = n

    def handle_L(self, n: int) -> None:
        """Sentence length"""
        assert self.n is not None
        assert self.n not in self.lengths
        self.lengths[self.n] = n

    def handle_S(self, n: int) -> None:
        """Start of sentence"""
        self.n = n
        self.stack = []
        self.at_start = True

    def handle_Q(self, n: int) -> None:
        """End of sentence"""
        # Store the root of the sentence tree at the appropriate index
        # in the dictionary
        assert self.n is not None
        assert self.n not in self.s
        assert self.stack is not None
        self.s[self.n] = self.stack[0]
        self.stack = None
        self.n = None

    def handle_E(self, n: int) -> None:
        """End of sentence with error"""
        # Nothing stored
        assert self.n not in self.s
        self.stack = None
        self.n = None

    def handle_P(self, n: int) -> None:
        """Epsilon node: leave the parent nonterminal childless"""
        pass

    @staticmethod
    def _parse_T(s: str) -> TreeToken:
        """Parse a T (Terminal) descriptor"""
        # The string s contains:
        # terminal "token" [TOKENTYPE] [auxiliary-json]

        # The terminal may itself be a single- or double-quoted string,
        # in which case it may contain underscores, colons and other
        # punctuation. It can then be followed by variant names,
        # separated by underscores. The \w regexp pattern matches
        # alpabetic characters as well as digits and underscores.
        if s[0] == "'":
            r = re.match(r"\'[^\']*\'\w*", s)
            terminal = r.group() if r else ""
            s = s[r.end() + 1 :] if r else ""
        elif s[0] == '"':
            r = re.match(r"\"[^\"]*\"\w*", s)
            terminal = r.group() if r else ""
            s = s[r.end() + 1 :] if r else ""
        else:
            a = s.split(" ", maxsplit=1)
            terminal = a[0]
            s = a[1]
        # Retrieve token text
        r = re.match(r"\"[^\"]*\"", s)
        if r is None:
            # Compatibility: older versions used single quotes around token text
            r = re.match(r"\'[^\']*\'", s)
        token = r.group() if r else ""
        s = s[r.end() + 1 :] if r else ""
        augmented_terminal = terminal
        if s:
            a = s.split(" ", maxsplit=1)
            tokentype = a[0]
            if tokentype and tokentype[0].islower():
                # The following string is actually an augmented terminal,
                # corresponding to a word token
                augmented_terminal = tokentype
                tokentype = "WORD"
                aux = ""
            else:
                aux = a[1] if len(a) > 1 else ""  # Auxiliary info (originally token.t2)
        else:
            # Default token type
            tokentype = "WORD"
            aux = ""
        # The 'cat' extracted here is actually the first part of the terminal
        # name, which is not the word category in all cases (for instance not
        # for literal terminals).
        cat = terminal.split("_", maxsplit=1)[0]
        return TreeToken(terminal, augmented_terminal, token, tokentype, aux, cat)

    def handle_T(self, n: int, s: str) -> None:
        """Terminal"""
        terminal, augmented_terminal, token, tokentype, aux, cat = self._parse_T(s)
        constructor = self._TC.get(cat, TerminalNode)
        self.push(
            n,
            constructor(
                terminal, augmented_terminal, token, tokentype, aux, self.at_start
            ),
        )
        self.at_start = False

    def handle_N(self, n: int, nonterminal: str) -> None:
        """Nonterminal"""
        self.push(n, NonterminalNode(nonterminal))

    def load(self, txt: str) -> None:
        """Loads a tree from the text format stored by the scraper"""
        for line in txt.split("\n"):
            if not line:
                continue
            a = line.split(" ", maxsplit=1)
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
                assert False, "*** No handler for {0}".format(line)


class Tree(TreeBase):

    """A processable tree corresponding to a single parsed article"""

    def __init__(self, url: str = "", authority: float = 1.0) -> None:
        super().__init__()
        self.url = url
        self.authority = authority

    def visit_children(self, state: TreeStateDict, node: Node) -> Optional[Result]:
        """Visit the children of node, obtain results from them and pass them to the node"""
        # First check whether the processor has a visit() method
        visit = state.get("_visit")
        if visit is not None and not visit(state, node):
            # Call the visit() method and if it returns False,
            # we do not visit this node or its children
            return None
        p: ParamList = []
        for child in node.children():
            pc = self.visit_children(state, child)
            if pc is not None:
                p.append(pc)
        return node.process(state, p)

    def process_sentence(self, state: TreeStateDict, tree: Node) -> None:
        """Process a single sentence tree"""
        result = self.visit_children(state, tree)
        # Sentence processing completed:
        # Invoke a function called 'sentence(state, result)',
        # if present in the processor
        sentence = state.get("_sentence")
        if sentence is not None:
            sentence(state, result)

    def process_trees(self, state: TreeStateDict) -> None:
        """Overridable inner loop for processing the sentence trees in an article"""
        # For each sentence in turn, do a depth-first traversal,
        # visiting each parent node after visiting its children
        for index, tree in self.s.items():
            if tree is not None:
                state["index"] = index
                self.process_sentence(state, tree)

    @contextmanager
    def context(
        self, session: Session, processor: Union[ProcEnv, ModuleType], **kwargs: Any
    ) -> Iterator[TreeStateDict]:
        """Context manager for tree processing, setting up the environment
        and encapsulating the sentence tree processing"""

        if isinstance(processor, ModuleType):
            processor = cast(ProcEnv, vars(processor))

        # Obtain the processor's handler functions
        article_begin = processor.get("article_begin", None)
        article_end = processor.get("article_end", None)
        sentence = cast(Optional[SentenceFunction], processor.get("sentence", None))
        # If visit(state, node) returns False for a node, do not visit child nodes
        visit = cast(Optional[VisitFunction], processor.get("visit", None))
        # If no handler exists for a nonterminal, call default() instead
        default = cast(Optional[NonterminalFunction], processor.get("default", None))

        with GreynirBin.get_db() as bin_db:

            state: TreeStateDict = {
                "session": session,
                "processor": processor,
                "bin_db": bin_db,
                "url": self.url,
                "authority": self.authority,
                "index": 0,
                "_sentence": sentence,
                "_visit": visit,
                "_default": default,
            }
            # Add state parameters passed via keyword arguments, if any
            state.update(cast(TreeStateDict, kwargs))

            # Call the article_begin(state) function, if it exists
            if article_begin is not None:
                article_begin(state)

            # Now that the context environment has been set up, invoke the
            # sentence handler(s), i.e. the body of the enclosing with statement
            yield state

            # Call the article_end(state) function, if it exists
            if article_end is not None:
                article_end(state)

    def process(
        self, session: Session, processor: Union[ProcEnv, ModuleType], **kwargs: Any
    ) -> None:
        with self.context(session, processor, **kwargs) as state:
            self.process_trees(state)


class TreeGist(TreeBase):

    """A gist of a tree corresponding to a single parsed article.
    A gist simply knows which sentences are present in the tree
    and what the error token index is for sentences that are not present."""

    def __init__(self) -> None:
        super().__init__()
        # Dictionary of error token indices for sentences that weren't successfully parsed
        self._err_index: Dict[int, int] = dict()

    def err_index(self, n: int) -> Optional[int]:
        """Return the error token index for an unparsed sentence, if any, or None"""
        return self._err_index.get(n)

    def push(self, n: int, node: Node) -> None:
        """This should not be invoked for a gist"""
        assert False

    def handle_Q(self, n: int) -> None:
        """End of sentence"""
        # Simply note that the sentence is present without storing it
        assert self.n is not None
        assert self.n not in self.s
        self.s[self.n] = None
        self.stack = None
        self.n = None

    def handle_E(self, n: int) -> None:
        """End of sentence with error"""
        super().handle_E(n)
        assert self.n is not None
        self._err_index[self.n] = n  # Note the index of the error token

    def handle_T(self, n: int, s: str) -> None:
        """Terminal"""
        # No need to store anything for gists
        pass

    def handle_N(self, n: int, nonterminal: str) -> None:
        """Nonterminal"""
        # No need to store anything for gists
        pass


class TreeTokenList(TreeBase):

    """A tree that allows easy iteration of its token/terminal matches"""

    def __init__(self) -> None:
        super().__init__()
        self.result: Dict[int, List[TreeToken]] = dict()

    def handle_Q(self, n: int) -> None:
        """End of sentence"""
        assert self.n is not None
        assert self.n not in self.result
        if self.stack:
            self.result[self.n] = cast(List[TreeToken], self.stack)
        self.stack = None
        self.n = None

    def handle_T(self, n: int, s: str) -> None:
        """Terminal"""
        t = self._parse_T(s)
        # Append to token list for current sentence
        assert self.stack is not None
        cast(List[TreeToken], self.stack).append(TreeToken(*t))

    def handle_N(self, n: int, nonterminal: str) -> None:
        """Nonterminal"""
        # No action required for token lists
        pass

    def token_lists(self) -> Iterator[Tuple[int, List[TreeToken]]]:
        """Enumerate the resulting token lists"""
        yield from self.result.items()
