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


# TODO: "Í hvaða póstnúmeri er ég?" "Í hvaða póstnúmeri er Fiskislóð 31?"
# TODO: "Í hvaða bæ er ég?" "Hver er næsti bær?"


import os
import re
import logging

from queries import (
    gen_answer,
    query_geocode_api_coords,
    country_desc,
    nom2dat,
    numbers_to_neutral,
)
from iceaddr import iceaddr_lookup
from geo import iceprep_for_placename, iceprep_for_street


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


def locality_desc(locality_nom):
    """ Return an appropriate preposition plus a locality name in dative case """
    locality_dat = nom2dat(locality_nom)
    return iceprep_for_placename(locality_nom) + " " + locality_dat


def _addr4voice(addr):
    """ Prepare an address string for voice synthesizer. """
    # E.g. "Fiskislóð 5-9" becomes "Fiskislóð 5 til 9"
    s = re.sub(r"(\d+)\-(\d+)", r"\1 til \2", addr)
    # Convert numbers to neutral gender:
    # 'Fiskislóð 2 til 4' -> 'Fiskislóð tvö til fjögur'
    return numbers_to_neutral(s)


def answer_for_location(loc):
    # Send API request
    res = query_geocode_api_coords(loc[0], loc[1])

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
            descr = locality_desc(locality)
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
        descr = "{0} {1} {2}".format(sdesc, locdesc, country_desc(country_code)).strip()

    if not descr:
        # Fall back on the formatted address string provided by Google
        descr = "á " + top.get("formatted_address")

    response = dict(answer=descr)
    voice = "Þú ert {0}".format(_addr4voice(descr))
    answer = descr[0].upper() + descr[1:]

    return response, answer, voice


_WHERE_AM_I_QUERIES = frozenset(
    (
        "hvar er ég",
        "hvað er ég",  # Too commonly misrecognized by the ASR
        "hvar er ég núna",
        "hvar er ég nú",
        "hvar er ég í heiminum",
        "hvar er ég staddur í heiminum",
        "hvar er ég stödd í heiminum",
        "hvar er ég staddur á hnettinum",
        "hvar er ég stödd á hnettinum",
        "hvar er ég eins og stendur",
        "hvar er ég eiginlega",
        "hvar er ég staddur",
        "hvar er ég staddur á landinu",
        "hvar er ég stödd",
        "hvar er ég stödd á landinu",
        "hvar er ég staðsettur",
        "hvar er ég staðsett"
        "hvar er ég staðsettur í heiminum",
        "hvar er ég staðsett í heiminum",
        "veistu hvar ég er staddur",
        "veistu hvar ég er stödd",
        "veistu hvar ég er staddur núna",
        "veistu hvar ég er stödd núna",
        "hver er staðsetning mín",
        "hvar erum við",
        "hvar erum við stödd",
        "hvar er ég sem stendur",
        "hvar er ég niðurkominn",
        "hvar er ég niðurkomin",
        "hvar erum við niðurkomin",
        "hvar erum við sem stendur",
        "staðsetning",
    )
)

# _POSTCODE_QUERIES = frozenset(
#     (
#         "í hvaða póstnúmeri er ég",
#         "í hvaða póstnúmeri er ég staddur",
#         "í hvaða póstnúmeri er ég stödd",
#         "hvaða póstnúmeri er ég í",
#         "hvaða póstnúmeri er ég staddur í",
#         "hvaða póstnúmeri er ég stödd í",
#     )
# )

_LOC_QTYPE = "Location"


def handle_plain_text(q):
    """ Handle a plain text query asking about user's current location. """
    ql = q.query_lower.rstrip("?")

    if ql not in _WHERE_AM_I_QUERIES:
        return False

    answ = None
    loc = q.location
    if loc:
        # Get info about this location
        answ = answer_for_location(loc)

    if answ:
        # For uniformity, store the returned location in the context
        # !!! TBD: We might want to store an address here as well
        q.set_context({"location": loc})
    else:
        # We either don't have a location or no info about
        # the location associated with the query
        answ = gen_answer("Ég veit ekki hvar þú ert.")

    # Hack since we recognize 'hvað er ég' as 'hvar er ég'
    if ql == "hvað er ég":
        q.set_beautified_query("Hvar er ég?")
    q.set_qtype(_LOC_QTYPE)
    q.set_key("CurrentPosition")
    q.set_answer(*answ)

    return True
