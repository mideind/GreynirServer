"""

    Greynir: Natural language processing for Icelandic

    Word properties query response module

    Copyright (C) 2020 Miðeind ehf.

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
# "Hvernig beygist *nafnorðið* X?" "Hvernig beygist lýsingarorðið X?"
# "Er X [tegund af orði]"
# TODO: Beautify query by placing word being asked about within quotation marks

import re
import logging
from datetime import datetime, timedelta

from queries import gen_answer
from reynir.bindb import BIN_Db


# Spell out how character names are pronounced in Icelandic
_CHAR_PRONUNCIATION = {
    "a": "a",
    "á": "á",
    "b": "bé",
    "c": "sé",
    "d": "dé",
    "ð": "eð",
    "e": "e",
    "é": "je",
    "f": "eff",
    "g": "gé",
    "h": "há",
    "i": "i",
    "í": "í",
    "j": "joð",
    "k": "ká",
    "l": "ell",
    "m": "emm",
    "n": "enn",
    "o": "o",
    "ó": "ó",
    "p": "pé",
    "q": "kú",
    "r": "err",
    "s": "ess",
    "t": "té",
    "u": "u",
    "ú": "ú",
    "v": "vaff",
    "x": "ex",
    "y": "ufsilon i",
    "ý": "ufsilon í",
    "þ": "þoddn",
    "æ": "æ",
    "ö": "ö",
    "z": "seta",
}


_SPELLING_RX = (
    r"^hvernig stafsetur maður orðið (.+)$",
    r"^hvernig stafsetur maður (.+)$",
    r"^hvernig skal stafsetja (.+)$",
    r"^hvernig skal stafsetja orðið (.+)$",
    r"^hvernig skrifar maður orðið (.+)$",
    r"^hvernig skrifar maður (.+)$",
    r"^hvernig stafar maður orðið (.+)$",
    r"^hvernig stafar maður (.+)$",
    r"^hvernig er orðið (.+) stafsett$",
    r"^hvernig er (.+) stafsett$",
    r"^hvernig er orðið (.+) skrifað$",
    r"^hvernig er (.+) skrifað$",
    r"^hvernig er orðið (.+) stafað$",
    r"^hvernig er (.+) stafað$",
    r"^hvernig skal stafa (.+)$",
    r"^hvernig skal stafa orðið (.+)$",
    r"^hvernig stafast orðið (.+)$",
)


_DECLENSION_RX = (
    r"^hvernig beygi ég orðið (.+)$",
    r"^hvernig beygirðu orðið (.+)$",
    r"^hvernig á að beygja orðið (.+)$",
    r"^hvernig á ég að beygja orðið (.+)$",
    r"^hvernig á maður að beygja orðið (.+)$",
    r"^hvernig beygir maður orðið (.+)$",
    r"^hvernig beygist orðið (.+)$",
    r"^hvernig skal beygja orðið (.+)$",
    r"^hvernig er orðið (.+) beygt$",
    r"^hverjar eru beygingarmyndir orðsins (.+)$",
    r"^hvað eru beygingarmyndir orðsins (.+)$",
)


def lookup_best_word(word):
    """ Look up word in BÍN, pick right one acc. to a criterion. """
    res = BIN_Db().lookup_nominative(word)
    if not res:
        return None

    # OK, we have one or more matching words
    if len(res) == 1:
        m = res[0]
    else:
        # TODO: Pick best result (prefer nouns vs. adjectives, etc?)
        m = res[0]  # For now

    # TODO: Fix this. If more than one declesion possible, list them all
    def sort_by_preference(m_list):
        """ Discourage rarer declension forms, i.e. ÞGF2 and ÞGF3 """
        return sorted(m_list, key=lambda m: "2" in m.beyging or "3" in m.beyging)

    # Look up all cases of the word in BÍN
    with BIN_Db().get_db() as db:
        nom = m.stofn
        acc = db.cast_to_accusative(nom, meaning_filter_func=sort_by_preference)
        dat = db.cast_to_dative(nom, meaning_filter_func=sort_by_preference)
        gen = db.cast_to_genitive(nom, meaning_filter_func=sort_by_preference)
        return nom, acc, dat, gen


_NOT_IN_BIN_MSG = "Orðið '{0}' fannst ekki í Beyingarlýsingu íslensks nútímamáls."


def declension_answer_for_word(word, query):
    """ Look up all morphological forms of a given word,
        construct natural language response. """

    # Look up in BÍN
    forms = lookup_best_word(word)

    if not forms:
        return gen_answer(_NOT_IN_BIN_MSG.format(word))

    answ = ", ".join(forms)
    response = dict(answer=answ)
    cases_desc = "Hér er {0}, um {1}, frá {2}, til {3}".format(*forms)
    voice = "Orðið '{0}' beygist á eftirfarandi hátt: {1}.".format(word, cases_desc)

    query.set_qtype("Declension")
    query.set_key(word)

    return response, answ, voice


# Time to pause after reciting each character name
_PAUSE_BTW_LETTERS = 0.3  # Seconds


def spelling_answer_for_word(word, query):
    """ Spell out a word provided in a query. """

    # Generate list of characters in word
    chars = list(word)

    # Text answer shows chars in uppercase separated by space
    answ = " ".join([c.upper() for c in chars])
    response = dict(answer=answ)

    # Piece together SSML for speech synthesis
    v = [_CHAR_PRONUNCIATION.get(c, c) for c in chars]
    jfmt = '<break time="{0}s"/>'.format(_PAUSE_BTW_LETTERS)
    voice = "Orðið '{0}' er stafað á eftirfarandi hátt: {1} {2}".format(
        word, jfmt, jfmt.join(v)
    )

    query.set_qtype("Spelling")
    query.set_key(word)

    return response, answ, voice


def handle_plain_text(q):
    """ Handle a plain text query, contained in the q parameter. """
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
    if not handler:
        for rx in _DECLENSION_RX:
            matches = re.search(rx, ql)
            if matches:
                handler = declension_answer_for_word
                break

    # Nothing caught by regexes, bail
    if not handler:
        return False

    # Generate answer
    try:
        answ = handler(matches.group(1), q)
    except Exception as e:
        logging.warning("Exception generating word query answer: {0}".format(e))
        q.set_error("E_EXCEPTION: {0}".format(e))
        answ = None

    if answ:
        q.set_answer(*answ)
        q.set_expires(datetime.utcnow() + timedelta(hours=24))
        return True

    return False
