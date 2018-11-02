"""
    Reynir: Natural language processing for Icelandic

    TreeUtility class

    Copyright (c) 2017 Miðeind ehf.

       This program is free software: you can redistribute it and/or modify
       it under the terms of the GNU General Public License as published by
       the Free Software Foundation, either version 3 of the License, or
       (at your option) any later version.
       This program is distributed in the hope that it will be useful,
       but WITHOUT ANY WARRANTY; without even the implied warranty of
       MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
       GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see http://www.gnu.org/licenses/.


    This module contains a class modeling an article originating from a scraped web page.

"""

import time
import threading
from collections import namedtuple

from fetcher import Fetcher
from nertokenizer import TOK, tokenize_and_recognize
from reynir.binparser import canonicalize_token, augment_terminal
from reynir.fastparser import Fast_Parser, ParseForestNavigator
from incparser import IncrementalParser
from scraperdb import SessionContext
from settings import Settings
from reynir.matcher import SimpleTree, SimpleTreeBuilder


WordTuple = namedtuple("WordTuple", ["stem", "cat"])


_TEST_NT_MAP = {  # Til að prófa í parse_text_to_bracket_form()
    "S0": "M",  # P veldur ruglingi við FS, breyti í M
    "HreinYfirsetning": "S",
    "Setning": "S",
    "SetningLo": "S",
    "SetningÁnF": "S",
    "SetningAukafall": "S",
    "SetningSkilyrði": "S",
    "SetningUmAðRæða": "S",
    "StViðtenging": "S",
    "Tengisetning": "S",
    "OgTengisetning": "S",
    "Skilyrði": "S-COND",
    "Afleiðing": "S-CONS",
    "NlSkýring": "S-EXPLAIN",
    "Tilvitnun": "S-QUOTE",
    "Atvikssetning": "CP-ADV",
    # "Tíðarsetning" : "CP-TMP",
    "BeygingarliðurÁnUmröðunar": "BL",
    "BeygingarliðurMeðUmröðun": "BL",
    "FsMeðFallstjórn": "PP",
    "Nl": "NP",
    "Sérnafn": "N",
    "Mannsnafn": "N",
    "EfLiður": "NP-POSS",
    "EfLiðurForskeyti": "NP-POSS",
    "OkkarFramhald": "NP-POSS",
    "Heimilisfang": "NP-ADDR",
    "NlFrumlag": "NP-SUBJ",
    "NlBeintAndlag": "NP-OBJ",
    "NlÓbeintAndlag": "NP-IOBJ",
    "NlSagnfylling": "NP-PRD",
    "Pfn": "PRON",
    "SagnInnskot": "ADVP",
    "FsAtv": "ADVP",
    "AtvFs": "ADVP",
    "Atviksliður": "ADVP",
    "LoAtviksliðir": "ADVP",
    "Dagsetning": "ADVP-DATE",
    "LoLiður": "ADJP",
    "Töluorð": "NUM",
    "OgEða": "C",
    "OgEðaEn": "C",
    "TengiorðEr": "C",
    "TengiorðSem": "C",
    "Greinir": "DET",
    # "Lo" : "ADJ",
}

_TEST_TERMINAL_MAP = {
    # To specify the creation of intermediate nonterminals
    # for particular terminals, put the first part of the terminal
    # name here
    "fs": "P",
    "no": "N",
    "hk": "N",
    "kk": "N",
    "kvk": "N",
    "fyrirtæki": "N",
    "fn": "PRON",
    "pfn": "PRON",
    "abfn": "PRON",
    "so": "V",
    "ao": "ADV",
    "eo": "ADV",
    "spao": "ADV",
    "lo": "ADJ",
    "raðnr": "ADJ",  # Raðtölur
    "töl": "NUM",
    "tala": "NUM",
    "ártal": "NUM",
    "st": "C",
    "stt": "C",
    "nhm": "INF",  # Nafnháttarmerki
    "gr": "DET",
}

_TEST_ID_MAP = {  # Til að prófa í parse_text_to_bracket_form()
    "M": dict(name="Málsgrein"),  # Breytti úr P til að forðast rugling
    "S": dict(name="Setning", subject_to={"S", "S-EXPLAIN"}),
    "S-COND": dict(name="Skilyrði", overrides="S"),  # Condition
    "S-CONS": dict(name="Afleiðing", overrides="S"),  # Consequence
    "S-EXPLAIN": dict(name="Skýring"),  # Explanation
    "S-QUOTE": dict(name="Tilvitnun"),  # Quote at end of sentence
    # "CP-TMP" : dict(name = "Tíðaratvikssetning"), # Temporal adverbial clause
    "CP-ADV": dict(name="Atvikssetning"),  # Adverbial clause
    "BL": dict(name="Beygingarliður"),
    # "VP" : dict(name = "Sagnliður", subject_to = { "VP" }),
    "NP": dict(name="Nafnliður", subject_to={"NP-SUBJ", "NP-OBJ", "NP-IOBJ", "NP-PRD"}),
    "NP-POSS": dict(name="Eignarfallsliður", overrides="NP"),
    "NP-ADDR": dict(name="Heimilisfang", overrides="NP"),
    "NP-SUBJ": dict(name="Frumlag"),
    "NP-OBJ": dict(name="Beint andlag"),
    "NP-IOBJ": dict(name="Óbeint andlag"),
    "NP-PRD": dict(name="Sagnfylling"),
    "ADVP": dict(name="Atviksliður", subject_to={"ADVP"}),
    "ADVP-DATE": dict(name="Tímasetning", overrides="ADVP"),
    "PP": dict(name="Forsetningarliður", overrides="ADVP"),
    "ADJP": dict(name="Lýsingarliður"),
    # Hausar
    "ADV": dict(name="Atviksorð"),
    "V": dict(name="Sögn"),
    "N": dict(name="Nafnorð"),
    "PRON": dict(name="Fornafn"),
    "P": dict(name="Forsetning"),
    "INF": dict(name="Nafnháttarmerki"),
    "NUM": dict(name="Töluorð"),
    "C": dict(name="Samtenging"),
    "ADJ": dict(name="Lýsingarorð", overrides="V"),
    "DET": dict(name="Greinir"),
}


class TreeUtility:

    """ A wrapper around a set of static utility functions for working
        with parse trees and tokens """

    @staticmethod
    def choose_full_name(val, case, gender):
        """ From a list of name possibilities in val, and given a case and a gender
            (which may be None), return the best matching full name and gender """
        fn_list = [
            (fn, g, c)
            for fn, g, c in val
            if (gender is None or g == gender) and (case is None or c == case)
        ]
        if not fn_list:
            # Oops - nothing matched this. Might be a foreign, undeclinable name.
            # Try nominative if it wasn't already tried
            if case is not None and case != "nf":
                fn_list = [
                    (fn, g, c)
                    for fn, g, c in val
                    if (gender is None or g == gender) and (case == "nf")
                ]
            # If still nothing, try anything with the same gender
            if not fn_list and gender is not None:
                fn_list = [(fn, g, c) for fn, g, c in val if (g == gender)]
            # If still nothing, give up and select the first available meaning
            if not fn_list:
                fn, g, c = val[0]
                fn_list = [(fn, g, c)]
        # If there are many choices, select the nominative case,
        # or the first element as a last resort
        fn = next((fn for fn in fn_list if fn[2] == "nf"), fn_list[0])
        return fn[0], fn[1] if gender is None else gender

    @staticmethod
    def _describe_token(t, terminal, meaning):
        """ Return a compact dictionary and a WordTuple describing the token t,
            which matches the given terminal with the given meaning """
        d = dict(x=t.txt)
        wt = None
        if terminal is not None:
            # There is a token-terminal match
            if t.kind == TOK.PUNCTUATION:
                if t.txt == "-":
                    # Hyphen: check whether it is matching an em or en-dash terminal
                    if terminal.colon_cat == "em":
                        # Substitute em dash (will be displayed with surrounding space)
                        d["x"] = "—"
                    elif terminal.colon_cat == "en":
                        # Substitute en dash
                        d["x"] = "–"
            else:
                # Annotate with terminal name and BÍN meaning
                # (no need to do this for punctuation)
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
                    wt = WordTuple(stem=m[0].replace("-", ""), cat=m[1])
                elif t.kind == TOK.ENTITY:
                    wt = WordTuple(stem=t.txt, cat="entity")
        if t.kind != TOK.WORD:
            # Optimize by only storing the k field for non-word tokens
            d["k"] = t.kind
        if t.val is not None and t.kind not in {TOK.WORD, TOK.ENTITY, TOK.PUNCTUATION}:
            # For tokens except words, entities and punctuation, include the val field
            if t.kind == TOK.PERSON:
                case = None
                gender = None
                if terminal is not None and terminal.num_variants >= 1:
                    gender = terminal.variant(-1)
                    if gender in {"nf", "þf", "þgf", "ef"}:
                        # Oops, mistaken identity
                        case = gender
                        gender = None
                    if terminal.num_variants >= 2:
                        case = terminal.variant(-2)
                d["v"], gender = TreeUtility.choose_full_name(t.val, case, gender)
                # Make sure the terminal field has a gender indicator
                if terminal is not None:
                    if not terminal.name.endswith("_" + gender):
                        d["t"] = terminal.name + "_" + gender
                else:
                    # No terminal field: create it
                    d["t"] = "person_" + gender
                # In any case, add a separate gender indicator field for convenience
                d["g"] = gender
                wt = WordTuple(stem=d["v"], cat="person_" + gender)
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
            ix = node.token.index  # Index into original sentence
            assert ix not in self._tmap
            meaning = node.token.match_with_meaning(node.terminal)
            # Map from original token to matched terminal
            self._tmap[ix] = (
                node.terminal,
                None if isinstance(meaning, bool) else meaning,
            )
            return None

    class _Simplifier(ParseForestNavigator):

        """ Local utility subclass to navigate a parse forest and return a
            simplified, condensed representation of it in a nested dictionary
            structure """

        def __init__(self, tokens, nt_map, id_map, terminal_map):
            super().__init__(visit_all=True)
            self._tokens = tokens
            self._builder = SimpleTreeBuilder(nt_map, id_map, terminal_map)

        def _visit_token(self, level, node):
            """ At token node """
            meaning = node.token.match_with_meaning(node.terminal)
            d, _ = TreeUtility._describe_token(
                self._tokens[node.token.index],
                node.terminal,
                None if isinstance(meaning, bool) else meaning,
            )
            # Convert from compact form to external (more verbose and descriptive) form
            canonicalize_token(d)
            self._builder.push_terminal(d)
            return None

        def _visit_nonterminal(self, level, node):
            """ Entering a nonterminal node """
            if node.is_interior or node.nonterminal.is_optional:
                nt_base = None
            else:
                nt_base = node.nonterminal.first
            self._builder.push_nonterminal(nt_base)
            return None

        def _process_results(self, results, node):
            """ Exiting a nonterminal node """
            self._builder.pop_nonterminal()

        @property
        def result(self):
            return self._builder.result

    @staticmethod
    def _terminal_map(tree):
        """ Return a dict containing a map from original token indices
            to matched terminals """
        tmap = dict()
        if tree is not None:
            TreeUtility._Annotator(tmap).go(tree)
        return tmap

    @staticmethod
    def dump_tokens(tokens, tree, words, error_index=None):

        """ Generate a list of dicts representing the tokens in the sentence.

            For each token dict t:

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
        # tmap is an empty dict if there's no parse tree
        tmap = TreeUtility._terminal_map(tree)
        dump = []
        for ix, token in enumerate(tokens):
            # We have already cut away paragraph and sentence markers
            # (P_BEGIN/P_END/S_BEGIN/S_END)
            terminal, meaning = tmap.get(ix, (None, None))
            d, wt = TreeUtility._describe_token(token, terminal, meaning)
            if ix == error_index:
                # Mark the error token, if present
                d["err"] = 1
            if meaning is not None and "x" in d:
                # Also return the augmented terminal name
                d["a"] = augment_terminal(
                    terminal.name,
                    d["x"].lower(),
                    meaning.beyging
                )
            dump.append(d)
            if words is not None and wt is not None:
                # Add the (stem, cat) combination to the words dictionary
                words[wt] += 1
        return dump

    @staticmethod
    def _simplify_tree(tokens, tree, nt_map=None, id_map=None, terminal_map=None):
        """ Return a simplified parse tree for a sentence, including POS-tagged,
            normalized terminal leaves """
        if tree is None:
            return None
        s = TreeUtility._Simplifier(
            tokens, nt_map=nt_map, id_map=id_map, terminal_map=terminal_map
        )
        s.go(tree)
        return s.result

    @staticmethod
    def _process_text(parser, session, text, all_names, xform):
        """ Low-level utility function to parse text and return the result of
            a transformation function (xform) for each sentence.
            Set all_names = True to get a comprehensive name register.
            Set all_names = False to get a simple name register.
            Set all_names = None to get no name register. """
        t0 = time.time()
        # Demarcate paragraphs in the input
        text = Fetcher.mark_paragraphs(text)
        # Tokenize the result
        toklist = list(tokenize_and_recognize(text, enclosing_session=session))
        t1 = time.time()
        pgs, stats = TreeUtility._process_toklist(parser, session, toklist, xform)
        if all_names is None:
            register = None
        else:
            from query import create_name_register
            register = create_name_register(toklist, session, all_names=all_names)
        t2 = time.time()
        stats["tok_time"] = t1 - t0
        stats["parse_time"] = t2 - t1
        stats["total_time"] = t2 - t0
        return (pgs, stats, register)

    @staticmethod
    def _process_toklist(parser, session, toklist, xform):
        """ Low-level utility function to parse token lists and return
            the result of a transformation function (xform) for each sentence """
        pgs = []  # Paragraph list, containing sentences, containing tokens
        ip = IncrementalParser(parser, toklist, verbose=True)
        for p in ip.paragraphs():
            pgs.append([])
            for sent in p.sentences():
                if sent.parse():
                    # Parsed successfully
                    pgs[-1].append(xform(sent.tokens, sent.tree, None))
                else:
                    # Error in parse
                    pgs[-1].append(xform(sent.tokens, None, sent.err_index))

        stats = dict(
            num_tokens=ip.num_tokens,
            num_sentences=ip.num_sentences,
            num_parsed=ip.num_parsed,
            ambiguity=ip.ambiguity,
            num_combinations=ip.num_combinations,
            total_score=ip.total_score,
        )

        return (pgs, stats)

    @staticmethod
    def raw_tag_text(parser, session, text, all_names=False):
        """ Parse plain text and return the parsed paragraphs as lists of sentences
            where each sentence is a list of tagged tokens. Uses a caller-provided
            parser object. """

        def xform(tokens, tree, err_index):
            """ Transformation function that simply returns a list of POS-tagged,
                normalized tokens for the sentence """
            return TreeUtility.dump_tokens(tokens, tree, None, err_index)

        return TreeUtility._process_text(parser, session, text, all_names, xform)

    @staticmethod
    def tag_text(session, text, all_names=False):
        """ Parse plain text and return the parsed paragraphs as lists of sentences
            where each sentence is a list of tagged tokens """
        with Fast_Parser(verbose=False) as parser:  # Don't emit diagnostic messages
            return TreeUtility.raw_tag_text(parser, session, text, all_names)

    @staticmethod
    def tag_toklist(session, toklist, all_names=False):
        """ Parse plain text and return the parsed paragraphs as lists of sentences
            where each sentence is a list of tagged tokens """

        def xform(tokens, tree, err_index):
            """ Transformation function that simply returns a list of POS-tagged,
                normalized tokens for the sentence """
            return TreeUtility.dump_tokens(tokens, tree, None, err_index)

        with Fast_Parser(verbose=False) as parser:  # Don't emit diagnostic messages
            pgs, stats = TreeUtility._process_toklist(parser, session, toklist, xform)

        from query import create_name_register

        register = create_name_register(toklist, session, all_names=all_names)

        return (pgs, stats, register)

    @staticmethod
    def raw_tag_toklist(session, toklist, root=None):
        """ Parse plain text and return the parsed paragraphs as lists of sentences
            where each sentence is a list of tagged tokens. The result does not
            include a name register. """

        def xform(tokens, tree, err_index):
            """ Transformation function that simply returns a list of POS-tagged,
                normalized tokens for the sentence """
            return TreeUtility.dump_tokens(tokens, tree, None, err_index)

        with Fast_Parser(verbose=False, root=root) as parser:
            return TreeUtility._process_toklist(parser, session, toklist, xform)

    @staticmethod
    def parse_text(session, text, all_names=False):
        """ Parse plain text and return the parsed paragraphs as simplified trees """

        def xform(tokens, tree, err_index):
            """ Transformation function that yields a simplified parse tree
                with POS-tagged, normalized terminal leaves for the sentence """
            if err_index is not None:
                return TreeUtility.dump_tokens(tokens, tree, None, err_index)
            # Successfully parsed: return a simplified tree for the sentence
            return TreeUtility._simplify_tree(tokens, tree)

        with Fast_Parser(verbose=False) as parser:  # Don't emit diagnostic messages
            return TreeUtility._process_text(parser, session, text, all_names, xform)

    @staticmethod
    def simple_parse(text):
        """ No-frills parse of text, returning a SimpleTree object """
        if not Settings.loaded:
            Settings.read("config/Reynir.conf")
        with SessionContext(read_only=True) as session:
            return SimpleTree(*TreeUtility.parse_text(session, text))

    @staticmethod
    def parse_text_to_bracket_form(session, text):
        """ Parse plain text and return the parsed paragraphs as bracketed strings """

        def xform(tokens, tree, err_index):
            """ Transformation function that yields a simplified parse tree
                with POS-tagged, normalized terminal leaves for the sentence """
            if err_index is not None:
                # Return an empty string for sentences that don't parse
                return ""
            # Successfully parsed: obtain a simplified tree for the sentence
            result = []

            def push(node):
                """ Append information about a node to the result list """
                if node is None:
                    return
                nonlocal result
                if node["k"] == "NONTERMINAL":
                    result.append("(" + node["i"])
                    # Recursively add the children of this nonterminal
                    for child in node["p"]:
                        result.append(" ")
                        push(child)
                    result.append(")")
                elif node["k"] == "PUNCTUATION":
                    pass
                    # Include punctuation?
                    # If so, do something like:
                    # result.push("(PUNCT |" + node["x"] + "|)")
                else:
                    # Terminal: append the text
                    result.append(node["x"].replace(" ", "_"))

            # This uses a custom simplification scheme
            simple_tree = TreeUtility._simplify_tree(
                tokens,
                tree,
                nt_map=_TEST_NT_MAP,
                id_map=_TEST_ID_MAP,
                terminal_map=_TEST_TERMINAL_MAP,
            )
            push(simple_tree)
            return "".join(result)

        with Fast_Parser(verbose=False) as parser:
            pgs, stats, _ = TreeUtility._process_text(
                parser, session, text, all_names=None, xform=xform
            )
        # pgs is a list of paragraphs, each being a list of sentences
        # To access the first parsed sentence, use pgs[0][0]
        return (pgs, stats)

    @staticmethod
    def parse_text_with_full_tree(session, text, all_names=False):
        """ Parse plain text, assumed to contain one sentence only, and
            return its simplified form as well as its full form. """

        full_tree = None

        def xform(tokens, tree, err_index):
            """ Transformation function that yields a simplified parse tree
                with POS-tagged, normalized terminal leaves for the sentence """
            if err_index is not None:
                return TreeUtility.dump_tokens(tokens, tree, None, err_index)
            # Successfully parsed: return a simplified tree for the sentence
            nonlocal full_tree
            # We are assuming that there is only one parsed sentence
            if full_tree is None:
                # Note the full tree of the first parsed paragraph
                full_tree = tree
            return TreeUtility._simplify_tree(tokens, tree)

        with Fast_Parser(verbose=False) as parser:
            pgs, stats, register = TreeUtility._process_text(
                parser, session, text, all_names, xform
            )

        if (
            not pgs
            or stats["num_parsed"] == 0
            or not pgs[0]
            or any("err" in t for t in pgs[0][0])
        ):
            # The first sentence didn't parse: let's not beat around the bush with that fact
            return (None, None, stats)

        # Return the simplified tree, full tree and stats
        assert full_tree is not None
        return (pgs[0][0], full_tree, stats)
