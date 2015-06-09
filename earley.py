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

    A grammar is specified as a set of rules. Each rule has a single
    left-hand-side nonterminal, associated with 1..n right-hand-side
    productions. Each right-hand-side production is a sequence of
    nonterminals and terminals. A terminal can match a token of
    input.

    In Reynir grammars, nonterminals always start with an uppercase letter.
    Terminals may be identifiers starting with lowercase letters, or
    literals enclosed within single or double quotes.

"""

import codecs

from pprint import pprint as pp


class ParseError(Exception):

    """ Exception class for parser errors """

    pass


class GrammarError(Exception):

    """ Exception class for errors in a grammar """

    def __init__(self, text, fname = None, line = 0):
        self.fname = fname
        self.line = line
        prefix = ""
        if line:
            prefix = "Line " + str(line) + ": "
        if fname:
            prefix = fname + " - " + prefix
        Exception.__init__(self, prefix + text)


class Nonterminal:

    """ A nonterminal, either at the left hand side of
        a rule or within a production """

    def __init__(self, name, fname = None, line = 0):
        self.name = name
        # Place of initial definition in a grammar file
        self._fname = fname
        self._line = line
        # Has this nonterminal been referenced in a production?
        self._ref = False

    def add_ref(self):
        """ Mark this as being referenced """
        self._ref = True

    def has_ref(self):
        """ Return True if the nonterminal has been referenced in a production """
        return self._ref

    def fname(self):
        return self._fname

    def line(self):
        return self._line

    def __eq__(self, other):
        return isinstance(other, Nonterminal) and self.name == other.name

    def __ne__(self, other):
        return not isinstance(other, Nonterminal) or self.name != other.name

    def __hash__(self):
        return self.name.__hash__()

    def __repr__(self):
        return '<{0}>'.format(self.name)

    def __str__(self):
        return '<{0}>'.format(self.name)


class Terminal:

    """ A terminal within a right-hand-side production """

    def __init__(self, name):
        self.name = name

    def __hash__(self):
        return self.name.__hash__()

    def __repr__(self):
        return '\'{0}\''.format(self.name)

    def __str__(self):
        return '\'{0}\''.format(self.name)


class Token:

    """ A token from the input stream tokenizer """

    def __init__(self, kind, val):
        self.kind = kind
        self.val = val

    def __repr__(self):
        if self.kind == self.val:
            return '{0}'.format(self.kind)
        return '{0}:{1}'.format(self.kind, self.val)

    def matches(self, terminal):
        """ Does this token match the given terminal? """
        return self.kind == terminal.name


class Production:

    """ A right-hand side of a grammar rule """

    _INDEX = 0 # Running sequence number of all productions

    def __init__(self, fname = None, line = 0, rhs = None):

        """ Initialize a production from a list of
            right-hand-side nonterminals and terminals """

        self._rhs = [] if rhs is None else rhs
        # If parsing a grammar file, note the position of the production
        # in the file
        self._fname = fname
        self._line = line
        # Give all productions a unique sequence number for hashing purposes
        self._index = Production._INDEX
        Production._INDEX += 1

    def __hash__(self):
        """ Use the index of this production as a basis for the hash """
        return self._index.__hash__()

    def __eq__(self, other):
        return isinstance(other, Production) and self._index == other._index

    def __ne__(self, other):
        return not isinstance(other, Production) or self._index != other._index

    def append(self, t):
        """ Append a terminal or nonterminal to this production """
        self._rhs.append(t)

    def expand(self, l):
        """ Add a list of terminals and/or nonterminals to this production """
        self._rhs.expand(l)

    def length(self):
        """ Return the length of this production """
        return len(self._rhs)

    def is_empty(self):
        """ Return True if this is an empty (epsilon) production """
        return len(self._rhs) == 0

    def fname(self):
        return self._fname

    def line(self):
        return self._line

    def __getitem__(self, index):
        """ Return the terminal or nonterminal at the given index position """
        return self._rhs[index]

    def __len__(self):
        """ Return the length of this production """
        return len(self._rhs)

    def __repr__(self):
        """ Return a representation of this production """
        return "Prod: " + self._rhs.__repr__()


class Grammar:

    """
        A grammar maps nonterminals to a list of right hand sides.
        Each right hand side is a list of terminals and nonterminals.

        The text representation of a grammar is as follows:

        A -> A B terminal C
            | A '/' D
            | 0
        B -> terminal "+" C

        Nonterminals start with uppercase letters.
        Terminals start with lowercase letters or are enclosed
        in single or double quotes.
        0 means an empty (epsilon) production

    """

    def __init__(self):
        self._nonterminals = { }
        self._terminals = { }
        self._grammar = { }
        self._root = None

    def grammar(self):
        """ Return the raw grammar dictionary, Nonterminal -> Production """
        return self._grammar

    def root(self):
        """ Return the root nonterminal for this grammar """
        return self._root

    def read(self, fname):
        """ Read grammar from a text file """

        # Shortcuts
        terminals = self._terminals
        nonterminals = self._nonterminals
        grammar = self._grammar
        line = 0

        try:
            with codecs.open(fname, "r", "utf-8") as inp:
                # Read grammar file line-by-line
                current_NT = None
                for s in inp:
                    line += 1
                    # Ignore comments
                    ix = s.find('#')
                    if ix >= 0:
                        s = s[0:ix]
                    s = s.strip()
                    if not s:
                        # Blank line: ignore
                        continue

                    def _add_rhs(nt, rhs):
                        """ Add a right-hand-side production to a nonterminal rule """
                        if nt not in grammar:
                            grammar[nt] = [ ] if rhs is None else [ rhs ]
                            return
                        if rhs is None:
                            return
                        if rhs.is_empty():
                            # Adding epsilon production: avoid multiple ones
                            for p in grammar[nt]:
                                if p.is_empty():
                                    # Another epsilon already there: quit
                                    return
                        grammar[nt].append(rhs)

                    def _parse_rhs(s):
                        """ Parse a right-hand side sequence """
                        s = s.strip()
                        if not s:
                            return None
                        rhs = s.split()
                        result = Production(fname, line)
                        for r in rhs:
                            if r == "0":
                                # Empty (epsilon) production
                                if len(rhs) != 1:
                                    raise GrammarError("Empty (epsilon) rule must be of the form NT -> 0", fname, line)
                                break
                            if r[0] in "\"'":
                                # Literal terminal symbol
                                sym = r[1:-1]
                                if sym not in terminals:
                                    terminals[sym] = Terminal(sym)
                                result.append(terminals[sym])
                                continue
                            if not r.isidentifier():
                                raise GrammarError("Invalid identifier '{0}'".format(r), fname, line)
                            if r[0].isupper():
                                # Reference to nonterminal
                                if r not in nonterminals:
                                    nonterminals[r] = Nonterminal(r, fname, line)
                                nonterminals[r].add_ref() # Note that the nonterminal has been referenced
                                result.append(nonterminals[r])
                            else:
                                # Identifier of terminal
                                if r not in terminals:
                                    terminals[r] = Terminal(r)
                                result.append(terminals[r])
                        if result.length() == 1 and result[0] == current_NT:
                            # Nonterminal derives itself
                            raise GrammarError("Nonterminal {0} deriving itself".format(current_NT), fname, line)
                        return result

                    if s.startswith('|'):
                        # Alternative to previous nonterminal rule
                        if current_NT is None:
                            raise GrammarError("Missing nonterminal", fname, line)
                        _add_rhs(current_NT, _parse_rhs(s[1:]))
                    else:
                        rule = s.split("->", maxsplit=1)
                        nt = rule[0].strip()
                        if not nt.isidentifier():
                            raise GrammarError("Invalid nonterminal name '{0}' in grammar".format(nt), fname, line)
                        if nt not in nonterminals:
                            nonterminals[nt] = Nonterminal(nt, fname, line)
                        current_NT = nonterminals[nt]
                        if self._root is None:
                            # Remember first nonterminal as the root
                            self._root = current_NT
                            self._root.add_ref() # Implicitly referenced
                        if current_NT not in grammar:
                            grammar[current_NT] = [ ]
                        if len(rule) >= 2:
                            # We have a right hand side: add a grammar rule
                            rhs = _parse_rhs(rule[1])
                            _add_rhs(current_NT, rhs)

        except (IOError, OSError):
            raise GrammarError("Unable to open or read grammar file", fname, 0)

        # Check all nonterminals to verify that they have productions and are referenced
        for nt in nonterminals.values():
            if not nt.has_ref():
                raise GrammarError("Nonterminal {0} is never referenced in a production".format(nt), nt.fname(), nt.line())
        for nt, plist in grammar.items():
            if len(plist) == 0:
                raise GrammarError("Nonterminal {0} has no productions".format(nt), nt.fname(), nt.line())
            else:
                for p in plist:
                    if len(p) == 1 and plist[0] == nt:
                        raise GrammarError("Nonterminal {0} produces itself".format(nt), p.fname(), p.line())

        # Check that all nonterminals derive terminal strings
        agenda = [ nt for nt in nonterminals.values() ]
        der_t = set()
        while agenda:
            reduced = False
            for nt in agenda:
                for p in grammar[nt]:
                    if all([True if isinstance(s, Terminal) else s in der_t for s in p]):
                        der_t.add(nt)
                        break
                if nt in der_t:
                    reduced = True
            if not reduced:
                break
            agenda = [ nt for nt in nonterminals.values() if nt not in der_t ]
        if agenda:
            raise GrammarError("Nonterminals {0} do not derive terminal strings"
                .format(", ".join([str(nt) for nt in agenda])), fname, 0)

        # Check that all nonterminals are reachable from the root
        unreachable = { nt for nt in nonterminals.values() }

        def _remove(nt):
            """ Recursively remove all nonterminals that are reachable from nt """
            unreachable.remove(nt)
            for p in grammar[nt]:
                for s in p:
                    if isinstance(s, Nonterminal) and s in unreachable:
                        _remove(s)

        _remove(self._root)

        if unreachable:
            raise GrammarError("Nonterminals {0} are unreachable from the root"
                .format(", ".join([str(nt) for nt in unreachable])), fname, 0)


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
        """ Initialize the parser from a grammar and a root nonterminal within it """
        assert grammar is not None
        assert root is not None
        assert root in grammar
        self.grammar = grammar
        self.root = root


    @classmethod
    def from_grammar(cls, g):
        """ Create a Parser from a Grammar object """
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


    def print_parse_forest(self, w):
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


# Test grammar 1

print("------ Test 1 ---------")

# Abbreviations
NT = Nonterminal
TERM = Terminal
TOK = Token

# Hard-coded test case - grammar not read from file

E = NT ('E')
T = NT ('T')
P = NT ('P')
plus = TERM ('+')
mult = TERM ('*')
ident = TERM ('ident')

g = {
    E: [Production(rhs=[E,plus,T]), Production(rhs=[T])],
    T: [Production(rhs=[T,mult,P]), Production(rhs=[P])],
    P: [Production(rhs=[ident])],
}

p = Parser(g, E)
s = [
    TOK('ident', 'a'),
    TOK('*', '*'),
    TOK ('ident', 'b'),
    TOK ('+', '+'),
    TOK ('ident', 'c'),
    TOK ('*', '*'),
    TOK ('ident', 'd'),
    TOK ('+', '+'),
    TOK ('ident', 'e'),
    TOK ('+', '+'),
    TOK ('ident', 'f')
]
forest = p.go(s)
p.print_parse_forest(forest)

print("------ Test 2 ---------")

# Test grammar 2 - read from file

g = Grammar()
g.read("Reynir.grammar")

# pp(g.grammar())

# s = "Villi leit út eða Anna og köttur komu beint heim og kona eða maður fóru snemma inn"
s = "kona með kött myrti mann með hálsbindi og Villi fór út"
# s = "kona með kött myrti mann með hund og Villi fór út"
# s = "Villi leit út"

toklist = [TOK(w, w) for w in s.split()]

p = Parser.from_grammar(g)

forest = p.go(toklist)

p.print_parse_forest(forest)
