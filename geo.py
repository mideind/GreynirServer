"""
    Reynir: Natural language processing for Icelandic

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


import json
import re
import sys
import os
from iceaddr import iceaddr_lookup, placename_lookup
from cityloc import city_lookup
from country_list import countries_for_language, available_languages


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
    ("Norðurlönd", "París", "Svalbarði", "Höfðaborg", "Hamborg")
)
ICE_STREETNAME_BLACKLIST = frozenset(("Sjáland", "Feney"))

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

# ISO codes for country names that are not
# included in Icelandic country name UN data
COUNTRY_NAME_TO_ISOCODE_ADDITIONS = {
    ICELANDIC_LANG_ISOCODE: {
        "Mjanmar": "MM",
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
    }
}


def location_description(loc):
    """ Return a description string (in Icelandic) for a location.
        Argument is a dictionary with at least "name" and "kind" keys """

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


ICE_CITY_NAMES = None
ICE_CITIES_JSONPATH = os.path.join(
    os.path.dirname(__file__), "resources/cities_is.json"
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
    cn = cnames.get(name, name)
    return city_lookup(cn)


def icelandic_city_name(name):
    """ Look up the Icelandic name of a city, given its
        English/international name. """
    cnames = _load_city_names()  # Lazy-load
    for ice, n in cnames.items():
        if n == name:
            return ice
    return name


# Data about countries, loaded from JSON data file
COUNTRY_DATA = None
COUNTRY_DATA_JSONPATH = os.path.join(
    os.path.dirname(__file__), "resources/country_data.json"
)


def _load_country_data():
    """ Load country data from JSON file """
    global COUNTRY_DATA
    if COUNTRY_DATA is None:
        with open(COUNTRY_DATA_JSONPATH) as f:
            COUNTRY_DATA = json.load(f)
    return COUNTRY_DATA


def continent_for_country(iso_code):
    """ Return two-char continent code, given a two-char country code """
    assert len(iso_code) == 2

    iso_code = iso_code.upper()

    data = _load_country_data()  # Lazy-load

    if iso_code in data:
        return data[iso_code].get("cc")

    return None


def coords_for_country(iso_code):
    """ Return coordinates for a given country code """
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
    """ Get coordinates from the address dict provided by iceaddr """
    if info is not None and "lat_wgs84" in info and "long_wgs84" in info:
        return (info["lat_wgs84"], info["long_wgs84"])
    return None


def country_name_for_isocode(iso_code, lang=ICELANDIC_LANG_ISOCODE):
    """ Return country name for an ISO 3166-1 alpha-2 code """
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
        name in the specified language (two-char ISO 639-1) """
    assert len(lang) == 2

    lang = lang.lower()
    if lang not in available_languages():
        return None

    countries = countries_for_language(lang)  # This is cached by module
    for iso_code, name in countries:
        if name == country_name:
            return iso_code

    if lang in COUNTRY_NAME_TO_ISOCODE_ADDITIONS:
        return COUNTRY_NAME_TO_ISOCODE_ADDITIONS[lang].get(country_name)

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
    """ Break Icelandic address string down to its components """
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


def iceprep_for_street(sn):
    """ Return the right preposition ("í" or "á") for
        an Icelandic street name, e.g. "Fiskislóð" """

    # TODO: Implement me properly
    isuffixes = frozenset(("brekka", "ás", "holt"))
    for suffix in isuffixes:
        if sn.endswith(suffix):
            return "í"
    return "á"


def iceprep_for_placename(pn):
    """ Return the right preposition ("í" or "á")
        for an Icelandic placename, e.g. "Akureyri" """

    # TODO: Update this with the data acquired
    # from Íslenskt Málfar (1992)
    suffix2prep = {
        "vík": "í",
        "fjörður": "á",
        "eyri": "á",
        "gata": "á",
        "stígur": "á",
        "vogur": "í",
        "brekka": "í",
        "staðir": "á",
        "höfn": "á",
        "eyjar": "í",
        "ey": "í",
        "nes": "á",
        "fjörður": "á",
    }
    for suffix, prep in suffix2prep.items():
        if pn.endswith(suffix):
            return prep

    return "í"


# TODO: This should be in a separate file, and should
# probably be part of the ReynirCorrect package
ICEPREP_FOR_CC = {
    "AF": "í",  # Afganistan
    "AL": "í",  # Albanía
    "DZ": "í",  # Alsír
    "AD": "í",  # Andorra
    "AO": "í",  # Angóla
    "AI": "í",  # Angvilla
    "AG": "á",  # Antígva og Barbúda
    "AR": "í",  # Argentína
    "AM": "í",  # Armenía
    "AW": "í",  # Arúba
    "AC": "á",  # Ascension-eyja
    "AZ": "í",  # Aserbaídsjan
    "AT": "í",  # Austurríki
    "AX": "á",  # Álandseyjar
    "AU": "í",  # Ástralía
    "BS": "á",  # Bahamaeyjar
    "US": "í",  # Bandaríkin
    "AS": "í",  # Bandaríska Samóa
    "VI": "á",  # Bandarísku Jómfrúaeyjar
    "BD": "í",  # Bangladess
    "BB": "á",  # Barbados
    "BH": "í",  # Barein
    "BE": "í",  # Belgía
    "BZ": "í",  # Belís
    "BJ": "í",  # Benín
    "BM": "í",  # Bermúdaeyjar
    "BA": "í",  # Bosnía og Hersegóvína
    "BW": "í",  # Botsvana
    "BO": "í",  # Bólivía
    "BR": "í",  # Brasilía
    "IO": "í",  # Bresku Indlandshafseyjar
    "VG": "í",  # Bresku Jómfrúaeyjar
    "GB": "í",  # Bretland
    "BN": "í",  # Brúnei
    "BG": "í",  # Búlgaría
    "BF": "í",  # Búrkína Fasó
    "BI": "í",  # Búrúndí
    "BT": "í",  # Bútan
    "KY": "í",  # Caymaneyjar
    "EA": "í",  # Ceuta og Melilla
    "CK": "í",  # Cooks-eyjar
    "CW": "í",  # Curacao
    "DK": "í",  # Danmörk
    "DG": "í",  # Diego Garcia
    "DJ": "í",  # Djíbútí
    "DM": "á",  # Dóminíka
    "DO": "í",  # Dóminíska lýðveldið
    "EG": "í",  # Egyptaland
    "EE": "í",  # Eistland
    "EC": "í",  # Ekvador
    "SV": "í",  # El Salvador
    "ER": "í",  # Erítrea
    "ET": "í",  # Eþíópía
    "FK": "á",  # Falklandseyjar
    "PH": "á",  # Filippseyjar
    "FI": "í",  # Finnland
    "FJ": "á",  # Fídjíeyjar
    "CI": "í",  # Fílabeinsströndin
    "FR": "í",  # Frakkland
    "GF": "í",  # Franska Gvæjana
    "PF": "í",  # Franska Pólýnesía
    "TF": "á",  # Frönsku suðlægu landsvæðin
    "FO": "í",  # Færeyjar
    "GA": "í",  # Gabon
    "GM": "í",  # Gambía
    "GH": "í",  # Gana
    "GE": "í",  # Georgía
    "GI": "í",  # Gíbraltar
    "GN": "í",  # Gínea
    "GW": "í",  # Gínea-Bissá
    "GD": "í",  # Grenada
    "GR": "í",  # Grikkland
    "CV": "á",  # Grænhöfðaeyjar
    "GL": "á",  # Grænland
    "GG": "í",  # Guernsey
    "GP": "í",  # Gvadelúpeyjar
    "GU": "í",  # Gvam
    "GT": "í",  # Gvatemala
    "GY": "í",  # Gvæjana
    "HT": "á",  # Haítí
    "PS": "í",  # Heimastjórnarsvæði Palestínumanna
    "NL": "í",  # Holland
    "HN": "í",  # Hondúras
    "BY": "í",  # Hvíta-Rússland
    "IN": "í",  # Indland
    "ID": "í",  # Indónesía
    "IQ": "í",  # Írak
    "IR": "í",  # Íran
    "IE": "í",  # Írland
    "IS": "á",  # Ísland
    "IL": "í",  # Ísrael
    "IT": "á",  # Ítalía
    "JM": "á",  # Jamaíka
    "JP": "í",  # Japan
    "YE": "í",  # Jemen
    "JE": "í",  # Jersey
    "CX": "á",  # Jólaey
    "JO": "í",  # Jórdanía
    "KH": "í",  # Kambódía
    "CM": "í",  # Kamerún
    "CA": "í",  # Kanada
    "IC": "á",  # Kanaríeyjar
    "BQ": "í",  # Karíbahafshluti Hollands
    "KZ": "í",  # Kasakstan
    "QA": "í",  # Katar
    "KE": "í",  # Kenía
    "KG": "í",  # Kirgistan
    "CN": "í",  # Kína
    "KI": "í",  # Kíribatí
    "CG": "í",  # Kongó-Brazzaville
    "CD": "í",  # Kongó-Kinshasa
    "CR": "í",  # Kostaríka
    "CC": "í",  # Kókoseyjar (Keeling)
    "CO": "í",  # Kólumbía
    "KM": "á",  # Kómoreyjar
    "XK": "í",  # Kósóvó
    "HR": "í",  # Króatía
    "CU": "á",  # Kúba
    "KW": "í",  # Kúveit
    "CY": "á",  # Kýpur
    "LA": "í",  # Laos
    "LS": "í",  # Lesótó
    "LV": "í",  # Lettland
    "LI": "í",  # Liechtenstein
    "LT": "í",  # Litháen
    "LB": "í",  # Líbanon
    "LR": "í",  # Líbería
    "LY": "í",  # Líbía
    "LU": "í",  # Lúxemborg
    "MG": "á",  # Madagaskar
    "MK": "í",  # Makedónía
    "MY": "í",  # Malasía
    "MW": "í",  # Malaví
    "MV": "á",  # Maldíveyjar
    "ML": "í",  # Malí
    "MT": "á",  # Malta
    "MA": "í",  # Marokkó
    "MH": "á",  # Marshalleyjar
    "MQ": "á",  # Martiník
    "YT": "í",  # Mayotte
    "MR": "í",  # Máritanía
    "MU": "í",  # Máritíus
    "MX": "í",  # Mexíkó
    "CF": "í",  # Mið-Afríkulýðveldið
    "GQ": "í",  # Miðbaugs-Gínea
    "FM": "í",  # Míkrónesía
    "MM": "í",  # Mjanmar (Búrma)
    "MD": "í",  # Moldóva
    "MN": "í",  # Mongólía
    "MS": "í",  # Montserrat
    "MC": "í",  # Mónakó
    "MZ": "í",  # Mósambík
    "IM": "á",  # Mön
    "NA": "í",  # Namibía
    "NR": "á",  # Nárú
    "NP": "í",  # Nepal
    "NU": "í",  # Niue
    "NE": "í",  # Níger
    "NG": "í",  # Nígería
    "NI": "í",  # Níkaragva
    "KP": "í",  # Norður-Kórea
    "MP": "á",  # Norður-Maríanaeyjar
    "NO": "í",  # Noregur
    "NF": "á",  # Norfolkeyja
    "NC": "í",  # Nýja-Kaledónía
    "NZ": "á",  # Nýja-Sjáland
    "OM": "í",  # Óman
    "PK": "í",  # Pakistan
    "PW": "í",  # Palá
    "PA": "í",  # Panama
    "PG": "í",  # Papúa Nýja-Gínea
    "PY": "í",  # Paragvæ
    "PE": "í",  # Perú
    "PN": "á",  # Pitcairn-eyjar
    "PT": "í",  # Portúgal
    "PL": "í",  # Pólland
    "XA": "í",  # Pseudo-Accents
    "XB": "í",  # Pseudo-Bidi
    "PR": "í",  # Púertó Ríkó
    "RE": "í",  # Réunion
    "RW": "í",  # Rúanda
    "RO": "í",  # Rúmenía
    "RU": "í",  # Rússland
    "SB": "í",  # Salómonseyjar
    "ZM": "í",  # Sambía
    "AE": "í",  # Sameinuðu arabísku furstadæmin
    "WS": "í",  # Samóa
    "SM": "í",  # San Marínó
    "BL": "í",  # Sankti Bartólómeusareyjar
    "SH": "í",  # Sankti Helena
    "KN": "í",  # Sankti Kitts og Nevis
    "LC": "í",  # Sankti Lúsía
    "SX": "í",  # Sankti Martin
    "PM": "í",  # Sankti Pierre og Miquelon
    "VC": "í",  # Sankti Vinsent og Grenadíneyjar
    "ST": "í",  # Saó Tóme og Prinsípe
    "SA": "í",  # Sádi-Arabía
    "SN": "í",  # Senegal
    "RS": "í",  # Serbía
    "SC": "í",  # Seychelles-eyjar
    "HK": "í",  # sérstjórnarsvæðið Hong Kong
    "MO": "í",  # sérstjórnarsvæðið Makaó
    "ZW": "í",  # Simbabve
    "SG": "í",  # Singapúr
    "SL": "í",  # Síerra Leóne
    "CL": "í",  # Síle
    "SK": "í",  # Slóvakía
    "SI": "í",  # Slóvenía
    "UM": "í",  # Smáeyjar Bandaríkjanna
    "SO": "í",  # Sómalía
    "ES": "á",  # Spánn
    "LK": "á",  # Srí Lanka
    "MF": "á",  # St. Martin
    "ZA": "í",  # Suður-Afríka
    "GS": "á",  # Suður-Georgía og Suður-Sandvíkureyjar
    "KR": "í",  # Suður-Kórea
    "SS": "í",  # Suður-Súdan
    "AQ": "á",  # Suðurskautslandið
    "SD": "í",  # Súdan
    "SR": "í",  # Súrínam
    "SJ": "á",  # Svalbarði og Jan Mayen
    "ME": "í",  # Svartfjallaland
    "SZ": "í",  # Svasíland
    "CH": "í",  # Sviss
    "SE": "í",  # Svíþjóð
    "SY": "í",  # Sýrland
    "TJ": "í",  # Tadsjikistan
    "TH": "í",  # Taíland
    "TW": "í",  # Taívan
    "TZ": "í",  # Tansanía
    "CZ": "í",  # Tékkland
    "TL": "í",  # Tímor-Leste
    "TO": "í",  # Tonga
    "TG": "í",  # Tógó
    "TK": "í",  # Tókelá
    "TA": "í",  # Tristan da Cunha
    "TT": "í",  # Trínidad og Tóbagó
    "TD": "í",  # Tsjad
    "TC": "í",  # Turks- og Caicoseyjar
    "TN": "í",  # Túnis
    "TM": "í",  # Túrkmenistan
    "TV": "í",  # Túvalú
    "TR": "í",  # Tyrkland
    "HU": "í",  # Ungverjaland
    "UG": "í",  # Úganda
    "UA": "í",  # Úkraína
    "UY": "í",  # Úrúgvæ
    "UZ": "í",  # Úsbekistan
    "VU": "á",  # Vanúatú
    "VA": "í",  # Vatíkanið
    "VE": "í",  # Venesúela
    "EH": "í",  # Vestur-Sahara
    "VN": "í",  # Víetnam
    "WF": "í",  # Wallis- og Fútúnaeyjar
    "DE": "í",  # Þýskaland
}


def iceprep4cc(cc):
    """ Return the right Icelandic preposition ("í" or "á") for
        a country, given its ISO country code, e.g. "IS" """
    return ICEPREP_FOR_CC.get(cc)


def iceprep_for_country(cn):
    """ Return the right Icelandic preposition ("í" or "á") for
        a country, given its Icelandic name in the nominative
        case, e.g. "Ítalía" """
    # TODO: Implement me
    return iceprep4cc(isocode_for_country_name(cn))


if __name__ == "__main__":
    """ Test location info lookup via command line """
    name = sys.argv[1] if len(sys.argv) > 1 else None
    kind = sys.argv[2] if len(sys.argv) > 2 else None

    if name:
        print(location_info(name, kind))
