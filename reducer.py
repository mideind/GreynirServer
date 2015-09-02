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

from collections import defaultdict
from grammar import Terminal
from settings import Preferences

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
        assert w.start == 0
        # Give the child trees priority in the given order (lowest number means highest priority),
        # with VenjulegSetning on top
        # self._reduce(w) # !!! DEBUG
        w.reduce_by_priority( { "VenjulegSetning" : 0, "Spurning" : 1, "Grein" : 2, "Fyrirsögn" : 3 })

        print("\nReducer.go assuming {0} final terminals".format(w.end))

        # First pass: for each token, find the possible terminals that
        # can correspond to that token
        finals = defaultdict(set)
        tokens = dict()
        self._find_options(w, finals, tokens)

        # Second pass: find a (partial) ordering by scoring the terminal alternatives for each token
        scores = dict()
        for i in range(w.end):
            s = finals[i]
            # Initially, each alternative has a score of 0
            scores[i] = { terminal: 0 for terminal in s }
            if len(s) > 1:
                # More than one terminal in the option set
                # Calculate the relative scores
                # Find out whether the first part of all the terminals are the same
                same_first = len(set(x.first for x in s)) == 1
                txt = tokens[i].lower
                print("Token '{0}' has {1} possible terminal matches: {2}".format(txt, len(s), s))
                # No need to check preferences if the first parts of all possible terminals are equal
                prefs = None if same_first else Preferences.get(txt)
                found_pref = False
                sc = scores[i]
                if prefs:
                    for worse, better in prefs:
                        for wt in s:
                            if wt.first in worse:
                                for bt in s:
                                    if wt is not bt and bt.first in better:
                                        print("Preference: increasing score of {1}, decreasing score of {0}".format(wt, bt))
                                        sc[wt] -= 2
                                        sc[bt] += 4
                                        found_pref = True
                if not found_pref:
                    print("Found no preference that applies to token '{0}'; applying heuristics".format(txt))
                    # Apply heuristics
                    for t in s:
                        if t.first == "ao" or t.first == "eo":
                            # Subtract from the score of all ao and eo
                            sc[t] -= 1
                        elif t.first == "no" and t.has_vbit_et():
                            # Add to singular nouns relative to plural ones
                            sc[t] += 1
                        elif t.first == "so" and t.variant(0) in "012":
                            # Give a bonus for verb arguments: the more matched, the better
                            sc[t] += int(t.variant(0))
                        elif t.name[0] in "\"'":
                            # Give a bonus for exact or semi-exact matches
                            sc[t] += 1
                    # !!! Add a heuristic to promote adjacent nhm + so_nh

        # Third pass: navigate the tree bottom-up, eliminating lower-rated
        # options (subtrees) in favor of higher rated ones

        self._reduce(w, scores)

        return w

    def _find_options(self, w, finals, tokens):
        """ Find token-terminal match options in a parse forest with a root in w """

        visited = set()

        def _opt_helper(w, index, parent):
            """ Find options from w """
            if w is None:
                # Epsilon node
                return
            if w.is_token:
                p = parent[index]
                assert isinstance(p, Terminal)
                finals[w.start].add(p)
                tokens[w.start] = w.head
                return
            if w.label in visited:
                return
            visited.add(w.label)
            for ix, pc in enumerate(w.enum_children()):
                prod, f = pc
                if w.is_completed:
                    # Completed nonterminal: start counting children from zero
                    child_ix = -1
                    # parent = w
                else:
                    child_ix = index
                if isinstance(f, tuple):
                    child_ix -= 1
                    _opt_helper(f[0], child_ix, prod)
                    _opt_helper(f[1], child_ix + 1, prod)
                else:
                    _opt_helper(f, child_ix, prod)

        _opt_helper(w, 0, None)

    def _reduce(self, w, scores):
        """ Reduce a forest with a root in w based on subtree scores """

        visited = dict()

        def _reduce_helper(w, index, parent):
            """ Reduce from w """
            if w is None:
                # Epsilon node
                return 0
            if w.is_token:
                p = parent[index]
                assert isinstance(p, Terminal)
                # Return the score of this terminal option
                return scores[w.start][p]
            if w.label in visited:
                # Already seen: return the previously calculated score
                return visited[w.label]
            # List of child scores
            csc = []
            for ix, pc in enumerate(w.enum_children()):
                prod, f = pc
                if w.is_completed:
                    # Completed nonterminal: start counting children from zero
                    child_ix = -1
                    # parent = w
                else:
                    child_ix = index
                sc = 0
                if isinstance(f, tuple):
                    child_ix -= 1
                    sc += _reduce_helper(f[0], child_ix, prod)
                    sc += _reduce_helper(f[1], child_ix + 1, prod)
                else:
                    sc += _reduce_helper(f, child_ix, prod)
                csc.append((ix, sc))

            assert csc
            if len(csc) == 1:
                # Not ambiguous: only one result
                assert csc[0][0] == 0
                sc = csc[0][1]
            else:
                # Eliminate all families except the best scoring one
                csc.sort(key = lambda x: x[1], reverse = True) # Sort in decreasing order by score
                # print("Reduce_to: at {0}, comparing scores {1}".format(str(w), csc))
                sc = csc[0][1]
                w.reduce_to(csc[0][0])

            visited[w.label] = sc
            return sc

        _reduce_helper(w, 0, None)


