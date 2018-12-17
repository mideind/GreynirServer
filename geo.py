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
from pkg_resources import resource_stream
from iceaddr import iceaddr_lookup, placename_lookup
from country_list import countries_for_language, available_languages


LOCATION_TAXONOMY = frozenset(("country", "placename", "street", "address"))

ICELAND_ISOCODE = "IS"
ICELANDIC_LANG_ISOCODE = "is"

COUNTRY_COORDS_JSONPATH = "resources/country_coords.json"


def location_info(name, kind, placename_hints=None):
    """ Returns dict with info about a location """
    if kind not in LOCATION_TAXONOMY:
        return None

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

    # Götuheiti
    elif kind == "street":
        # All street names in BÍN are Icelandic
        loc["country"] = ICELAND_ISOCODE
        coords = coords_for_street_name(name, placename_hints=placename_hints)

    # Örnefni
    elif kind == "placename":
        info = icelandic_placename_info(name)
        if info:
            loc["country"] = ICELAND_ISOCODE
            # Pick first matching placename, w/o disambiguating
            # TODO: This could be smarter
            coords = coords_from_addr_info(info[0])

    if coords:
        (loc["latitude"], loc["longitude"]) = coords

    return loc


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
    if info and info.get("lat_wgs84") and info.get("long_wgs84"):
        return (info["lat_wgs84"], info["long_wgs84"])
    return None


def country_name_for_isocode(iso_code, lang=ICELANDIC_LANG_ISOCODE):
    """ Return country name for an ISO 3166-1 alpha-2 code """
    assert len(iso_code) == 2
    assert len(lang) == 2

    iso_code = iso_code.upper()
    lang = lang.lower()

    if not lang in available_languages():
        return None

    countries = dict(countries_for_language(lang))
    return countries.get(iso_code)


def isocode_for_country_name(country_name, lang=ICELANDIC_LANG_ISOCODE):
    """ Return the ISO 3166-1 alpha-2 code for a country 
        name in the specified language (two-char ISO 639-1) """
    assert len(lang) == 2

    lang = lang.lower()
    if not lang in available_languages():
        return None

    countries = countries_for_language(lang)
    for iso_code, name in countries:
        if name == country_name:
            return iso_code

    additions = {
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
        }
    }

    if lang in additions:
        return additions[lang].get(country_name)

    return None


def icelandic_placename_info(placename):
    res = placename_lookup(placename)
    if len(res) >= 1:
        # Prefer placenames marked 'Þéttbýli'
        res.sort(key=lambda x: 0 if x.get("flokkur") == "Þéttbýli" else 1)
        return res
    return None


def icelandic_addr_info(addr_str, placename=None, placename_hints=[]):
    """ Look up info about a specific Icelandic address in Staðfangaskrá.
        We want either a single match or nothing. """
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

    last = comp[-1]
    r = re.search(r"^(\d+)([a-zA-Z]?)$", last)
    if r:
        addr["number"] = int(r.group(1))
        addr["letter"] = r.group(2) or None
        addr["street"] = " ".join(comp[:-1])
    else:
        addr["street"] = addrstr

    return addr
