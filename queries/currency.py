"""

    Greynir: Natural language processing for Icelandic

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


    This module handles queries related to currencies and exchange rates.

"""

# TODO: Switch from using apis.is
# TODO: Bug: "30 dollarar eru 3.801 krónUR." [!!!] Fix using is_plural
# TODO: Answer for exch rate should be of the form ISK 2000 = USD 14,65
# TODO: "hvað eru 10 evrur í íslenskum krónum"
# TODO: "Hvert er gengi krónunnar?"

from typing import Dict, List, Mapping, Optional, Sequence, cast

import cachetools  # type: ignore
import random
import logging

from queries import Query, QueryStateDict
from queries.util import (
    query_json_api,
    iceformat_float,
    gen_answer,
    is_plural,
    read_grammar_file,
)
from tree import Result, Node, NonterminalNode
from speech.trans import gssml

# Lemmas of keywords that could indicate that the user is trying to use this module
TOPIC_LEMMAS: Sequence[str] = [
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
    """Help text to return when query processor is unable to parse a query but
    one of the above lemmas is found in it"""
    return "Ég get svarað ef þú spyrð til dæmis: {0}?".format(
        random.choice(
            (
                "Hvert er gengi dollarans",
                "Hvert er gengi evru gagnvart dollara",
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

# Indicate that this module wants to handle parse trees for queries,
# as opposed to simple literal text strings
HANDLE_TREE = True

# The grammar nonterminals this module wants to handle
QUERY_NONTERMINALS = {"QCurrency"}

# The context-free grammar for the queries recognized by this plug-in module
GRAMMAR = read_grammar_file("currency")

NON_KVK_CURRENCY_GENDERS: Mapping[str, str] = {
    # KK
    "USD": "kk",
    "CHF": "kk",
    "CAD": "kk",
    # HK
    "GBP": "hk",
    "JPY": "hk",
    "PLN": "hk",
    "CNY": "hk",
    "RMB": "hk",
    "ZAR": "hk",
}


def add_currency(curr: str, result: Result) -> None:
    if "currencies" not in result:
        result.currencies = []
    rn = cast(List[str], result.currencies)
    rn.append(curr)


def QCurrency(node: Node, params: QueryStateDict, result: Result) -> None:
    """Currency query"""
    result.qtype = "Currency"
    result.qkey = result._canonical


def QCurNumberWord(node: Node, params: QueryStateDict, result: Result) -> None:
    if isinstance(result._canonical, (int, float)):
        if "numbers" not in result:
            result["numbers"] = []
        result["numbers"].append(result._canonical)


def QCurUnit(node: Node, params: QueryStateDict, result: Result) -> None:
    """Obtain the ISO currency code from the last three
    letters in the child nonterminal name."""
    child = cast(NonterminalNode, node.child)
    currency = child.nt_base[-3:]
    add_currency(currency, result)


def QCurExchangeRate(node: Node, params: QueryStateDict, result: Result) -> None:
    result.op = "exchange"
    result.desc = result._text


def QCurGeneralRate(node: Node, params: QueryStateDict, result: Result) -> None:
    result.op = "general"
    result.desc = result._text


def QCurGeneralCost(node: Node, params: QueryStateDict, result: Result) -> None:
    result.op = "general"
    result.desc = result._text


def QCurCurrencyIndex(node: Node, params: QueryStateDict, result: Result) -> None:
    result.op = "index"
    result.desc = result._text
    add_currency("GVT", result)


def QCurConvertAmount(node: Node, params: QueryStateDict, result: Result) -> None:
    # Hvað eru [X] margir [Y] - this is the X part
    amount: Optional[Node] = node.first_child(lambda n: n.has_t_base("amount"))
    if amount is not None:
        # Found an amount terminal node
        amt = amount.contained_amount
        if amt:
            result.amount, curr = amt
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


def QCurConvertTo(node: Node, params: QueryStateDict, result: Result) -> None:
    # Hvað eru [X] margir [Y] - this is the Y part
    result.currency = result._nominative


def QCurMuch(node: Node, params: QueryStateDict, result: Result) -> None:
    # 'Hvað eru þrír dollarar mikið [í evrum]?'
    # We assume that this means conversion to ISK if no currency is specified
    if "currency" not in result:
        result.currency = "krónur"
        add_currency("ISK", result)


def QCurAmountConversion(node: Node, params: QueryStateDict, result: Result) -> None:
    result.op = "convert"


_CURR_API_URL = "https://apis.is/currency/arion"
_CURR_CACHE_TTL = 3600  # seconds


@cachetools.cached(cachetools.TTLCache(1, _CURR_CACHE_TTL))
def _fetch_exchange_rates() -> Optional[Dict[str, float]]:
    """Fetch exchange rate data from apis.is and cache it."""
    res = query_json_api(_CURR_API_URL)
    if not isinstance(res, dict) or "results" not in res:
        logging.warning(f"Unable to fetch exchange rate data from {_CURR_API_URL}")
        return None
    return {
        c["shortName"]: c["value"]
        for c in res["results"]
        if "shortName" in c and "value" in c
    }


def fetch_exchange_rates() -> Optional[Dict[str, float]]:
    """Fetch exchange rate data using cache"""
    return _fetch_exchange_rates()


def _query_exchange_rate(curr1: str, curr2: str) -> Optional[float]:
    """Returns exchange rate of two ISO 4217 currencies"""
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


def _clean_voice_answer(s: str) -> str:
    """Clean up potential errors in speech recognised text."""
    s = s.replace("slot í", "slotí")
    s = s.replace(" dollars ", " Bandaríkjadals ")
    return s


def sentence(state: QueryStateDict, result: Result) -> None:
    """Called when sentence processing is complete"""
    q: Query = state["query"]
    if "qtype" in result and "op" in result:
        # Successfully matched a query type
        val = None
        target_currency = "ISK"
        target_gender = None
        suffix = ""
        verb = "er"

        if result.op == "index":
            # target_currency = "GVT"
            val = _query_exchange_rate("GVT", "")
            target_gender = "kk"
        elif result.op == "exchange":
            # 'Hvert er gengi evru gagnvart dollara?'
            target_currency = result.currencies[0]
            val = _query_exchange_rate(result.currencies[0], result.currencies[1])
            target_gender = "kk"
        elif result.op == "general":
            # 'Hvert er gengi dollarans?'
            val = _query_exchange_rate(result.currencies[0], "ISK")
            if val:
                suffix = "krónur" if is_plural(val) else "króna"
        elif result.op == "convert":
            # 'Hvað eru 100 evrur margar krónur?'
            suffix = result.currency  # 'krónur'
            verb = "eru" if is_plural(result.amount) else "er"
            target_currency = result.currencies[1]
            val = _query_exchange_rate(result.currencies[0], result.currencies[1])
            val = val * result.amount if val else None
        else:
            raise Exception(f"Unknown operator: {result.op}")

        if val:
            if target_currency == "ISK":
                # For ISK, round to whole numbers
                val = round(val, 0)
            else:
                val = round(val, 2)
            answer = iceformat_float(val)
            response = dict(answer=answer)
            if target_gender is None:
                target_gender = NON_KVK_CURRENCY_GENDERS.get(target_currency, "kvk")
            from_gender = NON_KVK_CURRENCY_GENDERS.get(result.currencies[0], "kvk")
            voice_answer = "{0} {1} {2}{3}.".format(
                gssml(result.desc, type="floats", gender=from_gender),
                verb,
                gssml(
                    val,
                    type="float",
                    case="nf",
                    gender=target_gender,
                    comma_null=(target_currency != "ISK"),
                ),
                (" " + suffix) if suffix else "",
            ).capitalize()
            voice_answer = _clean_voice_answer(voice_answer)
            q.set_answer(response, answer, voice_answer)
        else:
            # FIXME: This error could occur under circumstances where something
            # other than currency lookup failed. Refactor.
            # Ekki tókst að fletta upp gengi
            q.set_answer(*gen_answer("Ekki tókst að fletta upp gengi gjaldmiðla"))

        q.set_key(target_currency)
        # Store the amount in the query context
        q.set_context({"amount": {"currency": target_currency, "number": val}})
        q.set_qtype(_CURRENCY_QTYPE)

        return

    q.set_error("E_QUERY_NOT_UNDERSTOOD")
