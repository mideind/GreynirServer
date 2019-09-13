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

import re
import logging
import math

from queries import gen_answer, query_geocode_API_addr
from geo import distance


_DISTANCE_QTYPE = "Distance"


_QREGEXES = (
    r"^hvað er ég langt frá (.+)$",
    r"^hvað er ég langt í burtu frá (.+)$",
    r"^hversu langt er ég frá (.+)$",
    r"^hve langt er ég frá (.+)$",
    r"^hvað er langt á (.+)$",
    r"^hvað er langt í (.+)$",
)


def answer_for_remote_loc(locname, query):
    if not query.location:
        return gen_answer("Ég veit ekki hvar þú ert.")

    res = query_geocode_API_addr(locname)

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
    km_dist = round(km_dist, 1 if km_dist < 10 else 0)
    dist = km_dist if km_dist > 1.0 else int(math.ceil((km_dist * 1000.0) / 10.0)) * 10
    dist_str = str(dist).replace(".", ",").rstrip(",0")

    # Units of measurement
    unit = "kílómetra" if km_dist > 1.0 else "metra"
    unit_abbr = "km" if km_dist > 1.0 else "m"

    # Generate answer
    answer = "{0} {1}".format(dist_str, unit_abbr)
    response = dict(answer=answer)
    voice = "Þú ert {0} {1} frá {2}".format(dist_str, unit, locname)

    return response, answer, voice


def handle_plain_text(q):
    ql = q.query_lower.rstrip("?")

    remote_loc = None
    for rx in _QREGEXES:
        m = re.search(rx, ql)
        if m:
            remote_loc = m.group(1)
            break

    if not remote_loc:
        return False

    try:
        answ = answer_for_remote_loc(remote_loc, q)
    except Exception as e:
        logging.warning("Exception looking up addr in geocode API: {0}".format(e))
        answ = None
    if not answ:
        return False

    q.set_key(remote_loc)
    q.set_qtype(_DISTANCE_QTYPE)
    q.set_answer(*answ)

    return True
