"""

    Greynir: Natural language processing for Icelandic

    Flight schedule query response module

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
    along with this program. If not, see http://www.gnu.org/licenses/.


    This module handles queries relating to air travel.

"""

from typing import List, Dict, Any, Optional

import re
import random
import logging
import cachetools
from html import escape
from datetime import datetime, timedelta, timezone

from query import Query, QueryStateDict
from queries import query_json_api
from tree import Result
from settings import changedlocale

from reynir import NounPhrase
from geo import capitalize_placename, iceprep_for_placename, icelandic_city_name


_FLIGHTS_QTYPE = "Flights"


TOPIC_LEMMAS = [
    "flugvél",
    "flugvöllur",
    "flug",
    "lenda",
    "brottfarartími",
    "lendingartími",
]


def help_text(lemma: str) -> str:
    """Help text to return when query.py is unable to parse a query but
    one of the above lemmas is found in it"""
    return "Ég get svarað ef þú spyrð til dæmis: {0}?".format(
        random.choice(
            (
                "Hvenær lendir næsta vél frá Kaupmannahöfn",
                "Hvenær fer næsta flug til Lundúna",
                "Hvenær lendir næsta flugvél á Akureyri frá Egilsstöðum",
                "Hvenær flýgur næsta vél frá Keflavík til Stokkhólms",
            )
        )
    )


# This module wants to handle parse trees for queries
HANDLE_TREE = True

# The grammar nonterminals this module wants to handle
QUERY_NONTERMINALS = {"QFlights"}

# The context-free grammar for the queries recognized by this plug-in module
GRAMMAR = """

Query →
    QFlights

QFlights → QFlightsQuery '?'?

QFlightsQuery →
    QFlightsArrivalQuery
    | QFlightsDepartureQuery

QFlightsArrivalQuery →
    # Arrivals at Icelandic airports, e.g.
    # Hver er lendingartími næstu vélar í Reykjavík
    # Hvenær kemur næsta flug til Keflavíkur frá Kaupmannahöfn
    QFlightsWhenArr QFlightsNextPlane QFlightsPathDesc

QFlightsWhenArr →
    QFlightsWhen "lendir"
    | QFlightsWhen "kemur"
    | QFlightsWhen "mætir"
    | "hver" "er" "lendingartími"
    | "hver" "er" "lendingartíminn" "fyrir"

QFlightsDepartureQuery →
    # Departures from Icelandic airports, e.g.
    # Hver er brottfarartími næstu vélar til London
    # Hvenær flýgur næsta vél af stað frá Keflavík til Köben
    QFlightsWhenDepNextPlane QFlightsPathDesc

QFlightsAfStað → "af" "stað"

QFlightsWhenDepNextPlane →
    QFlightsWhen "leggur" QFlightsNextPlane QFlightsAfStað
    | QFlightsWhenDep QFlightsNextPlane QFlightsAfStað?

QFlightsNextPlane →
    "næsta" QFlightsPlane/fall
    | "næstu" QFlightsPlane/fall

QFlightsWhenDep →
    QFlightsWhen "fer"
    | QFlightsWhen "flýgur"
    | "hver" "er" "brottfarartími"
    | "hver" "er" "brottfarartíminn" "fyrir"

QFlightsWhen →
    "hvenær" | "klukkan" "hvað"

QFlightsPlane/fall ->
    'flug:hk'_et/fall
    | 'flugvél:kvk'_et/fall
    | 'vél:kvk'_et/fall

QFlightsPathDesc →
    # At least one endpoint of the flight (in any order), e.g.
    # frá Keflavík til Reykjavíkur
    # til Akureyrar
    QFlightsPrepLoc QFlightsPrepLoc
    > QFlightsPrepLoc

QFlightsPrepLoc →
    "til" QFlightsArrLoc_ef
    | "frá" QFlightsDepLoc_þgf
    | "í" QFlightsArrLoc_þgf
    | "á" QFlightsArrLoc_þgf
    | "á" QFlightsArrLoc_þf

QFlightsArrLoc/fall →
    Nl/fall

QFlightsDepLoc/fall →
    Nl/fall

$tag(keep) QFlightsArrLoc/fall
$tag(keep) QFlightsDepLoc/fall

"""

_LOCATION_ABBREV_MAP = {
    "köben": "kaupmannahöfn",
    "kef": "keflavík",
    "álaborg": "aalborg",
}

_IATA_TO_AIRPORT_MAP = {
    "aey": "akureyri",
    "biu": "bíldudalur",
    "egs": "egilsstaðir",
    "gjr": "gjögur",
    "gry": "grímsey",
    "hfn": "hornafjörður",
    "hzk": "húsavík",
    "ifj": "ísafjörður",
    "kef": "keflavík",
    "rkv": "reykjavík",
    "sak": "sauðárkrókur",
    "tho": "þórshöfn",
    "vey": "vestmannaeyjar",
    "vpn": "vopnafjörður",
}

_AIRPORT_TO_IATA_MAP = {val: key for key, val in _IATA_TO_AIRPORT_MAP.items()}

# Day indices in accusative case
_DAY_INDEX_ACC = {
    1: "fyrsta",
    2: "annan",
    3: "þriðja",
    4: "fjórða",
    5: "fimmta",
    6: "sjötta",
    7: "sjöunda",
    8: "áttunda",
    9: "níunda",
    10: "tíunda",
    11: "ellefta",
    12: "tólfta",
    13: "þrettánda",
    14: "fjórtánda",
    15: "fimmtánda",
    16: "sextánda",
    17: "sautjánda",
    18: "átjánda",
    19: "nítjánda",
    20: "tuttugasta",
    21: "tuttugasta og fyrsta",
    22: "tuttugasta og annan",
    23: "tuttugasta og þriðja",
    24: "tuttugasta og fjórða",
    25: "tuttugasta og fimmta",
    26: "tuttugasta og sjötta",
    27: "tuttugasta og sjöunda",
    28: "tuttugasta og áttunda",
    29: "tuttugasta og níunda",
    30: "þrítugasta",
    31: "þrítugasta og fyrsta",
}


def QFlightsQuery(node, params, result):
    # Set the query type
    result.qtype = _FLIGHTS_QTYPE


def QFlightsArrivalQuery(node, params, result):
    result["departure"] = False


def QFlightsDepartureQuery(node, params, result):
    result["departure"] = True


def QFlightsArrLoc(node, params, result):
    result["to_loc"] = result._nominative


def QFlightsDepLoc(node, params, result):
    result["from_loc"] = result._nominative


_ISAVIA_FLIGHTS_URL = (
    "https://www.isavia.is/json/flight/?cargo=0&airport={0}"
    "&dateFrom={1}&dateTo={2}&language=is&departures={3}"
)

_FLIGHTS_CACHE_TTL = 600  # seconds, ttl = 10 mins

# Cache for flights either departing or arriving
_FLIGHT_CACHE: cachetools.TTLCache = cachetools.TTLCache(
    maxsize=2, ttl=_FLIGHTS_CACHE_TTL
)

# For type checking
FlightType = Dict[str, Any]
FlightList = List[FlightType]


def _fetch_flight_data(
    from_date: datetime, to_date: datetime, iata_code: str, departing: bool
) -> FlightList:
    """
    Fetch data on flights to/from an Icelandic airport (given with its IATA code)
    between from_date and to_date from Isavia's JSON API.
    """
    date_format = "%Y-%m-%d %H:%M"
    from_date_str = from_date.strftime(date_format)
    to_date_str = to_date.strftime(date_format)

    # Insert GET parameters
    url: str = _ISAVIA_FLIGHTS_URL.format(
        iata_code.upper(), from_date_str, to_date_str, str(departing).lower()
    )

    res = query_json_api(url)

    # Verify result was successful
    if not res or "Success" not in res or not res["Success"] or "Items" not in res:
        return []

    # Add result to cache
    _FLIGHT_CACHE[departing] = res["Items"]
    return res["Items"]


def _filter_flight_data(
    flights: FlightList,
    airport: str,
    api_airport: str,
    n: int = 1,
) -> FlightList:
    """
    Narrows down list of flight data dicts for first n flights to/from the specified airport.
    Adds flight_time and api_airport attributes to matching flights.
    Returns the matching flights in a list.
    """
    flight_time: datetime
    flight: FlightType
    now: datetime = datetime.now(timezone.utc)  # Timezone aware datetime

    matching_flights: FlightList = []
    for flight in flights:
        if n <= 0:
            break

        if (
            airport == "*"
            or (
                flight.get("DisplayName") is not None
                and (
                    flight["DisplayName"].lower().startswith(airport)
                    or flight["DisplayName"].lower().endswith(airport)
                )
            )
            or (
                flight.get("AltDisplayName") is not None
                and (
                    flight["AltDisplayName"].lower().startswith(airport)
                    or flight["AltDisplayName"].lower().endswith(airport)
                )
            )
        ):
            # Use estimated time instead of scheduled if available
            if flight.get("Estimated") is not None:
                flight_time = datetime.fromisoformat(flight["Estimated"])
            elif flight.get("Scheduled") is not None:
                flight_time = datetime.fromisoformat(flight["Scheduled"])
            else:
                continue  # Failed, no time found

            # Make sure flight isn't in the past
            if flight_time and flight_time >= now:

                # Create copy of dictionary and
                # add flight_time and api_airport attributes
                flight_copy: FlightType = {
                    **flight,
                    "flight_time": flight_time,
                    "api_airport": api_airport,
                }

                matching_flights.append(flight_copy)
                n -= 1

    return matching_flights


_BREAK_LENGTH = 0.5  # Seconds
_BREAK_SSML = '<break time="{0}s"/>'.format(_BREAK_LENGTH)


def _format_flight_answer(flights: FlightList) -> Dict[str, str]:
    """
    Takes in a list of flights and returns a dict
    containing a formatted answer and text for a voice line.

    Each flight should contain the attributes:
        'No':           Flight number
        'DisplayName':  Name of airport/city
        'api_airport':  Name of Icelandic airport/city
        'flight_time':  Time of departure/arrival
        'Departure':    True if departing from api_airport, else False
        'Status':       Info on flight status (e.g. whether it's cancelled)
    """
    airport: str
    api_airport: str
    flight_dt: datetime
    answers: List[str] = []
    voice_lines: List[str] = []

    for flight in flights:
        airport = icelandic_city_name(capitalize_placename(flight["DisplayName"]))
        api_airport = icelandic_city_name(capitalize_placename(flight["api_airport"]))

        flight_dt = flight["flight_time"]
        flight_date_str = flight_dt.strftime("%-d. %B")
        flight_time_str = flight_dt.strftime("%H:%M")

        if flight["Departure"]:
            airport = NounPhrase(airport).genitive or airport
            api_airport = NounPhrase(api_airport).dative or api_airport

            # Catch cancelled flights
            if flight["Status"] and "aflýst" in flight["Status"].lower():
                line = (
                    f"Flugi {flight['No']} frá {api_airport} til {airport} er aflýst."
                )
            else:
                line = (
                    f"Flug {flight['No']} til {airport} "
                    f"flýgur frá {api_airport} {flight_date_str} "
                    f"klukkan {flight_time_str} að staðartíma."
                )
        else:
            airport = NounPhrase(airport).dative or airport
            prep = iceprep_for_placename(api_airport)
            api_airport = NounPhrase(api_airport).dative or api_airport

            if flight["Status"] and "aflýst" in flight["Status"].lower():
                line = (
                    f"Flugi {flight['No']} frá {airport} til {api_airport} er aflýst."
                )
            else:
                line = (
                    f"Flug {flight['No']} frá {airport} "
                    f"lendir {prep} {api_airport} {flight_date_str} "
                    f"klukkan {flight_time_str} að staðartíma."
                )

        voice_line = re.sub(r" \d+\. ", " " + _DAY_INDEX_ACC[flight_dt.day] + " ", line)

        answers.append(line)
        voice_lines.append(voice_line)

    return {
        "answer": "<br/>".join(answers).strip(),
        "voice": _BREAK_SSML.join(voice_lines).strip(),
    }


def _process_result(result: Result) -> Dict[str, str]:
    """
    Return formatted description of arrival/departure
    time of flights to or from an Icelandic airport,
    based on info in result dict.
    """
    airport: str  # Icelandic or foreign airport/country
    api_airport: str  # Always an Icelandic airport, as the ISAVIA API only covers them

    departing: bool = result["departure"]
    if departing:
        # Departures (from Keflavík by default)
        api_airport = result.get("from_loc", "keflavík").lower()
        # Wildcard matches any flight (if airport wasn't specified)
        airport = result.get("to_loc", "*").lower()
    else:
        # Arrivals (to Keflavík by default)
        api_airport = result.get("to_loc", "keflavík").lower()
        airport = result.get("from_loc", "*").lower()

    from_date: datetime
    to_date: datetime
    days: int = result.get("day_count", 5)  # Check 5 days into future by default
    from_date = result.get("from_date", datetime.now(timezone.utc))
    to_date = result.get("to_date", datetime.now(timezone.utc) + timedelta(days=days))

    # Normalize airport/city names
    airport = _LOCATION_ABBREV_MAP.get(airport, airport)
    airport = NounPhrase(airport).nominative or airport

    api_airport = _LOCATION_ABBREV_MAP.get(api_airport, api_airport)
    api_airport = NounPhrase(api_airport).nominative or api_airport

    # Translate Icelandic airport to its IATA code
    iata_code: str = _AIRPORT_TO_IATA_MAP.get(api_airport, api_airport)

    # TODO: Currently module only fetches one flight,
    # modifications to the grammar could allow fetching of more flights at once
    flight_count: int = result.get("flight_count", 1)

    flight_data: FlightList
    # Check first if function result in cache, else fetch data from API
    if departing in _FLIGHT_CACHE:
        flight_data = _FLIGHT_CACHE[departing]
    else:
        flight_data = _fetch_flight_data(from_date, to_date, iata_code, departing)

    flight_data = _filter_flight_data(flight_data, airport, api_airport, flight_count)

    answ: Dict[str, str] = dict()
    if len(flight_data) > 0:
        # (Format month names in Icelandic)
        with changedlocale(category="LC_TIME"):
            answ = _format_flight_answer(flight_data)
    else:
        to_airp: str
        from_airp: str
        if departing:
            to_airp, from_airp = airport, api_airport
        else:
            from_airp, to_airp = airport, api_airport

        to_airp = icelandic_city_name(capitalize_placename(to_airp))
        from_airp = icelandic_city_name(capitalize_placename(from_airp))

        from_airp = NounPhrase(from_airp).dative or from_airp
        to_airp = NounPhrase(to_airp).genitive or to_airp

        if from_airp == "*":
            answ["answer"] = f"Ekkert flug fannst til {escape(to_airp)} næstu {days} daga."
        elif to_airp == "*":
            answ["answer"] = f"Ekkert flug fannst frá {escape(from_airp)} næstu {days} daga."
        else:
            answ["answer"] = (
                f"Ekkert flug fannst "
                f"frá {escape(from_airp)} "
                f"til {escape(to_airp)} "
                f"næstu {days} daga."
            )
        answ["voice"] = answ["answer"]

    return answ


def sentence(state: QueryStateDict, result: Result) -> None:
    """Called when sentence processing is complete."""
    q: Query = state["query"]
    if (
        "qtype" in result
        and result["qtype"] == _FLIGHTS_QTYPE
        and "departure" in result
    ):
        try:
            answ: Dict[str, str] = _process_result(result)
            q.set_qtype(_FLIGHTS_QTYPE)
            q.set_answer(answ, answ["answer"], answ["voice"])
            return
        except Exception as e:
            logging.warning(
                "Exception generating answer from flight data: {0}".format(e)
            )
            q.set_error("E_EXCEPTION: {0}".format(e))
    else:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
