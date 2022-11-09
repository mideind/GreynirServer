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


def gssml(data: Any = None, type: str = "", **kwargs: Union[str, int, float]) -> str:
    """
    Utility function, surrounds data with Greynir-specific
    voice normalizing tags.
    E.g. '<greynir ... >{data}</greynir>'
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
    ), f"Must specify type keyword argument for gssml function. data: {data}"
    return (
        f'<greynir type="{type}"'
        + "".join(f' {k}="{v}"' for k, v in kwargs.items())
        + (f">{data}</greynir>" if data is not None else f"/>")
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


def _time(t: str) -> str:
    # TODO: Say e.g. "hálf fjögur" instead of "fimmtán þrjátíu"? korter í/yfir
    # TODO: Say "tuttugu mínútur yfir þrjú" instead of "fimmtán tuttugu"
    ts = t.split(":")
    return " ".join(number_to_text(x, gender="hk") for x in ts)


def _date(d: str, case: str = "nf") -> str:
    # TODO: Handle DD/MM/YYY
    # TODO: Handle MM. jan/feb/...
    return numbers_to_ordinal(d, gender="kk", case=case, number="et")


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


def _abbrev_handler(txt: str) -> str:
    return f" {spell_out(txt).replace(' ', _break_handler(strength='weak'))} "


_HFT = Callable[..., str]  # Permissive handler function type
HANDLER_MAPTYPE = ChainMapType[str, _HFT]
# Default/Fallback normalization handlers,
# voice modules can override the handlers by creating a ChainMap child
DEFAULT_NORM_HANDLERS: HANDLER_MAPTYPE = ChainMap(
    {
        "number": number_to_text,
        "numbers": numbers_to_text,  # Plural forms are lazy shortcuts
        "float": float_to_text,
        "floats": floats_to_text,
        "ordinal": number_to_ordinal,
        "ordinals": numbers_to_ordinal,
        "phone": digits_to_text,
        "time": _time,
        "date": _date,
        "year": year_to_text,
        "years": years_to_text,
        "abbrev": _abbrev_handler,
        "break": _break_handler,
        "paragraph": lambda txt: f"<p>{txt}</p>",
        "sentence": lambda txt: f"<s>{txt}</s>",
    }
)
