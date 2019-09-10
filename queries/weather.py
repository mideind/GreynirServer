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
# TODO: Timezones

import re
from datetime import datetime, timedelta
import logging

from pprint import pprint

from iceweather import observation_for_closest, observation_for_station

from queries import gen_answer


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
    | "hvernig" "veður" "er" QWeatherNow

QWeatherForecast →
    "hver" "er" "veðurspáin" QWeatherNextDays?
    | "hvernig" "er" "veðrið" QWeatherNextDays
    | "hvernig" "verður" "veðrið" QWeatherNextDays
    | "hvernig" "eru" "veðurhorfur" QWeatherHere? QWeatherNextDays?
    | "hverjar" "eru" "veðurhorfur" QWeatherHere? QWeatherNextDays?

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

QWeatherHere →
    "á" "landinu" | "á" "Íslandi" | "hér" "á" "landi"

QWeatherNextDays →
    "næstu" "daga" | "þessa" "viku" | "út" "vikuna" | "á" "næstunni"


# Hver er veðurspáin
# Hver er veðurspáin fyrir morgundaginn
# Hver er veðurspáin á morgun
# Hvernig verður veðrið á morgun
# Hvernig veður er á morgun
# Hversu hlýtt/heitt er úti
# Hvert er hitastigið úti



$score(535) QWeather

"""


def _descr4voice(descr):
    """ Prepare description for voice synthesizer by rewriting abbreviations etc. """
    d = descr.replace("m/s", "metrar á sekúndu")
    d = re.sub(r"(\d+)\-(\d+)", r"\1 til \2", voice_answer)
    # TODO: More processing needed, "NV-lands" etc.
    return d


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
    """ Icelandic-language description of wind conditions given meters per second.
        See https://www.vedur.is/vedur/frodleikur/greinar/nr/1098
    """
    bft = _wind_bft(wind_ms)
    return _BFT_ICEDESC.get(bft)


def _near_capital_region(lat, lon):
    return False


def _round_to_nearest_hour(t):
    return t.replace(second=0, microsecond=0, minute=0, hour=t.hour) + timedelta(
        hours=t.minute // 30
    )


def _curr_observations(query):
    loc = query.location

    try:
        res = (
            observation_for_closest(loc[0], loc[1])
            if loc
            else observation_for_station(1)  # Default to Reykjavík
        )
    except Exception as e:
        logging.warning("Failed to fetch weather info: {0}".format(str(e)))
        return None

    # Verify that response from server is sane
    if not res or "results" not in res or not len(res["results"]):
        return None

    return res["results"][0]


_API_ERRMSG = "Ekki tókst að sækja veðurupplýsingar."


def get_currtemp_answer(query):
    res = _curr_observations(query)
    if not res:
        return gen_answer(_API_ERRMSG)

    temp = int(float(res["T"]))  # Round to nearest whole number
    if temp < 0:
        voice = "Úti er {0} stiga frost".format(temp * -1)
    else:
        voice = "Úti er {0} stiga hiti".format(temp)
    answer = "{0}°".format(temp)
    response = dict(answer=answer)

    return response, answer, voice


def get_currweather_answer(query):
    res = _curr_observations(query)
    if not res:
        return gen_answer(_API_ERRMSG)

    print(res)

    temp = int(float(res["T"]))
    desc = res["W"].lower()
    windsp = float(res["F"])

    wind_desc = _wind_descr(windsp)
    temp_type = "hiti" if temp >= 0 else "frost"
    mdesc = ", " + desc + "," if desc else ""

    voice = "Úti er {0} stiga {1},{2} og {3}".format(
        abs(temp), temp_type, mdesc, wind_desc
    )

    answer = "{0}°{1}, vindhraði {2} m/s".format(temp, mdesc, windsp)
    
    response = dict(answer=answer)

    return response, answer, voice


def get_forecast(query):
    fc = res["results"][0]["forecast"]

    # Look up by ftime key, fmt. "2019-09-10 10:00:00"
    currhour = _round_to_nearest_hour(datetime.now())
    ftime = currhour.strftime("%Y-%m-%d %H:%M:%S")

    now_info = [x for x in fc if x.get("ftime") == ftime]
    if not now_info or "T" not in now_info[0]:
        return gen_answer(errmsg)

    now_info = now_info[0]
    temp = now_info["T"].replace(".", ",")
    desc = now_info["W"].lower()

    voice = "Úti er {0} stiga hiti og {1}".format(temp, desc)
    answer = "{0}°".format(temp)
    response = dict(answer=answer)

    return response, answer, voice


def QWeather(node, params, result):
    pass


def QWeatherCurrent(node, params, result):
    result.qtype = "Weather"
    result.qkey = "CurrentWeather"


def QWeatherForecast(node, params, result):
    result.qtype = "Weather"
    result.qkey = "WeatherForecast"


def QWeatherTemperature(node, params, result):
    result.qtype = "Weather"
    result.qkey = "CurrentTemperature"


_HANDLERS = {
    "CurrentWeather": get_currweather_answer,
    "WeatherForecast": get_forecast,
    "CurrentTemperature": get_currtemp_answer,
}


def _handle_weather_query(q, result):
    resp = _query_weather_api()

    if not resp or "results" not in resp or len(resp["results"]) < 1:
        return None

    r = resp["results"][0]
    answer = r["content"]
    response = dict(answer=answer)

    return response, answer, voice_answer


def sentence(state, result):
    """ Called when sentence processing is complete """
    q = state["query"]
    if "qtype" in result and "qkey" in result:
        # Successfully matched a query type
        q.set_qtype(result.qtype)
        q.set_key(result.qkey)

        handler_func = _HANDLERS.get(result.qkey)

        try:
            r = handler_func(q)
            if r:
                (response, answer, voice_answer) = r
                q.set_answer(response, answer, voice_answer)
        except Exception as e:
            raise
            q.set_error("E_EXCEPTION: {0}".format(e))
    else:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
