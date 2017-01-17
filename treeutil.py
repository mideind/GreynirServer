"""
    Reynir: Natural language processing for Icelandic

    TreeUtility class

    Copyright (c) 2016 Vilhjalmur Thorsteinsson
    All rights reserved
    See the accompanying README.md file for further licensing and copyright information.

    This module contains a class modeling an article originating from a scraped web page.

"""

import time
from collections import namedtuple

from fetcher import Fetcher
from tokenizer import TOK, tokenize, canonicalize_token
from fastparser import Fast_Parser, ParseForestNavigator
from incparser import IncrementalParser


WordTuple = namedtuple("WordTuple", ["stem", "cat"])


class TreeUtility:

    """ A wrapper around a set of static utility functions for working
        with parse trees and tokens """

    @staticmethod
    def _describe_token(t, terminal, meaning):
        """ Return a compact dictionary and a WordTuple describing the token t,
            which matches the given terminal with the given meaning """
        d = dict(x = t.txt)
        wt = None
        if terminal is not None:
            # There is a token-terminal match
            if t.kind == TOK.PUNCTUATION:
                if t.txt == "-":
                    # Hyphen: check whether it is matching an em or en-dash terminal
                    if terminal.cat == "em":
                        d["x"] = "—" # Substitute em dash (will be displayed with surrounding space)
                    elif terminal.cat == "en":
                        d["x"] = "–" # Substitute en dash
            else:
                # Annotate with terminal name and BÍN meaning (no need to do this for punctuation)
                d["t"] = terminal.name
                if meaning is not None:
                    if terminal.first == "fs":
                        # Special case for prepositions since they're really
                        # resolved from the preposition list in Main.conf, not from BÍN
                        m = (meaning.ordmynd, "fs", "alm", terminal.variant(0).upper())
                    else:
                        m = (meaning.stofn, meaning.ordfl, meaning.fl, meaning.beyging)
                    d["m"] = m
                    # Note the word stem and category
                    wt = WordTuple(stem = m[0].replace("-", ""), cat = m[1])
                elif t.kind == TOK.ENTITY:
                    wt = WordTuple(stem = t.txt, cat = "entity")
        if t.kind != TOK.WORD:
            # Optimize by only storing the k field for non-word tokens
            d["k"] = t.kind
        if t.val is not None and t.kind not in { TOK.WORD, TOK.ENTITY, TOK.PUNCTUATION }:
            # For tokens except words, entities and punctuation, include the val field
            if t.kind == TOK.PERSON:
                case = None
                gender = None
                if terminal is not None and terminal.num_variants >= 1:
                    gender = terminal.variant(-1)
                    if gender in { "nf", "þf", "þgf", "ef" }:
                        # Oops, mistaken identity
                        case = gender
                        gender = None
                    if terminal.num_variants >= 2:
                        case = terminal.variant(-2)
                fn_list = [ (fn, g, c) for fn, g, c in t.val if (gender is None or g == gender) and (case is None or c == case) ]
                # If there are many choices, select the nominative case, or the first element as a last resort
                fn = next((fn for fn in fn_list if fn[2] == "nf"), fn_list[0])
                d["v"] = fn[0] # Include only the name of the person in nominal form
                # Hack to make sure that the gender information is communicated in
                # the terminal name (in some cases the terminal only contains the case)
                if gender is None:
                    gender = fn[1]
                if terminal:
                    if not terminal.name.endswith("_" + gender):
                        d["t"] = terminal.name + "_" + gender
                else:
                    # There is no terminal: cop out by adding a separate gender field
                    d["g"] = gender
                wt = WordTuple(stem = d["v"], cat = "person_" + gender)
            else:
                d["v"] = t.val
        return d, wt

    class _Annotator(ParseForestNavigator):

        """ Local utility subclass to navigate a parse forest and annotate the
            original token list with the corresponding terminal matches """

        def __init__(self, tmap):
            super().__init__()
            self._tmap = tmap

        def _visit_token(self, level, node):
            """ At token node """
            ix = node.token.index # Index into original sentence
            assert ix not in self._tmap
            meaning = node.token.match_with_meaning(node.terminal)
            self._tmap[ix] = (node.terminal, None if isinstance(meaning, bool) else meaning) # Map from original token to matched terminal
            return None

    class _Simplifier(ParseForestNavigator):

        """ Local utility subclass to navigate a parse forest and return a
            simplified, condensed representation of it in a nested dictionary
            structure """

        # !!! TODO: Move the following dictionaries to a configuration file
        NT_MAP = {
            "S0" : "P",
            "HreinYfirsetning" : "S",
            "Setning" : "S",
            "SetningSo" : "VP",
            "SetningLo" : "S",
            "SetningÁnF" : "S",
            "SetningAukafall" : "S",
            "SetningSkilyrði" : "S",
            "Skilyrði" : "S-COND",
            "Afleiðing" : "S-CONS",
            "Nl" : "NP",
            "EfLiður" : "NP-POSS",
            "EfLiðurForskeyti" : "NP-POSS",
            "FsMeðFallstjórn" : "PP",
            "SagnInnskot" : "ADVP",
            "FsAtv" : "ADVP",
            "AtvFs" : "ADVP",
            "SagnRuna" : "VP",
            "NhLiðir" : "VP",
            "SagnliðurÁnF" : "VP"
        }

        ID_MAP = {
            "P" : dict(name = "Málsgrein"),
            "S" : dict(name = "Setning", subject_to = "S"),
            "S-COND" : dict(name = "Forsenda", overrides = "S"), # Condition
            "S-CONS" : dict(name = "Afleiðing", overrides = "S"), # Consequence
            "VP" : dict(name = "Sagnliður"),
            "NP" : dict(name = "Nafnliður"),
            "NP-POSS" : dict(name = "Eignarfallsliður", overrides = "NP"),
            "PP" : dict(name = "Forsetningarliður", overrides = "ADVP"),
            "ADVP" : dict(name = "Atviksliður", subject_to = "ADVP")
        }

        def __init__(self, tokens):
            super().__init__(visit_all = True)
            self._tokens = tokens
            self._result = []
            self._stack = [ self._result ]
            self._pushed = []
            self._scope = [ NotImplemented ] # Sentinel value

        def _visit_token(self, level, node):
            """ At token node """
            meaning = node.token.match_with_meaning(node.terminal)
            d, _ = TreeUtility._describe_token(self._tokens[node.token.index], node.terminal,
                None if isinstance(meaning, bool) else meaning)
            # Convert from compact form to external (more verbose and descriptive) form
            canonicalize_token(d)
            # Add as a child of the current node in the condensed tree
            self._stack[-1].append(d)
            return None

        def _visit_nonterminal(self, level, node):
            """ Entering a nonterminal node """
            self._pushed.append(False)
            if node.is_interior or node.nonterminal.is_optional:
                return None
            mapped_nt = self.NT_MAP.get(node.nonterminal.first)
            if mapped_nt is not None:
                # We want this nonterminal in the simplified tree:
                # push it (unless it is subject to a scope we're already in)
                mapped_id = self.ID_MAP[mapped_nt]
                subject_to = mapped_id.get("subject_to")
                if self._scope[-1] == subject_to:
                    # We are already within a nonterminal to which this one is subject:
                    # don't bother pushing it
                    return None
                children = []
                self._stack[-1].append(dict(k = "NONTERMINAL",
                    n = mapped_id["name"], i = mapped_nt, p = children))
                self._stack.append(children)
                self._scope.append(mapped_nt)
                self._pushed[-1] = True
            return None

        def _process_results(self, results, node):
            """ Exiting a nonterminal node """
            if not self._pushed.pop():
                return
            # Pushed this nonterminal in _visit_nonterminal(): pop it
            children = self._stack[-1]
            self._stack.pop()
            self._scope.pop()
            # Check whether this nonterminal has only one child, which is again
            # the same nonterminal - or a nonterminal which the parent overrides
            if len(children) == 1:

                def collapse_child(ch0, nt):
                    """ Determine whether to cut off a child and connect directly
                        from this node to its children """
                    d = self.NT_MAP[nt]
                    if ch0["i"] == d:
                        # Same nonterminal category: do the cut
                        return True
                    # If the child is a nonterminal that this one 'overrides',
                    # cut off the child
                    override = self.ID_MAP[d].get("overrides")
                    return ch0["i"] == override

                def replace_parent(ch0, nt):
                    d = self.NT_MAP[nt]
                    # If the child overrides the parent, replace the parent
                    override = self.ID_MAP[ch0["i"]].get("overrides")
                    return d == override

                ch0 = children[0]
                if ch0["k"] == "NONTERMINAL":
                    if collapse_child(ch0, node.nonterminal.first):
                        # If so, we eliminate one level and move the children of the child
                        # up to be children of this node
                        self._stack[-1][-1]["p"] = ch0["p"]
                    elif replace_parent(ch0, node.nonterminal.first):
                        # The child subsumes the parent: replace
                        # the parent by the child
                        self._stack[-1][-1] = ch0

        @property
        def result(self):
            return self._result[0]

    @staticmethod
    def _terminal_map(tree):
        """ Return a dict containing a map from original token indices to matched terminals """
        tmap = dict()
        if tree is not None:
            TreeUtility._Annotator(tmap).go(tree)
        return tmap

    @staticmethod
    def dump_tokens(tokens, tree, words, error_index = None):

        """ Generate a string (JSON) representation of the tokens in the sentence.

            The JSON token dict contents are as follows:

                t.x is original token text.
                t.k is the token kind (TOK.xxx). If omitted, the kind is TOK.WORD.
                t.t is the name of the matching terminal, if any.
                t.m is the BÍN meaning of the token, if any, as a tuple as follows:
                    t.m[0] is the lemma (stofn)
                    t.m[1] is the word category (ordfl)
                    t.m[2] is the word subcategory (fl)
                    t.m[3] is the word meaning/declination (beyging)
                t.v contains auxiliary information, depending on the token kind
                t.err is 1 if the token is an error token

            This function has the side effect of filling in the words dictionary
            with (stem, cat) keys and occurrence counts.

        """

        # Map tokens to associated terminals, if any
        tmap = TreeUtility._terminal_map(tree) # tmap is an empty dict if there's no parse tree
        dump = []
        for ix, token in enumerate(tokens):
            # We have already cut away paragraph and sentence markers (P_BEGIN/P_END/S_BEGIN/S_END)
            terminal, meaning = tmap.get(ix, (None, None))
            d, wt = TreeUtility._describe_token(token, terminal, meaning)
            if ix == error_index:
                # Mark the error token, if present
                d["err"] = 1
            dump.append(d)
            if words is not None and wt is not None:
                # Add the (stem, cat) combination to the words dictionary
                words[wt] += 1
        return dump

    @staticmethod
    def _simplify_tree(tokens, tree):
        """ Return a simplified parse tree for a sentence, including POS-tagged,
            normalized terminal leaves """
        """ Return a dict containing a map from original token indices to matched terminals """
        if tree is None:
            return None
        s = TreeUtility._Simplifier(tokens)
        s.go(tree)
        return s.result

    @staticmethod
    def _process_text(session, text, all_names, xform):
        """ Low-level utility function to parse text and return the result of
            a transformation function (xform) for each sentence """

        t0 = time.time()
        # Demarcate paragraphs in the input
        text = Fetcher.mark_paragraphs(text)
        # Tokenize the result
        toklist = list(tokenize(text, enclosing_session = session))
        t1 = time.time()
        pgs, stats = TreeUtility._process_toklist(session, toklist, xform)
        from query import create_name_register
        register = create_name_register(toklist, session, all_names = all_names)
        t2 = time.time()
        stats["tok_time"] = t1 - t0
        stats["parse_time"] = t2 - t1
        stats["total_time"] = t2 - t0
        return (pgs, stats, register)

    @staticmethod
    def _process_toklist(session, toklist, xform, root = None):
        """ Low-level utility function to parse token lists and return
            the result of a transformation function (xform) for each sentence """
        pgs = [] # Paragraph list, containing sentences, containing tokens
        with Fast_Parser(verbose = False, root = root) as bp: # Don't emit diagnostic messages
            ip = IncrementalParser(bp, toklist, verbose = True)
            for p in ip.paragraphs():
                pgs.append([])
                for sent in p.sentences():
                    if sent.parse():
                        # Parsed successfully
                        pgs[-1].append(xform(sent.tokens, sent.tree, None))
                    else:
                        # Errror in parse
                        pgs[-1].append(xform(sent.tokens, None, sent.err_index))

            stats = dict(
                num_tokens = ip.num_tokens,
                num_sentences = ip.num_sentences,
                num_parsed = ip.num_parsed,
                ambiguity = ip.ambiguity,
            )

        return (pgs, stats)

    @staticmethod
    def tag_text(session, text, all_names = False):
        """ Parse plain text and return the parsed paragraphs as lists of sentences
            where each sentence is a list of tagged tokens """

        def xform(tokens, tree, err_index):
            """ Transformation function that simply returns a list of POS-tagged,
                normalized tokens for the sentence """
            return TreeUtility.dump_tokens(tokens, tree, None, err_index)

        return TreeUtility._process_text(session, text, all_names, xform)

    @staticmethod
    def tag_toklist(session, toklist, all_names = False):
        """ Parse plain text and return the parsed paragraphs as lists of sentences
            where each sentence is a list of tagged tokens """

        def xform(tokens, tree, err_index):
            """ Transformation function that simply returns a list of POS-tagged,
                normalized tokens for the sentence """
            return TreeUtility.dump_tokens(tokens, tree, None, err_index)

        pgs, stats = TreeUtility._process_toklist(session, toklist, xform)
        from query import create_name_register
        register = create_name_register(toklist, session, all_names = all_names)
        return (pgs, stats, register)

    @staticmethod
    def raw_tag_toklist(session, toklist, root = None):
        """ Parse plain text and return the parsed paragraphs as lists of sentences
            where each sentence is a list of tagged tokens. The result does not
            include a name register. """

        def xform(tokens, tree, err_index):
            """ Transformation function that simply returns a list of POS-tagged,
                normalized tokens for the sentence """
            return TreeUtility.dump_tokens(tokens, tree, None, err_index)

        return TreeUtility._process_toklist(session, toklist, xform, root = root)

    @staticmethod
    def parse_text(session, text, all_names = False):
        """ Parse plain text and return the parsed paragraphs as simplified trees """

        def xform(tokens, tree, err_index):
            """ Transformation function that yields a simplified parse tree
                with POS-tagged, normalized terminal leaves for the sentence """
            if err_index is not None:
                return TreeUtility.dump_tokens(tokens, tree, None, err_index)
            # Successfully parsed: return a simplified tree for the sentence
            return TreeUtility._simplify_tree(tokens, tree)

        return TreeUtility._process_text(session, text, all_names, xform)

