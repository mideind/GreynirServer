"""
    Reynir: Natural language processing for Icelandic

    Processor module to extract entity names & definitions

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
from pkg_resources import resource_stream
from iceaddr import iceaddr_lookup, placename_lookup
from country_list import countries_for_language, available_languages
from pycountry_convert import country_alpha2_to_continent_code

ICELAND_ISOCODE = "IS"  # ISO 3166-1 alpha-2
ICELANDIC_LANG_ISOCODE = "is"  # ISO 639-1

CONTINENTS = {
    "Afríka": "AF",
    "Norður-Afríka": "AF",
    "Austur-Afríka": "AF",
    "Vestur-Afríka": "AF",
    "Mið-Afríka": "AF",
    "Norður-Ameríka": "NA",
    "Eyjaálfa": "OC",
    "Suðurskautslandið": "AN",
    "Asía": "AS",
    "Norður-Asía": "AS",
    "Suður-Asía": "AS",
    "Mið-Asía": "AS",
    "Austur-Asía": "AS",
    "Suðaustur-Asía": "AS",
    "Suðvestur-Asía": "AS",
    "Vestur-Asía": "AS",
    "Evrópa": "EU",
    "Suður-Evrópa": "EU",
    "Vestur-Evrópa": "EU",
    "Norður-Evrópa": "EU",
    "Austur-Evrópa": "EU",
    "Mið-Evrópa": "EU",
    "Suður-Ameríka": "SA",
}

ISO_TO_CONTINENT = {
    "AF": "Afríka",
    "NA": "Norður-Ameríka",
    "OC": "Eyjaálfa",
    "AN": "Suðurskautslandið",
    "AS": "Asía",
    "EU": "Evrópa",
    "SA": "Suður-Ameríka",
}

COUNTRY_COORDS_JSONPATH = "resources/country_coords.json"

# Types of locations
LOCATION_TAXONOMY = frozenset(
    ("continent", "country", "placename", "street", "address")
)

# Location names that exist in Iceland but
# should not be looked up in placenames
ICE_PLACENAME_BLACKLIST = frozenset(("Norðurlönd", "París", "Svalbarði"))

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
        "Vestfirðir",
        "Suðurnes",
    )
)

# ISO codes for country names that are not
# included in Icelandic country name UN data
COUNTRY_NAME_TO_ISOCODE_ADDITIONS = {
    ICELANDIC_LANG_ISOCODE: {
        "Mjanmar": "MM",
        "Búrma": "MM",
        "Ameríka": "US",
        "Hong Kong": "HK",
        "Makaó": "MO",
        "Stóra-Bretland": "GB",
        "England": "GB",
        "Skotland": "GB",
        "Wales": "GB",
        "Norður-Írland": "GB",
        "Bosnía": "BA",
        "Hersegóvína": "BA",
        "Palestína": "PS",
        "Páfagarður": "VA",
        "Chile": "CL",
        "Kenýa": "KE",
        "Kirgisistan": "KG",
    }
}


def location_description(loc):
    """ Return a description string for a location (in Icelandic) """
    if "kind" not in loc:
        return "staður"

    if loc["kind"] == "continent":
        return "heimsálfa"

    if loc["name"] in ICE_REGIONS:
        return "landshluti"

    if loc["kind"] == "country":
        desc = "land"
        c = loc.get("continent")
        if c is None and "country" in loc:
            c = continent_for_country(loc["country"])
        if c and c in ISO_TO_CONTINENT:
            cname = ISO_TO_CONTINENT[c]
            desc = "land í {0}u".format(cname[:-1])
        return desc

    if loc["kind"] == "address":
        desc = "heimilisfang"
        return desc

    if loc["kind"] == "street":
        if "country" in loc and loc["country"] == ICELAND_ISOCODE:
            return "gata á Íslandi"
        return "gata"

    if loc["kind"] == "placename":
        return "örnefni"

    return "staður"


def location_info(name, kind, placename_hints=None):
    """ Returns dict with info about a location, given name and kind.
        Info includes country code, gps coordinates etc. """
    if kind not in LOCATION_TAXONOMY:
        return None

    # Continents are marked "lönd" in BÍN, so we set kind manually
    if name in CONTINENTS:
        kind = "continent"

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
        code = CONTINENTS.get(name)

    # Götuheiti
    elif kind == "street":
        # All street names in BÍN are Icelandic
        loc["country"] = ICELAND_ISOCODE
        coords = coords_for_street_name(name, placename_hints=placename_hints)

    # Örnefni
    elif kind == "placename":
        if name in ICE_REGIONS:
            loc["country"] = ICELAND_ISOCODE
        elif name not in ICE_PLACENAME_BLACKLIST:
            info = icelandic_placename_info(name)
            if info:
                loc["country"] = ICELAND_ISOCODE
                # Pick first matching placename w/o disambiguating
                # TODO: This could be smarter
                coords = coords_from_addr_info(info[0])

    if coords:
        (loc["latitude"], loc["longitude"]) = coords

    return loc


def continent_for_country(iso_code):
    """ Return two-char continent code, given a two-char country code """
    assert len(iso_code) == 2

    iso_code = iso_code.upper()
    cc = None
    try:
        cc = country_alpha2_to_continent_code(iso_code)
    except:
        pass

    return cc


def coords_for_country(iso_code):
    """ Return coordinates for a given country code """
    assert len(iso_code) == 2

    iso_code = iso_code.upper()

    # Lazy-load data, save as function attribute
    if not hasattr(coords_for_country, "iso2coord"):
        jsonstr = resource_stream(__name__, COUNTRY_COORDS_JSONPATH).read().decode()
        coords_for_country.iso2coord = json.loads(jsonstr)

    return coords_for_country.iso2coord.get(iso_code)


def coords_for_street_name(street_name, placename=None, placename_hints=[]):
    """ Return coordinates for an Icelandic street name as a tuple. As some
        street names exist in more than one place, we try to narrow it down 
        to a single street if possible. Street coordinates are the coordinates
        of the lowest house number. """

    addresses = iceaddr_lookup(street_name, placename=placename, limit=100)

    if not len(addresses):
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


def icelandic_placename_info(placename):
    """ Look up info about an Icelandic placename ("örnefni") using
        data from Landmælingar Íslands via iceaddr """
    res = placename_lookup(placename)
    if len(res) >= 1:
        # Prefer placenames marked 'Þéttbýli'
        res.sort(key=lambda x: 0 if x.get("flokkur") == "Þéttbýli" else 1)
        return res
    return None


def icelandic_addr_info(addr_str, placename=None, placename_hints=[]):
    """ Look up info about a specific Icelandic address in Staðfangaskrá.
        via iceaddr. We want either a single match or nothing. """
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
    # (possibly with trailing alphabetic character)
    last = comp[-1]
    r = re.search(r"^(\d+)([a-zA-Z]?)$", last)
    if r:
        addr["number"] = int(r.group(1))
        addr["letter"] = r.group(2) or None
        # Non-numeric earlier components must be the street name
        addr["street"] = " ".join(comp[:-1])

    return addr


if __name__ == "__main__":

    name = sys.argv[1] if len(sys.argv) > 1 else None
    kind = sys.argv[2] if len(sys.argv) > 2 else None

    if name and kind:
        print(location_info(name, kind))
