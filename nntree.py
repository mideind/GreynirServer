"""
    Reynir: Natural language processing for Icelandic

    Neural Network Utilities

    Copyright (C) 2018 Miðeind ehf

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


    This module contains a handful of useful functions for parsing the
    output from an IceParsing neural network model and working with the
    result.

"""

from __future__ import print_function
from enum import IntEnum
import logging

import numpy as np
import tokenizer
import grammar_consts
from reynir import matcher
from parsing_subtokens import ParsingSubtokens, MISSING


PROJECT_PATH = os.path.dirname(__file__)
TOK_PATH = os.path.join(PROJECT_PATH, "resources", "parsing_tokens_180729.txt")
ENCODER = CompositeTokenEncoder(TOK_PATH, version=2)

NONTERMINALS = ENCODER._nonterminals
NONTERM_L = ENCODER._nonterm_l
NONTERM_R = ENCODER._nonterm_r
TERMINALS = ENCODER._terminals
TERMINALS = ENCODER._terminals
R_TO_L = ENCODER._r_to_l


class Node:
    """ Generic tree implementation """

    def __init__(self, name, is_terminal=False, data=None):
        self.name = name
        self.data = data
        self.children = []
        self.is_terminal = is_terminal

    def add_child(self, node):
        self.children.append(node)
        return self

    def has_children(self):
        return bool(self.children)

    def to_dict(self):
        if not self.children:
            json_node = _json_terminal_node(self.name, self.data)
        else:
            json_node = _json_nonterminal_node(self.name)
            json_node["p"] = [c.to_dict() for c in self.children]
        return json_node

    def to_postfix(self):
        result = []
        for child in self.children:
            result.extend(child.to_postfix())
        result.append(self.name)
        return result

    def __str__(self):
        text = (" " + self.data) if self.data is not None else ""
        return "<" + self.name + text + ">"

    def __repr__(self):
        if self.is_terminal:
            return self.__str__()
        result = [self.__str__()]
        for child in self.children:
            result.extend(child.__repr__())
        result.append(Node("/" + self.name).__str__())
        return "".join(result)

    def _pprint(self, _prefix="  ", depth=0):
        print("%s%s" % (_prefix * depth, self.__str__()))
        for c in self.children:
            c._pprint(_prefix=_prefix, depth=depth + 1)

    def pprint(self, indent=4):
        self._pprint(_prefix=" " * indent)

    @staticmethod
    def contains(forest, name):
        if isinstance(forest, Node):
            forest = [forest]
        for tree in forest:
            if tree.name == name:
                return True
            if any(Node.contains(c, name) for c in tree.children):
                return True
        return False


class ParseResult(IntEnum):
    """ Result types for the parsing of flat parse trees that are return by
        the NMT parsing model and the corresponding natural language source text
        into a (non) flat parse tree """

    # Successful parse
    SUCCESS = 0
    # A text token was not consumed before reaching end of parse tok stream
    INCOMPLETE = 1
    # A corresponding left token is missing before a right token is encountered
    UNOPENED_RTOKEN = 2
    # A left token is not closed before the surrounding nonterminal token is closed
    UNCLOSED_LTOKEN = 3
    # Terminal descends from pseudo root instead of a proper nonterminal
    TERM_DESC_ROOT = 5
    # Nonterminal has no terminal or leaf token
    EMPTY_NONTERM = 6
    # Multiple successful parse trees
    MULTI = 7
    # Undocumented parse failure
    FAILURE = 8


def parse_flat_tree_to_nodes(parse_toks, text_toks=None, verbose=False):
    """Parses list of toks (parse_toks) into a legal tree structure or None,
       If the corresponding tokenized source text is provided, it is
       included in the tree"""

    vprint = logging.debug if verbose else (lambda *ar, **kw: None)

    if not parse_toks or parse_toks[0] not in TOKENS.NONTERMINALS:
        raise ValueError("Invalid parse tokens.")

    root = Node(name="ROOT", is_terminal=False)  # Pseudo root
    stack = []
    parent = root
    txt_count = 0

    for idx, tok in enumerate(parse_toks):
        if tok in MISSING:
            vprint("Encountered missing token: '{}'".format(tok))
            continue
        if tok not in TOKENS.NONTERMINALS:
            if parent == root:
                msg = "Error: Tried to parse terminal node {} as descendant of root."
                vprint(msg.format(tok))

                tree = root.children[0] if root.children else None
                return tree, ParseResult.TERM_DESC_ROOT

            if text_toks and txt_count < len(text_toks):
                parse_tok, text_tok = tok, text_toks[txt_count]
                new_node = Node(parse_tok, data=text_tok, is_terminal=True)
                txt_count += 1
            else:
                new_node = Node(tok)

            string = "{}  {}".format(len(stack) * "    ", tok)
            string = string if not new_node.data else string + new_node.data
            vprint(string)

            parent.add_child(new_node)
            continue

        # tok is in TOKENS.NONTERMINALS and therefore is either a left or right nonterminal token
        if tok in TOKENS.NONTERM_L:
            new_node = Node(tok, is_terminal=False)
            parent.add_child(new_node)
            stack.append(parent)
            parent = new_node

            vprint(len(stack) * "    " + new_node.name)
            continue

        # Token must be a legal right nonterminal since it is not a left token
        # A right token must be matched by its corresponding left token
        if tok not in R_TO_L or parent.name != R_TO_L[tok]:
            msg = "Error: Found illegal nonterminal {}, expected right nonterminal"
            vprint(msg.format(tok))

            tree = root.children[0] if root.children else None
            return tree, ParseResult.UNOPENED_RTOKEN
        # Empty NONTERMINALS are not allowed
        if not parent.has_children():
            msg = ["{}{}".format(len(stack) * "    ", tok) for tok in parse_toks[idx:]]
            vprint("\n".join(msg))
            vprint("Error: Tried to close empty nonterminal {}".format(tok))

            tree = root.children[0] if root.children else None
            return tree, ParseResult.EMPTY_NONTERM
        parent = stack.pop()

    if len(stack) > 1:
        vprint("Error: Reached end of parse tokens but stack is not empty")
        vprint([item.name for item in stack])
        tree = root.children[0] if root.children else None
        return tree, ParseResult.INCOMPLETE

    if not root.children:
        return None, ParseResult.FAILURE
    if len(root.children) == 1:
        return root.children[0], ParseResult.SUCCESS

    return root.children, ParseResult.MULTI


def tokenize_flat_tree(parse_str):
    return parse_str.strip().split(" ")


def parse_tree(flat_parse_str):
    return parse_flat_tree_to_nodes(tokenize_flat_tree(flat_parse_str))


def parse_tree_with_text(flat_parse_str, text):
    parse_toks = tokenize_flat_tree(flat_parse_str)
    text_toks = [tok.txt for tok in tokenizer.tokenize(text) if tok.txt]
    return parse_flat_tree_to_nodes(parse_toks, text_toks)


# TODO: Use cache
def _json_terminal_node(tok, text="placeholder"):
    """ first can be:
            abfn
            ao
            fn
            fs
            gata
            gr
            lo
            no
            person
            pfn
            raðnr
            sérnafn
            so
            so_0
            so_1
            so_2
            tala
            to
            töl"""

    subtokens = tok.split("_")
    first = subtokens[0].split("_", 1)[0]

    tail_start = 1
    if first == "so":
        head = subtokens[0]
        suffix = head[-1]
        if "_" in head and suffix in "012":
            tail_start += int(suffix)
    tail = subtokens[tail_start:]

    if first == "no":
        cat = [t for t in grammar_consts.GENDERS if t in tail]
        cat = "" if not cat else cat[0]
        case = [t for t in grammar_consts.CASES if t in tail]
        case = "" if not case else case[0]
        number = [t for t in grammar_consts.NUMBERS if t in tail]
        number = "" if not number else number[0]
        gr = "gr" if "gr" in tail else ""

        b = "-".join([t for t in [case, number, gr] if t])

        new_node = dict(t=tok, x=text, k="WORD", b=b, c=cat)

    elif first == "st":
        new_node = dict(t=tok, x=text, k="WORD", c="st", b="-")

    elif first == "eo":
        new_node = dict(t=tok, x=text, k="WORD", c="ao", b="ao")

    elif first == "entity":
        new_node = dict(t=tok, x=text, k="ENTITY")

    elif first == "p":
        new_node = dict(x=text, k="PUNCTUATION")

    else:
        b = "-".join([t for t in tail if t])
        new_node = dict(x=text, t=tok, c=first, k="WORD", b=b)

    if "b" in new_node:
        new_node["b"] = (
            new_node["b"]
            .upper()
            .replace("GR", "gr")
            .replace("P1", "1P")
            .replace("P2", "2P")
            .replace("P3", "3P")
        )

    if "k" in new_node and new_node["k"] in ["ENTITY", "WORD"]:
        new_node["s"] = text if text else "-"

    return new_node


# TODO: Use cache
def _json_nonterminal_node(tok):
    new_node = dict(
        i=tok, n=matcher._DEFAULT_ID_MAP[tok]["name"], k="NONTERMINAL", p=[]
    )
    return new_node
