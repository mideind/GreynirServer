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

import logging
import random

from query import Query, QueryStateDict, AnswerTuple
from queries import gen_answer
from tree import Result, Node


_IOT_QTYPE = "IOT"

TOPIC_LEMMAS = ["ljós", "kveikja"]


def help_text(lemma: str) -> str:
    """Help text to return when query.py is unable to parse a query but
    one of the above lemmas is found in it"""
    return "Ég skil þig ef þú segir til dæmis: {0}.".format(
        random.choice(
            (
                "Kastaðu teningi",
                "Kastaðu tíu hliða teningi",
                "Fiskur eða skjaldarmerki",
                "Kastaðu teningi",
                "Kastaðu peningi",
                "Veldu tölu á milli sjö og þrettán",
            )
        )
    )


# This module wants to handle parse trees for queries
HANDLE_TREE = True

# The grammar nonterminals this module wants to handle
QUERY_NONTERMINALS = {"QIOT"}

# The context-free grammar for the queries recognized by this plug-in module
GRAMMAR = """

Query →
    QIOT

QIOT → QIOTQuery '?'?

QIOTQuery →
    "kveiktu" "ljósin"

"""


def QIOTQuery(node: Node, params: QueryStateDict, result: Result) -> None:
    result.qtype = _IOT_QTYPE


def sentence(state: QueryStateDict, result: Result) -> None:
    """Called when sentence processing is complete"""
    q: Query = state["query"]
    if "qtype" not in result:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
        return

    # Successfully matched a query type
    q.set_qtype(result.qtype)

    try:
        #kalla í javascripts stuff
        q.set_answer(*gen_answer("ég var að kveikja ljósin!"))
    except Exception as e:
        logging.warning("Exception while processing random query: {0}".format(e))
        q.set_error("E_EXCEPTION: {0}".format(e))
        raise