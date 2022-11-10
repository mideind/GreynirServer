#!/usr/bin/env python
"""

    Greynir: Natural language processing for Icelandic

    Copyright (C) 2022 Miðeind ehf.

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


    This file contains text normalization functionality
    specifically intended for Icelandic speech synthesis engines.

"""

from typing import (
    Any,
    Callable,
    Optional,
    Union,
    ChainMap as ChainMapType,
)

import re
from collections import ChainMap

from speech.norm.num import (
    digits_to_text,
    float_to_text,
    floats_to_text,
    number_to_text,
    numbers_to_text,
    number_to_ordinal,
    numbers_to_ordinal,
    year_to_text,
    years_to_text,
)

# Each voice module in voices/ can define the NORM_HANDLERS variable
# as its custom mapping of normalization functions
NORM_MAP_VAR = "NORM_HANDLERS"


def gssml(data: Any = None, *, type: str, **kwargs: Union[str, int, float]) -> str:
    """
    Utility function, surrounds data with Greynir-specific
    voice normalizing tags.
    E.g. '<greynir ...>{data}</greynir>'
      or '<greynir ... />' if data is None.

    Type specifies the type of handling needed when the tags are parsed.
    The kwargs are then passed to the handler functions as appropriate.

    The greynir tags can be handled/normalized
    in different ways depending on the voice engine used.

    Example:
        gssml(43, type="number", gender="kk") -> '<greynir type="number" gender="kk">43</greynir>'
    """
    assert type and isinstance(
        type, str
    ), f"type keyword arg must be non-empty string in function gssml; data: {data}"
    return (
        f'<greynir type="{type}"'
        + "".join(f' {k}="{v}"' for k, v in kwargs.items())
        + (f">{data}</greynir>" if data is not None else f" />")
    )


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
    "w": "tvöfalt vaff",
    "x": "ex",
    "y": "ufsilon",
    "ý": "ufsilon í",
    "þ": "þoddn",
    "æ": "æ",
    "ö": "ö",
    "z": "seta",
}


def spell_out(s: str) -> str:
    """Spell out a sequence of characters, e.g. "LTB" -> "ell té bé".
    Useful for controlling speech synthesis of serial numbers, etc."""
    if not s:
        return ""
    t = [_CHAR_PRONUNCIATION.get(c.lower(), c) if c != " " else "" for c in s]
    return " ".join(t).replace("  ", " ").strip()


def _time_handler(t: str) -> str:
    """Handles time of day data specified as 'HH:MM'."""
    # TODO: Say e.g. "hálf fjögur" instead of "fimmtán þrjátíu"? korter í/yfir
    # TODO: Say "tuttugu mínútur yfir þrjú" instead of "fimmtán tuttugu"
    ts = t.split(":")
    return " ".join(number_to_text(x, gender="hk") for x in ts)


_MONTH_ABBREVS = (
    "jan",
    "feb",
    "mar",
    "apr",
    "maí",
    "jún",
    "júl",
    "ágú",
    "sep",
    "okt",
    "nóv",
    "des",
)
_MONTH_NAMES = (
    "janúar",
    "febrúar",
    "mars",
    "apríl",
    "maí",
    "júní",
    "júlí",
    "ágúst",
    "september",
    "október",
    "nóvember",
    "desember",
)
_DATE_REGEXES = (
    # Matches e.g. "1986-03-07"
    re.compile(r"(?P<year>\d{1,4})-(?P<month>\d{1,2})-(?P<day>\d{1,2})"),
    # Matches e.g. "1/4/2001"
    re.compile(r"(?P<day>\d{1,2})/(?P<month>\d{1,2})/(?P<year>\d{1,4})"),
    # Matches e.g. "25. janúar 1999" or "25 des."
    re.compile(
        r"(?P<day>\d{1,2})\.? ?"
        r"(?P<month>(jan(úar|\.)?|feb(rúar|\.)?|mar(s|\.)?|"
        r"apr(íl|\.)?|maí\.?|jún(í|\.)?|"
        r"júl(í|\.)?|ágú(st|\.)?|sep(tember|\.)?|"
        r"okt(óber|\.)?|nóv(ember|\.)?|des(ember|\.)?))"  # 'month' capture group ends
        r"( (?P<year>\d{1,4}))?",  # Optional
        flags=re.IGNORECASE,
    ),
)


def _date_handler(d: str, case: str = "nf") -> str:
    """
    Handles dates specified in either
        'YYYY-MM-DD' (ISO 8601 format),
        'DD/MM/YYYY' or
        'DD. month [YYYY]'
    Note: doesn't check for incorrect numbers,
          as that should be handled by caller.
    """
    # Get first fullmatch from date regexes
    m = next(
        (
            match
            for match in (r.fullmatch(d) for r in _DATE_REGEXES)
            if match is not None
        ),
        None, # Default if no matches are found
    )
    assert m is not None, f"Incorrect date format specified for date handler: {d}"

    # Handle 'DD/MM/YYYY' or 'MM. jan/feb/... [year]' match
    gd = m.groupdict()
    day = number_to_ordinal(gd["day"], gender="kk", case=case, number="et")
    month = (
        _MONTH_NAMES[min(int(gd["month"]) - 1, 11)]  # DD/MM/YYYY specification
        if gd["month"].isdecimal()
        else _MONTH_NAMES[_MONTH_ABBREVS.index(gd["month"][:3])]  # Non-decimal
    )
    return (
        f"{day} {month} {year_to_text(gd['year'])}" if gd["year"] else f"{day} {month}"
    )


def _abbrev_handler(txt: str) -> str:
    return f' {spell_out(txt).replace(" ", _break_handler(strength="weak"))} '


def _email_handler(email: str) -> str:
    return email.replace("@", " hjá ").replace(".", " punktur ")


# Break strength values:
# none: No pause should be outputted. This can be used to remove a pause that would normally occur (such as after a period).
# x-weak: No pause should be outputted (same as none).
# weak: Treat adjacent words as if separated by a single comma (equivalent to medium).
# medium: Treat adjacent words as if separated by a single comma.
# strong: Make a sentence break (equivalent to using the s tag).
# x-strong: Make a paragraph break (equivalent to using the p tag).
_STRENGTHS = frozenset(("none", "x-weak", "weak", "medium", "strong", "x-strong"))


def _break_handler(time: Optional[str] = None, strength: Optional[str] = None):
    if time:
        return f'<break time="{time}" />'
    if strength:
        assert strength in _STRENGTHS, f"Break strength {strength} is invalid."
        return f'<break strength="{strength}" />'
    return f"<break />"


_HFT = Callable[..., str]  # Permissive handler function type
HANDLER_MAPTYPE = ChainMapType[str, _HFT]
# Default/Fallback normalization handlers,
# voice modules can override the handlers by creating a ChainMap child
DEFAULT_NORM_HANDLERS: HANDLER_MAPTYPE = ChainMap(
    {
        "number": number_to_text,
        "numbers": numbers_to_text,
        # ^ Plural forms are lazy shortcuts for longer text
        # TODO: amount/s
        # TODO: currency/ies
        # TODO: distance/s
        "float": float_to_text,
        "floats": floats_to_text,
        "ordinal": number_to_ordinal,
        "ordinals": numbers_to_ordinal,
        "phone": digits_to_text,
        "time": _time_handler,
        "date": _date_handler,
        "year": year_to_text,
        "years": years_to_text,
        "abbrev": _abbrev_handler,
        "email": _email_handler,
        "break": _break_handler,
        "paragraph": lambda txt: f"<p>{txt}</p>",
        "sentence": lambda txt: f"<s>{txt}</s>",
    }
)
