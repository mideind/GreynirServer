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

from typing import Any, Optional, Union

import re

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

# Each voice module in the directory speech/voices can define a
# 'Normalization' class as a subclass of 'DefaultNormalization' in
# order to override normalization functions/methods for a particular voice
NORMALIZATION_CLASS = "Normalization"


def strip_markup(text: str) -> str:
    """Remove HTML/SSML tags from a string."""
    return re.sub(r"<.*?>", "", text)


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


# Spell out how character names are pronunced in Icelandic
_CHAR_PRONUNCIATION = {
    "a": "a",
    "á": "á",
    "b": "bé",
    "c": "sé",
    "d": "dé",
    "ð": "eð",
    "e": "e",
    "é": "é",
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


# Break strength values:
# none: No pause should be outputted. This can be used to remove a pause that would normally occur (such as after a period).
# x-weak: No pause should be outputted (same as none).
# weak: Treat adjacent words as if separated by a single comma (equivalent to medium).
# medium: Treat adjacent words as if separated by a single comma.
# strong: Make a sentence break (equivalent to using the s tag).
# x-strong: Make a paragraph break (equivalent to using the p tag).
_STRENGTHS = frozenset(("none", "x-weak", "weak", "medium", "strong", "x-strong"))


class NormalizationHandler:  # Abstract base class
    ...


class DefaultNormalization(NormalizationHandler):
    """
    Class containing default text normalization functions
    for Icelandic speech synthesis.
    """

    # TODO
    # amount/s
    # currency/ies
    # distance/s

    @classmethod
    def number(cls, txt: str, **kwargs: str):
        """Voicify a number."""
        return number_to_text(txt, **kwargs)

    @classmethod
    def numbers(cls, txt: str, **kwargs: str):
        """Voicify text containing multiple numbers."""
        return numbers_to_text(txt, **kwargs)

    @classmethod
    def float(cls, txt: str, **kwargs: str):
        """Voicify a float."""
        return float_to_text(txt, **kwargs)

    @classmethod
    def floats(cls, txt: str, **kwargs: str):
        """Voicify text containing multiple floats."""
        return floats_to_text(txt, **kwargs)

    @classmethod
    def ordinal(cls, txt: str, **kwargs: str):
        """Voicify an ordinal."""
        return number_to_ordinal(txt, **kwargs)

    @classmethod
    def ordinals(cls, txt: str, **kwargs: str):
        """Voicify text containing multiple ordinals."""
        return numbers_to_ordinal(txt, **kwargs)

    @classmethod
    def digits(cls, txt: str):
        """Spell out digits."""
        return digits_to_text(txt)

    @classmethod
    def phone(cls, txt: str):
        """Spell out digits."""
        return cls.digits(txt)

    @classmethod
    def time(cls, txt: str):
        """
        Voicifies time of day, specified as 'HH:MM'.
        E.g.
            "11:34" -> "ellefu þrjátíu og fjögur",
            "00:30" -> "tólf þrjátíu um nótt"
        Note: doesn't check for incorrect data, caller should handle.
        """
        h, m = [int(i) for i in txt.split(":")]
        suffix: Optional[str] = None
        # Some times
        if h == 0:
            # Call 00:00 "tólf á miðnætti"
            # and 00:xx "tólf ... um nótt"
            h = 12
            suffix = "á miðnætti" if m == 0 else "um nótt"
        elif 0 < h <= 5:
            suffix = "um nótt"
        elif h == 12 and m == 0:
            suffix = "um hádegi"
        t = [
            number_to_text(h, case="nf", gender="hk"),
        ]
        if m > 0:
            if m < 10:
                # e.g. "þrettán núll fjögur"
                t.append("núll")
            t.append(number_to_text(m, case="nf", gender="hk"))
        if suffix:
            t.append(suffix)
        return " ".join(t)

    @classmethod
    def date(cls, txt: str, case: str = "nf"):
        """
        Voicifies dates specified in either
            'YYYY-MM-DD' (ISO 8601 format),
            'DD/MM/YYYY' or
            'DD. month[ YYYY]'
        Note: doesn't check for incorrect numbers,
            as that should be handled by caller.
        """
        # Get first fullmatch from date regexes
        m = next(
            filter(
                lambda x: x is not None,
                (r.fullmatch(txt) for r in _DATE_REGEXES),
            ),
            None,  # Default if no matches are found
        )
        assert m is not None, f"Incorrect date format specified for date handler: {txt}"

        # Handle 'DD/MM/YYYY' or 'MM. jan/feb/... [year]' match
        gd = m.groupdict()
        day = number_to_ordinal(gd["day"], gender="kk", case=case, number="et")
        # Month names don't change in different declensions
        month = (
            _MONTH_NAMES[int(gd["month"]) - 1]  # DD/MM/YYYY specification
            if gd["month"].isdecimal()
            else _MONTH_NAMES[_MONTH_ABBREVS.index(gd["month"][:3])]  # Non-decimal
        )
        return (
            f"{day} {month} {year_to_text(gd['year'])}"
            if gd["year"]
            else f"{day} {month}"
        )

    @classmethod
    def timespan(cls, seconds: str) -> str:
        """Voicify a span of time, specified in seconds."""
        # TODO: Replace time_period_desc in queries/util/__init__.py
        raise NotImplementedError()

    @classmethod
    def year(cls, txt: str, *, after_christ: Optional[str] = None):
        """Voicify a year."""
        ac = after_christ is not None and after_christ == "True"
        return year_to_text(txt, after_christ=ac)

    @classmethod
    def years(cls, txt: str, *, after_christ: Optional[str] = None):
        """Voicify text containing multiple years."""
        ac = after_christ is not None and after_christ == "True"
        return years_to_text(txt, after_christ=ac)

    # Pronunciation of character names in Icelandic
    _CHAR_PRONUNCIATION = {
        "a": "a",
        "á": "á",
        "b": "bé",
        "c": "sé",
        "d": "dé",
        "ð": "eð",
        "e": "e",
        "é": "é",
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
        "w": "tvöfaltvaff",
        "x": "ex",
        "y": "ufsilon",
        "ý": "ufsilon í",
        "þ": "þoddn",
        "æ": "æ",
        "ö": "ö",
        "z": "seta",
    }

    @classmethod
    def spell(cls, txt: str):
        """Spell out a sequence of characters."""
        if not txt:
            return ""
        t = [cls._CHAR_PRONUNCIATION.get(c.lower(), c) if c != " " else "" for c in txt]
        s = ", ".join(t).strip()
        return re.sub(r"\s\s+", r" ", s)  # Shorten repeated whitespace

    @classmethod
    def abbrev(cls, txt: str):
        """Spell out a sequence of characters."""
        return cls.spell(txt)

    _DOMAIN_PRONUNCIATIONS = {
        "is": "is",
        "org": "org",
        "net": "net",
        "com": "komm",
        "gmail": "gjé meil",
        "hotmail": "hott meil",
        "yahoo": "ja húú",
        "outlook": "átlúkk",
    }

    @classmethod
    def email(cls, txt: str):
        """Voicify emails."""
        user, domain = txt.split("@")
        user_parts = user.split(".")
        domain_parts = domain.split(".")
        for i, p in enumerate(user_parts):
            if len(p) < 3:
                # Short parts of username get spelled out
                user_parts[i] = cls.spell(p)
        for i, p in enumerate(domain_parts):
            if p in cls._DOMAIN_PRONUNCIATIONS:
                domain_parts[i] = cls._DOMAIN_PRONUNCIATIONS[p]
            elif len(p) <= 3:
                # Spell out short, unknown domains
                domain_parts[i] = cls.spell(p)
        return f"{' punktur '.join(user_parts)} hjá {' punktur '.join(domain_parts)}"

    @classmethod
    def vbreak(cls, time: Optional[str] = None, strength: Optional[str] = None):
        """Create a break in the voice/speech synthesis."""
        if time:
            return f'<break time="{time}" />'
        if strength:
            assert strength in _STRENGTHS, f"Break strength {strength} is invalid."
            return f'<break strength="{strength}" />'
        return f"<break />"

    @classmethod
    def paragraph(cls, txt: str):
        return f"<p>{txt}</p>"

    @classmethod
    def sentence(cls, txt: str):
        return f"<s>{txt}</s>"
