"""

    Reynir: Natural language processing for Icelandic

    Television schedule query response module

    Copyright (C) 2019 Miðeind ehf.

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


    This module handles queries related to counting up or down.

"""

import logging
import random
from datetime import datetime, timedelta

from queries import parse_num


_COUNTING_QTYPE = "Counting"


TOPIC_LEMMAS = ["teldu", "telja"]


def help_text(lemma):
    """ Help text to return when query.py is unable to parse a query but
        one of the above lemmas is found in it """
    return "Ég get svarað ef þú segir til dæmis: {0}?".format(
        random.choice(("Teldu upp í tíu", "Teldu niður frá tuttugu"))
    )


# This module wants to handle parse trees for queries
HANDLE_TREE = True

# The context-free grammar for the queries recognized by this plug-in module
GRAMMAR = """

Query →
    QCounting

QCounting → QCountingQuery '?'? 

QCountingQuery →
    QCountingUp | QCountingDown | QCountingBetween

QCountingUp →
    "teldu" QCountingSpeed? "upp" "að" QCountingFirstNumber
    | "teldu" QCountingSpeed? "upp" "í" QCountingFirstNumber
    | "teldu" QCountingSpeed? "upp" "til" QCountingFirstNumber

QCountingDown →
    "teldu" QCountingSpeed? "niður" "frá" QCountingFirstNumber

QCountingBetween →
    "teldu" QCountingSpeed? "frá" QCountingFirstNumber "upp"? "til" QCountingSecondNumber
    | "teldu" QCountingSpeed? "frá" QCountingFirstNumber "upp"? "í" QCountingSecondNumber
    | "teldu" QCountingSpeed? "frá" QCountingFirstNumber "upp"? "að" QCountingSecondNumber

QCountingFirstNumber →
    to | töl | tala

QCountingSecondNumber →
    to | töl | tala

QCountingSpeed →
    "mjög" "hægt" | "hægt" | "hratt" | "mjög" "hratt"

$score(+35) QCounting

"""


def QCountingQuery(node, params, result):
    # Set the query type
    result.qtype = _COUNTING_QTYPE


def QCountingUp(node, params, result):
    result.qkey = "CountUp"


def QCountingDown(node, params, result):
    result.qkey = "CountDown"


def QCountingBetween(node, params, result):
    result.qkey = "CountBetween"


def QCountingFirstNumber(node, params, result):
    result.first_num = int(parse_num(node, result._canonical))


def QCountingSecondNumber(node, params, result):
    result.second_num = int(parse_num(node, result._canonical))


_SPEED2DELAY = {"mjög hægt": 2.0, "hægt": 1.0, "hratt": 0.1, "mjög hratt": 0.0}


def QCountingSpeed(node, params, result):
    result.delay = _SPEED2DELAY.get(node.contained_text())


def _gen_count(q, result):
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

    answ = "{0}…{1}".format(num_range[0], num_range[-1])
    response = dict(answer=answ)
    voice = ""
    for n in num_range:
        # Default 0.4s delay results in roughly 1 sec per number in count
        delay = result["delay"] if "delay" in result else 0.4
        voice += '{0} <break time="{1}s"/>'.format(n, delay)

    return response, answ, voice


def sentence(state, result):
    """ Called when sentence processing is complete """
    q = state["query"]
    if "qtype" in result and "qkey" in result:
        # Successfully matched a query type
        q.set_qtype(result.qtype)
        q.set_key(result.qkey)

        try:
            r = _gen_count(q, result)
            q.set_answer(*r)
            q.set_expires(datetime.utcnow() + timedelta(hours=24))
        except Exception as e:
            logging.warning("Exception while processing counting query: {0}".format(e))
            q.set_error("E_EXCEPTION: {0}".format(e))
    else:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")