"""

    Greynir: Natural language processing for Icelandic

    Petrol query response module

    Copyright (C) 2019 Miðeind ehf.

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

import logging
import cachetools

from geo import distance
from queries import (
    query_json_api,
    format_icelandic_float,
    gen_answer,
    distance_desc,
    krona_desc,
)


_PETROL_QTYPE = "Petrol"


TOPIC_LEMMAS = ["bensín", "bensínstöð", "bensínlítri", "dísel"]


def help_text(lemma):
    """ Help text to return when query.py is unable to parse a query but
        one of the above lemmas is found in it """
    return "Ég get svarað ef þú spyrð til dæmis: {0}?".format(
        random.choice(
            (
                "Hvar er næsta bensínstöð",
                "Hvar fæ ég ódýrasta bensínið",
                "Hvar er ódýrt að fylla tankinn",
            )
        )
    )


# This module wants to handle parse trees for queries
HANDLE_TREE = True

# The context-free grammar for the queries recognized by this plug-in module
GRAMMAR = """

Query →
    QPetrol

QPetrol → QPetrolQuery '?'?

QPetrolQuery →
    QPetrolClosestStation | QPetrolCheapestStation | QPetrolClosestCheapestStation

QPetrolClosestStation →
    "bensín" QPetrolNearMe?
    | QPetrolStation QPetrolNearMe
    | "hvar" "fæ" "ég" "bensín" QPetrolNearMe?
    | "hvar" "get" "ég" "fengið" "bensín" QPetrolNearMe?
    | "hvar" "get" "ég" "keypt" "bensín" QPetrolNearMe?
    | "hvar" "get" "ég" "fyllt" "á"? "tankinn" QPetrolNearMe?
    | "hvar" "er" QPetrolClosest QPetrolStation
    | "hver" "er" QPetrolClosest QPetrolStation
    | "hvaða" QPetrolStation "er" QPetrolNearMe

QPetrolCheapestStation →
    "ódýrasta" "bensínið"
    | "hvaða" "bensínstöð" "er" "ódýrust"
    | "hvaða" "bensínstöð" "er" "með" "ódýrasta" "bensínið"
    | "hvaða" "bensínstöð" "er" "með" "ódýrasta" "bensínlítrann"
    | "hvaða" "bensínstöð" "er" "ódýrust"
    | "hvaða" "bensínstöð" "er" "með" "lægsta" "verðið"
    | "hvaða" "bensínstöð" "er" "með" "lægsta" "verðið" "á" "bensíni"
    | "hvar" "er" "bensín" "ódýrast"
    | "hvar" "er" "bensínið" "ódýrast"
    | "hvar" "er" "bensínlítrinn" "ódýrastur"
    | "hvar" "fæ" "ég" "ódýrasta" "bensínið"
    | "hvar" "fæ" "ég" "ódýrasta" "bensínlítrann"
    | "hvar" "er" "ódýrast" "að" "fylla" "á"? "tankinn"

QPetrolClosestCheapestStation →
    "ódýrt" "bensín" QPetrolNearMe?
    | "hvar" "fæ" "ég" "ódýrt" "bensín" QPetrolNearMe?
    | "hvar" "fæ" "ég" "bensínlítrann" "ódýrt" QPetrolNearMe?
    | "hvar" "fær" "maður" "ódýrt" "bensín" QPetrolNearMe?
    | "hvar" "fær" "maður" "bensín" "ódýrt" QPetrolNearMe?
    | "hvar" "fær" "maður" "bensínlítran" "ódýrt" QPetrolNearMe?
    | "hvar" "er" "bensínið" "ódýrt" QPetrolNearMe?
    | "hvar" "er" "bensínlítrinn" "ódýr" QPetrolNearMe?
    | "hvar" "er" "ódýrt" "bensín" QPetrolNearMe?
    | "hvar" "er" "ódýrt" "að" "kaupa" "bensín" QPetrolNearMe?
    | "hvaða" "bensínstöð" QPetrolNearMe? "er" "með" "ódýrt" "bensín"
    | "hvaða" "bensínstöð" QPetrolNearMe? "er" "ódýr"
    | "hvaða" "bensínstöð" QPetrolNearMe? "er" "með" "lágt" "verð"
    | "hvaða" "bensínstöð" QPetrolNearMe? "er" "með" "lágt" "verð" "á" "bensíni"
    | "hvar" "er" "ódýrast" "að" "fylla" "á"? "tankinn" QPetrolNearMe?
    | "hvar" "er" "ódýrt" "að" "fylla" "á"? "tankinn" QPetrolNearMe?
    | "hvar" "get" "ég" "fyllt" "á" "tankinn" "ódýrt" QPetrolNearMe?

QPetrolClosest →
    "næsta" | "nálægasta"

QPetrolNearMe →
    "nálægt" "mér"? | QPetrolHere? "í" "grenndinni" | QPetrolHere? "í" "grennd"
    | QPetrolHere "á" "svæðinu" | QPetrolHere? "skammt" "frá" "mér"? | QPetrolHere? "í" "nágrenninu"

QPetrolHere →
    "hér" | "hérna"

QPetrolStation →
    "bensínstöð" | "bensínstöðin" | "bensínafgreiðsla" 

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


_PETROL_API = "https://apis.is/petrol"
_PETROL_CACHE_TTL = 3600  # seconds


# @cachetools.cached(cachetools.TTLCache(1, _PETROL_CACHE_TTL))
def _get_petrol_station_data():
    """ Fetch list of petrol stations w. prices from apis.is """
    pd = query_json_api(_PETROL_API)
    if not pd or "results" not in pd:
        return None
    return pd["results"]


def _closest_petrol_station(loc):
    """ Find petrol station closest to the given location. """
    pd = _get_petrol_station_data()
    if not pd:
        return None

    lat, lon = loc

    # Calculate distance of all stations
    for s in pd:
        s["distance"] = distance((lat, lon), (s["geo"]["lat"], s["geo"]["lon"]))

    dist_sorted = sorted(pd, key=lambda s: s["distance"])
    if dist_sorted:
        return dist_sorted[0]


def _cheapest_station():
    pass


_ERRMSG = "Ekki tókst að sækja upplýsingar um bensínstöðvar."


def _answ_for_petrol_query(q, result):

    if result.qkey == "ClosestStation":
        station = _closest_petrol_station(q.location)
        answer = "{0} {1} ({2}, bensínverð {3})"
        voice = "Næsta bensínstöð er {0} {1} í u.þ.b. {2} fjarlægð. Þar kostar bensínlítrinn {3}."
    elif result.qkey == "CheapestStation":
        pass
    elif result.qkey == "ClosestCheapestStation":
        pass

    if not station or not "bensin95" in station or not "distance" in station:
        return gen_answer(_ERRMSG)

    dist_nf = distance_desc(station["distance"], case="þf")
    dist_þf = distance_desc(station["distance"], case="þf")
    kr_desc = krona_desc(float(station["bensin95"]))

    answer = answer.format(station["company"], station["name"], dist_nf, kr_desc)
    response = dict(answer=answer)
    voice = voice.format(station["company"], station["name"], dist_þf, kr_desc)

    return response, answer, voice


def sentence(state, result):
    """ Called when sentence processing is complete """
    q = state["query"]
    if "qtype" in result and "qkey" in result:
        # Successfully matched a query type
        try:
            loc = q.location
            answ = _answ_for_petrol_query(q, result)
            if answ:
                q.set_qtype(result.qtype)
                q.set_key(result.qkey)
                q.set_answer(*answ)
        except Exception as e:
            logging.warning("Exception while processing petrol query: {0}".format(e))
            q.set_error("E_EXCEPTION: {0}".format(e))
            raise
    else:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
