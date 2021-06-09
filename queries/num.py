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


    This file contains various utility functions that convert
    numbers to Icelandic text.

"""

from typing import Mapping, List, Tuple, Union, Iterable
import re


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


_SUB_20_NEUTRAL: Mapping[int, str] = {
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

_TENS_NEUTRAL: Mapping[int, str] = {
    20: "tuttugu",
    30: "þrjátíu",
    40: "fjörutíu",
    50: "fimmtíu",
    60: "sextíu",
    70: "sjötíu",
    80: "áttatíu",
    90: "níutíu",
}

_NUM_NEUT_TO_KK: Mapping[str, str] = {
    "eitt": "einn",
    "tvö": "tveir",
    "þrjú": "þrír",
    "fjögur": "fjórir",
}

_NUM_NEUT_TO_KVK: Mapping[str, str] = {
    "eitt": "ein",
    "tvö": "tvær",
    "þrjú": "þrjár",
    "fjögur": "fjórar",
}

_LARGE_NUMBERS: Tuple[Tuple[int, str], ...] = (
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
    Write integer out as neutral gender text in Icelandic.
    Example:
        1337 -> "eitt þúsund þrjú hundruð þrjátíu og sjö"
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

    if gender == "hk":
        return num_str

    nums = num_str.split()

    if gender == "kk" and nums[-1] in _NUM_NEUT_TO_KK:
        nums[-1] = _NUM_NEUT_TO_KK[nums[-1]]

    elif gender == "kvk" and nums[-1] in _NUM_NEUT_TO_KVK:
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
                out_str += _NUM_NEUT_TO_KK[digit_str]
            elif gender == "kvk" and digit_str in _NUM_NEUT_TO_KVK:
                out_str += _NUM_NEUT_TO_KVK[digit_str]
            else:
                out_str += digit_str
            out_str += " "

    return out_str.rstrip()


def year_to_text(year: int, *, after_christ: bool = False) -> str:
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


DeclensionMapping = Mapping[str, Mapping[str, Mapping[str, str]]]
_FYRSTUR_STRONG_DECL: DeclensionMapping = {
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

_SUB_20_NEUT_TO_ORDINAL: Mapping[str, str] = {
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

_ANNAR_TABLE: DeclensionMapping = {
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

SuffixMapping = Mapping[str, Mapping[str, str]]
_SUB_20_ORDINAL_SUFFIX: SuffixMapping = {
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

_TENS_NEUT_TO_ORDINAL: Mapping[str, str] = {
    "tuttugu": "tuttug",
    "þrjátíu": "þrítug",
    "fjörutíu": "fertug",
    "fimmtíu": "fimmtug",
    "sextíu": "sextug",
    "sjötíu": "sjötug",
    "áttatíu": "átttug",
    "níutíu": "nítug",
}

_LARGE_ORDINAL_SUFFIX: SuffixMapping = {
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
    word: str, case: str = "nf", gender: str = "kk", number: str = "et"
) -> str:
    """
    Helper function. Changes one part of a number (in written form) to ordinal form
    in correct case, gender and number.
    Example:
        "hundruð" -> "hundraðasti" (default args)
        "tvö" -> "aðrar" (þf, kvk, ft)
    """
    if word == "núll":
        word = "núllt" + _SUB_20_ORDINAL_SUFFIX[gender][case]

    elif word == "tvö":
        word = _ANNAR_TABLE[number][gender][case]

    elif word in _SUB_20_NEUT_TO_ORDINAL:
        word = _SUB_20_NEUT_TO_ORDINAL.get(word, word)
        if number == "ft":
            word += "u"
        else:
            word += _SUB_20_ORDINAL_SUFFIX[gender][case]

    elif word in _TENS_NEUT_TO_ORDINAL:
        word = _TENS_NEUT_TO_ORDINAL.get(word, word)
        if number == "ft":
            word += "ustu"
        else:
            word += _LARGE_ORDINAL_SUFFIX[gender][case]

    elif word.startswith("hundr"):
        if number == "ft" or (gender == "kvk" and case != "nf"):
            word = "hundruðustu"
        else:
            word = "hundrað" + _LARGE_ORDINAL_SUFFIX[gender][case]

    elif word == "þúsund":
        if number == "ft" or (gender == "kvk" and case != "nf"):
            word = "þúsundustu"
        else:
            word = "þúsund" + _LARGE_ORDINAL_SUFFIX[gender][case]

    elif "jón" in word:
        if number == "ft":
            word = re.sub(r"(\S*jón)\S*", r"\1ustu", word)
        else:
            word = re.sub(
                r"(\S*jón)\S*", r"\1" + _LARGE_ORDINAL_SUFFIX[gender][case], word
            )

    elif "jarð" in word:
        if number == "ft" or (gender == "kvk" and case != "nf"):
            word = re.sub(r"(\S*)jarð\S*", r"\1jörðustu", word)
        else:
            word = re.sub(
                r"(\S*jarð)\S*", r"\1" + _LARGE_ORDINAL_SUFFIX[gender][case], word
            )

    return word


def neutral_text_to_ordinal(
    s: str, case: str = "nf", gender: str = "kk", number: str = "et"
) -> str:
    """
    Takes Icelandic text representation of number
    and returns it as an ordinal in specified case (nf, þf, þgf, ef),
    gender (kk, kvk, hk) and number (et, ft).
    """
    if len(s) == 0:
        return s

    ordinal: List[str] = s.split()

    # Change last word to ordinal
    ordinal[-1] = _num_to_ordinal(ordinal[-1], case, gender, number)

    if len(ordinal) > 1:
        # Change e.g. "tvö þúsund og fyrsti" -> "tvö þúsundasti og fyrsti"
        if ordinal[-2] == "og" and len(ordinal) >= 3:
            # Check that last number in text isn't a large ordinal
            # e.g. "sextugustu", "hundraðasti" or "þúsundasta"
            if not re.search(r"[au]st[iau]$", ordinal[-1]):
                ordinal[-3] = _num_to_ordinal(ordinal[-3], case, gender, number)

    ordinal_str: str = " ".join(ordinal)

    # Change e.g.
    # "eitt hundraðasti" -> "hundraðasti"
    # "ein milljónasta og fyrsta" -> "milljónasta og fyrsta"
    ordinal_str = re.sub(r"^(einn?|eitt) ((\S*)([au]st[iau]))", r"\2", ordinal_str)

    return ordinal_str


def number_to_ordinal(
    n: int, case: str = "nf", gender: str = "kk", number: str = "et"
) -> str:
    """
    Takes number and returns it as an ordinal
    in specified case (nf, þf, þgf, ef),
    gender (kk, kvk, hk) and number (et, ft).
    """
    return neutral_text_to_ordinal(number_to_neutral(n), case, gender, number)


_DIGITS_TO_KK: Mapping[str, str] = {
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


def digits_to_text(digit_list: Iterable[Union[str, int]]) -> str:
    """
    Takes in a string of digits (or list of strings/ints)
    and returns as spoken text in Icelandic.
    Useful for phone numbers, social security numbers and such.
    Examples:
        "5885522" -> "fimm átta átta fimm fimm tveir tveir"
        ["234",1,"9"] -> "tveir þrír fjórir einn níu"
    """
    digit_text: List[str] = []

    for d in digit_list:
        d = str(d).strip()
        if not d or not d.isdecimal():
            continue
        elif d in _DIGITS_TO_KK:
            digit_text.append(_DIGITS_TO_KK[d])
        else:
            digit_str = digits_to_text(d)
            if len(digit_str):
                digit_text.append(digit_str)

    return " ".join(digit_text)
