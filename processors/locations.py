"""
    Greynir: Natural language processing for Icelandic

    Copyright (C) 2023 Miðeind ehf.

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
    in article tokens, looks up information about them and saves to a database.

"""

from typing import List
from datetime import datetime

from db.models import Location
from tokenizer import TOK
from geo import location_info
from tree import TreeStateDict, Loc
from treeutil import TokenDict


MODULE_NAME = __name__
PROCESSOR_TYPE = "token"


LOCFL = ["lönd", "göt", "örn", "borg"]
LOCFL_TO_KIND = dict(zip(LOCFL, ["country", "street", "placename", "placename"]))


# Always identify these words as locations, even when they
# have been identified as words in some other category.
ALWAYS_LOCATION = frozenset(
    (
        "París",  # also ism in BÍN
        # "Aþena",  # ism
        # "Árborg",  # ism
        # "Borg",  # ism
        # "Hella",  # ism
    )
)

# GENERAL_BLACKLIST = frozenset(())

PLACENAME_BLACKLIST = frozenset(
    (
        "Sámur",
        "Staður",
        "Eyjan",
        "Eyja",
        "Fjöll",
        "Bæir",
        "Bær",
        "Rauða",
        "Hjálp",
        "Stjórn",
        "Hrun",
        "Hrunið",
        "Mark",
        "Bás",
        "Vatnið",
        "Vatn",
        "Á",
        "Flag",
        "Stigi",
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
        "Stöð",
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
        "Land",
        "Gil",
        "Höllin",
        "Höll",
        "Fjórðungur",
        "Grænur",
        "Hagi",
        "Brenna",
        "Hraun",
        "Hagar",
        "Opnur",
        "Guðfinna",  # !
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
        "Haf",
        "Fossar",
        "Stuðlar",
        "Straumur",
        "Eden",
        "Haft",
        "Rétt",
        "Veitur",
        "Örkin",
        "Svangi",
        "Samvinna",
        "Stígamót",
        "Tafla",
        "Rauði",
        "Reitar",
        "Festi",
        "Bekkur",
        "Bakland",
    )
)

STREETNAME_BLACKLIST = frozenset(("Mark", "Á", "Sjáland", "Hús", "Húsið"))

# COUNTRY_BLACKLIST = frozenset(())


def article_begin(state: TreeStateDict) -> None:
    """Called at the beginning of article processing"""

    session = state["session"]  # Database session
    url = state["url"]  # URL of the article being processed

    # Delete all existing locations for this article
    session.execute(Location.table().delete().where(Location.article_url == url))  # type: ignore

    # Set that will contain all unique locations found in the article
    state["locations"] = set()


def article_end(state: TreeStateDict) -> None:
    """Called at the end of article processing"""

    locs = state.get("locations")
    if not locs:
        return

    url = state["url"]
    session = state["session"]

    # Find all placenames mentioned in article
    # We can use them to disambiguate addresses and street names
    # TODO: Perhaps do this in a more fine-grained manner, at a
    # sentence or paragraph level.
    placenames = [p.name for p in locs if p.kind == "placename"]

    # Get info about each location and save to database
    for name, kind in locs:
        loc = location_info(name=name, kind=kind, placename_hints=placenames)

        loc["article_url"] = url
        loc["timestamp"] = datetime.utcnow()

        print("Location '{0}' is a {1}".format(loc["name"], loc["kind"]))

        locmodel = Location(**loc)
        session.add(locmodel)


# def paragraph_begin(state, paragraph):
#     pass


# def paragraph_end(state, paragraph):
#     pass


# def sentence_begin(state, paragraph, sentence):
#     pass


# def sentence_end(state, paragraph, sentence):
#     pass


def token(
    state: TreeStateDict,
    paragraph: List[List[TokenDict]],
    sentence: List[TokenDict],
    token: TokenDict,
    idx: int,
) -> None:
    """Called for each token in each sentence. idx is the
    index of the token within the sentence."""
    if "m" not in token or len(token["m"]) < 3:
        return

    name = token["m"][0]  # Nominative case
    fl = token["m"][2]  # BÍN category
    if fl not in LOCFL and name not in ALWAYS_LOCATION:
        return

    kind = LOCFL_TO_KIND.get(fl)

    # Skip if blacklisted
    # if name in GENERAL_BLACKLIST:
    #     return
    if kind == "placename" and name in PLACENAME_BLACKLIST:
        return
    if kind == "street" and name in STREETNAME_BLACKLIST:
        return
    # if kind == "country" and name in COUNTRY_BLACKLIST:
    #     return

    # Special handling of addresses
    # Check if next token is a house number
    if kind == "street" and idx != len(sentence) - 1:  # not last token in sentence
        next_tok = sentence[idx + 1]
        next_word = next_tok["x"]
        if "k" in next_tok and (
            next_tok["k"] == TOK.NUMBER or next_tok["k"] == TOK.NUMWLETTER
        ):
            name = "{0} {1}".format(name, next_word)
            kind = "address"

    # Add
    loc = Loc(name=name, kind=kind)
    state["locations"].add(loc)
