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

from typing import Any, Callable, Mapping, Optional, Tuple, Union

import re

from tokenizer import Abbreviations
from reynir.bindb import GreynirBin

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
    _ROMAN_NUMERALS,
    roman_numeral_to_ordinal,
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


# Spell out how character names are pronounced in Icelandic
_CHAR_PRONUNCIATION: Mapping[str, str] = {
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
    t = [_CHAR_PRONUNCIATION.get(c.lower(), c) if not c.isspace() else "" for c in s]
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


NormMethod = Callable[..., str]


def _empty_str(f: NormMethod) -> NormMethod:
    """
    Decorator which returns an empty string
    if the normalization method is called
    with an empty string.
    """

    def _empty_str_wrapper(cls: "DefaultNormalization", txt: str, **kwargs: str):
        if not txt:
            return ""
        return f(cls, txt, **kwargs)

    return _empty_str_wrapper


# Ensure abbreviations have been loaded,
# common during normalization
Abbreviations.initialize()


class DefaultNormalization:
    """
    Class containing default text normalization functions
    for Icelandic speech synthesis.
    """

    # TODO
    # amount/s
    # currency/ies
    # distance/s

    @staticmethod
    def _coerce_to_boolean(arg: Optional[str]) -> bool:
        """
        Static helper for converting a string argument to a boolean.
        As GSSML is text-based, all function arguments are strings.
        """
        return arg is not None and arg == "True"

    @classmethod
    @_empty_str
    def danger_symbols(cls, txt: str) -> str:
        """
        Takes in any text and replaces the symbols that
        cause issues for the speech synthesis engine.
        These symbols are &,<,>.

        Note: HTML charrefs should be translated to their
              unicode character before this function is called.
              (GreynirSSMLParser does this automatically.)
        """
        # Ampersands
        txt = re.sub(r" ?& ?", " og ", txt)
        # <
        txt = re.sub(r" ?<= ?", " minna eða jafnt og ", txt)
        txt = re.sub(r" ?< ?", " minna en ", txt)
        # >
        txt = re.sub(r" ?>= ?", " stærra eða jafnt og ", txt)
        txt = re.sub(r" ?> ?", " stærra en ", txt)
        return txt

    @classmethod
    @_empty_str
    def number(cls, txt: str, **kwargs: str) -> str:
        """Voicify a number."""
        return number_to_text(txt, **kwargs)

    @classmethod
    @_empty_str
    def numbers(cls, txt: str, **kwargs: str) -> str:
        """Voicify text containing multiple numbers."""
        return numbers_to_text(txt, **kwargs)

    @classmethod
    @_empty_str
    def float(cls, txt: str, **kwargs: str) -> str:
        """Voicify a float."""
        return float_to_text(txt, **kwargs)

    @classmethod
    @_empty_str
    def floats(cls, txt: str, **kwargs: str) -> str:
        """Voicify text containing multiple floats."""
        return floats_to_text(txt, **kwargs)

    @classmethod
    @_empty_str
    def ordinal(cls, txt: str, **kwargs: str) -> str:
        """Voicify an ordinal."""
        return number_to_ordinal(txt, **kwargs)

    @classmethod
    @_empty_str
    def ordinals(cls, txt: str, **kwargs: str) -> str:
        """Voicify text containing multiple ordinals."""
        return numbers_to_ordinal(txt, **kwargs)

    @classmethod
    @_empty_str
    def digits(cls, txt: str) -> str:
        """Spell out digits."""
        return digits_to_text(txt)

    @classmethod
    @_empty_str
    def phone(cls, txt: str) -> str:
        """Spell out a phone number."""
        return cls.digits(txt)

    @classmethod
    @_empty_str
    def time(cls, txt: str) -> str:
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
            suffix = "á hádegi"
        t = [number_to_text(h, case="nf", gender="hk")]
        if m > 0:
            if m < 10:
                # e.g. "þrettán núll fjögur"
                t.append("núll")
            t.append(number_to_text(m, case="nf", gender="hk"))
        if suffix:
            t.append(suffix)
        return " ".join(t)

    @classmethod
    @_empty_str
    def date(cls, txt: str, case: str = "nf") -> str:
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
        mon: str = gd["month"]
        # Month names don't change in different declensions
        month = (
            _MONTH_NAMES[int(mon) - 1]  # DD/MM/YYYY specification
            if mon.isdecimal()
            else _MONTH_NAMES[_MONTH_ABBREVS.index(mon[:3])]  # Non-decimal
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
    @_empty_str
    def year(cls, txt: str, *, after_christ: Optional[str] = None) -> str:
        """Voicify a year."""
        ac = cls._coerce_to_boolean(after_christ)
        return year_to_text(txt, after_christ=ac)

    @classmethod
    @_empty_str
    def years(cls, txt: str, *, after_christ: Optional[str] = None) -> str:
        """Voicify text containing multiple years."""
        ac = cls._coerce_to_boolean(after_christ)
        return years_to_text(txt, after_christ=ac)

    # Pronunciation of character names in Icelandic
    _CHAR_PRONUNCIATION: Mapping[str, str] = {
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
    @_empty_str
    def spell(cls, txt: str, ignore_punctuation: Optional[str] = None) -> str:
        """Spell out a sequence of characters."""
        # TODO: Optionally pronunce e.g. '.,/()'
        # TODO: Control breaks between characters
        # ignore_punct = cls._coerce_to_boolean(ignore_punctuation)
        t = [
            cls._CHAR_PRONUNCIATION.get(c.lower(), c) if not c.isspace() else ""
            for c in txt
        ]
        return ", ".join(t)

    @classmethod
    @_empty_str
    def abbrev(cls, txt: str) -> str:
        """Expand an abbreviation."""
        meanings = list(
            filter(
                lambda m: m.fl != "erl",  # Only Icelandic abbrevs
                Abbreviations.get_meaning(txt) or [],
            )
        )
        if meanings:
            # Abbreviation has at least one known meaning, expand it
            return meanings[0].stofn

        # Fallbacks:
        # - Spell out, if any letter is uppercase (e.g. "MSc")
        if not txt.islower():
            return cls.spell(txt.replace(".", ""))
        # - Give up and keep as-is for all-lowercase txt
        # (e.g. "cand.med."),
        return txt

    _DOMAIN_PRONUNCIATIONS: Mapping[str, str] = {
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
    @_empty_str
    def email(cls, txt: str) -> str:
        """Voicify an email address."""
        # TODO: Use spelling with punctuation to spell weird characters
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

    # These uppercase parts of a entity name should be
    # pronounced as-is, not spelled out
    _ENTITY_DONT_SPELL = frozenset(
        (
            "ABBA",
            "BOYS",
            "BUGL",
            "BYKO",
            "CAVA",
            "CERN",
            "CERT",
            "EFTA",
            "ELKO",
            "NATO",
            "NEW",
            "NOVA",
            "PLAY",
            "PLUS",
            "RARIK",
            "RIFF",
            "RÚV",
            "SAAB",
            "SAAS",
            "SHAH",
            "SIRI",
            "UENO",
            "NASA",
            "YVES",
            # "XBOX": "ex box"
            # "VISA": "vísa"
            # "UKIP": "júkipp"
            # "TIME": "tæm",
            # "UEFA": "júei fa"
            # "FIFA": "FÍÍfFAh"
            # "LEGO": "llegó"
            # "GIRL": "görl"
            # "FIDE": "fídeh"
            # (sérhljóði samhljóði sérhljóði samhljóði)?
            # (samhljóði sérhljóði samhljóði sérhljóði)?
        )
    )
    # These parts of a entity name aren't all uppercase
    # and don't necessarily contain a period,
    # but should be spelled out
    _ENTITY_SPELL = frozenset(
        (
            "GmbH",
            "Ltd",
            "sf",
            "s/f",
            "hf",
            "h/f",
            "hsf",
            "ehf",
            "slhf",
            "slf",
            "svf",
            "vlf",
            "vmf",
            "ohf",
            "bs",
            "ses",
            "hses",
        )
    )

    @classmethod
    @_empty_str
    def entity(cls, txt: str) -> str:
        """Voicify an entity name."""
        txt.replace("&", " og ")
        parts = txt.split()
        # TODO: If gb.lookup(p.lower(), auto_uppercase=True)[1]
        #       then pronounce as icelandic word
        for i, p in enumerate(parts):
            if p in cls._ENTITY_DONT_SPELL:
                continue
            if p.replace(".", "") in cls._ENTITY_SPELL or (p.isupper() and len(p) <= 4):
                # Spell out this part of the entity name
                parts[i] = cls.spell(p)
        if parts[-1].endswith("."):
            # Probably should be spelled (e.g. 'ehf.')
            parts[-1] = cls.spell(parts[-1].replace(".", ""))
        return " ".join(parts)

    @staticmethod
    def _guess_noun_case_gender(noun: str) -> Tuple[str, str]:
        """Helper to return (case, gender) for a noun form."""
        # Fallback
        case = "nf"
        gender = "kk"
        # Followed by another word,
        # try to guess gender and case
        with GreynirBin.get_db() as gbin:
            bts = GreynirBin.nouns(gbin.lookup(noun)[1])
            if bts:
                case = bts[0].mark[:2].lower()
                gender = bts[0].ofl
        return case, gender

    @classmethod
    @_empty_str
    def title(cls, txt: str) -> str:
        """Voicify the title of a person."""
        return txt # TODO
        # Forstjóri MS, lektor við HÍ
        # eigandi BSÍ ehf., Strætó bs.
        # PhD, BSc, M.Phil.
        parts = txt.split()
        for i, p in enumerate(parts):
            last: bool = i == len(parts) - 1
            # Check if there is a number
            if p.isdecimal():
                if len(p) == 4 and (999 < int(p) < 2500):
                    # Year, probably
                    parts[i] = cls.year(p)
                elif not last and (parts[i + 1] == "ára" or parts[i + 1] == "árs"):
                    # Age, certainly
                    parts[i] = cls.number(p, case="ef", gender="hk")
                else:
                    # Fallback
                    case, gender = "nf", "kk"
                    if not last:
                        case, gender = cls._guess_noun_case_gender(parts[i + 1])
                    parts[i] = cls.number(p, case=case, gender=gender)
                continue
            # Check if there is an ordinal
            if "." in p and p.rstrip(".").isdecimal():
                # Ordinal, certainly
                case, gender = "nf", "kk"
                if not last:
                    case, gender = cls._guess_noun_case_gender(parts[i + 1])
                parts[i] = cls.ordinal(p, case=case, gender=gender)
                continue
            # Check abbreviations, expand if known
            # FIXME Correct case when expanding
            # if Abbreviations.has_meaning(p):
            #     parts[i] = cls.abbrev(p)
        return " ".join(parts)

    _PERSON_PRONUNCIATION: Mapping[str, str] = {
        "Jr": "djúníor",
    }

    @classmethod
    @_empty_str
    def person(cls, txt: str) -> str:
        """Voicify the name of a person."""
        with GreynirBin.get_db() as gbin:
            gender = gbin.lookup_name_gender(txt)
        parts = txt.split()
        for i, p in enumerate(parts):
            if p in cls._PERSON_PRONUNCIATION:
                parts[i] = cls._PERSON_PRONUNCIATION[p]
                continue
            if "." in p:
                # Contains period (e.g. 'Jak.' or 'Ólafsd.')
                abbrs = next(
                    filter(
                        lambda m: m.ordfl == gender  # Correct gender
                        # Icelandic abbrev
                        and m.fl != "erl"
                        # Uppercase first letter
                        and m.stofn[0].isupper()
                        # Expanded meaning must be longer
                        # (otherwise we just spell it, e.g. 'Th.' = 'Th.')
                        and len(m.stofn) > len(p),
                        Abbreviations.get_meaning(p) or [],
                    ),
                    None,
                )
                if abbrs is not None:
                    # Replace with expanded version of part
                    parts[i] = abbrs.stofn
                else:
                    # Spell this part
                    parts[i] = cls.spell(p.replace(".", ""))
            if i + 2 >= len(parts) and all(l in _ROMAN_NUMERALS for l in parts[i]):
                # Last or second to last part of name looks
                # like an uppercase roman numeral,
                # replace with ordinal
                parts[i] = roman_numeral_to_ordinal(parts[i], gender=gender)
        return " ".join(parts)

    @classmethod
    def vbreak(cls, time: Optional[str] = None, strength: Optional[str] = None) -> str:
        """Create a break in the voice/speech synthesis."""
        if time:
            return f'<break time="{time}" />'
        if strength:
            assert strength in _STRENGTHS, f"Break strength {strength} is invalid."
            return f'<break strength="{strength}" />'
        return f"<break />"

    @classmethod
    @_empty_str
    def paragraph(cls, txt: str) -> str:
        return f"<p>{txt}</p>"

    @classmethod
    @_empty_str
    def sentence(cls, txt: str) -> str:
        return f"<s>{txt}</s>"
