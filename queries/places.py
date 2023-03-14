"""

    Greynir: Natural language processing for Icelandic

    Places query response module

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


    This module handles queries related to places (shops, businesses, etc.)
    such as opening hours, location, address, etc. Uses Google's Places API.

"""

# TODO: Handle opening hours with intervals, e.g. 10:00-14:00 and 18:00-22:00 [!]
# TODO: "Hvenær er X opið?"
# TODO: Refactor this module (use grammar?)

from typing import Iterable, Mapping, Optional

import logging
import re
import random
from datetime import datetime

from reynir import NounPhrase

# from iceaddr import nearest_addr, nearest_placenames

from geo import in_iceland, iceprep_for_street, LatLonTuple
from queries import Query, QueryStateDict
from utility import icequote
from queries.util import (
    PlaceDict,
    gen_answer,
    query_places_api,
    query_place_details,
    AnswerTuple,
    read_grammar_file,
)
from speech.trans import gssml
from tree import Result, Node


_PLACES_QTYPE = "Places"

# Indicate that this module wants to handle parse trees for queries,
# as opposed to simple literal text strings
HANDLE_TREE = True

# The grammar nonterminals this module wants to handle
QUERY_NONTERMINALS = {"QPlaces"}

# The context-free grammar for the queries recognized by this plug-in module
GRAMMAR = read_grammar_file("places")

_PLACENAME_MAP: Mapping[str, str] = {}

TOPIC_LEMMAS = ["opnunartími", "opna", "loka", "lokunartími"]


def help_text(lemma: str) -> str:
    """Help text to return when query processor is unable to parse a query but
    one of the above lemmas is found in it"""
    return "Ég get svarað ef þú spyrð til dæmis: {0}?".format(
        random.choice(
            ("Hvað er opið lengi á Forréttabarnum", "Hvenær lokar Bónus á Fiskislóð",)
        )
    )


def _fix_placename(pn: str) -> str:
    p = pn.capitalize()
    return _PLACENAME_MAP.get(p, p)


def QPlacesQuery(node: Node, params: QueryStateDict, result: Result) -> None:
    result["qtype"] = _PLACES_QTYPE


def QPlacesOpeningHours(node: Node, params: QueryStateDict, result: Result) -> None:
    result["qkey"] = "OpeningHours"


def QPlacesIsOpen(node: Node, params: QueryStateDict, result: Result) -> None:
    result["qkey"] = "IsOpen"


def QPlacesIsClosed(node: Node, params: QueryStateDict, result: Result) -> None:
    result["qkey"] = "IsClosed"


def QPlacesAddress(node: Node, params: QueryStateDict, result: Result) -> None:
    result["qkey"] = "PlaceAddress"


def QPlacesSubject(node: Node, params: QueryStateDict, result: Result) -> None:
    result["subject_nom"] = _fix_placename(result._nominative)


_PLACES_API_ERRMSG = "Ekki tókst að fletta upp viðkomandi stað"
_NOT_IN_ICELAND_ERRMSG = "Enginn staður með þetta heiti fannst á Íslandi"


def _parse_coords(place: PlaceDict) -> Optional[LatLonTuple]:
    """Return tuple of coordinates given a place info data structure
    from Google's Places API."""
    try:
        lat = float(place["geometry"]["location"]["lat"])
        lng = float(place["geometry"]["location"]["lng"])
        return (lat, lng)
    except Exception as e:
        logging.warning(f"Unable to parse place coords for place '{place}': {e}")
    return None


def _top_candidate(cand: Iterable[PlaceDict]) -> Optional[PlaceDict]:
    """Return first place in Iceland in Google Places Search API results."""
    for place in cand:
        coords = _parse_coords(place)
        if coords and in_iceland(coords):
            return place
    return None


def answ_address(placename: str, loc: Optional[LatLonTuple], qtype: str) -> AnswerTuple:
    """Generate answer to a question concerning the address of a place."""
    # Look up placename in places API
    res = query_places_api(
        placename, userloc=loc, fields="formatted_address,name,geometry"
    )

    if (
        not res
        or res["status"] != "OK"
        or "candidates" not in res
        or not res["candidates"]
    ):
        return gen_answer(_PLACES_API_ERRMSG)

    # Use top result in Iceland
    place = _top_candidate(res["candidates"])
    if not place:
        return gen_answer(_NOT_IN_ICELAND_ERRMSG)

    # Remove superfluous "Ísland" in addr string
    addr = re.sub(r", Ísland$", "", place["formatted_address"])
    # Get street name without number to get preposition
    street_name = addr.split()[0].rstrip(",")
    maybe_postcode = re.search(r"^\d\d\d", street_name) is not None
    prep = "í" if maybe_postcode else iceprep_for_street(street_name)
    # Split addr into street name w. number, and remainder
    street_addr = addr.split(",")[0]
    remaining = re.sub(rf"^{street_addr}", "", addr)
    # Get street name in dative case
    addr_þgf = NounPhrase(street_addr).dative or street_addr
    # Assemble final address
    final_addr = f"{addr_þgf}{remaining}"

    # Create answer
    answer = final_addr
    voice = f"{placename} er {prep} {gssml(final_addr, type='numbers', gender='hk')}"
    response = dict(answer=answer)

    return response, answer, voice


def answ_openhours(
    placename: str, loc: Optional[LatLonTuple], qtype: str
) -> AnswerTuple:
    """Generate answer to a question concerning the opening hours of a place."""
    # Look up placename in places API
    res = query_places_api(
        placename,
        userloc=loc,
        fields="opening_hours,place_id,formatted_address,geometry",
    )

    if (
        res is None
        or res["status"] != "OK"
        or "candidates" not in res
        or not res["candidates"]
    ):
        return gen_answer(_PLACES_API_ERRMSG)

    # Use top result
    place = _top_candidate(res["candidates"])
    if place is None:
        return gen_answer(_NOT_IN_ICELAND_ERRMSG)

    if "opening_hours" not in place:
        return gen_answer(
            "Ekki tókst að sækja opnunartíma fyrir " + icequote(placename)
        )

    place_id = place["place_id"]
    is_open = place["opening_hours"]["open_now"]
    # needs_disambig = len(res["candidates"]) > 1
    fmt_addr = place["formatted_address"]

    # Look up place ID in Place Details API to get more information
    res = query_place_details(place_id, fields="opening_hours,name")
    if not res or res.get("status") != "OK" or "result" not in res:
        return gen_answer(_PLACES_API_ERRMSG)

    now = datetime.utcnow()
    wday = now.weekday()
    answer = voice = ""
    p_voice: Optional[str] = None

    try:
        name = res["result"]["name"]
        name_gender = NounPhrase(name).gender or "hk"

        # Generate placename w. street, e.g. "Forréttabarinn á Nýlendugötu"
        street = fmt_addr.split()[0].rstrip(",")
        if not street or street.isnumeric():
            # Street name is a number (probably a postcode), e.g. "101":
            # Don't treat it as a street name
            street = ""
            street_þgf = ""
        else:
            street_þgf = NounPhrase(street).dative or street
            name = f"{name} {iceprep_for_street(street)} {street_þgf}"

        # Get correct "open" adjective for place name
        open_adj_map = {"kk": "opinn", "kvk": "opin", "hk": "opið"}
        open_adj = open_adj_map.get(name_gender) or "opið"

        # Get opening hours for current weekday
        # TODO: Handle when place is closed (no entry in periods)
        periods = res["result"]["opening_hours"]["periods"]
        if len(periods) == 1 or wday >= len(periods):
            # Open 24 hours a day
            today_desc = p_desc = f"{name} er {open_adj} allan sólarhringinn"
        else:
            # Get period
            p = periods[wday]
            opens = p["open"]["time"]
            closes = p["close"]["time"]

            # Format correctly, e.g. "12:00 - 19:00"
            openstr = f"{opens[:2]}:{opens[2:]}"
            closestr = f"{closes[:2]}:{opens[2:]}"
            p_desc = f"{openstr} - {closestr}"
            p_voice = (
                f"{gssml(openstr, type='time')} til {gssml(closestr, type='time')}"
            )
            today_desc = f"Í dag er {name} {open_adj} frá {{opening_hours}}"
    except Exception as e:
        logging.warning(f"Exception generating answer for opening hours: {e}")
        return gen_answer(_PLACES_API_ERRMSG)

    # Generate answer
    if qtype == "OpeningHours":
        answer = p_desc
        voice = today_desc.format(opening_hours=p_voice or "")
    # Is X open? Is X closed?
    elif qtype == "IsOpen" or qtype == "IsClosed":
        yes_no = (
            "Já"
            if (
                (is_open and qtype == "IsOpen") or (not is_open and qtype == "IsClosed")
            )
            else "Nei"
        )
        answer = f"{yes_no}. {today_desc.format(opening_hours=p_desc or '')}."
        voice = f"{yes_no}. {today_desc.format(opening_hours=p_voice or '')}."

    response = dict(answer=answer)

    return response, answer, voice


_HANDLER_MAP = {
    "OpeningHours": answ_openhours,
    "IsOpen": answ_openhours,
    "IsClosed": answ_openhours,
    "PlaceAddress": answ_address,
}


def sentence(state: QueryStateDict, result: Result) -> None:
    """Called when sentence processing is complete"""
    q: Query = state["query"]
    if "qtype" in result and "qkey" in result and "subject_nom" in result:
        # Successfully matched a query type
        subj = result["subject_nom"]
        try:
            handlerfunc = _HANDLER_MAP[result.qkey]
            res: Optional[AnswerTuple] = handlerfunc(subj, q.location, result.qkey)
            if res:
                q.set_answer(*res)
                q.set_source("Google Maps")
            else:
                errmsg = f"Ekki tókst að fletta upp staðnum {icequote(subj)}"
                q.set_answer(*gen_answer(errmsg))
            q.set_qtype(result.qtype)
            q.set_key(subj)
        except Exception as e:
            logging.warning(f"Exception answering places query: {e}")
            q.set_error(f"E_EXCEPTION: {e}")
            return
    else:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
