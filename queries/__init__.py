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
from tzwhere import tzwhere
from pytz import country_timezones
from geo import country_name_for_isocode, iceprep4cc
from reynir.bindb import BIN_Db


def natlang_seq(words):
    """ Generate an Icelandic natural language sequence of words e.g.
        "A og B", "A, B og C", "A, B, C og D". No Oxford comma :) """
    if len(words) == 1:
        return words[0]
    elif len(words) >= 2:
        return "{0} og {1}".format(", ".join(words[:-1]), words[-1])


def nom2dat(w):
    """ Look up dative form of a noun in BÍN, try
        lowercase if capitalized form not found. """
    if w:
        b = BIN_Db()
        bin_res = b.lookup_dative(w, cat="no")
        if not bin_res and not w.islower():
            bin_res = b.lookup_dative(w.lower(), cat="no")
        if bin_res:
            return bin_res[0].ordmynd
    return w


def country_desc(cc):
    """ Generate description string of being in a particular country
        with correct preposition and case e.g. 'á Spáni'. """
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


_MAPS_API_COORDS_URL = "https://maps.googleapis.com/maps/api/geocode/json?latlng={0},{1}&key={2}&language=is"


def query_geocode_API_coords(lat, lon):
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


_MAPS_API_ADDR_URL = (
    "https://maps.googleapis.com/maps/api/geocode/json?address={0}&key={1}&language=is"
)


def query_geocode_API_addr(addr):
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


def strip_trailing_zeros(num_str):
    """ Strip trailing decimal zeros from an Icelandic-style
        float num string, e.g. "17,0" -> "17". """
    return num_str.rstrip("0").rstrip(",")


def format_icelandic_float(fp_num):
    """ Convert number to Icelandic decimal format. """
    res = "{0:.2f}".format(fp_num).replace(".", ",")
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
