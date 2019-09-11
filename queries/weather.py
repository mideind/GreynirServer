"""

    Reynir: Natural language processing for Icelandic

    Weather query response module

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


    This module handles weather-related queries.

"""

# TODO: Provide weather info for locations outside Iceland
# TODO: Add more info to description of current weather conditions?
# TODO: More detailed forecast?

import re
import logging
from datetime import datetime, timedelta

from queries import gen_answer
from geo import distance

from iceweather import observation_for_closest, observation_for_station, forecast_text


_WEATHER_QTYPE = "Weather"


# This module wants to handle parse trees for queries,
HANDLE_TREE = True

# The context-free grammar for the queries recognized by this plug-in module
GRAMMAR = """

Query →
    QWeather

QWeather → QWeatherQuery '?'?

QWeatherQuery →
    QWeatherCurrent
    | QWeatherForecast
    | QWeatherTemperature

QWeatherCurrent →
    "hvernig" "er" "veðrið" QWeatherNow?
    | "hvernig" "veður" "er" QWeatherNow?

QWeatherForecast →
    "hver" "er" "veðurspáin" QWeatherLocation? QWeatherNextDays?
    | "hver" "er" "spáin" QWeatherLocation? QWeatherNextDays?
    | "hvernig" "er" "veðurspáin" QWeatherLocation? QWeatherNextDays?
    | "hvernig" "er" "spáin" QWeatherLocation? QWeatherNextDays?
    | "hver" "er" "veðurspá" QWeatherLocation? QWeatherNextDays?
    | "hvernig" "er" "veðrið" QWeatherLocation? QWeatherNextDays
    | "hvernig" "verður" "veðrið" QWeatherLocation? QWeatherNextDays
    | "hvernig" "eru" "veðurhorfur" QWeatherLocation? QWeatherNextDays?
    | "hverjar" "eru" "veðurhorfur" QWeatherLocation? QWeatherNextDays?
    | "hvers" "konar" "veðri" "er" "spáð" QWeatherLocation? QWeatherNextDays?

QWeatherTemperature →
    "hvert" "er" "hitastigið" QWeatherNow?
    | "hversu" "heitt" "er" QWeatherNow?
    | "hvað" "er" "heitt" QWeatherNow?
    | "hvaða" "hitastig" "er" QWeatherNow
    | "hversu" "hlýtt" "er" QWeatherNow?
    | "hversu" "heitt" "er" QWeatherNow?
    | "hversu" "kalt" "er" QWeatherNow?
    | "hvað" "er" "kalt" QWeatherNow
    | "hvað" "er" "margra" "stiga" "hiti" QWeatherNow?

QWeatherNow →
    "úti"? "í" "dag" | "úti"? "núna" | "úti"

QWeatherNextDays →
    "næstu" "daga"
    | "næstu" "dagana"
    | "þessa" "viku" 
    | "út" "vikuna" 
    | "á" "næstunni" 
    | "á" "morgun"
    | "í" "fyrramálið"

QWeatherCountry →
    "á" "landinu" | "á" "Íslandi" | "hér" "á" "landi" | "á" "landsvísu"

QWeatherCapitalRegion →
    "á" "höfuðborgarsvæðinu" | "í" "Reykjavík"

QWeatherLocation →
    QWeatherCountry | QWeatherCapitalRegion


$score(35) QWeather

"""


_BFT_THRESHOLD = (0.3, 1.5, 3.4, 5.4, 7.9, 10.7, 13.8, 17.1, 20.7, 24.4, 28.4, 32.6)


def _wind_bft(ms):
    """ Convert wind from metres per second to Beaufort scale """
    if ms is None:
        return None
    for bft in range(len(_BFT_THRESHOLD)):
        if ms < _BFT_THRESHOLD[bft]:
            return bft
    return len(_BFT_THRESHOLD)


# From https://www.vedur.is/vedur/frodleikur/greinar/nr/1098
_BFT_ICEDESC = {
    0: "logn",
    1: "andvari",
    2: "kul",
    3: "gola",
    4: "stinningsgola",
    5: "kaldi",
    6: "stinningskaldi",
    7: "allhvasst",
    8: "hvassviðri",
    9: "stormur",
    10: "rok",
    11: "ofsaveður",
    12: "fárviðri",
}


def _wind_descr(wind_ms):
    """ Icelandic-language description of wind conditions given meters 
        per second. Uses Beaufort scale lookup.
        See https://www.vedur.is/vedur/frodleikur/greinar/nr/1098
    """
    return _BFT_ICEDESC.get(_wind_bft(wind_ms))


_RVK_COORDS = (64.133097, -21.898145)


def _near_capital_region(loc):
    """ Returns true if location coordinates are within 30 km of central Rvk """
    return distance(loc, _RVK_COORDS) < 30


_ICELAND_COORDS = (64.9957538607, -18.5739616708)


def _in_iceland(loc):
    """ Check if coordinates are within or very close to Iceland """
    return distance(loc, _ICELAND_COORDS) < 300


def _round_to_nearest_hour(t):
    """ Round datetime to nearest hour """
    return t.replace(second=0, microsecond=0, minute=0, hour=t.hour) + timedelta(
        hours=t.minute // 30
    )


_RVK_STATION_ID = 1


def _curr_observations(query):
    """ Fetch latest weather observation data from nearest weather station """
    loc = query.location

    try:
        res = (
            observation_for_closest(loc[0], loc[1])
            if loc
            else observation_for_station(_RVK_STATION_ID)  # Default to Reykjavík
        )
    except Exception as e:
        logging.warning("Failed to fetch weather info: {0}".format(str(e)))
        return None

    # Verify that response from server is sane
    if not res or "results" not in res or not len(res["results"]):
        return None

    return res["results"][0]


_API_ERRMSG = "Ekki tókst að sækja veðurupplýsingar."


def get_currtemp_answer(query, result):
    """ Handle queries concerning outside temperature """
    res = _curr_observations(query)
    if not res:
        return gen_answer(_API_ERRMSG)

    temp = int(float(res["T"]))  # Round to nearest whole number
    temp_type = "hiti" if temp >= 0 else "frost"

    voice = "Úti er {0} stiga {1}".format(abs(temp), temp_type)
    answer = "{0}°".format(temp)
    response = dict(answer=answer)

    return response, answer, voice


def get_currweather_answer(query, result):
    """ Handle queries concerning current weather conditions """
    res = _curr_observations(query)
    if not res:
        return gen_answer(_API_ERRMSG)

    temp = int(float(res["T"]))  # Round to nearest whole number
    desc = res["W"].lower()
    windsp = float(res["F"])

    wind_desc = _wind_descr(windsp)
    temp_type = "hiti" if temp >= 0 else "frost"
    mdesc = ", " + desc + "," if desc else ""

    voice = "Úti er {0} stiga {1}{2} og {3}".format(
        abs(temp), temp_type, mdesc, wind_desc
    )

    answer = "{0}°{1} og vindhraði {2} m/s".format(temp, mdesc, windsp)

    response = dict(answer=answer)

    return response, answer, voice


# Abbreviations to be expanded in natural language weather
# descriptions from the Icelandic Met Office.
_DESCR_ABBR = {
    "m/s": "metrar á sekúndu",
    "NV-": "norðvestan",
    "NA-": "norðaustan",
    "SV-": "suðvestan",
    "SA-": "suðaustan",
    "S-": "sunnan",
    "V-": "vestan",
    "N-": "norðan",
    "A-": "austan",
}


def _descr4voice(descr):
    """ Prepare natural language weather description for voice synthesizer 
        by rewriting/expanding abbreviations, etc. """

    # E.g. "8-13" becomes "8 til 13"
    d = re.sub(r"(\d+)\-(\d+)", r"\1 til \2", descr)

    for k, v in _DESCR_ABBR.items():
        d = d.replace(k, v)

    return d


_COUNTRY_FC_ID = 2
_CAPITAL_FC_ID = 3


def get_forecast_answer(query, result):
    """ Handle weather forecast queries """
    loc = query.location
    txt_id = _CAPITAL_FC_ID if (loc and _near_capital_region(loc)) else _COUNTRY_FC_ID

    # Did the query mention a specific scope?
    if "location" in result:
        if result.location == "capital":
            txt_id = _CAPITAL_FC_ID
        elif result.location == "general":
            txt_id = _COUNTRY_FC_ID

    try:
        res = forecast_text(txt_id)
    except Exception as e:
        logging.warning("Failed to fetch weather text: {0}".format(str(e)))
        res = None

    if (
        not res
        or not "results" in res
        or not len(res["results"])
        or "content" not in res["results"][0]
    ):
        return gen_answer(_API_ERRMSG)

    answer = res["results"][0]["content"]
    response = dict(answer=answer)
    voice = _descr4voice(answer)

    return response, answer, voice


def QWeather(node, params, result):
    result.qtype = _WEATHER_QTYPE


def QWeatherCapitalRegion(node, params, result):
    result["subject"] = "capital"


def QWeatherCountry(node, params, result):
    result["subject"] = "general"


def QWeatherCurrent(node, params, result):
    result.qkey = "CurrentWeather"


def QWeatherForecast(node, params, result):
    result.qkey = "WeatherForecast"


def QWeatherTemperature(node, params, result):
    result.qkey = "CurrentTemperature"


_HANDLERS = {
    "CurrentTemperature": get_currtemp_answer,
    "CurrentWeather": get_currweather_answer,
    "WeatherForecast": get_forecast_answer,
}


def sentence(state, result):
    """ Called when sentence processing is complete """
    q = state["query"]
    if "qtype" in result and "qkey" in result:
        # Successfully matched a query type
        q.set_qtype(result.qtype)
        q.set_key(result.qkey)

        if q.location and not _in_iceland(q.location):
            return gen_answer("Ég bý ekki yfir upplýsingum um veður utan Íslands")

        handler_func = _HANDLERS[result.qkey]

        try:
            r = handler_func(q, result)
            if r:
                q.set_answer(*r)
        except Exception as e:
            logging.warning("Exception while processing weather query: {0}".format(str(e)))
            q.set_error("E_EXCEPTION: {0}".format(e))
    else:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
