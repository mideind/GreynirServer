"""

    Greynir: Natural language processing for Icelandic

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


    This module handles queries related to the Icelandic Yule Lads
    (jólasveinar). This is very important functionality for Icelandic
    parents.

"""

# TODO: hvað eru íslensku jólasveinarnir margir

import random
from datetime import datetime

from query import Query


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

_DATE_TO_ORDINAL = {v: k for k, v in _ORDINAL_TO_DATE.items()}
# Date in genitive case - turns out only the 22nd is different
_DATE_TO_ORDINAL_GEN = _DATE_TO_ORDINAL.copy()
_DATE_TO_ORDINAL_GEN[22] = "tuttugasta og annars"

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
GRAMMAR = """

# A plug-in query grammar always starts with the following,
# adding one or more query productions to the Query nonterminal

Query →
    QYuleQuery

QYuleQuery →
    # Hvenær kemur Skyrgámur / fyrsti jólasveinninn?
    QYuleDate '?'?
    # Hvaða jólasveinn kemur 19. desember / [þann] nítjánda?
    | QYuleLad '?'?

$score(+35) QYuleQuery

QYuleComes_nf →
    "kemur" | "birtist"

QYuleComes_þf →
    ""  # Never matches

QYuleComes_þgf →
    "er" "von" "á"
    | "má" "búast" "við"
    | "má" "reikna" "með"

QYuleComes_ef →
    ""  # Never matches

QYuleLadFirst/fall →
    'fyrstur:lo'_vb_kk_et/fall? 'jólasveinn:kk'_gr_et/fall

QYuleLadLast/fall →
    'síðari:lo'_vb_kk_et/fall 'jólasveinn:kk'_gr_et/fall

QYuleLadId/fall →
    QYuleLadFirst/fall
    | QYuleLadLast/fall
    | QYuleLadName/fall

QYuleLadName/fall →
    {0}

QYuleSuffix →
    "til" "byggða"
    | "úr" "fjöllunum"
    | "til" "bæja"
    | "til" "borgarinnar"

QYuleDate →
    "hvenær" QYuleComes/fall QYuleLadId/fall QYuleSuffix?

QYuleDateRel →
    dagsafs

$score(-4) QYuleDateRel

QYuleNumberOrdinal →
    raðtala | tala

QYuleValidOrdinal →
    "ellefta"
    | "tólfta"
    | "þrettánda"
    | "fjórtánda"
    | "fimmtánda"
    | "sextánda"
    | "sautjánda"
    | "átjánda"
    | "nítjánda"
    | "tuttugasta"
    | "tuttugasta" "og" "fyrsta"
    | "tuttugasta" "og" "annan"
    | "tuttugasta" "og" "þriðja"
    | "tuttugasta" "og" "fjórða"

$score(+4) QYuleValidOrdinal

QYuleTwentyOrdinal →
    tala
    | tala "og" QYuleTwentyPart

QYuleTwentyPart →
    "fyrsta"
    | "annan"
    | "þriðja"
    | "fjórða"

QYuleInvalidOrdinal →
    "fyrsta"
    | "annan"
    | "þriðja"
    | "fjórða"
    | "fimmta"
    | "sjötta"
    | "sjöunda"
    | "áttunda"
    | "níunda"
    | "tíunda"
    | "tuttugasta" "og" "fimmta"
    | "tuttugasta" "og" "sjötta"
    | "tuttugasta" "og" "sjöunda"
    | "tuttugasta" "og" "áttunda"
    | "tuttugasta" "og" "níunda"
    | "þrítugasta"
    | "þrítugasta" "og" "fyrsta"

QYuleOrdinal →
    QYuleNumberOrdinal | QYuleValidOrdinal | QYuleInvalidOrdinal | QYuleTwentyOrdinal

QYuleWhichLad →
    "hvaða" "jólasveinn"
    | "hver" "af" "jólasveinunum"
    | "hver" "jólasveinanna"

QYuleToday →
    "í" "dag"
    | "í_kvöld"
    | "í" "nótt"

QYuleTomorrow →
    "á_morgun"
    | "annað" "kvöld"
    | "aðra" "nótt"

QYuleDay23 →
    "á" "þorláksmessu"

QYuleDay24 →
    "á" "aðfangadag"

QYuleDay →
    "þann"? QYuleOrdinal "desember"?
    | "þann"? QYuleDateRel
    | QYuleDay23
    | QYuleDay24
    | QYuleToday
    | QYuleTomorrow

QYuleLadByDate →
    QYuleWhichLad QYuleComes_nf QYuleSuffix? QYuleDay

QYuleLadFirst →
    QYuleWhichLad "er" "fyrstur"
    | QYuleWhichLad "kemur" "fyrstur"
    | QYuleWhichLad "kemur" "fyrst"
    | "hver" "er" "fyrsti" "jólasveinninn"
    | "hver" "er" "fyrstur" "jólasveinanna"
    | "hvenær" "á" "maður"? "að" "setja" 'skór:kk'_þf "út"? "í" 'gluggi:kk'_et_þf
    | "hvenær" "setur" "maður" 'skór:kk'_þf "út"? "í" 'gluggi:kk'_et_þf
    | "hvenær" "fer" 'skór:kk'_et_nf "út"? "í" 'gluggi:kk'_et_þf
    | "hvenær" "fara" 'skór:kk'_ft_nf "út"? "í" 'gluggi:kk'_et_þf

QYuleLadLast →
    QYuleWhichLad "er" "síðastur"
    | QYuleWhichLad "kemur" "síðastur"
    | QYuleWhichLad "kemur" "síðast"
    | "hver" "er" "síðasti" "jólasveinninn"
    | "hver" "er" "síðastur" "jólasveinanna"

QYuleLad →
    QYuleLadByDate
    | QYuleLadFirst QYuleSuffix?
    | QYuleLadLast QYuleSuffix?

""".format(
    " | ".join("'{0}'/fall".format(name) for name in _YULE_LADS_BY_NAME.keys())
)


def QYuleDate(node, params, result):
    """ Query for date when a particular yule lad appears """
    result.qtype = "YuleDate"
    result.qkey = result.yule_lad


def QYuleLad(node, params, result):
    """ Query for which yule lad appears on a particular date """
    result.qtype = "YuleLad"
    result.qkey = str(result.lad_date)


def QYuleLadFirst(node, params, result):
    result.yule_lad = "Stekkjarstaur"
    result.lad_date = 12


def QYuleLadLast(node, params, result):
    result.yule_lad = "Kertasníkir"
    result.lad_date = 24


def QYuleLadName(node, params, result):
    result.yule_lad = result._nominative
    result.lad_date = _YULE_LADS_BY_NAME[result.yule_lad]


def QYuleNumberOrdinal(node, params, result):
    ordinal = node.first_child(lambda n: True)
    if ordinal is not None:
        result.lad_date = ordinal.contained_number
    else:
        result.lad_date = 0
    if 11 <= result.lad_date <= 23:
        # If asking about December 11, reply with the
        # yule lad coming on the eve of the 12th, etc.
        result.lad_date += 1
    result.yule_lad = _YULE_LADS_BY_DATE.get(result.lad_date)
    if not (11 <= result.lad_date <= 24):
        result.invalid_date = True


def QYuleValidOrdinal(node, params, result):
    result.lad_date = _ORDINAL_TO_DATE[result._text]
    if 11 <= result.lad_date <= 23:
        # If asking about December 11, reply with the
        # yule lad coming on the eve of the 12th, etc.
        result.lad_date += 1
    result.yule_lad = _YULE_LADS_BY_DATE.get(result.lad_date)


def QYuleInvalidOrdinal(node, params, result):
    result.lad_date = _ORDINAL_TO_DATE[result._text]
    result.yule_lad = None
    result.invalid_date = True


def QYuleDay23(node, params, result):
    result.lad_date = 24  # Yes, correct
    result.yule_lad = _YULE_LADS_BY_DATE.get(result.lad_date)


def QYuleDay24(node, params, result):
    result.lad_date = 24  # Yes, correct
    result.yule_lad = _YULE_LADS_BY_DATE.get(result.lad_date)


def QYuleToday(node, params, result):
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


def QYuleTomorrow(node, params, result):
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


def QYuleTwentyPart(node, params, result):
    result.twenty_part = _TWENTY_PART[result._text]


def QYuleTwentyOrdinal(node, params, result):
    result.yule_lad = None
    result.lad_date = 0
    num_node = node.first_child(lambda n: True)
    if num_node is not None:
        day = num_node.contained_number
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


def QYuleDateRel(node, params, result):
    result.yule_lad = None
    daterel = node.first_child(lambda n: True)
    if daterel is not None:
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


def sentence(state, result):
    """ Called when sentence processing is complete """
    q: Query = state["query"]
    if "qtype" not in result:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
        return

    answer = voice_answer = ""
    if result.qtype == "YuleDate":
        # 'Hvenær kemur [jólasveinn X]'
        yule_lad = result.yule_lad
        answer = voice_answer = "{0} kemur til byggða aðfaranótt {1} desember.".format(
            yule_lad, _DATE_TO_ORDINAL_GEN[result.lad_date]
        )
    elif result.qtype == "YuleLad":
        # 'Hvaða jólasveinn kemur til byggða [á degi x]'
        lad_date = result.lad_date
        if "invalid_date" in result:
            if lad_date < 1 or lad_date > 31:
                answer = voice_answer = "Þetta er ekki gildur mánaðardagur."
            else:
                # TODO: Fix, always replies "desember" even during other months
                answer = (
                    voice_answer
                ) = "Enginn jólasveinn kemur til byggða þann {0} desember.".format(
                    _DATE_TO_ORDINAL[result.lad_date]
                )
        else:
            yule_lad = result.yule_lad
            answer = (
                voice_answer
            ) = "{0} kemur til byggða aðfaranótt {1} desember.".format(
                yule_lad, _DATE_TO_ORDINAL_GEN[result.lad_date]
            )
        q.lowercase_beautified_query()

    response = dict(answer=answer)
    # !!! TODO
    # q.set_context({"date": xxx})
    q.set_key(result.qkey)
    q.set_answer(response, answer, voice_answer)
    q.set_qtype(_YULE_QTYPE)
