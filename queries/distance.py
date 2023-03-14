"""

    Greynir: Natural language processing for Icelandic

    Distance query response module

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


    This module handles distance-related queries.

"""

# TODO: This module should probably use grammar instead of regexes
# TODO: "Hvað er ég langt frá heimili mínu?", "Hvað er ég lengi að ganga heim?"
# TODO: "Hvað er langt á milli X og Y?", "Hvað er langt frá A til B?"
# TODO: "Hvað er langt til tunglsins?", "Hvað er langt til Mars?"
# TODO: Identify when user is present at the location, respond "Þú ert í/á X"
# TODO: "Hvað er langur/margra kílómetra göngutúr í/á X?"
# TODO: Fix issue where answer complains about lack of location despite query
#       being handlable by another module, error checking should take place earlier

from typing import Callable, List, Match, Optional, Tuple, cast

import re
import logging

from reynir import NounPhrase
from queries import AnswerTuple, Query
from utility import cap_first
from queries.util import (
    gen_answer,
    time_period_desc,
    distance_desc,
    query_geocode_api_addr,
    query_traveltime_api,
)
from speech.trans import gssml
from geo import distance, capitalize_placename


_DISTANCE_QTYPE = "Distance"


_QDISTANCE_REGEXES = (
    r"^(?:en\s)?hvað er ég langt frá (.+)$",
    r"^hvað erum við langt frá (.+)$",
    r"^hvað er langt frá (.+)$",  # Speech recognition often misses "ég" in this context
    r"^hvað er ég langt í burtu frá (.+)$",
    r"^hvað erum við langt í burtu frá (.+)$",
    r"^hversu langt er ég frá (.+)$",
    r"^hversu langt erum við frá (.+)$",
    r"^hversu langt í burtu er (.+)$",
    r"^hve langt í burtu er (.+)$",
    r"^hversu langt frá (.+) er ég$",
    r"^hve langt frá (.+) er ég$",
    r"^hve langt er ég frá (.+)$",
    r"^hversu langt frá (.+) erum við$",
    r"^hve langt frá (.+) erum við$",
    r"^hve langt erum við frá (.+)$",
    r"^hvað er langt\s?(?:héðan)?\s?(?:austur|vestur|norður|suður|upp|niður)? á (.+)$",
    r"^hvað er langt\s?(?:héðan)? upp á (.+)$",
    r"^hvað er langt\s?(?:héðan)? niður á (.+)$",
    r"^hvað er langt\s?(?:héðan)?\s?(?:austur|vestur|norður|suður|upp|niður)? í ([^0-9.].+)$",
    r"^hvað er langt\s?(?:héðan)? upp í (.+)$",
    r"^hvað er langt\s?(?:héðan)? til (.+)$",
    r"^hvað er langt\s?(?:héðan)? út á ([^0-9.].+)$",
    r"^hversu langt er\s?(?:austur|vestur|norður|suður|upp|niður)? til (.+)$",
    r"^hversu langt er út á (.+)$",
    r"^hversu marga kílómetra er ég frá (.+)$",
    r"^hversu marga metra er ég frá (.+)$",
    r"^hversu marga kílómetra erum við frá (.+)$",
    r"^hversu marga metra erum við frá (.+)$",
    r"^hvað eru margir kílómetrar til (.+)$",
    r"^hvað eru margir metrar til (.+)$",
    r"^hvað er (.+) langt í burtu frá mér$",
    r"^hvað er (.+) langt í burtu frá okkur$",
    r"^hvað er (.+) langt í burtu$",
    # Home
    # r"^hvað er langt\s?(?:héðan)? (heim)\s?(?:héðan)?$",
    # r"^hvað er langt\s?(?:héðan)? (heim til mín)\s?(?:héðan)?$",
)

# Travel time questions
_TT_PREFIXES = (
    "hvað er ég lengi að",
    "hvað er lengi að",
    "hvað er maður lengi að",
    "hvað erum við lengi að",
    "hversu lengi er ég að",
    "hversu lengi er maður að",
    "hversu lengi erum við að",
    "hversu lengi að",
    "hve lengi að",
    "hve lengi er ég að",
    "hve lengi er maður að",
    "hve lengi erum við að",
    "hvað tekur langan tíma að",
    "hvað tekur mig langan tíma að",
    "hvað tekur mann langan tíma að",
    "hvað tekur okkur langan tíma að",
    "hvað tekur það langan tíma að",
    "hvað tekur það mig langan tíma að",
    "hvað tekur það okkur langan tíma að",
    "hvað tekur það mann langan tíma að",
    "hversu langan tíma tekur að",
    "hversu langan tíma tekur það að",
    "hversu langan tíma tekur það mig að",
    "hversu langan tíma tekur það okkur að",
    "hvað væri ég lengi að",
    "hvað værum við lengi að",
    "hvað væri maður lengi að",
    "hvað tæki það langan tíma að",
    "hvað tæki mann langan tíma að",
    "hvað tæki það mann langan tíma að",
    "hversu lengi væri ég að",
    "hversu lengi værum við að",
    "hversu lengi væri maður að",
    "hve lengi væri ég að",
    "hve lengi værum við að",
    "hve lengi væri maður að",
    "hversu langan tíma tæki að",
    "hversu langan tíma tæki það að",
    "hversu langan tíma tæki það mig að",
    "hvað er langt að",
    "hversu lengi tekur að",
    "hversu lengi tekur það að",
)

_TT_MODES = {
    "ganga": "walking",
    "labba": "walking",
    "rölta": "walking",
    "tölta": "walking",
    "skunda": "walking",
    # Distance matrix API doesn't support bike routes for Iceland
    # "hjóla": "bicycling",
    # "fara á hjóli": "bicycling",
    # "fara á reiðhjóli": "bicycling",
    # "ferðast á hjóli": "bicycling",
    # "ferðast á reiðhjóli": "bicycling",
    "keyra": "driving",
    "keyra á bíl": "driving",
    "aka": "driving",
    "fara á bílnum": "driving",
    "ferðast í bíl": "driving",
    "ferðast á bíl": "driving",
    "á bíl": "driving",
}

_PREPS = ("á", "í", "til", "að")
_TT_PREP_PREFIX = ("út", "upp", "niður", "vestur", "norður", "austur", "suður")
_TT_PREPS: List[str] = []

# Construct complex regexes for travel time queries
for p in _PREPS:
    _TT_PREPS.append(p)
    for pfx in _TT_PREP_PREFIX:
        _TT_PREPS.append(pfx + " " + p)

_PREFIX_RX = r"{0}".format("|".join(_TT_PREFIXES))
_VERBS_RX = r"{0}".format("|".join(_TT_MODES.keys()))
_PREPS_RX = r"{0}".format("|".join(_TT_PREPS))
_DEST_RX = r".+$"

_QTRAVELTIME_REGEXES = (
    r"^({0}) (({1}) ({2}) ({3}))".format(_PREFIX_RX, _VERBS_RX, _PREPS_RX, _DEST_RX),
)


_HOME_LOC = frozenset(
    (
        "heim",
        "heim til mín",
        "heimili mitt",
        "heimili mínu",
        "heimahús mitt",
        "heimahúsi mínu",
        # "heimilisfang",
        # "heimilisfangi",
        "heimilisfang mitt",
        "heimilisfangi mínu",
    )
)


def _addr2nom(address: str) -> str:
    """Convert location name to nominative form."""
    if not address:
        return ""
    try:
        nom = NounPhrase(cap_first(address)).nominative or address
    except Exception:
        nom = address
    return nom


def dist_answer_for_loc(matches: Match[str], query: Query) -> Optional[AnswerTuple]:
    """Generate response to distance query, e.g.
    "Hvað er ég langt frá X?" """
    locname = matches.group(1)
    loc_nf = _addr2nom(locname) or locname

    # Try to avoid answering certain queries here
    loc_lower = locname.lower()
    # TODO: Solve this by configuring qmodule priority
    if any(
        s in loc_lower
        for s in (
            "strætó",
            "stoppistöð",
            "strætisvagn",
            "biðstöð",
            "stoppustöð",
            "stræto",
            "strædo",
            "jólin",
            "jól",
            "páska",
        )
    ):
        return None

    # Check if user is asking about distance from home address
    is_home = False
    loc: Tuple[float, float]
    if loc_lower in _HOME_LOC:
        ad = query.client_data("address")
        if not ad:
            return gen_answer(
                "Ég veit ekki hvar þú átt heima, en þú getur sagt mér það."
            )
        elif "lat" not in ad or "lon" not in ad:
            return gen_answer("Ég veit ekki hvar heimili þitt er.")
        else:
            is_home = True
            loc = (cast(float, ad["lat"]), cast(float, ad["lon"]))
            loc_nf = f'{ad["street"]} {ad["number"]}'
    else:
        # Talk to geocode API
        res = query_geocode_api_addr(loc_nf)

        # Verify sanity of API response
        if (
            not res
            or "status" not in res
            or res["status"] != "OK"
            or not res.get("results")
        ):
            return None

        # Extract location coordinates from result
        coords = res["results"][0]["geometry"]["location"]
        loc = (coords["lat"], coords["lng"])

    # Calculate distance, round it intelligently and format num string
    if query.location is None:
        km_dist = 0.0
    else:
        km_dist = distance(query.location, loc)

    # Generate answer
    answer = distance_desc(km_dist, abbr=True)
    response = dict(answer=answer, distance=km_dist)

    loc_nf = capitalize_placename(loc_nf)
    dist = distance_desc(km_dist, case="þf", num_to_str=True)
    # Turn numbers to neutral in loc_nf for voice
    voice = f"{gssml(loc_nf, type='numbers', gender='hk')} er {dist} í burtu"

    query.set_key(loc_nf)

    # Beautify by capitalizing remote loc name
    uc = locname if is_home else capitalize_placename(locname)
    bq = query.beautified_query.replace(locname, uc)

    # Hack to fix the fact that the voice recognition often misses "ég"
    prefix_fix = "Hvað er langt frá"
    if bq.startswith(prefix_fix):
        bq = bq.replace(prefix_fix, "Hvað er ég langt frá")
    query.set_beautified_query(bq)

    query.set_context(dict(subject=loc_nf))

    return response, answer, voice


def traveltime_answer_for_loc(
    matches: Match[str], query: Query
) -> Optional[AnswerTuple]:
    """Generate answer to travel time query e.g.
    "Hvað er ég lengi að ganga/keyra í/til X?" """
    action_desc, tmode, locname = matches.group(2, 3, 5)

    loc_nf = _addr2nom(locname)
    mode = _TT_MODES.get(tmode, "walking")

    # Query API
    if query.location is None:
        res = None
    else:
        res = query_traveltime_api(query.location, loc_nf, mode=mode)

    # Verify sanity of API response
    if (
        not res
        or "status" not in res
        or res["status"] != "OK"
        or not res.get("rows")
        or not len(res["rows"])
    ):
        return None

    # Extract info we want
    elm = res["rows"][0]["elements"][0]
    if elm["status"] != "OK":
        return None

    # dur_desc = elm["duration"]["text"]  # API duration description
    dur_sec = int(elm["duration"]["value"])
    dur_desc = time_period_desc(dur_sec, case="þf")
    dur_desc_voice = time_period_desc(dur_sec, case="þf", num_to_str=True)
    dist_desc = elm["distance"]["text"]

    # Generate answer
    answer = f"{dur_desc} ({dist_desc})."
    response = dict(answer=answer, duration=dur_sec)
    voice = f"Að {action_desc} tekur um það bil {dur_desc_voice}"

    # Key is the remote loc in nominative case
    query.set_key(capitalize_placename(loc_nf))

    # Beautify by capitalizing remote loc name
    bq = query.beautified_query.replace(locname, capitalize_placename(locname))

    # Hack to fix common mistake in speech recognition
    prefix_fix = "Hvað er lengi "
    if bq.startswith(prefix_fix):
        bq = bq.replace(prefix_fix, "Hvað er ég lengi ")
    query.set_beautified_query(bq)

    query.set_context(dict(subject=loc_nf))

    return response, answer, voice


_UNKNOWN_LOC_RESP = "Ég veit ekki hvar þú ert, og get því ekki reiknað út vegalengdir."


def handle_plain_text(q: Query) -> bool:
    """Handle a plain text query."""
    ql = q.query_lower.rstrip("?")

    matches: Optional[Match[str]] = None
    handler: Optional[Callable[[Match[str], Query], Optional[AnswerTuple]]] = None

    # Distance queries
    for rx in _QDISTANCE_REGEXES:
        matches = re.search(rx, ql)
        if matches is not None:
            handler = dist_answer_for_loc
            break

    # Travel time queries
    if not handler:
        for rx in _QTRAVELTIME_REGEXES:
            matches = re.search(rx, ql)
            if matches is not None:
                handler = traveltime_answer_for_loc
                break

    # Nothing caught by regexes, bail
    if not handler or not matches:
        return False

    # Look up answer in geo API
    try:
        if q.location:
            answ = handler(matches, q)
        else:
            answ = gen_answer(_UNKNOWN_LOC_RESP)
    except Exception as e:
        logging.warning(f"Exception generating answer from geocode API: {e}")
        q.set_error(f"E_EXCEPTION: {e}")
        answ = None

    if answ:
        q.set_qtype(_DISTANCE_QTYPE)
        q.set_answer(*answ)
        q.set_source("Google Maps")
        return True

    return False
