#!/usr/bin/env python
"""
    Reynir: Natural language processing for Icelandic

    Processor module to extract entity names & definitions

    Copyright (C) 2016 Vilhjálmur Þorsteinsson

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


    This module implements a processor that looks at parsed sentence trees
    and extracts any addresses / locations, looks up information about
    them and saves to a database.

"""

from datetime import datetime
from scraperdb import Location
from iceaddr import iceaddr_lookup
from country_list import countries_for_language, available_languages
from pprint import pprint


def _country_name_for_isocode(iso_code, language="is"):
    assert language in available_languages()
    assert len(iso_code) == 2

    countries = dict(countries_for_language(language))
    return countries.get(iso_code)

def _isocode_for_country_name(country_name, language="is"):
    """ Return ISO 3166-1 alpha-2 code for a country 
        name in the specified language"""
    assert language in available_languages()

    countries = countries_for_language(language)
    for iso_code, name in countries:
        if name == country_name:
            return iso_code

    return None

def article_begin(state):
    """ Called at the beginning of article processing """

    # Delete all existing locations for this article
    # session = state["session"] # Database session
    # url = state["url"] # URL of the article being processed
    # session.execute(Location.table().delete().where(Location.article_url == url))


def article_end(state):
    """ Called at the end of article processing """
    pass


def sentence(state, result):
    """ Called at the end of sentence processing """
    pass

def Heimilisfang(node, params, result):
    return
    addrstr = node.contained_text()
    print(addrstr)

    children = list(node.children())
    last = children[-1]
    first = children[0]
    # print(', '.join("%s: %s" % item for item in vars(first).items()))

    def nom(w):
        bindb = result._state["bin_db"]
        n = bindb.lookup_nominative(w)
        return n[0][0] if n else w

    street = " ".join([nom(c.contained_text()) for c in children[:-1]])

    number = int(last.contained_text())
    address = "{0} {1}".format(street, number)
    print(address)

    # Look up address in Staðfangaskrá
    info = None
    lat = None
    lon = None
    if last.tokentype in ["NUMBER", "NUMWLETTER"]:
        info = iceaddr_lookup(street, number=number, letter="")
        if len(info) == 1:
            (lat, lon) = (info[0]["lat_wgs84"], info[0]["long_wgs84"])

    session = result._state["session"]
    url = result._state["session"]
    l = Location(
        article_url=result._state["url"],
        name=address,
        kind="address",
        country="IS",
        latitude=lat,
        longitude=lon,
        data=info,
        timestamp=datetime.utcnow(),
    )
    session.add(l)

    # for c in children:
    #     print(c.contained_text())
    #     print(c.tokentype)
    #     #print(c._nominative)


def Sérnafn(node, params, result):
    return
    # print("")
    # pprint(node.contained_text())
    # for c in node.descendants():
    #     pprint(type(c).__name__)
    #     pprint('    ' + type(c).__name__ + ': ' + c.contained_text())
    # child = next(node.descendants())
    # pprint(child.contained_text())

    bindb = result["_state"]["bin_db"]
    name = node.contained_text()
    m = bindb.meanings(name)
    for me in m: # "göt", "örn",
        if me.fl in [ "lönd"]:
            print("\n" + result["_state"]["url"])
            nom = me[0]
            pprint(nom)
            if me.fl == "lönd":
                print(_iso_for_country(nom))
