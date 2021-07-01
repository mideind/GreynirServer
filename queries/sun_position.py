"""

    Greynir: Natural language processing for Icelandic

    Example of a grammar query processor module.

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


    This module handles queries regarding time of sunrise/sunset.

"""
from typing import Dict, List, Tuple, Optional, Union
from tree import Result, Node
from query import Query, QueryStateDict
from queries import AnswerTuple, LatLonTuple, MONTHS_ABBR, gen_answer

import datetime
import random
import re
import requests
from bs4 import BeautifulSoup
from cachetools import cached, TTLCache
from settings import changedlocale
from geo import (
    distance,
    iceprep_for_placename,
    in_iceland,
    capitalize_placename,
    ICE_PLACENAME_BLACKLIST,
)
from iceaddr import placename_lookup


# Indicate that this module wants to handle parse trees for queries,
# as opposed to simple literal text strings
HANDLE_TREE = True

# The grammar nonterminals this module wants to handle
QUERY_NONTERMINALS = {"QSunQuery"}

_SUN_QTYPE = "SunPosition"

TOPIC_LEMMAS = [
    "birting",
    "dagsetur",
    "dögun",
    "hádegi",
    "miðnætti",
    "myrkur",
    "sólarhæð",
    "sólarlag",
    "sólarupprás",
    "sólris",
    "sólsetur",
    "sól",
]


def help_text(lemma: str) -> str:
    """Help text to return when query.py is unable to parse a query but
    one of the above lemmas is found in it"""
    return "Ég get svarað ef þú spyrð til dæmis: {0}?".format(
        random.choice(
            (
                "Hvenær reis sólin í morgun",
                "Hvenær er sólsetur í kvöld",
                "Hvenær rís sólin á morgun",
            )
        )
    )


# The context-free grammar for the queries recognized by this plug-in module
GRAMMAR = """

Query →
    QSunQuery '?'?

QSunQuery →
    QSunWhen QSunPositions QSunLocation? QSunDate? QSunLocation?
    | QSunSunheight

QSunWhen →
    "hvenær" | "klukkan" "hvað"

QSunIsWillWas →
    'vera' | 'verða'


QSunSunheight →
    "hver" QSunIsWillWas QSunSólarhæð QSunDate?

QSunSólarhæð →
    'sólarhæð'
    | "hæð" 'sól'

QSunPositions →
    QSunMiðnætti
    | QSunDögun
    | QSunBirting
    | QSunSólris
    | QSunHádegi
    | QSunSólarlag
    | QSunMyrkur
    | QSunDagsetur

QSunMiðnætti →
    QSunIsWillWas "miðnætti"

QSunDögun →
    QSunIsWillWas "dögun"

QSunBirting →
    QSunIsWillWas "birting"
    | "mun" "birta"

QSunSólris →
    'rísa' "sólin"
    | "mun" "sólin" "rísa"
    | QSunIsWillWas "sólarupprás"

QSunHádegi →
    QSunIsWillWas "hádegi"

QSunSólarlag →
    "sest" "sólin"
    | "mun" "sólin" "setjast"
    | QSunIsWillWas "sólarlag"

QSunMyrkur →
    QSunIsWillWas "myrkur"

QSunDagsetur →
    QSunIsWillWas "dagsetur"


QSunDate →
    QSunToday
    | QSunYesterday
    | QSunTomorrow
    # TODO: Arbitrary date

QSunToday →
    "í" "dag"

QSunYesterday →
    "í_gær"

QSunTomorrow →
    "á_morgun"


QSunLocation →
    QSunCapitalRegion
    | QSunInArbitraryLocation

QSunCapitalRegion →
    "á" "höfuðborgarsvæðinu" | "fyrir" "höfuðborgarsvæðið"
    | "í" "reykjavík" | "fyrir" "reykjavík"
    | "í" "höfuðborginni" | "fyrir" "höfuðborgina"
    | "á" "reykjavíkursvæðinu" | "fyrir" "reykjavíkursvæðið"
    | "í" "borginni" | "fyrir" "borgina"

QSunInArbitraryLocation →
    fs_þgf QSunArbitraryLocation

QSunArbitraryLocation →
    Nl_þgf

"""


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


def QSunQuery(node: Node, params: QueryStateDict, result: Result) -> None:
    # Set the query type
    result.qtype = _SUN_QTYPE


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
_ALMANAK_HI_COLUMNS: Tuple[_SOLAR_POS_ENUM] = (
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


_SOLAR_CELL_TYPE = Union[datetime.time, float, None]


def _parse_almanak_cell(pt_str: str) -> _SOLAR_CELL_TYPE:
    """
    Parse a cell in Almanak HÍ. Returns datetime.time for cells containing
    a timestamp, float for cells containing the solar height and None otherwise.
    Examples:
        '03 15' => datetime.time(3,15)
        '34,9'  => 34.9
        '     ' => None
    """
    if not pt_str.isspace():
        if " " in pt_str:
            # Column contains a time value, convert to datetime
            hour, minute = pt_str.split()
            return datetime.time(hour=int(hour) % 24, minute=int(minute) % 60)

        if "," in pt_str:
            # Column contains solar height at solar noon (in degrees)
            return float(pt_str.replace(",", "."))

    return None


_SOLAR_ROW_TYPE = Dict[int, _SOLAR_CELL_TYPE]
_SOLAR_DICT_TYPE = Dict[
    str, Dict[str, Union[LatLonTuple, Dict[datetime.date, _SOLAR_ROW_TYPE]]]
]


def _parse_almanak_hi_data(text: List[str]) -> _SOLAR_DICT_TYPE:
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
            city = capitalize_placename(city.lower())

            # Initialize dict for Icelandic city (place)
            data[city] = {"pos": _convert_dms_lat_lon_to_decimal(lat, lon)}

        else:
            sun_re = re.match(_ALMANAK_SUNPOS_REGEX, line)
            if sun_re and city is not None:
                # Matched line containing times of solar positions
                if sun_re.group(1) != " - ":
                    # New month started
                    month_str = sun_re.group(1).lower()
                    month = MONTHS_ABBR.index(month_str) + 1

                # Extract times of solar positions
                sun_pos: _SOLAR_ROW_TYPE = dict(
                    zip(
                        _ALMANAK_HI_COLUMNS,
                        (_parse_almanak_cell(cell) for cell in sun_re.groups()[2:]),
                    )
                )

                # Calculate solar midnight from solar noon
                solar_noon = sun_pos[_SOLAR_POSITIONS.HÁDEGI]
                solar_midnight = datetime.time(
                    hour=((solar_noon.hour + 12) % 24), minute=solar_noon.minute
                )
                sun_pos[_SOLAR_POSITIONS.MIÐNÆTTI] = solar_midnight

                # Add solar positions for city on a specific date
                date = datetime.date.today().replace(
                    month=month, day=int(sun_re.group(2))
                )
                data[city][date] = sun_pos

    return data


@cached(TTLCache(maxsize=1, ttl=86400))
def _get_almanak_hi_data() -> _SOLAR_DICT_TYPE:
    r = requests.get(_ALMANAK_HI_URL)
    # Use beautiful soup to extract text from HTML response
    # and split on newlines
    text: List[str] = (
        BeautifulSoup(r.text, "html.parser")
        .get_text()
        .replace("\r\n", "\n")
        .split("\n")
    )
    return _parse_almanak_hi_data(text)


def _find_closest_city(data: _SOLAR_DICT_TYPE, loc: LatLonTuple) -> str:
    """Find city closest to loc in data."""
    closest_city = None
    closest_distance = None

    for city_name, city_dict in data.items():
        dist = distance(loc, city_dict["pos"])

        if closest_distance is None or dist < closest_distance:
            closest_distance = dist
            closest_city = city_name

    return closest_city


def _answer_closest_solar_data(
    data: _SOLAR_DICT_TYPE, sun_pos: _SOLAR_POS_ENUM, qdate: datetime.date, city: str
) -> AnswerTuple:
    """
    Create answer for a sun position in city/place on date qdate.
    """
    # Get closest date to qdate in data
    closest_date: datetime.date = sorted(
        (k for k in data[city] if isinstance(k, datetime.date)),
        key=lambda d: abs(d - qdate),
    )[0]

    when: str
    in_past: Optional[bool] = None
    if qdate == datetime.date.today():
        when = "í dag"
    elif qdate == datetime.date.today() + datetime.timedelta(days=1):
        when = "á morgun"
        in_past = False
    elif qdate == datetime.date.today() - datetime.timedelta(days=1):
        when = "í gær"
        in_past = True
    else:
        with changedlocale(category="LC_TIME"):
            when = qdate.strftime("%-d. %B")
            in_past = qdate < datetime.date.today()

    if sun_pos == _SOLAR_POSITIONS.SÓLARHÆÐ:
        answer = f"Sólarhæð um hádegi {when} verður um {data[city][closest_date][sun_pos]} gráður."
        voice = answer

    else:
        time: Optional[datetime.time] = data[city][closest_date][sun_pos]
        if in_past is None:
            in_past = time <= datetime.datetime.now().time()

        if time:
            time_str = time.strftime("%H:%M")
            format_ans = "{0} var um klukkan {1} {2}."

            if sun_pos == _SOLAR_POSITIONS.DÖGUN:
                voice = answer = format_ans.format("Dögun", time_str, when)

            elif sun_pos == _SOLAR_POSITIONS.BIRTING:
                voice = answer = format_ans.format("Birting", time_str, when)

            elif sun_pos == _SOLAR_POSITIONS.SÓLRIS:
                if in_past:
                    voice = answer = f"Sólin reis klukkan {time_str} {when}."
                else:
                    voice = answer = f"Sólin rís klukkan {time_str} {when}."
            elif sun_pos == _SOLAR_POSITIONS.HÁDEGI:
                voice = answer = format_ans.format("Hádegi", time_str, when)

            elif sun_pos == _SOLAR_POSITIONS.SÓLARLAG:
                if in_past:
                    voice = answer = f"Sólin settist klukkan {time_str} {when}."
                else:
                    voice = answer = f"Sólin sest klukkan {time_str} {when}."

            elif sun_pos == _SOLAR_POSITIONS.MYRKUR:
                voice = answer = format_ans.format("Myrkur", time_str, when)

            elif sun_pos == _SOLAR_POSITIONS.DAGSETUR:
                voice = answer = format_ans.format("Dagsetur", time_str, when)

        else:
            format_ans = "Það varð ekki {0} {1}."
            if sun_pos == _SOLAR_POSITIONS.DÖGUN:
                voice = answer = format_ans.format("dögun", when)

            elif sun_pos == _SOLAR_POSITIONS.BIRTING:
                voice = answer = format_ans.format("birting", when)

            elif sun_pos == _SOLAR_POSITIONS.SÓLRIS:
                voice = answer = format_ans.format("sólris", when)

            elif sun_pos == _SOLAR_POSITIONS.HÁDEGI:
                voice = answer = format_ans.format("hádegi", when)

            elif sun_pos == _SOLAR_POSITIONS.SÓLARLAG:
                voice = answer = format_ans.format("sólarlag", when)

            elif sun_pos == _SOLAR_POSITIONS.MYRKUR:
                voice = answer = format_ans.format("myrkur", when)

            elif sun_pos == _SOLAR_POSITIONS.DAGSETUR:
                voice = answer = format_ans.format("dagsetur", when)

    if not in_past:
        voice = answer = answer.replace("varð", "verður").replace("var", "verður")

    # TODO: voicify string
    return {"answer": answer, "voice": voice}, answer, voice


def _get_answer(q: Query, result: Result) -> AnswerTuple:

    qdate: datetime.date = result.get("date", datetime.date.today())
    sun_pos: int = result.get("solar_position")
    city: Optional[str] = result.get("city")
    loc: Optional[LatLonTuple] = None

    # Fetch solar position data from cache or Almanak HÍ
    data: _SOLAR_DICT_TYPE = _get_almanak_hi_data()

    if city:
        # City specified
        if city in data:
            return _answer_closest_solar_data(data, sun_pos, qdate, city)

        if city not in ICE_PLACENAME_BLACKLIST:
            # Search Icelandic cities/places
            possible_cities = placename_lookup(city)
            if possible_cities:
                city_dict = possible_cities[0]
                loc = (city_dict.get("lat_wgs84"), city_dict.get("long_wgs84"))

                city = _find_closest_city(data, loc)
                return _answer_closest_solar_data(data, sun_pos, qdate, city)

        return gen_answer("Ég þekki ekki til sólargangs þar.")

    if q.location:
        # No city specified, use user location
        loc = q.location

        if in_iceland(loc):
            city = _find_closest_city(data, loc)
            return _answer_closest_solar_data(data, sun_pos, qdate, loc)

        return gen_answer("Ég þekki ekki til sólargangs utan Íslands.")

    # No city specified, user location unavailable
    # Default to Reykjavík
    return _answer_closest_solar_data(data, sun_pos, qdate, "Reykjavík")


def sentence(state: QueryStateDict, result: Result) -> None:
    """Called when sentence processing is complete"""
    q: Query = state["query"]

    if "qtype" in result and result.qtype == _SUN_QTYPE and "solar_position" in result:
        # Successfully matched this query type, we're handling it...
        q.set_qtype(result.qtype)

        answer: AnswerTuple = _get_answer(q, result)

        q.set_source("Háskóli Íslands")
        q.set_url(_ALMANAK_HI_URL)
        # Set query answer
        q.set_answer(*answer)
        return

    # This module did not understand the query
    q.set_error("E_QUERY_NOT_UNDERSTOOD")
