"""
    Reynir: Natural language processing for Icelandic

    Reducer module

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

from fastparser import ParseForestNavigator
from grammar import Terminal
from settings import Preferences, VerbObjects


class Reducer:

    """ Reduces a parse forest to a single most likely parse tree """

    def __init__(self, grammar):
        self._grammar = grammar

    def go_with_score(self, forest):

        """ Returns the argument forest after pruning it down to a single tree """

        if forest is None:
            return (None, 0)
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

            #print("Reducing token '{0}'; scores dict initialized to:\n{1}".format(tokens[i].t1, scores[i]))

            if len(s) > 1:
                # More than one terminal in the option set
                # Calculate the relative scores
                # Find out whether the first part of all the terminals are the same
                same_first = len(set(x.first for x in s)) == 1
                txt = tokens[i].lower
                # No need to check preferences if the first parts of all possible terminals are equal
                # Look up the preference ordering from Reynir.conf, if any
                prefs = None if same_first else Preferences.get(txt)
                found_pref = False
                sc = scores[i]
                if prefs:
                    adj_worse = defaultdict(int)
                    adj_better = defaultdict(int)
                    for worse, better, factor in prefs:
                        for wt in s:
                            if wt.first in worse:
                                for bt in s:
                                    if wt is not bt and bt.first in better:
                                        if bt.name[0] in "\"'":
                                            # Literal terminal: be even more aggressive in promoting it
                                            adj_w = -2 * factor
                                            adj_b = +6 * factor
                                        else:
                                            adj_w = -2 * factor
                                            adj_b = +4 * factor
                                        adj_worse[wt] = min(adj_worse[wt], adj_w)
                                        adj_better[bt] = max(adj_better[bt], adj_b)
                                        found_pref = True
                    for wt, adj in adj_worse.items():
                        sc[wt] += adj
                    for bt, adj in adj_better.items():
                        sc[bt] += adj
                #if not same_first and not found_pref:
                #    # Only display cases where there might be a missing pref
                #    print("Token '{0}' has {1} possible terminal matches: {2}".format(txt, len(s), s))

                # Apply heuristics to each terminal that potentially matches this token
                for t in s:
                    tfirst = t.first
                    if tfirst == "ao" or tfirst == "eo":
                        # Subtract from the score of all ao and eo
                        sc[t] -= 1
                    elif tfirst == "no":
                        if t.is_singular:
                            # Add to singular nouns relative to plural ones
                            sc[t] += 1
                        elif t.is_abbrev:
                            # Punish abbreviations in favor of other more specific terminals
                            sc[t] -= 1
                    elif tfirst == "fs":
                        if t.has_variant("nf"):
                            # Reduce the weight of the 'artificial' nominative prepositions
                            # 'næstum', 'sem', 'um'
                            sc[t] -= 4 # Make other cases outweigh the Nl_nf bonus of +4 (-2 -3 = -5)
                        else:
                            # Else, give a bonus for each matched preposition
                            sc[t] += 2
                    elif tfirst == "so":
                        if t.variant(0) in "012":
                            # Consider verb arguments
                            # Normally, we give a bonus for verb arguments: the more matched, the better
                            numcases = int(t.variant(0))
                            adj = 2 * numcases
                            # !!! Logic should be added here to encourage zero arguments for verbs in 'miðmynd'
                            if numcases == 0:
                                # Zero arguments: we might not like this
                                if all((m.stofn not in VerbObjects.VERBS[0]) and ("MM" not in m.beyging)
                                    for m in tokens[i].t2 if m.ordfl == "so"):
                                    # No meaning where the verb has zero arguments
                                    adj = -4
                                #for m in tokens[i].t2:
                                #    if m.ordfl == "so" and m.stofn not in VerbObjects.VERBS[0]:
                                #        # We're using a verb with zero arguments but that form is not
                                #        # explicitly listed in Verbs.conf: discourage this
                                #        # print("Discouraging zero-arg use of verb '{0}' (stem '{1}')"
                                #        #    .format(txt, m.stofn))
                                #        adj = -2
                                #        break
                            # Apply score adjustments for verbs with particular object cases,
                            # as specified by $score(n) pragmas in Verbs.conf
                            for m in tokens[i].t2:
                                if m.ordfl == "so":
                                    key = m.stofn + t.verb_cases
                                    score = VerbObjects.SCORES.get(key)
                                    if score is not None:
                                        #print("Applying verb score adjustment of {1} to {0}".format(key, score))
                                        adj += score
                                        break
                            sc[t] += adj
                        if t.is_sagnb:
                            # We like sagnb and lh, it means that more
                            # than one piece clicks into place
                            sc[t] += 4
                        elif t.is_lh:
                            # sagnb is preferred to lh, but vb (veik beyging) is discouraged
                            if t.has_variant("vb"):
                                sc[t] -= 2
                            else:
                                sc[t] += 3
                        if t.is_subj:
                            # Give a small bonus for subject matches
                            if t.has_variant("none"):
                                # ... but a punishment for subj_none
                                sc[t] -= 3
                            else:
                                sc[t] += 1
                        if t.is_nh:
                            if (i > 0) and any(pt.first == 'nhm' for pt in finals[i - 1]):
                                # Give a bonus for adjacent nhm + so_nh terminals
                                sc[t] += 4 # Prop up the verb terminal with the nh variant
                                for pt in scores[i - 1].keys():
                                    if pt.first == 'nhm':
                                        # Prop up the nhm terminal
                                        scores[i - 1][pt] += 2
                                        # print("Propping up nhm for verb {1}, score is now {0}".format(scores[i-1][pt], tokens[i].t1))
                                        break
                            if any(pt.first == "no" and pt.has_variant("ef") and pt.is_plural for pt in s):
                                # If this is a so_nh and an alternative no_ef_ft exists, choose this one
                                # (for example, 'hafa', 'vera', 'gera', 'fara', 'mynda', 'berja', 'borða')
                                sc[t] += 4
                    elif tfirst == "tala" or tfirst == "töl":
                        # A complete 'töl' or 'no' is better (has more info) than a rough 'tala'
                        if tfirst == "tala":
                            sc[t] -= 1
                        # Discourage possessive ('ef') meanings for numbers
                        for pt in s:
                            if (pt.first == "no" or pt.first == "töl") and pt.has_variant("ef"):
                                sc[pt] -= 1
                    elif tfirst == "sérnafn":
                        if not tokens[i].t2:
                            # If there are no BÍN meanings, we had no choice but to use sérnafn,
                            # so alleviate some of the penalty given by the grammar
                            sc[t] += 4
                        else:
                            pass
                            #print("Meanings for sérnafn {0}:".format(tokens[i].t1))
                            #for m in tokens[i].t2:
                            #    print("{0}".format(m))
                        #        if m.stofn[0].isupper():
                        #            sc[t] -= 4 # Discourage 'sérnafn' if an uppercase BÍN meaning is available
                        #            break
                    elif t.name[0] in "\"'":
                        # Give a bonus for exact or semi-exact matches
                        sc[t] += 1

        # Third pass: navigate the tree bottom-up, eliminating lower-rated
        # options (subtrees) in favor of higher rated ones

        # Loop through the indices of the tokens spanned by this tree
        #for i in range(w.start, w.end):
        #    print("At token '{0}' scores dict is:\n{1}".format(tokens[i].t1, scores[i]))

        score = self._reduce(w, scores)

        return (w, score)

    def go(self, forest):
        """ Return only the reduced forest, without its score """
        w, _ = self.go_with_score(forest)
        return w

    @staticmethod
    def _find_options(w, finals, tokens):
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

            def __init__(self, grammar, scores):
                super().__init__()
                self._scores = scores
                self._grammar = grammar
                self._score_adj = grammar._nt_scores

            def _visit_epsilon(self, level):
                """ At Epsilon node """
                return 0 # Score 0

            def _visit_token(self, level, node):
                """ At token node """
                # Return the score of this token/terminal match
                # !!! DEBUG
                node.score = self._scores[node.start][node.terminal]
                return node.score
                # return self._scores[node.start][node.terminal]

            def _visit_nonterminal(self, level, node):
                """ At nonterminal node """
                # Return a fresh object to collect results
                class ReductionInfo:
                    def __init__(self):
                        self.sc = defaultdict(int) # Child tree scores
                        # We are only interested in completed nonterminals
                        self.nt = node.nonterminal if node.is_completed else None
                        self.highest_prio = None # The priority of the highest-priority child, if any
                        self.use_prio = False
                        self.highest_ix = None # List of children with that priority
                    def add_child_score(self, ix, sc):
                        """ Add a child node's score to the parent family's score """
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
                if results.nt is not None:
                    # Get score adjustment for this nonterminal, if any
                    sc += self._score_adj.get(results.nt, 0)
                # !!! DEBUG
                node.score = sc
                return sc

        return ParseForestReducer(self._grammar, scores).go(w)
