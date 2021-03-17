"""

    Greynir: Natural language processing for Icelandic

    Randomness query response module

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

    This query module handles queries related to the generation
    of random numbers, e.g. "Kastaðu tengingi", "Nefndu tölu milli 5 og 10", etc.

"""

# TODO: Suport commands of the form "Kastaðu tveir dé 6", D&D style die rolling lingo

import logging
import random

from query import Query
from queries import gen_answer
from queries.arithmetic import add_num, terminal_num


_RANDOM_QTYPE = "Random"

TOPIC_LEMMAS = ["teningur", "skjaldarmerki", "handahóf"]


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
QUERY_NONTERMINALS = {"QRandom"}

# The context-free grammar for the queries recognized by this plug-in module
GRAMMAR = """

Query →
    QRandom

QRandom → QRandomQuery '?'?

QRandomQuery →
    QRandomDiceRoll | QRandomBetween | QRandomHeadsOrTails

QRandomHeadsOrTails →
    "fiskur" "eða" "skjaldarmerki" | "skjaldarmerki" "eða" "fiskur"
    | "kastaðu" "upp"? "peningi" | "kastaðu" "upp"? "pening" | "kastaðu" "upp"? "krónu"

QRandomDiceRoll →
    "kastaðu" QRandomDiceSides? QRandomDie QRandomForMe?
    | "kastaðu" QRandomForMe? QRandomDiceSides? QRandomDie
    | "kasta" QRandomDiceSides? QRandomDie
    | "geturðu" "kastað" QRandomDiceSides? QRandomDie QRandomForMe?
    | "geturðu" "kastað" QRandomForMe? QRandomDiceSides? QRandomDie
    | "kastaðu" "upp" "á" "teningnum" QRandomForMe?
    | "kastaðu" "upp" "á" "teningi" QRandomForMe?

QRandomForMe →
    "fyrir" "mig"

QRandomDie →
    # Allow "tening" (accusative) to make it a bit more robust. Common error.
    "teningi" | "tening" | "teningnum" | "teningunum"

QRandomDiceSides →
    QRandNumber "hliða"

QRandomBetween →
    QRandAction "tölu" "á"? "milli" QRandNumber "og" QRandNumber QRandRand?
    | QRandAction "tölu" QRandRand? "á"? "milli" QRandNumber "og" QRandNumber
    | QRandAction QRandRand? "tölu" "á"? "milli" QRandNumber "og" QRandNumber

QRandAction →
    "veldu" | "veldu" "fyrir" "mig" | "nefndu" | "nefndu" "fyrir" "mig"
    | "gefðu" "mér" | "komdu" "með" | "getur" "þú" "gefið" "mér"
    | "geturðu" "gefið" "mér" | "segðu" "mér"

QRandRand →
    # "Að handahófi" is incorrect but we'll allow it
    "af" "handahófi" | "að" "handahófi"

QRandNumber →
    # to is a declinable number word ('tveir/tvo/tveim/tveggja')
    # töl is an undeclinable number word ('sautján')
    # tala is a number ('17')
    to | töl | tala | "núll"

$score(+35) QRandom

"""


def QRandomQuery(node, params, result):
    result.qtype = _RANDOM_QTYPE


def QRandomHeadsOrTails(node, params, result):
    result.action = "headstails"


def QRandomBetween(node, params, result):
    result.action = "randbtwn"


def QRandomDiceRoll(node, params, result):
    result.action = "dieroll"


def QRandomDiceSides(node, params, result):
    result.dice_sides = 6


def QRandNumber(node, params, result):
    d = result.find_descendant(t_base="tala")
    if d:
        add_num(terminal_num(d), result)
    else:
        add_num(result._nominative, result)


def gen_random_answer(q: Query, result):
    (num1, num2) = (1, 6)  # Default

    if "numbers" in result:
        # Asking for a number between x and y
        if len(result.numbers) == 2:
            (num1, num2) = sorted(result.numbers)
        # Asking for the roll of an x-sided die
        else:
            if result.numbers[0] == 0:
                return gen_answer("Núll hliða teningar eru ekki til.")
            (num1, num2) = (1, result.numbers[0])

    # Query key is random number range (e.g. 1-6)
    q.set_key("{0}-{1}".format(num1, num2))

    answer = str(random.randint(num1, num2))
    response = dict(answer=answer)
    if result.action == "dieroll":
        voice_answer = "Talan {0} kom upp á teningnum".format(answer)
    else:
        voice_answer = "Ég vel töluna {0}".format(answer)

    return response, answer, voice_answer


def heads_or_tails(q: Query, result):
    q.set_key("HeadsOrTails")
    return gen_answer(random.choice(("Skjaldarmerki", "Fiskur")))


def sentence(state, result):
    """ Called when sentence processing is complete """
    q: Query = state["query"]
    if "qtype" not in result:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
        return

    # Successfully matched a query type
    q.set_qtype(result.qtype)

    try:
        func = heads_or_tails if result.action == "headstails" else gen_random_answer
        r = func(q, result)
        if r:
            q.set_answer(*r)
    except Exception as e:
        logging.warning("Exception while processing random query: {0}".format(e))
        q.set_error("E_EXCEPTION: {0}".format(e))
        raise
