"""

    Greynir: Natural language processing for Icelandic

    User location query response module

    Copyright (C) 2020 Miðeind ehf.

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

    This module handles queries related to user location ("Where am I?").

"""

import re
import logging

from queries import (
    gen_answer,
    query_geocode_api_coords,
    country_desc,
    nom2dat,
    numbers_to_neutral,
    cap_first
)
from iceaddr import iceaddr_lookup, postcodes
from geo import iceprep_for_placename, iceprep_for_street


_LOC_QTYPE = "UserLocation"


# This module wants to handle parse trees for queries
HANDLE_TREE = True

# The context-free grammar for the queries recognized by this plug-in module
GRAMMAR = """

Query →
    QUserLocation

QUserLocation → QUserLocationQuery '?'?

QUserLocationQuery →
    QUserLocationCurrent | QUserLocationPostcode

QUserLocationCurrent →
    "hvar" "er" "ég" QULocEiginlega? QULocLocated? QULocInTheWorld? QULocNow?
    | "hvað" "er" "ég" QULocEiginlega? QULocLocated? QULocInTheWorld? QULocNow?
    | "veistu" "hvar" "ég" "er" QULocEiginlega? QULocInTheWorld? QULocNow?
    | "veist" "þú" "hvar" "ég" "er" QULocEiginlega? QULocInTheWorld? QULocNow?
    | "hver" "er" "staðsetning" "mín"? QULocEiginlega? QULocInTheWorld? QULocNow?
    # TODO: Share above
    | "hver" "er" "staðsetningin" "mín"? QULocEiginlega? QULocInTheWorld? QULocNow?
    | "hvar" "erum" "við" QULocEiginlega? QULocLocatedFemAndPlural? QULocInTheWorld? QULocNow?
    | "staðsetning" QULocInTheWorld? QULocNow?
    | QULocWhichStreet QULocEiginlega? QULocLocated? QULocInTheWorld? QULocNow?

QUserLocationPostcode →
    "í" "hvaða" "póstnúmeri" "er" "ég" QULocEiginlega? QULocLocated? QULocNow?
    | "hvaða" "póstnúmeri" "er" "ég" QULocEiginlega? QULocLocated? "í" QULocNow?
    | "í" "hvaða" "póstnúmeri" "erum" "við" QULocEiginlega? QULocLocated? QULocNow?
    | "hvaða" "póstnúmeri" "erum" "við" QULocEiginlega? QULocLocated? "í" QULocNow?

QULocWhichStreet →
    QULocPreposition "hvaða" "götu" "er" "ég"
    | QULocPreposition "hvaða" "götu" "erum" "við"

QULocPreposition →
    "á" | "í"

QULocEiginlega →
    "eiginlega"

QULocLocated →
    "staddur" | "staðsettur" | "niðurkominn" | "niður" "kominn" | QULocLocatedFemAndPlural

QULocLocatedFemAndPlural →
    "stödd" | "staðsett" | "niðurkomin" | "niður" "komin"

QULocInTheWorld →
    "í" "heiminum"
    | "í" "veröldinni"
    | "á" "hnettinum"
    | "á" "jörðinni"
    | "á" "landinu"
    | "á" "Íslandi"
    | "á" "yfirborði" "jarðar"
    | "á" "jarðkringlunni"

QULocNow →
    "nákvæmlega"? QULocNowGeneric

QULocNowGeneric →
    "nú" | "akkúrat"? "núna" | "eins" "og" "stendur" | "sem" "stendur"
    | "í" "augnablikinu" | "á" "þessari" "stundu" | "hér" "og" "nú"

$score(+35) QUserLocation

"""


def QUserLocationQuery(node, params, result):
    result.qtype = _LOC_QTYPE


def QUserLocationCurrent(node, params, result):
    result.qkey = "CurrentLocation"


def QUserLocationPostcode(node, params, result):
    result.qkey = "CurrentPostcode"


def _addrinfo_from_api_result(result):
    """ Extract relevant address components from Google API result """

    comp = result["address_components"]

    num = None
    street = None
    locality = None
    country = None
    postcode = None

    for c in comp:
        if "types" not in c:
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


def _locality_desc(locality_nom):
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
    street, num, locality, postcode, country_code = _addrinfo_from_api_result(top)

    descr = None

    # Special handling of Icelandic locations since we have more info
    # about them and street/locality names need to be declined.
    if country_code == "IS":
        # We received a street name from the API
        if street:
            descr = street_desc(street, num, locality)
        # We at least have a locality (e.g. "Reykjavík")
        elif locality:
            descr = _locality_desc(locality)
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

    answer = cap_first(descr)
    response = dict(answer=answer)
    voice = "Þú ert {0}".format(_addr4voice(descr))

    return response, answer, voice


def answer_for_postcode(loc):
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

    # Only support Icelandic postcodes for now
    if country_code == "IS" and postcode:
        pc = postcodes.get(int(postcode))
        pd = "{0} {1}".format(postcode, pc["stadur_nf"])
        (response, answer, voice) = gen_answer(pd)
        voice = "Þú ert í {0}".format(pd)
        return response, answer, voice
    else:
        return gen_answer("Ég veit ekki í hvaða póstnúmeri þú ert.")


def sentence(state, result):
    """ Called when sentence processing is complete """
    q = state["query"]
    if "qtype" in result and "qkey" in result:
        # Successfully matched a query type
        q.set_qtype(result.qtype)
        q.set_key(result.qkey)

        try:
            answ = None
            loc = q.location
            if loc:
                # Get relevant info about this location
                if result.qkey == "CurrentPostcode":
                    answ = answer_for_postcode(loc)
                else:
                    answ = answer_for_location(loc)
            if answ:
                # For uniformity, store the returned location in the context
                # !!! TBD: We might want to store an address here as well
                q.set_context({"location": loc})
            else:
                # We either don't have a location or no info about
                # the location associated with the query
                answ = gen_answer("Ég veit ekki hvar þú ert.")

            ql = q.query_lower
            if ql.startswith("hvað er ég"):
                bq = re.sub(
                    r"^hvað er ég",
                    "Hvar er ég",
                    q.beautified_query,
                    flags=re.IGNORECASE,
                )
                q.set_beautified_query(bq)

            q.set_answer(*answ)

        except Exception as e:
            logging.warning("Exception while processing location query: {0}".format(e))
            q.set_error("E_EXCEPTION: {0}".format(e))
            raise
    else:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
