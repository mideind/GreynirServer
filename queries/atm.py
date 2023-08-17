"""

    Greynir: Natural language processing for Icelandic

    Petrol query response module

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

from typing import Any, Dict, List, Optional, cast

import os
import logging
import random
import json  # TODO: remove after we fetch json data online

from geo import distance
from tree import Result, Node
from queries import ContextDict, Query, QueryStateDict
from reynir import NounPhrase
from queries.util import (
    gen_answer,
    distance_desc,
    krona_desc,
    AnswerTuple,
    LatLonTuple,
    read_grammar_file,
)
from speech.trans.num import number_to_text

_ATM_QTYPE = "Atm"


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


def _temp_atm_json_data_from_file() -> dict:
    """Read JSON data from file"""
    try:
        script_dir = os.path.dirname(__file__)  # <-- absolute dir the script is in
        rel_path = "../resources/geo/atms.json"
        abs_file_path = os.path.join(script_dir, rel_path)
        with open(abs_file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.error("Error reading temp_atm.json: %s", e)
        return None


# TODO: Add caching
def _get_atm_data() -> Optional[List]:
    """Fetch list of atms w. prices from islandsbanki.is"""
    # TODO: Change from file to fetching from islandsbanki.is if they allow it
    atm_data = _temp_atm_json_data_from_file()

    return atm_data


def _atms_with_distance(loc: Optional[LatLonTuple]) -> Optional[List]:
    """Return list of atms w. added distance data."""
    atm_data = _get_atm_data()
    if not atm_data:
        return None

    filtered_atm_data = []
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


def _closest_atm(loc: LatLonTuple) -> Optional[Dict]:
    """Find ATM closest to the given location."""
    atms = _atms_with_distance(loc)
    if not atms:
        return None

    # Sort by distance
    dist_sorted = sorted(atms, key=lambda s: s["distance"])
    return dist_sorted[0] if dist_sorted else None


def _closest_atm_deposit(loc: LatLonTuple) -> Optional[Dict]:
    """Find ATM closest to the given location that accepts deposits."""
    atms = _atms_with_distance(loc)
    if not atms:
        return None

    filtered_atms = []
    for atm in atms:
        services = atm.get("services", {})
        if services.get("deposit", False) is True:
            filtered_atms.append(atm)
    atms = filtered_atms

    # Sort by distance
    dist_sorted = sorted(atms, key=lambda s: s["distance"])
    return dist_sorted[0] if dist_sorted else None


def _format_voice_street_number(s: str) -> str:
    """
    Format street name for voice output,
    also if it contains a range of numbers
    for example: Fiskislóð 7-9 becomes Fiskislóð sjö til níu
    """
    if s is None:
        return ""
    # Formatting numbers
    word_list = s.split()
    last_word = word_list[-1]
    if last_word[-1].isnumeric():
        # check if last word contains "–"
        # TODO: Notice this is not a regular hyphen, check if this is a problem. Regular hyphen does not work with the data
        if "–" in last_word:
            split_nr = last_word.split("–")
            first_number = number_to_text(split_nr[0], case="þf")
            last_number = number_to_text(split_nr[-1], case="þf")
            number = first_number + " til " + last_number
            return " ".join(word_list[:-1]) + " " + number
        return " ".join(word_list[:-1]) + " " + number_to_text(last_word, case="þf")
    return s


_ERRMSG = "Ekki tókst að sækja upplýsingar um hraðbanka."


def _answ_for_atm_query(q: Query, result: Result) -> AnswerTuple:
    """Return an answer tuple for the given ATM query"""
    ans_start = ""
    atm = None
    if "context_reference" in result:
        # There is a reference to a previous result
        atm = result.last_atm
        if result.qkey == "AtmFurtherInfoDeposit":
            if atm["services"]["deposit"] is True:
                ans_start = (
                    "Já, hægt er að leggja inn á reikninginn þinn í hraðbankanum við "
                )
            else:
                ans_start = "Nei, ekki er hægt að leggja inn á reikninginn þinn í hraðbankanum við "
        elif result.qkey == "AtmFurtherInfoWithdrawalLimit":
            ans_start = "Hámarksúttekt í hraðbankanum við "

    elif "error_context_reference" in result:
        return gen_answer("Ég veit ekki til hvers þú vísar.")
    else:
        location = q.location
        if location is None:
            return gen_answer("Ég veit ekki hvar þú ert.")

        if result.qkey == "ClosestAtm":
            atm = _closest_atm(location)
            ans_start = "Næsti hraðbanki"
        elif result.qkey == "ClosestAtmDeposit":
            atm = _closest_atm_deposit(location)
            ans_start = "Næsti hraðbanki sem tekur við innborgunum"
        answer = ""

    if atm is None or "distance" not in atm:
        return gen_answer(_ERRMSG)
    assert atm is not None

    # store the last atm in result to store for next request
    result.last_atm = atm
    # TODO: Þarf að skipta upp td Norðurturni Smáralindar áður en meðhöndlað af NounPhrase?
    # TODO: "við" er ekki rétt í öllum tilfellum, td ætti að vera "í Norðurturni Smáralindar"
    street_name = NounPhrase(atm["address"]["street"]).accusative
    voice_street_name = _format_voice_street_number(street_name)

    if result.qkey == "ClosestAtm" or result.qkey == "ClosestAtmDeposit":
        answ_fmt = "{0} er við {1} og er {2} frá þér."
        voice_fmt = "{0} er við {1} og er {2} frá þér."
        answer = answ_fmt.format(
            ans_start,
            street_name,
            distance_desc(atm["distance"], case="þgf"),
        )
        voice = voice_fmt.format(
            ans_start,
            voice_street_name,
            distance_desc(atm["distance"], case="þgf", num_to_str=True),
        )
    elif result.qkey == "AtmFurtherInfoDeposit":
        answ_fmt = "{0}{1}."
        voice_fmt = "{0}{1}."
        answer = answ_fmt.format(
            ans_start,
            street_name,
        )
        voice = voice_fmt.format(
            ans_start,
            voice_street_name,
        )
    elif result.qkey == "AtmFurtherInfoWithdrawalLimit":
        withdrawal_limit = atm["services"]["max_limit"]
        ans_withdrawal_limit = krona_desc(withdrawal_limit)
        temp_string = ans_withdrawal_limit.split()
        temp_string[0] = number_to_text(withdrawal_limit, case="nf")
        voice_withdawal_limit = " ".join(temp_string)

        answ_fmt = "{0}{1} er {2}."
        voice_fmt = "{0}{1} er {2}."
        answer = answ_fmt.format(
            ans_start,
            street_name,
            ans_withdrawal_limit,
        )

        voice = voice_fmt.format(
            ans_start,
            voice_street_name,
            voice_withdawal_limit,
        )
    elif result.qkey == "AtmFurtherInfoOpeningHours":
        ans_start = "Hraðbankinn við "
        opening_hours: str = atm.get("opening_hours_text").get("is", "")
        opening_hours = opening_hours[0].lower() + opening_hours[1:]
        if atm["always_open"] is True:
            answ_fmt = "{0}{1} er alltaf opinn."
            voice_fmt = "{0}{1} er alltaf opinn."
            answer = answ_fmt.format(
                ans_start,
                street_name,
            )
            voice = voice_fmt.format(
                ans_start,
                voice_street_name,
            )
        elif len(opening_hours) is not 0 and opening_hours.startswith("opnunartím"):
            answ_fmt = "{0}{1} fylgir {2}."
            voice_fmt = "{0}{1} fylgir {2}."
            answer = answ_fmt.format(
                ans_start,
                street_name,
                NounPhrase(opening_hours).dative,
            )
            voice = voice_fmt.format(
                ans_start,
                voice_street_name,
                NounPhrase(opening_hours).dative,
            )
        elif len(opening_hours) is not 0 and opening_hours.startswith("opið"):
            answ_fmt = "{0}{1} er {2}."
            voice_fmt = "{0}{1} er {2}."
            opening_hours = opening_hours.replace("opið", "opinn")
            index = opening_hours.find("daga") + 4
            if index != -1:
                opening_hours = (
                    opening_hours[:index] + " frá klukkan" + opening_hours[index:]
                )
            opening_hours_list = opening_hours.split()
            opening_hours_list[-1] = number_to_text(opening_hours_list[-1], case="þf")
            opening_hours_list[-2] = "til"
            opening_hours_list[-3] = number_to_text(opening_hours_list[-3], case="þf")
            voice_opening_hours = " ".join(opening_hours_list)
            answer = answ_fmt.format(
                ans_start,
                street_name,
                opening_hours,
            )
            voice = voice_fmt.format(
                ans_start,
                voice_street_name,
                voice_opening_hours,
            )
        else:
            return gen_answer("Ekki tókst að sækja opnunartíma fyrir hraðbankann.")

        # Hraðbankinn við ... er opinn alla virka daga frá 10-16
        # Hraðbankinn við ... fylgir opnunartíma Eiðistorgs
        # Hraðbankinn við ... er alltaf opinn

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
                q.set_source("Íslandsbanki")
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
