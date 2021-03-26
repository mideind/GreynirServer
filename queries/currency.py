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


    This module handles queries related to currencies and exchange rates.

"""

# TODO: Bug: "30 dollarar eru 3.801 krónUR." [!!!] Fix using is_plural
# TODO: Answer for exch rate should be of the form ISK 2000 = USD 14,65
# TODO: "hvað eru 10 evrur í íslenskum krónum"
# TODO: "Hvert er gengi krónunnar?"

from typing import Dict, Optional

import re
import cachetools  # type: ignore
import random
import logging

from query import Query
from queries import query_json_api, iceformat_float, is_plural
from settings import Settings


# Lemmas of keywords that could indicate that the user is trying to use this module
TOPIC_LEMMAS = [
    "gengi",
    "gengisvísitala",
    "gjaldmiðill",
    "króna",
    "pund",
    "sterlingspund",
    "dollari",
    "evra",
    "rand",
    "jen",
    "júan",
    "franki",
    "dalur",
    "bandaríkjadalur",
    "kanadadalur",
    "rúbla",
]


def help_text(lemma: str) -> str:
    """Help text to return when query.py is unable to parse a query but
    one of the above lemmas is found in it"""
    return "Ég get svarað ef þú spyrð til dæmis: {0}?".format(
        random.choice(
            (
                "Hvert er gengi dollarans",
                "Hvert er gengu evru gagnvart dollara",
                "Hvað eru tíu þúsund krónur margar evrur",
                "Hvað er einn dollari margar krónur",
                "Hvað eru sextán hundruð krónur mikið í evrum",
                "Hvað eru hundrað danskar krónur í evrum",
                "Hvert er gengi pundsins gagnvart krónunni",
                "Hvað eru sex rúblur mikið",
            )
        )
    )


_CURRENCY_QTYPE = "Currency"


_NUMBER_WORDS = {
    "núll": 0,
    "einn": 1,
    "ein": 1,
    "eitt": 1,
    "tveir": 2,
    "tvær": 2,
    "tvö": 2,
    "þrír": 3,
    "þrjár": 3,
    "þrjú": 3,
    "fjórir": 4,
    "fjórar": 4,
    "fjögur": 4,
    "fimm": 5,
    "sex": 6,
    "sjö": 7,
    "átta": 8,
    "níu": 9,
    "tíu": 10,
    "ellefu": 11,
    "tólf": 12,
    "þrettán": 13,
    "fjórtán": 14,
    "fimmtán": 15,
    "sextán": 16,
    "sautján": 17,
    "átján": 18,
    "nítján": 19,
    "tuttugu": 20,
    "þrjátíu": 30,
    "fjörutíu": 40,
    "fimmtíu": 50,
    "sextíu": 60,
    "sjötíu": 70,
    "áttatíu": 80,
    "níutíu": 90,
    "hundrað": 100,
    "þúsund": 1000,
    "milljón": 1e6,
    "milljarður": 1e9,
}

# Indicate that this module wants to handle parse trees for queries,
# as opposed to simple literal text strings
HANDLE_TREE = True

# The grammar nonterminals this module wants to handle
QUERY_NONTERMINALS = {"QCurrency"}

# The context-free grammar for the queries recognized by this plug-in module
GRAMMAR = """

# A plug-in query grammar always starts with the following,
# adding one or more query productions to the Query nonterminal

Query →
    QCurrency

QCurrency →
    QCurrencyQuery '?'?

$score(+35) QCurrency

QCurrencyQuery →
    # "Hver er gengisvísitalan?"
    QCurSpecificPrefix? QCurCurrencyIndex_nf QCurNow?
    # "Hvert/hvað/hvernig er gengi X?"
    | QCurAnyPrefix? QCurGeneralRate QCurNow?
    # "Hvað kostar X?"
    | QCurCostPrefix QCurGeneralCost "mikið"? QCurInKronas? QCurNow?

    # "Hvert/hvað/hvernig er gengi X gagnvart Y?"
    | QCurAnyPrefix? QCurExchangeRate QCurNow?

    # "Hvað eru NUM X margir/margar/mörg Y?"
    | QCurGenericPrefix? QCurAmountConversion

    # "Hvað fæ ég marga/margar/mörg X fyrir NUM Y?"
    # |

QCurGenericPrefix → "hvað" "er" | "hvað" "eru" | "hvernig" "er"
QCurSpecificPrefix → "hvert" "er" | "hvernig" "er" | "hver" "er"
QCurAnyPrefix → QCurGenericPrefix | QCurSpecificPrefix
QCurCostPrefix → "hvað" "kostar" | "hversu" "mikið" "kostar" | "hve" "mikið" "kostar"
QCurInKronas → "í" "krónum"

QCurNow → "núna" | "nú" | "í" "augnablikinu" | "eins" "og" "stendur" | "í" "dag"

# Supported currencies
# Note: All child productions of QCurUnit must have valid
# ISO currency codes as the last three letters in their name
QCurUnit/fall →
    QCurISK/fall | QCurUSD/fall | QCurEUR/fall | QCurGBP/fall
    | QCurJPY/fall | QCurRUB/fall | QCurCHF/fall | QCurCAD/fall
    | QCurZAR/fall | QCurPLN/fall | QCurRUB/fall | QCurCNY/fall
    | QCurNOK/fall | QCurDKK/fall | QCurSEK/fall

QCurISK/fall →
    'íslenskur:lo'_kvk/fall? 'króna:kvk'/fall
    | currency_isk/fall

QCurNOK/fall →
    'norskur:lo'_kvk/fall 'króna:kvk'/fall
    | currency_nok/fall

QCurDKK/fall →
    'danskur:lo'_kvk/fall 'króna:kvk'/fall
    | currency_dkk/fall

QCurSEK/fall →
    'sænskur:lo'_kvk/fall 'króna:kvk'/fall
    | currency_sek/fall

QCurUSD/fall →
    'bandaríkjadalur:kk'/fall
    | 'dalur:kk'/fall
    | 'bandarískur:lo'_kk/fall? 'dollari:kk'/fall
    | currency_usd/fall
    | "dollar" # Common mistake
    | "bandaríkjadollar" # Common mistake

QCurUSD_þgf →
    "bandaríkjadollara" | "bandaríkjadollaranum" | "bandaríkjadollarnum"

QCurUSD_ef →
    "bandaríkjadollara"
    | "bandaríkjadollarans"
    | "bandaríkjadollars"
    | "bandarísks"? "dollars"

QCurEUR/fall →
    'evra:kvk'/fall
    | currency_eur/fall

QCurGBP/fall →
    'breskur:lo'_hk/fall? 'pund:hk'/fall
    | 'breskur:lo'_sb_hk/fall? 'pund:hk'_gr/fall
    | 'sterlingspund:hk'/fall
    | currency_gbp/fall

QCurJPY/fall →
    'japanskur:lo'_hk/fall? 'jen:hk'/fall
    | currency_jpy/fall

QCurCHF/fall →
    'svissneskur:lo'_kk/fall? 'franki:kk'/fall
    | currency_chf/fall

QCurCAD/fall →
    | 'kanadískur:lo'_kk/fall 'dollari:kk'/fall
    | 'kanadadalur:kk'_kk/fall
    | 'kanadadollari:kk'_kk/fall
    | "kanadadollar" # Common mistake
    | currency_cad/fall

QCurCAD_nf →
    "kanadadalur" | "kanadadalurinn"
    | "kanadadollari" | "kanadadollarinn"

QCurCAD_þgf →
    "kanadadal" | "kanadadalnum"
    | "kanadadollara" | "kanadadollaranum"

QCurCAD_ef →
    "kanadadals" | "kanadadalsins"
    | "kanadadollars" | "kanadísks" "dollars"
    | "kanadadollara" | "kanadadollarans"

QCurZAR/fall →
    'suðurafrískur:lo'_hk/fall? 'rand:hk'/fall
    | currency_zar/fall

QCurPLN/fall →
    'pólskur:lo'_hk/fall? 'slot:hk'/fall
    | "zloty"
    | "slotí"
    | "slot" "í"  # Algeng villa í raddgreiningu
    | currency_pln/fall

QCurPLN_ef →
    'pólskur:lo'_sb_hk_ef? "slotís"
    | 'pólskur:lo'_vb_hk_ef? "slotísins"

QCurRUB/fall →
    'rússneskur:lo'_kvk/fall? 'rúbla:kvk'/fall
    | currency_rub/fall

QCurCNY/fall →
    'kínverskur:lo'_hk/fall? 'júan:hk'/fall
    | "yuan"
    | "júan"
    | currency_cny/fall

QCurNumberWord →
    # to is a declinable number word ('tveir/tvo/tveim/tveggja')
    # töl is an undeclinable number word ('sautján')
    # tala is a number ('17')
    to | töl | tala

QCurCurrencyIndex/fall →
    'gengisvísitala:kvk'_et/fall QCurISK_ef?

QCurVisAVis → "gagnvart" | "á" "móti" | "gegn"

QCurXch → "gengi" | "gengið"

QCurExchangeRate →
    QCurXch QCurUnit_ef QCurVisAVis QCurUnit_þgf
    | "gengið" "á" QCurUnit_þgf QCurVisAVis QCurUnit_þgf

QCurGeneralRate →
    QCurXch QCurUnit_ef
    | "gengið" "á" QCurUnit_þgf

QCurGeneralCost →
    QCurUnit_nf

QCurConvertAmount →
    QCurNumberWord QCurUnit_nf
    | amount

QCurMany →
    "margir" | "margar" | "mörg"

QCurConvertTo/fall →
    QCurUnit/fall

$tag(keep) QCurConvertTo/fall # Keep this from being optimized away

QCurMuch →
    "mikið" QCurMuchIn?

QCurMuchIn →
    "í" QCurConvertTo_þgf

QCurAmountConversion →
    # Hvað eru 10 dollarar margar krónur?
    QCurConvertAmount QCurMany QCurConvertTo_nf
    # Hvað eru 10 dollarar í íslenskum krónum?
    | QCurConvertAmount QCurMuchIn
    # Hvað eru 10 dollarar mikið [í evrum]?
    | QCurConvertAmount QCurMuch
    # Hvað fæ ég margar krónur fyrir 10 dollara?
    # | "hvað" "fæ" "ég" QCurMany "krónur" "fyrir"

"""


def parse_num(num_str: str):
    """ Parse Icelandic number string to float or int """
    num = None
    try:
        # Handle numbers w. Icelandic decimal places ("17,2")
        if re.search(r"^\d+,\d+", num_str):
            num = float(num_str.replace(",", "."))
        # Handle digits ("17")
        else:
            num = float(num_str)
    except ValueError:
        # Handle number words ("sautján")
        num = _NUMBER_WORDS.get(num_str)
    except Exception as e:
        if Settings.DEBUG:
            print("Unexpected exception: {0}".format(e))
        raise
    return num


def add_num(num, result):
    """ Add a number to accumulated number args """
    if "numbers" not in result:
        result.numbers = []
    if isinstance(num, str):
        result.numbers.append(parse_num(num))
    else:
        result.numbers.append(num)


def add_currency(curr: str, result):
    if "currencies" not in result:
        result.currencies = []
    result.currencies.append(curr)


def QCurrency(node, params, result):
    """ Currency query """
    result.qtype = "Currency"
    result.qkey = result._canonical


def QCurNumberWord(node, params, result):
    add_num(result._canonical, result)


def QCurUnit(node, params, result):
    """Obtain the ISO currency code from the last three
    letters in the child nonterminal name."""
    currency = node.child.nt_base[-3:]
    add_currency(currency, result)


def QCurExchangeRate(node, params, result):
    result.op = "exchange"
    result.desc = result._text


def QCurGeneralRate(node, params, result):
    result.op = "general"
    result.desc = result._text


def QCurGeneralCost(node, params, result):
    result.op = "general"
    result.desc = result._text


def QCurCurrencyIndex(node, params, result):
    result.op = "index"
    result.desc = result._text
    add_currency("GVT", result)


def QCurConvertAmount(node, params, result):
    # Hvað eru [X] margir [Y] - this is the X part
    amount = node.first_child(lambda n: n.has_t_base("amount"))
    if amount is not None:
        # Found an amount terminal node
        result.amount, curr = amount.contained_amount
        add_currency(curr, result)
    elif "numbers" in result:
        # Number words
        result.amount = result.numbers[0]
    else:
        # Error!
        result.amount = 0
        # In this case, we assume that a QCurUnit node was present
        # and the currency code has thus already been picked up
    result.desc = result._text


def QCurConvertTo(node, params, result):
    # Hvað eru [X] margir [Y] - this is the Y part
    result.currency = result._nominative


def QCurMuch(node, params, result):
    # 'Hvað eru þrír dollarar mikið [í evrum]?'
    # We assume that this means conversion to ISK if no currency is specified
    if "currency" not in result:
        result.currency = "krónur"
        add_currency("ISK", result)


def QCurAmountConversion(node, params, result):
    result.op = "convert"


_CURR_API_URL = "https://apis.is/currency/lb"
_CURR_CACHE_TTL = 3600  # seconds


@cachetools.cached(cachetools.TTLCache(1, _CURR_CACHE_TTL))
def _fetch_exchange_rates() -> Optional[Dict]:
    """ Fetch exchange rate data from apis.is and cache it. """
    res = query_json_api(_CURR_API_URL)
    if not res or "results" not in res:
        logging.warning(
            "Unable to fetch exchange rate data from {0}".format(_CURR_API_URL)
        )
        return None
    return {c["shortName"]: c["value"] for c in res["results"]}


def _query_exchange_rate(curr1: str, curr2: str) -> Optional[float]:
    """ Returns exchange rate of two ISO 4217 currencies """
    # print("Gengi {0} gagnvart {1}".format(curr1, curr2))

    # A currency is always worth 1 of itself
    if curr1 == curr2:
        return 1

    # Get exchange rate data
    xr = _fetch_exchange_rates()
    if xr is None:
        return None

    xr["ISK"] = 1.0

    # ISK currency index (basket), 'gengisvísitala'
    if curr1 == "GVT" and "GVT" in xr:
        return xr["GVT"]
    # Foreign currency vs. foreign currency
    elif curr1 in xr and curr2 in xr and xr[curr2] != 0:
        return xr[curr1] / xr[curr2]

    return None


def sentence(state, result):
    """ Called when sentence processing is complete """
    q: Query = state["query"]
    if "qtype" in result and "op" in result:
        # Successfully matched a query type
        val = None
        target_currency = "ISK"
        suffix = ""
        verb = "er"

        if result.op == "index":
            # target_currency = "GVT"
            val = _query_exchange_rate("GVT", "")
        elif result.op == "exchange":
            # 'Hvert er gengi evru gagnvart dollara?'
            target_currency = result.currencies[0]
            val = _query_exchange_rate(result.currencies[0], result.currencies[1])
        elif result.op == "general":
            # 'Hvert er gengi dollarans?'
            val = _query_exchange_rate(result.currencies[0], "ISK")
            if val is None:
                val = 1.0
            suffix = "krónur" if is_plural(iceformat_float(val)) else "króna"
        elif result.op == "convert":
            # 'Hvað eru 100 evrur margar krónur?'
            suffix = result.currency  # 'krónur'
            verb = "eru"
            target_currency = result.currencies[1]
            val = _query_exchange_rate(result.currencies[0], result.currencies[1])
            val = val * result.amount if val else None
            if target_currency == "ISK" and val is not None:
                # For ISK, round to whole numbers
                val = round(val, 0)
        else:
            raise Exception("Unknown operator: {0}".format(result.op))

        if val:
            answer = iceformat_float(val)
            response = dict(answer=answer)
            voice_answer = "{0} {3} {1}{2}.".format(
                result.desc, answer, (" " + suffix) if suffix else "", verb
            ).capitalize()
            # Clean up voice answer
            voice_answer = voice_answer.replace("slot í", "slotí")
            voice_answer = voice_answer.replace(" dollars ", " Bandaríkjadals ")
            q.set_answer(response, answer, voice_answer)
            q.set_key(target_currency)
            # Store the amount in the query context
            q.set_context({"amount": {"currency": target_currency, "number": val}})
            q.set_qtype(_CURRENCY_QTYPE)

        return

    q.set_error("E_QUERY_NOT_UNDERSTOOD")
