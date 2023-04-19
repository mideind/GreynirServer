"""

    Greynir: Natural language processing for Icelandic

    User location query response module

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


    This module handles queries related to user location ("Where am I?").

"""

from typing import Any, Tuple, Optional, cast

import re
import logging

from queries import Query, QueryStateDict, AnswerTuple
from utility import cap_first
from queries.util import (
    gen_answer,
    query_geocode_api_coords,
    country_desc,
    nom2dat,
    read_grammar_file,
)
from speech.trans.num import numbers_to_text
from tree import Result, Node
from iceaddr import iceaddr_lookup, postcodes
from geo import (
    country_name_for_isocode,
    iceprep_for_placename,
    iceprep_for_street,
    in_iceland,
    LatLonTuple,
)


_LOC_QTYPE = "UserLocation"


# This module wants to handle parse trees for queries
HANDLE_TREE = True

# The grammar nonterminals this module wants to handle
QUERY_NONTERMINALS = {"QUserLocation"}

# The context-free grammar for the queries recognized by this plug-in module
GRAMMAR = read_grammar_file("userloc")


def QUserLocationQuery(node: Node, params: QueryStateDict, result: Result) -> None:
    result.qtype = _LOC_QTYPE


def QUserLocationCurrent(node: Node, params: QueryStateDict, result: Result) -> None:
    result.qkey = "CurrentLocation"


def QUserLocationPostcode(node: Node, params: QueryStateDict, result: Result) -> None:
    result.qkey = "CurrentPostcode"


def QUserLocationCountry(node: Node, params: QueryStateDict, result: Result) -> None:
    result.qkey = "CurrentCountry"


def _addrinfo_from_api_result(result) -> Tuple[str, int, str, str, str]:
    """Extract relevant address components from Google API result."""

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


def street_desc(street_nom: str, street_num: int, locality_nom: str) -> str:
    """Generate description of being on a particular (Icelandic) street with
    correct preposition and case + locality e.g. 'á Fiskislóð 31 í Reykjavík'."""
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
        street_comp += " " + str(street_num)

    # Append locality if available ("í Reykjavík")
    if locality_dat:
        ldesc = iceprep_for_placename(locality_nom) + " " + locality_dat
        street_comp += " " + ldesc

    return street_comp


def _locality_desc(locality_nom: str) -> str:
    """Return an appropriate preposition plus a locality name in dative case."""
    locality_dat = nom2dat(locality_nom)
    return iceprep_for_placename(locality_nom) + " " + locality_dat


def _addr4voice(addr: str) -> Optional[str]:
    """Prepare an address string for voice synthesizer."""
    # E.g. "Fiskislóð 5-9" becomes "Fiskislóð 5 til 9"
    s = re.sub(r"(\d+)\-(\d+)", r"\1 til \2", addr)
    # E.g. "Fiskislóð 31d" becomes "Fiskislóð 31 d"
    s = re.sub(r"(\d+)([a-zA-Z])", r"\1 \2", s)
    # Convert numbers to neutral gender:
    # 'Fiskislóð 2 til 4' -> 'Fiskislóð tvö til fjögur'
    return numbers_to_text(s) if s else None


_LOC_LOOKUP_FAIL_MSG = "Ekki tókst að fletta upp staðsetningu."


def locality_and_country(loc: LatLonTuple) -> Optional[str]:
    """Return the locality and country of the given location, or None"""
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

    # Extract locality and country info from top result
    _, _, locality, _, country_code = _addrinfo_from_api_result(top)
    country_name = country_name_for_isocode(country_code) or country_code

    return locality + ", " + country_name if locality else country_name


def answer_for_location(loc: LatLonTuple) -> Optional[AnswerTuple]:
    """Answer user location query, e.g. 'Hvar er ég staddur?'"""
    # Send API request
    res = query_geocode_api_coords(loc[0], loc[1])

    # Verify that we have at least one valid result
    if (
        not res
        or "results" not in res
        or not len(res["results"])
        or not res["results"][0]
    ):
        return gen_answer(_LOC_LOOKUP_FAIL_MSG)

    # Grab top result from API call
    top = res["results"][0]
    # TODO: Fall back on lower-ranked results from the API
    # if the top result doesn't even contain a locality.

    # Extract address info from top result
    street, num, locality, postcode, country_code = _addrinfo_from_api_result(top)

    descr = ""

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
            sdesc += f" {num}"
        # e.g. "í París"
        locdesc = f"{iceprep_for_placename(locality)} {locality}" if locality else ""
        # "[á Boulevard St. Germain] [í París] [í Frakklandi]"
        descr = f"{sdesc} {locdesc} {country_desc(country_code)}".strip()

    if not descr:
        # Fall back on the formatted address string provided by Google
        descr = "á " + top.get("formatted_address")

    answer = cap_first(descr)
    response = dict(answer=answer)
    voice = f"Þú ert {_addr4voice(descr)}"

    return response, answer, voice


def answer_for_postcode(loc: LatLonTuple):
    """Answer postcode query, e.g. 'Í hvaða póstnúmeri er ég?'"""
    # Send API request
    res = query_geocode_api_coords(loc[0], loc[1])

    # Verify that we have at least one valid result
    if (
        not res
        or "results" not in res
        or not len(res["results"])
        or not res["results"][0]
    ):
        return gen_answer(_LOC_LOOKUP_FAIL_MSG)

    # Grab top result from API call
    top = res["results"][0]
    # TODO: Fall back on lower-ranked results from the API
    # if the top result doesn't even contain a locality.

    # Extract address info from top result
    (street, num, locality, postcode, country_code) = _addrinfo_from_api_result(top)

    # Only support Icelandic postcodes for now
    if country_code == "IS" and postcode:
        pc = cast(Any, postcodes).get(int(postcode))
        pd = f'{postcode} {pc["stadur_nf"]}'
        (response, answer, voice) = gen_answer(pd)
        voice = f"Þú ert í {pd}"
        return response, answer, voice
    else:
        return gen_answer("Ég veit ekki í hvaða póstnúmeri þú ert.")


def answer_for_country(loc: LatLonTuple):
    """Answer country query, e.g. 'Í hvaða landi er ég?'"""
    if in_iceland(loc):
        return gen_answer("Þú ert á Íslandi.")

    # Send API request
    res = query_geocode_api_coords(loc[0], loc[1])

    # Verify that we have at least one valid result
    if (
        not res
        or "results" not in res
        or not len(res["results"])
        or not res["results"][0]
    ):
        return gen_answer(_LOC_LOOKUP_FAIL_MSG)

    # Grab top result from API call
    top = res["results"][0]

    # Extract address info from top result
    street, num, locality, postcode, country_code = _addrinfo_from_api_result(top)
    if not country_code or len(country_code) != 2:
        return gen_answer(_LOC_LOOKUP_FAIL_MSG)

    # OK, we have a valid country code
    return gen_answer(f"Þú ert {country_desc(country_code)}.")


def sentence(state: QueryStateDict, result: Result) -> None:
    """Called when sentence processing is complete."""
    q: Query = state["query"]
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
                elif result.qkey == "CurrentCountry":
                    answ = answer_for_country(loc)
                else:
                    answ = answer_for_location(loc)
            if answ and loc is not None:
                # For uniformity, store the returned location in the context
                # !!! TBD: We might want to store an address here as well
                q.set_context({"location": loc})
            else:
                # We either don't have a location or no info about
                # the location associated with the query
                answ = gen_answer("Ég veit ekki hvar þú ert.")

            ql = q.query_lower
            # This is a hack to fix issue where speech recognition
            # identifies "hvar er ég" as "hvað er ég". We assume it's
            # not actually a moment of existential angst ;)
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
            logging.warning(f"Exception while processing location query: {e}")
            q.set_error(f"E_EXCEPTION: {e}")
            raise
    else:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
