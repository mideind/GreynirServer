"""

    Greynir: Natural language processing for Icelandic

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


    This module handles queries related to the Icelandic Yule Lads
    (jólasveinar). This is very important functionality for Icelandic
    parents.

"""

# TODO: hvað eru íslensku jólasveinarnir margir

import random
from datetime import datetime

from query import Query, QueryStateDict
from tree import Result, Node, TerminalNode
from queries import read_grammar_file
from speech.norm.num import numbers_to_ordinal


def help_text(lemma: str) -> str:
    """Help text to return when query.py is unable to parse a query but
    one of the above lemmas is found in it"""
    return "Ég get svarað ef þú spyrð til dæmis: {0}?".format(
        random.choice(
            (
                "Hvenær kemur fyrsti jólasveinninn til byggða",
                "Hvenær kemur Askasleikir",
                "Hvaða jólasveinn kemur fimmtánda desember",
                "Hvenær er von á Hurðaskelli",
            )
        )
    )


_YULE_QTYPE = "YuleLads"


_YULE_LADS_BY_NAME = {
    "Stekkjarstaur": 12,
    "Stekkjastaur": 12,
    "stekkjastaur": 12,
    "Giljagaur": 13,
    "Stúfur": 14,
    "Þvörusleikir": 15,
    "Pottaskefill": 16,
    "Pottasleikir": 16,
    "Askasleikir": 17,
    "Hurðaskellir": 18,
    "Skyrjarmur": 19,
    "Skyrgámur": 19,
    "Bjúgnakrækir": 20,
    "Gluggagægir": 21,
    "Gáttaþefur": 22,
    "Ketkrókur": 23,
    "Kertasníkir": 24,
}

_YULE_LADS_BY_DATE = {
    12: "Stekkjarstaur",
    13: "Giljagaur",
    14: "Stúfur",
    15: "Þvörusleikir",
    16: "Pottasleikir",
    17: "Askasleikir",
    18: "Hurðaskellir",
    19: "Skyrgámur",
    20: "Bjúgnakrækir",
    21: "Gluggagægir",
    22: "Gáttaþefur",
    23: "Ketkrókur",
    24: "Kertasníkir",
}

_ORDINAL_TO_DATE = {
    "fyrsta": 1,
    "annan": 2,
    "þriðja": 3,
    "fjórða": 4,
    "fimmta": 5,
    "sjötta": 6,
    "sjöunda": 7,
    "áttunda": 8,
    "níunda": 9,
    "tíunda": 10,
    "ellefta": 11,
    "tólfta": 12,
    "þrettánda": 13,
    "fjórtánda": 14,
    "fimmtánda": 15,
    "sextánda": 16,
    "sautjánda": 17,
    "átjánda": 18,
    "nítjánda": 19,
    "tuttugasta": 20,
    "tuttugasta og fyrsta": 21,
    "tuttugasta og annan": 22,
    "tuttugasta og þriðja": 23,
    "tuttugasta og fjórða": 24,
    "tuttugasta og fimmta": 25,
    "tuttugasta og sjötta": 26,
    "tuttugasta og sjöunda": 27,
    "tuttugasta og áttunda": 28,
    "tuttugasta og níunda": 29,
    "þrítugasta": 30,
    "þrítugasta og fyrsta": 31,
}


_TWENTY_PART = {"fyrsta": 1, "annan": 2, "þriðja": 3, "fjórða": 4}

# Lemmas of keywords that could indicate that the user is trying to use this module
TOPIC_LEMMAS = (
    ["jólasveinn"]
    + list(_YULE_LADS_BY_NAME.keys())
    + [lad.lower() for lad in _YULE_LADS_BY_NAME.keys()]
)

# Indicate that this module wants to handle parse trees for queries,
# as opposed to simple literal text strings
HANDLE_TREE = True

# The grammar nonterminals this module wants to handle
QUERY_NONTERMINALS = {"QYuleQuery"}

# The context-free grammar for the queries recognized by this plug-in module
GRAMMAR = read_grammar_file(
    "yulelads",
    yulelad_names=" | ".join(
        "'{0}'/fall".format(name) for name in _YULE_LADS_BY_NAME.keys()
    ),
)


def QYuleDate(node: Node, params: QueryStateDict, result: Result) -> None:
    """Query for date when a particular yule lad appears"""
    result.qtype = "YuleDate"
    result.qkey = result.yule_lad


def QYuleLad(node: Node, params: QueryStateDict, result: Result) -> None:
    """Query for which yule lad appears on a particular date"""
    result.qtype = "YuleLad"
    result.qkey = str(result.lad_date)


def QYuleLadFirst(node: Node, params: QueryStateDict, result: Result) -> None:
    result.yule_lad = "Stekkjarstaur"
    result.lad_date = 12


def QYuleLadLast(node: Node, params: QueryStateDict, result: Result) -> None:
    result.yule_lad = "Kertasníkir"
    result.lad_date = 24


def QYuleLadName(node: Node, params: QueryStateDict, result: Result) -> None:
    result.yule_lad = result._nominative
    result.lad_date = _YULE_LADS_BY_NAME[result.yule_lad]


def QYuleNumberOrdinal(node: Node, params: QueryStateDict, result: Result) -> None:
    ordinal = node.first_child(lambda n: True)
    if ordinal is not None:
        result.lad_date = int(ordinal.contained_number or 0)
    else:
        result.lad_date = 0
    if 11 <= result.lad_date <= 23:
        # If asking about December 11, reply with the
        # yule lad coming on the eve of the 12th, etc.
        result.lad_date += 1
    result.yule_lad = _YULE_LADS_BY_DATE.get(result.lad_date)
    if not (11 <= result.lad_date <= 24):
        result.invalid_date = True


def QYuleValidOrdinal(node: Node, params: QueryStateDict, result: Result) -> None:
    result.lad_date = _ORDINAL_TO_DATE[result._text]
    if 11 <= result.lad_date <= 23:
        # If asking about December 11, reply with the
        # yule lad coming on the eve of the 12th, etc.
        result.lad_date += 1
    result.yule_lad = _YULE_LADS_BY_DATE.get(result.lad_date)


def QYuleInvalidOrdinal(node: Node, params: QueryStateDict, result: Result) -> None:
    result.lad_date = _ORDINAL_TO_DATE[result._text]
    result.yule_lad = None
    result.invalid_date = True


def QYuleDay23(node: Node, params: QueryStateDict, result: Result) -> None:
    result.lad_date = 24  # Yes, correct
    result.yule_lad = _YULE_LADS_BY_DATE.get(result.lad_date)


def QYuleDay24(node: Node, params: QueryStateDict, result: Result) -> None:
    result.lad_date = 24  # Yes, correct
    result.yule_lad = _YULE_LADS_BY_DATE.get(result.lad_date)


def QYuleToday(node: Node, params: QueryStateDict, result: Result) -> None:
    result.yule_lad = None
    result.lad_date = datetime.utcnow().day
    if not (11 <= result.lad_date <= 24):
        result.invalid_date = True
    else:
        if result.lad_date < 24:
            # If asking about December 11, reply with the
            # yule lad coming on the eve of the 12th, etc.
            result.lad_date += 1
        result.yule_lad = _YULE_LADS_BY_DATE.get(result.lad_date)


def QYuleTomorrow(node: Node, params: QueryStateDict, result: Result) -> None:
    result.yule_lad = None
    result.lad_date = datetime.utcnow().day + 1
    if not (11 <= result.lad_date <= 24):
        result.invalid_date = True
    else:
        if result.lad_date < 24:
            # If asking about December 11, reply with the
            # yule lad coming on the eve of the 12th, etc.
            result.lad_date += 1
        result.yule_lad = _YULE_LADS_BY_DATE.get(result.lad_date)


def QYuleTwentyPart(node: Node, params: QueryStateDict, result: Result) -> None:
    result.twenty_part = _TWENTY_PART[result._text]


def QYuleTwentyOrdinal(node: Node, params: QueryStateDict, result: Result) -> None:
    result.yule_lad = None
    result.lad_date = 0
    num_node = node.first_child(lambda n: True)
    if num_node is not None:
        day = int(num_node.contained_number or 0)
        if day != 20:
            # Only accept something like '20 og annar', not '10 og annar'
            day = 0
        elif "twenty_part" in result:
            day += result.twenty_part
        result.lad_date = day
        if not (11 <= result.lad_date <= 24):
            result.invalid_date = True
        else:
            if result.lad_date < 24:
                # If asking about December 11, reply with the
                # yule lad coming on the eve of the 12th, etc.
                result.lad_date += 1
            result.yule_lad = _YULE_LADS_BY_DATE.get(result.lad_date)


def QYuleDateRel(node: Node, params: QueryStateDict, result: Result) -> None:
    result.yule_lad = None
    daterel = node.first_child(lambda n: True)
    if daterel is not None:
        assert isinstance(daterel, TerminalNode)
        assert daterel.contained_date is not None
        year, month, result.lad_date = daterel.contained_date
        if year != 0 or month != 12:
            result.invalid_date = True
        elif not (11 <= result.lad_date <= 24):
            result.invalid_date = True
        else:
            if result.lad_date < 24:
                # If asking about December 11, reply with the
                # yule lad coming on the eve of the 12th, etc.
                result.lad_date += 1
            result.yule_lad = _YULE_LADS_BY_DATE.get(result.lad_date)
    else:
        result.lad_date = 0
        result.invalid_date = True


def sentence(state: QueryStateDict, result: Result) -> None:
    """Called when sentence processing is complete"""
    q: Query = state["query"]
    if "qtype" not in result:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
        return

    answer = voice_answer = ""
    if result.qtype == "YuleDate":
        # 'Hvenær kemur [jólasveinn X]'
        yule_lad = result.yule_lad
        answer = f"{yule_lad} kemur til byggða aðfaranótt {result.lad_date}. desember."
    elif result.qtype == "YuleLad":
        # 'Hvaða jólasveinn kemur til byggða [á degi x]'
        lad_date = result.lad_date
        if "invalid_date" in result:
            if lad_date < 1 or lad_date > 31:
                answer = voice_answer = "Þetta er ekki gildur mánaðardagur."
            else:
                # TODO: Fix, always replies "desember" even during other months
                answer = f"Enginn jólasveinn kemur til byggða þann {result.lad_date}. desember."
        else:
            yule_lad = result.yule_lad
            answer = (
                f"{yule_lad} kemur til byggða aðfaranótt {result.lad_date}. desember."
            )
        q.lowercase_beautified_query()

    voice_answer = numbers_to_ordinal(answer, case="ef", gender="kk")
    response = dict(answer=answer)
    # !!! TODO
    # q.set_context({"date": xxx})
    q.set_key(result.qkey)
    q.set_answer(response, answer, voice_answer)
    q.set_qtype(_YULE_QTYPE)
