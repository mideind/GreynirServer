"""

    Greynir: Natural language processing for Icelandic

    Randomness query response module

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
from icespeak import gssml
from tree import Result, Node


_RANDOM_QTYPE = "Random"

TOPIC_LEMMAS = ["teningur", "skjaldarmerki", "handahóf"]


def help_text(lemma: str) -> str:
    """Help text to return when query processor is unable to parse a query but
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
GRAMMAR = read_grammar_file("rand")


def QRandomQuery(node: Node, params: QueryStateDict, result: Result) -> None:
    result.qtype = _RANDOM_QTYPE


def QRandomHeadsOrTails(node: Node, params: QueryStateDict, result: Result) -> None:
    result.action = "headstails"


def QRandomBetween(node: Node, params: QueryStateDict, result: Result) -> None:
    result.action = "randbtwn"


def QRandomDieRoll(node: Node, params: QueryStateDict, result: Result) -> None:
    result.action = "dieroll"


def QRandomDiceSides(node: Node, params: QueryStateDict, result: Result) -> None:
    result.dice_sides = 6


def QRandNumber(node: Node, params: QueryStateDict, result: Result) -> None:
    d = result.find_descendant(t_base="tala")
    if d:
        add_num(terminal_num(d), result)
    else:
        add_num(result._nominative, result)


def gen_multiple_die_rolls_answer(q: Query, result: Result):
    # TODO: Implement me
    pass


def gen_random_answer(q: Query, result: Result):
    """Generate answer to a query asking for a random number between two numbers."""
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

    answer = random.randint(num1, num2)
    response = dict(answer=answer)
    if result.action == "dieroll":
        voice_answer = (
            f"Talan {gssml(answer, type='number', gender='kk')} kom upp á teningnum"
        )
    else:
        voice_answer = f"Ég vel töluna {gssml(answer, type='number', gender='kk')}"

    return response, str(answer), voice_answer


def heads_or_tails(q: Query, result: Result) -> AnswerTuple:
    """Generate answer to "heads or tails" queries, i.e. "fiskur eða skjaldarmerki."""
    q.set_key("HeadsOrTails")
    return gen_answer(random.choice(("Skjaldarmerki", "Fiskur")))


def sentence(state: QueryStateDict, result: Result) -> None:
    """Called when sentence processing is complete"""
    q: Query = state["query"]
    if "qtype" not in result or "action" not in result:
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
        logging.warning(f"Exception while processing random query: {e}")
        q.set_error(f"E_EXCEPTION: {e}")
        raise
