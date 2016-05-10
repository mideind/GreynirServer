"""
    Reynir: Natural language processing for Icelandic

    Python wrapper for C++ Earley/Scott parser

    Copyright (c) 2015 Vilhjalmur Thorsteinsson
    All rights reserved

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

from threading import Lock

import os
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

    struct Node* earleyParse(struct Parser*, UINT nTokens, UINT nHandle, UINT* pnErrorToken);
    struct Grammar* newGrammar(const CHAR* pszGrammarFile);
    void deleteGrammar(struct Grammar*);
    struct Parser* newParser(struct Grammar*, MatchingFunc fpMatcher);
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

    def __init__(self, handle, tokens, terminals):
        self._handle = handle
        self._tokens = tokens
        self._terminals = terminals

    def matches(self, token, terminal):
        """ Convert the token reference from a 0-based token index
            to the token object itself; convert the terminal from a
            1-based terminal index to a terminal object. """
        return self._tokens[token].matches(self._terminals[terminal])

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
    def make(cls, tokens, terminals):
        """ Create a new parse job with for a given token sequence and set of terminals """
        with cls._lock:
            h = cls._seq
            cls._seq += 1
            if cls._seq >= cls._MAX_JOBS:
                cls._seq = 0
            j = cls._jobs[h] = ParseJob(h, tokens, terminals)
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


# CFFI callback function

@ffi.callback("BOOL(UINT, UINT, UINT)")
def matching_func(handle, token, terminal):
    """ This function is called from the C++ parser to determine
        whether a token matches a terminal. The token is referenced
        by 0-based index, and the terminal by a 1-based index.
        The handle is an arbitrary UINT that was passed to
        earleyParse(). In this case, it is used to identify
        a ParseJob object that dispatches the match query. """
    return ParseJob.dispatch(handle, token, terminal)


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

    def __init__(self, grammar, tokens, c_dict, c_node, parent = None, index = 0):
        """ Initialize a Python SPPF node from a C++ node structure """
        lb = c_node.label
        self._start = lb.nI
        self._end = lb.nJ
        self._hash = id(self).__hash__()
        self._families = None # Families of children
        if lb.iNt < 0:
            # Nonterminal node, completed or not
            self._nonterminal = grammar.lookup(lb.iNt)
            #assert isinstance(self._nonterminal, Nonterminal), \
            #    "nonterminal {0} is a {1}, i.e. {2}".format(lb.iNt, type(self._nonterminal), self._nonterminal)
            self._completed = (lb.pProd == ffi.NULL) or lb.nDot >= lb.pProd.n
            self._terminal = None
            self._token = None
            c_dict[c_node] = self # Re-use nonterminal nodes if identical
        else:
            # Token node: find the corresponding terminal
            assert parent is not None
            assert parent != ffi.NULL
            tix = parent.pList[index + parent.n] if index < 0 else parent.pList[index]
            self._terminal = grammar.lookup(tix)
            #assert isinstance(self._terminal, Terminal), \
            #    "index is {0}, parent.n is {1}, tix is {2}, production {3}".format(index, parent.n, tix, grammar.productions_by_ix[parent.nId])
            self._token = tokens[lb.iNt]
            self._nonterminal = None
            self._completed = True
        fe = c_node.pHead
        while fe != ffi.NULL:
            if self._completed:
                child_ix = -1
            else:
                child_ix = index
            self._add_family(grammar, tokens, c_dict, fe.pProd, fe.p1, fe.p2, child_ix)
            fe = fe.pNext

    def _add_family(self, grammar, tokens, c_dict, prod, ch1, ch2, child_ix):
        """ Add a family of children to this node, in parallel with other families """
        if ch1 != ffi.NULL and ch2 != ffi.NULL:
            child_ix -= 1
        if ch1 == ffi.NULL:
            n1 = None
        elif ch1 in c_dict:
            n1 = c_dict[ch1]
        else:
            n1 = Node(grammar, tokens, c_dict, ch1, prod, child_ix)
        if n1 is not None:
            child_ix += 1
        if ch2 == ffi.NULL:
            n2 = None
        elif ch2 in c_dict:
            n2 = c_dict[ch2]
        else:
            n2 = Node(grammar, tokens, c_dict, ch2, prod, child_ix)
        if n1 is not None and n2 is not None:
            children = (n1, n2)
        elif n2 is not None:
            children = n2
        else:
            # n1 may be None if this is an epsilon node
            children = n1
        # Recreate the pc tuple from the production index
        pc = (grammar.productions_by_ix[prod.nId], children)
        if self._families is None:
            self._families = [ pc ]
            return
        self._families.append(pc)

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
        return self._families and len(self._families) >= 2

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

    def enum_children(self):
        """ Enumerate families of children """
        if self._families:
            for prod, children in self._families:
                yield (prod, children)

    def reduce_to(self, child_ix):
        """ Eliminate all child families except the given one """
        if not self._families or child_ix >= len(self._families):
            raise IndexError("Child index out of range")
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

    def go(self, root_node):
        """ Navigate the forest from the root node """

        visited = dict()

        def _nav_helper(w, index, level):
            """ Navigate from w """
            if w is None:
                # Epsilon node
                return self._visit_epsilon(level)
            if w.is_token:
                # Return the score of this terminal option
                return self._visit_token(level, w)
            if not self._visit_all and w in visited:
                # Already seen: return the previously calculated result
                return visited[w]
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
                for ix, pc in enumerate(w.enum_children()):
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

    def __init__(self, verbose = False):

        # Only one initialization at a time, since we don't want a race
        # condition between threads with regards to reading and parsing the grammar file
        # vs. writing the binary grammar
        with GlobalLock('grammar'):
            super().__init__(verbose) # Reads and parses the grammar text file
            # Create instances of the C++ Grammar and Parser classes
            c_grammar = Fast_Parser._load_binary_grammar()
            # Create a C++ parser object for the grammar
            self._c_parser = Fast_Parser.eparser.newParser(c_grammar, matching_func)

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

        wrapped_tokens, wrap_map = self._wrap(tokens) # Inherited from BIN_Parser
        ep = Fast_Parser.eparser
        err = ffi.new("unsigned int*")

        # Use the context manager protocol to guarantee that the parse job
        # handle will be properly deleted even if an exception is thrown

        with ParseJob.make(wrapped_tokens, self._terminals) as job:
            node = ep.earleyParse(self._c_parser, len(wrapped_tokens), job.handle, err)

        if node == ffi.NULL:
            ix = err[0] # Token index
            if ix >= 1:
                # Find the error token index in the original (unwrapped) token list
                orig_ix = wrap_map[ix] if ix in wrap_map else ix
                raise ParseError("No parse available at token {0} ({1})"
                    .format(orig_ix, wrapped_tokens[ix-1]), orig_ix - 1)
            else:
                # Not a normal parse error, but report it anyway
                raise ParseError("No parse available at token {0} ({1} tokens in input)"
                    .format(ix, len(wrapped_tokens)), 0)

        c_dict = dict() # Node pointer conversion dictionary
        # Create a new Python-side node forest corresponding to the C++ one
        result = Node(self.grammar, wrapped_tokens, c_dict, node)

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

    def __init__(self, detailed = False, file = None, show_scores = False):
        super().__init__(visit_all = True) # Visit all nodes
        self._detailed = detailed
        self._file = file
        self._show_scores = show_scores

    def _score(self, w):
        return " [{0}]".format(w.score) if self._show_scores else ""

    def _visit_epsilon(self, level):
        indent = "  " * level # Two spaces per indent level
        print(indent + "(empty)", file = self._file)
        return None

    def _visit_token(self, level, w):
        indent = "  " * level # Two spaces per indent level
        print(indent + "{0}: {1}{2}".format(w.terminal, w.token, self._score(w)),
            file = self._file)
        return None

    def _visit_nonterminal(self, level, w):
        # Interior nodes are not printed
        # and do not increment the indentation level
        if self._detailed or not w.is_interior:
            h = str(w.nonterminal)
            if not self._detailed:
                if (h.endswith("?") or h.endswith("*")) and w.is_empty:
                    # Skip printing optional nodes that don't contain anything
                    return NotImplemented # Don't visit child nodes
            indent = "  " * level # Two spaces per indent level
            print(indent + h + self._score(w), file = self._file)
        return None # No results required, but visit children

    def _visit_family(self, results, level, w, ix, prod):
        if w.is_ambiguous:
            indent = "  " * level # Two spaces per indent level
            print(indent + "Option " + str(ix + 1) + ":", file = self._file)

    @classmethod
    def print_forest(cls, root_node, detailed = False, file = None, show_scores = False):
        """ Print a parse forest to the given file, or stdout if none """
        cls(detailed, file, show_scores).go(root_node)


class ParseForestDumper(ParseForestNavigator):

    """ Dump a parse forest into a compact string """

    # The result is a string consisting of lines separated by newline characters.
    # The format is as follows:
    # (n indicates a nesting level, >= 0)
    # R1 -- start indicator and version number
    # En -- Epsilon node
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
        self._result.append("E{0}".format(level))
        return None

    def _visit_token(self, level, w):
        # Identify this as a terminal/token
        self._result.append("T{0} {1} {2}".format(level, w.terminal, w.token.dump))
        return None

    def _visit_nonterminal(self, level, w):
        # Interior nodes are not dumped
        # and do not increment the indentation level
        if not w.is_interior:
            n = w.nonterminal.name
            if (n.endswith("?") or n.endswith("*")) and w.is_empty:
                # Skip printing optional nodes that don't contain anything
                return NotImplemented # Don't visit child nodes
            # Identify this as a nonterminal
            self._result.append("N{0} {1}".format(level, n))
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


