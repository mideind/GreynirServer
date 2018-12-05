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
from iceaddr import iceaddr_lookup
from country_list import countries_for_language, available_languages


ICELAND_ISOCODE = "IS"
ICELANDIC_LANG_ISOCODE = "is"

COUNTRY_COORDS_JSONPATH = "resources/country_coords.json"


def coords_for_country(iso_code):
    """ Return coordinates for a given country code """
    assert len(iso_code) == 2 and iso_code.isupper()

    # Lazy-load data, save as function attribute
    if not hasattr(coords_for_country, "iso2coord"):
        with open(COUNTRY_COORDS_JSONPATH) as f:
            coords_for_country.iso2coord = json.load(f)

    return coords_for_country.iso2coord.get(iso_code)


def coords_for_street_name(street_name, placename=None, placename_hints=[]):
    """ Return coordinates for an Icelandic street name as a tuple """

    addresses = iceaddr_lookup(street_name, placename=placename, limit=100)
    places = set(a["stadur_nf"] for a in addresses if a.get("stadur_nf"))
    addr = None

    # Street name only exists in one place
    if len(places) == 1:
        addr = addresses[0]
    elif placename_hints:
        # See if placename hints can narrow it down
        for pn in placename_hints:
            addresses = iceaddr_lookup(street_name, placename=pn)
            places = set(a["stadur_nf"] for a in addresses if a.get("stadur_nf"))
            if len(places) == 1:
                addr = addresses[0]
                break

    if addr and addr.get("lat_wgs84") and addr.get("long_wgs84"):
        return (addr["lat_wgs84"], addr["long_wgs84"])

    return None


def country_name_for_isocode(iso_code, lang=ICELANDIC_LANG_ISOCODE):
    """ Return country name for an ISO 3166-1 alpha-2 code """
    assert len(iso_code) == 2 and iso_code.isupper()
    assert len(lang) == 2 and lang.islower()
    assert lang in available_languages()

    countries = dict(countries_for_language(lang))
    return countries.get(iso_code)


def isocode_for_country_name(country_name, lang=ICELANDIC_LANG_ISOCODE):
    """ Return ISO 3166-1 alpha-2 code for a country 
        name in the specified language (two-char ISO 639-1) """
    assert len(lang) == 2 and lang.islower()
    assert lang in available_languages()

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
            "England": "GB",
            "Skotland": "GB",
            "Bosnía": "BA",
            "Hersegóvína": "BA",
            "Palestína": "PS",
        }
    }

    if additions.get(lang):
        return additions[lang].get(country_name)

    return None


def icelandic_addr_info(addr_str, placename=None, placename_hints=[]):
    """ Look up info about Icelandic address in Staðfangaskrá """
    addr = parse_address_string(addr_str)

    def lookup(pn):
        a = iceaddr_lookup(
            addr["street"],
            number=addr.get("number"),
            letter=addr.get("letter"),
            placename=pn,
            limit=100,
        )
        return a[0] if len(a) == 1 else None

    # Look up with the (optional) placename provided
    res = lookup(placename)

    # If no single address found, try to disambiguate using placename hints
    if not res:
        for p in placename_hints:
            res = lookup(p)
            if res:
                break

    return res


def parse_address_string(addrstr):
    """ Break Icelandic address string down to its components """
    addr = {"street": addrstr}

    comp = addrstr.split(" ")
    if len(comp) == 1:
        return addr

    last = comp[-1]
    r = re.search(r"^(\d+)([a-zA-Z]?)$", last)
    if r:
        addr["number"] = int(r.group(1))
        addr["letter"] = r.group(2) if r.group(2) else None
        addr["street"] = " ".join(comp[:-1])
    else:
        addr["street"] = addrstr

    return addr
