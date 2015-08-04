"""
    Reynir: Natural language processing for Icelandic

    Parser module

    Author: Vilhjalmur Thorsteinsson

    This software is at a very early development stage.
    While that is the case, it is:
    Copyright (c) 2015 Vilhjalmur Thorsteinsson
    All rights reserved

    This module uses an Earley-Scott parser to transform token sequences
    (sentences) into forests of parse trees, with each tree representing a
    possible parse of a sentence, according to a given context-free grammar.

    An Earley parser handles all valid context-free grammars,
    irrespective of ambiguity, recursion (left/middle/right), nullability, etc.
    The returned parse trees reflect the original grammar, which does not
    need to be normalized or modified in any way. All partial parses are
    available in the final parse state table.

    For further information see J. Earley, "An efficient context-free parsing algorithm",
    Communications of the Association for Computing Machinery, 13:2:94-102, 1970.

    The Earley parser used here is the improved version described by Scott et al,
    referencing Tomita. This allows worst-case cubic (O(n^3)) order, where n is the
    length of the input sentence, while still returning all possible parse trees
    for an ambiguous grammar.

    See Elizabeth Scott, Adrian Johnstone:
    "Recognition is not parsing — SPPF-style parsing from cubic recognisers"
    Science of Computer Programming, Volume 75, Issues 1–2, 1 January 2010, Pages 55–70

"""

from collections import defaultdict

from grammar import Nonterminal, Terminal, Token

#from flask import current_app
#
#def debug():
#   # Call this to trigger the Flask debugger on purpose
#   assert current_app.debug == False, "Don't panic! You're here by request of debug()"


class ParseError(Exception):

    """ Exception class for parser errors """

    def __init__(self, txt, token_index = None, info = None):
        """ Store an information object with the exception,
            containing the parser state immediately before the error """
        self._info = info
        self._token_index = token_index
        Exception.__init__(self, txt)

    def info(self):
        """ Return the parser state information object """
        return self._info

    def token_index(self):
        """ Return the 0-based index of the token where the parser ran out of options """
        return self._token_index


class Parser:

    """ Parses a sequence of tokens according to a given grammar and
        a root nonterminal within that grammar, returning a forest of
        possible parses. The parses uses an optimized Earley algorithm.
    """

    class EarleyColumn:

        """ Container for the (unique) states in a single Earley column.
            Each token in the input sentence has an associated column,
            and a final column corresponds to the end-of-sentence marker.
            This class stores the states both in a list for easy indexed
            access, and in a set to enable a quick check for whether
            a state is already present. It also stores a dictionary
            of all states keyed by the particular nonterminal at the
            'dot' in the production that the state refers to. This greatly
            speeds up the Earley completion phase. """

        def __init__(self, token):
            """ Maintain a list and a set in parallel """
            self._token = token
            if token is None:
                # If no token associated with this column
                # (because it's the last column), call
                # self.matches_none() instead of self.matches()
                # to avoid a check for this (rare) condition
                # on every call to self.matches()
                self.matches = self.matches_none
            self._states = []
            self._numstates = 0
            self._set = set()
            # Dictionary of states keyed by nonterminal at prod[dot]
            self._nt_dict = defaultdict(list)
            # Cache of terminal matches
            self._matches = dict()

        def add(self, newstate):
            """ Add a new state to this column if it is not already there """
            if newstate not in self._set:
                self._states.append(newstate)
                self._set.add(newstate)
                _, dot, prod, _, _ = newstate
                # prod is a tuple of terminal (>0) and nonterminal (<0) indexes
                nt = 0 if dot >= len(prod) else prod[dot]
                if nt < 0:
                    # The state is at a nonterminal: add its index to our dict
                    # defaultdict automatically creates empty list if no entry for nt
                    self._nt_dict[nt].append(self._numstates)
                self._numstates += 1

        def matches(self, terminal):
            """ Check whether the token in this column matches the given terminal """
            # Cache lookup
            m = self._matches.get(terminal)
            if m is None:
                # Not found in cache: do the actual match and cache it
                self._matches[terminal] = m = self._token.matches(terminal)
            return m

        def matches_none(self, terminal):
            """ Shadow function for matches() that is called if there is no token in this column """
            return False

        def enum_nt(self, nt):
            """ Enumerate all states where prod[dot] is nt """
            if nt in self._nt_dict:
                for ix in self._nt_dict[nt]:
                    yield self._states[ix]

        def cleanup(self):
            """ Get rid of temporary data once the parser has moved past this column """
            self._set = None
            self._matches = None
            # Keep the states themselves for diagnostics and debugging

        def __len__(self):
            """ Return the number of states in the column """
            return self._numstates

        def __getitem__(self, index):
            """ Return the state at the given index position """
            return self._states[index]

        def __iter__(self):
            """ Return an iterator over the state list """
            return iter(self._states)

        def info(self, parser):
            """ Return a list of the parser states within this column in a 'readable' format """

            def readable(s):
                """ Return a 'readable' form of parser state s where
                    item indices have been converted to object references """
                nt, dot, prod, i, w = s
                return (parser._lookup(nt), dot, [parser._lookup(t) for t in prod], i)

            return [readable(s) for s in self._states if s[1] > 0] # Skip states with the dot at the beginning


    class Node:

        """ Shared Packed Parse Forest (SPPF) node representation.

            A node label is a tuple (s, j, i) where s can be
            (a) a nonterminal, for completed productions;
            (b) a token corresponding to a terminal;
            (c) a (nonterminal, dot, prod) tuple, for partially parsed productions.

            j and i are the start and end token indices, respectively.

        """

        def __init__(self, parser, label):
            """ Initialize a SPPF node with a given label tuple """
            # assert isinstance(label, tuple)
            if isinstance(label[0], int):
                # Convert the label from (nt-index, i, j) to (nt, i, j)
                assert label[0] < 0 # Nonterminal indices are negative
                label = (parser._nonterminals[label[0]], label[1], label[2])
            self._label = label
            self._families = None # Families of children

        def add_family(self, parser, prod, children):
            """ Add a family of children to this node, in parallel with other families """
            # Note which production is responsible for this subtree,
            # to help navigate the tree in case of ambiguity

            prod = [parser._lookup(ix) for ix in prod]
            pc_tuple = (prod, children)
            if self._families is None:
                self._families = [ pc_tuple ]
                return
            if pc_tuple not in self._families:
                self._families.append(pc_tuple)

        def label(self):
            """ Return the node label """
            return self._label

        def start(self):
            """ Return the start token index """
            return self._label[1]

        def end(self):
            """ Return the end token index """
            return self._label[2]

        def head(self):
            """ Return the 'head' of this node, i.e. a top-level readable name for it """
            return self._label[0]

        def is_ambiguous(self):
            """ Return True if this node has more than one family of children """
            return self._families and len(self._families) >= 2

        def is_interior(self):
            """ Returns True if this is an interior node (partially parsed production) """
            return isinstance(self._label[0], tuple)

        def is_completed(self):
            """ Returns True if this is a node corresponding to a completed nonterminal """
            return isinstance(self._label[0], Nonterminal)

        def is_token(self):
            """ Returns True if this is a token node """
            return isinstance(self._label[0], Token)

        def has_children(self):
            """ Return True if there are any families of children of this node """
            return bool(self._families)

        def is_empty(self):
            """ Return True if there is only a single empty family of this node """
            if not self._families:
                return True
            return len(self._families) == 1 and self._families[0][1] == None

        def enum_children(self):
            """ Enumerate families of children """
            if self._families:
                for prod, c in self._families:
                    yield (prod, c)

        def __hash__(self):
            """ Make this node hashable """
            return id(self).__hash__()

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

        def __str__(self):
            """ Return a string representation of this node """
            return str(self.head())


    def __init__(self, g):

        """ Initialize a parser for a given grammar """

        nt_d = g.nt_dict()
        r = g.root()
        assert nt_d is not None
        assert r is not None
        assert r in nt_d
        # Convert the grammar to integer index representation for speed
        self._root = r.index()
        # Make new grammar dictionary keyed by nonterminal index
        self._nt_dict = { }
        for nt, plist in nt_d.items():
            self._nt_dict[nt.index()] = None if plist is None else [ p.prod() for p in plist ]
        # Make a dictionary of nonterminals from the grammar
        # keyed by the nonterminal index instead of its name
        self._nonterminals = { }
        for nt in g.nonterminals().values():
            assert nt.index() not in self._nonterminals
            self._nonterminals[nt.index()] = nt
        # Make a dictionary of terminals from the grammar
        # keyed by the terminal index instead of its name
        self._terminals = { }
        for t in g.terminals().values():
            assert t.index() not in self._terminals
            self._terminals[t.index()] = t


    @classmethod
    def for_grammar(cls, g):
        """ Create a Parser for the Grammar in g """
        return cls(g)


    def go(self, tokens):

        """ Parse the token stream and return a forest of nodes using
            the Earley algorithm as improved by Scott (referencing Tomita).

            The parser handles ambiguity, returning alternative options within
            a single packed tree.

            Comments refer to the EARLEY_PARSER pseudocode given in the
            Scott/Johnstone paper, cf. the reference at the top of this module.

        """

        def _make_node(nt_B, dot, prod, j, i, w, v, V):
            """ MAKE_NODE(B ::= αx · β, j, i, w, v, V) """
            len_prod = len(prod)
            if dot == 1 and len_prod >= 2:
                # α is empty and β is nonempty: return v
                return v
            # Create a label for the new node
            if dot >= len_prod:
                # β is empty (i.e. the nonterminal B is complete)
                s = nt_B
            else:
                # Intermediate position within production of B
                s = (nt_B, dot, prod)
            # If there is no node y ∈ V labelled (s, j, i),
            # create one and add it to V
            label = (s, j, i)
            if label in V:
                y = V[label]
            else:
                V[label] = y = Parser.Node(self, label)
            # assert v is not None
            if w is None:
                y.add_family(self, prod, v)
            else:
                # w is an already built subtree that we're putting a new
                # node on top of
                y.add_family(self, prod, (w, v)) # The code breaks if this is modified!
            return y

        def _push(newstate, _E, _Q):
            """ Append a new state to an Earley column (_E) and a look-ahead set (_Q), as appropriate """
            # (N ::= α·δ, h, y)
            # newstate = (N, dot, prod, h, y)

            dot, prod = newstate[1], newstate[2]
            item = 0 if dot >= len(prod) else prod[dot]
            if item <= 0:
                # Nonterminal or epsilon
                # δ ∈ ΣN
                _E.add(newstate)
            elif _E.matches(self._terminals[item]):
                # Terminal matching the current token
                _Q.append(newstate)

        # V = ∅
        V = { }

        n = len(tokens)
        # Initialize the Earley columns
        E = [ Parser.EarleyColumn(tokens[i] if i < n else None) for i in range(n + 1) ]
        E0 = E[0]
        Q0 = [ ]

        # Populate column 0 (E0) with start states and Q0 with lookaheads
        for root_p in self._nt_dict[self._root]:
            # Go through root productions
            newstate = (self._root, 0, root_p, 0, None)
            # add (S ::= ·α, 0, null) to E0 and Q0
            _push(newstate, E0, Q0)

        # Step through the Earley columns
        for i, Ei in enumerate(E):
            # The agenda set R is Ei[j..len(Ei)]
            if not Ei and not Q0:
                # Parse options exhausted, nothing to do
                raise ParseError("No parse available at token {0} ({1})"
                    .format(i, tokens[i-1]), i-1, E[i-1].info(self)) # Token index is 1-based
            j = 0
            H = defaultdict(list)
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
                if dot < len_prod and prod[dot] < 0: # Nonterminal
                    # Earley predictor
                    # for all (C ::= δ) ∈ P:
                    nt_C = prod[dot]
                    # Go through all right hand sides of non-terminal nt_C
                    for p in self._nt_dict[nt_C]:
                        # if δ ∈ ΣN and (C ::= ·δ, i, null) !∈ Ei:
                        newstate = (nt_C, 0, p, i, None)
                        _push(newstate, Ei, Q)
                    # if ((C, v) ∈ H):
                    for v in H.get(nt_C, []):
                        # y = MAKE_NODE(B ::= αC · β, h, i, w, v, V)
                        y = _make_node(nt_B, dot + 1, prod, h, i, w, v, V)
                        newstate = (nt_B, dot + 1, prod, h, y)
                        _push(newstate, Ei, Q)
                # if Λ = (D ::= α·, h, w):
                elif dot >= len_prod:
                    # Earley completer
                    if not w:
                        label = (nt_B, i, i)
                        if label in V:
                            w = v = V[label]
                        else:
                            w = v = V[label] = Parser.Node(self, label)
                        w.add_family(self, prod, None) # Add e (empty production) as a family
                    if h == i:
                        # Empty production satisfied
                        H[nt_B].append(w) # defaultdict automatically creates an empty list
                    # for all (A ::= τ · Dδ, k, z) in Eh:
                    for st0 in E[h].enum_nt(nt_B):
                        nt_A, dot0, prod0, k, z = st0
                        y = _make_node(nt_A, dot0 + 1, prod0, k, i, z, w, V)
                        newstate = (nt_A, dot0 + 1, prod0, k, y)
                        _push(newstate, Ei, Q)

            V = { }
            if Q:
                label = (tokens[i], i, i + 1)
                v = Parser.Node(self, label)
            while Q:
                # Earley scanner
                # Remove an element, Λ = (B ::= α · ai+1β, h, w) say, from Q
                state = Q.pop()
                nt_B, dot, prod, h, w = state
                # assert isinstance(prod[dot], Terminal)
                # assert tokens[i].matches(prod[dot])
                # y = MAKE_NODE(B ::= αai+1 · β, h, i + 1, w, v, V)
                y = _make_node(nt_B, dot + 1, prod, h, i + 1, w, v, V)
                newstate = (nt_B, dot + 1, prod, h, y)
                _push(newstate, E[i + 1], Q0)

            # Discard unnecessary cache stuff from memory
            Ei.cleanup()

        # if (S ::= τ ·, 0, w) ∈ En: return w
        for nt, dot, prod, k, w in E[n]:
            if nt == self._root and dot >= len(prod) and k == 0:
                # Completed production that spans the entire chart: we're done
                return w

        # No parse at last token
        raise ParseError("No parse available at token {0} ({1})"
            .format(n, tokens[n-1]), n - 1, E[n].info(self)) # Token index is 1-based


    def go_no_exc(self, tokens):
        """ Simple version of go() that returns None instead of throwing ParseError """
        try:
            return self.go(tokens)
        except ParseError:
            return None


    def _lookup(self, ix):
        """ Convert a production item from an index to an object reference """
        return self._nonterminals[ix] if ix < 0 else self._terminals[ix]


    @staticmethod
    def print_parse_forest(w, detailed = False):
        """ Print an Earley-Scott-Tomita SPPF parse forest in a nice indented format """

        def _print_helper(w, level, index, parent):
            """ Print the node w at the given indentation level """
            indent = "  " * level # Two spaces per indent level
            if w is None:
                # Epsilon node
                print(indent + "(empty)")
                return
            if w.is_token():
                p = parent[index]
                assert isinstance(p, Terminal)
                if detailed:
                    print("{0} [{1}] {2}: {3}".format(indent, index, p, w))
                else:
                    print("{0} {1}: {2}".format(indent, p, w))
                return
            # Interior nodes are not printed
            # and do not increment the indentation level
            if detailed or not w.is_interior():
                h = str(w)
                if (h.endswith("?") or h.endswith("*")) and w.is_empty():
                    # Skip printing optional nodes that don't contain anything
                    return
                print(indent + h)
                if not w.is_interior():
                    level += 1
            ambig = w.is_ambiguous()
            for ix, pc in enumerate(w.enum_children()):
                prod, f = pc
                if ambig:
                    # Identify the available parse options
                    print(indent + "Option " + str(ix + 1) + ":")
                if w.is_completed():
                    # Completed nonterminal: start counting children from zero
                    child_ix = -1
                    # parent = w
                else:
                    child_ix = index
                if isinstance(f, tuple):
                    # assert len(f) == 2
                    child_ix -= 1
                    #print("{0}Tuple element 0:".format(indent))
                    _print_helper(f[0], level, child_ix, prod)
                    #print("{0}Tuple element 1:".format(indent))
                    _print_helper(f[1], level, child_ix + 1, prod)
                else:
                    _print_helper(f, level, child_ix, prod)

        _print_helper(w, 0, 0, None)


    @staticmethod
    def num_combinations(w):
        """ Count the number of possible parse trees in the given forest """

        if w is None or w.is_token():
            # Empty (epsilon) node or token node
            return 1
        comb = 0
        for _, f in w.enum_children():
            if isinstance(f, tuple):
                cnt = 1
                for c in f:
                    cnt *= Parser.num_combinations(c)
                comb += cnt
            else:
                comb += Parser.num_combinations(f)
        return comb if comb > 0 else 1


    @staticmethod
    def make_schema(w):
        """ Create a flattened parse schema from the forest w """

        class CC:
            """ Manages choice coordinates """

            stack = []
            level = 0

            @classmethod
            def push(cls, option):
                """ Identify each option subtree with a different root index """
                cls.level += 1
                while len(cls.stack) < cls.level:
                    cls.stack.append(0)
                r = cls.stack[cls.level - 1]
                cls.stack[cls.level - 1] += 1
                return r

            @classmethod
            def pop(cls):
                """ Maintain one level count above the now current level """
                while len(cls.stack) > cls.level:
                    cls.stack.pop()
                cls.level -= 1

            @classmethod
            def coord(cls):
                return tuple(cls.stack[0:cls.level])

        def _part(w, level, index, parent, suffix):
            """ Return a tuple (colheading + options, start_token, end_token, partlist, info)
                where the partlist is again a list of the component schemas - or a terminal
                matching a single token - or None if empty """
            if w is None:
                # Epsilon node: return empty list
                return None
            if w.is_token():
                p = parent[index]
                assert isinstance(p, Terminal)
                return ([ level ] + suffix, w.start(), w.end(), None, (p, w.head().text()))
            # Interior nodes are not returned
            # and do not increment the indentation level
            if not w.is_interior():
                level += 1
            # Accumulate the resulting parts
            plist = [ ]
            ambig = w.is_ambiguous()
            add_suffix = [ ]

            for ix, pc in enumerate(w.enum_children()):
                prod, f = pc
                if ambig:
                    # Uniquely identify the available parse options with a coordinate
                    add_suffix = [ ix ]
                if w.is_completed():
                    # Completed nonterminal: start counting children from the last one
                    child_ix = -1
                    # parent = w
                else:
                    # Interior node: continue the indexing from where we left off
                    child_ix = index

                def add_part(p):
                    """ Add a subtuple p to the part list plist """
                    if p:
                        if p[0] is None:
                            # p describes an interior node
                            plist.extend(p[3])
                        elif p[2] > p[1]:
                            # Only include subtrees that actually contain terminals
                            plist.append(p)

                if isinstance(f, tuple):
                    # len(f) is always 2
                    child_ix -= 1
                    add_part(_part(f[0], level, child_ix, prod, suffix + add_suffix))
                    add_part(_part(f[1], level, child_ix + 1, prod, suffix + add_suffix))
                else:
                    add_part(_part(f, level, child_ix, prod, suffix + add_suffix))

            if w.is_interior():
                # Interior node: relay plist up the tree
                return (None, 0, 0, plist, None)
            # Completed nonterminal
            assert w.is_completed()
            assert isinstance(w.head(), Nonterminal)
            return ([ level - 1] + suffix, w.start(), w.end(), plist, w.head())

        if w is None:
            return None
        # !!! DEBUG
        #Parser.print_parse_forest(w, True)
        return _part(w, 0, 0, None, [ ])


    @staticmethod
    def make_grid(w):
        """ Make a 2d grid from a flattened parse schema """
        if w is None:
            return None
        schema = Parser.make_schema(w)
        assert schema[1] == 0
        cols = [] # The columns to be populated
        NULL_TUPLE = tuple()

        def _traverse(p):
            """ Traverse a schema subtree and insert the nodes into their
                respective grid columns """
            # p[0] is the coordinate of this subtree (level + suffix)
            # p[1] is the start column of this subtree
            # p[2] is the end column of this subtree
            # p[3] is the subpart list
            # p[4] is the nonterminal or terminal/token at the head of this subtree
            col, option = p[0][0], p[0][1:] # Level of this subtree and option

            if not option:
                # No option: use a 'clean key' of NULL_TUPLE
                option = NULL_TUPLE
            else:
                # Convert list to a frozen (hashable) tuple
                option = tuple(option)

            while len(cols) <= col:
                # Add empty columns as required to reach this level
                cols.append(dict())

            # Add a tuple describing the rows spanned and the node info
            assert isinstance(p[4], Nonterminal) or isinstance(p[4], tuple)
            if option not in cols[col]:
                # Put in a dictionary entry for this option
                cols[col][option] = []
            cols[col][option].append((p[1], p[2], p[4]))

            # Navigate into subparts, if any
            if p[3]:
                for subpart in p[3]:
                    _traverse(subpart)

        _traverse(schema)
        # Return a tuple with the grid and the number of tokens
        return (cols, schema[2])

