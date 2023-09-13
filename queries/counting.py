"""

    Greynir: Natural language processing for Icelandic

    Counting query response module

    Copyright (C) 2023 Miðeind ehf.

       This program is free software: you can redistribute it and/or modify
       it under the terms of the GNU General Public License as published by
       the Free Software Foundation, either version 3 of the License, or
       (at your option) any later version.
       This program is distributed in the hope that it will be useful,
       but WITHOUT ANY WARRANTY; without even the implied warranty of
       MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
       GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program. If not, see http://www.gnu.org/licenses/.


    This module handles requests to count up or down.

"""

from typing import Dict

import logging
import random
from datetime import datetime, timedelta

from icespeak import gssml
from queries.util import parse_num, gen_answer, read_grammar_file
from queries import Query, QueryStateDict
from tree import Result, Node


_COUNTING_QTYPE = "Counting"


TOPIC_LEMMAS = ["telja"]


def help_text(lemma: str) -> str:
    """Help text to return when query processor is unable to parse a query but
    one of the above lemmas is found in it"""
    return "Ég skil þig ef þú segir til dæmis: {0}.".format(
        random.choice(("Teldu upp að tíu", "Teldu niður frá tuttugu"))
    )


# This module wants to handle parse trees for queries
HANDLE_TREE = True

# The grammar nonterminals this module wants to handle
QUERY_NONTERMINALS = {"QCounting"}

# The context-free grammar for the queries recognized by this plug-in module
GRAMMAR = read_grammar_file("counting")


def QCountingQuery(node: Node, params: QueryStateDict, result: Result) -> None:
    # Set the query type
    result.qtype = _COUNTING_QTYPE


def QCountingUp(node: Node, params: QueryStateDict, result: Result) -> None:
    result.qkey = "CountUp"


def QCountingDown(node: Node, params: QueryStateDict, result: Result) -> None:
    result.qkey = "CountDown"


def QCountingBetween(node: Node, params: QueryStateDict, result: Result) -> None:
    result.qkey = "CountBetween"


def QCountingFirstNumber(node: Node, params: QueryStateDict, result: Result) -> None:
    result.first_num = int(parse_num(node, result._canonical))


def QCountingSecondNumber(node: Node, params: QueryStateDict, result: Result) -> None:
    result.second_num = int(parse_num(node, result._canonical))


_DEFAULT_DELAY = 0.4
_SPEED2DELAY = {"mjög hægt": 2.0, "hægt": 1.0, "hratt": 0.1, "mjög hratt": 0.0}
_MAX_COUNT = 100


def QCountingSpeed(node: Node, params: QueryStateDict, result: Result) -> None:
    result.delay = _SPEED2DELAY.get(node.contained_text())


def _gen_count(q: Query, result: Result):
    num_range = None
    if result.qkey == "CountUp":
        num_range = list(range(1, result.first_num + 1))
    elif result.qkey == "CountDown":
        num_range = list(range(0, result.first_num))[::-1]
    else:
        (fn, sn) = (result.first_num, result.second_num)
        if fn > sn:
            (fn, sn) = (sn, fn)
        num_range = list(range(fn, sn + 1))

    if len(num_range) > _MAX_COUNT:
        return gen_answer("Ég nenni ekki að telja svona lengi.")

    answ = f"{num_range[0]}…{num_range[-1]}"
    response: Dict[str, str] = dict(answer=answ)
    delay = result.get("delay", _DEFAULT_DELAY)

    voice = gssml(type="vbreak", time=f"{delay}s").join(
        gssml(n, type="number", gender="kk") for n in num_range
    )

    return response, answ, voice


def sentence(state: QueryStateDict, result: Result) -> None:
    """Called when sentence processing is complete"""
    q: Query = state["query"]
    if "qtype" in result and "qkey" in result:
        # Successfully matched a query type
        q.set_qtype(result.qtype)
        q.set_key(result.qkey)

        try:
            r = _gen_count(q, result)
            q.set_answer(*r)
            q.set_expires(datetime.utcnow() + timedelta(hours=24))
        except Exception as e:
            logging.warning(f"Exception while processing counting query: {e}")
            q.set_error(f"E_EXCEPTION: {e}")
    else:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
