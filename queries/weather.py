"""

    Greynir: Natural language processing for Icelandic

    Weather query response module

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


    This module handles weather-related queries.

"""

# TODO: Natural language weather forecasts for different parts of the country (N-land, etc.)
# TODO: Provide weather info for locations outside Iceland
# TODO: Add more info to description of current weather conditions?
# TODO: More detailed forecast, time specific? E.g. "hvernig verður veðrið klukkan þrjú?"
# TODO: "Mun rigna í dag?" "Verður mikið rok í dag?" "Verður kalt í kvöld?" "Þarf ég regnhlíf?"
# TODO: "Hversu mikið rok er úti?" "Hversu mikill vindur er úti?" "Hvað er mikill vindur núna?"
# TODO: "Verður sól á morgun?" "Verður sól í dag?" - sólskin - sést til sólar
# TODO: "Hvernig er færðin?"
# TODO: "Hversu hvasst er úti?"
# TODO: "HVAÐ er hitastigið á egilsstöðum?" "Hvað er mikill hiti úti?"
# TODO: "Hvar er heitast á landinu?"
# TODO: "Er gott veður úti?"
# TODO: "Hvað er mikið frost?" "Hversu mikið frost er úti?"
# TODO: "Verður snjór á morgun?"
# TODO: "Hvað er mikill hiti úti?"
# TODO: "Hvernig er veðurspáin fyrir garðabæ?"
# TODO: "Hvernig er færðin"
# TODO: "Hvernig eru loftgæðin [í Reykjavík] etc."

from typing import Optional

import os
import re
import logging
import random
from datetime import timedelta, datetime

from query import Query
from queries import gen_answer, query_json_api, cap_first, sing_or_plur
from geo import distance, in_iceland, ICE_PLACENAME_BLACKLIST
from iceaddr import placename_lookup  # type: ignore
from iceweather import observation_for_closest, observation_for_station, forecast_text  # type: ignore

from . import LatLonTuple, AnswerTuple


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
    """Help text to return when query.py is unable to parse a query but
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
GRAMMAR = """

Query →
    QWeather

QWeather → QWeatherQuery '?'?

QWeatherQuery →
    QWeatherCurrent
    | QWeatherForecast
    | QWeatherTemperature
    | QWeatherWind

QWeatherCurrent →
    QWeatherHowIs? "veðrið" QWeatherAnyLoc? QWeatherNow?
    | QWeatherHowIs? "veðrið" QWeatherNow? QWeatherAnyLoc?
    | "hvernig" "veður" "er" QWeatherAnyLoc? QWeatherNow?
    | "hvernig" "viðrar" QWeatherAnyLoc? QWeatherNow?
    | QWeatherWhatCanYouTellMeAbout "veðrið" QWeatherAnyLoc? QWeatherNow?
    | QWeatherWhatCanYouTellMeAbout "veðrið" QWeatherAnyLoc? QWeatherNow?

QWeatherWhatCanYouTellMeAbout →
    "hvað" "geturðu" "sagt" "mér"? "um"
    | "hvað" "getur" "þú" "sagt" "mér"? "um"
    | "hvað" "geturðu" "sagt" "mér"? "varðandi"
    | "hvað" "getur" "þú" "sagt" "mér"? "varðandi"

QWeatherForecast →
    QWeatherWhatIs QWeatherConditionSingular QWeatherLocation? QWeatherNextDays?
    | QWeatherHowIs QWeatherConditionSingular QWeatherLocation? QWeatherNextDays?
    | QWeatherConditionSingular

    | QWeatherHowAre QWeatherConditionPlural QWeatherLocation? QWeatherNextDays?
    | QWeatherWhatAre QWeatherConditionPlural QWeatherLocation? QWeatherNextDays?

    | "hvernig" QWeatherIsWill "veðrið" QWeatherLocation? QWeatherNextDays

    | QWeatherWhatKindOfWeather "er" "spáð" QWeatherLocation? QWeatherNextDays?
    | QWeatherWhatKindOfWeather "má" "búast" "við" QWeatherLocation? QWeatherNextDays?

QWeatherWhatKindOfWeather →
    "hvers" "konar" "veðri" | "hverskonar" "veðri"
    | "hvers" "kyns" "veðri" | "hvernig" "veðri"

QWeatherConditionSingular →
    "veðurspáin" | "spáin" | "veðurspá"

QWeatherConditionPlural →
    "veðurhorfur" | "veður" "horfur"
    | "veðurhorfurnar" | "veður" "horfurnar"
    | "horfur" | "horfurnar"

QWeatherIsWill →
    "er" | "verður"

QWeatherWhatIs →
    "hver" "er" | "hvað" "er"

QWeatherHowIs →
    "hvernig" "er"

QWeatherHowAre →
    "hvernig" "eru"

QWeatherWhatAre →
    "hverjar" "eru"

QWeatherTemperature →
    "hvert" "er" "hitastigið" QWeatherAnyLoc? QWeatherNow?
    | "hvað" "er" "hitastigið" QWeatherAnyLoc? QWeatherNow?
    | "hversu" "heitt" "er" QWeatherAnyLoc? QWeatherNow?
    | "hvað" "er" "heitt" QWeatherAnyLoc? QWeatherNow?
    | "hvaða" "hitastig" "er" QWeatherAnyLoc? QWeatherNow
    | "hversu" "hlýtt" "er" QWeatherAnyLoc? QWeatherNow?
    | "hversu" "heitt" "er" QWeatherAnyLoc? QWeatherNow?
    | "hversu" "kalt" "er" QWeatherAnyLoc? QWeatherNow?
    | "hversu" "mikið" "frost" "er" QWeatherAnyLoc? QWeatherNow?
    | "hvað" "er" "kalt" QWeatherAnyLoc? QWeatherNow
    | "hvað" "er" "hlýtt" QWeatherAnyLoc? QWeatherNow
    | "hvað" "er" "margra" "stiga" "hiti" QWeatherAnyLoc? QWeatherNow?
    | "hvað" "er" "mikið" "frost" QWeatherAnyLoc? QWeatherNow?
    | "hvað" "er" "margra" "stiga" "frost" QWeatherAnyLoc? QWeatherNow?
    | "hversu" "margra" "stiga" "hiti" "er" QWeatherAnyLoc? QWeatherNow?
    | "hversu" "margra" "stiga" "frost" "er" QWeatherAnyLoc? QWeatherNow?
    | "hve" "margra" "stiga" "hiti" "er" QWeatherAnyLoc? QWeatherNow?
    | "hve" "margra" "stiga" "frost" "er" QWeatherAnyLoc? QWeatherNow?
    | "er" "mjög"? "heitt" "úti"? QWeatherAnyLoc? QWeatherNow?
    | "er" "mjög"? "kalt" "úti"? QWeatherAnyLoc? QWeatherNow?
    | "er" "mikill"? "kuldi" "úti"? QWeatherAnyLoc? QWeatherNow?
    | "er" "mikill"? "hiti" "úti"? QWeatherAnyLoc? QWeatherNow?
    | "er" "mikið"? "frost" "úti"? QWeatherAnyLoc? QWeatherNow?
    | "er" QWeatherHotCold? "fyrir_ofan" "frostmark" "úti"? QWeatherAnyLoc? QWeatherNow?
    | "er" QWeatherHotCold? "fyrir_neðan" "frostmark" "úti"? QWeatherAnyLoc? QWeatherNow?

QWeatherHotCold →
    "hiti" | "hitinn" | "kuldi" | "kuldinn" | "hitastig" | "hitastigið"

QWeatherWind →
    "hvað"? "er" "mikið"? "rok" QWeatherAnyLoc? QWeatherNow?
    | "hversu" "mikið" "rok" "er" QWeatherAnyLoc? QWeatherNow?
    | "hve" "mikið" "rok" "er" QWeatherAnyLoc? QWeatherNow?
    | "hversu" "hvasst" "er" QWeatherAnyLoc? QWeatherNow?
    | "hvað" "er" "hvasst" QWeatherAnyLoc? QWeatherNow?
    | "er" "mjög"? "hvasst" QWeatherAnyLoc? QWeatherNow?
    | "hvað"? "eru" "mörg" "vindstig" QWeatherAnyLoc? QWeatherNow?
    | "hversu"? "mörg" "vindstig" "eru"? QWeatherAnyLoc? QWeatherNow?
    | "hvað"? "er" "mikill" "vindur" QWeatherAnyLoc? QWeatherNow?
    | "hvað"? "er" "mikill" "vindhraði" QWeatherAnyLoc? QWeatherNow?
    | "hver" "er" "vindhraðinn" QWeatherAnyLoc? QWeatherNow?
    | "hvaða"? "vindhraði" "er"? QWeatherAnyLoc? QWeatherNow?

QWeatherUmbrella →
    "þarf" QWeatherOne? "regnhlíf" QWeatherNow
    | "þarf" "ég" "að" "taka" "með" "mér" "regnhlíf" QWeatherNow
    | "þarf" "maður" "að" "taka" "með" "sér" "regnhlíf" QWeatherNow
    | "væri" "regnhlíf" "gagnleg" QWeatherForMe? QWeatherNow
    | "væri" "gagn" "af" "regnhlíf" QWeatherForMe? QWeatherNow
    | "kæmi" "regnhlíf" "að" "gagni" QWeatherForMe? QWeatherNow
    | "myndi" "regnhlíf" "gagnast" "mér" QWeatherNow

QWeatherOne →
    "ég" | "maður"

QWeatherForMe →
    "fyrir" "mig"

QWeatherNow →
    "úti"
    | "úti"? "í" "dag"
    | "úti"? "núna"
    | "úti"? "í" "augnablikinu"
    | "úti"? "eins" "og" "stendur"

QWeatherNextDays →
    "á_næstunni"
    | "næstu" "daga"
    | "næstu" "dagana"
    | "fyrir" "næstu" "daga"
    | "á" "næstu" "dögum"
    | "þessa" "viku"
    | "þessa" "vikuna"
    | "út" "vikuna"
    | "í" "vikunni"
    | "á_morgun"
    | "í" "fyrramálið"
    | "fyrir" "morgundaginn"

QWeatherCountry →
    "á" "landinu" | "á" "íslandi" | "hér_á_landi" | "á" "landsvísu"
    | "um" "landið" "allt" | "um" "allt" "land" | "fyrir" "allt" "landið"
    | "á" "fróni" | "heima"

QWeatherCapitalRegion →
    "á" "höfuðborgarsvæðinu" | "fyrir" "höfuðborgarsvæðið"
    | "í" "reykjavík" | "fyrir" "reykjavík"
    | "í" "höfuðborginni" | "fyrir" "höfuðborgina"
    | "á" "reykjavíkursvæðinu" | "fyrir" "reykjavíkursvæðið"
    | "í" "borginni" | "fyrir" "borgina"

QWeatherAnyLoc →
    QWeatherCountry > QWeatherCapitalRegion > QWeatherOpenLoc

QWeatherOpenLoc →
    fs_þgf Nl_þgf

QWeatherLocation →
    QWeatherCountry | QWeatherCapitalRegion

$score(+55) QWeather

"""


# The OpenWeatherMap API key (you must obtain your
# own key if you want to use this code)
_OWM_API_KEY = ""
_OWM_KEY_PATH = os.path.join(
    os.path.dirname(__file__), "..", "resources", "OpenWeatherMapKey.txt"
)


def _get_OWM_API_key() -> str:
    """ Read OpenWeatherMap API key from file """
    global _OWM_API_KEY
    if not _OWM_API_KEY:
        try:
            # You need to obtain your own key and put it in
            # _OWM_API_KEY if you want to use this code.
            with open(_OWM_KEY_PATH) as f:
                _OWM_API_KEY = f.read().rstrip()
        except FileNotFoundError:
            logging.warning(
                "Could not read OpenWeatherMap API key from {0}".format(_OWM_KEY_PATH)
            )
            _OWM_API_KEY = ""
    return _OWM_API_KEY


def _postprocess_owm_data(d):
    """Restructure data from OWM API so it matches that provided by
    the iceweather module."""
    if not d:
        return d

    return d


_OWM_API_URL_BYNAME = (
    "https://api.openweathermap.org/data/2.5/weather?q={0},{1}&appid={2}&units=metric"
)


def _query_owm_by_name(city: str, country_code: Optional[str] = None):
    d = query_json_api(
        _OWM_API_URL_BYNAME.format(city, country_code or "", _get_OWM_API_key())
    )
    return _postprocess_owm_data(d)


_OWM_API_URL_BYLOC = (
    "https://api.openweathermap.org/data/2.5/weather?"
    "lat={0}&lon={1}&appid={2}&units=metric"
)


def _query_owm_by_coords(lat: float, lon: float):
    d = query_json_api(_OWM_API_URL_BYLOC.format(lat, lon, _get_OWM_API_key()))
    return _postprocess_owm_data(d)


_BFT_THRESHOLD = (0.3, 1.5, 3.4, 5.4, 7.9, 10.7, 13.8, 17.1, 20.7, 24.4, 28.4, 32.6)


def _wind_bft(ms: float) -> int:
    """ Convert wind from metres per second to Beaufort scale """
    if ms is None:
        return 0
    ix = 0
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


def _wind_descr(wind_ms: float) -> Optional[str]:
    """Icelandic-language description of wind conditions given metres
    per second. Uses Beaufort scale lookup.
    See https://www.vedur.is/vedur/frodleikur/greinar/nr/1098
    """
    return _BFT_ICEDESC.get(_wind_bft(wind_ms))


_RVK_COORDS = (64.133097, -21.898145)


def _near_capital_region(loc: LatLonTuple) -> bool:
    """ Returns true if location coordinates are within 30 km of central Rvk """
    return distance(loc, _RVK_COORDS) < 30


def _round_to_nearest_hour(t: datetime) -> datetime:
    """ Round datetime to nearest hour """
    return t.replace(second=0, microsecond=0, minute=0, hour=t.hour) + timedelta(
        hours=t.minute // 30
    )


_RVK_STATION_ID = 1


def _curr_observations(query: Query, result):
    """Fetch latest weather observation data from weather station closest
    to the location associated with the query (i.e. either user location
    coordinates or a specific placename)"""
    loc = query.location

    # User asked about a specific location
    # Try to find a matching Icelandic placename
    if (
        "location" in result
        and result.location != "Ísland"
        and result.location != "general"
    ):
        if result.location == "capital":
            loc = _RVK_COORDS
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
        if loc:
            res = observation_for_closest(loc[0], loc[1])
        else:
            res = observation_for_station(_RVK_STATION_ID)  # Default to Reykjavík
            result.subject = "Í Reykjavík"
    except Exception as e:
        logging.warning("Failed to fetch weather info: {0}".format(str(e)))
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


def get_currweather_answer(query: Query, result) -> AnswerTuple:
    """ Handle queries concerning current weather conditions """
    res = _curr_observations(query, result)
    if not res:
        return gen_answer(_API_ERRMSG)

    try:
        temp = int(round(float(res["T"])))  # Round to nearest whole number
        desc = res["W"].lower()
        windsp = float(res["F"])
    except Exception as e:
        logging.warning("Exception parsing weather API result: {0}".format(e))
        return gen_answer(_API_ERRMSG)

    wind_desc = _wind_descr(windsp)
    wind_ms_str = str(windsp).rstrip("0").rstrip(".")
    temp_type = "hiti" if temp >= 0 else "frost"
    mdesc = ", " + desc + "," if desc else ""

    locdesc = result.get("subject") or "Úti"

    # Meters per second string for voice. Say nothing if "logn".
    voice_ms = (
        ", {0} á sekúndu".format(sing_or_plur(int(wind_ms_str), "metri", "metrar"))
        if wind_ms_str != "0"
        else ""
    )

    # Format voice string
    voice = "{0} er {1} stiga {2}{3} og {4}{5}".format(
        locdesc.capitalize(), abs(temp), temp_type, mdesc, wind_desc, voice_ms
    )

    # Text answer
    answer = "{0} °C{1} og {2} ({3} m/s)".format(temp, mdesc, wind_desc, wind_ms_str)

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


def get_forecast_answer(query: Query, result):
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
        or "results" not in res
        or not len(res["results"])
        or "content" not in res["results"][0]
    ):
        return gen_answer(_API_ERRMSG)

    answer = res["results"][0]["content"]
    response = dict(answer=answer)
    voice = _descr4voice(answer)

    return response, answer, voice


def get_umbrella_answer(query: Query, result):
    """Handle a query concerning whether an umbrella is needed
    for current weather conditions."""

    # if rain and high wind: no, not gonna work buddy
    # if no rain: no, it's not raining or likely to rain
    # else: yeah, take the umbrella

    return None


def QWeather(node, params, result):
    result.qtype = _WEATHER_QTYPE


def QWeatherCapitalRegion(node, params, result):
    result["location"] = "capital"


def QWeatherCountry(node, params, result):
    result["location"] = "general"


def QWeatherOpenLoc(node, params, result):
    """Store preposition and placename to use in voice
    description, e.g. "Á Raufarhöfn" """
    result["subject"] = result._node.contained_text().title()


def Nl(node, params, result):
    """ Noun phrase containing name of specific location """
    result["location"] = cap_first(result._nominative)


def EfLiður(node, params, result):
    """ Don't change the case of possessive clauses """
    result._nominative = result._text


def FsMeðFallstjórn(node, params, result):
    """ Don't change the case of prepositional clauses """
    result._nominative = result._text


def QWeatherCurrent(node, params, result):
    result.qkey = "CurrentWeather"


def QWeatherWind(node, params, result):
    result.qkey = "CurrentWeather"


def QWeatherForecast(node, params, result):
    result.qkey = "WeatherForecast"


def QWeatherTemperature(node, params, result):
    result.qkey = "CurrentWeather"


def QWeatherUmbrella(node, params, result):
    result.qkey = "Umbrella"


_HANDLERS = {
    "CurrentWeather": get_currweather_answer,
    "WeatherForecast": get_forecast_answer,
    "Umbrella": get_umbrella_answer,
}


def sentence(state, result):
    """ Called when sentence processing is complete """
    q: Query = state["query"]
    if "qtype" in result and "qkey" in result:
        # Successfully matched a query type
        q.set_qtype(result.qtype)
        q.set_key(result.qkey)

        # Asking for a location outside Iceland
        if q.location and not in_iceland(q.location):
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
