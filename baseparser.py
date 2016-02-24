"""
    Reynir: Natural language processing for Icelandic

    Parser base module

    Copyright (c) 2016 Vilhjalmur Thorsteinsson
    All rights reserved

    This module defines a base parser class. The base is used in
    BIN_Parser (see binparser.py) which is again the base of the
    C++ Earley parser Fast_Parser (see fastparser.py)

"""

from collections import defaultdict

from grammar import Nonterminal, Terminal, Token


class Base_Parser:

    """ Parses a sequence of tokens according to a given grammar and
        a root nonterminal within that grammar, returning a forest of
        possible parses. The parses uses an optimized Earley algorithm.
    """

    # Parser version - change when logic changes so that output is affected
    _VERSION = "1.0"

    class PackedProduction:

        """ A container for a packed production, i.e. a grammar Production
            where the component terminals and nonterminals have been packed
            into a list of integer indices """

        def __init__(self, priority, production):
            # Store the relative priority of this production within its nonterminal
            self._priority = priority
            # Keep a reference to the original production
            self._production = production
            # Store the packed list of indices
            self._ix_list = production.prod
            # Cache the length
            self._len = len(self._ix_list)
            # Cache the hash
            self._hash = production.__hash__()

        @property
        def production(self):
            return self._production

        @property
        def priority(self):
            return self._priority

        def __hash__(self):
            return self._hash

        def __getitem__(self, index):
            return self._ix_list[index] if index < self._len else 0

        def __len__(self):
            return self._len

        def __eq__(self, other):
            return id(self) == id(other)

        def __iter__(self):
            return iter(self._ix_list)


    def __init__(self, g):

        """ Initialize a parser for a given grammar """

        nt_d = g.nt_dict
        r = g.root
        assert nt_d is not None
        assert r is not None
        assert r in nt_d
        # Convert the grammar to integer index representation for speed
        self._root = r.index
        # Make new grammar dictionary, keyed by nonterminal index and
        # containing packed productions with integer indices
        self._nt_dict = { }
        for nt, plist in nt_d.items():
            self._nt_dict[nt.index] = None if plist is None else \
                [ Base_Parser.PackedProduction(prio, p) for prio, p in plist ]
        self._nonterminals = g.nonterminals_by_ix
        self._terminals = g.terminals_by_ix


    @classmethod
    def for_grammar(cls, g):
        """ Create a parser for the Grammar in g """
        return cls(g)


    def _lookup(self, ix):
        """ Convert a production item from an index to an object reference """
        assert ix != 0
        return self._nonterminals[ix] if ix < 0 else self._terminals[ix]


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
            if w.is_token:
                p = parent.production[index]
                assert isinstance(p, Terminal)
                return ([ level ] + suffix, w.start, w.end, None, (p, w.head.text))
            # Interior nodes are not returned
            # and do not increment the indentation level
            if not w.is_interior:
                level += 1
            # Accumulate the resulting parts
            plist = [ ]
            ambig = w.is_ambiguous
            add_suffix = [ ]

            for ix, pc in enumerate(w.enum_children()):
                prod, f = pc
                if ambig:
                    # Uniquely identify the available parse options with a coordinate
                    add_suffix = [ ix ]
                if w.is_completed:
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

            if w.is_interior:
                # Interior node: relay plist up the tree
                return (None, 0, 0, plist, None)
            # Completed nonterminal
            assert w.is_completed
            assert isinstance(w.head, Nonterminal)
            return ([level - 1] + suffix, w.start, w.end, plist, w.head)

        if w is None:
            return None
        return _part(w, 0, 0, None, [ ])


    @staticmethod
    def make_grid(w):
        """ Make a 2d grid from a flattened parse schema """
        if w is None:
            return None
        schema = Base_Parser.make_schema(w)
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


