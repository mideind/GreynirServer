"""

    Reynir: Natural language processing for Icelandic

    Distance query response module

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


    This module handles distance-related queries.

"""

# TODO: This module should probably use grammar instead of regexes
# TODO: Handle travel time queries such as "Hvað er ég lengi að ganga til X?",
#       or "Hvað er ég lengi að keyra í Y?"

import re
import logging
import math

from reynir.bindb import BIN_Db
from queries import gen_answer, query_geocode_api_addr
from geo import distance


_DISTANCE_QTYPE = "Distance"


# TODO: This may grab queries of the form "Hvað er langt í jólin"!
_QDISTANCE_REGEXES = (
    r"^hvað er ég langt frá (.+)$",
    r"^hvað er ég langt í burtu frá (.+)$",
    r"^hversu langt er ég frá (.+)$",
    r"^hve langt er ég frá (.+)$",
    r"^hvað er langt á (.+)$",
    r"^hvað er langt upp á (.+)$",
    r"^hvað er langt í ([^0-9.].+)$",
    r"^hvað er langt upp í (.+)$",
    r"^hvað er langt til (.+)$",
    r"^hversu langt er til (.+)$",
)

# TODO: Handle queries of this kind, incl. driving and cycling
_QTRAVELTIME_REGEXES = (
    r"^hvað er ég lengi að ganga á (.+)$",
    r"^hvað er ég lengi að ganga upp á (.+)$",
    r"^hvað er ég lengi að ganga niður á (.+)$",
    r"^hvað er ég lengi að ganga í (.+)$",
    r"^hvað er ég lengi að rölta á (.+)$",
    r"^hvað er ég lengi að rölta í (.+)$",
)


def _addr2nom(address):
    """ Convert location name to nominative form """
    # TODO: Implement more intelligently
    # This is a tad simplistic and mucks up some things,
    # e.g. "Ráðhús Reykjavíkur" becomes "Ráðhús Reykjavík"
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


def dist_answer_for_loc(locname, query):
    """ Generate response to distance query """
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

    # Extract location coordinates from API result
    topres = res["results"][0]
    coords = topres["geometry"]["location"]
    loc = (coords["lat"], coords["lng"])

    # Calculate distance, round it intelligently and format num string
    km_dist = distance(query.location, loc)

    # E.g. 7,3 kílómetra
    if km_dist >= 1.0:
        km_dist = round(km_dist, 1 if km_dist < 10 else 0)
        dist = str(km_dist).replace(".", ",")
        dist = re.sub(r",0$", "", dist)
        unit = "kílómetra"
        unit_abbr = "km"
    # E.g. 940 metra
    else:
        dist = int(math.ceil((km_dist * 1000.0) / 10.0) * 10)  # Round to nearest 10 m
        unit = "metra"
        unit_abbr = "m"

    # Generate answer
    answer = "{0} {1}".format(dist, unit_abbr)
    response = dict(answer=answer)
    loc_nf = loc_nf[0].upper() + loc_nf[1:]
    voice = "{2} er {0} {1} í burtu".format(dist, unit, loc_nf)

    query.set_key(loc_nf)

    # Beautify by capitalizing remote loc name
    uc = locname.title()
    bq = query.beautified_query.replace(locname, uc)
    query.set_beautified_query(bq)

    return response, answer, voice


def handle_plain_text(q):
    """ Handle a plain text query, contained in the q parameter """
    ql = q.query_lower.rstrip("?")

    remote_loc = None
    for rx in _QDISTANCE_REGEXES:
        m = re.search(rx, ql)
        if m:
            remote_loc = m.group(1)
            handler = dist_answer_for_loc
            break
    else:
        # Nothing caught by regexes, bail
        return False

    # Look up in geo API
    try:
        if q.location:
            answ = handler(remote_loc, q)
        else:
            answ = gen_answer("Ég veit ekki hvar þú ert.")
    except Exception as e:
        logging.warning("Exception generating answer from geocode API: {0}".format(e))
        q.set_error("E_EXCEPTION: {0}".format(e))
        answ = None

    if answ:
        q.set_qtype(_DISTANCE_QTYPE)
        q.set_answer(*answ)
        return True

    return False
