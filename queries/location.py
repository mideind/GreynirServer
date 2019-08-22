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


    This module handles location-related queries.

"""

# TODO: Country name should also be declined.
# TODO: "staddur á" vs. "staddur í"
# TODO: Speech synthesis: "Bárugötu þrjú" ekki "þrír"
# TODO: "Hvað er ég langt frá X?"

import logging
from queries import query_json_api, gen_answer
from iceaddr import iceaddr_lookup
from geo import iceprep_for_country, iceprep_for_placename
from reynir.bindb import BIN_Db
from pprint import pprint


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


_MAPS_API_URL = "https://maps.googleapis.com/maps/api/geocode/json?latlng={0},{1}&key={2}&language=is"


def _query_geocode_API(lat, lon):
    # Load API key
    key = _get_API_key()
    if not key:
        # No key, can't query Google location API
        logging.warning("No API key for location lookup")
        return None

    # Send API request
    url = _MAPS_API_URL.format(lat, lon, key)
    return query_json_api(url)


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


_WHERE_AM_I_STRINGS = frozenset(
    (
        "hvar er ég",
        "hvar er ég núna",
        "hvar er ég staddur",
        "hvar er ég stödd",
        "hver er staðsetning mín",
    )
)
_LOC_QTYPE = "Location"


def answer_for_location(loc):
    # Send API request
    res = _query_geocode_API(loc[0], loc[1])
    pprint(res)

    # Verify that we have at least one valid result
    # TODO: Handle this differently?
    if (
        not res
        or "results" not in res
        or not len(res["results"])
        or not res["results"][0]
    ):
        return None

    top = res["results"][0]
    # TODO, fall back on lower-ranked results from the API
    # if the top result doesn't even contain a locality.

    # Extract address info from top result
    (street, num, locality, postcode, country) = _addrinfo_from_api_result(top)
    print(street, num, locality, postcode, country)


    def nom2dat(w):
        """ Look up dative form of a noun in BÍN, try
            lowercase if capitalized form not found """
        b = BIN_Db() 
        bin_res = b.lookup_dative(w, cat="no")
        if not bin_res and not w.islower():
            bin_res = b.lookup_dative(w.lower(), cat="no")
        if bin_res:
            return bin_res[0].ordmynd
        return None

    if country == "Ísland":
        descr = "Íslandi"

        if street:
            street_dat = None
            locality_dat = None

            # Start by looking up address in staðfangaskrá to get 
            # the dative case of street name and locality
            # addrinfo = iceaddr_lookup(street, placename=locality, limit=1)
            # if len(addrinfo):
            #     street_dat = addrinfo[0]["heiti_tgf"]
            #     if locality and locality == addrinfo[0]["stadur_nf"]:
            #         locality_dat = addrinfo[0]["stadur_tgf"]

            # OK, if staðfangaskrá can't help us, try to use BÍN to
            # get dative version of name. Some names given by Google's
            # API are generic words such as "Göngustígur" and the like.
            if not street_dat:
                street_dat = nom2dat(street)
                locality_dat = nom2dat(locality)
                print(street_dat)
                print(locality_dat)

            descr = street_dat or street
            if num:
                descr += " " + num
            if locality:
                prep = iceprep_for_placename(locality_dat)
                descr += " {0} {1}".format(prep, locality_dat)
    else:
        # TODO: Elegant implementation for foreign roads/placenames/countries
        pass

    if not descr:
        # Just use the formatted address string provided by Google
        descr = top["formatted_address"]

    answer = descr
    response = dict(answer=answer)
    voice = "Þú ert á {0}".format(answer)

    return response, answer, voice


def handle_plain_text(q):
    """ Handle a plain text query asking about user's current location. """
    ql = q.query_lower.rstrip("?")

    if ql not in _WHERE_AM_I_STRINGS:
        return False

    loc = q.location
    answ = None

    if loc:
        # Get info about this location
        answ = answer_for_location(loc)

    if not answ:
        # We either don't have a location or no info about the
        # location associated with the query
        answ = gen_answer("Ég veit ekkert um staðsetningu þína.")

    q.set_qtype(_LOC_QTYPE)
    q.set_answer(*answ)

    return True
