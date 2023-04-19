"""

    Greynir: Natural language processing for Icelandic

    Flight schedule query response module

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
    along with this program. If not, see http://www.gnu.org/licenses/.


    This module handles queries relating to air travel.

"""
# TODO: Map country to capital city, e.g. "Svíþjóð" -> "Stokkhólmur"
# TODO: Fetch more than one flight using "flight_count"?

from typing import List, Dict, Optional
from typing_extensions import TypedDict

import re
import random
import logging
import cachetools
from datetime import datetime, timedelta, timezone

from queries import Query, QueryStateDict
from queries.util import query_json_api, is_plural, read_grammar_file
from tree import Result, Node
from settings import changedlocale
from speech.trans import gssml

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
    """Help text to return when query processor is unable to parse a query but
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
GRAMMAR = read_grammar_file("flights")

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


def QFlightsQuery(node: Node, params: QueryStateDict, result: Result) -> None:
    # Set the query type
    result.qtype = _FLIGHTS_QTYPE


def QFlightsArrivalQuery(node: Node, params: QueryStateDict, result: Result) -> None:
    result["departure"] = False


def QFlightsDepartureQuery(node: Node, params: QueryStateDict, result: Result) -> None:
    result["departure"] = True


def QFlightsArrLoc(node: Node, params: QueryStateDict, result: Result) -> None:
    result["to_loc"] = result._nominative


def QFlightsDepLoc(node: Node, params: QueryStateDict, result: Result) -> None:
    result["from_loc"] = result._nominative


_ISAVIA_FLIGHTS_URL = (
    "https://www.isavia.is/json/flight/?cargo=0&airport={0}"
    "&dateFrom={1}&dateTo={2}&language=is&departures={3}"
)

_FLIGHTS_CACHE_TTL = 600  # seconds, ttl = 10 mins

# Cache for flights either departing or arriving
_FLIGHT_CACHE: cachetools.TTLCache = cachetools.TTLCache(  # type: ignore
    maxsize=2, ttl=_FLIGHTS_CACHE_TTL
)

# For type checking
class FlightType(TypedDict, total=False):
    No: str
    Departure: bool
    HomeAirportIATA: str
    HomeAirport: str
    OriginDestIATA: str
    OriginDest: str
    DisplayName: str
    Scheduled: str
    Estimated: Optional[str]
    Status: Optional[str]
    Additional: Optional[str]
    AltDisplayName: Optional[str]
    # We add these
    api_airport: str
    flight_time: datetime


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
    if (
        not isinstance(res, dict)
        or "Success" not in res
        or not res["Success"]
        or "Items" not in res
    ):
        return []

    # Add result to cache
    _FLIGHT_CACHE[departing] = res["Items"]
    return res["Items"]


def _attribute_airport_match(flight: FlightType, attribute: str, airport: str) -> bool:
    """
    Safely checks whether the string flight[attribute] in lowercase
    either starts or ends with airport string.
    """
    a = flight.get(attribute)
    if not isinstance(a, str):
        return False
    a = a.lower()
    return a.startswith(airport) or a.endswith(airport)


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
    now: datetime = datetime.now(timezone.utc) # Timezone aware datetime (don't change to datetime.utcnow()!)

    matching_flights: FlightList = []
    for flight in flights:
        if n <= 0:
            break

        if (
            airport == "*"
            or _attribute_airport_match(flight, "DisplayName", airport)
            or _attribute_airport_match(flight, "AltDisplayName", airport)
        ):
            # Use estimated time instead of scheduled if available
            flight_time_str = flight.get("Estimated") or flight.get("Scheduled")

            if not flight_time_str:
                continue  # Failed, no time found (either None or "")

            # Change +00:00 UTC offset to +0000 for %z tag
            flight_time_str = re.sub(
                r"([-+]\d{2}):(\d{2})(?:(\d{2}))?$",
                r"\1\2\3",
                flight_time_str,
            )

            flight_time = datetime.strptime(flight_time_str, "%Y-%m-%dT%H:%M:%S%z")

            # Make sure flight isn't in the past
            if flight_time and flight_time >= now:
                # Create copy of dictionary and
                # add flight_time and api_airport attributes
                flight_copy: FlightType = {
                    **flight,  # type: ignore[misc]
                    "flight_time": flight_time,
                    "api_airport": api_airport,
                }

                matching_flights.append(flight_copy)
                n -= 1

    return matching_flights


# Break in speech synthesis between each flight
_BREAK_TIME = "0.5s"


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
    flight_dt: Optional[datetime]
    answers: List[str] = []
    voice_lines: List[str] = []

    for flight in flights:
        flight_number = flight.get("No")
        if flight_number is None:
            continue  # Invalid flight number

        airport = icelandic_city_name(
            capitalize_placename(flight.get("DisplayName", ""))
        )
        api_airport = icelandic_city_name(
            capitalize_placename(flight.get("api_airport", ""))
        )

        flight_dt = flight.get("flight_time")
        if flight_dt is None or airport == "" or api_airport == "":
            continue  # Invalid time or locations

        flight_status = flight.get("Status")  # Whether flight is cancelled or not

        if flight.get("Departure"):
            airport = NounPhrase(airport).genitive or airport
            api_airport = NounPhrase(api_airport).dative or api_airport

            # Catch cancelled flights
            if flight_status and "aflýst" in flight_status.lower():
                line = (
                    "Flugi {flight_number} frá {api_airport} til {airport} er aflýst."
                )
            else:
                line = (
                    "Flug {flight_number} til {airport} "
                    "flýgur frá {api_airport} {flight_date_str} "
                    "klukkan {flight_time_str} að staðartíma."
                )
        else:
            airport = NounPhrase(airport).dative or airport
            prep = iceprep_for_placename(api_airport)
            api_airport = NounPhrase(api_airport).dative or api_airport

            if flight_status and "aflýst" in flight_status.lower():
                line = (
                    "Flugi {flight_number} frá {airport} til {api_airport} er aflýst."
                )
            else:
                line = (
                    "Flug {flight_number} frá {airport} "
                    f"lendir {prep} "
                    "{api_airport} {flight_date_str} "
                    "klukkan {flight_time_str} að staðartíma."
                )
        fds = flight_dt.strftime("%-d. %B")
        fts = flight_dt.strftime("%H:%M")

        # Voice answer needs parts of the text to be transcribed
        # e.g. wrap the flight number in transcription markdown
        # so e.g. 'GS209' is eventually transcribed
        # something like 'gé ess tveir núll níu'
        voice_line = line.format(
            flight_number=gssml(flight_number, type="numalpha"),
            airport=airport,
            api_airport=api_airport,
            flight_date_str=gssml(fds, type="date", case="þf"),
            flight_time_str=gssml(fts, type="time"),
        )
        voice_lines.append(voice_line)

        # Visual answer doesn't need transcribing
        line = line.format(
            flight_number=flight_number,
            airport=airport,
            api_airport=api_airport,
            flight_date_str=fds,
            flight_time_str=fts,
        )
        answers.append(line)

    return {
        "answer": "<br/>".join(answers).strip(),
        "voice": gssml(type="vbreak", time=_BREAK_TIME).join(voice_lines).strip(),
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
    now = datetime.now(timezone.utc)  # Timezone aware datetime, don't change to .utcnow()!
    days: int = result.get("day_count", 5)  # Check 5 days into future by default
    from_date = result.get("from_date", now)
    to_date = result.get("to_date", now + timedelta(days=days))

    # Normalize airport/city names
    airport = _LOCATION_ABBREV_MAP.get(airport, airport)
    airport = NounPhrase(airport).nominative or airport

    api_airport = _LOCATION_ABBREV_MAP.get(api_airport, api_airport)
    api_airport = NounPhrase(api_airport).nominative or api_airport

    # Translate Icelandic airport to its IATA code
    iata_code: str = _AIRPORT_TO_IATA_MAP.get(api_airport, api_airport)

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
            answ["answer"] = f"Ekkert flug fannst til {to_airp} "
        elif to_airp == "*":
            answ["answer"] = f"Ekkert flug fannst frá {from_airp} "
        else:
            answ["answer"] = f"Ekkert flug fannst frá {from_airp} til {to_airp} "

        answ["voice"] = answ["answer"]
        if days == 1:
            # Wording if only checking next 24 hours
            answ["answer"] += "næsta sólarhringinn."
            answ["voice"] += "næsta sólarhringinn."
        else:
            answ["answer"] += (
                f"næstu {days} sólarhringa."
                if is_plural(days)
                else f"næsta {days} sólarhringinn."
            )
            # Convert numbers to text in correct case and gender for voice
            # ("næstu 4 sólarhringa" -> "næstu fjóra sólarhringa")
            answ["voice"] += (
                f"næstu {gssml(days, type='number', gender='kk', case='þf')} sólarhringa."
                if is_plural(days)
                else f"næsta {gssml(days, type='number', gender='kk', case='þf')} sólarhringinn."
            )

    return answ


def sentence(state: QueryStateDict, result: Result) -> None:
    """Called when sentence processing is complete."""
    q: Query = state["query"]
    if (
        "qtype" in result
        and result["qtype"] == _FLIGHTS_QTYPE
        and isinstance(result.get("departure"), bool)
    ):
        try:
            answ: Dict[str, str] = _process_result(result)
            q.set_qtype(_FLIGHTS_QTYPE)
            q.set_source("Isavia")
            q.set_answer(answ, answ["answer"], answ["voice"])
            return
        except Exception as e:
            logging.warning(f"Exception generating answer from flight data: {e}")
            q.set_error(f"E_EXCEPTION: {e}")
    else:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
