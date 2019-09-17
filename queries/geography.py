"""

    Reynir: Natural language processing for Icelandic

    Geography query response module

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


    This module handles geography-related queries.

"""

# "Hver er höfuðborg [LANDS]?"
# "Í hvaða landi er [BORG]?"
# "Hvað búa margir í [BORG]?"

from cityloc import capital_for_cc
from geo import icelandic_city_name, isocode_for_country_name
from reynir.bindb import BIN_Db


_GEO_QTYPE = "Geography"


def handle_plain_text(q):
    """ Handle a plain text query, contained in the q parameter
        which is an instance of the query.Query class.
        Returns True if the query was handled, and in that case
        the appropriate properties on the Query instance have
        been set, such as the answer and the query type (qtype).
        If the query is not recognized, returns False. """
    ql = q.query_lower.rstrip("?").strip()
    pfx = "hver er höfuðborg "

    if ql.startswith(pfx):
        country = q.query[len(pfx) :].strip()
        if not len(country):
            return False

        country = country[0].upper() + country[1:]  # Capitalize first char
        # TODO: This only works for single-word country names
        # Transform country name from genitive to nominative
        bres = BIN_Db().lookup_nominative(country, cat="no")
        words = [m.stofn for m in bres]
        if not words:
            return False

        # Look up ISO code from country name
        nom_country = words[0]
        cc = isocode_for_country_name(nom_country)
        if not cc:
            return False

        # Find capital city, given the country code
        capital = capital_for_cc(cc)
        if not capital:
            return False

        # Use the Icelandic name for the city
        ice_cname = icelandic_city_name(capital["name_ascii"])

        answer = ice_cname
        response = dict(answer=answer)
        voice = "Höfuðborg {0} er {1}".format(country, answer)

        q.set_answer(response, answer, voice)
        q.set_qtype(_GEO_QTYPE)

        return True

    return False
