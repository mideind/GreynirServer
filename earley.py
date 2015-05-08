# -*- coding: utf-8 -*-

""" Reynir: Natural language processing for Icelandic

    Earley parser module

    Author: Vilhjalmur Thorsteinsson

    This software is at a very early development stage.
    While that is the case, it is:
    Copyright (c) 2015 Vilhjalmur Thorsteinsson
    All rights reserved

    An Earley parser can recognize all valid context-free grammars,
    irrespective of ambiguity, recursion (left or right), nullability, etc.

    For further information see J. Earley, "An efficient context-free parsing algorithm",
    Communications of the Association for Computing Machinery, 13:2:94-102, 1970.

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
import itertools

from pprint import pprint as pp


class ParseError(Exception):
    """ Exception class for parser errors """
    pass


class Nonterminal:

    """ A nonterminal, either at the left hand side of
        a rule or within a production """

    def __init__(self, name):
        self.name = name

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

    def __init__(self, rhs = None):
        """ Initialize a production from a list of
            right-hand-side nonterminals and terminals """
        self._rhs = [] if rhs is None else rhs
        # Give all productions a unique sequence number for hashing purposes
        self._index = Production._INDEX
        Production._INDEX += 1

    def __hash__(self):
        """ Use the index of this production as a basis for the hash """
        return self._index.__hash__()

    def append(self, t):
        """ Append a terminal or nonterminal to this production """
        self._rhs.append(t)

    def expand(self, l):
        """ Add a list of terminals and/or nonterminals to this production """
        self._rhs.expand(l)

    def length(self):
        """ Return the length of this production """
        return len(self._rhs)

    def __getitem__(self, index):
        """ Return the terminal or nonterminal at the given index position """
        return self._rhs.__getitem__(index)

    def __len__(self):
        """ Return the length of this production """
        return self._rhs.__len__()

    def __repr__(self):
        """ Return a representation of this production """
        return self._rhs.__repr__()


# Abbreviations
NT = Nonterminal
TERM = Terminal
TOK = Token
EOF = TERM('EOF') # End-of-stream terminal (uppercase by intent)
EOF_TOKEN = TOK('EOF', 'EOF')
S0 = NT('s0') # Reserved nonterminal (lowercase by intent)


class Parser:

    """ A parser state is represented as follows:

        (nt, dot, prod, start, tok0)
         [0] [1]  [2]   [3]    [4]

        nt = nonterminal (left hand side) being derived
        dot = index position within production [p0, p1, (*) p2, ..., pN]
        prod = production (right hand side) list: [p0, p1, p2, ..., pN]
        start = index of token where this production began
        tok0 = the token that matched the previous terminal

    """

    def __init__(self, grammar, root):
        self.grammar = grammar
        self.root = root

    def go(self, tokens):
        """ Parse an iterable stream of tokens """
        # Create the Earley state table, consisting of columns of states,
        # one column for each token parsed and a final column for the
        # end (EOF) state
        cols = [
            [(S0, 0, [self.root, EOF], 0, None)] # Initial state (column 0)
        ]
        # Chain an EOF marker to the end of the token list
        for i, t in enumerate(itertools.chain(tokens, [ EOF_TOKEN ])): # enumerate(tokens + [ EOF_TOKEN ]):
            # Step through the tokens, adding state columns to the table
            self._step(cols, t, i)
        # Look at the last column generated by _step()
        last_col = cols[-1]
        print("Parse yields {0} end states".format(len(last_col)))
        if not last_col or last_col[0][0] is not S0:
            raise ParseError ('No valid parse tree found')
        # Reconstruct the parse trees from the state table
        return self._build_parse_trees(cols)

    def _step(self, cols, tok, i):
        """ Parse the i-th token using the Earley algorithm

            To resolve ambiguity correctly, consider converting
            state list inside column from regular list to
            Python OrderedDict. Then, when adding a completed
            state that is already in the dict, move it to the
            end of the dict - making sure build_parse_tree
            catches all completions. OrderedDict will also speed
            up the tree-building process since we may no longer
            need a linear scan for nonterminals (?)

         """
        nxt = [] # States to be added to the next column (i+1)
        states = cols[i] # The list of states in this column
        j = 0 # The next item on the state agenda
        #print("Step {0}: token {1}".format(i, tok))
        while j < len(states):
            # Get the next agenda item
            state = states[j]
            j += 1
            nt, dot, prod, start, tok0 = state
            #print("   State {0}: nt {nt}, dot {dot}, prod {prod}, start {start}, tok0 {tok0}"
            #    .format(j-1, nt=nt, dot=dot, prod=prod, start=start, tok0=tok0))
            if dot == len(prod):
                # Completer
                # A production has been completely matched and a nonterminal thus derived
                #print("      Completer")
                for state0 in cols[start]:
                    nt0, dot0, prod0, start0, tok0 = state0
                    if dot0 < len(prod0) and prod0[dot0] == nt:
                        maybe_new = (nt0, dot0 + 1, prod0, start0, tok0)
                        if maybe_new not in states: # or (last and start0 == 0):
                            # Add duplicate state if we're at the last token (before EOF)
                            # and the state spans the entire tree
                            states.append(maybe_new)
            elif isinstance(prod[dot], Nonterminal):
                nt0 = prod[dot]
                # Predictor
                # Add all potential derivations (productions) of the current
                # nonterminal to the agenda
                #print("      Predictor: nt0 {0}".format(nt0))
                for prod0 in self.grammar[nt0]:
                    maybe_new = (nt0, 0, prod0, i, None)
                    if maybe_new not in states:
                        states.append(maybe_new)
            elif isinstance(prod[dot], Terminal) and tok.matches(prod[dot]):
                # Scanner
                #print("      Scanner: tok.kind {0}, prod[dot].name {1}".format(tok.kind, prod[dot].name))
                nxt.append((nt, dot + 1, prod, start, tok))

        cols.append (nxt)

    def _build_parse_trees(self, cols):
        """
            After a successful parse, build the parse tree by scanning
            backwards through completed states
        """

        # This uses the technique described in "Parsing Techniques - A Practical Guide"
        # by Grune and Jacobs (2nd. ed. page 210)

        # To save memory and run-time checks, remove non-completed states from
        # each column (keeping the columns themselves)
        # i.e.,                   dot  == len(prod)

        cols = allcomp = [
            [st for st in col if st[1] == len(st[2])] for col in cols
        ]

        def walk (nt, end, limit):
            """ Walk backward through completed states in column <end>,
                starting at state[limit-1] and going to state[0],
                to find a completed version of nonterminal <nt> """
            #print("walk({0}, {1}, {2})".format(nt, end, limit))
            assert end >= 0
            assert limit <= len(allcomp[end])
            j = limit
            r = None
            return_end = end
            while j > 0:
                j -= 1
                st = allcomp[end][j]
                if st[0] == nt:
                    if r:
                        print("Found nonterminal {0} again, skipping it".format(nt))
                        continue
                    _, dot, prod, start, tok0 = st
                    # Found a completed production of this nonterminal.
                    # Walk backward through the production, recursing
                    # and building this node of the parse tree in the process.
                    #print("Found nt {nt} at state {j}".format(nt=nt, j=j))
                    r = [nt]
                    # Start off in the same column, but with lower
                    # state indices than the one we're working with
                    limit = j
                    original_end = end
                    for p in reversed(prod):
                        if isinstance(p, Nonterminal):
                            # Look for the derivation of the nonterminal
                            subtree, end, limit = walk(p, end, limit)
                            assert subtree is not None
                            if subtree is not None:
                                r.insert(1, subtree)
                        else:
                            # Terminal: insert the matched token
                            r.insert(1, tok0)
                            # Move back one column
                            assert end > 0
                            end -= 1
                            # Reset the limit accordingly
                            limit = len(allcomp[end])
                    return_end = end
                    end = original_end
                    # return r, end, limit
            # assert False # Shouldn't come here?
            return r, return_end, limit

        forest = []

        lastindex = len(allcomp) - 2
        lastcol = allcomp[lastindex] # Column where the last token was accepted
        limit = len(lastcol)
        for endstate in allcomp[-1]: # Column of completed end states
            root = endstate[2][0]
            #pp(root)
            # Seek out the roots and walk the parse table from there
            while lastcol[limit - 1][0] != root:
                limit -= 1
            assert limit > 0
            tree, _, _ = walk(root, lastindex, limit)
            forest.append(tree)
            limit -= 1

        return forest

    def _earley_scott_parse(self, tokens):

        """ Parse the tokens and build a parse forest using
            the Earley algorithm as improved by Scott (referencing Tomita).

            See Elizabeth Scott, Adrian Johnstone (2010):
            "Recognition is not parsing — SPPF-style parsing from cubic recognisers"

            Comments refer to the EARLEY_PARSER pseudocode given in the paper.

        """

        class _Node:

            """ Shared Packed Parse Forest (SPPF) node representation """

            def __init__(self, label):
                """ Initialize a SPPF node with a given label tuple """
                self._label = label
                self._families = None # Families of children
                self._hash = None

            def add_family(self, children):
                """ Add a family of children to this node, in parallel with other families """
                if children is None:
                    return
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
                V[label] = y = _Node(label)
            assert v is not None
            if w is None:
                y.add_family(v)
            else:
                y.add_family((w, v)) # The code breaks if this is modified!
            return y

        def _in_sigma(dot, prod, len_prod = None):
            """ Check whether the right-hand-side symbol prod[dot] is empty or a Nonterminal """
            if len_prod is None:
                len_prod = len(prod)
            return True if dot >= len_prod else isinstance(prod[dot], Nonterminal)

        def _match(dot, prod, token_index, len_prod = None):
            """ Check whether the terminal at dot[prod] matches the token at token_index """
            if len_prod is None:
                len_prod = len(prod)
            return False if dot >= len_prod or token_index >= n else tokens[token_index].matches(prod[dot])

        def _push(newstate, i, _E, _Q):
            """ Append a new state to an Earley column (_E) and a look-ahead set (_Q), as appropriate """
            # newstate = (nt, dot, prod, h, y)
            _, dot, prod, _, _ = newstate
            len_prod = len(prod)
            if _in_sigma(dot, prod, len_prod):
                if newstate not in _E:
                    _E.append(newstate)
            elif _match(dot, prod, i, len_prod):
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
                            V[label] = _Node(label)
                        w = v = V[label]
                        # w.add_family(None) # !!! Not necessary?
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
                v = _Node(label)
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

    def print_parse_tree(self, w):
        """ Print an Earley-Scott parse tree """

        def _print_helper(w, level):
            h = w.head()
            indent = "  " * level
            if not isinstance(h, tuple):
                print(indent + str(h))
                level += 1
            ambig = w.is_ambiguous()
            for ix, f in enumerate(w.enum_children()):
                if ambig:
                    print(indent + "Option " + str(ix + 1) + ":")
                if isinstance(f, tuple):
                    for c in f:
                        _print_helper(c, level)
                else:
                    _print_helper(f, level)

        _print_helper(w, 0)


class GrammarError(Exception):
    """ Exception raised when there is an error in a grammar """
    pass


def read_grammar(fname):
    """ Read grammar from a text file.

    A grammar is specified as follows:

    A -> A B terminal C
        | A '/' D
        | e
    B -> terminal "+" C

    Nonterminals start with uppercase letters.
    Terminals start with lowercase letters or are enclosed
    in single or double quotes.

    """

    nonterminals = { }
    terminals = { }

    # A grammar maps nonterminals to a list of right hand sides.
    # Each right hand side is a list of terminals and nonterminals.
    grammar = { }

    root_NT = None

    try:
        with codecs.open(fname, "r", "utf-8") as inp:
            # Read grammar file line-by-line
            current_NT = None
            for s in inp:
                # Ignore comments
                ix = s.find('#')
                if ix >= 0:
                    s = s[0:ix]
                s = s.strip()
                if not s:
                    # Blank line: ignore
                    continue

                def parse_rhs(s):
                    """ Parse a right-hand side sequence """
                    rhs = s.strip().split()
                    result = Production()
                    for r in rhs:
                        if r[0] in "\"'":
                            # Literal terminal symbol
                            sym = r[1:-1]
                            if sym not in terminals:
                                terminals[sym] = Terminal(sym)
                            result.append(terminals[sym])
                            continue
                        if not r.isidentifier():
                            raise GrammarError("Invalid identifier '{0}'".format(r))
                        if r[0].isupper():
                            # Reference to nonterminal
                            if r not in nonterminals:
                                nonterminals[r] = Nonterminal(r)
                            result.append(nonterminals[r])
                        else:
                            # Identifier of terminal
                            if r not in terminals:
                                terminals[r] = Terminal(r)
                            result.append(terminals[r])
                    if result.length() == 1 and result[0] == current_NT:
                        # Nonterminal derives itself
                        raise GrammarError("Nonterminal {0} deriving itself".format(current_NT))
                    return result

                if s.startswith('|'):
                    # Alternative to previous nonterminal rule
                    grammar[current_NT].append(parse_rhs(s[1:]))
                else:
                    rule = s.split("->", maxsplit=1)
                    nt = rule[0].strip()
                    if not nt.isidentifier():
                        raise GrammarError("Invalid nonterminal name '{0}' in grammar".format(nt))
                    if nt not in nonterminals:
                        nonterminals[nt] = Nonterminal(nt)
                    current_NT = nonterminals[nt]
                    if root_NT is None:
                        # Remember first nonterminal as the root
                        root_NT = current_NT
                    if len(rule) == 1:
                        # No right hand side
                        if current_NT not in grammar:
                            grammar[current_NT] = [ ]
                    else:
                        # We have a right hand side: add a grammar rule
                        assert len(rule) >= 2
                        rhs = parse_rhs(rule[1])
                        if current_NT in grammar:
                            grammar[current_NT].append(rhs)
                        else:
                            grammar[current_NT] = [ rhs ]

    except (IOError, OSError):
        print("Error while opening or reading config file '{0}'".format(fname))

    return grammar, root_NT


# Test grammar 1

E = NT ('E')
T = NT ('T')
P = NT ('P')
plus = TERM ('+')
mult = TERM ('*')
ident = TERM ('ident')

g = {
    E: [Production([E,plus,T]), Production([T])],
    T: [Production([T,mult,P]), Production([P])],
    P: [Production([ident])],
}

p = Parser(g, E)
s = [TOK('ident', 'a'),
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
pp (p.go (s))

# Test grammar 2

g, root = read_grammar("Reynir.grammar")

# pp(g)

# s = "Villi leit út eða Anna og köttur komu beint heim og kona eða maður fóru snemma inn"
s = "kona með kött myrti mann með hálsbindi og Villi fór út"
# s = "kona með kött myrti mann með hund og Villi fór út"

toklist = [TOK(w, w) for w in s.split()]

p = Parser(g, root)

forest = p.go(toklist)

for tree in forest:
    print("--------------")
    pp(tree)

print("------Earley-Scott--------")

forest = p._earley_scott_parse(toklist)

p.print_parse_tree(forest)
