"""

    Greynir: Natural language processing for Icelandic

    Opinion query response module

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


    This module handles queries related to Embla's opinions.

"""


from datetime import datetime, timedelta

from query import Query, QueryStateDict
from queries import gen_answer, read_grammar_file
from tree import Result, Node


_OPINION_QTYPE = "Opinion"


# Indicate that this module wants to handle parse trees for queries,
# as opposed to simple literal text strings
HANDLE_TREE = True

# The grammar nonterminals this module wants to handle
QUERY_NONTERMINALS = {"QOpinion"}

# The context-free grammar for the queries recognized by this plug-in module
GRAMMAR = read_grammar_file("opinion")


def QOpinionQuery(node: Node, params: QueryStateDict, result: Result) -> None:
    result["qtype"] = _OPINION_QTYPE


def QOpinionSubject(node: Node, params: QueryStateDict, result: Result) -> None:
    result["subject_nom"] = result._nominative


def sentence(state: QueryStateDict, result: Result) -> None:
    """Called when sentence processing is complete"""
    q: Query = state["query"]

    if "qtype" not in result or "subject_nom" not in result:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
        return

    # OK, we've successfully matched a query type
    subj: str = result["subject_nom"]
    answer = "Ég hef enga sérstaka skoðun í þeim efnum."
    q.set_answer(*gen_answer(answer))
    q.set_qtype(_OPINION_QTYPE)
    q.set_context(dict(subject=subj))
    q.set_key(subj)
    q.set_expires(datetime.utcnow() + timedelta(hours=24))
