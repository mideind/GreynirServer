"""

    Greynir: Natural language processing for Icelandic

    Time query response module

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


    This particular module handles queries related to time and timezones.

"""

# TODO: "Í hvaða tímabelti er ég?"
# TODO: "Hvað er klukkan í tókýó?" should capitalize Tókýó

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
from queries import Query
from queries.util import timezone4loc, gen_answer
from speech.trans import gssml
from utility import icequote

_TIME_QTYPE = "Time"


# Lemmas of keywords that could indicate that the user is trying to use this module
TOPIC_LEMMAS = ["klukka", "tími"]


def help_text(lemma: str) -> str:
    """Help text to return when query processor is unable to parse a query but
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
        "núna",
        "hvað klukkan",
        "hvað klukkan núna",
        "hver klukkan",
        "hvað tíminn",
        "hvað tíminn núna",
        "hver tíminn",
        "tíminn núna",
        "klukkan núna",
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
        "hver tíminn",
        "hvað er tíminn",
        "hvað er tíminn núna",
        "hvað er tíminn nákvæmlega",
        "hvað er tíminn eins og stendur",
        "hver er tíminn",
        "hver er tíminn núna",
        "hver er tíminn nákvæmlega",
        "hver er tíminn eins og stendur",
        "hvað líður tímanum",
        "hvernig líður tímanum",
        "veistu hvað klukkan",
        "veistu hvað klukkan er",
        "veist þú hvað klukkan",
        "veist þú hvað klukkan er",
        "veistu hvað klukkan er núna",
        "veist þú hvað klukkan er núna",
        "veistu hvað tímanum líður",
        "veist þú hvað tímanum líður",
        "segðu mér hvað klukkan er",
        "segðu mér hvað er klukkan",
        "segðu mér hvað tímanum líður",
        "geturðu sagt mér hvað klukkan er",
        "getur þú sagt mér hvað klukkan er",
        "gætirðu sagt mér hvað klukkan er",
        "gætir þú sagt mér hvað klukkan er",
        "viltu segja mér hvað klukkan er",
        "vilt þú segja mér hvað klukkan er",
        "geturðu sagt mér hvað tímanum líður",
        "getur þú sagt mér hvað tímanum líður",
        "gætirðu sagt mér hvað tímanum líður",
        "gætir þú sagt mér hvað tímanum líður",
        "viltu segja mér hvað tímanum líður",
        "vilt þú segja mér hvað tímanum líður",
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


# Hardcoded fixes for nom. placename lookups
_LOC2NOM_FIXES = {
    # BÍN contains placename "Stokkhólmi" as opposed to more probable "Stokkhólmur"
    "Stokkhólmi": "Stokkhólmur",
}


def _loc2nom(loc: str) -> str:
    """Return location name in nominative case."""
    fix = _LOC2NOM_FIXES.get(loc)
    if fix:
        return fix
    return NounPhrase(loc).nominative or loc


def handle_plain_text(q: Query) -> bool:
    """Handle plain text query."""
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
        loc_nom = _loc2nom(loc)
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
            specific_desc = f"Klukkan {prep} {dat} er"
        else:
            # Unable to find the specified location
            q.set_qtype(_TIME_QTYPE)
            q.set_key(loc)
            q.set_answer(
                *gen_answer(f"Ég gat ekki flett upp staðsetningunni {icequote(loc)}")
            )
            return True

    # We have a timezone. Return formatted answer.
    if tz:
        # This is one of the very few places where datetime.utcnow() is not used
        now = datetime.now(timezone(tz))

        desc = specific_desc or "Klukkan er"

        # Create displayable answer
        answer = f"{now.hour:02}:{now.minute:02}"
        # A detailed response object is usually a list or a dict
        response = dict(answer=answer)
        # A voice answer is a plain string that will be
        # passed as-is to a voice synthesizer
        voice = f"{desc} {gssml(answer, type='time')}."

        q.set_qtype(_TIME_QTYPE)
        q.set_key(tz)  # Query key is the timezone
        q.set_answer(response, answer, voice)
        return True

    return False
