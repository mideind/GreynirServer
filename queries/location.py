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

# TODO: Speech synthesis: "Bárugötu þrjú" ekki "þrír"
# TODO: "Hvað er ég langt frá X?"

import os
import logging

from queries import query_json_api, gen_answer
from iceaddr import iceaddr_lookup
from geo import (
    iceprep4cc,
    iceprep_for_placename,
    iceprep_for_street,
    country_name_for_isocode,
)
from reynir.bindb import BIN_Db


# The Google API identifier (you must obtain your
# own key if you want to use this code)
_API_KEY = ""
_API_KEY_PATH = os.path.join("resources", "GoogleServerKey.txt")


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

        types = c["types"]

        if "street_number" in types:
            num = c["long_name"]
        elif "route" in types:
            street = c["long_name"]
        elif "locality" in types:
            locality = c["long_name"]
        elif "country" in types:
            country = c["short_name"]
        elif "postal_code" in types:
            postcode = c["long_name"]

    # HACK: Google's API sometimes (rarely) returns the English-language
    # string "Unnamed Road" irrespective of language settings.
    if street == "Unnamed Road":
        street = "ónefnd gata"

    return (street, num, locality, postcode, country)


def nom2dat(w):
    """ Look up dative form of a noun in BÍN, try
        lowercase if capitalized form not found """
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
        with correct preposition and case e.g. 'á Spáni' """
    cn = country_name_for_isocode(cc)
    prep = iceprep4cc(cc)
    return "{0} {1}".format(prep, nom2dat(cn))


def street_desc(street_nom, street_num, locality_nom):
    """ Generate description of being on a particular (Icelandic) street with 
        correct preposition and case + locality e.g. 'á Fiskislóð 31 í Reykjavík'. """
    street_dat = None
    locality_dat = None

    # Start by looking up address in staðfangaskrá to get
    # the dative case of street name and locality.
    # This works better than BÍN lookup since not all street
    # names are present in BÍN.
    addrinfo = iceaddr_lookup(street_nom, placename=locality_nom, limit=1)
    if len(addrinfo):
        street_dat = addrinfo[0]["heiti_tgf"]
        if locality_nom and locality_nom == addrinfo[0]["stadur_nf"]:
            locality_dat = addrinfo[0]["stadur_tgf"]

    # OK, if staðfangaskrá can't help us, try to use BÍN to
    # get dative version of name. Some names given by Google's
    # API are generic terms such as "Göngustígur" and the like.
    if not street_dat:
        street_dat = nom2dat(street_nom)
    if not locality_dat:
        locality_dat = nom2dat(locality_nom)

    # Create street descr. ("á Fiskislóð 31")
    street_comp = iceprep_for_street(street_nom) + " " + street_dat
    if street_num:
        street_comp += " " + street_num

    # Append locality if available ("í Reykjavík")
    if locality_dat:
        ldesc = iceprep_for_placename(locality_nom) + " " + locality_dat
        street_comp += " " + ldesc

    return street_comp


def answer_for_location(loc):
    # Send API request
    res = _query_geocode_API(loc[0], loc[1])

    # Verify that we have at least one valid result
    if (
        not res
        or "results" not in res
        or not len(res["results"])
        or not res["results"][0]
    ):
        return None

    # Grab top result from API call
    top = res["results"][0]
    # TODO: Fall back on lower-ranked results from the API
    # if the top result doesn't even contain a locality.

    # Extract address info from top result
    (street, num, locality, postcode, country_code) = _addrinfo_from_api_result(top)

    descr = None

    # Special handling of Icelandic locations since we have more info
    # about them and street/locality names need to be declined.
    if country_code == "IS":
        # We received a street name from the API
        if street:
            descr = street_desc(street, num, locality)
        # We at least have a locality (e.g. "Reykjavík")
        elif locality:
            descr = iceprep_for_placename(locality) + " " + locality
        # Only country
        else:
            descr = country_desc("IS")
    # The provided location is abroad.
    else:
        sdesc = ("á " + street) if street else ""
        if num and street:
            sdesc += " " + num
        locdesc = (
            "{0} {1}".format(iceprep_for_placename(locality), locality)
            if locality
            else ""
        )
        # "[á Boulevard St. Germain] [í París] [í Frakklandi]"
        descr = "{0} {1} {2}".format(
            sdesc, locdesc, country_desc(country_code)
        ).strip()

    if not descr:
        # Fall back on the formatted address string provided by Google
        descr = "á" + top.get("formatted_address")

    response = dict(answer=descr)
    voice = "Þú ert {0}".format(descr)
    answer = descr[0].upper() + descr[1:]

    return response, answer, voice


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
        # We either don't have a location or no info about
        # the location associated with the query
        answ = gen_answer("Ég veit ekki hvar þú ert.")

    q.set_qtype(_LOC_QTYPE)
    q.set_key("CurrentPosition")
    q.set_answer(*answ)

    return True
