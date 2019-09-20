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


# TODO: "Í hvaða landi er [BORG]?", "Hvað búa margir í/á [BORG/LAND]?" etc.


from datetime import datetime, timedelta
from cityloc import capital_for_cc
from geo import icelandic_city_name, isocode_for_country_name
from reynir.bindb import BIN_Db


_GEO_QTYPE = "Geography"


_CAPITAL_QUERIES = [
    "hver er höfuðborgin í ",
    "hvað er höfuðborgin í ",
    "hver er höfuðborgin á ",
    "hvað er höfuðborgin á ",
    "hvað er höfuðborg ",
    "hver er höfuðborg ",
    "hver er höfuðstaður ",
    "hvað er höfuðstaður ",
]


def handle_plain_text(q):
    """ Handle a plain text query, contained in the q parameter """
    ql = q.query_lower.rstrip("?").strip()
    pfx = None

    for p in _CAPITAL_QUERIES:
        if ql.startswith(p):
            pfx = p
            break
    else:
        return False

    country = ql[len(pfx) :].strip()
    if not len(country):
        return False

    country = country[0].upper() + country[1:]  # Capitalize first char
    # TODO: This only works for single-word country names, fix that
    # Transform country name from genitive to nominative
    bres = BIN_Db().lookup_nominative(country, cat="no")
    if not bres:
        return False
    words = [m.ordmynd for m in bres]

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

    # Look up genitive country name for voice description,
    bres = BIN_Db().lookup_genitive(nom_country, cat="no")
    country_gen = bres[0].ordmynd if bres else country

    answer = ice_cname
    response = dict(answer=answer)
    voice = "Höfuðborg {0} er {1}".format(country_gen, answer)

    q.set_answer(response, answer, voice)
    q.set_qtype(_GEO_QTYPE)
    q.set_expires(datetime.utcnow() + timedelta(hours=12))

    return True
