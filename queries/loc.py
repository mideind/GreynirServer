"""

    Reynir: Natural language processing for Icelandic

    Location query response module

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

"""

# TODO: Country name should also be declined.
# TODO: "staddur á" vs. "staddur í"

import requests
import json
import logging
from iceaddr import iceaddr_lookup

MAPS_API_URL = "https://maps.googleapis.com/maps/api/geocode/json?latlng={0},{1}&key={2}&language=is"


# The Google API identifier (you must obtain your own key if you want to use this code)
_API_KEY = ""
_API_KEY_PATH = "resources/GoogleServerKey.txt"


def _get_API_key():
    """ Read Google API key from file """
    global _API_KEY
    if not _API_KEY:
        try:
            # You need to obtain your own key and put it in
            # _API_KEY_PATH if you want to use this code
            with open(_API_KEY_PATH) as f:
                _API_KEY = f.read().rstrip()
        except FileNotFoundError:
            _API_KEY = ""
    return _API_KEY


def _query_geocode_API(lat, lon):
    # Load API key
    key = _get_API_key()
    if not key:
        # No key, can't query Google location API
        logging.warning("No API key for location lookup")
        return False

    # Send API request
    url = MAPS_API_URL.format(lat, lon, key)
    try:
        r = requests.get(url)
    except Exception as e:
        logging.warning(str(e))
        return None

    # Verify that status is OK
    if r.status_code != 200:
        logging.warning("Received status {0} from geocode API server", r.status_code)
        return None

    # Parse json API response
    try:
        res = json.loads(r.text)
        return res
    except Exception as e:
        logging.warning("Error parsing JSON API response: {0}", str(e))

    return None


def _addrinfo_from_api_result(result):
    """ Extract relevant address components from Google API result """
    comp = result["address_components"]

    num = None
    street = None
    locality = None
    country = None
    postcode = None

    for c in comp:
        if not "types" in c:
            continue
        if "street_number" in c["types"]:
            num = c["long_name"]
        elif "route" in c["types"]:
            street = c["long_name"]
        elif "locality" in c["types"]:
            locality = c["long_name"]
        elif "country" in c["types"]:
            country = c["long_name"]
        elif "postal_code" in c["types"]:
            postcode = c["long_name"]

    return (street, num, locality, postcode, country)


WHERE_AM_I_STRINGS = frozenset(
    ("hvar er ég", "hvar er ég núna", "hvar er ég staddur", "hver er staðsetning mín")
)
LOC_QTYPE = "Location"


def handle_plain_text(q):
    """ Handle a plain text query asking about user's current location. """
    ql = q.query_lower

    if ql.endswith("?"):
        ql = ql[:-1]

    if ql not in WHERE_AM_I_STRINGS:
        return False

    loc = q.location
    if not loc:
        # We don't have a location associated with the query
        # so we return a response saying we don't know
        answer = "Ég veit ekkert um staðsetningu þína."
        response = dict(answer=answer)
        voice = answer
        q.set_qtype(LOC_QTYPE)
        q.set_answer(response, answer, voice)
        return True

    # Send API request
    res = _query_geocode_API(loc[0], loc[1])

    # Verify that we have at least one valid result
    if (
        not res
        or "results" not in res
        or not len(res["results"])
        or not res["results"][0]
    ):
        return False

    top = res["results"][0]

    # Extract address info from top result
    (street, num, locality, postcode, country) = _addrinfo_from_api_result(top)

    if country == "Ísland":
        descr = "Íslandi"

        if street:
            # Look up address in staðfangaskrá to get the
            # dative case of street name and locality
            addrinfo = iceaddr_lookup(street, placename=locality, limit=1)
            if len(addrinfo):
                street = addrinfo[0]["heiti_tgf"]
                if locality and locality == addrinfo[0]["stadur_nf"]:
                    locality = addrinfo[0]["stadur_tgf"]

            descr = street
            if num:
                descr += " " + num
            if locality:
                prefix = "í" # TODO: "í" vs. "á" for locality
                descr += " {0} {1}".format(prefix, locality)
    
    if not descr:
        # Just use the formatted address string provided by Google
        descr = top["formatted_address"]

    answer = descr
    response = dict(answer=answer)
    voice = "Þú ert á {0}".format(answer)

    q.set_qtype(LOC_QTYPE)
    q.set_answer(response, answer, voice)

    return True
