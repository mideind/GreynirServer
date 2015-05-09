# -*- coding: utf-8 -*-

""" Reynir: Natural language processing for Icelandic

    Parser module

    Author: Vilhjalmur Thorsteinsson

    This software is at a very early development stage.
    While that is the case, it is:
    Copyright (c) 2015 Vilhjalmur Thorsteinsson
    All rights reserved

    This module uses an Earley-Scott parser to transform token sequences
    (sentences) into forests of parse trees, with each tree representing a
    possible parse of a sequence.

    An Earley parser handles all valid context-free grammars,
    irrespective of ambiguity, recursion (left/middle/right), nullability, etc.
    The returned parse trees reflect the original grammar, which does not
    need to be normalized or modified in any way. All partial parses are
    available in the final parse state table.

    For further information see J. Earley, "An efficient context-free parsing algorithm",
    Communications of the Association for Computing Machinery, 13:2:94-102, 1970.

    The Earley parser used here is the improved version described by Scott et al,
    referencing Tomita. This allows worst-case O(n^2) order, where n is the length
    of the input sentence, while still returning all possible parse trees
    for an ambiguous grammar. See comments in Parser.go() below.

"""

import codecs

from pprint import pprint as pp

from grammar import Nonterminal, Terminal, Token


class ParseError(Exception):

    """ Exception class for parser errors """

    pass


class Parser:

    """ Parses a sequence of tokens according to a given grammar and
        a root nonterminal within that grammar, returning a forest of
        possible parses

    """

    class Node:

        """ Shared Packed Parse Forest (SPPF) node representation """

        def __init__(self, label):
            """ Initialize a SPPF node with a given label tuple """
            self._label = label
            self._families = None # Families of children
            self._hash = None

        def add_family(self, children):
            """ Add a family of children to this node, in parallel with other families """
            if self._families is None:
                self._families = [ children ]
                return
            if children not in self._families:
                self._families.append(children)

        def label(self):
            """ Return the node label """
            return self._label

        def head(self):
            """ Return the 'head' of this node, i.e. a top-level readable name for it """
            h = self._label
            # while isinstance(h, tuple):
            if isinstance(h, tuple):
                h = h[0]
            # assert isinstance(h, Nonterminal) or isinstance(h, Terminal) or isinstance(h, Token)
            return h

        def is_ambiguous(self):
            """ Return True if this node has more than one family of children """
            return self._families and len(self._families) >= 2

        def has_children(self):
            """ Return True if there are any families of children of this node """
            return bool(self._families)

        def enum_children(self):
            """ Enumerate families of children """
            if not self._families:
                raise StopIteration
            for c in self._families:
                yield c

        def __hash__(self):
            """ Calculate and cache our hash value """
            # Note that Python does not cache tuple hashes;
            # therefore it's wise do to this manually
            if self._hash is None:
                self._hash = self._label.__hash__()
            return self._hash

        def __repr__(self):
            """ Create a reasonably nice text representation of this node
                and its families of children, if any """
            label_rep = self._label.__repr__()
            families_rep = ""
            if self._families:
                if len(self._families) == 1:
                    families_rep = self._families[0].__repr__()
                else:
                    families_rep = "<" + self._families.__repr__() + ">"
            return label_rep + ((": " + families_rep + "\n") if families_rep else "")


    def __init__(self, grammar, root):

        """ Initialize a parser from a "raw" grammar dictionary and a root nonterminal within it """

        assert grammar is not None
        assert root is not None
        assert root in grammar
        self.grammar = grammar
        self.root = root


    @classmethod
    def for_grammar(cls, g):
        """ Create a Parser for the Grammar in g """
        return cls(g.grammar(), g.root())


    def go(self, tokens):

        """ Parse the tokens and return a forest of nodes using
            the Earley algorithm as improved by Scott (referencing Tomita).

            The parser handles ambiguity, returning alternative options within
            a single packed tree.

            See Elizabeth Scott, Adrian Johnstone:
            "Recognition is not parsing — SPPF-style parsing from cubic recognisers"
            Science of Computer Programming, Volume 75, Issues 1–2, 1 January 2010, Pages 55–70

            Comments refer to the EARLEY_PARSER pseudocode given in the paper.

        """

        def _make_node(nt_B, dot, prod, j, i, w, v, V):
            """ MAKE_NODE(B ::= αx · β, j, i, w, v, V) """
            len_prod = len(prod)
            if dot == 1 and len_prod >= 2:
                return v
            # Create a label for the new node
            if dot >= len_prod:
                # β is empty (i.e. the nonterminal B is complete)
                s = nt_B
            else:
                s = (nt_B, dot, prod)
            # If there is no node y ∈ V labelled (s, j, i),
            # create one and add it to V
            label = (s, j, i)
            if label in V:
                y = V[label]
            else:
                V[label] = y = Parser.Node(label)
            assert v is not None
            if w is None:
                y.add_family(v)
            else:
                y.add_family((w, v)) # The code breaks if this is modified!
            return y

        def _push(newstate, i, _E, _Q):
            """ Append a new state to an Earley column (_E) and a look-ahead set (_Q), as appropriate """
            # (N ::= α·δ, h, y)
            # newstate = (N, dot, prod, h, y)
            _, dot, prod, _, _ = newstate
            len_prod = len(prod)
            if dot >= len_prod or isinstance(prod[dot], Nonterminal):
                # Nonterminal or epsilon
                # δ ∈ ΣN
                if newstate not in _E:
                    _E.append(newstate)
            elif dot < len_prod and i < n and tokens[i].matches(prod[dot]):
                # Terminal matching the current token
                _Q.append(newstate)

        # V = ∅
        V = { }

        n = len(tokens)
        # Initialize the Earley columns
        E = [ [] for _ in range(n + 1) ]
        E0 = E[0]
        Q0 = [ ]

        # Populate column 0 (E0) with start states and Q0 with lookaheads
        for root_p in self.grammar[self.root]:
            # Go through root productions
            newstate = (self.root, 0, root_p, 0, None)
            # add (S ::= ·α, 0, null) to E0 and Q0
            _push(newstate, 0, E0, Q0)
        # Step through the Earley columns
        for i, Ei in enumerate(E):
            # The agenda set R is Ei[j..len(Ei)]
            if not Ei:
                # Parse options exhausted, nothing to do
                raise ParseError("No parse available at token {0} ({1})"
                    .format(i, tokens[i-1])) # Token index is 1-based
            j = 0
            H = { }
            Q = Q0
            Q0 = [ ]
            while j < len(Ei):
                # Remove an element, Λ say, from R
                # Λ = state
                state = Ei[j]
                j += 1
                nt_B, dot, prod, h, w = state
                len_prod = len(prod)
                # if Λ = (B ::= α · Cβ, h, w):
                if dot < len_prod and isinstance(prod[dot], Nonterminal):
                    # Earley predictor
                    # for all (C ::= δ) ∈ P:
                    nt_C = prod[dot]
                    # Go through all right hand sides of non-terminal nt_C
                    for p in self.grammar[nt_C]:
                        # if δ ∈ ΣN and (C ::= ·δ, i, null) !∈ Ei:
                        newstate = (nt_C, 0, p, i, None)
                        _push(newstate, i, Ei, Q)
                    # if ((C, v) ∈ H):
                    if nt_C in H:
                        for v in H[nt_C]:
                            # y = MAKE_NODE(B ::= αC · β, h, i, w, v, V)
                            y = _make_node(nt_B, dot + 1, prod, h, i, w, v, V)
                            newstate = (nt_B, dot + 1, prod, h, y)
                            _push(newstate, i, Ei, Q)
                # if Λ = (D ::= α·, h, w):
                elif dot >= len_prod:
                    # Earley completer
                    if not w:
                        label = (nt_B, i, i)
                        if label not in V:
                            V[label] = Parser.Node(label)
                        w = v = V[label]
                        w.add_family(None) # Add e (empty production) as a family
                    if h == i:
                        if nt_B in H:
                            H[nt_B].append(w)
                        else:
                            H[nt_B] = [w]
                    # for all (A ::= τ · Dδ, k, z) in Eh:
                    for st0 in E[h]:
                        nt_A, dot0, prod0, k, z = st0
                        len_prod0 = len(prod0)
                        if dot0 < len_prod0 and prod0[dot0] == nt_B:
                            # y = MAKE_NODE(A ::= τD · δ, k, i, z, w, V)
                            y = _make_node(nt_A, dot0 + 1, prod0, k, i, z, w, V)
                            newstate = (nt_A, dot0 + 1, prod0, k, y)
                            _push(newstate, i, Ei, Q)

            V = { }
            if Q:
                label = (tokens[i], i, i + 1)
                v = Parser.Node(label)
            while Q:
                # Earley scanner
                # Remove an element, Λ = (B ::= α · ai+1β, h, w) say, from Q
                state = Q.pop()
                nt_B, dot, prod, h, w = state
                assert isinstance(prod[dot], Terminal)
                assert tokens[i].matches(prod[dot])
                # y = MAKE_NODE(B ::= αai+1 · β, h, i + 1, w, v, V)
                y = _make_node(nt_B, dot + 1, prod, h, i + 1, w, v, V)
                newstate = (nt_B, dot + 1, prod, h, y)
                _push(newstate, i + 1, E[i + 1], Q0)

        # if (S ::= τ ·, 0, w) ∈ En: return w
        for state in E[n]:
            nt, dot, prod, k, w = state
            if nt == self.root and dot >= len(prod) and k == 0:
                return w
        # No parse
        return None


    def go_no_exc(self, tokens):
        """ Simple version of go() that returns None instead of throwing ParseError """
        try:
            return self.go(tokens)
        except ParseError:
            return None


    @staticmethod
    def print_parse_forest(w):
        """ Print an Earley-Scott-Tomita SPPF parse forest in a nice indented format """

        def _print_helper(w, level):
            """ Print the node w at the given indentation level """
            indent = "  " * level # Two spaces per indent level
            if w is None:
                # Epsilon node
                print(indent + "(empty)")
                return
            h = w.head()
            # If h is a tuple, this is an interor node that is not printed
            # and does not increment the indentation level
            if not isinstance(h, tuple):
                print(indent + str(h))
                level += 1
            ambig = w.is_ambiguous()
            for ix, f in enumerate(w.enum_children()):
                if ambig:
                    # Identify the available parse options
                    print(indent + "Option " + str(ix + 1) + ":")
                if isinstance(f, tuple):
                    for c in f:
                        _print_helper(c, level)
                else:
                    _print_helper(f, level)

        _print_helper(w, 0)

