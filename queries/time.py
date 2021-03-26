"""

    Greynir: Natural language processing for Icelandic

    Time query response module

    Copyright (C) 2021 Miðeind ehf.

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


    This module is an example of a plug-in query response module
    for the Greynir query subsystem. It handles plain text queries, i.e.
    ones that do not require parsing the query text. For this purpose
    it only needs to implement the handle_plain_text() function, as
    shown below.

    This particular module handles queries related to time and timezones.

"""

# TODO: "Í hvaða tímabelti er ég?"

import random
from datetime import datetime
from typing import cast
from pytz import country_timezones, timezone

from reynir import NounPhrase
from geo import (
    isocode_for_country_name,
    lookup_city_info,
    capitalize_placename,
    iceprep_for_cc,
    iceprep_for_placename,
)
from query import Query
from queries import timezone4loc, gen_answer, icequote

_TIME_QTYPE = "Time"


# Lemmas of keywords that could indicate that the user is trying to use this module
TOPIC_LEMMAS = ["klukka", "tími"]


def help_text(lemma: str) -> str:
    """Help text to return when query.py is unable to parse a query but
    one of the above lemmas is found in it"""
    return "Ég get svarað ef þú spyrð til dæmis: {0}?".format(
        random.choice(
            (
                "Hvað er klukkan",
                "Hvað líður tímanum",
                "Hvað er klukkan í Kaupmannahöfn",
                "Hvað er klukkan í Tókýó",
            )
        )
    )


_TIME_QUERIES = frozenset(
    (
        "klukkan",
        "tíminn",
        "hvað klukkan",
        "hver klukkan",
        "hvað tíminn",
        "hver tíminn",
        "hvað er klukkan",
        "hvað er klukkan eiginlega",
        "hvað er klukkan nákvæmlega",
        "hvað er klukkan eins og stendur",
        "hvað er klukkan núna",
        "hvað er klukkan hér",
        "hver er klukkan",
        "hver er klukkan núna",
        "hver er klukkan nákvæmlega",
        "hver er klukkan eins og stendur",
        "hvað er tíminn",
        "hvað er tíminn núna",
        "hvað er tíminn nákvæmlega",
        "hvað er tíminn eins og stendur",
        "hver er tíminn",
        "hver er tíminn núna",
        "hver er tíminn nákvæmlega",
        "hver er tíminn eins og stendur",
        "hvað líður tímanum",
        "veistu hvað klukkan er",
        "veist þú hvað klukkan er",
        "veistu hvað klukkan er núna",
        "veist þú hvað klukkan er núna",
    )
)

_TIME_IN_LOC_QUERIES = frozenset(
    (
        "klukkan í",
        "klukkan á",
        "tíminn í",
        "tíminn á",
        "hvað klukkan í",
        "hvað klukkan á",
        "hvað er klukkan í",
        "hvað er klukkan á",
        "hver er klukkan í",
        "hver er klukkan á",
        "hvað er tíminn í",
        "hvað er tíminn á",
        "hver er tíminn í",
        "hver er tíminn á",
    )
)


def handle_plain_text(q: Query) -> bool:
    """Handle a plain text query, contained in the q parameter
    which is an instance of the query.Query class.
    Returns True if the query was handled, and in that case
    the appropriate properties on the Query instance have
    been set, such as the answer and the query type (qtype).
    If the query is not recognized, returns False."""
    ql = q.query_lower.rstrip("?")

    # Timezone being asked about
    tz = None
    # Whether user asked for the time in a particular location
    specific_desc = None

    if ql in _TIME_QUERIES:
        # Use location to determine time zone
        tz = timezone4loc(q.location, fallback="IS")
    else:
        locq = [x for x in _TIME_IN_LOC_QUERIES if ql.startswith(x.lower())]
        if not locq:
            return False  # Not matching any time queries
        # This is a query about the time in a particular location, i.e. country or city
        # Cut away question prefix, leaving only loc name
        loc = ql[len(locq[0]) :].strip()
        if not loc:
            return False  # No location string
        # Intelligently capitalize country/city/location name
        loc = capitalize_placename(loc)

        # Look up nominative
        loc_nom = NounPhrase(loc).nominative or loc
        prep = "í"

        # Check if loc is a recognised country or city name
        cc = isocode_for_country_name(loc_nom)
        if cc and cc in country_timezones:
            # Look up country timezone
            # Use the first timezone although some countries have more than one
            # The timezone list returned by pytz is ordered by "dominance"
            tz = country_timezones[cc][0]
            prep = iceprep_for_cc(cc)
        else:
            # It's not a country name, look up in city database
            info = lookup_city_info(loc_nom)
            if info:
                top = info[0]
                location = (
                    cast(float, top.get("lat_wgs84")),
                    cast(float, top.get("long_wgs84")),
                )
                tz = timezone4loc(location)
                prep = iceprep_for_placename(loc_nom)

        if tz:
            # "Klukkan í Lundúnum er" - Used for voice answer
            dat = NounPhrase(loc_nom).dative or loc
            specific_desc = "Klukkan {0} {1} er".format(prep, dat)
        else:
            # Unable to find the specified location
            q.set_qtype(_TIME_QTYPE)
            q.set_key(loc)
            q.set_answer(
                *gen_answer(
                    "Ég gat ekki flett upp staðsetningunni {0}".format(icequote(loc))
                )
            )
            return True

    # We have a timezone. Return formatted answer.
    if tz:
        now = datetime.now(timezone(tz))

        desc = specific_desc or "Klukkan er"

        # Create displayable answer
        answer = "{0:02}:{1:02}".format(now.hour, now.minute)
        # A detailed response object is usually a list or a dict
        response = dict(answer=answer)
        # A voice answer is a plain string that will be
        # passed as-is to a voice synthesizer
        voice = "{0} {1}:{2:02}.".format(desc, now.hour, now.minute)

        q.set_qtype(_TIME_QTYPE)
        q.set_key(tz)  # Query key is the timezone
        q.set_answer(response, answer, voice)
        return True

    return False
