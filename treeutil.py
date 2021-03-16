"""

    Greynir: Natural language processing for Icelandic

    TreeUtility class

    Copyright (C) 2021 Miðeind ehf.

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


    This module implements the TreeUtility class, which contains a number
    of static methods and subclasses that wrap the raw parser and return
    parse results in a variety of forms.

"""

from typing import (
    Callable,
    Dict,
    Iterable,
    Mapping,
    Sequence,
    TYPE_CHECKING,
    List,
    Optional,
    Tuple,
    Union,
    cast,
)

import time
from collections import namedtuple

from sqlalchemy.orm.session import Session

from nertokenizer import recognize_entities

from reynir import TOK, Tok, mark_paragraphs, tokenize
from reynir.binparser import (
    BIN_Parser,
    BIN_Terminal,
    BIN_Meaning,
    CanonicalTokenDict,
    augment_terminal,
    describe_token,
    TokenDict,
)
from reynir.fastparser import Fast_Parser, Node
from reynir.incparser import IncrementalParser
from reynir.simpletree import Annotator, SimpleTreeNode, Simplifier

if TYPE_CHECKING:
    from reynir.simpletree import TerminalMap
    from queries.builtin import RegisterType


WordTuple = namedtuple("WordTuple", ["stem", "cat"])
StatsDict = Dict[str, Union[int, float]]
PgsList = List[List[List[TokenDict]]]
XformFunc = Callable[[List[Tok], Optional[Node], Optional[int]], List[TokenDict]]

_TEST_NT_MAP: Mapping[str, str] = {  # Til að prófa í parse_text_to_bracket_form()
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
    def choose_full_name(
        val: Sequence[Tuple[str, str, str]], case: Optional[str], gender: Optional[str]
    ) -> Tuple[str, str]:
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
        ft = next((fn for fn in fn_list if fn[2] == "nf"), fn_list[0])
        return ft[0], ft[1] if gender is None else gender

    @staticmethod
    def _word_tuple(
        t: Tok, terminal: Optional[BIN_Terminal], meaning: Optional[BIN_Meaning]
    ) -> Optional[WordTuple]:
        """ Return a WordTuple describing the token t, matching the
            given terminal with the given meaning  """
        wt = None
        if terminal is not None:
            # There is a token-terminal match
            if t.kind != TOK.PUNCTUATION:
                # Annotate with terminal name and BÍN meaning
                # (no need to do this for punctuation)
                if meaning is not None:
                    if terminal.first == "fs":
                        # Special case for prepositions since they're really
                        # resolved from the preposition list in Main.conf, not from BÍN
                        wt = WordTuple(stem=meaning.ordmynd, cat="fs")
                    else:
                        wt = WordTuple(
                            stem=meaning.stofn.replace("-", ""), cat=meaning.ordfl
                        )
                elif t.kind == TOK.ENTITY:
                    wt = WordTuple(stem=t.txt, cat="entity")
        if t.val is not None and t.kind == TOK.PERSON:
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
            name, gender = TreeUtility.choose_full_name(t.val, case, gender)
            # In any case, add a separate gender indicator field for convenience
            wt = WordTuple(stem=name, cat="person_" + gender)
        return wt

    @staticmethod
    def _terminal_map(tree: Optional[Node]) -> "TerminalMap":
        """ Return a dict containing a map from original token indices
            to matched terminals """
        tmap: "TerminalMap" = dict()
        if tree is not None:
            Annotator(tmap).go(tree)
        return tmap

    @staticmethod
    def dump_tokens(
        tokens: Iterable[Tok],
        tree: Optional[Node],
        *,
        error_index: Optional[int] = None,
        words: Optional[Dict[WordTuple, int]] = None
    ) -> List[TokenDict]:

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
        dump: List[TokenDict] = []
        for ix, token in enumerate(tokens):
            # We have already cut away paragraph and sentence markers
            # (P_BEGIN/P_END/S_BEGIN/S_END)
            terminal, meaning = tmap.get(ix, (None, None))
            d: TokenDict = describe_token(ix, token, terminal, meaning)
            if words is not None:
                wt = TreeUtility._word_tuple(token, terminal, meaning)
                if wt is not None:
                    # Add the (stem, cat) combination to the words dictionary
                    words[wt] += 1
            if ix == error_index:
                # Mark the error token, if present
                d["err"] = 1
            # The following code is a bit convoluted, in order to
            # work around a bug in Pylance
            if meaning is not None:
                txt = d.get("x", "").lower()
                if txt:
                    # Also return the augmented terminal name
                    d["a"] = augment_terminal(
                        terminal.name, txt, meaning.beyging
                    )
            dump.append(d)
        return dump

    @staticmethod
    def _simplify_tree(
        tokens: List[Tok],
        tree: Optional[Node],
        nt_map=None,
        id_map=None,
        terminal_map=None,
    ) -> Optional[CanonicalTokenDict]:
        """ Return a simplified parse tree for a sentence, including POS-tagged,
            normalized terminal leaves """
        if tree is None:
            return None
        s = Simplifier(tokens, nt_map=nt_map, id_map=id_map, terminal_map=terminal_map)
        s.go(tree)
        return s.result

    @staticmethod
    def _process_toklist(
        parser: Fast_Parser, toklist: Iterable[Tok], xform: XformFunc
    ) -> Tuple[PgsList, StatsDict]:
        """ Low-level utility function to parse token lists and return
            the result of a transformation function (xform) for each sentence """
        # Paragraph list, containing sentences, containing tokens
        pgs: PgsList = []
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

        stats: StatsDict = dict(
            num_tokens=ip.num_tokens,
            num_sentences=ip.num_sentences,
            num_parsed=ip.num_parsed,
            ambiguity=ip.ambiguity,
            num_combinations=ip.num_combinations,
            total_score=ip.total_score,
        )

        return pgs, stats

    @staticmethod
    def _process_text(
        parser: Fast_Parser,
        session: Session,
        text: str,
        all_names: bool,
        xform: XformFunc,
    ) -> Tuple[PgsList, StatsDict, Optional["RegisterType"]]:
        """ Low-level utility function to parse text and return the result of
            a transformation function (xform) for each sentence.
            Set all_names = True to get a comprehensive name register.
            Set all_names = False to get a simple name register.
            Set all_names = None to get no name register. """
        t0 = time.time()
        # Demarcate paragraphs in the input
        text = mark_paragraphs(text)
        # Tokenize the result
        token_stream = tokenize(text)
        toklist = list(recognize_entities(token_stream, enclosing_session=session))
        t1 = time.time()
        pgs, stats = TreeUtility._process_toklist(parser, toklist, xform)

        if all_names is None:
            register = None
        else:
            from queries.builtin import create_name_register

            register = create_name_register(toklist, session, all_names=all_names)

        t2 = time.time()
        stats["tok_time"] = t1 - t0
        stats["parse_time"] = t2 - t1
        stats["total_time"] = t2 - t0
        return pgs, stats, register

    @staticmethod
    def raw_tag_text(
        parser: Fast_Parser, session: Session, text: str, all_names: bool = False
    ) -> Tuple[PgsList, StatsDict, Optional["RegisterType"]]:
        """ Parse plain text and return the parsed paragraphs as lists of sentences
            where each sentence is a list of tagged tokens. Uses a caller-provided
            parser object. """

        def xform(
            tokens: List[Tok], tree: Optional[Node], err_index: Optional[int]
        ) -> List[TokenDict]:
            """ Transformation function that simply returns a list of POS-tagged,
                normalized tokens for the sentence """
            return TreeUtility.dump_tokens(tokens, tree, error_index=err_index)

        return TreeUtility._process_text(parser, session, text, all_names, xform)

    @staticmethod
    def tag_text(
        session: Session, text: str, all_names: bool = False
    ) -> Tuple[PgsList, StatsDict, Optional["RegisterType"]]:
        """ Parse plain text and return the parsed paragraphs as lists of sentences
            where each sentence is a list of tagged tokens """
        # Don't emit diagnostic messages
        with Fast_Parser(verbose=False) as parser:
            return TreeUtility.raw_tag_text(parser, session, text, all_names=all_names)

    @staticmethod
    def tag_toklist(session: Session, toklist: Iterable[Tok], all_names: bool = False):
        """ Parse plain text and return the parsed paragraphs as lists of sentences
            where each sentence is a list of tagged tokens """

        def xform(
            tokens: List[Tok], tree: Optional[Node], err_index: Optional[int]
        ) -> List[TokenDict]:
            """ Transformation function that simply returns a list of POS-tagged,
                normalized tokens for the sentence """
            return TreeUtility.dump_tokens(tokens, tree, error_index=err_index)

        with Fast_Parser(verbose=False) as parser:  # Don't emit diagnostic messages
            pgs, stats = TreeUtility._process_toklist(parser, toklist, xform)
        from queries.builtin import create_name_register

        register = create_name_register(toklist, session, all_names=all_names)
        return pgs, stats, register

    @staticmethod
    def raw_tag_toklist(
        toklist: Iterable[Tok], root: Optional[str] = None
    ) -> Tuple[PgsList, StatsDict]:
        """ Parse plain text and return the parsed paragraphs as lists of sentences
            where each sentence is a list of tagged tokens. The result does not
            include a name register. """

        def xform(
            tokens: List[Tok], tree: Optional[Node], err_index: Optional[int]
        ) -> List[TokenDict]:
            """ Transformation function that simply returns a list of POS-tagged,
                normalized tokens for the sentence """
            return TreeUtility.dump_tokens(tokens, tree, error_index=err_index)

        with Fast_Parser(verbose=False, root=root) as parser:
            return TreeUtility._process_toklist(parser, toklist, xform)

    @staticmethod
    def parse_text(
        session: Session, text: str, all_names: bool = False
    ) -> Tuple[PgsList, StatsDict, Optional["RegisterType"]]:
        """ Parse plain text and return the parsed paragraphs as simplified trees """

        def xform(
            tokens: List[Tok], tree: Optional[Node], err_index: Optional[int]
        ) -> Union[None, List[TokenDict], CanonicalTokenDict]:
            """ Transformation function that yields a simplified parse tree
                with POS-tagged, normalized terminal leaves for the sentence """
            if err_index is not None:
                return TreeUtility.dump_tokens(tokens, tree, error_index=err_index)
            # Successfully parsed: return a simplified tree for the sentence
            return TreeUtility._simplify_tree(tokens, tree)

        with Fast_Parser(verbose=False) as parser:  # Don't emit diagnostic messages
            # The type annotation cast(XformFunc, xform) is a hack
            return TreeUtility._process_text(
                parser, session, text, all_names, cast(XformFunc, xform)
            )

    @staticmethod
    def parse_text_to_bracket_form(session: Session, text: str):
        """ Parse plain text and return the parsed paragraphs as bracketed strings """

        def xform(
            tokens: List[Tok], tree: Optional[Node], err_index: Optional[int]
        ) -> str:
            """ Transformation function that yields a simplified parse tree
                with POS-tagged, normalized terminal leaves for the sentence """
            if err_index is not None:
                # Return an empty string for sentences that don't parse
                return ""
            # Successfully parsed: obtain a simplified tree for the sentence
            result = []

            def push(node: Optional[CanonicalTokenDict]) -> None:
                """ Append information about a node to the result list """
                if node is None:
                    return
                nonlocal result
                if node.get("k") == "NONTERMINAL":
                    node = cast(SimpleTreeNode, node)
                    result.append("(" + node.get("i", ""))
                    # Recursively add the children of this nonterminal
                    for child in node.get("p", []):
                        result.append(" ")
                        push(child)
                    result.append(")")
                elif node.get("k") == "PUNCTUATION":
                    pass
                    # Include punctuation?
                    # If so, do something like:
                    # result.push("(PUNCT |" + node["x"] + "|)")
                else:
                    # Terminal: append the text
                    result.append(node.get("x", "").replace(" ", "_"))

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
            # The cast(XformFunc, xform) type annotation is a hack
            pgs, stats, _ = TreeUtility._process_text(
                parser, session, text, all_names=False, xform=cast(XformFunc, xform)
            )
        # pgs is a list of paragraphs, each being a list of sentences
        # To access the first parsed sentence, use pgs[0][0]
        return (pgs, stats)

    @staticmethod
    def parse_text_with_full_tree(
        session: Session, text: str, all_names: bool = False
    ) -> Tuple[Optional[List[TokenDict]], Optional[Node], StatsDict]:
        """ Parse plain text, assumed to contain one sentence only, and
            return its simplified form as well as its full form. """

        full_tree: Optional[Node] = None

        def xform(
            tokens: List[Tok], tree: Optional[Node], err_index: Optional[int]
        ) -> Union[None, List[TokenDict], CanonicalTokenDict]:
            """ Transformation function that yields a simplified parse tree
                with POS-tagged, normalized terminal leaves for the sentence """
            if err_index is not None:
                return TreeUtility.dump_tokens(tokens, tree, error_index=err_index)
            # Successfully parsed: return a simplified tree for the sentence
            nonlocal full_tree
            # We are assuming that there is only one parsed sentence
            if full_tree is None:
                # Note the full tree of the first parsed paragraph
                full_tree = tree
            return TreeUtility._simplify_tree(tokens, tree)

        with Fast_Parser(verbose=False) as parser:
            # The cast(XformFunction, xform) type annotation is a hack
            pgs, stats, _ = TreeUtility._process_text(
                parser, session, text, all_names, cast(XformFunc, xform)
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
