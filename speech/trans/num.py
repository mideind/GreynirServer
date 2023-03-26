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


    This file contains various utility functions that convert
    numbers to Icelandic text.

"""

from typing import Mapping, List, Optional, Tuple, Match, Callable, Union
from typing_extensions import Literal
import re


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

_DeclensionMapping = Mapping[str, Mapping[str, Mapping[str, str]]]
_NUM_NEUT_TO_DECL: _DeclensionMapping = {
    "eitt": {
        "kk": {"nf": "einn", "þf": "einn", "þgf": "einum", "ef": "eins"},
        "kvk": {"nf": "ein", "þf": "eina", "þgf": "einni", "ef": "einnar"},
        "hk": {"nf": "eitt", "þf": "eitt", "þgf": "einu", "ef": "eins"},
    },
    "tvö": {
        "kk": {"nf": "tveir", "þf": "tvo", "þgf": "tveimur", "ef": "tveggja"},
        "kvk": {"nf": "tvær", "þf": "tvær", "þgf": "tveimur", "ef": "tveggja"},
        "hk": {"nf": "tvö", "þf": "tvö", "þgf": "tveimur", "ef": "tveggja"},
    },
    "þrjú": {
        "kk": {"nf": "þrír", "þf": "þrjá", "þgf": "þremur", "ef": "þriggja"},
        "kvk": {"nf": "þrjár", "þf": "þrjár", "þgf": "þremur", "ef": "þriggja"},
        "hk": {"nf": "þrjú", "þf": "þrjú", "þgf": "þremur", "ef": "þriggja"},
    },
    "fjögur": {
        "kk": {"nf": "fjórir", "þf": "fjóra", "þgf": "fjórum", "ef": "fjögurra"},
        "kvk": {"nf": "fjórar", "þf": "fjórar", "þgf": "fjórum", "ef": "fjögurra"},
        "hk": {"nf": "fjögur", "þf": "fjögur", "þgf": "fjórum", "ef": "fjögurra"},
    },
}

_LARGE_NUMBERS: Tuple[Tuple[int, str, str], ...] = (
    (10 ** 48, "oktilljón", "kvk"),
    (10 ** 42, "septilljón", "kvk"),
    (10 ** 36, "sextilljón", "kvk"),
    (10 ** 30, "kvintilljón", "kvk"),
    (10 ** 27, "kvaðrilljarð", "kk"),
    (10 ** 24, "kvaðrilljón", "kvk"),
    (10 ** 21, "trilljarð", "kk"),
    (10 ** 18, "trilljón", "kvk"),
    (10 ** 15, "billjarð", "kk"),
    (10 ** 12, "billjón", "kvk"),
    (10 ** 9, "milljarð", "kk"),
    (10 ** 6, "milljón", "kvk"),
)


def number_to_neutral(n: int = 0, *, one_hundred: bool = False) -> str:
    """
    Write integer out as neutral gender text in Icelandic.
    Argument one_hundred specifies whether to add "eitt" before "hundrað".
    Example:
        number_to_neutral(1337) -> "eitt þúsund þrjú hundruð þrjátíu og sjö"
    """
    n = int(n)

    if n == 0:
        return "núll"

    text: List[str] = []
    # Make n positive while creating written number string
    minus: str = ""
    if n < 0:
        minus = "mínus "
        n = -n

    MILLION = 1000000
    THOUSAND = 1000

    # Helper function to check whether a number should be prefixed with "og"
    should_prepend_og: Callable[[int], bool] = (
        lambda x: x > 0 and int(str(x).rstrip("0")) < 20
    )

    # Very large numbers
    while n >= MILLION:

        large_num, isl_num, gender = 1, "", ""
        for large_num, isl_num, gender in _LARGE_NUMBERS:
            if large_num <= n:
                break

        large_count, n = divmod(n, large_num)

        text.extend(number_to_neutral(large_count, one_hundred=True).split())

        last = text[-1]
        if gender == "kk":
            # e.g. "milljarður" if last number ends with "eitt/einn" else "milljarðar"
            isl_num += "ur" if last == "eitt" else "ar"
        elif gender == "kvk":
            # e.g. "milljón" if last number ends with "eitt/ein" else "milljónir"
            if last != "eitt":
                isl_num += "ir"

        if last in _NUM_NEUT_TO_DECL:
            # Change "eitt" to "einn/ein"
            text[-1] = _NUM_NEUT_TO_DECL[last][gender]["nf"]

        text.append(isl_num)
        if should_prepend_og(n):
            text.append("og")

    if THOUSAND <= n < MILLION:
        thousands, n = divmod(n, THOUSAND)

        if thousands > 1:
            text.extend(number_to_neutral(thousands, one_hundred=True).split())
        elif thousands == 1:
            text.append("eitt")

        # Singular/Plural form of "þúsund" is the same
        text.append("þúsund")
        # Don't prepend 'og' in front of 110, 120, ..., 190
        if should_prepend_og(n) and n not in range(110, 200, 10):
            text.append("og")

    if 100 <= n < THOUSAND:
        hundreds, n = divmod(n, 100)

        if hundreds > 1:
            text.extend(number_to_neutral(hundreds).split())
            # Note: don't need to fix singular here as e.g.
            # 2100 gets interpreted as "tvö þúsund og eitt hundrað"
            # instead of "tuttugu og eitt hundrað"
            text.append("hundruð")
        elif hundreds == 1:
            if text or one_hundred:
                # Add "eitt" before "hundrað"
                # if not first number in text
                # or if one_hundred is True
                text.append("eitt")
            text.append("hundrað")

        if should_prepend_og(n):
            text.append("og")

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

    # Fix e.g. "milljónir milljarðar" -> "milljónir milljarða"
    number_string: str = minus + re.sub(
        r"(\S*(jónir|jarð[au]r?)) (\S*(jarð|jón))[ia]r", r"\1 \3a", " ".join(text)
    )

    return number_string


CaseType = Literal["nf", "þf", "þgf", "ef"]
GenderType = Literal["kk", "kvk", "hk"]
NumberType = Literal["et", "ft"]


def number_to_text(
    n: Union[int, str],
    *,
    case: str = "nf",
    gender: str = "hk",
    one_hundred: bool = False
) -> str:
    """
    Convert an integer into written Icelandic text in given case/gender.
    Argument one_hundred specifies whether to add "eitt" before "hundrað".
    Example:
        302 -> "þrjú hundruð og tvær" (gender="kvk")
        501 -> "fimm hundruð og einn" (gender="kk")
    """
    if isinstance(n, str):
        n = n.replace(".", "")
    n = int(n)
    nums = number_to_neutral(n, one_hundred=one_hundred).split()

    last = nums[-1]
    if last in _NUM_NEUT_TO_DECL:
        nums[-1] = _NUM_NEUT_TO_DECL[last][gender][case]

    return " ".join(nums)


def numbers_to_text(
    s: str,
    *,
    regex: str = r"((?<!\d)-)?\b\d+\b",
    # ^ matches "15" & "-15", but matches "1-5" as "1" and "5"
    case: str = "nf",
    gender: str = "hk",
    one_hundred: bool = False
) -> str:
    """
    Converts numbers in string to Icelandic text.
    (Can also be supplied with custom regex to match certain numbers)
    Extra arguments specifies case/gender of number
    and whether to add "eitt" before "hundrað".
    """

    def convert(m: Match[str]) -> str:
        match = m.group(0)
        n = int(match)
        return number_to_text(n, case=case, gender=gender, one_hundred=one_hundred)

    return re.sub(regex, convert, s)


def float_to_text(
    f: Union[float, str],
    *,
    case: str = "nf",
    gender: str = "hk",
    comma_null: bool = False,
    one_hundred: bool = False
) -> str:
    """
    Convert a float into written Icelandic text in given case/gender.
    Argument one_hundred specifies whether to add "eitt" before "hundrað".
    Example:
        -0.02 -> "mínus núll komma núll tveir" (gender="kk")
    """
    if isinstance(f, str):
        if "," in f and "." in f:
            # Remove Icelandic thousand markers
            f = f.replace(".", "")
        # Change Icelandic comma to period
        f = f.replace(",", ".")

    f = float(f)
    out_str: str = ""
    # To prevent edge cases like -0.2 being translated to
    # "núll komma tvö" instead of "mínus núll komma tvö"
    if f < 0:
        out_str = "mínus "
        f = -f

    first, second = str(f).split(".")

    # Number before decimal point
    out_str += number_to_text(
        int(first), case=case, gender=gender, one_hundred=one_hundred
    )

    if not comma_null and second == "0":
        # Skip "komma núll" if comma_null is False
        return out_str

    out_str += " komma "

    if len(second.lstrip("0")) <= 2:
        # e.g. 2,41 -> "tveimur komma fjörutíu og einum"
        while second and second[0] == "0":
            # e.g. 1,03 -> "einni komma núll tveimur"
            # or 2,003 -> "tveimur komma núll núll þremur"
            out_str += "núll "
            second = second[1:]
        if second:
            out_str += number_to_text(int(second), case=case, gender=gender)
    else:
        if len(second) > 2:
            # Only allow declension for two digits at most after decimal point
            # Otherwise fall back to "nf"
            case = "nf"
        # Numbers after decimal point
        for digit in second:
            if digit == "0":
                out_str += "núll "
            else:
                digit_str = _SUB_20_NEUTRAL.get(int(digit), "")
                if digit_str in _NUM_NEUT_TO_DECL:
                    out_str += _NUM_NEUT_TO_DECL[digit_str][gender][case]
                else:
                    out_str += digit_str
                out_str += " "

    return out_str.rstrip()


def floats_to_text(
    s: str,
    *,
    regex: str = r"((?<!\d)-)?\b(\d{1,3}\.)*\d+(,\d+)?\b",
    case: str = "nf",
    gender: str = "hk",
    comma_null: bool = False,
    one_hundred: bool = False
) -> str:
    """
    Converts floats of the form '14.022,14', '0,42' (with Icelandic comma)
    (or matching custom regex if provided)
    in string to Icelandic text.
    Extra arguments specifies case/gender of float,
    whether to read after decimal point if fractional part is zero
    and whether to add "eitt" before "hundrað".
    """

    def convert(m: Match[str]) -> str:
        match = m.group(0)
        n = float(match.replace(".", "").replace(",", "."))
        return float_to_text(
            n, case=case, gender=gender, comma_null=comma_null, one_hundred=one_hundred
        )

    return re.sub(regex, convert, s)


def year_to_text(year: Union[int, str]) -> str:
    """
    Write year as text in Icelandic.
    Negative years automatically append "fyrir Krist" to the text.
    """
    year = int(year)
    suffix: str = ""
    text: List[str] = []

    if year < 0:
        suffix = " fyrir Krist"
        year = -year

    # People say e.g. "nítján hundruð þrjátíu og tvö"
    # instead of "eitt þúsund níu hundruð þrjátíu og tvö"
    # for years between 1100-2000
    if 1100 <= year < 2000:
        hundreds, digits = divmod(year, 100)

        text.append(_SUB_20_NEUTRAL[hundreds])
        text.append("hundruð")
        if digits > 0:
            if digits in _SUB_20_NEUTRAL or digits in _TENS_NEUTRAL:
                text.append("og")
            text.append(number_to_neutral(digits))

    # Other years are spoken like regular numbers
    else:
        text.append(number_to_neutral(year))

    return " ".join(text) + suffix


def years_to_text(
    s: str, *, regex: Optional[str] = None, allow_three_digits: bool = False
) -> str:
    """
    Converts numbers in string matching the regex
    to text as spoken Icelandic year.
    """

    if regex is None:
        if allow_three_digits:
            # Use a regex that matches 3-4 digit numbers but does a lookahead
            # to not match numbers that are followed by a decimal point and a digit
            regex = r"\b\d{3,4}(?![\.,]\d)\b"
        else:
            regex = r"\b\d{4}(?![\.,]\d)\b"

    def convert(m: Match[str]) -> str:
        match = m.group(0)
        n = int(match)
        # Don't interpret numbers lower than 850 or higher than 2200 as years
        return year_to_text(n) if 850 < n < 2200 else match

    return re.sub(regex, convert, s)


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

_ANNAR_TABLE: _DeclensionMapping = {
    "et": {
        "kk": {"nf": "annar", "þf": "annan", "þgf": "öðrum", "ef": "annars",},
        "kvk": {"nf": "önnur", "þf": "aðra", "þgf": "annarri", "ef": "annarrar",},
        "hk": {"nf": "annað", "þf": "annað", "þgf": "öðru", "ef": "annars",},
    },
    "ft": {
        "kk": {"nf": "aðrir", "þf": "aðra", "þgf": "öðrum", "ef": "annarra",},
        "kvk": {"nf": "aðrar", "þf": "aðrar", "þgf": "öðrum", "ef": "annarra",},
        "hk": {"nf": "önnur", "þf": "önnur", "þgf": "öðrum", "ef": "annarra",},
    },
}

_SuffixMapping = Mapping[str, Mapping[str, str]]
_SUB_20_ORDINAL_SUFFIX: _SuffixMapping = {
    "kk": {"nf": "i", "þf": "a", "þgf": "a", "ef": "a",},
    "kvk": {"nf": "a", "þf": "u", "þgf": "u", "ef": "u",},
    "hk": {"nf": "a", "þf": "a", "þgf": "a", "ef": "a",},
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

_LARGE_ORDINAL_SUFFIX: _SuffixMapping = {
    "kk": {"nf": "asti", "þf": "asta", "þgf": "asta", "ef": "asta",},
    "kvk": {"nf": "asta", "þf": "ustu", "þgf": "ustu", "ef": "ustu",},
    "hk": {"nf": "asta", "þf": "asta", "þgf": "asta", "ef": "asta",},
}


def _num_to_ordinal(
    word: str,
    case: str = "nf",
    gender: str = "kk",
    number: str = "et",
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
    s: str,
    *,
    case: str = "nf",
    gender: str = "kk",
    number: str = "et"
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
    n: Union[int, str],
    *,
    case: str = "nf",
    gender: str = "kk",
    number: str = "et"
) -> str:
    """
    Takes number and returns it as an ordinal
    in specified case (nf, þf, þgf, ef),
    gender (kk, kvk, hk) and number (et, ft).
    """
    if isinstance(n, str):
        n = int(n.rstrip("."))
    return neutral_text_to_ordinal(
        number_to_neutral(n), case=case, gender=gender, number=number
    )


def numbers_to_ordinal(
    s: str,
    *,
    regex: Optional[str] = None,
    case: str = "nf",
    gender: str = "kk",
    number: str = "et"
) -> str:
    """
    Converts ordinals of the form '2.', '101.'
    (or matching regex if provided)
    in string to Icelandic text.
    Extra arguments specify case, gender and number.
    """

    if regex is None:
        # Match ordinals of the form '2.', '101.'
        regex = r"((?<!\d\.)-)?\b\d+\.(?=[ ,)-])"

    def convert(m: Match[str]) -> str:
        match = m.group(0)
        n = int(match.strip("."))
        return number_to_ordinal(n, case=case, gender=gender, number=number)

    return re.sub(regex, convert, s)


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


def digits_to_text(s: str, *, regex: str = r"\b\d+") -> str:
    """
    Converts digits in string to Icelandic text.
    Useful for phone numbers, social security numbers and such.
    Can also supply custom regex to match only certain numbers.
    Examples:
        "5885522" -> "fimm átta átta fimm fimm tveir tveir"
        "Síminn minn er 581-2345" -> "Síminn minn er fimm átta einn-tveir þrír fjórir fimm"
    """

    def convert(m: Match[str]) -> str:
        match = m.group(0).replace("-", "")
        return "".join(
            _DIGITS_TO_KK[letter] + " " if letter.isdecimal() else letter
            for letter in match
        ).rstrip()

    return re.sub(regex, convert, s)


_ROMAN_NUMERALS: Mapping[str, int] = {
    "I": 1,
    "V": 5,
    "X": 10,
    "L": 50,
    "C": 100,
    "D": 500,
    "M": 1000,
}


def _roman_numeral_to_int(n: str) -> int:
    """
    Helper function, changes a correct roman numeral to an integer.
    Source: https://stackoverflow.com/a/52426119
    """
    nums = [_ROMAN_NUMERALS[i] for i in n.upper() if i in _ROMAN_NUMERALS]
    return sum(
        val if val >= nums[min(i + 1, len(n) - 1)] else -val
        for i, val in enumerate(nums)
    )


def roman_numeral_to_ordinal(
    n: str,
    *,
    case: str = "nf",
    gender: str = "kk",
    number: str = "et"
):
    """
    Change a roman numeral into a written Icelandic ordinal.
    Example:
        "III" -> "þriðji"
        "MMXXII" -> "tvö þúsund tuttugasti og annar"
    """
    return number_to_ordinal(
        _roman_numeral_to_int(n), case=case, gender=gender, number=number,
    )
