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


import re
from iceweather import observation_for_closest


_RVK_COORDS = (64.1275, -21.9028)


# This module wants to handle parse trees for queries,
HANDLE_TREE = True

# The context-free grammar for the queries recognized by this plug-in module
GRAMMAR = """

Query →
    QWeather

QWeather → QWeatherQuery '?'?

QWeatherQuery →
    "heitt" "úti"
    | QWeatherCurrent
    | QWeatherForecast
    | QWeatherTemperature

QWeatherCurrent →
    "hvernig" "er" "veðrið" QWeatherCurrentAddition?
    | "hvernig" "veður" "er" QWeatherCurrentAddition

QWeatherForecast →
    "hver" "er" "veðurspáin" QWeatherNextDays?
    | "hvernig" "er" "veðrið" QWeatherNextDays
    | "hvernig" "verður" "veðrið" QWeatherNextDays

QWeatherTemperature →
    "hvert" "er" "hitastigið" QWeatherNow?
    | "hversu" "heitt" "er" QWeatherNow?
    | "hvað" "er" "heitt" QWeatherNow?
    | "hvaða" "hitastig" "er" QWeatherNow
    | "hversu" "hlýtt" "er" QWeatherNow?
    | "hversu" "heitt" "er" QWeatherNow?

QWeatherNow →
    "úti"? "í" "dag" | "úti"? "núna" | "úti"

QWeatherNextDays →
    "næstu" "daga" | "þessa" "viku" | "út" "vikuna" | "á næstunni"


# Hver er veðurspáin
# Hver er veðurspáin fyrir morgundaginn
# Hver er veðurspáin á morgun
# Hvernig verður veðrið á morgun
# Hvernig veður er á morgun
# Hversu hlýtt/heitt er úti
# Hvert er hitastigið úti



$score(535) QWeather

"""


def QWeather(node, params, result):
    """ Weather query """
    print("QWEATHER!!!!!")
    pass


def QWeatherCurrent(node, params, result):
    result.qtype = "Weather"
    result.qkey = "CurrentWeather"
    result.handler_func = get_currweather_answer


def QWeatherForecast(node, params, result):
    result.qtype = "Weather"
    result.qkey = "WeatherForecast"
    result.handler_func = get_forecast


def QWeatherTemperature(node, params, result):
    result.qtype = "Weather"
    result.qkey = "CurrentTemperature"
    result.handler_func = get_currtemp_answer


def _descr4voice(descr):
    """ Prepare description for voice synthesizer by rewriting abbreviations etc. """
    d = descr.replace("m/s", "metrar á sekúndu")
    d = re.sub(r"(\d+)\-(\d+)", r"\1 til \2", voice_answer)
    # TODO: More processing needed, "NV-lands" etc.
    return d


def _near_capital_region(lat, lon):
    return False


def get_currtemp_answer(query):
    loc = query.location or _RVK_COORDS

    res = observation_for_closest(loc[0], loc[1])

    from pprint import pprint

    pprint(res)

    return "Hello", "Hello", "Hello"


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
    if "qtype" in result:
        # Successfully matched a query type
        q.set_qtype(result.qtype)
        q.set_key(result.qkey)

        handler_func = result.handler_func

        try:
            r = handler_func(q)
            if r:
                (response, answer, voice_answer) = r
                q.set_answer(response, answer, voice_answer)
        except Exception as e:
            q.set_error("E_EXCEPTION: {0}".format(e))
    else:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
