"""

    Greynir: Natural language processing for Icelandic

    Petrol query response module

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


    This module handles petrol-related queries.

"""

# TODO: "Hver er ódýrasta bensínstöðin innan X kílómetra? Innan X kílómetra radíus?" etc.
# TODO: Laga krónutölur og fjarlægðartölur f. talgervil

from typing import List, Dict, Tuple, Optional

import logging
import cachetools  # type: ignore
import random

from geo import distance
from query import Query
from queries import query_json_api, gen_answer, distance_desc, krona_desc

from . import AnswerTuple, LatLonTuple


_PETROL_QTYPE = "Petrol"


TOPIC_LEMMAS = [
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
    """Help text to return when query.py is unable to parse a query but
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
GRAMMAR = """

Query →
    QPetrol

QPetrol → QPetrolQuery '?'?

QPetrolQuery →
    QPetrolClosestStation | QPetrolCheapestStation QPetrolNow? | QPetrolClosestCheapestStation

QPetrolClosestStation →
    QPetrolPetrol QPetrolNearMe?
    | QPetrolStation QPetrolNearMe?
    | "hvar" QPetrolCanIGet QPetrolPetrol QPetrolNearMe?
    | "hvar" QPetrolCanI "keypt" QPetrolPetrol QPetrolNearMe?
    | "hvar" QPetrolCanI "fyllt" "á"? QPetrolFillableÞf QPetrolNearMe?
    | QPetrolWhereIs? QPetrolClosest QPetrolStation
    | "hver" "er" QPetrolClosest QPetrolStation
    | QPetrolWhichStation "er"? QPetrolNearMe
    | QPetrolWhichStation "er"? "nálægust" "mér"?
    | "hvað" "kostar" QPetrolPetrol QPetrolNearMe?

QPetrolCheapestStation →
    "ódýrasta" QPetrolPetrol
    | QPetrolWhereIs "ódýrasta" QPetrolPetrol
    | QPetrolWhichStation "er" "ódýrust"
    | QPetrolWhichStation QPetrolHas "ódýrasta" QPetrolPetrol
    | QPetrolWhichStation QPetrolHas "ódýrasta" "bensínlítrann"
    | QPetrolWhichStation QPetrolHas QPetrolBestPriceÞf
    | QPetrolWhichStation QPetrolHas QPetrolBestPriceÞf "á" "bensínlítranum"
    | QPetrolWhichStation QPetrolHas QPetrolBestPriceÞf "á" "bensíni"
    | QPetrolWhichStation QPetrolHas QPetrolBestPriceÞf "á" "dísel" "lítranum"
    | QPetrolWhichStation QPetrolHas QPetrolBestPriceÞf "á" "dísel"
    | QPetrolWhereIs QPetrolPetrol "ódýrast"
    | QPetrolWhereIs "bensínlítrinn" "ódýrastur"
    | "hvar" QPetrolCanIGet "ódýrasta" QPetrolPetrol
    | "hvar" QPetrolCanIGet "ódýrasta" "bensínlítrann"
    | QPetrolWhereIs "ódýrast" "að" "fylla" "á"? QPetrolFillableÞf

QPetrolClosestCheapestStation →
    "ódýrt" QPetrolPetrol QPetrolNearMe?
    | "hvar" QPetrolCanIGet "ódýrt" QPetrolPetrol QPetrolNearMe?
    | "hvar" QPetrolCanIGet "ódýrasta" QPetrolPetrol QPetrolNearMe
    | "hvar" QPetrolCanIGet "bensínlítrann" "ódýrt" QPetrolNearMe?
    | "hvar" QPetrolCanIGet QPetrolPetrol "ódýrast" QPetrolNearMe
    | "hvar" QPetrolCanIGet QPetrolPetrol "ódýrt" QPetrolNearMe?
    | "hvar" QPetrolCanIGet QPetrolPetrol "á" "góðu" "verði" QPetrolNearMe?
    | "hvar" QPetrolCanI "fyllt" "á" QPetrolFillableÞf "ódýrt" QPetrolNearMe?
    | QPetrolWhereIs QPetrolPetrol "ódýrt" QPetrolNearMe?
    | QPetrolWhereIs QPetrolPetrol "ódýrast" QPetrolNearMe
    | QPetrolWhereIs "bensínlítrinn" "ódýr" QPetrolNearMe?
    | QPetrolWhereIs "bensínlítrinn" "ódýrastur" QPetrolNearMe
    | QPetrolWhereIs "ódýrt" QPetrolPetrol QPetrolNearMe?
    | QPetrolWhereIs "ódýrt" "að" "kaupa" QPetrolPetrol QPetrolNearMe?
    | QPetrolWhereIs "ódýrt" "að" "fylla" "á"? QPetrolFillableÞf QPetrolNearMe?
    | QPetrolWhichStation QPetrolNearMe? QPetrolHas "ódýrt" QPetrolPetrol
    | QPetrolWhichStation QPetrolNearMe? "er" "ódýr"
    | QPetrolWhichStation QPetrolNearMe? QPetrolHas QPetrolLowPriceÞf
    | QPetrolWhichStation QPetrolNearMe? QPetrolHas QPetrolLowPriceÞf "á" "bensíni"
    | QPetrolWhichStation QPetrolHas "ódýrt" QPetrolPetrol QPetrolNearMe?
    | QPetrolWhichStation "er" "ódýr" QPetrolNearMe?
    | QPetrolWhichStation QPetrolHas QPetrolLowPriceÞf QPetrolNearMe?
    | QPetrolWhichStation QPetrolHas QPetrolLowPriceÞf "á" "bensíni" QPetrolNearMe?

QPetrolCanI →
    "get" "ég" | "getur" "maður"

QPetrolWhereIs →
    "hvar" "er"

QPetrolCanIGet →
    "fæ" "ég" | "fær" "maður" | "get" "ég" "fengið" | "getur" "maður" "fengið"
    | "kaupi" "ég" | "kaupir" "maður" | "get" "ég" "keypt" | "getur" "maður" "keypt"

QPetrolHas →
    "er" "með" | "hefur" | "býður" "upp" "á"

QPetrolPetrol →
    "bensín" | "bensínið" | "eldsneyti" | "eldsneytið" | "dísel" | "díselið"
    | "díselolía" | "díselolíu"

QPetrolClosest →
    "næsta" | "nálægasta"

QPetrolFillableÞf →
    "tank" | "tankinn" | "bensíntank" | "bensíntankinn"
    | "bílinn" | "bifreiðina" | "eldsneytið" | "eldsneytistankinn"

QPetrolNearMe →
    QPetrolHere? QPetrolAround

QPetrolAround →
    "nálægt" "mér"? | "í" "grenndinni" | "í" "grennd" | "á" "svæðinu"
    | "skammt" "frá" "mér"? | "í" "nágrenninu"

QPetrolHere →
    "hér" | "hérna"

QPetrolNow →
    "núna" | "í" "dag" | "eins" "og" "stendur" | "í" "augnablikinu" | "þessa_dagana"

QPetrolStation →
    "bensínstöð" | "bensínstöðin" | "bensínafgreiðslustöð"

QPetrolWhichStation →
    "hvaða" "bensínstöð" | "hvaða" "bensínafgreiðslustöð"

QPetrolLowPriceÞf →
    "lágt" "verð" | "gott" "verð" | "lágan" "prís" | "góðan" "prís"
    | "sæmilegt" "verð" | "sæmilegan" "prís"

QPetrolBestPriceÞf →
    "lægsta" "verðið" | "besta" "verðið" | "besta" "verð" | "lægsta" "verð"
    | "lægsta" "prísinn" | "besta" "prísinn" | "lægsta" "prís" | "besta" "prís"

$score(+35) QPetrol

"""


def QPetrolQuery(node, params, result):
    result.qtype = _PETROL_QTYPE


def QPetrolClosestStation(node, params, result):
    result.qkey = "ClosestStation"


def QPetrolCheapestStation(node, params, result):
    result.qkey = "CheapestStation"


def QPetrolClosestCheapestStation(node, params, result):
    result.qkey = "ClosestCheapestStation"


_COMPANY_NAME_FIXES = {"Costco Iceland": "Costco"}


_PETROL_API = "https://apis.is/petrol"
_PETROL_CACHE_TTL = 3600  # seconds, ttl 1 hour


@cachetools.cached(cachetools.TTLCache(1, _PETROL_CACHE_TTL))
def _get_petrol_station_data() -> Optional[List]:
    """ Fetch list of petrol stations w. prices from apis.is (Gasvaktin) """
    pd = query_json_api(_PETROL_API)
    if not pd or "results" not in pd:
        return None

    # Fix company names
    for s in pd["results"]:
        name = s.get("company", "")
        s["company"] = _COMPANY_NAME_FIXES.get(name, name)

    return pd["results"]


def _stations_with_distance(loc: Optional[LatLonTuple]) -> Optional[List]:
    """ Return list of petrol stations w. added distance data. """
    pd = _get_petrol_station_data()
    if not pd:
        return None

    if loc:
        # Calculate distance of all stations
        for s in pd:
            s["distance"] = distance(loc, (s["geo"]["lat"], s["geo"]["lon"]))

    return pd


def _closest_petrol_station(loc: LatLonTuple) -> Optional[Dict]:
    """ Find petrol station closest to the given location. """
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


def _answ_for_petrol_query(q: Query, result) -> AnswerTuple:
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
        dist_nf = distance_desc(station["distance"], case="nf")
        dist_þf = distance_desc(station["distance"], case="þf")
        answer = answ_fmt.format(
            station["company"], station["name"], dist_nf, bensin_kr_desc, diesel_kr_desc
        )
        voice = voice_fmt.format(
            desc,
            station["company"],
            station["name"],
            dist_þf,
            bensin_kr_desc,
            diesel_kr_desc,
        )
    else:
        answ_fmt = "{0} {1} (bensínverð {2}, díselverð {3})"
        voice_fmt = "{0} er {1} {2}. Þar kostar bensínlítrinn {3} og dísel-lítrinn {4}."
        answer = answ_fmt.format(
            station["company"], station["name"], bensin_kr_desc, diesel_kr_desc
        )
        voice = voice_fmt.format(
            desc, station["company"], station["name"], bensin_kr_desc, diesel_kr_desc
        )

    response = dict(answer=answer)

    return response, answer, voice


def sentence(state, result) -> None:
    """ Called when sentence processing is complete """
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
            logging.warning("Exception while processing petrol query: {0}".format(e))
            q.set_error("E_EXCEPTION: {0}".format(e))
            raise
    else:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
