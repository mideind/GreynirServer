"""
    Reynir: Natural language processing for Icelandic

    Python wrapper for C++ Earley/Scott parser

    Author: Vilhjalmur Thorsteinsson

    This software is at a very early development stage.
    While that is the case, it is:
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

from binparser import BIN_Parser
from cffi import FFI


ffi = FFI()

# CFFI magic stuff to make Python understand the C/C++ structures

declarations = """

    typedef unsigned int UINT;
    typedef int INT;
    typedef int BOOL; // Different from C++
    typedef char CHAR;

    typedef struct {
        UINT m_nNonterminals;   // Number of nonterminals
        UINT m_nTerminals;      // Number of terminals (indexed from 1)
        INT m_iRoot;            // Index of root nonterminal (negative)
    } Grammar;

    typedef struct {
        Grammar* m_pGrammar;
    } Parser;

    typedef struct {
        UINT m_nPriority;
    } Production;

    typedef struct {
        INT m_iNt;
        UINT m_nDot;
        Production* m_pProd;
        UINT m_nI;
        UINT m_nJ;
    } Label;

    typedef struct {
        struct Node* p1;
        struct Node* p2;
        struct FamilyEntry* pNext;
    } FamilyEntry;

    typedef struct {
        Label m_label;
        FamilyEntry* m_pHead;
        UINT m_nRefCount;
    } Node;

    typedef BOOL (*MatchingFunc)(UINT nToken, UINT nTerminal);

    Node* earleyParse(Parser*, UINT nTokens);
    Grammar* newGrammar(const CHAR* pszGrammarFile);
    void deleteGrammar(Grammar*);
    Parser* newParser(Grammar*, MatchingFunc fpMatcher);
    void deleteParser(Parser*);
    void deleteForest(Node*);
    UINT numCombinations(Node*);

    void printAllocationReport(void);

"""

ffi.cdef(declarations)

_tokens = None
_terminals = None

@ffi.callback("BOOL(UINT, UINT)")
def matching_func(token, terminal):
    # print("Matching_func: token {0}, terminal {1}".format(token, terminal))

    return _tokens[token].matches(_terminals[terminal])


class Fast_Parser(BIN_Parser):

    """ This class wraps a fast Earley-Scott parser written
        in C++ and called via CFFI """

    # Dynamically load the C++ shared library
    eparser = ffi.dlopen("./libeparser.so")

    # Callback function to match tokens with terminals

    GRAMMAR_BINARY_FILE = "Reynir.grammar.bin"
    GRAMMAR_BINARY_FILE_BYTES = GRAMMAR_BINARY_FILE.encode('ascii')

    def __init__(self, verbose = False):
        super().__init__(verbose)
        global _terminals
        _terminals = self._terminals
        # Create instances of the C++ Grammar and Parser classes
        fname = Fast_Parser.GRAMMAR_BINARY_FILE_BYTES
        ep = Fast_Parser.eparser
        self._c_grammar = ep.newGrammar(fname)
        self._c_parser = ep.newParser(self._c_grammar, matching_func)

    def go(self, tokens):
        """ Parse the tokens using the C++ parser module """

        global _tokens
        _tokens = self._wrap(tokens) # Inherited from BIN_Parser
        ep = Fast_Parser.eparser
        node = ep.earleyParse(self._c_parser, len(_tokens))
        print("Returned node {0}".format(node))
        # Remember to call Fast_Parser.deleteForest() on the returned Node!
        return node

    @classmethod
    def delete_forest(cls, node):
        """ Delete a node that was returned from Fast_Parser.go() """
        ep = cls.eparser
        ep.deleteForest(node)

    @classmethod
    def num_combinations(cls, node):
        """ Return the number of parse trees in a forest """
        ep = cls.eparser
        return ep.numCombinations(node)

    def cleanup(self):
        """ Delete C++ objects. Must call after last use of Fast_Parser
            to avoid memory leaks. """
        ep = Fast_Parser.eparser
        ep.deleteParser(self._c_parser)
        self._c_parser = None
        ep.deleteGrammar(self._c_grammar)
        self._c_grammar = None
        # !!! DEBUG
        ep.printAllocationReport()
