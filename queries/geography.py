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

# TODO: "Hvað búa margir í/á [BORG/LAND]?" etc.

from datetime import datetime, timedelta
from cityloc import capital_for_cc
from queries import country_desc, nom2dat
from reynir.bindb import BIN_Db
from geo import (
    icelandic_city_name,
    isocode_for_country_name,
    continent_for_country,
    ISO_TO_CONTINENT,
    location_info,
)

_GEO_QTYPE = "Geography"


# This module wants to handle parse trees for queries
HANDLE_TREE = True

# The context-free grammar for the queries recognized by this plug-in module
GRAMMAR = """

Query →
    QGeo

QGeo → QGeoQuery '?'?

QGeoQuery →
    QGeoCapitalQuery
    | QGeoCountryQuery
    | QGeoContinentQuery

QGeoCapitalQuery →
    # "hvað/hver er höfuðborgin í/á Spáni?"
    QGeoWhatIs "höfuðborgin" QGeoPreposition QGeoSubject_þgf
    # "hvað/hver er höfuðborg Spánar?"
    | QGeoWhatIs "höfuðborg" QGeoSubject_ef
    # "hvað/hver er höfuðstaður Spánar?"
    | QGeoWhatIs "höfuðstaður" QGeoSubject_ef

QGeoCountryQuery →
    "í" "hvaða" "landi" "er" "borgin"? QGeoSubject_nf
    | "í" "hvaða" "ríki" "er" "borgin"? QGeoSubject_nf

QGeoContinentQuery →
    "í" "hvaða" "heimsálfu" "er" QGeoCountryOrCity? QGeoSubject_nf

QGeoCountryOrCity →
    "landið" | "ríkið" | "borgin"

QGeoWhatIs →
    "hver" "er" | "hvað" "er" | "hvað" "heitir" | 0

QGeoPreposition →
    "í" | "á"

QGeoSubject/fall →
    Nl/fall

$score(+1) QGeoSubject/fall

$score(+35) QGeo

"""


def QGeoQuery(node, params, result):
    # Set the query type
    result.qtype = _GEO_QTYPE


def QGeoCapitalQuery(node, params, result):
    result["geo_qtype"] = "capital"


def QGeoCountryQuery(node, params, result):
    result["geo_qtype"] = "country"


def QGeoContinentQuery(node, params, result):
    result["geo_qtype"] = "continent"


def QGeoSubject(node, params, result):
    n = result._nominative
    if n:
        n = n.replace(" - ", "-")
        n = n[0].upper() + n[1:]
        result.subject = n
        print(n)


def _capital_query(country, q):
    # Get country code
    cc = isocode_for_country_name(country)
    if not cc:
        return False

    # Find capital city, given the country code
    capital = capital_for_cc(cc)
    if not capital:
        return False

    # Use the Icelandic name for the city
    ice_cname = icelandic_city_name(capital["name_ascii"])

    # Look up genitive country name for voice description
    bres = BIN_Db().lookup_genitive(country, cat="no")
    country_gen = bres[0].ordmynd if bres else country

    answer = ice_cname
    response = dict(answer=answer)
    voice = "Höfuðborg {0} er {1}".format(country_gen, answer)

    q.set_answer(response, answer, voice)
    q.set_key("Höfuðborg {0}".format(country_gen))

    return True


def _which_country_query(subject, q):
    info = location_info(subject, "placename")
    if not info:
        return False

    cc = info.get("country")
    if not cc:
        return False

    # Get country name w. preposition ("í Þýskalandi")
    desc = country_desc(cc)

    # Format answer
    answer = desc[0].upper() + desc[1:]
    response = dict(answer=answer)
    voice = "{0} er {1}".format(subject, desc)

    q.set_answer(response, answer, voice)
    q.set_key(subject)

    return True


def _which_continent_query(subject, q):
    # Get country code
    cc = isocode_for_country_name(subject)
    is_city = False
    if not cc:
        # OK, the subject is not a country
        # Let's see if it's a city
        info = location_info(subject, "placename")
        if not info:
            return False
        cc = info.get("country")
        is_city = True

    contcode = continent_for_country(cc)
    continent = ISO_TO_CONTINENT[contcode]

    # Look up dative continent name
    continent_dat = nom2dat(continent)

    # Format answer
    answer = continent_dat
    response = dict(answer=answer)
    if is_city:
        voice = "Borgin {0} er {1}, sem er land í {2}".format(subject, country_desc(cc), continent_dat)
    else:
        voice = "Landið {0} er í {1}".format(subject, continent_dat)

    q.set_answer(response, answer, voice)
    q.set_key(subject)

    return True


_HANDLERS = {
    "capital": _capital_query,
    "country": _which_country_query,
    "continent": _which_continent_query,
}


def sentence(state, result):
    """ Called when sentence processing is complete """
    q = state["query"]

    handled = False

    if (
        "qtype" in result
        and "subject" in result
        and "geo_qtype" in result
        and result.geo_qtype in _HANDLERS
    ):
        # Successfully matched a query type
        fn = _HANDLERS[result.geo_qtype]
        handled = fn(result.subject, q)

    if handled:
        q.set_qtype(_GEO_QTYPE)
        q.set_expires(datetime.utcnow() + timedelta(hours=24))
    else:
        state["query"].set_error("E_QUERY_NOT_UNDERSTOOD")
