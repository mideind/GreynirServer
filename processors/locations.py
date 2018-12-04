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

from collections import namedtuple
from datetime import datetime
from scraperdb import Location
from geo import (
    coords_for_country,
    coords_for_street_name,
    icelandic_addr_info,
    isocode_for_country_name,
    ICELAND_ISOCODE,
)

PLACENAME_BLACKLIST = ["Staður", "Eyjan", "Fjöll", "Bæir""]

Loc = namedtuple("Loc", "name kind")


def article_begin(state):
    """ Called at the beginning of article processing """

    # Delete all existing locations for this article
    session = state["session"]  # Database session
    url = state["url"]  # URL of the article being processed
    session.execute(Location.table().delete().where(Location.article_url == url))

    # Set of all unique locations found in article
    state["locations"] = set()


def article_end(state):
    """ Called at the end of article processing """

    url = state["url"]
    session = state["session"]

    locs = state.get("locations")
    if not locs:
        return

    print(locs)

    # Find all placenames mentioned in article
    # We can use them to disambiguate addresses and street names
    placenames = [p.name for p in locs if p.kind == "placename"]

    # Get info about each location and save to database
    for loctuple in locs:
        loc = loctuple._asdict()
        kind = loc["kind"]
        coords = None

        # Heimilisfang
        if kind == "address":
            loc["country"] = ICELAND_ISOCODE
            info = icelandic_addr_info(loc["name"], placename_hints=placenames)
            if info and info.get("lat_wgs84") and info.get("long_wgs84"):
                coords = (info["lat_wgs84"], info["long_wgs84"])
            loc["data"] = info

        # Land
        elif kind == "country":
            code = isocode_for_country_name(loc["name"])
            if code:
                loc["country"] = code
                coords = coords_for_country(code)

        # Götuheiti
        elif kind == "street":
            # All the street names in BÍN are Icelandic
            loc["country"] = ICELAND_ISOCODE
            coords = coords_for_street_name(loc["name"], placename_hints=placenames)

        # Örnefni
        elif kind == "placename":
            if loc["name"] in PLACENAME_BLACKLIST:
                continue

        if coords:
            (loc["latitude"], loc["longitude"]) = coords

        loc["article_url"] = url
        loc["timestamp"] = datetime.utcnow()

        l = Location(**loc)
        session.add(l)


def sentence(state, result):
    """ Called at the end of sentence processing """
    pass


def Heimilisfang(node, params, result):
    """ NP-ADDR """

    children = list(node.children())

    # Make sure address is in nominative case
    def nom(w):
        bindb = result._state["bin_db"]
        n = bindb.lookup_nominative(w)
        return n[0][0] if n else w

    addr_nom = " ".join([nom(c.contained_text()) for c in children])

    l = Loc(name=addr_nom, kind="address")
    result._state["locations"].add(l)


def Nafn(node, params, result):
    # print(node.contained_text())
    pass


def Sérnafn(node, params, result):
    # print(node.contained_text())

    state = result._state

    bindb = result["_state"]["bin_db"]
    name = node.contained_text()
    meanings = bindb.meanings(name)

    loc_fl = ["göt", "lönd", "örn"]
    binfl2kind = dict(zip(loc_fl, ["street", "country", "placename"]))

    # TODO: Ignore words with non-placename meanings?
    for m in meanings:
        if m.fl not in loc_fl:
            continue

        nom = m[0]
        kind = binfl2kind[m.fl]

        # HACK: BÍN has Iceland as "örn"!
        if nom == "Ísland":
            kind = "country"

        loc = Loc(name=nom, kind=kind)
        state["locations"].add(loc)
