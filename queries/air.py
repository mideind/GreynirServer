"""

    Greynir: Natural language processing for Icelandic

    Air quality query response module

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


    This module handles queries related to air quality.

"""

from typing import List, Optional, Dict

import json
import logging
import cachetools  # type: ignore

import requests

from geo import LatLonTuple, in_iceland, distance
from tree import Result, Node
from query import Query, QueryStateDict
from . import gen_answer


def closest_station(latlon: LatLonTuple) -> Optional[Dict]:
    """ Returns air quality monitoring station closest to coordinates, w. distance. """
    stations = stations_info()
    if not stations:
        return None

    sd = [distance(latlon, (i["latitude"], i["longitude"]), i) for i in stations]
    closest = sorted(sd, key=lambda i: i[0])

    return closest[0]


STATIONS: Optional[List] = None
STATIONS_URL = "https://api.ust.is/aq/a/getStations"
STATIONS_CACHE_TTL = 24 * 60 * 60  # 24 hours


@cachetools.cached(cachetools.TTLCache(1, STATIONS_CACHE_TTL))
def stations_info() -> Optional[List]:
    """ Fetch list of air quality monitoring stations. """
    try:
        r = requests.get(STATIONS_URL)
    except Exception as e:
        logging.warning(str(e))
        return None

    # Verify that status is OK
    if r.status_code != 200:
        logging.warning(f"Received status {r.status_code} from API server")
        return None

    # Parse json API response
    try:
        res = json.loads(r.text)
    except Exception as e:
        logging.warning(f"Error parsing JSON API response: {e}")
        return None

    if not isinstance(res, list):
        logging.warning("Invalid data format from air quality API")
        return None

    global STATIONS
    STATIONS = res
    return STATIONS


_MAX_STATION_DISTANCE = 100


def _answ_airquality_query(q: Query, result: Result) -> None:
    """ Answer air quality query. """

    if not q.location:
        q.set_answer(gen_answer("Ég veit ekki hvar þú ert."))
        return

    distance, station = closest_station(q.location)
    if distance > _MAX_STATION_DISTANCE:
        q.set_answer(gen_answer("Þú ert ekki nálægt neinni loftgæðastöð."))
        return

    q.set_qtype(result.qtype)
    q.set_key(result.qkey)
    q.set_answer(*gen_answer("Blabla"))
    q.set_source("Umhverfisstofnun")


def sentence(state: QueryStateDict, result: Result) -> None:
    """ Called when sentence processing is complete """
    q: Query = state["query"]
    if "qtype" in result and "qkey" in result:
        # Successfully matched a query type
        try:
            if result.qkey == "AirQuality":
                _answ_airquality_query(q)
        except Exception as e:
            logging.warning("Exception while processing petrol query: {0}".format(e))
            q.set_error("E_EXCEPTION: {0}".format(e))
            raise
    else:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
