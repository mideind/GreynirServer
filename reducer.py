"""
    Reynir: Natural language processing for Icelandic

    Reducer module

    Author: Vilhjalmur Thorsteinsson

    This software is at a very early development stage.
    While that is the case, it is:
    Copyright (c) 2015 Vilhjalmur Thorsteinsson
    All rights reserved

    The classes within this module attempt to reduce a parse forest containing
    multiple possible parses of a sentence to a single most likely parse tree.

"""

#from flask import current_app
#
#def debug():
#   # Call this to trigger the Flask debugger on purpose
#   assert current_app.debug == False, "Don't panic! You're here by request of debug()"


class Reducer:

    """ Reduces a parse tree to a single most likely parse """

    def __init__(self):

        pass

    def go(self, forest):

        """ Return a single most likely parse within a forest of potential parses """

        if not forest:
            return None
        w = forest
        # Check that we have the expected forest root node
        assert w.is_completed and str(w) == "S0"
        # Give the child trees priority in the given order (lowest number means highest priority),
        # with VenjulegSetning on top
        # self._reduce(w) # !!! DEBUG
        w.reduce_by_priority( { "VenjulegSetning" : 0, "Spurning" : 1, "Grein" : 2, "Fyrirsögn" : 3 })
        return w

    def _reduce(self, w):
        """ Reduce a forest with a root in w """

        def _reduce_helper(w, level, index, parent, file = None):
            """ Reduce from w """
            indent = "  " * level # Two spaces per indent level
            if w is None:
                # Epsilon node
                print(indent + "(empty)", file = file)
                return
            if w.is_token:
                p = parent[index]
                # p is a Nonterminal
                print(indent + "[{0}] {1}: {2}".format(index, p, w), file = file)
                return
            h = str(w)
            if (h.endswith("?") or h.endswith("*")) and w.is_empty:
                # Skip printing optional nodes that don't contain anything
                return
            print(indent + h, file = file)
            if not w.is_interior:
                level += 1
            ambig = w.is_ambiguous
            for ix, pc in enumerate(w.enum_children()):
                prod, f = pc
                if ambig:
                    # Identify the available parse options
                    print(indent + "Option " + str(ix + 1) + ":", file = file)
                if w.is_completed:
                    # Completed nonterminal: start counting children from zero
                    child_ix = -1
                    # parent = w
                else:
                    child_ix = index
                if isinstance(f, tuple):
                    # assert len(f) == 2
                    child_ix -= 1
                    #print("{0}Tuple element 0:".format(indent))
                    _reduce_helper(f[0], level, child_ix, prod)
                    #print("{0}Tuple element 1:".format(indent))
                    _reduce_helper(f[1], level, child_ix + 1, prod)
                else:
                    _reduce_helper(f, level, child_ix, prod)

        _reduce_helper(w, 0, 0, None)


