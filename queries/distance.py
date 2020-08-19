"""

    Greynir: Natural language processing for Icelandic

    Distance query response module

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


    This module handles distance-related queries.

"""

# TODO: This module should probably use grammar instead of regexes
# TODO: "Hvað er langt á milli X og Y?"
# TODO: "Hvað er langt til tunglsins"? "Hvað er langt til Mars?"
# TODO: Identify when user is present at the location, respond "Þú ert í/á X"
# TODO: "Hvað er langur/margra kílómetra göngutúr í/á X?"

import re
import logging
import math

from reynir.bindb import BIN_Db
from queries import (
    gen_answer,
    time_period_desc,
    distance_desc,
    query_geocode_api_addr,
    query_traveltime_api,
)
from geo import distance, capitalize_placename


_DISTANCE_QTYPE = "Distance"


# TODO: This may grab queries of the form "Hvað er langt í jólin"!
_QDISTANCE_REGEXES = (
    r"^hvað er ég langt frá (.+)$",
    r"^hvað er ég langt í burtu frá (.+)$",
    r"^hversu langt er ég frá (.+)$",
    r"^hve langt er ég frá (.+)$",
    r"^hvað er langt\s?(?:héðan)?\s?(?:austur|vestur|norður|suður)? á (.+)$",
    r"^hvað er langt\s?(?:héðan)? upp á (.+)$",
    r"^hvað er langt\s?(?:héðan)? niður á (.+)$",
    r"^hvað er langt\s?(?:héðan)?\s?(?:austur|vestur|norður|suður)? í ([^0-9.].+)$",
    r"^hvað er langt\s?(?:héðan)? upp í (.+)$",
    r"^hvað er langt\s?(?:héðan)? til (.+)$",
    r"^hvað er langt\s?(?:héðan)? út á ([^0-9.].+)$",
    r"^hversu langt er\s?(?:austur|vestur|norður|suður)? til (.+)$",
    r"^hversu langt er út á (.+)$",
    r"^hversu marga kílómetra er ég frá (.+)$",
    r"^hversu marga metra er ég frá (.+)$",
)

# Travel time questions
_TT_PREFIXES = (
    "hvað er ég lengi að",
    "hvað er maður lengi að",
    "hvað erum við lengi að",
    "hversu lengi er ég að",
    "hversu lengi er maður að",
    "hversu lengi erum að",
    "hversu lengi að",
    "hve lengi að",
    "hve lengi er ég að",
    "hve lengi er maður að",
    "hve lengi erum við að",
    "hvað tekur langan tíma að",
    "hvað tekur mig langan tíma að",
    "hvað tekur mann langan tíma að",
    "hvað tekur það langan tíma að",
    "hvað tekur það mig langan tíma að",
    "hvað tekur það mann langan tíma að",
    "hversu langan tíma tekur að",
    "hversu langan tíma tekur það að",
    "hversu langan tíma tekur það mig að",
    "hvað væri ég lengi að",
    "hvað væri maður lengi að",
    "hvað tæki það langan tíma að",
    "hvað tæki mann langan tíma að",
    "hvað tæki það mann langan tíma að",
    "hversu lengi væri ég að",
    "hversu lengi væri maður að",
    "hve lengi væri ég að",
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
    "hjóla": "cycling",
    "fara á hjóli": "cycling",
    "fara á reiðhjóli": "cycling",
    "ferðast á hjóli": "cycling",
    "ferðast á reiðhjóli": "cycling",
    "keyra": "driving",
    "keyra á bíl": "driving",
    "aka": "driving",
    "fara á bílnum": "driving",
    "ferðast í bíl": "driving",
    "ferðast á bíl": "driving",
    "á bíl": "driving",
}

_PREPS = ("á", "í", "til")
_TT_PREP_PREFIX = ("upp", "niður", "vestur", "norður", "austur", "suður", "út")
_TT_PREPS = []

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


def _addr2nom(address):
    """ Convert location name to nominative form. """
    # TODO: Implement more intelligently.
    # This is a tad simplistic and mucks up some things,
    # e.g. "Ráðhús Reykjavíkur" becomes "Ráðhús Reykjavík".
    with BIN_Db.get_db() as db:
        nf = []
        for w in address.split():
            bin_res = db.lookup_nominative(w)
            if not bin_res and not w.islower():
                # Try lowercase form
                bin_res = db.lookup_nominative(w.lower())
            if bin_res:
                nf.append(bin_res[0].ordmynd)
            else:
                nf.append(w)
        return " ".join(nf)


def dist_answer_for_loc(matches, query):
    """ Generate response to distance query. """
    locname = matches.group(1)
    loc_nf = _addr2nom(locname[0].upper() + locname[1:])
    res = query_geocode_api_addr(loc_nf)

    # Verify sanity of API response
    if (
        not res
        or not "status" in res
        or res["status"] != "OK"
        or not res.get("results")
    ):
        return None

    # Try to avoid answering bus queries here
    loc_lower = locname.lower()
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
        )
    ):
        return None

    # Extract location coordinates from API result
    topres = res["results"][0]
    coords = topres["geometry"]["location"]
    loc = (coords["lat"], coords["lng"])

    # Calculate distance, round it intelligently and format num string
    km_dist = distance(query.location, loc)

    # Generate answer
    answer = distance_desc(km_dist, abbr=True)
    response = dict(answer=answer)

    loc_nf = loc_nf[0].upper() + loc_nf[1:]
    dist = distance_desc(km_dist, case="þf")
    voice = "{0} er {1} í burtu".format(loc_nf, dist)

    query.set_key(capitalize_placename(loc_nf))

    # Beautify by capitalizing remote loc name
    uc = capitalize_placename(locname)
    bq = query.beautified_query.replace(locname, uc)
    query.set_beautified_query(bq)
    query.set_context(dict(subject=loc_nf))

    return response, answer, voice


def traveltime_answer_for_loc(matches, query):
    action_desc, tmode, locname = matches.group(2, 3, 5)

    loc_nf = _addr2nom(locname[0].upper() + locname[1:])
    mode = _TT_MODES.get(tmode, "walking")

    # Query API
    res = query_traveltime_api(query.location, loc_nf, mode=mode)

    # Verify sanity of API response
    if (
        not res
        or not "status" in res
        or res["status"] != "OK"
        or not res.get("rows")
        or not len(res["rows"])
    ):
        return None

    # Extract info we want
    elm = res["rows"][0]["elements"][0]
    if elm["status"] != "OK":
        return None

    # dur_desc = elm["duration"]["text"]
    dur_sec = int(elm["duration"]["value"])
    dur_desc = time_period_desc(dur_sec, case="þf")
    dist_desc = elm["distance"]["text"]

    # Generate answer
    answer = "{0} ({1}).".format(dur_desc, dist_desc)
    response = dict(answer=answer)
    voice = "Að {0} tekur um það bil {1}".format(action_desc, dur_desc)

    # Key is the remote loc in nominative case
    query.set_key(capitalize_placename(loc_nf))

    # Beautify by capitalizing remote loc name
    uc = capitalize_placename(locname)
    bq = query.beautified_query.replace(locname, uc)
    query.set_beautified_query(bq)
    query.set_context(dict(subject=loc_nf))

    return response, answer, voice


def handle_plain_text(q):
    """ Handle a plain text query, contained in the q parameter. """
    ql = q.query_lower.rstrip("?")

    matches = None
    handler = None

    # Distance queries
    for rx in _QDISTANCE_REGEXES:
        matches = re.search(rx, ql)
        if matches:
            handler = dist_answer_for_loc
            break

    # Travel time queries
    if not handler:
        for rx in _QTRAVELTIME_REGEXES:
            matches = re.search(rx, ql)
            if matches:
                handler = traveltime_answer_for_loc
                break

    # Nothing caught by regexes, bail
    if not handler or not matches:
        return False

    # Look up in geo API
    try:
        if q.location:
            answ = handler(matches, q)
        else:
            answ = gen_answer("Ég veit ekki hvar þú ert.")
    except Exception as e:
        logging.warning("Exception generating answer from geocode API: {0}".format(e))
        q.set_error("E_EXCEPTION: {0}".format(e))
        answ = None

    if answ:
        q.set_qtype(_DISTANCE_QTYPE)
        q.set_answer(*answ)
        q.set_source("Google Maps")
        return True

    return False
