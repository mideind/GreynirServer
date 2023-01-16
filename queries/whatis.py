"""

    Greynir: Natural language processing for Icelandic

    'What is?' query module

    Copyright (C) 2023 Miðeind ehf.
    Original author: Vilhjálmur Þorsteinsson

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


    This module implements handlers for "What is X?" type queries,
    i.e. "Hvað er X?".

    The module is currently disabled.

"""

from typing import Set

from queries import ResponseType, QueryStateDict
from queries.util import read_grammar_file
from tree import Node, ParamList, Result

# --- Begin "magic" module constants ---

# The following constants - HANDLE_TREE, PRIORITY and GRAMMAR -
# are "magic"; they are read by query.py to determine how to
# integrate this query module into the server's set of active modules.

# Indicate that this module wants to handle parse trees for queries
HANDLE_TREE = True

# Invoke this processor before other tree processors
PRIORITY = 1

QUERY_NONTERMINALS: Set[str] = set()  # { "QWhatIsQuery" }

GRAMMAR = read_grammar_file("whatis")

# --- End of "magic" module constants ---


def QWhatIsEntity(node: Node, params: ParamList, result: Result) -> None:
    result.qtype = "WhatIs"
    result.qkey = result._nominative


def EfLiður(node: Node, params: ParamList, result: Result) -> None:
    """Eignarfallsliðir haldast óbreyttir,
    þ.e. þeim á ekki að breyta í nefnifall"""
    result._nominative = result._text


def FsMeðFallstjórn(node: Node, params: ParamList, result: Result) -> None:
    """Forsetningarliðir haldast óbreyttir,
    þ.e. þeim á ekki að breyta í nefnifall"""
    result._nominative = result._text


def sentence(state: QueryStateDict, result: Result) -> None:
    """Called when sentence processing is complete"""
    q = state["query"]
    if "qtype" not in result:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
        return
    # Successfully matched a query type
    q.set_qtype(result.qtype)
    q.set_key(result.qkey)
    # session = state.get("session")
    # Select a query function and exceute it
    answer: str = result.qtype + ": " + result.qkey
    voice_answer: str = answer
    response: ResponseType = dict(answer=answer)
    q.set_answer(response, answer, voice_answer)
