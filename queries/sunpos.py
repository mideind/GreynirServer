"""

    Greynir: Natural language processing for Icelandic

    Solar position query response module

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


    This module handles queries regarding time of sunrise/sunset.

"""

# TODO: "Hvenær rís sólin [any date]"
# TODO: "Hvenær kemur sólin upp"
# TODO: Use gssml instead of numbers_to_... functions
# TODO: Use https://vedur.is/gogn/vefgogn/sol/index.html instead of inaccurate HÍ almanak

from typing import Dict, List, Iterable, Tuple, Optional, Union, cast

from tree import Result, Node
from queries import Query, QueryStateDict

from queries.util import (
    AnswerTuple,
    LatLonTuple,
    MONTH_ABBREV_ORDERED,
    read_grammar_file,
    sing_or_plur,
    gen_answer,
)

import datetime
import logging
import random
import re
import requests

from bs4 import BeautifulSoup  # type: ignore
from cachetools import TTLCache
from settings import changedlocale
from geo import (
    distance,
    in_iceland,
    capitalize_placename,
    ICE_PLACENAME_BLACKLIST,
)
from iceaddr import placename_lookup
from speech.trans.num import numbers_to_ordinal, floats_to_text

# Indicate that this module wants to handle parse trees for queries,
# as opposed to simple literal text strings
HANDLE_TREE = True

# The grammar nonterminals this module wants to handle
QUERY_NONTERMINALS = {"QSunQuery"}

_SUN_QTYPE = "SunPosition"

TOPIC_LEMMAS = [
    "birting",
    "birta",
    "dagsetur",
    "dögun",
    # "hádegi",
    "miðnætti",
    "myrkur",
    # "rísa",
    "setjast",
    "sólarhæð",
    "sólarlag",
    "sólarupprás",
    "sólris",
    "sólsetur",
    "sól",
]


def help_text(lemma: str) -> str:
    """Help text to return when query processor is unable to parse a query but
    one of the above lemmas is found in it"""
    return "Ég get svarað ef þú spyrð til dæmis: {0}?".format(
        random.choice(
            (
                "Hvenær reis sólin í morgun",
                "Hvenær sest sólin á morgun",
                "Hvenær er sólsetur í kvöld",
                "Klukkan hvað rís sólin á morgun",
            )
        )
    )


# The context-free grammar for the queries recognized by this plug-in module
GRAMMAR = read_grammar_file("sunpos")


class _SOLAR_POSITIONS:
    MIÐNÆTTI = 0
    DÖGUN = 1
    BIRTING = 2
    SÓLRIS = 3
    HÁDEGI = 4
    SÓLARLAG = 5
    MYRKUR = 6
    DAGSETUR = 7
    SÓLARHÆÐ = 8  # Not a specific position, rather height in degrees at solar noon


_SOLAR_POS_ENUM = int
_SOLAR_CELL_TYPE = Union[datetime.time, float, None]
_SOLAR_ROW_TYPE = Dict[_SOLAR_POS_ENUM, _SOLAR_CELL_TYPE]
_SOLAR_DICT_TYPE = Dict[
    str, Dict[Union[str, datetime.date], Union[LatLonTuple, _SOLAR_ROW_TYPE]]
]

_SOLAR_ENUM_TO_WORD: Dict[_SOLAR_POS_ENUM, str] = {
    _SOLAR_POSITIONS.MIÐNÆTTI: "Miðnætti",
    _SOLAR_POSITIONS.DÖGUN: "Dögun",
    _SOLAR_POSITIONS.BIRTING: "Birting",
    _SOLAR_POSITIONS.SÓLRIS: "Sólris",
    _SOLAR_POSITIONS.HÁDEGI: "Hádegi",
    _SOLAR_POSITIONS.SÓLARLAG: "Sólarlag",
    _SOLAR_POSITIONS.MYRKUR: "Myrkur",
    _SOLAR_POSITIONS.DAGSETUR: "Dagsetur",
    _SOLAR_POSITIONS.SÓLARHÆÐ: "Sólarhæð",
}


def QSunQuery(node: Node, params: QueryStateDict, result: Result) -> None:
    # Set the query type
    result.qtype = _SUN_QTYPE


def QSunIsWillWas(node: Node, params: QueryStateDict, result: Result) -> None:
    if result._nominative == "verður":
        result["will_be"] = True


### QSunPositions ###


def QSunMiðnætti(node: Node, params: QueryStateDict, result: Result) -> None:
    result["solar_position"] = _SOLAR_POSITIONS.MIÐNÆTTI


def QSunDögun(node: Node, params: QueryStateDict, result: Result) -> None:
    result["solar_position"] = _SOLAR_POSITIONS.DÖGUN


def QSunBirting(node: Node, params: QueryStateDict, result: Result) -> None:
    result["solar_position"] = _SOLAR_POSITIONS.BIRTING


def QSunSólris(node: Node, params: QueryStateDict, result: Result) -> None:
    result["solar_position"] = _SOLAR_POSITIONS.SÓLRIS


def QSunHádegi(node: Node, params: QueryStateDict, result: Result) -> None:
    result["solar_position"] = _SOLAR_POSITIONS.HÁDEGI


def QSunSólarlag(node: Node, params: QueryStateDict, result: Result) -> None:
    result["solar_position"] = _SOLAR_POSITIONS.SÓLARLAG


def QSunMyrkur(node: Node, params: QueryStateDict, result: Result) -> None:
    result["solar_position"] = _SOLAR_POSITIONS.MYRKUR


def QSunDagsetur(node: Node, params: QueryStateDict, result: Result) -> None:
    result["solar_position"] = _SOLAR_POSITIONS.DAGSETUR


def QSunSólarhæð(node: Node, params: QueryStateDict, result: Result) -> None:
    result["solar_position"] = _SOLAR_POSITIONS.SÓLARHÆÐ


### QSunDates ###


def QSunToday(node: Node, params: QueryStateDict, result: Result) -> None:
    result["date"] = datetime.date.today()


def QSunYesterday(node: Node, params: QueryStateDict, result: Result) -> None:
    result["date"] = datetime.date.today() - datetime.timedelta(days=1)


def QSunTomorrow(node: Node, params: QueryStateDict, result: Result) -> None:
    result["date"] = datetime.date.today() + datetime.timedelta(days=1)


### QSunLocation ###


def QSunCapitalRegion(node: Node, params: QueryStateDict, result: Result) -> None:
    result["city"] = "Reykjavík"


def QSunArbitraryLocation(node: Node, params: QueryStateDict, result: Result) -> None:
    result["city"] = capitalize_placename(result._nominative)


###

_ALMANAK_HI_URL: str = "http://www.almanak.hi.is/solgang.html"
_ALMANAK_HI_COLUMNS: Tuple[_SOLAR_POS_ENUM, ...] = (
    _SOLAR_POSITIONS.DÖGUN,
    _SOLAR_POSITIONS.BIRTING,
    _SOLAR_POSITIONS.SÓLRIS,
    _SOLAR_POSITIONS.HÁDEGI,
    _SOLAR_POSITIONS.SÓLARLAG,
    _SOLAR_POSITIONS.MYRKUR,
    _SOLAR_POSITIONS.DAGSETUR,
    _SOLAR_POSITIONS.SÓLARHÆÐ,
)


# Match lines such as (lat/lon given in format DD°MM.M')
#    "VESTMANNAEYJAR  2021   63°26,2'  20°16,5'"
_ALMANAK_CITY_REGEX = re.compile(
    r"^(\w+)\s+\d\d\d\d\s+(\d+°\d+,\d+')\s+(\d+°\d+,\d+'?)$"
)

# Match lines such as:
#    "JAN  1.    07 55    10 03    11 18    13 31    15 45    17 00    19 08     3,1"
#    " -   8.    07 52    09 57    11 08    13 35    16 01    17 13    19 18     3,9"
#    " -  29.                      09 02    13 11    16 00                      12,3"

_ALMANAK_SUNPOS_REGEX = re.compile(
    r"^(\w\w\w| - )\s+(\d+)\." + 7 * r"    (\d\d \d\d|     )" + r"\s+(\d+,\d+)$"
)


def _convert_dms_lat_lon_to_decimal(lat: str, lon: str) -> LatLonTuple:
    """
    Convert lat/lon coordinate strings of the format DD°MM.M' to decimal degrees.
    Returns tuple of floats.
    """
    dlat_str, mlat_str = lat.rstrip("'").replace(",", ".").split("°")
    dlat: float = float(dlat_str) + (float(mlat_str) / 60)

    dlon_str, mlon_str = lon.rstrip("'").replace(",", ".").split("°")
    dlon: float = float(dlon_str) + (float(mlon_str) / 60)

    return (dlat, dlon)


def _parse_almanak_cell(pt_str: str) -> _SOLAR_CELL_TYPE:
    """
    Parse a cell in Almanak HÍ. Returns datetime.time for cells containing
    a timestamp, float for cells containing the solar height and None otherwise.
    Examples:
        '03 15' => datetime.time(3,15)
        '34,9'  => 34.9
        '     ' => None
    """
    try:
        if not pt_str.isspace():
            if " " in pt_str:
                # Column contains a time value, convert to datetime
                hour, minute = pt_str.split()
                return datetime.time(hour=int(hour) % 24, minute=int(minute) % 60)

            if "," in pt_str:
                # Column contains solar height at solar noon (in degrees)
                return float(pt_str.replace(",", "."))
    except ValueError:
        pass
    return None


def _parse_almanak_hi_data(text: Iterable[str]) -> _SOLAR_DICT_TYPE:
    """
    Parse text received from Almanak HÍ endpoint into usable dict.
    """
    data: _SOLAR_DICT_TYPE = {}
    city: Optional[str] = None
    month: Optional[int] = None

    for line in text:
        city_re = re.match(_ALMANAK_CITY_REGEX, line)
        if city_re:
            # Matched line containing name of city
            city, lat, lon = city_re.groups()
            city = capitalize_placename((city or "").lower())

            # Initialize dict for Icelandic city (place)
            data[city] = {"pos": _convert_dms_lat_lon_to_decimal(lat, lon)}

        else:
            sun_re = re.match(_ALMANAK_SUNPOS_REGEX, line)
            if sun_re and city is not None:
                # Matched line containing times of solar positions
                if sun_re.group(1) != " - ":
                    # New month started
                    month_str = sun_re.group(1).lower()
                    month = MONTH_ABBREV_ORDERED.index(month_str) + 1

                # Extract times of solar positions
                sun_pos: _SOLAR_ROW_TYPE = dict(
                    zip(
                        _ALMANAK_HI_COLUMNS,
                        (_parse_almanak_cell(cell) for cell in sun_re.groups()[2:]),
                    )
                )

                # Calculate solar midnight from solar noon
                # ("Hádegi" (solar noon) is never None)
                solar_noon: datetime.time = cast(
                    datetime.time, sun_pos[_SOLAR_POSITIONS.HÁDEGI]
                )
                solar_midnight = datetime.time(
                    hour=((solar_noon.hour + 12) % 24), minute=solar_noon.minute
                )
                sun_pos[_SOLAR_POSITIONS.MIÐNÆTTI] = solar_midnight

                # Add solar positions for city on a specific date
                date = datetime.date.today().replace(
                    month=cast(int, month), day=int(sun_re.group(2))
                )
                data[city][date] = sun_pos

    return data


_ALMANAK_HI_CACHE: TTLCache = TTLCache(maxsize=1, ttl=86400)


def _get_almanak_hi_data() -> Optional[_SOLAR_DICT_TYPE]:
    """Fetch solar calendar from Univeristy of Iceland."""
    data = cast(Optional[_SOLAR_DICT_TYPE], _ALMANAK_HI_CACHE.get("data"))

    if data:
        return data

    try:
        r = requests.get(_ALMANAK_HI_URL, timeout=10)
    except Exception as e:
        logging.warning(str(e))
        return None

    if r.status_code != 200:
        logging.warning(f"Received status {r.status_code} from Almanak HÍ")
        return None

    try:
        # Use beautiful soup to extract text from HTML response
        # and split on newlines
        text: List[str] = (
            BeautifulSoup(r.text, "html.parser")
            .get_text()
            .replace("\r\n", "\n")
            .split("\n")
        )

        data = _parse_almanak_hi_data(text)
        # Only cache valid data
        _ALMANAK_HI_CACHE["data"] = data

        return data
    except Exception as e:
        logging.warning(f"Error parsing Almanak HÍ response: {e}")

    return None


def _find_closest_city(data: _SOLAR_DICT_TYPE, loc: LatLonTuple) -> Optional[str]:
    """Find city closest to loc in data."""
    closest_city = None
    closest_distance = None

    for city_name, city_dict in data.items():
        dist = distance(loc, cast(LatLonTuple, city_dict["pos"]))

        if closest_distance is None or dist < closest_distance:
            closest_distance = dist
            closest_city = city_name

    return closest_city


def _answer_city_solar_data(
    data: _SOLAR_DICT_TYPE, sun_pos: _SOLAR_POS_ENUM, qdate: datetime.date, city: str
) -> AnswerTuple:
    """
    Create answer for a sun position in city/place on date qdate.
    City must be a key in data.
    """
    # Get closest date to qdate in data
    closest_date: datetime.date = sorted(
        (k for k in data[city] if isinstance(k, datetime.date)),
        key=lambda d: abs(d - qdate),
    )[0]

    voice: str = ""
    answer: str = ""

    today: datetime.date = datetime.date.today()
    when: str
    in_past: Optional[bool] = None
    if qdate == today:
        when = "í dag"
    elif qdate == today + datetime.timedelta(days=1):
        when = "á morgun"
        in_past = False
    elif qdate == today - datetime.timedelta(days=1):
        when = "í gær"
        in_past = True
    else:
        with changedlocale(category="LC_TIME"):
            when = qdate.strftime("%-d. %B")
            in_past = qdate < today

    if sun_pos == _SOLAR_POSITIONS.SÓLARHÆÐ:
        if in_past is None:
            is_will_was = "er"
        else:
            is_will_was = "var"

        degrees = cast(Union[int, float], data[city][closest_date][sun_pos])
        answer = f"Sólarhæð um hádegi {when} {is_will_was} um {sing_or_plur(float(degrees), 'gráða', 'gráður')}."

    else:
        time: Optional[datetime.time] = cast(
            Optional[datetime.time], data[city][closest_date][sun_pos]
        )

        if time:
            if in_past is None:
                in_past = time <= datetime.datetime.utcnow().time()

            # More specific answer when asking about today
            # (this morning/this evening/tonight/...)
            if when == "í dag":
                if time.hour >= 23 or time.hour <= 4:
                    when = "í nótt"
                elif 4 < time.hour <= 9:
                    when = "í morgun"
                elif 20 <= time.hour < 23:
                    when = "í kvöld"

            elif when == "á morgun" and time.hour <= 4:
                when = "í nótt"

            time_str = time.strftime("%-H:%M")
            format_ans = "{0} var um klukkan {1} {2}."

            if sun_pos == _SOLAR_POSITIONS.SÓLRIS:
                if in_past:
                    answer = f"Sólin reis um klukkan {time_str} {when}."
                else:
                    answer = f"Sólin rís um klukkan {time_str} {when}."

            elif sun_pos == _SOLAR_POSITIONS.SÓLARLAG:
                if in_past:
                    answer = f"Sólin settist um klukkan {time_str} {when}."
                else:
                    answer = f"Sólin sest um klukkan {time_str} {when}."

            else:
                answer = format_ans.format(_SOLAR_ENUM_TO_WORD[sun_pos], time_str, when)

        else:
            format_ans = "Það varð ekki {0} {1}."

            answer = format_ans.format(_SOLAR_ENUM_TO_WORD[sun_pos].lower(), when)

    if not in_past:
        answer = answer.replace("varð", "verður").replace("var", "verður")

    # Convert date ordinals to text for voice
    voice = numbers_to_ordinal(answer, case="þf", gender="kk")
    # Convert degrees to text for voice when asking about height of sun
    voice = floats_to_text(
        voice,
        gender="kvk",
        regex=r"(?<= )(\d?\d?\d\.)*\d+(,\d+)?(?= )",
        comma_null=False,
    )
    return {"answer": answer, "voice": voice}, answer, voice


def _get_answer(q: Query, result: Result) -> AnswerTuple:

    qdate: datetime.date = result.get("date", datetime.date.today())
    sun_pos: int = result.get("solar_position")

    if (
        qdate == datetime.date.today()
        and result.get("will_be")
        and sun_pos == _SOLAR_POSITIONS.MIÐNÆTTI
    ):
        # Just to fix wording of answer to queries such as "Hvenær verður miðnætti í nótt?".
        qdate += datetime.timedelta(days=1)

    city: Optional[str] = result.get("city")
    loc: Optional[LatLonTuple] = None

    # Fetch solar position data from cache or Almanak HÍ
    data: Optional[_SOLAR_DICT_TYPE] = _get_almanak_hi_data()

    if data is None:
        return gen_answer("Ekki tókst að sækja upplýsingar um sólargang.")

    if city:
        # City specified
        if city in data:
            return _answer_city_solar_data(data, sun_pos, qdate, city)

        if city not in ICE_PLACENAME_BLACKLIST:
            # Search Icelandic cities/places
            possible_cities = placename_lookup(city)
            if possible_cities:
                city_dict = possible_cities[0]
                loc = (
                    cast(float, city_dict.get("lat_wgs84")),
                    cast(float, city_dict.get("long_wgs84")),
                )

                city = _find_closest_city(data, loc)
                if city is not None and city in data:
                    return _answer_city_solar_data(data, sun_pos, qdate, city)

        return gen_answer("Ég þekki ekki til sólargangs þar.")

    if q.location:
        # No city specified, use user location
        loc = q.location

        if in_iceland(loc):
            city = _find_closest_city(data, loc)

            if city is not None and city in data:
                return _answer_city_solar_data(data, sun_pos, qdate, city)

        return gen_answer("Ég þekki ekki til sólargangs utan Íslands.")

    # No city specified, user location unavailable
    # Default to Reykjavík
    city = "Reykjavík"
    if city not in data:
        # Get first key in data
        city = list(data.keys())[0]

    return _answer_city_solar_data(data, sun_pos, qdate, city)


def sentence(state: QueryStateDict, result: Result) -> None:
    """Called when sentence processing is complete"""
    q: Query = state["query"]

    if "qtype" in result and result.qtype == _SUN_QTYPE and "solar_position" in result:
        # Successfully matched this query type, we're handling it...
        q.set_qtype(result.qtype)

        answer: AnswerTuple = _get_answer(q, result)

        q.set_source("Háskóli Íslands")
        # Set query answer
        q.set_answer(*answer)
        return

    # This module did not understand the query
    q.set_error("E_QUERY_NOT_UNDERSTOOD")
