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

"""

from datetime import datetime
from pytz import country_timezones, timezone
from reynir.bindb import BIN_Db
from geo import isocode_for_country_name, lookup_city_info


def handle_plain_text(q):
    """ Handle a plain text query, contained in the q parameter
        which is an instance of the query.Query class.
        Returns True if the query was handled, and in that case
        the appropriate properties on the Query instance have
        been set, such as the answer and the query type (qtype).
        If the query is not recognized, returns False. """
    ql = q.query_lower
    if ql.endswith("?"):
        ql = ql[:-1]

    if ql == "hvað er klukkan":
        # This is a query we recognize and handle
        q.set_qtype("Time")
        now = datetime.utcnow()
        # Calculate a 'single best' displayable answer
        answer = "{0:02}:{1:02}".format(now.hour, now.minute)
        # A detailed response object is usually a list or a dict
        response = dict(answer=answer)
        # A voice answer is a plain string that will be
        # passed as-is to a voice synthesizer
        voice = "Klukkan er {0} {1:02}.".format(now.hour, now.minute)
        q.set_answer(response, answer, voice)
        return True
    elif ql.startswith("hvað er klukkan á ") or ql.startswith("hvað er klukkan í "):
        loc = ql[18:]
        # Capitalize each word in country/city name
        loc = " ".join([c.capitalize() for c in loc.split()])

        # Look up nominative
        # TODO: This only works for single-word city/country names (fails for e.g. "Nýja Jórvík")
        bres = BIN_Db().lookup_nominative(loc)
        words = [m.stofn for m in bres]
        words.append(loc)  # In case it doesn't exist in BÍN (e.g. "New York")

        # Check if any word is a recognised country or city name
        for w in words:
            cc = isocode_for_country_name(w)
            if not cc:
                info = lookup_city_info(w)
                if info:
                    cc = info[0].get("country")
            if cc:
                break

        if not cc or cc not in country_timezones:
            return False

        # Look up timezone for country
        # We use the first timezone although some countries have more than one
        # TODO: Be smarter about this.
        ct = country_timezones[cc]
        tz = timezone(country_timezones[cc][0])
        now = datetime.now(tz)

        answer = "{0:02}:{1:02}".format(now.hour, now.minute)
        response = dict(answer=answer)
        voice = "{0} er {1} {2:02}.".format(ql[8:], now.hour, now.minute)

        q.set_qtype("Time")
        q.set_beautified_query("{0}{1}".format(q.beautified_query[:18], loc))
        q.set_answer(response, answer, voice)


        return True

    return False
