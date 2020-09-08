"""
    Greynir: Natural language processing for Icelandic

    Copyright (c) 2018 Miðeind ehf.

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


    This module contains geography and location-related utility functions.

"""

# TODO: Handle generic direction prefixes for country names and map to
# corresponding country code, e.g. "Norður-Ítalía" -> "IT"

from typing import Optional, Dict, Union, Tuple

import json
import re
import sys
import os
import math
from iceaddr import iceaddr_lookup, placename_lookup
from cityloc import city_lookup
from country_list import countries_for_language, available_languages
from functools import lru_cache


ICELAND_ISOCODE = "IS"  # ISO 3166-1 alpha-2
ICELANDIC_LANG_ISOCODE = "is"  # ISO 639-1

# Map Icelandic continent names to ISO continent code
CONTINENTS = {
    "Afríka": "AF",
    "Norður-Afríka": "AF",
    "Austur-Afríka": "AF",
    "Vestur-Afríka": "AF",
    "Mið-Afríka": "AF",
    "Suðurálfa": "AF",
    "Norður-Ameríka": "NA",
    "Mið-Ameríka": "NA",
    "Suður-Ameríka": "SA",
    "Eyjaálfa": "OC",
    "Suðurskautslandið": "AN",
    "Suðurskautsland": "AN",
    "Antarktíka": "AN",  # Til í BÍN!
    "Asía": "AS",
    "Norður-Asía": "AS",
    "Suður-Asía": "AS",
    "Mið-Asía": "AS",
    "Austur-Asía": "AS",
    "Suðaustur-Asía": "AS",
    "Suðvestur-Asía": "AS",
    "Vestur-Asía": "AS",
    "Evrópa": "EU",
    "Norðurálfa": "EU",
    "Suður-Evrópa": "EU",
    "Vestur-Evrópa": "EU",
    "Norður-Evrópa": "EU",
    "Austur-Evrópa": "EU",
    "Mið-Evrópa": "EU",
}

# Map ISO continent codes to canonical Icelandic name
ISO_TO_CONTINENT = {
    "AF": "Afríka",
    "NA": "Norður-Ameríka",
    "OC": "Eyjaálfa",
    "AN": "Suðurskautslandið",
    "AS": "Asía",
    "EU": "Evrópa",
    "SA": "Suður-Ameríka",
}

# Types of locations
LOCATION_TAXONOMY = frozenset(
    ("continent", "country", "placename", "street", "address")
)

# Location names that exist in Iceland but should
# not be looked up as Icelandic place/street names
ICE_PLACENAME_BLACKLIST = frozenset(
    (
        "Norðurlönd",
        "París",
        "Svalbarði",
        "Höfðaborg",
        "Hamborg",
        "Pétursborg",
        "Stöð",
        "Álaborg",
        "Árósar",
    )
)

# These should *never* be interpreted as Icelandic street names
ICE_STREETNAME_BLACKLIST = frozenset(("Sjáland", "Feney", "Ráðhúsið", "Húsið"))

# These should *always* be interpreted as Icelandic street names
ALWAYS_STREET_ADDR = frozenset(("Skeifan", "Bessastaðir", "Kringlan"))

# Names that should always be identified
# as Icelandic regions, not placenames
ICE_REGIONS = frozenset(
    (
        "Vesturland",
        "Norðurland",
        "Norðausturland",
        "Norðvesturland",
        "Suðvesturland",
        "Suðausturland",
        "Suðurland",
        "Austurland",
        "Mið-Austurland",
        "Vestfirðir",
        "Austfirðir",
        "Suðurnes",
    )
)

# ISO codes for country names that are not part of the Icelandic-language
# country name UN data included in the country_list package
COUNTRY_NAME_TO_ISOCODE_ADDITIONS = {
    ICELANDIC_LANG_ISOCODE: {
        "Mjanmar": "MM",
        "Myanmar": "MM",
        "Bahrain": "BH",
        "Bandaríki Norður-Ameríku": "US",
        "Búrma": "MM",
        "Burma": "MM",
        "Ameríka": "US",
        "Hong Kong": "HK",
        "Makaó": "MO",
        "Stóra-Bretland": "GB",
        "England": "GB",
        "Skotland": "GB",
        "Wales": "GB",
        "Norður-Írland": "GB",
        "Norður-Makedónía": "MK",
        "Bosnía": "BA",
        "Hersegóvína": "BA",
        "Palestína": "PS",
        "Páfagarður": "VA",
        "Páfastóll": "VA",
        "Páfaríki": "VA",
        "Vatíkan": "VA",
        "Vatíkanríki": "VA",  # Formal name
        "Vatikan": "VA",
        "Vatikanríki": "VA",  # Formal name
        "Papúa": "PG",
        "Nevis": "KN",
        "Chile": "CL",
        "Kenýa": "KE",
        "Kongó": "CD",
        "Austur-Kongó": "CD",
        "Vestur-Kongó": "CG",
        "Caicoseyjar": "TC",
        "Fídjieyjar": "FJ",
        "Grenadíneyjar": "VC",
        "Guatemala": "GT",
        "Kirgisistan": "KG",
        "Antígva": "AG",
        "Antigva": "AG",
        "Antigúa": "AG",
        "Sri Lanka": "LK",
        "Kórea": "KR",  # South Korea :)
        "Moldavía": "MD",
        "Trínidad": "TT",
        "Tóbagó": "TT",
        "Seychelleseyjar": "SC",
        "Seychelles": "SC",
        "Salvador": "SV",
        "Mikrónesía": "FM",
        "Lýbía": "LY",
        "Líbýa": "LY",
        "Kókoseyjar": "CC",
        "Kípur": "CY",
        "Barbadoseyjar": "BB",
        "Austur-Tímor": "TL",
        "Kíríbatí": "KI",
        "Nikaragva": "NI",
        "Nikaragúa": "NI",
        "Cookseyjar": "CK",
        "Egiptaland": "EG",
        "Egiftaland": "EG",
        "Malawi": "MW",
        "Norður-Noregur": "NO",
        "Tæland": "TH",
        "Aserbaísjan": "AZ",  # Til svona stafsett í BÍN
        "Aserbædjan": "AZ",
        "Azerbaijan": "AZ",
        "Kanarí": "IC",
        "Kanaríeyjar": "IC",
        "Jómfrúaeyjar": "US",
        "Ghana": "GH",
        "Kosovo": "XK",
        "Sameinuðu Arabísku Furstadæmin": "AE",
        "Norður-Súdan": "SD",
    }
}


def location_description(loc):
    """ Return a natural language description string (in Icelandic) for a given
        location. Argument is a dictionary with at least "name" and "kind" keys. """

    if "kind" not in loc or "name" not in loc:
        return "staðarheiti"

    name = loc["name"]
    kind = loc["kind"]

    if kind == "continent":
        return "heimsálfa"

    if name in ICE_REGIONS:
        return "landshluti"

    if kind == "country":
        desc = "landsvæði"
        c = loc.get("continent")
        if c is None and "country" in loc:
            c = continent_for_country(loc["country"])
        if c in ISO_TO_CONTINENT:
            cname = ISO_TO_CONTINENT[c]
            desc = "land í {0}u".format(cname[:-1])
        return desc

    if kind == "address":
        return "heimilisfang"

    if kind == "street":
        if "country" in loc and loc["country"] == ICELAND_ISOCODE:
            return "gata á Íslandi"
        return "gata"

    if kind == "placename":
        return "örnefni"

    return "staðarheiti"


def location_info(name, kind, placename_hints=None):
    """ Returns dict with info about a location, given name and kind.
        Info includes ISO country and continent code, GPS coordinates, etc. """

    # Continents are marked as "lönd" in BÍN, so we set kind manually
    if name in CONTINENTS:
        kind = "continent"
    elif name in ALWAYS_STREET_ADDR:
        kind = "street"

    loc = dict(name=name, kind=kind)
    coords = None

    # Heimilisfang
    if kind == "address":
        # We currently assume all addresses are Icelandic ones
        loc["country"] = ICELAND_ISOCODE
        info = icelandic_addr_info(name, placename_hints=placename_hints)
        if info:
            coords = coords_from_addr_info(info)
        loc["data"] = info

    # Land
    elif kind == "country":
        code = isocode_for_country_name(name)
        if code:
            loc["country"] = code
            coords = coords_for_country(code)

    # Heimsálfa
    elif kind == "continent":
        # Get continent ISO code
        loc["continent"] = CONTINENTS.get(name)

    # Götuheiti
    elif kind == "street":
        # All street names in BÍN are Icelandic
        if name not in ICE_STREETNAME_BLACKLIST:
            loc["country"] = ICELAND_ISOCODE
            coords = coords_for_street_name(name, placename_hints=placename_hints)

    # Örnefni
    elif kind == "placename":
        info = None

        # Check if it's an Icelandic placename
        if name in ICE_REGIONS:
            loc["country"] = ICELAND_ISOCODE
        elif name not in ICE_PLACENAME_BLACKLIST:
            # Try to find a matching Icelandic placename
            info = placename_lookup(name)
            if info:
                loc["country"] = ICELAND_ISOCODE
                # Pick first matching placename
                coords = coords_from_addr_info(info[0])

        # OK, not Icelandic. Let's see if it's a foreign city
        if not info:
            cities = lookup_city_info(name)
            if cities:
                # Pick first match. Cityloc package should give us a match list
                # ordered by population, with capital cities given precedence
                c = cities[0]
                loc["country"] = c.get("country")
                coords = coords_from_addr_info(c)

    # Look up continent code for country
    if "country" in loc:
        loc["continent"] = continent_for_country(loc["country"])

    if coords:
        (loc["latitude"], loc["longitude"]) = coords

    return loc


ICE_CITY_NAMES = None  # type: Optional[Dict[str, str]]
ICE_CITIES_JSONPATH = os.path.join(
    os.path.dirname(__file__), "resources", "cities_is.json"
)


def _load_city_names():
    """ Load data from JSON file mapping Icelandic city names
        to their corresponding English/international name. """
    global ICE_CITY_NAMES
    if ICE_CITY_NAMES is None:
        with open(ICE_CITIES_JSONPATH) as f:
            ICE_CITY_NAMES = json.load(f)
    return ICE_CITY_NAMES


def lookup_city_info(name):
    """ Look up name in city database. Convert Icelandic-specific
        city names (e.g. "Lundúnir") to their corresponding
        English/international name before querying. """
    cnames = _load_city_names()  # Lazy-load
    cn = cnames.get(name.strip(), name)
    return city_lookup(cn)


@lru_cache(maxsize=32)
def icelandic_city_name(name):
    """ Look up the Icelandic name of a city, given its
        English/international name. """
    name = name.strip()
    cnames = _load_city_names()  # Lazy-load
    for ice, n in cnames.items():
        if n == name:
            return ice
    return name


# Data about countries, loaded from JSON data file
COUNTRY_DATA = (
    None
)  # type: Optional[Dict[str, Dict[str, Union[Tuple[float, float], str]]]]
COUNTRY_DATA_JSONPATH = os.path.join(
    os.path.dirname(__file__), "resources", "country_data.json"
)


def _load_country_data():
    """ Load country coordinates and ISO country code data from JSON file. """
    global COUNTRY_DATA
    if COUNTRY_DATA is None:
        with open(COUNTRY_DATA_JSONPATH) as f:
            COUNTRY_DATA = json.load(f)
    return COUNTRY_DATA


def continent_for_country(iso_code):
    """ Return two-char continent code, given a two-char country code. """
    assert len(iso_code) == 2
    iso_code = iso_code.upper()
    data = _load_country_data()  # Lazy-load
    if iso_code in data:
        return data[iso_code].get("cc")
    return None


def coords_for_country(iso_code):
    """ Return coordinates for a given country code. """
    assert len(iso_code) == 2
    iso_code = iso_code.upper()
    # Lazy-loaded
    data = _load_country_data()
    if iso_code in data:
        return data[iso_code].get("coords")
    return None


def coords_for_street_name(street_name, placename=None, placename_hints=[]):
    """ Return coordinates for an Icelandic street name as a tuple. As some
        street names exist in more than one place, we try to narrow it down
        to a single street if possible. Street coordinates are the coordinates
        of the lowest house number. """

    addresses = iceaddr_lookup(street_name, placename=placename, limit=100)

    if not addresses:
        return None

    # Find all places containing street_name
    places = set(a.get("stadur_nf") for a in addresses)
    addr = None

    # Only exists in one place
    if len(places) == 1:
        addr = addresses[0]
    elif placename_hints:
        # See if placename hints can narrow it down
        for pn in placename_hints:
            addresses = iceaddr_lookup(street_name, placename=pn)
            places = set(a.get("stadur_nf") for a in addresses)
            if len(places) == 1:
                addr = addresses[0]
                break

    return coords_from_addr_info(addr)


def coords_from_addr_info(info):
    """ Get coordinates from the address dict provided by iceaddr package. """
    if info is not None and "lat_wgs84" in info and "long_wgs84" in info:
        return (info["lat_wgs84"], info["long_wgs84"])
    return None


def country_name_for_isocode(iso_code, lang=ICELANDIC_LANG_ISOCODE):
    """ Return country name for an ISO 3166-1 alpha-2 code. """
    assert len(iso_code) == 2
    assert len(lang) == 2
    iso_code = iso_code.upper()
    lang = lang.lower()
    if lang not in available_languages():
        return None
    countries = dict(countries_for_language(lang))
    return countries.get(iso_code)


def isocode_for_country_name(country_name, lang=ICELANDIC_LANG_ISOCODE):
    """ Return the ISO 3166-1 alpha-2 code for a country
        name in the specified language (two-char ISO 639-1). """
    assert len(lang) == 2
    lang = lang.lower()
    if lang not in available_languages():
        return None
    # Hardcoded mappings take precedence
    if lang in COUNTRY_NAME_TO_ISOCODE_ADDITIONS:
        if country_name in COUNTRY_NAME_TO_ISOCODE_ADDITIONS[lang]:
            return COUNTRY_NAME_TO_ISOCODE_ADDITIONS[lang][country_name]
    countries = countries_for_language(lang)  # This is cached by module
    uc_cn = capitalize_placename(country_name)
    for iso_code, name in countries:
        if name == country_name or name == uc_cn:
            return iso_code
    return None


def icelandic_addr_info(addr_str, placename=None, placename_hints=[]):
    """ Look up info about a specific Icelandic address in Staðfangaskrá via
        the iceaddr package. We want either a single definite match or nothing. """
    addr = parse_address_string(addr_str)

    def lookup(pn):
        a = iceaddr_lookup(
            addr["street"],
            number=addr.get("number"),
            letter=addr.get("letter"),
            placename=pn,
            limit=2,
        )
        return a[0] if len(a) == 1 else None

    # Look up with the (optional) placename provided
    res = lookup(placename)

    # If no single address found, try to disambiguate using placename hints
    if not res and placename_hints:
        for p in placename_hints:
            res = lookup(p)
            if res:
                break

    return res


def parse_address_string(addrstr):
    """ Break Icelandic address string down to its components. """
    addr = {"street": addrstr}

    comp = addrstr.split()
    if len(comp) == 1:
        return addr

    # Check if last address component is a house number
    # (possibly with a trailing alphabetic character)
    last = comp[-1]
    r = re.search(r"^(\d+)([a-zA-Z]?)$", last)
    if r:
        addr["number"] = int(r.group(1))
        addr["letter"] = r.group(2) or None
        # Non-numeric earlier components must be the street name
        addr["street"] = " ".join(comp[:-1])

    return addr


_I_SUFFIXES = (
    "brekka",
    "ás",
    "holt",
    "tún",
    "tangi",
    "nes",
    "stræti",
    "hlíð",
    "sund",
    "garður",
    "garðar",
    "múli",
    "fen",
    "vík",
    "vogur",
    "Lækjargata",
    "Skeifan",
    "Kringlan",
)


def iceprep_for_street(street_name):
    """ Return the right preposition ("í" or "á") for
        an Icelandic street name, e.g. "Fiskislóð". """
    if street_name.endswith(_I_SUFFIXES):
        return "í"
    return "á"


ICELOC_PREP = None  # type: Optional[Dict[str, str]]
ICELOC_PREP_JSONPATH = os.path.join(
    os.path.dirname(__file__), "resources", "iceloc_prep.json"
)


def _load_placename_prepositions():
    """ Load data mapping Icelandic placenames to the correct
        prepositions ("á" or "í") from JSON file. """
    global ICELOC_PREP
    if ICELOC_PREP is None:
        with open(ICELOC_PREP_JSONPATH) as f:
            ICELOC_PREP = json.load(f)
    return ICELOC_PREP


# This is not strictly accurate as the correct prepositions
# are based on convention, not rational rules. :/
_SUFFIX2PREP = {
    "vík": "í",
    "fjörður": "á",
    "eyri": "á",
    "vogur": "í",
    "brekka": "í",
    "staðir": "á",
    "höfn": "á",
    "eyjar": "í",
    "ey": "í",
    "nes": "á",
}


def iceprep_for_placename(pn):
    """ Attempt to return the right preposition ("í" or "á")
        for an Icelandic placename, e.g. "Akureyri". """
    place2prep = _load_placename_prepositions()  # Lazy-load
    if pn in place2prep:
        return place2prep[pn]

    for suffix, prep in _SUFFIX2PREP.items():
        if pn.lower().endswith(suffix):
            return prep

    return "í"


# ISO country codes of all countries whose names take
# the preposition "á" in Icelandic (mostly islands, with
# notable exceptions such as "Spánn" and "Ítalía")
# TODO: This should be in a separate file, and should
# probably be part of the GreynirCorrect package going forward
CC_ICEPREP_A = frozenset(
    (
        "AG",  # Antígva og Barbúda
        "AC",  # Ascension-eyja
        "AX",  # Álandseyjar
        "BS",  # Bahamaeyjar
        "VI",  # Bandarísku Jómfrúaeyjar
        "BB",  # Barbados
        "BM",  # Bermúdaeyjar
        "IO",  # Bresku Indlandshafseyjar
        "VG",  # Bresku Jómfrúaeyjar
        "KY",  # Caymaneyjar
        "CK",  # Cooks-eyjar
        "DM",  # Dóminíka
        "FK",  # Falklandseyjar
        "PH",  # Filippseyjar
        "FJ",  # Fídjíeyjar
        "TF",  # Frönsku suðlægu landsvæðin
        "GD",  # Grenada
        "CV",  # Grænhöfðaeyjar
        "GL",  # Grænland
        "GG",  # Guernsey
        "GP",  # Gvadelúpeyjar
        "HT",  # Haítí
        "IE",  # Írland
        "IS",  # Ísland
        "IT",  # Ítalía
        "JM",  # Jamaíka
        "JE",  # Jersey
        "CX",  # Jólaey
        "IC",  # Kanaríeyjar
        "CC",  # Kókoseyjar
        "KM",  # Kómoreyjar
        "CU",  # Kúba
        "CY",  # Kýpur
        "MG",  # Madagaskar
        "MV",  # Maldíveyjar
        "MT",  # Malta
        "MH",  # Marshalleyjar
        "MQ",  # Martiník
        "IM",  # Mön
        "NR",  # Nárú
        "MP",  # Norður-Maríanaeyjar
        "NF",  # Norfolkeyja
        "NZ",  # Nýja-Sjáland
        "PN",  # Pitcairn-eyjar
        "SB",  # Salómonseyjar
        "BL",  # Sankti Bartólómeusareyjar
        "SH",  # Sankti Helena
        "LC",  # Sankti Lúsía
        "SX",  # Sankti Martin
        "PM",  # Sankti Pierre og Miquelon
        "VC",  # Sankti Vinsent og Grenadíneyjar
        "SC",  # Seychelles-eyjar
        "ES",  # Spánn
        "LK",  # Srí Lanka
        "MF",  # St. Martin
        "GS",  # Suður-Georgía og Suður-Sandvíkureyjar
        "AQ",  # Suðurskautslandið
        "SJ",  # Svalbarði og Jan Mayen
        "TA",  # Tristan da Cunha
        "TC",  # Turks- og Caicoseyjar
        "VU",  # Vanúatú
        "WF",  # Wallis- og Fútúnaeyjar
    )
)


def iceprep_for_cc(cc):
    """ Return the right Icelandic preposition ("í" or "á") for
        a country, given its ISO country code, e.g. "IS". """
    return "á" if cc.upper() in CC_ICEPREP_A else "í"


def iceprep_for_country(cn):
    """ Return the right Icelandic preposition ("í" or "á") for
        a country, given its Icelandic name in the nominative
        case, e.g. "Ítalía". """
    cc = isocode_for_country_name(cn)
    return iceprep_for_cc(cc) if cc else None


# Placename components that should not be capitalized
_PLACENAME_PREPS = frozenset(("í", "á", "de", "la", "am", "og"))


def capitalize_placename(pn):
    """ Correctly capitalize an Icelandic-language lowercase placename, e.g.
        "vík í mýrdal"->"Vík í Mýrdal", "bosnía og hersegóvína"->"Bosnía og Hersegóvína",
        "norður-makedónía"->"Norður-Makedónía", "rio de janeiro"->"Rio de Janeiro", etc. """
    if not pn:
        return pn
    comp = pn.split()
    # Uppercase each individual word (w. some exceptions)
    ucpn = " ".join(
        c[0].upper() + c[1:] if c not in _PLACENAME_PREPS else c for c in comp
    )
    # Uppercase each component in words containing a hyphen
    # e.g. "norður-makedónía" -> "Norður-Makedónía"
    ucpn = "-".join([c[0].upper() + c[1:] for c in ucpn.split("-")])
    return ucpn


_EARTH_RADIUS = 6371.0088  # Earth's radius in km


def distance(loc1, loc2):
    """
    Calculate the Haversine distance.
    Parameters
    ----------
    origin : tuple of float
        (lat, long)
    destination : tuple of float
        (lat, long)
    Returns
    -------
    distance_in_km : float
    Examples
    --------
    >>> origin = (48.1372, 11.5756)  # Munich
    >>> destination = (52.5186, 13.4083)  # Berlin
    >>> round(distance(origin, destination), 1)
    504.2
    Source:
    https://stackoverflow.com/questions/19412462
        /getting-distance-between-two-points-based-on-latitude-longitude
    """
    lat1, lon1 = loc1
    lat2, lon2 = loc2

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    slat = math.sin(dlat / 2)
    slon = math.sin(dlon / 2)
    a = (
        slat * slat
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * slon * slon
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return _EARTH_RADIUS * c


ICELAND_COORDS = (64.9957538607, -18.5739616708)


def in_iceland(loc, km_radius=300.0):
    """ Check if coordinates are within or very close to Iceland. """
    return distance(loc, ICELAND_COORDS) <= km_radius


if __name__ == "__main__":
    """ Test location info lookup via command line. """
    name = sys.argv[1] if len(sys.argv) > 1 else None
    kind = sys.argv[2] if len(sys.argv) > 2 else None

    if name:
        print(location_info(name, kind))
