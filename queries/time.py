"""

    Reynir: Natural language processing for Icelandic

    Clock query response module

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


    This module is an example of a plug-in query response module
    for the Greynir query subsystem. It handles plain text queries, i.e.
    ones that do not require parsing the query text. For this purpose
    it only needs to implement the handle_plain_text() function, as
    shown below.

    This particular module handles queries related to time and timezones.

"""

from datetime import datetime
from pytz import country_timezones, timezone
from reynir.bindb import BIN_Db
from geo import isocode_for_country_name, lookup_city_info, ICELAND_ISOCODE
from tzwhere import tzwhere


TIME_QTYPE = "Time"


def handle_plain_text(q):
    """ Handle a plain text query, contained in the q parameter
        which is an instance of the query.Query class.
        Returns True if the query was handled, and in that case
        the appropriate properties on the Query instance have
        been set, such as the answer and the query type (qtype).
        If the query is not recognized, returns False. """
    ql = q.query_lower.rstrip("?")

    tz = None  # Timezone being asked about
    specific_loc = None

    if ql == "hvað er klukkan":
        # Use location, if available, to determine time zone
        loc = q.location
        if loc:
            # TODO: This seems to be rather slow :(
            tz = tzwhere.tzwhere().tzNameAt(loc[0], loc[1])
        else:
            # Default to Iceland's timezone
            tz = country_timezones[ICELAND_ISOCODE][0]

    elif ql.startswith("hvað er klukkan á ") or ql.startswith("hvað er klukkan í "):
        # Query about the time in a particular location, i.e. country or city
        loc = ql[18:]
        # Capitalize each word in country/city name
        loc = " ".join([c.capitalize() for c in loc.split()])

        # Look up nominative
        # TODO: This only works for single-word city/country names
        # in BÍN and could be improved (e.g. fails for "Nýja Jórvík")
        bres = BIN_Db().lookup_nominative(loc)
        words = [m.stofn for m in bres]
        words.append(loc)  # In case it's not in BÍN (e.g. "New York", "San José")

        # Check if any word is a recognised country or city name
        for w in words:
            cc = isocode_for_country_name(w)
            if cc and cc in country_timezones:
                # Look up country timezone
                # Use the first timezone although some countries have more than one
                # The timezone list returned by pytz is ordered by "dominance"
                tz = country_timezones[cc][0]
            else:
                # It's not a country name, look up in city database
                info = lookup_city_info(w)
                if info:
                    top = info[0]
                    (lat, lon) = (top.get("lat_wgs84"), top.get("long_wgs84"))
                    tz = tzwhere.tzwhere().tzNameAt(lat, lon)
            if tz:
                # We have a timezone
                break

        # "Klukkan í Lundúnum er" - Used for voice answer
        specific_loc = "{0} er".format(ql[8:])

        # Beautify query by capitalizing the country/city name
        q.set_beautified_query("{0}{1}".format(q.beautified_query[:18], loc))

    # We have a timezone. Return formatted answer.
    if tz:
        now = datetime.now(timezone(tz))

        desc = specific_loc if specific_loc else "Klukkan er"

        # Create displayable answer
        answer = "{0:02}:{1:02}".format(now.hour, now.minute)
        # A detailed response object is usually a list or a dict
        response = dict(answer=answer)
        # A voice answer is a plain string that will be
        # passed as-is to a voice synthesizer
        voice = "{0} {1} {2:02}.".format(desc, now.hour, now.minute)
        q.set_qtype(TIME_QTYPE)
        q.set_answer(response, answer, voice)
        return True

    return False
