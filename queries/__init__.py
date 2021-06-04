"""

    Greynir: Natural language processing for Icelandic

    Copyright (C) 2021 Miðeind ehf.

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


    Queries folder
    This is the location to put custom query responders.

    This file contains various shared functions used by the query modules.

"""

from tree import Node
from typing import Mapping, Optional, List, Dict, Tuple, Union, cast, Iterable

import logging
import requests
import json
import os
import re
import locale
from urllib.parse import urlencode
from functools import lru_cache
from xml.dom import minidom  # type: ignore

from tzwhere import tzwhere  # type: ignore
from pytz import country_timezones

from geo import country_name_for_isocode, iceprep_for_cc
from reynir import NounPhrase
from settings import changedlocale
from util import read_api_key


# Type definitions
AnswerTuple = Tuple[Dict, str, str]
LatLonTuple = Tuple[float, float]


def natlang_seq(words: List[str], oxford_comma: bool = False) -> str:
    """Generate an Icelandic natural language sequence of words
    e.g. "A og B", "A, B og C", "A, B, C og D"."""
    if not words:
        return ""
    if len(words) == 1:
        return words[0]
    return "{0}{1} og {2}".format(
        ", ".join(words[:-1]), "," if oxford_comma and len(words) > 2 else "", words[-1]
    )


def nom2dat(w: str) -> str:
    """ Look up the dative of an Icelandic noun given its nominative form. """
    try:
        d = NounPhrase(w).dative
        return d or w
    except Exception:
        pass
    return w


def is_plural(num: Union[str, int, float]) -> bool:
    """Determine whether an Icelandic word following a given number should be
    plural or not, e.g. "21 maður", "22 menn", "1,1 kílómetri", "11 menn" etc.
    Accepts string, float or int as argument."""
    sn = str(num)
    return not (sn.endswith("1") and not sn.endswith("11"))


def sing_or_plur(num: Union[int, float], sing: str, pl: str) -> str:
    """Utility function that returns a formatted string w. Icelandic number and a subsequent
    singular or plural noun, as appropriate, e.g. "1 einstaklingur", "2 einstaklingar",
    "21 einstaklingur" etc. Accepts both floats and ints as first argument."""
    return f"{iceformat_float(num)} {pl if is_plural(num) else sing}"


# The following needs to include at least nominative and dative forms of number words
_NUMBER_WORDS: Mapping[str, float] = {
    "núll": 0,
    "hálfur": 0.5,
    "hálfum": 0.5,
    "hálf": 0.5,
    "hálfri": 0.5,
    "hálft": 0.5,
    "hálfu": 0.5,
    "einn": 1,
    "einum": 1,
    "ein": 1,
    "einni": 1,
    "eitt": 1,
    "einu": 1,
    "tveir": 2,
    "tveim": 2,
    "tveimur": 2,
    "tvær": 2,
    "tvö": 2,
    "þrír": 3,
    "þrem": 3,
    "þremur": 3,
    "þrjár": 3,
    "þrjú": 3,
    "fjórir": 4,
    "fjórum": 4,
    "fjórar": 4,
    "fjögur": 4,
    "fimm": 5,
    "sex": 6,
    "sjö": 7,
    "átta": 8,
    "níu": 9,
    "tíu": 10,
    "ellefu": 11,
    "tólf": 12,
    "þrettán": 13,
    "fjórtán": 14,
    "fimmtán": 15,
    "sextán": 16,
    "sautján": 17,
    "átján": 18,
    "nítján": 19,
    "tuttugu": 20,
    "þrjátíu": 30,
    "fjörutíu": 40,
    "fimmtíu": 50,
    "sextíu": 60,
    "sjötíu": 70,
    "áttatíu": 80,
    "níutíu": 90,
    "hundrað": 100,
    "þúsund": 1000,
    "milljón": 1e6,
    "milljarður": 1e9,
}


def parse_num(node: Node, num_str: str) -> float:
    """Parse Icelandic number string to float or int.
    TODO: This needs to be a more capable, generic function. There are
    several mildly differing implementions in various query modules."""

    # Hack to handle the word "eina" being identified as f. name "Eina"
    if num_str in ("Eina", "Einu"):
        return 1.0

    # If we have a number token as a direct child,
    # return its numeric value directly
    num = node.child.contained_number
    if num is not None:
        return float(num)
    try:
        # Handle numbers with Icelandic decimal places ("17,2")
        # and potentially thousands separators as well
        num_str = num_str.replace(".", "")
        if re.search(r"^\d+,\d+", num_str):
            num = float(num_str.replace(",", "."))
        # Handle digits ("17")
        else:
            num = float(num_str)
    except ValueError:
        # Handle number words ("sautján")
        num = _NUMBER_WORDS.get(num_str)
        if num is not None:
            num = float(num)
    except Exception as e:
        logging.warning("Unexpected exception: {0}".format(e))
        raise
    return num or 0.0


# Neutral gender form of numbers
NUMBERS_NEUTRAL = {
    "1": "eitt",
    "2": "tvö",
    "3": "þrjú",
    "4": "fjögur",
    "21": "tuttugu og eitt",
    "22": "tuttugu og tvö",
    "23": "tuttugu og þrjú",
    "24": "tuttugu og fjögur",
    "31": "þrjátíu og eitt",
    "32": "þrjátíu og tvö",
    "33": "þrjátíu og þrjú",
    "34": "þrjátíu og fjögur",
    "41": "fjörutíu og eitt",
    "42": "fjörutíu og tvö",
    "43": "fjörutíu og þrjú",
    "44": "fjörutíu og fjögur",
    "51": "fimmtíu og eitt",
    "52": "fimmtíu og tvö",
    "53": "fimmtíu og þrjú",
    "54": "fimmtíu og fjögur",
    "61": "sextíu og eitt",
    "62": "sextíu og tvö",
    "63": "sextíu og þrjú",
    "64": "sextíu og fjögur",
    "71": "sjötíu og eitt",
    "72": "sjötíu og tvö",
    "73": "sjötíu og þrjú",
    "74": "sjötíu og fjögur",
    "81": "áttatíu og eitt",
    "82": "áttatíu og tvö",
    "83": "áttatíu og þrjú",
    "84": "áttatíu og fjögur",
    "91": "níutíu og eitt",
    "92": "níutíu og tvö",
    "93": "níutíu og þrjú",
    "94": "níutíu og fjögur",
    "101": "hundrað og eitt",
    "102": "hundrað og tvö",
    "103": "hundrað og þrjú",
    "104": "hundrað og fjögur",
}

HUNDREDS = ("tvö", "þrjú", "fjögur", "fimm", "sex", "sjö", "átta", "níu")


def numbers_to_neutral(s: str) -> str:
    """Convert integers within the string s to voice
    representations using neutral gender, i.e.
    4 -> 'fjögur', 21 -> 'tuttugu og eitt'"""

    def convert(m):
        match = m.group(0)
        n = int(match)
        prefix = ""
        if 121 <= n <= 999 and 1 <= (n % 10) <= 4 and not 11 <= (n % 100) <= 14:
            # A number such as 104, 223, 871 (but not 111 or 614)
            if n // 100 == 1:
                prefix = "hundrað "
            else:
                prefix = HUNDREDS[n // 100 - 2] + " hundruð "
            n %= 100
            if n <= 4:
                # 'tvö hundruð og eitt', 'sjö hundruð og fjögur'
                prefix += "og "
            match = str(n)
        return prefix + NUMBERS_NEUTRAL.get(match, match)

    return re.sub(r"(\d+)", convert, s)


_SUB_20_NEUTRAL = {
    1: "eitt",
    2: "tvö",
    3: "þrjú",
    4: "fjögur",
    5: "fimm",
    6: "sex",
    7: "sjö",
    8: "átta",
    9: "níu",
    10: "tíu",
    11: "ellefu",
    12: "tólf",
    13: "þrettán",
    14: "fjórtán",
    15: "fimmtán",
    16: "sextán",
    17: "sautján",
    18: "átján",
    19: "nítján",
}

_TENS_NEUTRAL = {
    20: "tuttugu",
    30: "þrjátíu",
    40: "fjörutíu",
    50: "fimmtíu",
    60: "sextíu",
    70: "sjötíu",
    80: "áttatíu",
    90: "níutíu",
}

_NUM_NEUT_TO_KK = {
    "eitt": "einn",
    "tvö": "tveir",
    "þrjú": "þrír",
    "fjögur": "fjórir",
}

_NUM_NEUT_TO_KVK = {
    "eitt": "ein",
    "tvö": "tvær",
    "þrjú": "þrjár",
    "fjögur": "fjórar",
}

_LARGE_NUMBERS = (
    (int(1e21) * int(1e21) * int(1e6), "oktilljón"),  # 10^48
    (int(1e21) * int(1e21), "septilljón"),  # 10^42
    (int(1e21) * int(1e15), "sextilljón"),  # 10^36
    (int(1e21) * int(1e9), "kvintilljón"),  # 10^30
    (int(1e21) * int(1e6), "kvaðrilljarð"),  # 10^27
    (int(1e21) * int(1e3), "kvaðrilljón"),  # 10^24
    (int(1e21), "trilljarð"),  # 10^21
    (int(1e18), "trilljón"),  # 10^18
    (int(1e15), "billjarð"),  # 10^15
    (int(1e12), "billjón"),  # 10^12
    (int(1e9), "milljarð"),  # 10^9
    (int(1e6), "milljón"),  # 10^6
)


def number_to_neutral(n: int = 0) -> str:
    """
    Write integer out as text in Icelandic.
    Example:
        1337 -> eitt þúsund þrjú hundruð þrjátíu og sjö
    """
    try:
        n = int(n)
    except ValueError:
        return ""

    if n == 0:
        return "núll"

    text: List[str] = []
    if n < 0:
        text.append("mínus")
        n = -n

    MILLION = 1000000
    THOUSAND = 1000

    # Very large numbers
    while n >= MILLION:
        for large_num, isl_num in _LARGE_NUMBERS:
            if large_num <= n:
                break

        large_count, n = divmod(n, large_num)

        text.extend(number_to_neutral(large_count).split())

        if isl_num.endswith("jarð"):  # kk
            text[-1] = _NUM_NEUT_TO_KK.get(text[-1], text[-1])
            if text[-1] == "einn":
                text.append(isl_num + "ur")
            else:
                text.append(isl_num + "ar")

        elif isl_num.endswith("jón"):  # kvk
            text[-1] = _NUM_NEUT_TO_KVK.get(text[-1], text[-1])
            if text[-1] == "ein":
                text.append(isl_num)
            else:
                text.append(isl_num + "ir")

    if THOUSAND <= n < MILLION:
        thousands, n = divmod(n, THOUSAND)

        if thousands > 1:
            text.append(number_to_neutral(thousands))
        elif thousands == 1:
            text.append("eitt")
        # Singular/Plural form of "þúsund" is the same
        text.append("þúsund")

    if 100 <= n < THOUSAND:
        hundreds, n = divmod(n, 100)

        if hundreds > 1:
            text.append(number_to_neutral(hundreds))
            # Note: don't need to fix singular here as e.g.
            # 2100 gets interpreted as "tvö þúsund og eitt hundrað"
            # instead of "tuttugu og eitt hundrað"
            text.append("hundruð")

        elif hundreds == 1:
            text.append("eitt")
            text.append("hundrað")

    if 20 <= n < 100:
        tens, digit = divmod(n, 10)
        tens *= 10

        text.append(_TENS_NEUTRAL[tens])
        if digit != 0:
            text.append("og")
            text.append(_SUB_20_NEUTRAL[digit])
        n = 0

    if 0 < n < 20:
        text.append(_SUB_20_NEUTRAL[n])
        n = 0

    if len(text) > 2 and text[-2] != "og":
        # Fix sentences with missing "og"
        if text[-1] in _SUB_20_NEUTRAL.values() or text[-1] in _TENS_NEUTRAL.values():
            # "fimm þúsund tuttugu" -> "fimm þúsund og tuttugu"
            # "eitt hundrað fjögur" -> "eitt hundrað og fjögur"
            text.insert(-1, "og")
        elif (
            len(text) >= 3
            and not re.search(r"(hundr|þúsund|jarð|jón)", text[-2])
            and text[-3] != "og"
        ):
            # TODO: This if statement can probably be improved

            # If-statement catches errors like "eitt og hundrað milljónir",
            # but fixes numbers such as:
            # "fimm þúsund tvö hundruð" -> "fimm þúsund og tvö hundruð"
            # "sextíu milljónir fjögur hundruð" -> "sextíu milljónir og fjögur hundruð"
            text.insert(-2, "og")

    # Fix e.g. "milljónir milljarðar" -> "milljónir milljarða"
    number_string: str = re.sub(
        r"(\S*(jónir|jarð[au]r?)) (\S*(jarð|jón))[ia]r", r"\1 \3a", " ".join(text)
    )

    return number_string


def number_to_text(n: int, gender="hk") -> str:
    """
    Convert an integer into written Icelandic text in given gender (hk, kk, kvk).
    Example:
        302 -> "þrjú hundruð og tvær" (gender="kvk")
        501 -> "fimm hundruð og einn" (gender="kk")
    """
    num_str = number_to_neutral(n)

    if gender =="hk":
        return num_str

    nums = num_str.split()

    if gender=="kk" and nums[-1] in _NUM_NEUT_TO_KK:
        nums[-1] = _NUM_NEUT_TO_KK[nums[-1]]

    elif gender=="kvk" and nums[-1] in _NUM_NEUT_TO_KVK:
        nums[-1] = _NUM_NEUT_TO_KVK[nums[-1]]

    return " ".join(nums)


def float_to_text(f: float = 0.0, gender="hk") -> str:
    """
    Convert a float into written Icelandic text in given gender (hk, kk, kvk).
    Example:
        -0.02 -> "mínus núll komma núll tveir" (gender="kk")
    """
    out_str: str = ""
    # To prevent edge cases like -0.2 being translated to
    # "núll komma tvö" instead of "mínus núll komma tvö"
    if f < 0:
        out_str = "mínus "

    first, second = str(f).split(".")

    # Number before decimal point
    out_str += number_to_text(abs(int(first)), gender)
    out_str += " komma "

    # Numbers after decimal point
    for digit in second:
        if digit == "0":
            out_str += "núll "
        else:
            digit_str = _SUB_20_NEUTRAL.get(int(digit), "")
            if gender == "kk" and digit_str in _NUM_NEUT_TO_KK:
                out_str+= _NUM_NEUT_TO_KK[digit_str]
            elif gender == "kvk" and digit_str in _NUM_NEUT_TO_KVK:
                out_str+= _NUM_NEUT_TO_KVK[digit_str]
            else:
                out_str += digit_str
            out_str += " "

    return out_str.strip()


def year_to_text(year: int, after_christ: bool = False) -> str:
    """
    Write year as text in Icelandic.
    Negative years automatically append "fyrir Krist" to the text.
    If after_christ is True, add "eftir Krist" after the year.
    """
    suffix: str = ""
    text: List[str] = []

    if year < 0:
        suffix = " fyrir Krist"
        year = -year

    elif year > 0 and after_christ:
        suffix = " eftir Krist"

    # People say e.g. "nítján hundruð þrjátíu og tvö"
    # instead of "eitt þúsund níu hundruð þrjátíu og tvö"
    # for years between 1100-2000
    if 1100 <= year < 2000:
        hundreds, digits = divmod(year, 100)

        text.append(_SUB_20_NEUTRAL[hundreds])
        text.append("hundruð")
        text.append(number_to_neutral(digits))

    # Other years are spoken like regular numbers
    else:
        text.append(number_to_neutral(year))

    return " ".join(text) + suffix


FYRSTUR_STRONG_DECL = {
    "et": {
        "kk": {"nf": "fyrstur", "þf": "fyrstan", "þgf": "fyrstum", "ef": "fyrsts"},
        "kvk": {"nf": "fyrst", "þf": "fyrsta", "þgf": "fyrstri", "ef": "fyrstrar"},
        "hk": {"nf": "fyrst", "þf": "fyrst", "þgf": "fyrstu", "ef": "fyrsts"},
    },
    "ft": {
        "kk": {"nf": "fyrstir", "þf": "fyrsta", "þgf": "fyrstum", "ef": "fyrstra"},
        "kvk": {"nf": "fyrstrar", "þf": "fyrstar", "þgf": "fyrstum", "ef": "fyrstra"},
        "hk": {"nf": "fyrst", "þf": "fyrst", "þgf": "fyrstum", "ef": "fyrstra"},
    },
}

_SUB_20_NEUT_TO_ORDINAL = {
    "eitt": "fyrst",
    # 2 is a special case
    "þrjú": "þriðj",
    "fjögur": "fjórð",
    "fimm": "fimmt",
    "sex": "sjött",
    "sjö": "sjöund",
    "átta": "áttund",
    "níu": "níund",
    "tíu": "tíund",
    "ellefu": "elleft",
    "tólf": "tólft",
    "þrettán": "þrettánd",
    "fjórtán": "fjórtánd",
    "fimmtán": "fimmtánd",
    "sextán": "sextánd",
    "sautján": "sautjánd",
    "átján": "átjánd",
    "nítján": "nítjánd",
}

_ANNAR_TABLE = {
    "et": {
        "kk": {
            "nf": "annar",
            "þf": "annan",
            "þgf": "öðrum",
            "ef": "annars",
        },
        "kvk": {
            "nf": "önnur",
            "þf": "aðra",
            "þgf": "annarri",
            "ef": "annarrar",
        },
        "hk": {
            "nf": "annað",
            "þf": "annað",
            "þgf": "öðru",
            "ef": "annars",
        },
    },
    "ft": {
        "kk": {
            "nf": "aðrir",
            "þf": "aðra",
            "þgf": "öðrum",
            "ef": "annarra",
        },
        "kvk": {
            "nf": "aðrar",
            "þf": "aðrar",
            "þgf": "öðrum",
            "ef": "annarra",
        },
        "hk": {
            "nf": "önnur",
            "þf": "önnur",
            "þgf": "öðrum",
            "ef": "annarra",
        },
    },
}

_SUB_20_ORDINAL_SUFFIX = {
    "kk": {
        "nf": "i",
        "þf": "a",
        "þgf": "a",
        "ef": "a",
    },
    "kvk": {
        "nf": "a",
        "þf": "u",
        "þgf": "u",
        "ef": "u",
    },
    "hk": {
        "nf": "a",
        "þf": "a",
        "þgf": "a",
        "ef": "a",
    },
}

_TENS_NEUT_TO_ORDINAL = {
    "tuttugu": "tuttug",
    "þrjátíu": "þrítug",
    "fjörutíu": "fertug",
    "fimmtíu": "fimmtug",
    "sextíu": "sextug",
    "sjötíu": "sjötug",
    "áttatíu": "átttug",
    "níutíu": "nítug",
}

_LARGE_ORDINAL_SUFFIX = {
    "kk": {
        "nf": "asti",
        "þf": "asta",
        "þgf": "asta",
        "ef": "asta",
    },
    "kvk": {
        "nf": "asta",
        "þf": "ustu",
        "þgf": "ustu",
        "ef": "ustu",
    },
    "hk": {
        "nf": "asta",
        "þf": "asta",
        "þgf": "asta",
        "ef": "asta",
    },
}


def _num_to_ordinal(
    word: str, decl: str = "nf", gender: str = "kk", number: str = "et"
) -> str:
    """
    Helper function. Changes one part of a number (in written form) to ordinal form
    in correct declension, gender and number.
    Example:
        "hundruð" -> "hundraðasti" (default args)
        "tvö" -> "aðrar" (þf, kvk, ft)
    """
    if word == "núll":
        word = "núllt" + _SUB_20_ORDINAL_SUFFIX[gender][decl]

    elif word == "tvö":
        word = _ANNAR_TABLE[number][gender][decl]

    elif word in _SUB_20_NEUT_TO_ORDINAL:
        word = _SUB_20_NEUT_TO_ORDINAL.get(word, word)
        if number == "ft":
            word += "u"
        else:
            word += _SUB_20_ORDINAL_SUFFIX[gender][decl]

    elif word in _TENS_NEUT_TO_ORDINAL:
        word = _TENS_NEUT_TO_ORDINAL.get(word, word)
        if number == "ft":
            word += "ustu"
        else:
            word += _LARGE_ORDINAL_SUFFIX[gender][decl]

    elif word.startswith("hundr"):
        if number == "ft" or (gender == "kvk" and decl != "nf"):
            word = "hundruðustu"
        else:
            word = "hundrað" + _LARGE_ORDINAL_SUFFIX[gender][decl]

    elif word == "þúsund":
        if number == "ft" or (gender == "kvk" and decl != "nf"):
            word = "þúsundustu"
        else:
            word = "þúsund" + _LARGE_ORDINAL_SUFFIX[gender][decl]

    elif "jón" in word:
        if number == "ft":
            word = re.sub(r"(\S*jón)\S*", r"\1ustu", word)
        else:
            word = re.sub(
                r"(\S*jón)\S*", r"\1" + _LARGE_ORDINAL_SUFFIX[gender][decl], word
            )

    elif "jarð" in word:
        if number == "ft" or (gender == "kvk" and decl != "nf"):
            word = re.sub(r"(\S*)jarð\S*", r"\1jörðustu", word)
        else:
            word = re.sub(
                r"(\S*jarð)\S*", r"\1" + _LARGE_ORDINAL_SUFFIX[gender][decl], word
            )

    return word


def neutral_text_to_ordinal(
    s: str, decl: str = "nf", gender: str = "kk", number: str = "et"
) -> str:
    """
    Takes Icelandic text representation of number
    and returns it as an ordinal in specified declension (nf, þf, þgf, ef),
    gender (kk, kvk, hk) and number (et, ft).
    """
    if len(s) <= 0:
        return s

    ordinal: List[str] = s.split()

    # Change last word to ordinal
    ordinal[-1] = _num_to_ordinal(ordinal[-1], decl, gender, number)

    if len(ordinal) > 1:
        # Change e.g. "tvö þúsund og fyrsti" -> "tvö þúsundasti og fyrsti"
        if ordinal[-2] == "og" and len(ordinal) >= 3:
            # Check that last number in text isn't a large ordinal
            # e.g. "sextugustu", "hundraðasti" or "þúsundasta"
            if not re.search(r"[au]st[iau]$", ordinal[-1]):
                ordinal[-3] = _num_to_ordinal(ordinal[-3], decl, gender, number)

    ordinal_str: str = " ".join(ordinal)

    # Change e.g.
    # "eitt hundraðasti" -> "hundraðasti"
    # "ein milljónasta og fyrsta" -> "milljónasta og fyrsta"
    ordinal_str = re.sub(r"^(einn?|eitt) ((\S*)([au]st[iau]))", r"\2", ordinal_str)

    return ordinal_str


def number_to_ordinal(
    n: int, decl: str = "nf", gender: str = "kk", number: str = "et"
) -> str:
    """
    Takes number and returns it as an ordinal
    in specified declension (nf, þf, þgf, ef),
    gender (kk, kvk, hk) and number (et, ft).
    """
    return neutral_text_to_ordinal(number_to_neutral(n), decl, gender, number)


_DIGITS_TO_KK = {
    "0": "núll",
    "1": "einn",
    "2": "tveir",
    "3": "þrír",
    "4": "fjórir",
    "5": "fimm",
    "6": "sex",
    "7": "sjö",
    "8": "átta",
    "9": "níu",
}


def digits_to_text(digit_list: Iterable[Union[str,int]]) -> str:
    """
    Takes in a string of digits (or list of strings/ints)
    and returns as spoken text in Icelandic.
    Useful for phone numbers, social security numbers and such.
    Examples:
        "5885522" -> "fimm átta átta fimm fimm tveir tveir"
        ["234","1","9"] -> "tveir þrír fjórir einn níu"
    """
    digit_text: List[str] = []

    for d in digit_list:
        d = str(d).strip()
        if len(d) == 1 and d in _DIGITS_TO_KK:
            digit_text.append(_DIGITS_TO_KK[d])
        elif len(d) > 1:
            digit_str = digits_to_text(d)
            if len(digit_str):
                digit_text.append(digit_str)

    return " ".join(digit_text)


def country_desc(cc: str) -> str:
    """Generate Icelandic description of being in a particular country
    with correct preposition and case e.g. 'á Spáni', 'í Þýskalandi'."""
    cn = country_name_for_isocode(cc)
    if cn is None:
        return f"í landinu '{cc}'"
    prep = iceprep_for_cc(cc)
    return f"{prep} {nom2dat(cn)}"


def cap_first(s: str) -> str:
    """ Capitalize first character in a string. """
    return s[0].upper() + s[1:] if s else s


# This could be done at runtime using BÍN lookup, but this is
# faster, cleaner, and allows for reuse outside the codebase.
_TIMEUNIT_NOUNS = {
    "w": (["vika", "viku", "viku", "viku"], ["vikur", "vikur", "vikum", "vikna"]),
    "d": (["dagur", "dag", "degi", "dags"], ["dagar", "daga", "dögum", "daga"]),
    "h": (
        ["klukkustund", "klukkustund", "klukkustund", "klukkustundar"],
        ["klukkustundir", "klukkustundir", "klukkustundum", "klukkustunda"],
    ),
    "m": (
        ["mínúta", "mínútu", "mínútu", "mínútu"],
        ["mínútur", "mínútur", "mínútum", "mínútna"],
    ),
    "s": (
        ["sekúnda", "sekúndu", "sekúndu", "sekúndu"],
        ["sekúndur", "sekúndur", "sekúndum", "sekúndna"],
    ),
}

_TIMEUNIT_INTERVALS = (
    ("w", 604800),  # 60 * 60 * 24 * 7
    ("d", 86400),  # 60 * 60 * 24
    ("h", 3600),  # 60 * 60
    ("m", 60),
    ("s", 1),
)

_CASE_ABBR = ["nf", "þf", "þgf", "ef"]


def time_period_desc(seconds: int, case: str = "nf", omit_seconds: bool = True) -> str:
    """Generate Icelandic description of the length of a given time
    span, e.g. "4 dagar, 6 klukkustundir og 21 mínúta."""
    assert case in _CASE_ABBR
    cidx = _CASE_ABBR.index(case)
    # Round to nearest minute if omitting second precision
    seconds = ((seconds + 30) // 60) * 60 if omit_seconds else seconds

    # Break it down to weeks, days, hours, mins, secs.
    result = []
    for unit, count in _TIMEUNIT_INTERVALS:
        value = seconds // count
        if value:
            seconds -= value * count
            plidx = 1 if is_plural(value) else 0
            icename = _TIMEUNIT_NOUNS[unit][plidx][cidx]
            result.append("{0} {1}".format(value, icename))

    return natlang_seq(result)


_METER_NOUN = (
    ["metri", "metra", "metra", "metra"],
    ["metrar", "metra", "metrum", "metra"],
)


def distance_desc(
    km_dist: float, case: str = "nf", in_metres: float = 1.0, abbr: bool = False
) -> str:
    """Generate an Icelandic description of distance in km/m w. option to
    specify case, abbreviations, cutoff for returning desc in metres."""
    assert case in _CASE_ABBR
    cidx = _CASE_ABBR.index(case)

    # E.g. 7,3 kílómetrar
    if km_dist >= in_metres:
        rounded_km = round(km_dist, 1 if km_dist < 10 else 0)
        dist = iceformat_float(rounded_km)
        plidx = 1 if is_plural(rounded_km) else 0
        unit_long = "kíló" + _METER_NOUN[plidx][cidx]
        unit = "km" if abbr else unit_long
    # E.g. 940 metrar
    else:
        # Round to nearest 10
        def rnd(n):
            return ((n + 5) // 10) * 10

        dist = rnd(int(km_dist * 1000.0))
        plidx = 1 if is_plural(dist) else 0
        unit_long = _METER_NOUN[plidx][cidx]
        unit = "m" if abbr else unit_long

    return "{0} {1}".format(dist, unit)


_KRONA_NOUN = (
    ["króna", "krónu", "krónu", "krónu"],
    ["krónur", "krónur", "krónum", "króna"],
)


def krona_desc(amount: float, case: str = "nf") -> str:
    """Generate description of an amount in krónas, e.g.
    "213,5 krónur", "361 króna", "70,11 krónur", etc."""
    assert case in _CASE_ABBR
    cidx = _CASE_ABBR.index(case)
    plidx = 1 if is_plural(amount) else 0
    return "{0} {1}".format(iceformat_float(amount), _KRONA_NOUN[plidx][cidx])


def strip_trailing_zeros(num_str: str) -> str:
    """Strip trailing decimal zeros from an Icelandic-style
    float num string, e.g. "17,0" -> "17"."""
    if "," in num_str:
        return num_str.rstrip("0").rstrip(",")
    return num_str


def iceformat_float(
    fp_num: float, decimal_places: int = 2, strip_zeros: bool = True
) -> str:
    """ Convert number to Icelandic decimal format string. """
    with changedlocale(category="LC_NUMERIC"):
        fmt = "%.{0}f".format(decimal_places)
        res = locale.format_string(fmt, float(fp_num), grouping=True).replace(" ", ".")
        return strip_trailing_zeros(res) if strip_zeros else res


def icequote(s: str) -> str:
    """ Return string surrounded by Icelandic-style quotation marks. """
    return "„{0}“".format(s.strip())


def gen_answer(a: str) -> AnswerTuple:
    """ Convenience function for query modules: response, answer, voice answer """
    return dict(answer=a), a, a


def query_json_api(url: str, headers: Optional[Dict] = None) -> Optional[Dict]:
    """Request the URL, expecting a JSON response which is
    parsed and returned as a Python data structure."""

    # Send request
    try:
        r = requests.get(url, headers=headers)
    except Exception as e:
        logging.warning(str(e))
        return None

    # Verify that status is OK
    if r.status_code != 200:
        logging.warning("Received status {0} from API server".format(r.status_code))
        return None

    # Parse json API response
    try:
        res = json.loads(r.text)
        return res
    except Exception as e:
        logging.warning("Error parsing JSON API response: {0}".format(e))
    return None


def query_xml_api(url: str):
    """Request the URL, expecting an XML response which is
    parsed and returned as an XML document object."""

    # Send request
    try:
        r = requests.get(url)
    except Exception as e:
        logging.warning(str(e))
        return None

    # Verify that status is OK
    if r.status_code != 200:
        logging.warning(
            "Received status {0} from remote URL {1}".format(r.status_code, url)
        )
        return None

    # Parse XML response text
    try:
        xmldoc = minidom.parseString(r.text)
        return xmldoc
    except Exception as e:
        logging.warning("Error parsing XML response from {0}: {1}".format(url, e))


_MAPS_API_COORDS_URL = (
    "https://maps.googleapis.com/maps/api/geocode/json"
    "?latlng={0},{1}&key={2}&language=is&region=is"
)


def query_geocode_api_coords(lat: float, lon: float) -> Optional[Dict]:
    """ Look up coordinates in Google's geocode API. """
    # Load API key
    key = read_api_key("GoogleServerKey")
    if not key:
        # No key, can't query Google location API
        logging.warning("No API key for coordinates lookup")
        return None

    # Send API request
    res = query_json_api(_MAPS_API_COORDS_URL.format(lat, lon, key))

    return res


_MAPS_API_ADDR_URL = (
    "https://maps.googleapis.com/maps/api/geocode/json"
    "?address={0}&key={1}&language=is&region=is"
)


def query_geocode_api_addr(addr: str) -> Optional[Dict]:
    """ Look up address in Google's geocode API. """
    # Load API key
    key = read_api_key("GoogleServerKey")
    if not key:
        # No key, can't query the API
        logging.warning("No API key for address lookup")
        return None

    # Send API request
    url = _MAPS_API_ADDR_URL.format(addr, key)
    res = query_json_api(url)

    return res


_MAPS_API_TRAVELTIME_URL = (
    "https://maps.googleapis.com/maps/api/distancematrix/json"
    "?units=metric&origins={0}&destinations={1}&mode={2}&key={3}&language=is&region=is"
)

_TRAVEL_MODES = frozenset(("walking", "driving", "bicycling", "transit"))


def query_traveltime_api(
    startloc: Union[str, LatLonTuple],
    endloc: Union[str, LatLonTuple],
    mode: str = "walking",
) -> Optional[Dict]:
    """Look up travel time between two places, given a particular mode
    of transportation, i.e. one of the modes in _TRAVEL_MODES.
    The location arguments can be names, to be resolved by the API, or
    a tuple of coordinates, e.g. (64.156742, -21.949426)
    Uses Google Maps' Distance Matrix API. For more info, see:
    https://developers.google.com/maps/documentation/distance-matrix/intro
    """
    assert mode in _TRAVEL_MODES

    # Load API key
    key = read_api_key("GoogleServerKey")
    if not key:
        # No key, can't query the API
        logging.warning("No API key for travel time lookup")
        return None

    # Format query string args
    p1 = "{0},{1}".format(*startloc) if isinstance(startloc, tuple) else startloc
    p2 = "{0},{1}".format(*endloc) if isinstance(endloc, tuple) else endloc

    # Send API request
    url = _MAPS_API_TRAVELTIME_URL.format(p1, p2, mode, key)
    res = query_json_api(url)

    return res


_PLACES_API_URL = (
    "https://maps.googleapis.com/maps/api/place/findplacefromtext/json?{0}"
)

_PLACES_LOCBIAS_RADIUS = 5000  # Metres


def query_places_api(
    placename: str,
    userloc: Optional[LatLonTuple] = None,
    radius: float = _PLACES_LOCBIAS_RADIUS,
    fields: Optional[str] = None,
) -> Optional[Dict]:
    """Look up a placename in Google's Places API. For details, see:
    https://developers.google.com/places/web-service/search"""

    if not fields:
        # Default fields requested from API
        fields = "place_id,opening_hours,geometry/location,formatted_address"

    # Load API key
    key = read_api_key("GoogleServerKey")
    if not key:
        # No key, can't query the API
        logging.warning("No API key for Google Places lookup")
        return None

    # Generate query string
    qdict = {
        "input": placename,
        "inputtype": "textquery",
        "fields": fields,
        "key": key,
        "language": "is",
        "region": "is",
    }
    if userloc:
        qdict["locationbias"] = "circle:{0}@{1},{2}".format(
            radius, userloc[0], userloc[1]
        )
    qstr = urlencode(qdict)

    # Send API request
    url = _PLACES_API_URL.format(qstr)
    res = query_json_api(url)

    return res


_PLACEDETAILS_API_URL = "https://maps.googleapis.com/maps/api/place/details/json?{0}"


@lru_cache(maxsize=32)
def query_place_details(place_id: str, fields: Optional[str] = None) -> Optional[Dict]:
    """Look up place details by ID in Google's Place Details API. If "fields"
    parameter is omitted, *all* fields are returned. For details, see
    https://developers.google.com/places/web-service/details"""

    # Load API key
    key = read_api_key("GoogleServerKey")
    if not key:
        # No key, can't query the API
        logging.warning("No API key for Google Place Details lookup")
        return None

    # Generate query string
    qdict = {"place_id": place_id, "key": key, "language": "is"}
    if fields:
        qdict["fields"] = fields
    qstr = urlencode(qdict)

    # Send API request
    url = _PLACEDETAILS_API_URL.format(qstr)
    res = query_json_api(url)

    return res


_TZW: Optional[tzwhere.tzwhere] = None


def _tzwhere_singleton() -> tzwhere.tzwhere:
    """ Lazy-load location/timezone database. """
    global _TZW
    if not _TZW:
        _TZW = tzwhere.tzwhere(forceTZ=True)
    return _TZW


def timezone4loc(
    loc: Optional[LatLonTuple], fallback: Optional[str] = None
) -> Optional[str]:
    """Returns timezone string given a tuple of coordinates.
    Fallback argument should be a 2-char ISO 3166 country code."""
    if loc is not None:
        return _tzwhere_singleton().tzNameAt(loc[0], loc[1], forceTZ=True)
    if fallback and fallback in country_timezones:
        return country_timezones[fallback][0]
    return None


@lru_cache(maxsize=32)
def read_jsfile(filename: str) -> str:
    """ Read and return a minified JavaScript (.js) file """
    # The file is read from the directory 'js' within the directory
    # containing this __init__.py file
    from rjsmin import jsmin  # type: ignore

    basepath, _ = os.path.split(os.path.realpath(__file__))
    fpath = os.path.join(basepath, "js", filename)
    with open(fpath, mode="r") as file:
        return cast(str, jsmin(file.read()))
