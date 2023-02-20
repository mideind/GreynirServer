"""

    Greynir: Natural language processing for Icelandic

    Word properties query response module

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


    This module handles queries related to words and their properties,
    e.g. spelling, declension, dictionary definitions, etymology, etc.

"""

# "Hvernig orð er X", "Hvers konar orð er X"
# "Er X [tegund af orði]"
# TODO: Er orðið X í BÍN?
# TODO: Handle definite article in declension ("Hvernig beygist orðið 'kötturinn'?")
# TODO: Declension queries should support adjectives etc.
# TODO: Beautify query by placing word being asked about within quotation marks
# TODO: Handle numbers ("3" should be spelled as "þrír" etc.)
# TODO "Hvaða orð rímar við X"

from typing import Optional, Tuple

import re
import logging
from datetime import datetime, timedelta

from tokenizer.definitions import BIN_Tuple
from islenska.bindb import BinEntryIterable, BinEntryList
from reynir.bindb import GreynirBin

from queries import Query, AnswerTuple
from queries.util import gen_answer
from utility import icequote
from speech.trans import gssml


_WORDTYPE_RX_NOM = "(?:orðið|nafnið|nafnorðið)"
_WORDTYPE_RX_GEN = "(?:orðsins|nafnsins|nafnorðsins)"
_WORDTYPE_RX_DAT = "(?:orðinu|nafninu|nafnorðinu)"

_SPELLING_RX = (
    r"^hvernig stafsetur maður {0}?\s?(.+)$".format(_WORDTYPE_RX_NOM),
    r"^hvernig stafset ég {0}?\s?(.+)$".format(_WORDTYPE_RX_NOM),
    r"^hvernig stafa ég {0}?\s?(.+)$".format(_WORDTYPE_RX_NOM),
    r"^hvernig stafar þú {0}?\s?(.+)$".format(_WORDTYPE_RX_NOM),
    r"^hvernig stafarðu {0}?\s?(.+)$".format(_WORDTYPE_RX_NOM),
    r"^hvernig skal stafsetja {0}?\s?(.+)$".format(_WORDTYPE_RX_NOM),
    r"^hvernig skrifar maður {0}?\s?(.+)$".format(_WORDTYPE_RX_NOM),
    r"^hvernig skrifa ég {0}?\s?(.+)$".format(_WORDTYPE_RX_NOM),
    r"^hvernig stafar maður {0}?\s?(.+)$".format(_WORDTYPE_RX_NOM),
    r"^hvernig rita ég {0}?\s?(.+)$".format(_WORDTYPE_RX_NOM),
    r"^hvernig ritar maður {0}?\s?(.+)$".format(_WORDTYPE_RX_NOM),
    r"^hvernig er {0}?\s?(.+) stafsett$".format(_WORDTYPE_RX_NOM),
    r"^hvernig er {0}?\s?(.+) skrifað$".format(_WORDTYPE_RX_NOM),
    r"^hvernig er {0}?\s?(.+) stafað$".format(_WORDTYPE_RX_NOM),
    r"^hvernig er {0}?\s?(.+) ritað$".format(_WORDTYPE_RX_NOM),
    r"^hvernig skal stafa {0}?\s?(.+)$".format(_WORDTYPE_RX_NOM),
    r"^hvernig skal stafsetja {0}?\s?(.+)$".format(_WORDTYPE_RX_NOM),
    r"^hvernig stafast {0}?\s?(.+)$".format(_WORDTYPE_RX_NOM),
    r"^hvernig ritast {0}?\s?(.+)$".format(_WORDTYPE_RX_NOM),
)


_DECLENSION_RX = (
    r"^hvernig beygi ég {0}\s?(.+)$".format(_WORDTYPE_RX_NOM),
    r"^hvernig fallbeygi ég {0}\s?(.+)$".format(_WORDTYPE_RX_NOM),
    r"^hvernig beygirðu {0}\s?(.+)$".format(_WORDTYPE_RX_NOM),
    r"^hvernig fallbeygirðu {0}\s?(.+)$".format(_WORDTYPE_RX_NOM),
    r"^hvernig á að beygja {0}\s?(.+)$".format(_WORDTYPE_RX_NOM),
    r"^hvernig á að fallbeygja {0}\s?(.+)$".format(_WORDTYPE_RX_NOM),
    r"^hvernig á ég að beygja {0}\s?(.+)$".format(_WORDTYPE_RX_NOM),
    r"^hvernig á ég að fallbeygja {0}\s?(.+)$".format(_WORDTYPE_RX_NOM),
    r"^hvernig á maður að beygja {0}\s?(.+)$".format(_WORDTYPE_RX_NOM),
    r"^hvernig á maður að fallbeygja {0}\s?(.+)$".format(_WORDTYPE_RX_NOM),
    r"^hvernig beygir maður {0}\s?(.+)$".format(_WORDTYPE_RX_NOM),
    r"^hvernig fallbeygir maður {0}\s?(.+)$".format(_WORDTYPE_RX_NOM),
    r"^hvernig beygist {0}\s?(.+)$".format(_WORDTYPE_RX_NOM),
    r"^hvernig fallbeygist {0}\s?(.+)$".format(_WORDTYPE_RX_NOM),
    r"^hvernig skal beygja {0}\s?(.+)$".format(_WORDTYPE_RX_NOM),
    r"^hvernig skal fallbeygja {0}\s?(.+)$".format(_WORDTYPE_RX_NOM),
    r"^hvernig er {0}\s?(.+) beygt$".format(_WORDTYPE_RX_NOM),
    r"^hvernig er {0}\s?(.+) fallbeygt$".format(_WORDTYPE_RX_NOM),
    r"^hverjar eru beygingarmyndir {0}\s?(.+)$".format(_WORDTYPE_RX_GEN),
    r"^hvað eru beygingarmyndir {0}\s?(.+)$".format(_WORDTYPE_RX_GEN),
    r"^hvernig eru beygingarmyndir {0}\s?(.+)$".format(_WORDTYPE_RX_GEN),
    r"^fallbeyging á {0}\s?(.+)$".format(_WORDTYPE_RX_DAT),
)


def lookup_best_word(word: str) -> Optional[Tuple[str, str, str, str]]:
    """Look up word in BÍN, pick right one acc. to a criterion."""
    with GreynirBin().get_db() as db:

        def nouns_only(bin_meaning: BIN_Tuple) -> bool:
            return bin_meaning.ordfl in ("kk", "kvk", "hk")

        res = list(filter(nouns_only, db.lookup_nominative_g(word)))
        if not res:
            # Try with uppercase first char
            capw = word.capitalize()
            res = list(filter(nouns_only, db.lookup_nominative_g(capw)))
            if not res:
                return None

        # OK, we have one or more matching nouns
        if len(res) == 1:
            m = res[0]
        else:
            # TODO: Pick best result
            m = res[0]  # For now

        wid = m.utg

        # TODO: If more than one declension form possible (e.g. gen. björns vs. bjarnar)
        # we should also list such variations
        def sort_by_preference(m_list: BinEntryIterable) -> BinEntryList:
            # Filter out words that don't have the same "utg" i.e. word ID as
            # the one we successfully looked up in BÍN
            mns = list(filter(lambda w: w.bin_id == wid, m_list))
            # Discourage rarer declension forms, i.e. ÞGF2 and ÞGF3
            return sorted(mns, key=lambda m: "2" in m.mark or "3" in m.mark)

        # Look up all cases of the word in BÍN
        nom = m.stofn
        acc = db.cast_to_accusative(nom, filter_func=sort_by_preference)
        dat = db.cast_to_dative(nom, filter_func=sort_by_preference)
        gen = db.cast_to_genitive(nom, filter_func=sort_by_preference)
        return nom, acc, dat, gen


_NOT_IN_BIN_MSG = "Nafnorðið „{0}“ fannst ekki í Beygingarlýsingu íslensks nútímamáls."


def declension_answer_for_word(word: str, query: Query) -> AnswerTuple:
    """Look up all morphological forms of a given word,
    construct natural language response."""

    query.set_qtype("Declension")
    query.set_key(word)
    # Look up in BÍN
    forms = lookup_best_word(word)

    if not forms:
        return gen_answer(_NOT_IN_BIN_MSG.format(word))

    answ = ", ".join(forms)
    response = dict(answer=answ)
    # TODO: Handle plural e.g. "Hér eru"
    cases_desc = "Hér er {0}, um {1}, frá {2}, til {3}".format(*forms)
    voice = f"Orðið {icequote(word)} beygist á eftirfarandi hátt: {cases_desc}."

    # Beautify by placing word in query within quotation marks
    bq = re.sub(word + r"\??$", icequote(word) + "?", query.beautified_query)
    query.set_beautified_query(bq)

    return response, answ, voice


# Time to pause after reciting each character name
_LETTER_INTERVAL = "0.3s"


def spelling_answer_for_word(word: str, query: Query) -> AnswerTuple:
    """Spell out a word provided in a query."""

    # Generate list of characters in word
    chars = list(word)

    # Text answer shows chars in uppercase separated by space
    answ = " ".join([c.upper() for c in chars])
    response = dict(answer=answ)

    # Piece together GSSML for speech synthesis
    v = gssml(word, type="spell", pause_length=_LETTER_INTERVAL)
    voice = f"Orðið {icequote(word)} er stafað á eftirfarandi hátt: {gssml(type='vbreak')} {v}"

    query.set_qtype("Spelling")
    query.set_key(word)

    # Beautify by placing word in query within quotation marks
    bq = re.sub(word + r"\??$", icequote(word) + "?", query.beautified_query)
    query.set_beautified_query(bq)

    return response, answ, voice


def handle_plain_text(q: Query) -> bool:
    """Handle a plain text query, contained in the q parameter."""
    ql = q.query_lower.rstrip("?")

    matches = None
    handler = None

    # Spelling queries
    for rx in _SPELLING_RX:
        matches = re.search(rx, ql)
        if matches:
            handler = spelling_answer_for_word
            break

    # Declension queries
    if handler is None:
        for rx in _DECLENSION_RX:
            matches = re.search(rx, ql)
            if matches:
                handler = declension_answer_for_word
                break

    # Nothing caught by regexes, bail
    if handler is None:
        return False

    assert matches is not None
    matching_word = matches.group(1)

    # Generate answer
    answ: Optional[AnswerTuple]
    try:
        answ = handler(matching_word, q)
    except Exception as e:
        logging.warning("Exception generating word query answer: {0}".format(e))
        q.set_error("E_EXCEPTION: {0}".format(e))
        answ = None

    if answ is not None:
        q.set_answer(*answ)
        q.set_expires(datetime.utcnow() + timedelta(hours=24))
        # Beautify query by placing word being asked about within Icelandic quotation marks
        # TODO: This needs to be fixed, mangles the query if asking about "maður", "orð", etc.
        # bq = re.sub(r"\s({0})".format(matching_word), r" „\1“", q.beautified_query)
        # q.set_beautified_query(bq)
        return True

    return False
