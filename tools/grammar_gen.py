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

from typing import Iterable, Iterator, List, Optional, Set, Union

import os
import sys
import itertools


# Hack to make this Python program executable from the tools subdirectory
basepath, _ = os.path.split(os.path.realpath(__file__))
_UTILS = os.sep + "tools"
if basepath.endswith(_UTILS):
    basepath = basepath[0 : -len(_UTILS)]
    sys.path.append(basepath)


from islenska import Bin
from reynir.grammar import Nonterminal, Terminal
from reynir.binparser import BIN_Parser, BIN_LiteralTerminal
from reynir.bintokenizer import ALL_CASES

from query import QueryGrammar

# TODO: Create wrapper functions, output to file with optional size limit in MB and such
# TODO: Allow replacing special terminals (no, sérnafn, lo, ...) with words

# Grammar item type
_GIType = Union[Nonterminal, Terminal]
# BÍN, for word lookups
BIN = Bin()
# Variants not needed for lookup
SKIPVARS = frozenset(("op", "subj", "0", "1", "2"))

PREAMBLE = """
QueryRoot →
    Query

Query → "" # Hack, in case we aren't testing a query grammar (prevents an error)

"""

strict = True


def get_wordform(gi: BIN_LiteralTerminal) -> str:
    """
    Fetch all possible wordforms for a literal terminal
    specification and return as readable string.
    """
    global strict
    word, cat, variants = gi.first, gi.category, gi.variants
    if strict and gi.name != '""':
        assert (
            cat is not None
        ), f"Specify category for single quoted terminal: {gi.name}"
        assert (
            len(variants) > 0
        ), f"Specify variant for single quoted terminal: {gi.name}"

    realvars: Union[Set[str], Iterable[str]]
    if cat == "so":
        # Get rid of irrelevant variants for verbs
        realvars = set(variants) - SKIPVARS
        if "lhþt" not in realvars:
            # No need for cases if this is not LHÞT
            realvars -= ALL_CASES
    else:
        realvars = variants

    wordforms = BIN.lookup_variants(word, cat or "no", tuple(realvars), lemma=word)
    # Return the wordform if only one option,
    # otherwise join all allowed wordforms together within parenthesis
    t = (
        wordforms[0].bmynd
        if len(wordforms) == 1
        else f"({'|'.join(wf.bmynd for wf in wordforms)})"
    )
    if t == "()" and word:
        t = gi.name
    return t


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

    iter: Iterable[List[str]] = itertools.chain.from_iterable(
        _generate_all(
            grammar,
            pt[1]._rhs,  # type: ignore
            depth,
        )
        for pt in grammar.nt_dict[root]
    )

    # Start at index one to remove empty (Query -> "") production
    # n=None means return all sentences, otherwise return n sentences
    iter = itertools.islice(iter, 1, n)

    return (" ".join(sl) for sl in iter)


def _generate_all(
    grammar: QueryGrammar, items: List[_GIType], depth: int
) -> Iterator[List[str]]:
    if items:
        try:
            for frag1 in _generate_one(grammar, items[0], depth):
                for frag2 in _generate_all(grammar, items[1:], depth):
                    yield frag1 + frag2
        except RecursionError as error:
            # Helpful error message while still showing the recursion stack.
            raise RuntimeError(
                f"The grammar has rule(s) that yield infinite recursion! Depth: {depth}, {sys.maxsize}"
            ) from error
    else:
        yield []


def _generate_one(
    grammar: QueryGrammar, gi: _GIType, depth: int
) -> Iterator[List[str]]:
    if depth > 0:
        if gi.name == "Nl":
            # Special handling of Nl nonterminal, since it is recursive
            yield ["<Nl>"]
        elif isinstance(gi, Nonterminal):
            if gi.is_optional and gi.name.endswith("*"):
                # Star nonterminal, signify using brackets and '...'
                prod = grammar.nt_dict[gi][0][1]
                gi = prod._rhs[-1]  # type: ignore
                # Literal text if gi is terminal,
                # otherwise surround nonterminal name with curly brackets
                t = gi.literal_text or f"{{{gi.name}}}"
                yield [f"[{t} ...]"]
            else:
                # Nonterminal, fetch its productions
                for pt in grammar.nt_dict[gi]:
                    yield from _generate_all(
                        grammar,
                        pt[1]._rhs,  # type: ignore
                        depth - 1,
                    )
        else:
            if gi.name == "'?'":
                pass
            elif isinstance(gi, BIN_LiteralTerminal):
                lit = gi.literal_text
                if lit:
                    yield [lit]
                else:
                    yield [get_wordform(gi)]
            else:
                # Special nonterminals such as no, sérnafn, töl, ...
                yield [f"<{gi.name}>"]
    else:
        yield [f"{{{gi.name}}}"]


def main():
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
        "--no-strict",
        action="store_true",
        help="Disable strict mode, removes some assertions",
    )
    args = parser.parse_args()

    global strict
    strict = not args.no_strict

    grammar_fragments: str = PREAMBLE
    for file in [BIN_Parser._GRAMMAR_FILE] + args.files:  # type: ignore
        with open(file, "r") as f:
            grammar_fragments += "\n"
            grammar_fragments += f.read()

    grammar = QueryGrammar()
    grammar.read_from_generator(args.files[0], iter(grammar_fragments.split("\n")))

    if args.num:
        # For empty production at start
        args.num += 1

    for sentence in generate_from_cfg(
        grammar,
        root=args.root,
        depth=args.depth,
        n=args.num,
    ):
        print(sentence)

    return grammar


if __name__ == "__main__":
    g = main()
