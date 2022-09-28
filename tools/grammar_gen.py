#!/usr/bin/env python3
"""

    Greynir: Natural language processing for Icelandic

    Grammar generator

    Copyright (C) 2022 Miðeind ehf.

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


    This tool reads in one or more grammar files and generates
    all possible sentences from the grammar.
    Uses algorithm from https://github.com/nltk/nltk/blob/develop/nltk/parse/generate.py
    The algorithm is modified to work with classes from GreynirPackage.
    Use --help to see more information on usage.

"""
from typing import Callable, Iterable, Iterator, List, Optional, Union, Match

import re
import sys
import itertools
from pathlib import Path
from functools import lru_cache

from islenska.basics import BinEntry


# Hack to make this Python program executable from the tools subdirectory
basepath = Path(__file__).parent.resolve()
_UTILS = "tools"
if basepath.stem == _UTILS:
    sys.path.append(str(basepath.parent))


from islenska import Bin
from reynir.grammar import Nonterminal, Terminal
from reynir.binparser import BIN_Parser, BIN_LiteralTerminal

from query import QueryGrammar

# TODO: Create random traversal functionality (itertools.dropwhile?)
# TODO: Allow replacing special terminals (no, sérnafn, lo, ...) with words

ColorF = Callable[[str], str]
_reset: str = "\033[0m"
bold: ColorF = lambda s: f"\033[01m{s}{_reset}"
black: ColorF = lambda s: f"\033[30m{s}{_reset}"
red: ColorF = lambda s: f"\033[31m{s}{_reset}"
green: ColorF = lambda s: f"\033[32m{s}{_reset}"
orange: ColorF = lambda s: f"\033[33m{s}{_reset}"
blue: ColorF = lambda s: f"\033[34m{s}{_reset}"
purple: ColorF = lambda s: f"\033[35m{s}{_reset}"
cyan: ColorF = lambda s: f"\033[36m{s}{_reset}"
lightgrey: ColorF = lambda s: f"\033[37m{s}{_reset}"
darkgrey: ColorF = lambda s: f"\033[90m{s}{_reset}"
lightred: ColorF = lambda s: f"\033[91m{s}{_reset}"
lightgreen: ColorF = lambda s: f"\033[92m{s}{_reset}"
yellow: ColorF = lambda s: f"\033[93m{s}{_reset}"
lightblue: ColorF = lambda s: f"\033[94m{s}{_reset}"
pink: ColorF = lambda s: f"\033[95m{s}{_reset}"
lightcyan: ColorF = lambda s: f"\033[96m{s}{_reset}"

nonverb_variant_order = [
    ("esb", "evb", "fsb", "fvb", "mst", "vb", "sb"),
    ("kk", "kvk", "hk"),
    ("nf", "þf", "þgf", "ef"),
    ("et", "ft"),
    ("gr",),
    ("0", "1", "2", "3"),
]
verb_variant_order = [
    ("gm", "mm"),
    ("lhnt", "nh", "fh", "vh", "bh"),
    ("þt", "nt"),
    ("1p", "2p", "3p"),
    ("et", "ft"),
    ("0", "1", "2", "3"),
]
_order_len = max(len(nonverb_variant_order), len(verb_variant_order))

_orderings = {
    "hk": (
        "NFET",
        "ÞFET",
        "ÞGFET",
        "EFET",
        "NFFT",
        "ÞFFT",
        "ÞGFFT",
        "EFFT",
        "NFETgr",
        "ÞFETgr",
        "ÞGFETgr",
        "EFETgr",
        "NFFTgr",
        "ÞFFTgr",
        "ÞGFFTgr",
        "EFFTgr",
    ),
}
# kk = kvk = hk
_orderings["kk"] = _orderings["kvk"] = _orderings["hk"]

# Grammar item type
_GIType = Union[Nonterminal, Terminal]
# BÍN, for word lookups
BIN = Bin()

# Mebibyte
MiB = 1024 * 1024

# Preamble with a hacke in case we aren't testing a query grammar
# (prevents an error in the QueryGrammar class)
PREAMBLE = """
QueryRoot →
    Query

Query → ""

"""


def _binentry_to_int(w: BinEntry) -> List[int]:
    """Used for pretty ordering of variants in output :)."""
    try:
        return [_orderings[w.ofl].index(w.mark)]
    except (KeyError, ValueError):
        pass

    # Fallback, manually compute order
    val = [0 for _ in range(_order_len)]
    if w.ofl == "so":
        var_order = verb_variant_order
    else:
        var_order = nonverb_variant_order

    for x, v_list in enumerate(var_order):
        for y, v in enumerate(v_list):
            if v in w.mark.casefold():
                val[-x] = y + 1
                break
    return val


# Word categories which should have some variant specified
_STRICT_CATEGORIES = frozenset(("no", "so", "lo"))


@lru_cache(maxsize=500)  # VERY useful cache
def get_wordform(gi: BIN_LiteralTerminal) -> str:
    """
    Fetch all possible wordforms for a literal terminal
    specification and return as readable string.
    """
    global strict
    word, cat, variants = gi.first, gi.category, "".join(gi.variants).casefold()
    ll = BIN.lookup_lemmas(word)

    if strict:
        # Strictness checks on usage of
        # single-quoted terminals in the grammar
        assert len(ll[1]) > 0, f"Meaning not found, use root of word for: {gi.name}"
        assert (
            cat is not None
        ), f"Specify category for single quoted terminal: {gi.name}"
        # Filter by word category
        assert len(list(filter(lambda m: m.ofl == cat, ll[1]))) < 2, (
            "Category not specific enough, "
            "single quoted terminal has "
            f"multiple meanings: {gi.name}"
        )
        if cat in _STRICT_CATEGORIES:
            assert (
                len(variants) > 0
            ), f"Specify variant for single quoted terminal: {gi.name}"

    if not cat and len(ll[1]) > 0:
        # Guess category from lemma lookup
        cat = ll[1][0].ofl

    # Have correct order of variants for form lookup (otherwise it doesn't work)
    spec: List[str] = ["" for _ in range(_order_len)]
    if cat == "so":
        # Verb variants
        var_order = verb_variant_order
    else:
        # Nonverb variants
        var_order = nonverb_variant_order

    # Re-order correctly
    for i, v_list in enumerate(var_order):
        for v in v_list:
            if v in variants:
                spec[i] = v

    wordforms = BIN.lookup_forms(
        word,
        cat or None,  # type: ignore
        "".join(spec),
    )

    if len(wordforms) == 0:
        # BÍN can't find variants, weird word,
        # use double-quotes
        return red(gi.name)
    if len(wordforms) == 1:
        # Author of grammar should probably use double-quotes
        # (except if this is due to backslash specification, like /fall)
        return yellow(wordforms[0].bmynd)
    if len(set(wf.bmynd for wf in wordforms)) == 1:
        # All variants are the same here,
        # author of grammar should maybe use double-quotes instead
        return lightred(f"({'|'.join(wf.bmynd for wf in wordforms)})")

    # Sort wordforms in a logical order
    wordforms.sort(key=_binentry_to_int)

    # Join all matched wordforms together (within parenthesis)
    return lightcyan(f"({'|'.join(wf.bmynd for wf in wordforms)})")


def generate_from_cfg(
    grammar: QueryGrammar,
    *,
    root: Optional[Union[Nonterminal, str]] = None,
    depth: Optional[int] = None,
    n: Optional[int] = None,
) -> Iterable[str]:
    """
    Generates an iterator of all sentences from
    a context free grammar.
    """

    if root is None:
        root = grammar.root
    elif isinstance(root, str):
        root = grammar.nonterminals.get(root)
    assert (
        root is not None and root in grammar.nt_dict
    ), "Invalid root, make sure it exists in the grammar"

    if depth is None:
        depth = sys.maxsize // 2

    assert depth is not None, "Invalid depth"
    assert 0 < depth <= sys.maxsize, f"Depth must be in range 1 - {sys.maxsize}"

    if (
        len(grammar.nt_dict[root][0][1]._rhs) == 1  # type: ignore
        and grammar.nt_dict[root][0][1]._rhs[0].name == '""'  # type: ignore
    ):
        # Remove hack empty (Query -> "") production
        grammar.nt_dict[root].pop(0)

    iter: Iterable[List[str]] = itertools.chain.from_iterable(
        _generate_all(
            grammar,
            pt[1]._rhs,  # type: ignore
            depth,
        )
        for pt in grammar.nt_dict[root]
    )

    # n=None means return all sentences, otherwise return n sentences
    iter = itertools.islice(iter, 0, n)

    return (" ".join(sl) for sl in iter)


def _generate_all(
    grammar: QueryGrammar, items: List[_GIType], depth: int
) -> Iterator[List[str]]:
    if items:
        try:
            if items[0].name == "'?'?" and len(items) == 1:
                # Skip the optional final question mark
                # (common in query grammars)
                yield []
            else:
                for frag1 in _generate_one(grammar, items[0], depth):
                    for frag2 in _generate_all(grammar, items[1:], depth):
                        yield frag1 + frag2
        except RecursionError:
            raise RecursionError(
                "The grammar has a rule that yields infinite recursion!\n"
                "Try running again with a smaller max depth set.\n"
                f"Depth: {depth}.\nCurrent nonterminal: {items[0]}"
            )
    else:
        yield []


# Recursive nonterminals raise a recursion error,
# match them with this regex and skip traversal
# (note: there are probably more recursive
# nonterminals, they can be added here)
_RECURSIVE_NT = re.compile(r"^Nl([/_][a-zA-Z0-9]+)*$")
_PLACEHOLDER_RE = re.compile(r"{([\w]+?)}")
_PLACEHOLDER_PREFIX = "GENERATORPLACEHOLDER_"
_PLACEHOLDER_PREFIX_LEN = len(_PLACEHOLDER_PREFIX)


def _generate_one(
    grammar: QueryGrammar, gi: _GIType, depth: int
) -> Iterator[List[str]]:
    if depth > 0:
        if _RECURSIVE_NT.fullmatch(gi.name):
            # Special handling of Nl nonterminal,
            # since it is recursive
            yield [pink(f"<{gi.name}>")]
        elif gi.name.startswith(_PLACEHOLDER_PREFIX):
            # Placeholder nonterminal (replaces)
            yield [blue(f"{{{gi.name[_PLACEHOLDER_PREFIX_LEN:]}}}")]
        elif isinstance(gi, Nonterminal):
            if gi.is_optional and gi.name.endswith("*"):
                # Star nonterminal, signify using brackets and '...'
                prod = grammar.nt_dict[gi][0][1]
                gi = prod._rhs[-1]  # type: ignore
                # Literal text if gi is terminal,
                # otherwise surround nonterminal name with curly brackets
                t = gi.literal_text or f"{{{gi.name}}}"
                yield [purple(f"[{t} ...]")]
            else:
                # Nonterminal, fetch its productions
                for pt in grammar.nt_dict[gi]:
                    yield from _generate_all(
                        grammar,
                        pt[1]._rhs,  # type: ignore
                        depth - 1,
                    )
        else:
            if isinstance(gi, BIN_LiteralTerminal):
                lit = gi.literal_text
                if lit:
                    yield [lit]
                else:
                    yield [get_wordform(gi)]
            else:
                # Special nonterminals such as no, sérnafn, töl, ...
                yield [green(f"<{gi.name}>")]
    else:
        yield [lightblue(f"{{{gi.name}}}")]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Generates sentences from a context free grammar."
    )
    parser.add_argument(
        "files",
        nargs="+",
        help="File/s containing the grammar fragments",
    )
    parser.add_argument(
        "-r",
        "--root",
        default="Query",
        help="Root nonterminal to start from",
    )
    parser.add_argument(
        "-d",
        "--depth",
        type=int,
        help="Maximum depth of the generated sentences",
    )
    parser.add_argument(
        "-n",
        "--num",
        type=int,
        help="Maximum number of sentences to generate",
    )
    parser.add_argument(
        "-s",
        "--strict",
        action="store_true",
        help="Enable strict mode, adds some opinionated assertions about the grammar",
    )
    parser.add_argument(
        "-c",
        "--color",
        action="store_true",
        help="Enables colored output (to stdout only)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Write output to file instead of stdout (faster)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Forcefully overwrite output file, ignoring any warnings",
    )
    parser.add_argument("--max-size", type=int, help="Maximum output filesize in MiB.")
    args = parser.parse_args()

    strict = args.strict

    if args.num:
        args.num += 1

    output = sys.stdout
    p: Optional[Path] = None
    if args.output:
        p = args.output
        assert isinstance(p, Path)
        if (p.is_file() or p.exists()) and not args.force:
            print("Output file already exists!")
            exit(1)

    if not args.color or p is not None:
        useless: ColorF = lambda s: s
        # Undefine color functions
        [
            bold,
            black,
            red,
            green,
            orange,
            blue,
            purple,
            cyan,
            lightgrey,
            darkgrey,
            lightred,
            lightgreen,
            yellow,
            lightblue,
            pink,
            lightcyan,
        ] = [useless] * 16

    grammar_fragments: str = PREAMBLE

    # We replace {...} format strings with a placeholder
    placeholder_defs: str = ""

    def placeholder_func(m: Match[str]) -> str:
        """
        Replaces {...} format strings in grammar with an empty nonterminal.
        We then handle these nonterminals specifically in _generate_one().
        """
        global placeholder_defs
        new_nt = f"{_PLACEHOLDER_PREFIX}{m.group(1)}"
        # Create empty production for this nonterminal ('keep' tag just in case)
        placeholder_defs += f"\n{new_nt} → ∅\n$tag(keep) {new_nt}\n"
        # Replace format string with reference to new nonterminal
        return new_nt

    for file in [BIN_Parser._GRAMMAR_FILE] + args.files:  # type: ignore
        with open(file, "r") as f:
            grammar_fragments += "\n"
            grammar_fragments += _PLACEHOLDER_RE.sub(placeholder_func, f.read())

    # Add all the placeholder nonterminal definitions we added
    grammar_fragments += placeholder_defs

    # Initialize QueryGrammar class from grammar files
    grammar = QueryGrammar()
    grammar.read_from_generator(args.files[0], iter(grammar_fragments.split("\n")))

    # Create sentence generator
    g = generate_from_cfg(
        grammar,
        root=args.root,
        depth=args.depth,
        n=args.num,
    )

    if p is not None:
        # Writing to file
        with p.open("w") as f:
            if args.max_size:
                max_size = args.max_size * MiB
                for sentence in g:
                    print(sentence, file=f)
                    if f.tell() >= max_size:
                        break
            else:
                for sentence in g:
                    print(sentence, file=f)
    else:
        # Writing to stdout
        try:
            for sentence in g:
                print(sentence)
        finally:
            # Just in case an error is raised
            # before terminal color is reset
            if args.color:
                print(_reset, end="")
