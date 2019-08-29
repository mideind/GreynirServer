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

    This file contains shared code used the query modules.

"""


import logging
import requests
import json
from tzwhere import tzwhere
from pytz import country_timezones


def query_json_api(url):
    """ Request the URL, expecting a json response which is 
        parsed and returned as a Python data structure """

    # Send request
    try:
        r = requests.get(url)
    except Exception as e:
        logging.warning(str(e))
        return None

    # Verify that status is OK
    if r.status_code != 200:
        logging.warning("Received status {0} from API server", r.status_code)
        return None

    # Parse json API response
    try:
        res = json.loads(r.text)
        return res
    except Exception as e:
        logging.warning("Error parsing JSON API response: {0}", str(e))

    return None


def strip_trailing_zeros(num_str):
    # Strip trailing decimal zeros from an Icelandic-style
    # float num string, e.g. "17,0" -> "17"
    return num_str.rstrip("0").rstrip(",")


def format_icelandic_float(fp_num):
    # Convert number to Icelandic decimal format
    res = "{0:.2f}".format(fp_num).replace(".", ",")
    return strip_trailing_zeros(res)


def gen_answer(a):
    return dict(answer=a), a, a


_TZW = None


def tzwhere_singleton(force=True):
    """ Lazy-load location/timezone database. The force argument 
        makes tzwhere return the closest timezone if location is
        outside all timezone polygons. """
    global _TZW
    if not _TZW:
        _TZW = tzwhere.tzwhere(forceTZ=force)
    return _TZW


def timezone4loc(loc, fallback=None):
    """ Returns timezone string given a tuple of coordinates. 
        Fallback argument can be an ISO country code."""
    if loc:
        return tzwhere_singleton().tzNameAt(loc[0], loc[1])
    if fallback and fallback in country_timezones:
        return country_timezones[fallback][0]
    return None
