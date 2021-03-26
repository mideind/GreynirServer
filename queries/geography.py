"""

    Greynir: Natural language processing for Icelandic

    Geography query response module

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


    This module handles geography-related queries.

"""

# TODO: "Hvað búa margir í/á [BORG/LAND]?" etc. Wiki api?
# TODO: Beautify queries by fixing capitalization of countries, placenames
# TODO: Beautify query: "Hver er höfuðborg Norður-Kóreu"

import logging
import random
import re
from datetime import datetime, timedelta

from cityloc import capital_for_cc  # type: ignore

from query import Query
from queries import country_desc, nom2dat, cap_first
from reynir import NounPhrase
from geo import (
    icelandic_city_name,
    isocode_for_country_name,
    country_name_for_isocode,
    continent_for_country,
    ISO_TO_CONTINENT,
    location_info,
    capitalize_placename,
)

_GEO_QTYPE = "Geography"

TOPIC_LEMMAS = ["höfuðborg", "heimsálfa", "borg", "landafræði"]


def help_text(lemma: str) -> str:
    """Help text to return when query.py is unable to parse a query but
    one of the above lemmas is found in it"""
    return "Ég get svarað ef þú spyrð til dæmis: {0}?".format(
        random.choice(
            (
                "Hver er höfuðborg Frakklands",
                "Í hvaða landi er Minsk",
                "Í hvaða heimsálfu er Kambódía",
                "Hvar er Kaupmannahöfn",
                "Hvar í heiminum er Máritanía",
            )
        )
    )


# This module wants to handle parse trees for queries
HANDLE_TREE = True

# The grammar nonterminals this module wants to handle
QUERY_NONTERMINALS = {"QGeo"}

# The context-free grammar for the queries recognized by this plug-in module
GRAMMAR = """

Query →
    QGeo

QGeo → QGeoQuery '?'?

QGeoQuery →
    QGeoCapitalQuery
    | QGeoCountryQuery
    | QGeoContinentQuery
    | QGeoLocationDescQuery

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
    | "hvar" "í" "heiminum" "er" QGeoCountryOrCity? QGeoSubject_nf

QGeoLocationDescQuery →
    # Hvar er borgin Tókýó / Hvar er landið Kambódía?
    QGeoWhereIs QGeoCountryOrCity? QGeoSubject_nf

QGeoCountryOrCity →
    "landið" | "ríkið" | "borgin" | "bærinn" | "kaupstaðurinn"

$score(+100) QGeoCountryOrCity

QGeoWhatIs →
    "hver" "er" | "hvað" "er" | "hvað" "heitir" | 0

QGeoWhereIs →
    "hvar" "er"
    | "hvar" "eru"
    | "hvar" "í" "heiminum" "er"
    | "hvar" "í" "heiminum" "eru"
    | "hvar" "á" "jörðinni" "er"
    | "hvar" "á" "jörðinni" "eru"
    | "hvar" "á" "plánetunni" "er"
    | "hvar" "á" "plánetunni" "eru"
    | "hvar" "á" "hnettinum" "er"
    | "hvar" "á" "hnettinum" "eru"

QGeoPreposition →
    "í" | "á"

QGeoSubject/fall →
    Nl/fall

QGeoSubject_nf →
    # Hardcoded special case, otherwise identified as adj. "kostaríkur" :)
    "kostaríka"
    # The grammar seems to have a hard time with these
    | "norður" "kórea"
    | "nýja" "sjáland"
    | "norður" "makedónía"
    | "hvíta" "rússland" | "hvíta-rússland"
    | "sameinuðu" "arabísku" "furstadæmin"
    | "seychelles" "eyjar"

QGeoSubject_þgf →
    # Hardcoded special case, otherwise identified as adj. "kostaríkur" :)
    "kostaríku"
    | "norður" "kóreu"
    | "nýja" "sjálandi"
    | "norður" "makedóníu"
    | "hvíta" "rússlandi" | "hvíta-rússlandi"
    | "sameinuðu" "arabísku" "furstadæmunum"
    | "seychelles" "eyjum"

QGeoSubject_ef →
    # Hardcoded special case, otherwise identified as adj. "kostaríkur" :)
    "kostaríku"
    | "norður" "kóreu"
    | "nýja" "sjálands"
    | "norður" "makedóníu"
    | "hvíta" "rússlands" | "hvíta-rússlands"
    | "sameinuðu" "arabísku" "furstadæmanna"
    | "seychelles" "eyja"

$score(+10) QGeoSubject/fall
$score(-100) QGeoLocationDescQuery

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


def QGeoLocationDescQuery(node, params, result):
    result["geo_qtype"] = "loc_desc"


_PLACENAME_FIXES = [
    (r"nýja sjáland", "Nýja-Sjáland"),
    (r"norður kóre", "Norður-Kóre"),
    (r"norður kaledón", "Norður-Kaledón"),
    (r"^seychelles.+$", "Seychelles"),
    (r"^taiwans$", "Taiwan"),
]


def _preprocess(name: str) -> str:
    """Change country/city names mangled by speech recognition to
    the canonical spelling so lookup works."""
    fixed = name
    for k, v in _PLACENAME_FIXES:
        fixed = re.sub(k, v, fixed, flags=re.IGNORECASE)
    return fixed


def QGeoSubject(node, params, result):
    n = capitalize_placename(_preprocess(result._text))
    nom = NounPhrase(n).nominative or n
    result.subject = nom


def _capital_query(country: str, q: Query):
    """ Generate answer to question concerning a country capital. """

    # Get country code
    cc = isocode_for_country_name(country)
    if not cc:
        logging.warning("No CC for country {0}".format(country))
        return False

    # Find capital city, given the country code
    capital = capital_for_cc(cc)
    if not capital:
        return False

    # Use the Icelandic name for the city
    ice_cname = icelandic_city_name(capital["name_ascii"])

    # Look up genitive country name for voice description
    country_gen = NounPhrase(country).genitive or country
    answer = ice_cname
    response = dict(answer=answer)
    voice = "Höfuðborg {0} er {1}".format(country_gen, answer)

    q.set_answer(response, answer, voice)
    q.set_key("Höfuðborg {0}".format(country_gen))
    q.set_context(dict(subject=ice_cname))

    return True


def _which_country_query(subject: str, q: Query):
    """Generate answer to question concerning the country in which
    a given placename is located."""
    info = location_info(subject, "placename")
    if not info:
        return False

    cc = info.get("country")
    if not cc:
        return False

    # Get country name w. preposition ("í Þýskalandi")
    desc = country_desc(cc)

    # Format answer
    answer = cap_first(desc)
    response = dict(answer=answer)
    voice = "{0} er {1}".format(subject, desc)

    q.set_answer(response, answer, voice)
    q.set_key(subject)
    cname = country_name_for_isocode(cc)
    if cname is not None:
        q.set_context(dict(subject=cname))

    return True


def _which_continent_query(subject: str, q: Query):
    """Generate answer to question concerning the continent on which
    a given country name or placename is located."""

    # Get country code
    cc = isocode_for_country_name(subject)
    is_placename = False
    if not cc:
        # OK, the subject is not a country
        # Let's see if it's a placename
        info = location_info(subject, "placename")
        if not info:
            return False  # We don't know where it is
        cc = info.get("country")
        is_placename = True

    if not cc:
        return False

    contcode = continent_for_country(cc)
    if contcode is None:
        continent = "óþekkt heimsálfa"
        continent_dat = "óþekktri heimsálfu"
    else:
        continent = ISO_TO_CONTINENT[contcode]
        continent_dat = nom2dat(continent)

    # Format answer
    answer = continent_dat
    response = dict(answer=answer)
    if is_placename:
        cd = country_desc(cc)
        voice = "Staðurinn {0} er {1}, sem er land í {2}".format(
            subject, cd, continent_dat
        )
        answer = "{0}, {1}".format(cap_first(cd), continent_dat)
    else:
        voice = "Landið {0} er í {1}".format(subject, continent_dat)

    q.set_answer(response, answer, voice)
    q.set_key(subject)
    q.set_context(dict(subject=continent))

    return True


def _loc_desc_query(subject: str, q: Query):
    """Generate answer to a question about where a
    country or placename is located."""

    # Get country code
    cc = isocode_for_country_name(subject)
    if not cc:
        # Not a country, try placename lookup
        return _which_country_query(subject, q)

    contcode = continent_for_country(cc)
    if contcode is None:
        continent = "óþekkt heimsálfa"
        continent_dat = "óþekktri heimsálfu"
    else:
        continent = ISO_TO_CONTINENT[contcode]
        continent_dat = nom2dat(continent)

    answer = "{0} er land í {1}.".format(subject, continent_dat)
    voice = answer
    response = dict(answer=answer)

    q.set_answer(response, answer, voice)
    q.set_key(subject)
    q.set_context(dict(subject=subject))

    return True


# Map handler functions to query types
_HANDLERS = {
    "capital": _capital_query,
    "country": _which_country_query,
    "continent": _which_continent_query,
    "loc_desc": _loc_desc_query,
}


def sentence(state, result):
    """ Called when sentence processing is complete """
    q: Query = state["query"]

    handled = False

    if (
        "qtype" in result
        and "subject" in result
        and "geo_qtype" in result
        and result.geo_qtype in _HANDLERS
    ):
        # Successfully matched a query type
        try:
            fn = _HANDLERS[result.geo_qtype]
            handled = fn(result.subject, q)
        except Exception as e:
            logging.warning("Exception answering geography query: {0}".format(e))
            q.set_error("E_EXCEPTION: {0}".format(e))
            return

    if handled:
        q.set_qtype(_GEO_QTYPE)
        q.set_expires(datetime.utcnow() + timedelta(hours=24))
        # Beautify by fixing "Landi" issue
        q.set_beautified_query(q.beautified_query.replace(" Landi ", " landi "))
    else:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
