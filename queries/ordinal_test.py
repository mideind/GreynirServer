"""

    Greynir: Natural language processing for Icelandic

    Randomness query response module

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

    This query module handles queries related to the generation
    of random numbers, e.g. "Kastaðu tengingi", "Nefndu tölu milli 5 og 10", etc.

"""

# TODO: Suport commands of the form "Kastaðu tveir dé 6", D&D style die rolling lingo

import logging
import random

from queries import Query, QueryStateDict, AnswerTuple
from queries.util import gen_answer, read_grammar_file
from queries.arithmetic import add_num, terminal_num
from speech.norm import gssml
from tree import Result, Node


_ORDINAL_QTYPE = "Ordinal"


# This module wants to handle parse trees for queries
HANDLE_TREE = True

# The grammar nonterminals this module wants to handle
QUERY_NONTERMINALS = {"QOrdinal"}

# The context-free grammar for the queries recognized by this plug-in module
GRAMMAR = read_grammar_file("ordinal_test")


def QOrdinal(node: Node, params: QueryStateDict, result: Result) -> None:
    result.qtype = _ORDINAL_QTYPE


def sentence(state: QueryStateDict, result: Result) -> None:
    """Called when sentence processing is complete"""
    q: Query = state["query"]
    if "qtype" not in result:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
        return

    # Successfully matched a query type
    q.set_qtype(result.qtype)

    print("I'm here " + result.qtype)
    print("I am " + str(result.numbers[0]) + ".")
    val = str(result.numbers[0])
    try:
        q.set_answer({"answer":val}, val, "")
    except Exception as e:
        logging.warning("Exception while processing random query: {0}".format(e))
        q.set_error("E_EXCEPTION: {0}".format(e))
        raise
