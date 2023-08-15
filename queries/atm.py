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

from typing import List, Dict, Optional

import os
import logging
import random
import json  # TODO: remove after we fetch json data online

from geo import distance
from tree import Result, Node
from queries import Query, QueryStateDict
from queries.util import (
    gen_answer,
    distance_desc,
    AnswerTuple,
    LatLonTuple,
    read_grammar_file,
)

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
        if item_type is not "atm":
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


_ERRMSG = "Ekki tókst að sækja upplýsingar um hraðbanka."


def _answ_for_atm_query(q: Query, result: Result) -> AnswerTuple:
    """Return an answer tuple for the given ATM query"""
    location = q.location
    if location is None:
        return gen_answer("Ég veit ekki hvar þú ert.")

    ans_start = ""
    # TODO: Check where qkey is defined and add one for ATMs
    if result.qkey == "ClosestAtm":
        atm = _closest_atm(location)
        ans_start = "Næsti hraðbanki"
    elif result.qkey == "ClosestAtmDeposit":
        atm = _closest_atm_deposit(location)
        ans_start = "Næsti hraðbanki sem tekur við innborgunum"
    answer = ""

    if not atm or "distance" not in atm:
        return gen_answer(_ERRMSG)

    answ_fmt = "{0} er á {1} og er {2} frá þér."
    voice_fmt = "{0} er á {1} og er {2} frá þér."
    answer = answ_fmt.format(
        ans_start,
        atm["address"]["street"],
        distance_desc(atm["distance"], case="þgf"),
    )
    voice = voice_fmt.format(
        ans_start,
        atm["address"]["street"],
        distance_desc(atm["distance"], case="þgf", num_to_str=True),
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
                q.set_source("Íslandsbanki")
        except Exception as e:
            logging.warning(f"Exception while processing ATM query: {e}")
            q.set_error(f"E_EXCEPTION: {e}")
            raise
    else:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
