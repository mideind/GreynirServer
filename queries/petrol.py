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


    This module handles petrol-related queries.

"""

# TODO: "Hver er ódýrasta bensínstöðin innan X kílómetra? Innan X kílómetra radíus?" etc.
# TODO: Type hints

from typing import List, Dict, Optional

import logging
import cachetools  # type: ignore
import random

from icespeak import gssml

from geo import distance
from tree import Result, Node
from queries import Query, QueryStateDict
from queries.util import (
    query_json_api,
    gen_answer,
    distance_desc,
    krona_desc,
    AnswerTuple,
    LatLonTuple,
    read_grammar_file,
)

_PETROL_QTYPE = "Petrol"


TOPIC_LEMMAS: List[str] = [
    "bensín",
    "bensínstöð",
    "bensínlítri",
    "dísel",
    "tankur",
    "bensíntankur",
    "bíll",
    "eldsneyti",
    "olía",
    "díselolía",
    "bifreið",
]


def help_text(lemma: str) -> str:
    """Help text to return when query processor is unable to parse a query but
    one of the above lemmas is found in it"""
    return "Ég get svarað ef þú spyrð til dæmis: {0}?".format(
        random.choice(
            (
                "Hvar er næsta bensínstöð",
                "Hvar fæ ég ódýrasta bensínið",
                "Hvar er ódýrt að fylla tankinn",
                "Hvar fæ ég ódýrt bensín í nágrenninu",
            )
        )
    )


# This module wants to handle parse trees for queries
HANDLE_TREE = True

# The grammar nonterminals this module wants to handle
QUERY_NONTERMINALS = {"QPetrol"}

# The context-free grammar for the queries recognized by this plug-in module
GRAMMAR = read_grammar_file("petrol")


def QPetrolQuery(node: Node, params: QueryStateDict, result: Result) -> None:
    result.qtype = _PETROL_QTYPE


def QPetrolClosestStation(node: Node, params: QueryStateDict, result: Result) -> None:
    result.qkey = "ClosestStation"


def QPetrolCheapestStation(node: Node, params: QueryStateDict, result: Result) -> None:
    result.qkey = "CheapestStation"


def QPetrolClosestCheapestStation(
    node: Node, params: QueryStateDict, result: Result
) -> None:
    result.qkey = "ClosestCheapestStation"


_COMPANY_NAME_FIXES = {"Costco Iceland": "Costco"}


_PETROL_API = "https://apis.is/petrol"
_PETROL_CACHE_TTL = 3600  # seconds, ttl 1 hour


@cachetools.cached(cachetools.TTLCache(1, _PETROL_CACHE_TTL))
def _get_petrol_station_data() -> Optional[List]:
    """Fetch list of petrol stations w. prices from apis.is (Gasvaktin)"""
    pd = query_json_api(_PETROL_API)
    if not isinstance(pd, dict) or "results" not in pd:
        return None

    # Fix company names
    for s in pd["results"]:
        name = s.get("company", "")
        s["company"] = _COMPANY_NAME_FIXES.get(name, name)

    return pd["results"]


def _stations_with_distance(loc: Optional[LatLonTuple]) -> Optional[List]:
    """Return list of petrol stations w. added distance data."""
    pd = _get_petrol_station_data()
    if not pd:
        return None

    if loc:
        # Calculate distance of all stations
        for s in pd:
            s["distance"] = distance(loc, (s["geo"]["lat"], s["geo"]["lon"]))

    return pd


def _closest_petrol_station(loc: LatLonTuple) -> Optional[Dict]:
    """Find petrol station closest to the given location."""
    stations = _stations_with_distance(loc)
    if not stations:
        return None

    # Sort by distance
    dist_sorted = sorted(stations, key=lambda s: s["distance"])
    return dist_sorted[0] if dist_sorted else None


def _cheapest_petrol_station() -> Optional[Dict]:
    stations = _get_petrol_station_data()
    if not stations:
        return None

    # Sort by price
    price_sorted = sorted(stations, key=lambda s: s["bensin95"])
    return price_sorted[0] if price_sorted else None


# Too liberal?
_CLOSE_DISTANCE = 5.0  # km


def _closest_cheapest_petrol_station(loc: LatLonTuple) -> Optional[Dict]:
    stations = _stations_with_distance(loc)
    if not stations:
        return None

    # Filter out all stations that are not close by
    filtered = filter(lambda x: x["distance"] <= _CLOSE_DISTANCE, stations)

    # Sort by price
    price_sorted = sorted(filtered, key=lambda s: s["bensin95"])
    return price_sorted[0] if price_sorted else None


_ERRMSG = "Ekki tókst að sækja upplýsingar um bensínstöðvar."


def _answ_for_petrol_query(q: Query, result: Result) -> AnswerTuple:
    req_distance = True
    location = q.location
    if location is None:
        return gen_answer("Ég veit ekki hvar þú ert")
    if result.qkey == "ClosestStation":
        station = _closest_petrol_station(location)
        answer = "{0} {1} ({2}, bensínverð {3})"
        desc = "Næsta bensínstöð"
    elif result.qkey == "CheapestStation":
        station = _cheapest_petrol_station()
        answer = "{0} {1} ({2}, bensínverð {3})"
        desc = "Ódýrasta bensínstöðin"
        req_distance = False
    elif result.qkey == "ClosestCheapestStation":
        station = _closest_cheapest_petrol_station(location)
        desc = "Ódýrasta bensínstöðin í grenndinni"
    else:
        raise ValueError("Unknown petrol query type")

    if (
        not station
        or "bensin95" not in station
        or "diesel" not in station
        or (req_distance and "distance" not in station)
    ):
        return gen_answer(_ERRMSG)

    bensin_kr_desc = krona_desc(float(station["bensin95"]))
    diesel_kr_desc = krona_desc(float(station["diesel"]))

    if req_distance:
        answ_fmt = "{0} {1} ({2}, bensínverð {3}, díselverð {4})"
        voice_fmt = (
            "{0} er {1} {2} í um það bil {3} fjarlægð. "
            "Þar kostar bensínlítrinn {4} og dísel-lítrinn {5}."
        )

        answer = answ_fmt.format(
            station["company"],
            station["name"],
            distance_desc(station["distance"], case="nf"),
            bensin_kr_desc,
            diesel_kr_desc,
        )
        voice = voice_fmt.format(
            desc,
            station["company"],
            station["name"],
            distance_desc(station["distance"], case="ef", num_to_str=True),
            gssml(bensin_kr_desc, type="floats", gender="kvk", comma_null=False),
            gssml(diesel_kr_desc, type="floats", gender="kvk", comma_null=False),
        )
    else:
        answ_fmt = "{0} {1} (bensínverð {2}, díselverð {3})"
        voice_fmt = "{0} er {1} {2}. Þar kostar bensínlítrinn {3} og dísel-lítrinn {4}."
        answer = answ_fmt.format(
            station["company"], station["name"], bensin_kr_desc, diesel_kr_desc
        )
        voice = voice_fmt.format(
            desc,
            station["company"],
            station["name"],
            gssml(bensin_kr_desc, type="floats", gender="kvk", comma_null=False),
            gssml(diesel_kr_desc, type="floats", gender="kvk", comma_null=False),
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
            if result.qkey == "CheapestStation" or loc:
                answ = _answ_for_petrol_query(q, result)
            else:
                # We need a location but don't have one
                answ = gen_answer("Ég veit ekki hvar þú ert.")
            if answ:
                q.set_qtype(result.qtype)
                q.set_key(result.qkey)
                q.set_answer(*answ)
                q.set_source("Gasvaktin")
        except Exception as e:
            logging.warning(f"Exception while processing petrol query: {e}")
            q.set_error(f"E_EXCEPTION: {e}")
            raise
    else:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
