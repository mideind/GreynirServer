"""

    Greynir: Natural language processing for Icelandic

    Atm query response module

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


    This module handles ATM-related queries.

"""

from typing import Any, Dict, List, Mapping, Optional, cast

import os
import logging
import random
import json

from geo import distance
from tree import Result, Node
from queries import ContextDict, Query, QueryStateDict
from reynir import NounPhrase
from queries.util import (
    gen_answer,
    distance_desc,
    krona_desc,
    natlang_seq,
    read_grammar_file,
    AnswerTuple,
    LatLonTuple,
)
from speech.trans.num import number_to_text

_ATM_QTYPE = "Atm"

_PATH_TO_ISB_JSON = "../resources/geo/isb_locations.json"

_FOREIGN_CURRENCY: Mapping[str, str] = {
    "USD": "bandaríkjadalir",
    "GBP": "sterlingspund",
    "EUR": "evrur",
    "DKK": "danskar krónur",
    "SEK": "sænskar krónur",
    "PLN": "pólsk slot",
    "ISK": "íslenskar krónur",
}


def help_text(lemma: str) -> str:
    """Help text to return when query processor is unable to parse a query but
    one of the above lemmas is found in it"""
    return "Ég get svarað ef þú spyrð til dæmis: {0}?".format(
        random.choice(("Hvar er næsti hraðbanki",))
    )


# This module wants to handle parse trees for queries
HANDLE_TREE = True

# The grammar nonterminals this module wants to handle
QUERY_NONTERMINALS = {"QAtm"}

# The context-free grammar for the queries recognized by this plug-in module
GRAMMAR = read_grammar_file("atm")


def QAtmQuery(node: Node, params: QueryStateDict, result: Result) -> None:
    result.qtype = _ATM_QTYPE


def QAtmClosest(node: Node, params: QueryStateDict, result: Result) -> None:
    result.qkey = "ClosestAtm"


def QAtmClosestDeposit(node: Node, params: QueryStateDict, result: Result) -> None:
    result.qkey = "ClosestAtmDeposit"


def QAtmClosestForeignExchange(
    node: Node, params: QueryStateDict, result: Result
) -> None:
    result.qkey = "ClosestAtmForeignExchange"


def QAtmClosestCoinmachine(node: Node, params: QueryStateDict, result: Result) -> None:
    result.qkey = "ClosestAtmCoinmachine"


def QAtmFurtherInfo(node: Node, params: QueryStateDict, result: Result) -> None:
    """Reference to previous ATM query"""
    q = result.state.get("query")
    ctx = None if q is None else q.fetch_context()
    if ctx is None or "result" not in ctx:
        # There is a reference to a previous result
        # which is not available: flag an error
        result.error_context_reference = True
    else:
        result.context_reference = True
        result.last_atm = ctx["result"]


def QAtmFurtherInfoDeposit(node: Node, params: QueryStateDict, result: Result) -> None:
    result.qkey = "AtmFurtherInfoDeposit"


def QAtmFurtherInfoWithdrawalLimit(
    node: Node, params: QueryStateDict, result: Result
) -> None:
    result.qkey = "AtmFurtherInfoWithdrawalLimit"


def QAtmFurtherInfoOpeningHours(
    node: Node, params: QueryStateDict, result: Result
) -> None:
    result.qkey = "AtmFurtherInfoOpeningHours"


def QAtmFurtherInfoForeignExchange(
    node: Node, params: QueryStateDict, result: Result
) -> None:
    result.qkey = "AtmFurtherInfoForeignExchange"


def QAtmFurtherInfoCoinmachine(
    node: Node, params: QueryStateDict, result: Result
) -> None:
    result.qkey = "AtmFurtherInfoCoinmachine"


def _read_isb_location_data_from_file() -> List[Dict[str, Any]]:
    """Read isb locations JSON data from file"""
    try:
        script_dir = os.path.dirname(__file__)
        rel_path = _PATH_TO_ISB_JSON
        abs_file_path = os.path.join(script_dir, rel_path)
        with open(abs_file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.error("Error reading isb locations json data: %s", e)
        return []


def _get_atm_data() -> Optional[List[Dict[str, Any]]]:
    """Get ATM data"""
    atm_data: List[Dict[str, Any]] = _read_isb_location_data_from_file()
    return atm_data


def _atms_with_distance(loc: Optional[LatLonTuple]) -> Optional[List[Dict[str, Any]]]:
    """Return list of atms w. added distance data."""
    atm_data: Optional[List[Dict[str, Any]]] = _get_atm_data()
    if not atm_data:
        return None

    filtered_atm_data: List[Dict[str, Any]] = []
    for s in atm_data:
        """Filter out all non ATMs from the dictionary"""
        item_type: str = s.get("type", "")
        if item_type == "atm":
            filtered_atm_data.append(s)
    atm_data = filtered_atm_data
    if loc:
        # Calculate distance of all stations
        for s in atm_data:
            s["distance"] = distance(
                loc, (s["location"]["latitude"], s["location"]["longitude"])
            )
    return atm_data


def _group_closest_based_on_address(
    atm_data: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Group closest ATMs based on address,
    returns all atms with the same address or
    an empty list if no atms are found.
    """
    if len(atm_data) == 0:
        return []
    atms: List[Dict[str, Any]] = []
    atms.append(atm_data[0])
    for idx, atm in enumerate(atm_data[:-1]):
        if atm["address"]["street"] == atm_data[idx + 1]["address"]["street"]:
            atms.append(atm_data[idx + 1])
        else:
            break
    return atms


def _closest_atm(loc: LatLonTuple) -> List[Dict[str, Any]]:
    """Find ATM closest to the given location."""
    atms: Optional[List[Dict[str, Any]]] = _atms_with_distance(loc)
    if not atms:
        return []

    # Sort by distance
    dist_sorted = sorted(atms, key=lambda s: s["distance"])
    return _group_closest_based_on_address(dist_sorted)


def _closest_atm_deposit(loc: LatLonTuple) -> List[Dict[str, Any]]:
    """Find ATM closest to the given location that accepts deposits."""
    atms: Optional[List[Dict[str, Any]]] = _atms_with_distance(loc)
    if not atms:
        return []

    filtered_atms: List[Dict[str, Any]] = []
    for atm in atms:
        services = atm.get("services", {})
        if services.get("deposit", False) is True:
            filtered_atms.append(atm)
    atms = filtered_atms

    # Sort by distance
    dist_sorted = sorted(atms, key=lambda s: s["distance"])
    return _group_closest_based_on_address(dist_sorted)


def _closest_atm_foreign_exchange(loc: LatLonTuple) -> List[Dict[str, Any]]:
    """Find ATM closest to the given location that accepts foreign exchange."""
    atms: Optional[List[Dict[str, Any]]] = _atms_with_distance(loc)
    if not atms:
        return []

    filtered_atms: List[Dict[str, Any]] = []
    for atm in atms:
        services = atm.get("services", {})
        if services.get("foreign_exchange", {}).get("active", False) is True:
            filtered_atms.append(atm)
    atms = filtered_atms

    # Sort by distance
    dist_sorted = sorted(atms, key=lambda s: s["distance"])
    return _group_closest_based_on_address(dist_sorted)


def _closest_atm_coinmachine(loc: LatLonTuple) -> List[Dict[str, Any]]:
    """Find ATM closest to the given location that has a coinmachine."""
    atms: Optional[List[Dict[str, Any]]] = _atms_with_distance(loc)
    if not atms:
        return []

    filtered_atms: List[Dict[str, Any]] = []
    for atm in atms:
        services = atm.get("services", {})
        if services.get("coinmachine", False) is True:
            filtered_atms.append(atm)
    atms = filtered_atms

    # Sort by distance
    dist_sorted = sorted(atms, key=lambda s: s["distance"])
    return _group_closest_based_on_address(dist_sorted)


def _format_voice_street_number(s: str) -> str:
    """
    Format street name for voice output,
    also if it contains a range of numbers
    for example: Fiskislóð 7-9 becomes Fiskislóð sjö til níu
    """
    # Formatting numbers
    word_list = s.split()
    last_word = word_list[-1]
    if last_word[-1].isnumeric():
        if "–" in last_word:
            # replace irregular hyphen with regular hyphen
            last_word.replace("–", "-")
        if "-" in last_word:
            split_nr = last_word.split("-")
            first_number = number_to_text(split_nr[0], case="þf")
            last_number = number_to_text(split_nr[-1], case="þf")
            number = first_number + " til " + last_number
            return " ".join(word_list[:-1]) + " " + number
        return " ".join(word_list[:-1]) + " " + number_to_text(last_word, case="þf")
    return s


def _get_foreign_exchange_string(atm_list: List[Dict[str, Any]]) -> str:
    """Return a string with foreign exchange info for the given ATM"""
    atm: Dict[str, Any] = {}
    # if len(atm_list) == 1:
    atm = atm_list[0]
    # else:
    #    for a in atm_list:
    #        if a["services"]["foreign_exchange"]["active"]:
    #            atm = a
    #            break
    currency_abr = atm["services"]["foreign_exchange"]["currency"]
    # Convert currency tags to strings through _FOREIGN_CURRENCY map
    currencies: List[str] = list()
    for i in range(len(currency_abr)):
        print("abr: ", currency_abr[i])
        currency = NounPhrase(_FOREIGN_CURRENCY[currency_abr[i].strip()]).accusative
        print("currency: ", currency)
        if currency is not None:
            currencies.append(currency)
    return natlang_seq(currencies)


_ERRMSG = "Ekki tókst að sækja upplýsingar um hraðbanka."


def _answ_for_atm_query(q: Query, result: Result) -> AnswerTuple:
    """Return an answer tuple for the given ATM query"""
    ans_start = ""
    atm_list: List[Dict[str, Any]] = []
    if "context_reference" in result and result.last_atm is not None:
        # There is a reference to a previous result
        # TODO: Handle multiple ATMs in same location, but with different services
        atm_list = result.last_atm
        atm_word = "hraðbankanum"  # if len(atm_list) == 1 else "hraðbönkunum"
        if result.qkey == "AtmFurtherInfoDeposit":
            # if any(atm["services"]["deposit"] is True for atm in atm_list):
            if atm_list[0]["services"]["deposit"] is True:
                ans_start = (
                    f"Já, hægt er að leggja inn á reikninginn þinn í {atm_word} við "
                )
            else:
                ans_start = f"Nei, ekki er hægt að leggja inn á reikninginn þinn í {atm_word} við "
        elif result.qkey == "AtmFurtherInfoWithdrawalLimit":
            ans_start = "Hámarksúttekt í {atm_word} við "

    elif "error_context_reference" in result:
        return gen_answer("Ég veit ekki til hvaða hraðbanka þú vísar.")
    else:
        location = q.location
        if location is None:
            return gen_answer("Ég veit ekki hvar þú ert.")

        if result.qkey == "ClosestAtm":
            atm_list = _closest_atm(location)
            ans_start = "Næsti hraðbanki"
        elif result.qkey == "ClosestAtmDeposit":
            atm_list = _closest_atm_deposit(location)
            ans_start = "Næsti hraðbanki sem tekur við innborgunum"
        elif result.qkey == "ClosestAtmForeignExchange":
            atm_list = _closest_atm_foreign_exchange(location)
        elif result.qkey == "ClosestAtmCoinmachine":
            atm_list = _closest_atm_coinmachine(location)

    answer = ""
    voice = ""

    if not atm_list or "distance" not in atm_list[0]:
        return gen_answer(_ERRMSG)
    assert atm_list is not None

    # store the last atm in result to store for next request
    result.last_atm = atm_list

    # TODO: Þarf að skipta upp td Norðurturni Smáralindar áður en meðhöndlað af NounPhrase?
    # TODO: "við" er ekki rétt í öllum tilfellum, td ætti að vera "í Norðurturni Smáralindar"
    street_name: str = NounPhrase(atm_list[0]["address"]["street"]).accusative or ""
    voice_street_name = _format_voice_street_number(street_name)

    if result.qkey == "ClosestAtm" or result.qkey == "ClosestAtmDeposit":
        answ_fmt = "{0} er við {1} og er {2} frá þér."
        answer = answ_fmt.format(
            ans_start,
            street_name,
            distance_desc(atm_list[0]["distance"], case="þgf"),
        )
        voice = answ_fmt.format(
            ans_start,
            voice_street_name,
            distance_desc(atm_list[0]["distance"], case="þgf", num_to_str=True),
        )
    elif result.qkey == "ClosestAtmForeignExchange":
        currencies_str = _get_foreign_exchange_string(atm_list)
        answ_fmt = "Hægt er að kaupa {0} í hraðbankanum við {1} og hann er {2} frá þér."
        answer = answ_fmt.format(
            currencies_str,
            street_name,
            distance_desc(atm_list[0]["distance"], case="þgf"),
        )
        voice = answ_fmt.format(
            currencies_str,
            voice_street_name,
            distance_desc(atm_list[0]["distance"], case="þgf", num_to_str=True),
        )
    elif result.qkey == "ClosestAtmCoinmachine":
        answ_fmt = "Hraðbankinn við {0} er með myntsöluvél og er {1} frá þér."
        answer = answ_fmt.format(
            street_name,
            distance_desc(atm_list[0]["distance"], case="þgf"),
        )
        voice = answ_fmt.format(
            voice_street_name,
            distance_desc(atm_list[0]["distance"], case="þgf", num_to_str=True),
        )
    elif result.qkey == "AtmFurtherInfoDeposit":
        answ_fmt = "{0}{1}."
        answer = answ_fmt.format(
            ans_start,
            street_name,
        )
        voice = answ_fmt.format(
            ans_start,
            voice_street_name,
        )
    elif result.qkey == "AtmFurtherInfoWithdrawalLimit":
        withdrawal_limit = max(atm["services"]["max_limit"] for atm in atm_list)
        ans_withdrawal_limit = krona_desc(withdrawal_limit)
        temp_string = ans_withdrawal_limit.split()
        temp_string[0] = number_to_text(withdrawal_limit, case="nf")
        voice_withdawal_limit = " ".join(temp_string)

        answ_fmt = "{0}{1} er {2}."
        answer = answ_fmt.format(
            ans_start,
            street_name,
            ans_withdrawal_limit,
        )

        voice = answ_fmt.format(
            ans_start,
            voice_street_name,
            voice_withdawal_limit,
        )
    elif result.qkey == "AtmFurtherInfoOpeningHours":
        ans_start = "Hraðbankinn við "
        opening_hours: str = atm_list[0]["opening_hours_text"].get("is", "")
        if len(opening_hours) is not 0:
            opening_hours = opening_hours[0].lower() + opening_hours[1:]
        if atm_list[0]["always_open"] is True:
            answ_fmt = "{0}{1} er alltaf opinn."
            answer = answ_fmt.format(
                ans_start,
                street_name,
            )
            voice = answ_fmt.format(
                ans_start,
                voice_street_name,
            )
        elif len(opening_hours) is not 0 and opening_hours.startswith("opnunartím"):
            answ_fmt = "{0}{1} fylgir {2}."
            answer = answ_fmt.format(
                ans_start,
                street_name,
                NounPhrase(opening_hours).dative,
            )
            voice = answ_fmt.format(
                ans_start,
                voice_street_name,
                NounPhrase(opening_hours).dative,
            )
        elif len(opening_hours) is not 0 and opening_hours.startswith("opið"):
            answ_fmt = "{0}{1} er {2}."
            opening_hours = opening_hours.replace("opið", "opinn")
            index = opening_hours.find("daga") + 4
            # Find opening hours from the string
            times = opening_hours[index:].replace(" ", "")
            open_time = times[: times.find("-")]
            close_time = times[times.find("-") + 1 :]
            voice_opening_hours = ""
            if index != -1:
                voice_opening_hours = opening_hours[:index] + " frá klukkan "
                opening_hours = (
                    opening_hours[:index]
                    + " frá klukkan "
                    + opening_hours[index:].replace(" ", "")
                )
            voice_opening_hours = (
                voice_opening_hours
                + number_to_text(open_time, case="þf")
                + " til "
                + number_to_text(close_time, case="þf")
            )
            answer = answ_fmt.format(
                ans_start,
                street_name,
                opening_hours,
            )
            voice = answ_fmt.format(
                ans_start,
                voice_street_name,
                voice_opening_hours,
            )
        else:
            return gen_answer("Ekki tókst að sækja opnunartíma fyrir hraðbankann.")
    elif result.qkey == "AtmFurtherInfoForeignExchange":
        # Check if atm accepts foreign exchange
        if atm_list[0]["services"]["foreign_exchange"]["active"] is True:
            currencies_str: str = _get_foreign_exchange_string(atm_list)
            ans_start = "Hægt er að kaupa "
            answ_fmt: str = "{0}{1} í hraðbankanum við {2}."
            answer: str = answ_fmt.format(
                ans_start,
                currencies_str,
                street_name,
            )
            voice: str = answ_fmt.format(
                ans_start,
                currencies_str,
                voice_street_name,
            )
        else:
            answ_fmt: str = (
                "Ekki er hægt að kaupa erlendan gjaldeyri í hraðbankanum við {0}."
            )
            answer: str = answ_fmt.format(
                street_name,
            )
            voice: str = answ_fmt.format(
                voice_street_name,
            )
    elif result.qkey == "AtmFurtherInfoCoinmachine":
        # Check if atm has a coinmachine
        if atm_list[0]["services"]["coinmachine"] is True:
            answ_fmt: str = "Hraðbankinn við {0} er með myntsöluvél."
            answer: str = answ_fmt.format(
                street_name,
            )
            voice: str = answ_fmt.format(
                voice_street_name,
            )
        else:
            answ_fmt: str = "Hraðbankinn við {0} er ekki með myntsöluvél."
            answer: str = answ_fmt.format(
                street_name,
            )
            voice: str = answ_fmt.format(
                voice_street_name,
            )

    response = dict(answer=answer)

    return response, answer, voice


def sentence(state: QueryStateDict, result: Result) -> None:
    """Called when sentence processing is complete"""
    q: Query = state["query"]
    if "qtype" in result and "qkey" in result:
        # Successfully matched a query type
        try:
            loc = q.location
            if loc:
                answ = _answ_for_atm_query(q, result)
            else:
                # We need a location but don't have one
                answ = gen_answer("Ég veit ekki hvar þú ert.")
            if answ:
                q.set_qtype(result.qtype)
                q.set_key(result.qkey)
                q.set_answer(*answ)
                # Pass the result into a query context having
                # the 'result' property
                if "last_atm" in result:
                    ctx = cast(ContextDict, dict(result=result.last_atm))
                    q.set_context(ctx)
        except Exception as e:
            logging.warning(f"Exception while processing ATM query: {e}")
            q.set_error(f"E_EXCEPTION: {e}")
            raise
    else:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
