"""

    Reynir: Natural language processing for Icelandic

    Python wrapper for C++ Earley/Scott parser

    Copyright (C) 2016 Vilhjálmur Þorsteinsson

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


    This module wraps an Earley-Scott parser written in C++ to transform token
    sequences (sentences) into forests of parse trees, with each tree representing a
    possible parse of a sentence, according to a given context-free grammar.

    An Earley parser handles all valid context-free grammars,
    irrespective of ambiguity, recursion (left/middle/right), nullability, etc.
    The returned parse trees reflect the original grammar, which does not
    need to be normalized or modified in any way. All partial parses are
    available in the final parse state table.

    For further information see J. Earley, "An efficient context-free parsing algorithm",
    Communications of the Association for Computing Machinery, 13:2:94-102, 1970.

    The Earley parser used here is the improved version described by Scott & Johnstone,
    referencing Tomita. This allows worst-case cubic (O(n^3)) order, where n is the
    length of the input sentence, while still returning all possible parse trees
    for an ambiguous grammar.

    See Elizabeth Scott, Adrian Johnstone:
    "Recognition is not parsing — SPPF-style parsing from cubic recognisers"
    Science of Computer Programming, Volume 75, Issues 1–2, 1 January 2010, Pages 55–70

    The C++ source code is found in eparser.h and eparser.cpp.

    This wrapper uses the CFFI module (http://cffi.readthedocs.org/en/latest/)
    to call C++ code from CPython and PyPy.

"""


import os
from threading import Lock

from cffi import FFI

from binparser import BIN_Parser
from grammar import GrammarError
from settings import Settings
from glock import GlobalLock

ffi = FFI()

# Describe the C++ data structures and interface functions to the CFFI bridge

declarations = """

    typedef unsigned int UINT;
    typedef int INT;
    typedef int BOOL; // Different from C++
    typedef char CHAR;
    typedef unsigned char BYTE;

    struct Grammar {
        UINT nNonterminals;   // Number of nonterminals
        UINT nTerminals;      // Number of terminals (indexed from 1)
        INT iRoot;            // Index of root nonterminal (negative)
    };

    struct Parser {
        struct Grammar* pGrammar;
    };

    struct Production {
        UINT nId;
        UINT nPriority;
        UINT n;
        INT* pList;
    };

    struct Label {
        INT iNt;
        UINT nDot;
        struct Production* pProd;
        UINT nI;
        UINT nJ;
    };

    struct FamilyEntry {
        struct Production* pProd;
        struct Node* p1;
        struct Node* p2;
        struct FamilyEntry* pNext;
    };

    struct Node {
        struct Label label;
        struct FamilyEntry* pHead;
        UINT nRefCount;
    } Node;

    typedef BOOL (*MatchingFunc)(UINT nHandle, UINT nToken, UINT nTerminal);
    typedef BYTE* (*AllocFunc)(UINT nHandle, UINT nToken, UINT nSize);

    struct Node* earleyParse(struct Parser*, UINT nTokens, INT iRoot, UINT nHandle, UINT* pnErrorToken);
    struct Grammar* newGrammar(const CHAR* pszGrammarFile);
    void deleteGrammar(struct Grammar*);
    struct Parser* newParser(struct Grammar*, MatchingFunc fpMatcher, AllocFunc fpAlloc);
    void deleteParser(struct Parser*);
    void deleteForest(struct Node*);
    void dumpForest(struct Node*, struct Grammar*);
    UINT numCombinations(struct Node*);

    void printAllocationReport(void);

"""

ffi.cdef(declarations)


class ParseJob:

    """ Dispatch token matching requests coming in from the C++ code """

    # Parse jobs have rotating integer IDs, reaching _MAX_JOBS before cycling back
    _MAX_JOBS = 10000
    _seq = 0
    _jobs = dict()
    _lock = Lock()

    def __init__(self, handle, grammar, tokens, terminals, matching_cache):
        self._handle = handle
        self.tokens = tokens
        self.terminals = terminals
        self.grammar = grammar
        self.c_dict = dict() # Node pointer conversion dictionary
        self.matching_cache = matching_cache # Token/terminal matching buffers

    def matches(self, token, terminal):
        """ Convert the token reference from a 0-based token index
            to the token object itself; convert the terminal from a
            1-based terminal index to a terminal object. """
        return self.tokens[token].matches(self.terminals[terminal])

    def alloc_cache(self, token, size):
        """ Allocate a token/terminal matching cache buffer for the given token """
        key = self.tokens[token].key # Obtain the (hashable) key of the BIN_Token
        try:
            # Do we already have a token/terminal cache match buffer for this key?
            b = self.matching_cache.get(key)
            if b is None:
                # No: create a fresh one (assumed to be initialized to zero)
                b = self.matching_cache[key] = ffi.new("BYTE[]", size)
        except TypeError:
            print("alloc_cache() unable to hash key: {0}".format(repr(key)))
            b = ffi.NULL
        return b

    @property
    def handle(self):
        return self._handle

    def __enter__(self):
        """ Python context manager protocol """
        return self

    # noinspection PyUnusedLocal
    def __exit__(self, exc_type, exc_value, traceback):
        """ Python context manager protocol """
        self.__class__.delete(self._handle)
        # Return False to re-throw exception from the context, if any
        return False

    @classmethod
    def make(cls, grammar, tokens, terminals, matching_cache):
        """ Create a new parse job with for a given token sequence and set of terminals """
        with cls._lock:
            h = cls._seq
            cls._seq += 1
            if cls._seq >= cls._MAX_JOBS:
                cls._seq = 0
            j = cls._jobs[h] = ParseJob(h, grammar, tokens, terminals, matching_cache)
        return j

    @classmethod
    def delete(cls, handle):
        """ Delete a no-longer-used parse job """
        with cls._lock:
            del cls._jobs[handle]

    @classmethod
    def dispatch(cls, handle, token, terminal):
        """ Dispatch a match request to the correct parse job """
        return cls._jobs[handle].matches(token, terminal)

    @classmethod
    def alloc(cls, handle, token, size):
        """ Dispatch a cache buffer allocation request to the correct parse job """
        return cls._jobs[handle].alloc_cache(token, size)


# CFFI callback functions

@ffi.callback("BOOL(UINT, UINT, UINT)")
def matching_func(handle, token, terminal):
    """ This function is called from the C++ parser to determine
        whether a token matches a terminal. The token is referenced
        by 0-based index, and the terminal by a 1-based index.
        The handle is an arbitrary UINT that was passed to
        earleyParse(). In this case, it is used to identify
        a ParseJob object that dispatches the match query. """
    return ParseJob.dispatch(handle, token, terminal)

@ffi.callback("BYTE*(UINT, UINT, UINT)")
def alloc_func(handle, token, size):
    """ Allocate a token/terminal matching cache buffer, at least size bytes.
        If the callback returns ffi.NULL, the parser will allocate its own buffer.
        The point of this callback is to allow re-using buffers for identical tokens,
        so we avoid making unnecessary matching calls. """
    return ParseJob.alloc(handle, token, size)


class Node:

    """ Shared Packed Parse Forest (SPPF) node representation.

        A node label is a tuple (s, j, i) where s can be
        (a) an index < 0 of a nonterminal, for completed productions;
        (b) an index >= 0 of a token corresponding to a terminal;
        (c) a (nonterminal index, dot, prod) tuple, for partially parsed productions.

        j and i are the start and end token indices, respectively.

        A forest of Nodes can be navigated using a subclass of
        ParseForestNavigator.

    """

    def __init__(self):
        self._hash = id(self).__hash__()

    @classmethod
    def from_c_node(cls, job, c_node, parent = None, index = 0):
        """ Initialize a Python SPPF node from a C++ node structure """
        node = cls()
        lb = c_node.label
        node._start = lb.nI
        node._end = lb.nJ
        node._families = None # Families of children
        if lb.iNt < 0:
            # Nonterminal node, completed or not
            node._nonterminal = job.grammar.lookup(lb.iNt)
            node._completed = (lb.pProd == ffi.NULL) or lb.nDot >= lb.pProd.n
            node._terminal = None
            node._token = None
            job.c_dict[c_node] = node # Re-use nonterminal nodes if identical
        else:
            # Token node: find the corresponding terminal
            #assert parent is not None
            #assert parent != ffi.NULL
            tix = parent.pList[index + parent.n] if index < 0 else parent.pList[index]
            node._terminal = job.grammar.lookup(tix)
            node._token = job.tokens[lb.iNt]
            node._nonterminal = None
            node._completed = True
        fe = c_node.pHead
        while fe != ffi.NULL:
            child_ix = -1 if node._completed else index
            node._add_family(job, fe.pProd, fe.p1, fe.p2, child_ix)
            fe = fe.pNext
        return node

    @classmethod
    def copy(cls, other):
        """ Returns a copy of a Node instance """
        node = cls()
        node._start = other._start
        node._end = other._end
        node._nonterminal = other._nonterminal
        node._terminal = other._terminal
        node._token = other._token
        node._completed = other._completed
        if other._families is None:
            node._families = None
        else:
            # Create a new list object having the
            # same child nodes as the source node
            node._families = other._families[:] # [ pc for pc in other._families ]
        return node

    def _add_family(self, job, prod, ch1, ch2, child_ix):
        """ Add a family of children to this node, in parallel with other families """
        if ch1 != ffi.NULL and ch2 != ffi.NULL:
            child_ix -= 1
        if ch1 == ffi.NULL:
            n1 = None
        else:
            n1 = job.c_dict.get(ch1) or Node.from_c_node(job, ch1, prod, child_ix)
        if n1 is not None:
            child_ix += 1
        if ch2 == ffi.NULL:
            n2 = None
        else:
            n2 = job.c_dict.get(ch2) or Node.from_c_node(job, ch2, prod, child_ix)
        if n1 is not None and n2 is not None:
            children = (n1, n2)
        elif n2 is not None:
            children = n2
        else:
            # n1 may be None if this is an epsilon node
            children = n1
        # Recreate the pc tuple from the production index
        pc = (job.grammar.productions_by_ix[prod.nId], children)
        if self._families is None:
            self._families = [ pc ]
            return
        self._families.append(pc)

    def transform_children(self, func):
        """ Apply a given function to the children of this node,
            replacing the children with the result.
            Calls func(child, ix, offset) where child is the
            original child node, ix is the family, and offset
            is the tuple index (0 or 1) """
        if not self._families:
            return
        for ix, pc in enumerate(self._families):
            prod, f = pc
            if f is None:
                continue
            if isinstance(f, tuple):
                f = (func(f[0], ix, 0), func(f[1], ix, 1))
            else:
                f = func(f, ix, 0)
            self._families[ix] = (prod, f)

    @property
    def start(self):
        """ Return the start token index """
        return self._start

    @property
    def end(self):
        """ Return the end token index """
        return self._end

    @property
    def nonterminal(self):
        """ Return the nonterminal associated with this node """
        return self._nonterminal

    @property
    def is_ambiguous(self):
        """ Return True if this node has more than one family of children """
        return self._families is not None and len(self._families) >= 2

    @property
    def is_interior(self):
        """ Returns True if this is an interior node (partially parsed production) """
        return not self._completed

    @property
    def is_completed(self):
        """ Returns True if this is a node corresponding to a completed nonterminal """
        return self._completed

    @property
    def is_token(self):
        """ Returns True if this is a token node """
        return self._token is not None

    @property
    def terminal(self):
        """ Return the terminal associated with a token node, or None if none """
        return self._terminal
    
    @property
    def token(self):
        """ Return the terminal associated with a token node, or None if none """
        return self._token
    
    @property
    def has_children(self):
        """ Return True if there are any families of children of this node """
        return bool(self._families)

    @property
    def is_empty(self):
        """ Return True if there is only a single empty family of this node """
        if not self._families:
            return True
        return len(self._families) == 1 and self._families[0][1] is None

    @property
    def num_families(self):
        return len(self._families) if self._families is not None else 0

    def enum_children(self):
        """ Enumerate families of children """
        if self._families:
            for prod, children in self._families:
                yield (prod, children)

    def reduce_to(self, child_ix):
        """ Eliminate all child families except the given one """
        #if not self._families or child_ix >= len(self._families):
        #    raise IndexError("Child index out of range")
        f = self._families[child_ix] # The survivor
        # Collapse the list to one option
        self._families = [ f ]

    def __hash__(self):
        """ Make this node hashable """
        return self._hash

    def __repr__(self):
        """ Create a reasonably nice text representation of this node
            and its families of children, if any """
        label_rep = repr(self._nonterminal or self._token)
        families_rep = ""
        if self._families:
            if len(self._families) == 1:
                families_rep = self._families[0].__repr__()
            else:
                families_rep = "<" + self._families.__repr__() + ">"
        return label_rep + ((": " + families_rep + "\n") if families_rep else "")

    def __str__(self):
        """ Return a string representation of this node """
        return str(self._nonterminal or self._token)


class ParseForestNavigator:

    """ Base class for navigating parse forests. Override the underscored
        methods to perform actions at the corresponding points of navigation. """

    def __init__(self, visit_all = False):
        """ If visit_all is False, we only visit each packed node once.
            If True, we visit the entire tree in order. """
        self._visit_all = visit_all

    def _visit_epsilon(self, level):
        """ At Epsilon node """
        return None

    def _visit_token(self, level, node):
        """ At token node """
        return None

    def _visit_nonterminal(self, level, node):
        """ At nonterminal node """
        # Return object to collect results
        return None

    def _visit_family(self, results, level, node, ix, prod):
        """ At a family of children """
        return

    def _add_result(self, results, ix, r):
        """ Append a single result object r to the result object """
        return

    def _process_results(self, results, node):
        """ Process results after visiting children.
            The results list typically contains tuples (ix, r) where ix is
            the family index and r is the child result """
        return None

    def _force_visit(self, w, visited):
        """ Override this and return True to visit a node, even if self._visit_all
            is False and the node has been visited before """
        return False

    def go(self, root_node):
        """ Navigate the forest from the root node """

        visited = dict()

        def _nav_helper(w, index, level):
            """ Navigate from w """
            if not self._visit_all and w in visited and not self._force_visit(w, visited):
                # Already seen: return the previously calculated result
                return visited[w]
            if w is None:
                # Epsilon node
                v = self._visit_epsilon(level)
            elif w.is_token:
                # Return the score of this terminal option
                v = self._visit_token(level, w)
            else:
                # Init container for child results
                results = self._visit_nonterminal(level, w)
                if results is NotImplemented:
                    # If _visit_nonterminal() returns NotImplemented,
                    # don't bother visiting children or processing
                    # results; instead _nav_helper() returns NotImplemented
                    v = results
                else:
                    if w.is_interior:
                        child_level = level
                    else:
                        child_level = level + 1
                    if w.is_ambiguous:
                        child_level += 1
                    for ix, pc in enumerate(w._families):
                        prod, f = pc
                        self._visit_family(results, level, w, ix, prod)
                        if w.is_completed:
                            # Completed nonterminal: restart children index
                            child_ix = -1
                        else:
                            child_ix = index
                        if isinstance(f, tuple):
                            self._add_result(results, ix,
                                _nav_helper(f[0], child_ix - 1, child_level))
                            self._add_result(results, ix,
                                _nav_helper(f[1], child_ix, child_level))
                        else:
                            self._add_result(results, ix,
                                _nav_helper(f, child_ix, child_level))
                    v = self._process_results(results, w)
            if not self._visit_all:
                # Mark the node as visited and store its result
                visited[w] = v
            return v

        return _nav_helper(root_node, 0, 0)


class ParseError(Exception):

    """ Exception class for parser errors """

    def __init__(self, txt, token_index = None, info = None):
        """ Store an information object with the exception,
            containing the parser state immediately before the error """
        Exception.__init__(self, txt)
        self._info = info
        self._token_index = token_index

    @property
    def info(self):
        """ Return the parser state information object """
        return self._info

    @property
    def token_index(self):
        """ Return the 0-based index of the token where the parser ran out of options """
        return self._token_index


class Fast_Parser(BIN_Parser):

    """ This class wraps an Earley-Scott parser written in C++.
        It is called via CFFI.
        The class supports the context manager protocol so you can say:

        with Fast_Parser() as fast_p:
           node = fast_p.go(...)

        C++ objects associated with the parser will then be cleaned
        up automatically upon exit of the context, whether by normal
        means or as a consequence of an exception.

        Otherwise, i.e. if not using a context manager, call fast_p.cleanup()
        after using the fast_p parser instance, preferably in a try/finally block.
    """

    # Dynamically load the C++ shared library
    eparser = ffi.dlopen("./libeparser.so")
    assert eparser is not None

    GRAMMAR_BINARY_FILE = "Reynir.grammar.bin"
    GRAMMAR_BINARY_FILE_BYTES = GRAMMAR_BINARY_FILE.encode('ascii')

    _c_grammar = None
    _c_grammar_ts = None

    @classmethod
    def _load_binary_grammar(cls):
        """ Load the binary grammar file into memory, if required """
        fname = cls.GRAMMAR_BINARY_FILE_BYTES
        try:
            ts = os.path.getmtime(fname)
        except os.error:
            raise GrammarError("Binary grammar file {0} not found"
                .format(cls.GRAMMAR_BINARY_FILE))
        if cls._c_grammar is None or cls._c_grammar_ts != ts:
            # Need to load or reload the grammar
            ep = cls.eparser
            if cls._c_grammar is not None:
                # Delete previous grammar instance, if any
                ep.deleteGrammar(cls._c_grammar)
                cls._c_grammar = None
            cls._c_grammar = ep.newGrammar(fname)
            cls._c_grammar_ts = ts
            if cls._c_grammar is None or cls._c_grammar == ffi.NULL:
                raise GrammarError("Unable to load binary grammar file " +
                    cls.GRAMMAR_BINARY_FILE)
        return cls._c_grammar

    def __init__(self, verbose = False, root = None):

        # Only one initialization at a time, since we don't want a race
        # condition between threads with regards to reading and parsing the grammar file
        # vs. writing the binary grammar
        with GlobalLock('grammar'):
            super().__init__(verbose) # Reads and parses the grammar text file
            # Create instances of the C++ Grammar and Parser classes
            c_grammar = Fast_Parser._load_binary_grammar()
            # Create a C++ parser object for the grammar
            self._c_parser = Fast_Parser.eparser.newParser(c_grammar, matching_func, alloc_func)
            # Find the index of the root nonterminal for this parser instance
            self._root_index = 0 if root is None else self.grammar.nonterminals[root].index
            # Maintain a token/terminal matching cache for the duration
            # of this parser instance. Note that this cache will grow with use,
            # as it includes an entry (about 2K bytes) for every distinct token that the parser
            # encounters.
            self._matching_cache = dict()

    def __enter__(self):
        """ Python context manager protocol """
        return self

    # noinspection PyUnusedLocal
    def __exit__(self, exc_type, exc_value, traceback):
        """ Python context manager protocol """
        self.cleanup()
        return False

    def go(self, tokens):
        """ Call the C++ parser module to parse the tokens """

        wrapped_tokens = self._wrap(tokens) # Inherited from BIN_Parser
        lw = len(wrapped_tokens)
        ep = Fast_Parser.eparser
        err = ffi.new("unsigned int*")

        # Use the context manager protocol to guarantee that the parse job
        # handle will be properly deleted even if an exception is thrown

        with ParseJob.make(self.grammar, wrapped_tokens, self._terminals, self._matching_cache) as job:

            node = ep.earleyParse(self._c_parser, lw, self._root_index, job.handle, err)

            if node == ffi.NULL:
                ix = err[0] # Token index
                if ix >= 1:
                    # Find the error token index in the original (unwrapped) token list
                    orig_ix = wrapped_tokens[ix].index if ix < lw else ix
                    raise ParseError("No parse available at token {0} ({1})"
                        .format(orig_ix, wrapped_tokens[ix-1]), orig_ix - 1)
                else:
                    # Not a normal parse error, but report it anyway
                    raise ParseError("No parse available at token {0} ({1} tokens in input)"
                        .format(ix, len(wrapped_tokens)), 0)

            # Create a new Python-side node forest corresponding to the C++ one
            result = Node.from_c_node(job, node)

        # Delete the C++ nodes
        ep.deleteForest(node)
        return result

    def go_no_exc(self, tokens):
        """ Simple version of go() that returns None instead of throwing ParseError """
        try:
            return self.go(tokens)
        except ParseError:
            return None

    def cleanup(self):
        """ Delete C++ objects. Must call after last use of Fast_Parser
            to avoid memory leaks. The context manager protocol is recommended
            to guarantee cleanup. """
        ep = Fast_Parser.eparser
        ep.deleteParser(self._c_parser)
        self._c_parser = None
        if Settings.DEBUG:
            ep.printAllocationReport()

    @classmethod
    def num_combinations(cls, w):
        """ Count the number of possible parse tree combinations in the given forest """

        nc = dict()

        def _num_comb(w):
            if w is None or w.is_token:
                # Empty (epsilon) node or token node
                return 1
            # If a subtree has already been counted, re-use that count
            # (this is less efficient for small trees but much more efficient
            # for extremely ambiguous trees, with combinations in the
            # hundreds of billions)
            if w in nc:
                if nc[w] is None:
                    print("Loop in node tree at {0}".format(str(w)))
                    assert False
                return nc[w]
            nc[w] = None
            comb = 0
            for _, f in w.enum_children():
                if isinstance(f, tuple):
                    comb += _num_comb(f[0]) * _num_comb(f[1])
                else:
                    comb += _num_comb(f)
            result = nc[w] = comb if comb > 0 else 1
            return result

        return _num_comb(w)


class ParseForestPrinter(ParseForestNavigator):

    """ Print a parse forest to stdout or a file """

    def __init__(self, detailed = False, file = None,
        show_scores = False, show_ids = False, visit_all = True):
        super().__init__(visit_all = visit_all) # Normally, we visit all nodes
        self._detailed = detailed
        self._file = file
        self._show_scores = show_scores
        self._show_ids = show_ids

    def _score(self, w):
        """ Return a string showing the node's score """
        # !!! To enable this, assignment of the .score attribute
        # !!! needs to be uncommented in reducer.py
        return " [{0}]".format(w.score) if self._show_scores else ""

    def _visit_epsilon(self, level):
        """ Epsilon (null) node """
        indent = "  " * level # Two spaces per indent level
        print(indent + "(empty)", file = self._file)
        return None

    def _visit_token(self, level, w):
        """ Token matching a terminal """
        indent = "  " * level # Two spaces per indent level
        h = str(w.token)
        if self._show_ids:
            h += " @ {0:x}".format(id(w))
        print(indent + "{0}: {1}{2}".format(w.terminal, h, self._score(w)),
            file = self._file)
        return None

    def _visit_nonterminal(self, level, w):
        # Interior nodes are not printed
        # and do not increment the indentation level
        if self._detailed or not w.is_interior:
            if not self._detailed:
                if w.is_empty and w.nonterminal.is_optional:
                    # Skip printing optional nodes that don't contain anything
                    return NotImplemented # Don't visit child nodes
            h = w.nonterminal.name
            indent = "  " * level # Two spaces per indent level
            if self._show_ids:
                h += " @ {0:x}".format(id(w))
            print(indent + h + self._score(w), file = self._file)
        return None # No results required, but visit children

    def _visit_family(self, results, level, w, ix, prod):
        """ Show trees for different options, if ambiguous """
        if w.is_ambiguous:
            indent = "  " * level # Two spaces per indent level
            print(indent + "Option " + str(ix + 1) + ":", file = self._file)

    @classmethod
    def print_forest(cls, root_node, detailed = False, file = None,
        show_scores = False, show_ids = False, visit_all = True):
        """ Print a parse forest to the given file, or stdout if none """
        cls(detailed, file, show_scores, show_ids, visit_all).go(root_node)


class ParseForestDumper(ParseForestNavigator):

    """ Dump a parse forest into a compact string """

    # The result is a string consisting of lines separated by newline characters.
    # The format is as follows:
    # (n indicates a nesting level, >= 0)
    # R1 -- start indicator and version number
    # Pn -- Epsilon node
    # Tn terminal token -- Token/terminal node
    # Nn nonterminal -- Nonterminal node
    # On index -- Option with index >= 0
    # Q0 -- end indicator (not followed by newline)

    VERSION = "Reynir/1.00"

    def __init__(self):
        super().__init__(visit_all = True) # Visit all nodes
        self._result = ["R1"] # Start indicator and version number

    def _visit_epsilon(self, level):
        # Identify this as an epsilon (null) node
        self._result.append("P{0}".format(level))
        return None

    def _visit_token(self, level, w):
        # Identify this as a terminal/token
        self._result.append("T{0} {1} {2}".format(level, w.terminal, w.token.dump))
        return None

    def _visit_nonterminal(self, level, w):
        # Interior nodes are not dumped
        # and do not increment the indentation level
        if not w.is_interior:
            if w.is_empty and w.nonterminal.is_optional:
                # Skip printing optional nodes that don't contain anything
                return NotImplemented # Don't visit child nodes
            # Identify this as a nonterminal
            self._result.append("N{0} {1}".format(level, w.nonterminal.name))
        return None # No results required, but visit children

    def _visit_family(self, results, level, w, ix, prod):
        if w.is_ambiguous:
            # Identify this as an option
            self._result.append("O{0} {1}".format(level, ix))

    @classmethod
    def dump_forest(cls, root_node):
        """ Print a parse forest to the given file, or stdout if none """
        dumper = cls()
        dumper.go(root_node)
        dumper._result.append("Q0") # End marker
        return "\n".join(dumper._result)


class ParseForestFlattener(ParseForestNavigator):

    """ Create a simpler, flatter version of an already disambiguated parse tree """

    class Node:

        def __init__(self, p):
            self._p = p
            self._children = None

        def add_child(self, child):
            if self._children is None:
                self._children = [ child ]
            else:
                self._children.append(child)

        @property
        def p(self):
            return self._p

        @property
        def children(self):
            return self._children

        @property
        def has_children(self):
            return self._children is not None

        @property
        def is_nonterminal(self):
            return not isinstance(self._p, tuple)

        def _to_str(self, indent):
            if self.has_children:
                return "{0}{1}{2}".format(" " * indent,
                    self._p,
                    "".join("\n" + child._to_str(indent+1) for child in self._children))
            return "{0}{1}".format(" " * indent, self._p)

        def __str__(self):
            return self._to_str(0)

    def __init__(self):
        super().__init__(visit_all = True) # Visit all nodes

    def go(self, root_node):
        self._stack = None
        super().go(root_node)

    @property
    def root(self):
        return self._stack[0] if self._stack else None

    def _visit_epsilon(self, level):
        """ Epsilon (null) node: not included in a flattened tree """
        return None

    def _visit_token(self, level, w):
        """ Add a terminal/token node to the flattened tree """
        assert level > 0
        assert self._stack
        node = ParseForestFlattener.Node((w.terminal, w.token))
        self._stack = self._stack[0:level]
        self._stack[-1].add_child(node)
        return None

    def _visit_nonterminal(self, level, w):
        """ Add a nonterminal node to the flattened tree """
        # Interior nodes are not dumped
        # and do not increment the indentation level
        if not w.is_interior:
            if w.is_empty and w.nonterminal.is_optional:
                # Skip optional nodes that don't contain anything
                return NotImplemented # Signal: Don't visit child nodes
            # Identify this as a nonterminal
            node = ParseForestFlattener.Node(w.nonterminal)
            if level == 0:
                # New root (must be the only one)
                assert self._stack is None
                self._stack = [ node ]
            else:
                # New child of the parent node
                self._stack = self._stack[0:level]
                self._stack[-1].add_child(node)
                self._stack.append(node)
        return None # No results required, but visit children

    def _visit_family(self, results, level, w, ix, prod):
        """ Visit different subtree options within a parse forest """
        # In this case, the tree should be unambigous
        assert not w.is_ambiguous

    @classmethod
    def flatten(cls, root_node):
        """ Flatten a parse tree """
        dumper = cls()
        dumper.go(root_node)
        return dumper.root

