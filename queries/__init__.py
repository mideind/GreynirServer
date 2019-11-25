"""

    Reynir: Natural language processing for Icelandic

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


    Queries folder
    This is the location to put custom query responders.

    This file contains various shared functions used by the query modules.

"""

import logging
import requests
import json
import os
import re
import locale
from tzwhere import tzwhere
from pytz import country_timezones
from geo import country_name_for_isocode, iceprep4cc
from reynir.bindb import BIN_Db
from settings import changedlocale


def natlang_seq(words):
    """ Generate an Icelandic natural language sequence of words e.g.
        "A og B", "A, B og C", "A, B, C og D". No Oxford comma :) """
    if not words:
        return ""
    if len(words) == 1:
        return words[0]
    return "{0} og {1}".format(", ".join(words[:-1]), words[-1])


def nom2dat(w):
    """ Look up dative form of a noun in BÍN, try
        lowercase if capitalized form is not found. """
    if w:
        b = BIN_Db()
        bin_res = b.lookup_dative(w, cat="no")
        if not bin_res and not w.islower():
            bin_res = b.lookup_dative(w.lower(), cat="no")
        if bin_res:
            return bin_res[0].ordmynd
    return w


# Neutral gender form of numbers
NUMBERS_NEUTRAL = {
    "1": "eitt",
    "2": "tvö",
    "3": "þrjú",
    "4": "fjögur",
    "21": "tuttugu og eitt",
    "22": "tuttugu og tvö",
    "23": "tuttugu og þrjú",
    "24": "tuttugu og fjögur",
    "31": "þrjátíu og eitt",
    "32": "þrjátíu og tvö",
    "33": "þrjátíu og þrjú",
    "34": "þrjátíu og fjögur",
    "41": "fjörutíu og eitt",
    "42": "fjörutíu og tvö",
    "43": "fjörutíu og þrjú",
    "44": "fjörutíu og fjögur",
    "51": "fimmtíu og eitt",
    "52": "fimmtíu og tvö",
    "53": "fimmtíu og þrjú",
    "54": "fimmtíu og fjögur",
    "61": "sextíu og eitt",
    "62": "sextíu og tvö",
    "63": "sextíu og þrjú",
    "64": "sextíu og fjögur",
    "71": "sjötíu og eitt",
    "72": "sjötíu og tvö",
    "73": "sjötíu og þrjú",
    "74": "sjötíu og fjögur",
    "81": "áttatíu og eitt",
    "82": "áttatíu og tvö",
    "83": "áttatíu og þrjú",
    "84": "áttatíu og fjögur",
    "91": "níutíu og eitt",
    "92": "níutíu og tvö",
    "93": "níutíu og þrjú",
    "94": "níutíu og fjögur",
    "101": "hundrað og eitt",
    "102": "hundrað og tvö",
    "103": "hundrað og þrjú",
    "104": "hundrað og fjögur",
}

HUNDREDS = ("tvö", "þrjú", "fjögur", "fimm", "sex", "sjö", "átta", "níu")


def numbers_to_neutral(s):
    """ Convert integers within the string s to voice
        representations using neutral gender, i.e.
        4 -> 'fjögur', 21 -> 'tuttugu og eitt' """

    def convert(m):
        match = m.group(0)
        n = int(match)
        prefix = ""
        if 121 <= n <= 999 and 1 <= (n % 10) <= 4 and not 11 <= (n % 100) <= 14:
            # A number such as 104, 223, 871 (but not 111 or 614)
            if n // 100 == 1:
                prefix = "hundrað "
            else:
                prefix = HUNDREDS[n // 100 - 2] + " hundruð "
            n %= 100
            if n <= 4:
                # 'tvö hundruð og eitt', 'sjö hundruð og fjögur'
                prefix += "og "
            match = str(n)
        return prefix + NUMBERS_NEUTRAL.get(match, match)

    return re.sub(r"(\d+)", convert, s)


def is_plural(num):
    """ Determine whether an Icelandic word following a given number
         should be plural or not, e.g. "21 maður" vs. "22 menn" vs. "11 menn" """
    sn = str(num)
    return not (sn.endswith("1") and not sn.endswith("11"))


def country_desc(cc):
    """ Generate Icelandic description string of being in a particular country
        with correct preposition and case e.g. 'á Spáni', 'í Þýskalandi' """
    cn = country_name_for_isocode(cc)
    prep = iceprep4cc(cc)
    return "{0} {1}".format(prep, nom2dat(cn))


def query_json_api(url):
    """ Request the URL, expecting a json response which is 
        parsed and returned as a Python data structure. """

    # Send request
    try:
        r = requests.get(url)
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


# The Google API identifier (you must obtain your
# own key if you want to use this code)
_API_KEY = ""
_API_KEY_PATH = os.path.join(
    os.path.dirname(__file__), "..", "resources", "GoogleServerKey.txt"
)


def _get_API_key():
    """ Read Google API key from file """
    global _API_KEY
    if not _API_KEY:
        try:
            # You need to obtain your own key and put it in
            # _API_KEY_PATH if you want to use this code.
            with open(_API_KEY_PATH) as f:
                _API_KEY = f.read().rstrip()
        except FileNotFoundError:
            _API_KEY = ""
    return _API_KEY


_MAPS_API_COORDS_URL = "https://maps.googleapis.com/maps/api/geocode/json?latlng={0},{1}&key={2}&language=is&region=is"


def query_geocode_api_coords(lat, lon):
    """ Look up coordinates in Google's geocode API. """
    # Load API key
    key = _get_API_key()
    if not key:
        # No key, can't query Google location API
        logging.warning("No API key for location lookup")
        return None

    # Send API request
    url = _MAPS_API_COORDS_URL.format(lat, lon, key)
    return query_json_api(url)


_MAPS_API_ADDR_URL = "https://maps.googleapis.com/maps/api/geocode/json?address={0}&key={1}&language=is&region=is"


def query_geocode_api_addr(addr):
    """ Look up address in Google's geocode API. """
    # Load API key
    key = _get_API_key()
    if not key:
        # No key, can't query the API
        logging.warning("No API key for location lookup")
        return None

    # Send API request
    url = _MAPS_API_ADDR_URL.format(addr, key)
    return query_json_api(url)


_MAPS_API_DISTANCE_URL = "https://maps.googleapis.com/maps/api/distancematrix/json?units=metric&origins={0}&destinations={1}&mode={2}&key={3}&language=is&region=is"


def query_traveltime_api(startloc, endloc, mode="walking"):
    """ Look up travel time between two places, given a particular mode
        of transportation, e.g. "walking", "driving, "bicycling", "transit".
        The location arguments can be names, to be resolved by the API, or
        a tuple of coordinates, e.g. (64.156742, -21.949426)
        Uses Google Maps' Distance Matrix API. For details, see:
        https://developers.google.com/maps/documentation/distance-matrix/intro """
    # Load API key
    key = _get_API_key()
    if not key:
        # No key, can't query the API
        logging.warning("No API key for travel time lookup")
        return None

    p1 = "{0},{1}".format(*startloc) if type(startloc) is tuple else startloc
    p2 = "{0},{1}".format(*endloc) if type(endloc) is tuple else endloc

    # Send API request
    url = _MAPS_API_DISTANCE_URL.format(p1, p2, mode, key)
    return query_json_api(url)


def strip_trailing_zeros(num_str):
    """ Strip trailing decimal zeros from an Icelandic-style
        float num string, e.g. "17,0" -> "17". """
    if "," in num_str:
        return num_str.rstrip("0").rstrip(",")
    return num_str


def format_icelandic_float(fp_num):
    """ Convert number to Icelandic decimal format. """
    with changedlocale(category="LC_NUMERIC"):
        res = locale.format_string("%.2f", fp_num, grouping=True).replace(" ", ".")
        return strip_trailing_zeros(res)


def gen_answer(a):
    return dict(answer=a), a, a


_TZW = None


def tzwhere_singleton():
    """ Lazy-load location/timezone database. """
    global _TZW
    if not _TZW:
        _TZW = tzwhere.tzwhere(forceTZ=True)
    return _TZW


def timezone4loc(loc, fallback=None):
    """ Returns timezone string given a tuple of coordinates. 
        Fallback argument should be an ISO country code."""
    if loc:
        return tzwhere_singleton().tzNameAt(loc[0], loc[1], forceTZ=True)
    if fallback and fallback in country_timezones:
        return country_timezones[fallback][0]
    return None
