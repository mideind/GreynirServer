#!/usr/bin/env python
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


    This module implements a processor that extracts any addresses / locations
    in parsed sentence trees, looks up information about them and saves to a database.

"""

import logging
from collections import namedtuple
from datetime import datetime
from scraperdb import Location
from geo import location_info

Loc = namedtuple("Loc", ["name", "kind"])

BIN_LOCFL = ["lönd", "göt", "örn"]
LOCFL_TO_KIND = dict(zip(BIN_LOCFL, ["country", "street", "placename"]))

# Always identify these words as locations, even when other meanings exist
ALWAYS_LOCATION = frozenset(
    (
        "París",  # also ism in BÍN
        "Ísrael",  # ism
        "Aþena",  # ism
        "Árborg",  # ism
        "Borg",  # ism
        "Hella",  # ism
    )
)

PLACENAME_BLACKLIST = frozenset(
    (
        "Staður",
        "Eyjan",
        "Fjöll",
        "Bæir",
        "Bær",
        "Rauða",
        "Hjálp",
        "Stjórn",
        "Hrun",
        "Mark",
        "Vatnið",
        "Vatn",
        "Á",
        "Kjarni",
        "Hagar",
        "Þing",
        "Langa",
        "Hús",
        "Kirkjan",
        "Kirkja",
        "Maður",
        "Systur",
        "Pallar",
        "Snið",
        "Stöð"
        "Síða",
        "Síðan",
        "Hundruð",
        "Hestur",
        "Skipti",
        "Skólinn",
        "Skurður",
        "Gat",
        "Eik",
        "Hlíf",
        "Karl",
        "Félagar",
        "Lækur",
        "Síðan",
        "Lægðin",
        "Prestur",
        "Paradís",
        "Lón",
        "Hróarskeldu",
        "Land",
        "Fjórðungur",
        "Grænur",
        "Hagi",
        "Hagar",
        "Opnur",
        "Guðfinna",
        "Svið",
        "Öxi",
        "Skyggnir",
        "Egg",
        "Toppar",
        "Toppur",
        "Einkunn",
        "Borgir",
        "Langur",
        "Drög",
    )
)

STREETNAME_BLACKLIST = frozenset(("Mark", "Á", "Sjáland", "Hús", "Húsið"))

COUNTRY_BLACKLIST = frozenset(())


def article_begin(state):
    """ Called at the beginning of article processing """

    session = state["session"]  # Database session
    url = state["url"]  # URL of the article being processed

    # Delete all existing locations for this article
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

    # Find all placenames mentioned in article
    # We can use them to disambiguate addresses and street names
    placenames = [p.name for p in locs if p.kind == "placename"]

    # Get info about each location and save to database
    for name, kind in locs:
        loc = location_info(name=name, kind=kind, placename_hints=placenames)

        loc["article_url"] = url
        loc["timestamp"] = datetime.utcnow()

        print("Location '{0}' is a {1}".format(loc["name"], loc["kind"]))

        l = Location(**loc)
        session.add(l)


def sentence(state, result):
    """ Called at the end of sentence processing """
    pass


def Heimilisfang(node, params, result):
    """ NP-ADDR """

    # Convert address to nominative case
    def nom(w):
        try:
            bindb = result._state["bin_db"]
            n = bindb.lookup_nominative(w)
        except:
            return w
        return n[0][0] if n else w

    addr_nom = " ".join([nom(c.contained_text()) for c in node.children()])

    # Add as location
    l = Loc(name=addr_nom, kind="address")
    result._state["locations"].add(l)


def _process(node, params, result):
    """ Look up meaning in BÍN, add as location if in right category """
    state = result._state

    # TODO: Special handling of placenames at the beginning
    # of sentences to reduce the number of false positives.

    # Get in nominative form
    txt = node.nominative(state, params)

    # Look up meanings
    try:
        bindb = state["bin_db"]
        meanings = bindb.meanings(txt)
    except Exception as e:
        logging.warning("Error looking up word '{0}': {1}".format(txt, str(e)))
        return

    if not meanings:
        return

    fls = [m.fl for m in meanings]

    # Skip if no location-related meaning
    if not any(f in BIN_LOCFL for f in fls):
        return

    # Skip if one or more non-location-related meanings
    if any(f not in BIN_LOCFL for f in fls):
        if txt in ALWAYS_LOCATION:
            # Get rid of non-loc meanings
            meanings = [m for m in meanings if m.fl in BIN_LOCFL]
        else:
            return

    # If more than one location-related meaning, pick
    # one based on the order of items in BIN_LOCFL
    if len(meanings) > 1:
        meanings.sort(key=lambda x: BIN_LOCFL.index(x.fl))

    m = meanings[0]
    name = m.stofn
    kind = LOCFL_TO_KIND[m.fl]

    # Skip if blacklisted
    if kind == "placename" and name in PLACENAME_BLACKLIST:
        return
    if kind == "street" and name in STREETNAME_BLACKLIST:
        return
    if kind == "country" and name in COUNTRY_BLACKLIST:
        return

    # Add
    loc = Loc(name=name, kind=kind)
    state["locations"].add(loc)


""" Country and place names can occur as both Fyrirbæri and Sérnafn """


def Sérnafn(node, params, result):
    _process(node, params, result)


def Fyrirbæri(node, params, result):
    _process(node, params, result)
