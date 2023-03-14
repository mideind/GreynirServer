"""

    Greynir: Natural language processing for Icelandic

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


    This file contains various utility functions used by the query modules.

"""

from __future__ import annotations

from typing import (
    Any,
    Mapping,
    Optional,
    List,
    Dict,
    Sequence,
    Tuple,
    Union,
    cast,
)
from typing_extensions import TypedDict

import logging
import requests
import json
import re
import locale
from urllib.parse import urlencode
from functools import lru_cache

from timezonefinder import TimezoneFinder
from pytz import country_timezones

from geo import country_name_for_isocode, iceprep_for_cc, LatLonTuple
from speech.trans.num import number_to_text, float_to_text
from reynir import NounPhrase
from tree import Node
from settings import changedlocale
from utility import (
    QUERIES_GRAMMAR_DIR,
    QUERIES_JS_DIR,
    QUERIES_UTIL_GRAMMAR_DIR,
    read_api_key,
)


# Type definitions
AnswerTuple = Tuple[Dict[str, str], str, str]
JsonResponse = Union[None, List[Any], Dict[str, Any]]


class OpeningHoursDict(TypedDict):
    """Opening hours type data structure"""

    open_now: bool
    weekday_text: List[str]


class LatLonDict(TypedDict):
    """LatLon type data structure"""

    lat: float
    lng: float


class GeometryDict(TypedDict):
    """Geometry type data structure"""

    location: LatLonDict


class PlaceDict(TypedDict):
    """Place type data structure"""

    place_id: str
    opening_hours: OpeningHoursDict
    formatted_address: str
    geometry: GeometryDict


class QueryPlacesDict(TypedDict):
    """Result from query_places_api() call"""

    status: str
    candidates: List[PlaceDict]


MONTH_ABBREV_ORDERED: Sequence[str] = (
    "jan",
    "feb",
    "mar",
    "apr",
    "maí",
    "jún",
    "júl",
    "ágú",
    "sep",
    "okt",
    "nóv",
    "des",
)


def natlang_seq(words: List[str], oxford_comma: bool = False) -> str:
    """Generate an Icelandic natural language sequence of words
    e.g. "A og B", "A, B og C", "A, B, C og D"."""
    if not words:
        return ""
    if len(words) == 1:
        return words[0]
    return "{0}{1} og {2}".format(
        ", ".join(words[:-1]), "," if oxford_comma and len(words) > 2 else "", words[-1]
    )


def nom2dat(w: str) -> str:
    """Look up the dative of an Icelandic noun given its nominative form."""
    try:
        d = NounPhrase(w).dative
        return d or w
    except Exception:
        pass
    return w


def is_plural(num: Union[str, int, float]) -> bool:
    """Determine whether an Icelandic word following a given number should be
    plural or not, e.g. "21 maður", "22 menn", "1,1 kílómetri", "11 menn" etc.
    Accepts string, float or int as argument."""
    sn = str(num)
    return not (sn.endswith("1") and not sn.endswith("11"))


def sing_or_plur(num: Union[int, float], sing: str, pl: str) -> str:
    """Utility function that returns a formatted string w. Icelandic number and a subsequent
    singular or plural noun, as appropriate, e.g. "1 einstaklingur", "2 einstaklingar",
    "21 einstaklingur" etc. Accepts both floats and ints as first argument."""
    return f"{iceformat_float(num)} {pl if is_plural(num) else sing}"


# The following needs to include at least nominative and dative forms of number words
_NUMBER_WORDS: Mapping[str, float] = {
    "núll": 0,
    "hálfur": 0.5,
    "hálfum": 0.5,
    "hálf": 0.5,
    "hálfri": 0.5,
    "hálft": 0.5,
    "hálfu": 0.5,
    "einn": 1,
    "einum": 1,
    "ein": 1,
    "einni": 1,
    "eitt": 1,
    "einu": 1,
    "tveir": 2,
    "tveim": 2,
    "tveimur": 2,
    "tvær": 2,
    "tvö": 2,
    "þrír": 3,
    "þrem": 3,
    "þremur": 3,
    "þrjár": 3,
    "þrjú": 3,
    "fjórir": 4,
    "fjórum": 4,
    "fjórar": 4,
    "fjögur": 4,
    "fimm": 5,
    "sex": 6,
    "sjö": 7,
    "átta": 8,
    "níu": 9,
    "tíu": 10,
    "ellefu": 11,
    "tólf": 12,
    "þrettán": 13,
    "fjórtán": 14,
    "fimmtán": 15,
    "sextán": 16,
    "sautján": 17,
    "átján": 18,
    "nítján": 19,
    "tuttugu": 20,
    "þrjátíu": 30,
    "fjörutíu": 40,
    "fimmtíu": 50,
    "sextíu": 60,
    "sjötíu": 70,
    "áttatíu": 80,
    "níutíu": 90,
    "hundrað": 100,
    "þúsund": 1000,
    "milljón": 1e6,
    "milljarður": 1e9,
}


def parse_num(node: Node, num_str: str) -> float:
    """Parse Icelandic number string to float or int.
    TODO: This needs to be a more capable, generic function. There are
    several mildly differing implementions in various query modules."""

    # Hack to handle the word "eina" being identified as f. name "Eina"
    if num_str in ("Eina", "Einu"):
        return 1.0

    # If we have a number token as a direct child,
    # return its numeric value directly
    num = None if node.child is None else node.child.contained_number
    if num is not None:
        return float(num)
    try:
        # Handle numbers with Icelandic decimal places ("17,2")
        # and potentially thousands separators as well
        num_str = num_str.replace(".", "")
        if re.search(r"^\d+,\d+", num_str):
            num = float(num_str.replace(",", "."))
        # Handle digits ("17")
        else:
            num = float(num_str)
    except ValueError:
        # Handle number words ("sautján")
        num = _NUMBER_WORDS.get(num_str)
        if num is not None:
            num = float(num)
    except Exception as e:
        logging.warning("Unexpected exception: {0}".format(e))
        raise
    return num or 0.0


def country_desc(cc: str) -> str:
    """Generate Icelandic description of being in a particular country
    with correct preposition and case e.g. 'á Spáni', 'í Þýskalandi'."""
    cn = country_name_for_isocode(cc)
    if cn is None:
        return f"í landinu '{cc}'"
    prep = iceprep_for_cc(cc)
    return f"{prep} {nom2dat(cn)}"


# This could be done at runtime using BÍN lookup, but this is
# faster, cleaner, and allows for reuse outside the codebase.
_TIMEUNIT_NOUNS = {
    "w": (["vika", "viku", "viku", "viku"], ["vikur", "vikur", "vikum", "vikna"]),
    "d": (["dagur", "dag", "degi", "dags"], ["dagar", "daga", "dögum", "daga"]),
    "h": (
        ["klukkustund", "klukkustund", "klukkustund", "klukkustundar"],
        ["klukkustundir", "klukkustundir", "klukkustundum", "klukkustunda"],
    ),
    "m": (
        ["mínúta", "mínútu", "mínútu", "mínútu"],
        ["mínútur", "mínútur", "mínútum", "mínútna"],
    ),
    "s": (
        ["sekúnda", "sekúndu", "sekúndu", "sekúndu"],
        ["sekúndur", "sekúndur", "sekúndum", "sekúndna"],
    ),
}

_TIMEUNIT_INTERVALS = (
    ("w", 604800),  # 60 * 60 * 24 * 7
    ("d", 86400),  # 60 * 60 * 24
    ("h", 3600),  # 60 * 60
    ("m", 60),
    ("s", 1),
)

_CASE_ABBR = ["nf", "þf", "þgf", "ef"]


def time_period_desc(
    seconds: int,
    *,
    case: str = "nf",
    omit_seconds: bool = True,
    num_to_str: bool = False,
) -> str:
    """Generate Icelandic description of the length of a given time
    span, e.g. "4 dagar, 6 klukkustundir og 21 mínúta."""
    assert case in _CASE_ABBR
    cidx = _CASE_ABBR.index(case)
    # Round to nearest minute if omitting second precision
    seconds = ((seconds + 30) // 60) * 60 if omit_seconds else seconds

    # Break it down to weeks, days, hours, mins, secs.
    result: List[str] = []
    for unit, count in _TIMEUNIT_INTERVALS:
        value = seconds // count
        if value:
            seconds -= value * count
            plidx = 1 if is_plural(value) else 0
            icename = _TIMEUNIT_NOUNS[unit][plidx][cidx]
            svalue: Union[int, str] = value
            if num_to_str:
                # Convert number to spoken text
                svalue = number_to_text(
                    value, case=case, gender="kk" if unit == "d" else "kvk"
                )
            result.append(f"{svalue} {icename}")

    return natlang_seq(result)


_METER_NOUN = (
    ["metri", "metra", "metra", "metra"],
    ["metrar", "metra", "metrum", "metra"],
)


def distance_desc(
    km_dist: float,
    *,
    case: str = "nf",
    in_metres: float = 1.0,
    abbr: bool = False,
    num_to_str: bool = False,
) -> str:
    """Generate an Icelandic description of distance in km/m w. option to
    specify case, abbreviations, cutoff for returning descr. in metres."""
    assert case in _CASE_ABBR
    cidx = _CASE_ABBR.index(case)

    # E.g. 7,3 kílómetrar
    if km_dist >= in_metres:
        rounded_km = round(km_dist, 1 if km_dist < 10 else 0)
        dist = iceformat_float(rounded_km)
        plidx = 1 if is_plural(rounded_km) else 0
        unit_long = "kíló" + _METER_NOUN[plidx][cidx]
        unit = "km" if abbr else unit_long
        sdist = dist
        if num_to_str:
            sdist = float_to_text(rounded_km, case=case, gender="kk")
    # E.g. 940 metrar
    else:
        # Round to nearest 10
        def rnd(n: int) -> int:
            return ((n + 5) // 10) * 10

        rounded_dist = rnd(int(km_dist * 1000.0))
        plidx = 1 if is_plural(rounded_dist) else 0
        unit_long = _METER_NOUN[plidx][cidx]
        unit = "m" if abbr else unit_long
        sdist = str(rounded_dist)
        if num_to_str:
            sdist = number_to_text(rounded_dist, case=case, gender="kk")

    return f"{sdist} {unit}"


_KRONA_NOUN = (
    ["króna", "krónu", "krónu", "krónu"],
    ["krónur", "krónur", "krónum", "króna"],
)


def krona_desc(amount: float, case: str = "nf") -> str:
    """Generate description of an amount in krónas, e.g.
    "213,5 krónur", "361 króna", "70,11 krónur", etc."""
    assert case in _CASE_ABBR
    cidx = _CASE_ABBR.index(case)
    plidx = 1 if is_plural(amount) else 0
    return "{0} {1}".format(iceformat_float(amount), _KRONA_NOUN[plidx][cidx])


def strip_trailing_zeros(num_str: str) -> str:
    """Strip trailing decimal zeros from an Icelandic-style
    float num string, e.g. "17,0" -> "17"."""
    if "," in num_str:
        return num_str.rstrip("0").rstrip(",")
    return num_str


def iceformat_float(
    fp_num: float, decimal_places: int = 2, strip_zeros: bool = True
) -> str:
    """Convert number to Icelandic decimal format string."""
    with changedlocale(category="LC_NUMERIC"):
        fmt = "%.{0}f".format(decimal_places)
        res = locale.format_string(fmt, float(fp_num), grouping=True).replace(" ", ".")
        return strip_trailing_zeros(res) if strip_zeros else res


def gen_answer(a: str) -> AnswerTuple:
    """Convenience function for query modules: response, answer, voice answer"""
    return dict(answer=a), a, a


def query_json_api(
    url: str, headers: Optional[Dict[str, str]] = None, *, timeout: int = 10
) -> JsonResponse:
    """Request the URL, expecting a JSON response which is
    parsed and returned as a Python data structure."""

    # Send request
    try:
        r = requests.get(url, headers=headers, timeout=timeout)
    except Exception as e:
        logging.warning(str(e))
        return None

    # Verify that status is OK
    if r.status_code != 200:
        logging.warning("Received status {0} from API server".format(r.status_code))
        return None

    # Parse json API response
    try:
        res = json.loads(r.text)
        return res
    except Exception as e:
        logging.warning("Error parsing JSON API response: {0}".format(e))
    return None


_MAPS_API_COORDS_URL = (
    "https://maps.googleapis.com/maps/api/geocode/json"
    "?latlng={0},{1}&key={2}&language=is&region=is"
)


def query_geocode_api_coords(lat: float, lon: float) -> Optional[Dict[str, Any]]:
    """Look up coordinates in Google's geocode API."""
    # Load API key
    key = read_api_key("GoogleServerKey")
    if not key:
        # No key, can't query Google location API
        logging.warning("No API key for coordinates lookup")
        return None

    # Send API request
    return cast(
        Optional[Dict[str, Any]],
        query_json_api(_MAPS_API_COORDS_URL.format(lat, lon, key)),
    )


_MAPS_API_ADDR_URL = (
    "https://maps.googleapis.com/maps/api/geocode/json"
    "?address={0}&key={1}&language=is&region=is"
)


def query_geocode_api_addr(addr: str) -> Optional[Dict[str, Any]]:
    """Look up address in Google's geocode API."""
    # Load API key
    key = read_api_key("GoogleServerKey")
    if not key:
        # No key, can't query the API
        logging.warning("No API key for address lookup")
        return None

    # Send API request
    url = _MAPS_API_ADDR_URL.format(addr, key)
    return cast(Optional[Dict[str, Any]], query_json_api(url))


_MAPS_API_TRAVELTIME_URL = (
    "https://maps.googleapis.com/maps/api/distancematrix/json"
    "?units=metric&origins={0}&destinations={1}&mode={2}&key={3}&language=is&region=is"
)

_TRAVEL_MODES = frozenset(("walking", "driving", "bicycling", "transit"))


def query_traveltime_api(
    startloc: Union[str, LatLonTuple],
    endloc: Union[str, LatLonTuple],
    mode: str = "walking",
) -> Optional[Dict[str, Any]]:
    """Look up travel time between two places, given a particular mode
    of transportation, i.e. one of the modes in _TRAVEL_MODES.
    The location arguments can be names, to be resolved by the API, or
    a tuple of coordinates, e.g. (64.156742, -21.949426)
    Uses Google Maps' Distance Matrix API. For more info, see:
    https://developers.google.com/maps/documentation/distance-matrix/intro
    """
    assert mode in _TRAVEL_MODES

    # Load API key
    key = read_api_key("GoogleServerKey")
    if not key:
        # No key, can't query the API
        logging.warning("No API key for travel time lookup")
        return None

    # Format query string args
    p1 = "{0},{1}".format(*startloc) if isinstance(startloc, tuple) else startloc
    p2 = "{0},{1}".format(*endloc) if isinstance(endloc, tuple) else endloc

    # Send API request
    url = _MAPS_API_TRAVELTIME_URL.format(p1, p2, mode, key)
    return cast(Optional[Dict[str, Any]], query_json_api(url))


_PLACES_API_URL = (
    "https://maps.googleapis.com/maps/api/place/findplacefromtext/json?{0}"
)

_PLACES_LOCBIAS_RADIUS = 5000  # Metres


def query_places_api(
    placename: str,
    userloc: Optional[LatLonTuple] = None,
    radius: float = _PLACES_LOCBIAS_RADIUS,
    fields: Optional[str] = None,
) -> Optional[QueryPlacesDict]:
    """Look up a placename in Google's Places API. For details, see:
    https://developers.google.com/places/web-service/search"""

    if not fields:
        # Default fields requested from API
        fields = "place_id,opening_hours,geometry/location,formatted_address"

    # Load API key
    key = read_api_key("GoogleServerKey")
    if not key:
        # No key, can't query the API
        logging.warning("No API key for Google Places lookup")
        return None

    # Generate query string
    qdict = {
        "input": placename,
        "inputtype": "textquery",
        "fields": fields,
        "key": key,
        "language": "is",
        "region": "is",
    }
    if userloc:
        qdict["locationbias"] = "circle:{0}@{1},{2}".format(
            radius, userloc[0], userloc[1]
        )
    qstr = urlencode(qdict)

    # Send API request
    url = _PLACES_API_URL.format(qstr)
    return cast(Optional[QueryPlacesDict], query_json_api(url))


_PLACEDETAILS_API_URL = "https://maps.googleapis.com/maps/api/place/details/json?{0}"


@lru_cache(maxsize=32)
def query_place_details(
    place_id: str, fields: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Look up place details by ID in Google's Place Details API. If "fields"
    parameter is omitted, *all* fields are returned. For details, see
    https://developers.google.com/places/web-service/details"""

    # Load API key
    key = read_api_key("GoogleServerKey")
    if not key:
        # No key, can't query the API
        logging.warning("No API key for Google Place Details lookup")
        return None

    # Generate query string
    qdict = {"place_id": place_id, "key": key, "language": "is"}
    if fields:
        qdict["fields"] = fields
    qstr = urlencode(qdict)

    # Send API request
    url = _PLACEDETAILS_API_URL.format(qstr)
    return cast(Optional[Dict[str, Any]], query_json_api(url))


_tsw: Optional[TimezoneFinder] = None


def _tzfinder_singleton() -> TimezoneFinder:
    """Lazy-load location/timezone database."""
    global _tsw
    if _tsw is None:
        _tsw = TimezoneFinder()
    return _tsw


def timezone4loc(
    loc: Optional[LatLonTuple], fallback: Optional[str] = None
) -> Optional[str]:
    """Returns timezone string given a tuple of coordinates.
    Fallback argument should be a 2-char ISO 3166 country code."""
    if loc is not None:
        return _tzfinder_singleton().timezone_at(lat=loc[0], lng=loc[1])
    if fallback and fallback in country_timezones:
        return country_timezones[fallback][0]
    return None


@lru_cache(maxsize=32)
def read_jsfile(filename: str) -> str:
    """
    Read and return a minified JavaScript (.js)
    file from the QUERY_JS_DIR folder.
    """
    from rjsmin import jsmin  # type: ignore

    jsfile = QUERIES_JS_DIR / filename
    return cast(str, jsmin(jsfile.read_text()))


def read_grammar_file(filename: str, **format_kwargs: str) -> str:
    """
    Read and return a grammar file from the QUERY_GRAMMAR_DIR folder.
    Optionally specify keyword arguments for str.format() call
    """
    gfile = QUERIES_GRAMMAR_DIR / f"{filename}.grammar"

    grammar = gfile.read_text()
    if len(format_kwargs) > 0:
        grammar = grammar.format(**format_kwargs)
    return grammar


def read_utility_grammar_file(filename: str, **format_kwargs: str) -> str:
    """
    Read and return a grammar file from the QUERY_UTIL_GRAMMAR_DIR folder.
    Optionally specify keyword arguments for str.format() call
    """
    gfile = QUERIES_UTIL_GRAMMAR_DIR / f"{filename}.grammar"

    grammar = gfile.read_text()
    if len(format_kwargs) > 0:
        grammar = grammar.format(**format_kwargs)
    return grammar
