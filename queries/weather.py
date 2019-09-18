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

# TODO: Natural language weather forecasts for different parts of the country (N-land, etc.)
# TODO: Provide weather info for locations outside Iceland
# TODO: Add more info to description of current weather conditions?
# TODO: More detailed forecast?

import re
import logging
from datetime import datetime, timedelta

from queries import gen_answer
from geo import distance, isocode_for_country_name, ICE_PLACENAME_BLACKLIST
from iceaddr import placename_lookup

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
    "hvernig" "er" "veðrið" QWeatherAnyLoc? QWeatherNow?
    | "hvernig" "veður" "er" QWeatherAnyLoc? QWeatherNow?

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
    "hvert" "er" "hitastigið" QWeatherAnyLoc? QWeatherNow?
    | "hversu" "heitt" "er" QWeatherAnyLoc? QWeatherNow?
    | "hvað" "er" "heitt" QWeatherAnyLoc? QWeatherNow?
    | "hvaða" "hitastig" "er" QWeatherAnyLoc? QWeatherNow
    | "hversu" "hlýtt" "er" QWeatherAnyLoc? QWeatherNow?
    | "hversu" "heitt" "er" QWeatherAnyLoc? QWeatherNow?
    | "hversu" "kalt" "er" QWeatherAnyLoc? QWeatherNow?
    | "hvað" "er" "kalt" QWeatherAnyLoc? QWeatherNow
    | "hvað" "er" "hlýtt" QWeatherAnyLoc? QWeatherNow
    | "hvað" "er" "margra" "stiga" "hiti" QWeatherAnyLoc? QWeatherNow?

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
    "á" "landinu" | "á" "íslandi" | "hér" "á" "landi" | "á" "landsvísu"

QWeatherCapitalRegion →
    "á" "höfuðborgarsvæðinu" | "í" "reykjavík"

QWeatherAnyLoc →
    QWeatherCountry | QWeatherCapitalRegion | QWeatherOpenLoc

QWeatherOpenLoc →
    fs_þgf Nl_þgf

QWeatherLocation →
    QWeatherCountry | QWeatherCapitalRegion


$score(35) QWeather

"""


_BFT_THRESHOLD = (0.3, 1.5, 3.4, 5.4, 7.9, 10.7, 13.8, 17.1, 20.7, 24.4, 28.4, 32.6)


def _wind_bft(ms):
    """ Convert wind from metres per second to Beaufort scale """
    if ms is None:
        return None
    for ix, bft in enumerate(_BFT_THRESHOLD):
        if ms < bft:
            return ix
    return ix + 1


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


def _curr_observations(query, result):
    """ Fetch latest weather observation data from weather station closest
        to the location associated with the query (i.e. either user location 
        coordinates or a specific placename) """
    loc = query.location

    # User asked about a specific location
    # Try to find a matching Icelandic placename
    if "location" in result and result.location != "Ísland":

        # Some strings should never be interpreted as Icelandic placenames
        if result.location in ICE_PLACENAME_BLACKLIST:
            return None

        # Unfortunately, many foreign country names are also Icelandic
        # placenames, so we automatically exclude country names.
        cc = isocode_for_country_name(result.location)
        if cc:
            return None

        info = placename_lookup(result.location)
        if info:
            i = info[0]
            loc = (i.get("lat_wgs84"), i.get("long_wgs84"))
        else:
            return None

    # Talk to weather API
    try:
        if loc:
            res = observation_for_closest(loc[0], loc[1])
        else:
            res = observation_for_station(_RVK_STATION_ID)  # Default to Reykjavík
            result.subject = "Í Reykjavík"
    except Exception as e:
        logging.warning("Failed to fetch weather info: {0}".format(str(e)))
        return None

    # Verify that response from server is sane
    if not res or "results" not in res or not len(res["results"]):
        return None

    return res["results"][0]


_API_ERRMSG = "Ekki tókst að sækja veðurupplýsingar."


def get_currtemp_answer(query, result):
    """ Handle queries concerning temperature """
    res = _curr_observations(query, result)
    if not res:
        return gen_answer(_API_ERRMSG)

    temp = int(round(float(res["T"])))  # Round to nearest whole number
    temp_type = "hiti" if temp >= 0 else "frost"

    locdesc = result.get("subject") or "Úti"

    voice = "{0} er {1} stiga {2}".format(locdesc.capitalize(), abs(temp), temp_type)
    answer = "{0}°".format(temp)
    response = dict(answer=answer)

    return response, answer, voice


def get_currweather_answer(query, result):
    """ Handle queries concerning current weather conditions """
    res = _curr_observations(query, result)
    if not res:
        return gen_answer(_API_ERRMSG)

    temp = int(round(float(res["T"])))  # Round to nearest whole number
    desc = res["W"].lower()
    windsp = float(res["F"])

    wind_desc = _wind_descr(windsp)
    temp_type = "hiti" if temp >= 0 else "frost"
    mdesc = ", " + desc + "," if desc else ""

    locdesc = result.get("subject") or "Úti"

    voice = "{0} er {1} stiga {2}{3} og {4}".format(
        locdesc.capitalize(), abs(temp), temp_type, mdesc, wind_desc
    )

    answer = "{0}°{1} og {2} ({3} m/s)".format(temp, mdesc, wind_desc, windsp)

    response = dict(answer=answer)

    return response, answer, voice


# Abbreviations to expand in natural language weather
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
    """ Prepare natural language weather description for speech synthesizer 
        by rewriting/expanding abbreviations, etc. """

    # E.g. "8-13" becomes "8 til 13"
    d = re.sub(r"(\d+)\-(\d+)", r"\1 til \2", descr)

    # Fix faulty formatting in Met text where no space follows period.
    # This formatting error confuses speech synthesis.
    d = re.sub(r"(\S+)\.(\S+)", r"\1. \2", d)

    # Abbreviations
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
        logging.warning("Failed to fetch weather text: {0}".format(e))
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
    result["location"] = "capital"


def QWeatherCountry(node, params, result):
    result["location"] = "general"


def QWeatherOpenLoc(node, params, result):
    """ Store preposition and placename to use in voice
        description, e.g. "á Raufarhöfn" """
    result["subject"] = result._node.contained_text()


def Nl(node, params, result):
    """ Noun phrase containing name of specific location """
    result["location"] = result._nominative


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
            return gen_answer("Ég þekki ekki til veðurs utan Íslands")

        handler_func = _HANDLERS[result.qkey]

        try:
            r = handler_func(q, result)
            if r:
                q.set_answer(*r)
        except Exception as e:
            logging.warning("Exception while processing weather query: {0}".format(e))
            q.set_error("E_EXCEPTION: {0}".format(e))
            raise
    else:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
