"""
    Reynir: Natural language processing for Icelandic

    Reducer module

    Author: Vilhjalmur Thorsteinsson

    This software is at a very early development stage.
    While that is the case, it is:
    Copyright (c) 2015 Vilhjalmur Thorsteinsson
    All rights reserved

    The classes within this module reduce a parse forest containing
    multiple possible parses of a sentence to a single most likely
    parse tree.

    The reduction uses three methods:

  * First, a dictionary of preferred
    token interpretations (fetched from Reynir.conf), where words
    like 'ekki' are classified as being more likely to be from one
    category than another (in this case adverb rather than noun);
  * Second, a set of general heuristics (adverbs being by default less
    preferred than other categories, etc.);
  * Third, production priorities within nonterminals, as specified
    using > signs between productions in Reynir.grammar.

"""

from collections import defaultdict

from grammar import Terminal, Nonterminal
from settings import Preferences
from fastparser import ParseForestNavigator


class Reducer:

    """ Reduces a parse forest to a single most likely parse tree """

    def __init__(self):
        pass

    def go(self, forest):

        """ Returns the argument forest after pruning it down to a single tree """

        if forest is None:
            return None
        w = forest

        # First pass: for each token, find the possible terminals that
        # can correspond to that token
        finals = defaultdict(set)
        tokens = dict()
        self._find_options(w, finals, tokens)

        # Second pass: find a (partial) ordering by scoring the terminal alternatives for each token
        scores = dict()
        # Loop through the indices of the tokens spanned by this tree
        for i in range(w.start, w.end):
            s = finals[i]
            # Initially, each alternative has a score of 0
            scores[i] = { terminal: 0 for terminal in s }
            if len(s) > 1:
                # More than one terminal in the option set
                # Calculate the relative scores
                # Find out whether the first part of all the terminals are the same
                same_first = len(set(x.first for x in s)) == 1
                txt = tokens[i].lower
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
                                        #print("Preference: increasing score of {1}, decreasing score of {0}".format(wt, bt))
                                        if bt.name[0] in "\"'":
                                            # Literal terminal: be even more aggressive in promoting it
                                            sc[wt] -= 2
                                            sc[bt] += 6
                                        else:
                                            sc[wt] -= 1
                                            sc[bt] += 4
                                        found_pref = True
                if not same_first and not found_pref:
                    # Only display cases where there might be a missing pref
                    print("Token '{0}' has {1} possible terminal matches: {2}".format(txt, len(s), s))
                if True: # not found_pref:
                    # print("Found no preference that applies to token '{0}'; applying heuristics".format(txt))
                    # Apply heuristics
                    for t in s:
                        if t.first == "ao" or t.first == "eo":
                            # Subtract from the score of all ao and eo
                            sc[t] -= 1
                        elif t.first == "no":
                            if t.is_singular:
                                # Add to singular nouns relative to plural ones
                                sc[t] += 1
                            elif t.is_abbrev:
                                # Punish abbreviations in favor of other more specific terminals
                                sc[t] -= 1
                        elif t.first == "tala" or t.first == "töl":
                            # A complete 'töl' or 'no' is better (has more info) than a rough 'tala'
                            if t.first == "tala":
                                sc[t] -= 1
                            # Discourage possessive ('ef') meanings for numbers
                            for pt in s:
                                if (pt.first == "no" or pt.first == "töl") and pt.has_variant("ef"):
                                    sc[pt] -= 1
                        elif t.first == "fs":
                            if t.has_variant("nf"):
                                # Reduce the weight of the 'artificial' nominative prepositions
                                # 'næstum', 'sem', 'um'
                                sc[t] -= 2
                            else:
                                # Else, give a bonus for each matched preposition
                                sc[t] += 1
                        elif t.first == "so":
                            if t.variant(0) in "012":
                                # Give a bonus for verb arguments: the more matched, the better
                                sc[t] += int(t.variant(0))
                            if t.is_sagnb:
                                # We like sagnb and lh, it means that more
                                # than one piece clicks into place
                                print("Giving bonus for sagnb, token '{0}', terminal {1}".format(txt, t))
                                sc[t] += 2
                            elif t.is_lh:
                                # sagnb is preferred to lh
                                sc[t] += 1
                            if t.is_subj:
                                # Give a small bonus for subject matches
                                if t.has_variant("none"):
                                    # ... but a punishment for subj_none
                                    sc[t] -= 1
                                else:
                                    sc[t] += 1
                            if t.is_nh:
                                if (i > 0) and any(pt.first == 'nhm' for pt in finals[i - 1]):
                                    # Give a bonus for adjacent nhm + so_nh terminals
                                    sc[t] += 2 # Prop up the verb terminal with the nh variant
                                    for pt in scores[i - 1].keys():
                                        if pt.first == 'nhm':
                                            # Prop up the nhm terminal
                                            scores[i - 1][pt] += 2
                                if any(pt.first == "no" and pt.has_variant("ef") and pt.is_plural for pt in s):
                                    # If this is a so_nh and an alternative no_ef_ft exists, choose this one
                                    # (for example, 'hafa', 'vera', 'gera', 'fara', 'mynda', 'berja', 'borða')
                                    sc[t] += 2
                        elif t.name[0] in "\"'":
                            # Give a bonus for exact or semi-exact matches
                            #print("Giving bonus for exact match of {0}".format(t.name))
                            sc[t] += 1

        # Third pass: navigate the tree bottom-up, eliminating lower-rated
        # options (subtrees) in favor of higher rated ones

        self._reduce(w, scores)

        return w

    def _find_options(self, w, finals, tokens):
        """ Find token-terminal match options in a parse forest with a root in w """

        class OptionFinder(ParseForestNavigator):

            """ Subclass to navigate a parse forest and populate the set
                of terminals that match each token """

            def _visit_token(self, level, node):
                """ At token node """
                assert node.terminal is not None
                assert isinstance(node.terminal, Terminal)
                finals[node.start].add(node.terminal)
                tokens[node.start] = node.token
                return None

        OptionFinder().go(w)

    def _reduce(self, w, scores):
        """ Reduce a forest with a root in w based on subtree scores """

        class ParseForestReducer(ParseForestNavigator):

            """ Subclass to navigate a parse forest and reduce it
                so that the highest-scoring family of children survives
                at each place of ambiguity """

            def __init__(self, scores):
                super().__init__()
                self._scores = scores

            def _visit_epsilon(self, level):
                """ At Epsilon node """
                return 0 # Score 0

            def _visit_token(self, level, node):
                """ At token node """
                # Return the score of this token/terminal match
                return self._scores[node.start][node.terminal]

            def _visit_nonterminal(self, level, node):
                """ At nonterminal node """
                # Return a fresh object to collect results
                class ReductionInfo:
                    def __init__(self):
                        self.sc = defaultdict(int) # Child tree scores
                        # We are only interested in completed nonterminals
                        self.nt = node.nonterminal if node.is_completed else None
                        assert self.nt is None or isinstance(self.nt, Nonterminal)
                        self.highest_prio = None # The priority of the highest-priority child, if any
                        self.use_prio = False
                        self.highest_ix = None # List of children with that priority
                    def add_child_score(self, ix, sc):
                        """ Add a child node's score to the parent's score """
                        self.sc[ix] += sc
                    def add_child_production(self, ix, prod):
                        """ Add a family of children to the priority pool """
                        if self.nt is None:
                            # Not a completed nonterminal; priorities don't apply
                            return
                        prio = prod.priority
                        if self.highest_prio is not None and prio != self.highest_prio:
                            # Note that there are different priorities
                            self.use_prio = True
                        if self.highest_prio is None or prio < self.highest_prio:
                            # Note: lower number means higher priority ;-)
                            self.highest_prio = prio
                            self.highest_ix = { ix }
                        elif prio == self.highest_prio:
                            # Another child with the same (highest) priority
                            self.highest_ix.add(ix)
                return ReductionInfo()

            def _visit_family(self, results, level, w, ix, prod):
                """ Add information about a family of children to the result object """
                results.add_child_production(ix, prod)

            def _add_result(self, results, ix, sc):
                """ Append a single result to the result object """
                # Add up scores for each family of children
                results.add_child_score(ix, sc)

            def _process_results(self, results, node):
                """ Sort scores after visiting children """
                csc = results.sc
                if results.use_prio:
                    # There is a priority ordering between the productions
                    # of this nonterminal: remove those child trees from
                    # consideration that do not have the highest priority
                    #print("Reducing set of child nodes by production priority")
                    #for ix, sc in csc.items():
                    #    prod, prio = node._families[ix]
                    #    print("Family {0}: prod {1} priority {2} highest {3}"
                    #        .format(ix, prod.production, prod.priority, ix in results.highest_ix))
                    csc = { ix: sc for ix, sc in csc.items() if ix in results.highest_ix }
                assert csc
                if len(csc) == 1 and not results.use_prio:
                    # Not ambiguous: only one result
                    [ sc ] = csc.values() # Will raise an exception if not exactly one value
                else:
                    # Eliminate all families except the best scoring one
                    # Sort in decreasing order by score
                    s = sorted(csc.items(), key = lambda x: x[1], reverse = True)
                    ix, sc = s[0] # This is the best scoring family
                    node.reduce_to(ix)
                return sc

        ParseForestReducer(scores).go(w)
