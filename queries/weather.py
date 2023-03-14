"""

    Greynir: Natural language processing for Icelandic

    Weather query response module

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


    This module handles weather-related queries.

"""

# TODO: Fall back on other source of weather data if iceweather fails
# TODO: Provide weather info for locations outside Iceland
# TODO: GSSML processing of forecast text
# TODO: Natural language weather forecasts for different parts of the country (N-land, etc.)
# TODO: Add more info to description of current weather conditions?
# TODO: More detailed forecast, time specific? E.g. "hvernig verður veðrið klukkan þrjú?"
# TODO: "Mun rigna í dag?" "Verður mikið rok í dag?" "Verður kalt í kvöld?" "Þarf ég regnhlíf?"
# TODO: "Hversu mikið rok er úti?" "Hversu mikill vindur er úti?" "Hvað er mikill vindur núna?"
# TODO: "Verður sól á morgun?" "Verður sól í dag?" - sólskin - sést til sólar
# TODO: "Hvernig er færðin?"
# TODO: "Hversu hvasst er úti?"
# TODO: "Hvað er hitastigið á egilsstöðum?" "Hvað er mikill hiti úti?"
# TODO: "Hvar er heitast á landinu?" "Hvar er kaldast á landinu?"
# TODO: "Er gott veður úti?"
# TODO: "Hvað er mikið frost?" "Hversu mikið frost er úti?"
# TODO: "Verður snjór á morgun?"
# TODO: "Hvað er mikill hiti úti?"
# TODO: "Hvernig er veðurspáin fyrir garðabæ?"
# TODO: "Hvernig er færðin"
# TODO: Er rigning úti? Er sól úti? Er sól á Húsavík? Er rigning í Reykjavík?

from __future__ import annotations

from typing import Dict, Mapping, Optional, Union

import os
import re
import logging
import random
from datetime import timedelta, datetime

from queries import Query, QueryStateDict
from utility import cap_first
from queries.util import (
    JsonResponse,
    AnswerTuple,
    gen_answer,
    query_json_api,
    read_grammar_file,
)
from tree import Result, Node
from geo import in_iceland, RVK_COORDS, near_capital_region, ICE_PLACENAME_BLACKLIST
from iceaddr import placename_lookup  # type: ignore
from iceweather import observation_for_closest, observation_for_station, forecast_text  # type: ignore

from speech.trans import gssml

_WEATHER_QTYPE = "Weather"


# This module wants to handle parse trees for queries
HANDLE_TREE = True


# Lemmas of keywords that could indicate that the user is trying to use this module
TOPIC_LEMMAS = [
    "veður",
    "veðurspá",
    "spá",
    "rigning",
    "vindur",
    "regn",
    "rok",
    "stormur",
    "fárviðri",
    "ofsaveður",
    "logn",
    "lygn",
    "blautur",
    "bleyta",
    "rigna",
    "regnhlíf",
    "votur",
    "kaldur",
    # "heitur", # Clashes with "hvað heitir X" etc.
    "hiti",
    "kuldi",
    "veðurhorfur",
    "hitastig",
    "vindstig",
    "væta",
    "úrkoma",
    "úrkomumikill",
    "úrkomulítill",
]


def help_text(lemma: str) -> str:
    """Help text to return when query processor is unable to parse a query but
    one of the above lemmas is found in it"""
    return "Ég get svarað ef þú spyrð til dæmis: {0}?".format(
        random.choice(
            (
                "Hvernig er veðrið",
                "Hvernig er veðurspáin",
                "Hvernig er veðrið á Vopnafirði",
                "Hvernig eru veðurhorfurnar",
                "Hversu heitt er í Borgarfirði",
                "Hvernig veður er á Siglufirði",
                "Hversu kalt er á Akureyri",
            )
        )
    )


# The grammar nonterminals this module wants to handle
QUERY_NONTERMINALS = {"QWeather"}

# The context-free grammar for the queries recognized by this module
GRAMMAR = read_grammar_file("weather")


# The OpenWeatherMap API key (you must obtain your
# own key if you want to use this code)
_owm_api_key = ""
_OWM_KEY_PATH = os.path.join(
    os.path.dirname(__file__), "..", "resources", "OpenWeatherMapKey.txt"
)


def _get_OWM_API_key() -> str:
    """Read OpenWeatherMap API key from file"""
    global _owm_api_key
    if not _owm_api_key:
        try:
            # You need to obtain your own key and put it in
            # _OWM_API_KEY if you want to use this code.
            with open(_OWM_KEY_PATH) as f:
                _owm_api_key = f.read().rstrip()
        except FileNotFoundError:
            logging.warning(
                "Could not read OpenWeatherMap API key from {0}".format(_OWM_KEY_PATH)
            )
            _owm_api_key = ""
    return _owm_api_key


def _postprocess_owm_data(d: JsonResponse) -> JsonResponse:
    """Restructure data from OWM API so it matches that provided by
    the iceweather module."""
    if not d:
        return d
    return d


_OWM_API_URL_BYNAME = (
    "https://api.openweathermap.org/data/2.5/weather?q={0},{1}&appid={2}&units=metric"
)


def _query_owm_by_name(city: str, country_code: Optional[str] = None) -> JsonResponse:
    d = query_json_api(
        _OWM_API_URL_BYNAME.format(city, country_code or "", _get_OWM_API_key())
    )
    return _postprocess_owm_data(d)


_OWM_API_URL_BYLOC = (
    "https://api.openweathermap.org/data/2.5/weather?"
    "lat={0}&lon={1}&appid={2}&units=metric"
)


def _query_owm_by_coords(lat: float, lon: float) -> JsonResponse:
    d = query_json_api(_OWM_API_URL_BYLOC.format(lat, lon, _get_OWM_API_key()))
    return _postprocess_owm_data(d)


_BFT_THRESHOLD = (0.3, 1.5, 3.4, 5.4, 7.9, 10.7, 13.8, 17.1, 20.7, 24.4, 28.4, 32.6)


def _wind_bft(ms: Optional[float]) -> int:
    """Convert wind from metres per second to Beaufort scale"""
    if ms is None:
        return 0
    ix = 0
    for ix, bft in enumerate(_BFT_THRESHOLD):
        if ms < bft:
            return ix
    return ix + 1


# From https://www.vedur.is/vedur/frodleikur/greinar/nr/1098
_BFT_ICEDESC: Mapping[int, str] = {
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


def _wind_descr(wind_ms: float) -> Optional[str]:
    """Icelandic-language description of wind conditions given metres
    per second. Uses Beaufort scale lookup.
    See https://www.vedur.is/vedur/frodleikur/greinar/nr/1098
    """
    return _BFT_ICEDESC.get(_wind_bft(wind_ms))


def _round_to_nearest_hour(t: datetime) -> datetime:
    """Round datetime to nearest hour"""
    return t.replace(second=0, microsecond=0, minute=0, hour=t.hour) + timedelta(
        hours=t.minute // 30
    )


_RVK_STATION_ID = 1


def _curr_observations(query: Query, result: Result):
    """Fetch latest weather observation data from weather station closest
    to the location associated with the query (i.e. either user location
    coordinates or a specific placename)"""
    loc = query.location
    res = None

    # User asked about a specific location
    # Try to find a matching Icelandic placename
    if (
        "location" in result
        and result.location != "Ísland"
        and result.location != "general"
    ):
        if result.location == "capital":
            loc = RVK_COORDS
            result.subject = "Í Reykjavík"
        else:
            # First, check if it could be a location in Iceland
            if result.location not in ICE_PLACENAME_BLACKLIST:
                info = placename_lookup(result.location)
                if info:
                    i = info[0]
                    loc = (i.get("lat_wgs84"), i.get("long_wgs84"))
            # OK, could be a location abroad
            if not loc:
                # TODO: Finish this!
                return None
                # If it's a country name, get coordinates for capital city
                # and look that up
                # If not a country name, maybe a foreign city. Look up city
                # name and get coordinates

            # if loc within iceland:
            # talk to iceweather module
            #  else
            # fetch data from openweathermap api

    # Talk to weather API
    try:
        if loc and loc[0] and loc[1]:
            res = observation_for_closest(loc[0], loc[1])
            if isinstance(res, tuple):
                # !!! FIXME: The type annotations here should be made more accurate
                res = res[0]  # type: ignore
        else:
            res = observation_for_station(_RVK_STATION_ID)  # Default to Reykjavík
            result.subject = "Í Reykjavík"
    except Exception as e:
        logging.warning(f"Failed to fetch weather info: {e}")
        return None

    # Verify that response from server is sane
    if (
        not res
        or "results" not in res
        or not len(res["results"])
        or res["results"][0].get("err")
    ):
        return None

    return res["results"][0]


_API_ERRMSG = "Ekki tókst að sækja veðurupplýsingar."


def get_currweather_answer(query: Query, result: Result) -> AnswerTuple:
    """Handle queries concerning current weather conditions"""
    res = _curr_observations(query, result)
    if not res:
        return gen_answer(_API_ERRMSG)

    try:
        # Round to nearest whole number
        temp = int(round(float(res["T"].replace(",", "."))))
        desc: str = res["W"].lower()
        windsp = float(res["F"].replace(",", "."))
    except Exception as e:
        logging.warning(f"Exception parsing weather API result: {e}")
        return gen_answer(_API_ERRMSG)

    wind_desc = _wind_descr(windsp)
    wind_ms_str = str(windsp).rstrip("0").rstrip(".")
    temp_type = "hiti" if temp >= 0 else "frost"
    mdesc = ", " + desc + "," if desc else ""

    locdesc = result.get("subject") or "Úti"

    # Meters per second string for voice. Say nothing if "logn".
    msec = int(wind_ms_str)
    voice_ms = ""
    if wind_ms_str != "0":
        msec_numword = gssml(msec, type="number", gender="kk", case="nf")
        meters = "metrar" if msec > 1 else "metri"
        voice_ms = f", {msec_numword} {meters} á sekúndu"

    temp_numw = gssml(abs(temp), type="number", gender="kk", case="ef")

    # Format voice string
    voice = f"{locdesc.capitalize()} er {temp_numw} stiga {temp_type}{mdesc} og {wind_desc}{voice_ms}"

    # Text answer
    answer = f"{temp} °C{mdesc} og {wind_desc} ({wind_ms_str} m/s)"

    response = dict(answer=answer)

    return response, answer, voice


def gpt_query(q: Query, query: str, time: str, location: str) -> Dict[str, Union[str, int, float]]:
    """Return a string response for a GPT query"""
    weather: Dict[str, Union[str, int, float]] = dict(temperature=random.randint(-10, 30), wind=random.randint(0, 20))
    return weather


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


def _descr4voice(descr: str) -> str:
    """Prepare natural language weather description for speech synthesizer
    by rewriting/expanding abbreviations, etc."""

    # E.g. "8-13" becomes "8 til 13"
    d = re.sub(r"(\d+)\-(\d+)", r"\1 til \2", descr)

    # Fix faulty formatting in Met text where no space follows period.
    # This formatting error confuses speech synthesis.
    d = re.sub(r"(\S+)\.(\S+)", r"\1. \2", d)

    # Expand abbreviations
    for k, v in _DESCR_ABBR.items():
        d = d.replace(k, v)

    return d


_COUNTRY_FC_ID = 2
_CAPITAL_FC_ID = 3


def get_forecast_answer(query: Query, result: Result) -> AnswerTuple:
    """Handle weather forecast queries"""
    loc = query.location
    txt_id = _CAPITAL_FC_ID if (loc and near_capital_region(loc)) else _COUNTRY_FC_ID

    # Did the query mention a specific scope?
    if "location" in result:
        if result.location == "capital":
            txt_id = _CAPITAL_FC_ID
        elif result.location == "general":
            txt_id = _COUNTRY_FC_ID

    try:
        res = forecast_text(txt_id)
    except Exception as e:
        logging.warning(f"Failed to fetch weather text: {e}")
        res = None

    if (
        not res
        or "results" not in res
        or not len(res["results"])
        or "content" not in res["results"][0]
    ):
        return gen_answer(_API_ERRMSG)

    answer: str = res["results"][0]["content"]
    response = dict(answer=answer)
    voice = _descr4voice(answer)

    return response, answer, voice


def get_umbrella_answer(query: Query, result: Result) -> Optional[AnswerTuple]:
    """Handle a query concerning whether an umbrella is needed
    for current weather conditions."""

    # if rain and high wind: no, not gonna work buddy
    # if no rain: no, it's not raining or likely to rain
    # else: yeah, take the umbrella

    return None


def QWeather(node: Node, params: QueryStateDict, result: Result) -> None:
    result.qtype = _WEATHER_QTYPE


def QWeatherCapitalRegion(node: Node, params: QueryStateDict, result: Result) -> None:
    result["location"] = "capital"


def QWeatherCountry(node: Node, params: QueryStateDict, result: Result) -> None:
    result["location"] = "general"


def QWeatherOpenLoc(node: Node, params: QueryStateDict, result: Result) -> None:
    """Store preposition and placename to use in voice
    description, e.g. "Á Raufarhöfn" """
    result["subject"] = result._node.contained_text().title()


def Nl(node: Node, params: QueryStateDict, result: Result) -> None:
    """Noun phrase containing name of specific location"""
    result["location"] = cap_first(result._nominative)


def EfLiður(node: Node, params: QueryStateDict, result: Result) -> None:
    """Don't change the case of possessive clauses"""
    result._nominative = result._text


def FsMeðFallstjórn(node: Node, params: QueryStateDict, result: Result) -> None:
    """Don't change the case of prepositional clauses"""
    result._nominative = result._text


def QWeatherCurrent(node: Node, params: QueryStateDict, result: Result) -> None:
    result.qkey = "CurrentWeather"


def QWeatherWind(node: Node, params: QueryStateDict, result: Result) -> None:
    result.qkey = "CurrentWeather"


def QWeatherForecast(node: Node, params: QueryStateDict, result: Result) -> None:
    result.qkey = "WeatherForecast"


def QWeatherTemperature(node: Node, params: QueryStateDict, result: Result) -> None:
    result.qkey = "CurrentWeather"


def QWeatherUmbrella(node: Node, params: QueryStateDict, result: Result) -> None:
    result.qkey = "Umbrella"


_HANDLERS = {
    "CurrentWeather": get_currweather_answer,
    "WeatherForecast": get_forecast_answer,
    "Umbrella": get_umbrella_answer,
}


def sentence(state: QueryStateDict, result: Result) -> None:
    """Called when sentence processing is complete"""
    q: Query = state["query"]
    if "qtype" in result and "qkey" in result:
        # Successfully matched a query type
        q.set_qtype(result.qtype)
        q.set_key(result.qkey)

        # Asking for a location outside Iceland
        if q.location and not in_iceland(q.location):
            q.set_answer(*gen_answer("Ég þekki ekki til veðurs utan Íslands"))
            return

        handler_func = _HANDLERS[result.qkey]

        try:
            r = handler_func(q, result)
            if r:
                q.set_answer(*r)
        except Exception as e:
            logging.warning(f"Exception while processing weather query: {e}")
            q.set_error(f"E_EXCEPTION: {e}")
            raise
    else:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
