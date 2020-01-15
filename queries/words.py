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

# "Hvernig beygist orðið? X"


import re
import logging
from datetime import datetime, timedelta

from queries import gen_answer
from reynir.bindb import BIN_Db


# Spell out how character names are pronounced
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
    r"^hvernig stafast orðið (.+)$",
)

_DECLENSION_RX = (
    r"^hvernig beygirðu orðið (.+)$",
    r"^hvernig á ég að beygja orðið (.+)$",
    r"^hvernig beygir maður orðið (.+)$",
    r"^hvernig beygist orðið (.+)$",
    r"^hvernig er orðið (.+) beygt$",
    r"^hverjar eru beygingarmyndir orðsins (.+)$",
)


def lookup_best_word(word):
    """ Look up word in BÍN, pick right one acc. to a criterion. """
    with BIN_Db().get_db() as db:
        pass
        # Do lookup
        # Pick best result (prefer nouns vs. adjectives, etc?)


def declension_answer_for_word(word, query):
    # Look up in BÍN
    best = lookup_best_word(word)

    # Get all forms of word
    # Generate answer string
    # Generate voice string ("hér er maður, um mann, frá manni, til manns")

    query.set_qtype("Declension")
    query.set_qkey(word)

    return gen_answer("Það veit ég ekki")


_PAUSE_BTW_LETTERS = 0.3  # Seconds


def spelling_answer_for_word(word, query):
    """ Spell out a word provided in a query. """

    # Generate list of characters in word
    chars = list(word)

    # Text answer shows them in uppercase separated by space
    answ = " ".join([c.upper() for c in chars])
    response = dict(answer=answ)

    # Piece together SSML for speech synthesis
    v = [_CHAR_PRONUNCIATION[c] if c in _CHAR_PRONUNCIATION else c for c in chars]
    jfmt = '<break time="{0}s"/>'.format(_PAUSE_BTW_LETTERS)
    voice = "Orðið '{0}' er stafað á eftirfarandi hátt: {1} {2}".format(
        word, jfmt, jfmt.join(v)
    )

    query.set_qtype("Spelling")
    query.set_qkey(word)

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
    for rx in _DECLENSION_RX:
        matches = re.search(rx, ql)
        if matches:
            handler = declension_answer_for_word
            break

    # Nothing caught by regexes, bail
    if not handler or not matches:
        return False

    # Generate answer
    try:
        answ = handler(matches.group(1), q)
    except Exception as e:
        logging.warning("Exception generating spelling query answer: {0}".format(e))
        q.set_error("E_EXCEPTION: {0}".format(e))
        answ = None

    if answ:
        q.set_answer(*answ)
        q.set_expires(datetime.utcnow() + timedelta(hours=24))
        return True

    return False
