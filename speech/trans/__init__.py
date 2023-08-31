#!/usr/bin/env python
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


    This file contains phonetic transcription functionality
    specifically intended for Icelandic speech synthesis engines.

"""

from typing import (
    Any,
    Callable,
    FrozenSet,
    Iterable,
    List,
    Match,
    Mapping,
    Optional,
    Tuple,
    Union,
    cast,
)

import re
import itertools
from functools import lru_cache

from tokenizer import Abbreviations

# Ensure abbreviations have been loaded
Abbreviations.initialize()

from tokenizer.definitions import HYPHENS
from islenska.basics import ALL_CASES, ALL_GENDERS, ALL_NUMBERS
from reynir.bindb import GreynirBin
from reynir.simpletree import SimpleTree
from reynir import Greynir, TOK, Tok

from speech.trans.num import (
    CaseType,
    GenderType,
    NumberType,
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

# Each voice module in the directory `speech/voices` can define a
# 'Transcriber' class, as a subclass of 'DefaultTranscriber', in
# order to override transcription methods for a particular voice
TRANSCRIBER_CLASS = "Transcriber"


def strip_markup(text: str) -> str:
    """Remove HTML/SSML tags from a string."""
    return re.sub(r"<.*?>", "", text)


def gssml(data: Any = None, *, type: str, **kwargs: Union[str, int, float]) -> str:
    """
    Utility function, surrounds data with Greynir-specific
    voice transcription tags.
    E.g. '<greynir ...>{data}</greynir>'
      or '<greynir ... />' if data is None.

    Type specifies the type of handling needed when the tags are parsed.
    The kwargs are then passed to the handler functions as appropriate.

    The greynir tags can be transcribed
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

# Icelandic/English alphabet, uppercased
_ICE_ENG_ALPHA = "".join(c.upper() for c in _CHAR_PRONUNCIATION.keys())

# Matches e.g. "klukkan 14:30", "kl. 2:23:31", "02:15"
_TIME_REGEX = re.compile(
    r"((?P<klukkan>(kl\.|klukkan)) )?(?P<hour>\d{1,2}):"
    r"(?P<minute>\d\d)(:(?P<second>\d\d))?",
    flags=re.IGNORECASE,
)
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


def _split_substring_types(t: str) -> Iterable[str]:
    """
    Split text into alphabetic, decimal or
    other character type substrings.

    Example:
        list(_split_substring_types("hello world,123"))
        -> ["hello", " ", "world", ",", "123"]
    """
    f: Callable[[str], int] = lambda c: c.isalpha() + 2 * c.isdecimal()
    return ("".join(g) for _, g in itertools.groupby(t, key=f))


# Matches letter followed by period or
# 2-5 uppercase letters side-by-side not
# followed by another uppercase letter
# (e.g. matches "EUIPO" or "MSc", but not "TESTING")
_ABBREV_RE = re.compile(
    rf"([{_ICE_ENG_ALPHA + _ICE_ENG_ALPHA.lower()}]\."
    rf"|\b[{_ICE_ENG_ALPHA}]{{2,5}}(?![{_ICE_ENG_ALPHA}]))"
)

# Terms common in sentences which refer to results from sports
_SPORTS_LEMMAS: FrozenSet[str] = frozenset(("leikur", "vinna", "tapa", "sigra"))

_HYPHEN_SYMBOLS = frozenset(HYPHENS)

_StrBool = Union[str, bool]
TranscriptionMethod = Callable[..., str]


def _empty_str(f: TranscriptionMethod) -> TranscriptionMethod:
    """
    Decorator which returns an empty string
    if the transcription method is called
    with an empty string.
    """

    def _inner(cls: "DefaultTranscriber", txt: str, **kwargs: _StrBool):
        if not txt:
            return ""
        return f(cls, txt, **kwargs)

    return _inner


def _bool_args(*bool_args: str) -> Callable[[TranscriptionMethod], TranscriptionMethod]:
    """
    Returns a decorator which converts keyword arguments in bool_args
    from strings into booleans before calling the decorated function.

    As GSSML is text-based, all function arguments come from strings.
    Booleans also work when calling the methods directly, e.g. in testing.
    """

    def _decorator(f: TranscriptionMethod) -> TranscriptionMethod:
        def _bool_translate(cls: "DefaultTranscriber", *args: str, **kwargs: str):
            # Convert keyword arguments in bool_args from
            # str to boolean before calling decorated function
            newkwargs = {
                key: (str(val) == "True" if key in bool_args else val)
                for key, val in kwargs.items()
            }
            return f(cls, *args, **newkwargs)

        return _bool_translate

    return _decorator


class DefaultTranscriber:
    """
    Class containing default phonetic transcription functions
    for Icelandic speech synthesis.
    """

    # Singleton Greynir instance
    _greynir: Optional[Greynir] = None

    # &,<,> cause speech synthesis errors,
    # change these to text
    _DANGER_SYMBOLS: Tuple[Tuple[str, str], ...] = (
        ("&", " og "),
        ("<=", " minna eða jafnt og "),
        ("<", " minna en "),
        (">=", " stærra eða jafnt og "),
        (">", " stærra en "),
    )

    @classmethod
    @_empty_str
    def danger_symbols(cls, txt: str) -> str:
        """
        Takes in any text and replaces the symbols that
        cause issues for the speech synthesis engine.
        These symbols are &,<,>.

        Note: HTML charrefs (e.g. &amp;) should be translated to their
              unicode character before this function is called.
              (GreynirSSMLParser does this automatically.)
        """
        for symb, new in cls._DANGER_SYMBOLS:
            txt = txt.replace(symb, new)
        return txt

    @classmethod
    @_empty_str
    @_bool_args("one_hundred")
    def number(
        cls,
        txt: str,
        *,
        case: CaseType = "nf",
        gender: GenderType = "hk",
        one_hundred: bool = False,
    ) -> str:
        """Voicify a number."""
        return number_to_text(txt, case=case, gender=gender, one_hundred=one_hundred)

    @classmethod
    @_empty_str
    @_bool_args("one_hundred")
    def numbers(
        cls,
        txt: str,
        *,
        case: CaseType = "nf",
        gender: GenderType = "hk",
        one_hundred: bool = False,
    ) -> str:
        """Voicify text containing multiple numbers."""
        return numbers_to_text(txt, case=case, gender=gender, one_hundred=one_hundred)

    @classmethod
    @_empty_str
    @_bool_args("comma_null", "one_hundred")
    def float(
        cls,
        txt: str,
        *,
        case: CaseType = "nf",
        gender: GenderType = "hk",
        one_hundred: bool = False,
        comma_null: bool = False,
    ) -> str:
        """Voicify a float."""
        return float_to_text(
            txt,
            case=case,
            gender=gender,
            one_hundred=one_hundred,
            comma_null=comma_null,
        )

    @classmethod
    @_empty_str
    @_bool_args("comma_null", "one_hundred")
    def floats(
        cls,
        txt: str,
        *,
        case: CaseType = "nf",
        gender: GenderType = "hk",
        one_hundred: bool = False,
        comma_null: bool = False,
    ) -> str:
        """Voicify text containing multiple floats."""
        return floats_to_text(
            txt,
            case=case,
            gender=gender,
            one_hundred=one_hundred,
            comma_null=comma_null,
        )

    @classmethod
    @_empty_str
    def ordinal(
        cls,
        txt: str,
        *,
        case: CaseType = "nf",
        gender: GenderType = "hk",
        number: NumberType = "et",
    ) -> str:
        """Voicify an ordinal."""
        return number_to_ordinal(txt, case=case, gender=gender, number=number)

    @classmethod
    @_empty_str
    def ordinals(
        cls,
        txt: str,
        *,
        case: CaseType = "nf",
        gender: GenderType = "hk",
        number: NumberType = "et",
    ) -> str:
        """Voicify text containing multiple ordinals."""
        return numbers_to_ordinal(txt, case=case, gender=gender, number=number)

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
    def timespan(cls, seconds: str) -> str:
        """Voicify a span of time, specified in seconds."""
        # TODO: Replace time_period_desc in queries/util/__init__.py
        raise NotImplementedError()

    @classmethod
    def distance(cls, meters: str) -> str:
        # TODO: Replace distance_desc in queries/util/__init__.py
        raise NotImplementedError()

    @classmethod
    @_empty_str
    def time(cls, txt: str) -> str:
        """Voicifies time of day."""

        def _time_fmt(match: Match[str]) -> str:
            gd = match.groupdict()
            prefix: Optional[str] = gd["klukkan"]
            h: int = int(gd["hour"])
            m: int = int(gd["minute"])
            s: Optional[int] = int(gd["second"]) if gd["second"] is not None else None
            suffix: Optional[str] = None

            t: List[str] = []
            # If "klukkan" or "kl." at beginning of string,
            # prepend "klukkan"
            if prefix:
                t.append("klukkan")

            # Hours
            if h == 0 and m == 0:
                # Call 00:00 "tólf á miðnætti"
                h = 12
                suffix = "á miðnætti"
            elif 0 <= h <= 5:
                # Call 00:xx-0:5:xx "... um nótt"
                suffix = "um nótt"
            elif h == 12 and m == 0:
                # Call 12:00 "tólf á hádegi"
                suffix = "á hádegi"
            t.append(number_to_text(h, case="nf", gender="hk"))

            # Minutes
            if m > 0:
                if m < 10:
                    # e.g. "þrettán núll fjögur"
                    t.append("núll")
                t.append(number_to_text(m, case="nf", gender="hk"))

            # Seconds
            if s is not None and s > 0:
                if s < 10:
                    # e.g. "þrettán núll fjögur núll sex"
                    t.append("núll")
                t.append(number_to_text(s, case="nf", gender="hk"))

            # Suffix for certain times of day to reduce ambiguity
            if suffix:
                t.append(suffix)

            return " ".join(t)

        return _TIME_REGEX.sub(_time_fmt, txt)

    @classmethod
    @_empty_str
    def date(cls, txt: str, case: CaseType = "nf") -> str:
        """Voicifies a date"""
        for r in _DATE_REGEXES:
            match = r.search(txt)
            if match:
                # Found match
                start, end = match.span()
                gd = match.groupdict()
                day = number_to_ordinal(gd["day"], gender="kk", case=case, number="et")
                mon: str = gd["month"]
                # Month names don't change in different declensions
                month = (
                    _MONTH_NAMES[int(mon) - 1]  # DD/MM/YYYY specification
                    if mon.isdecimal()
                    else _MONTH_NAMES[_MONTH_ABBREVS.index(mon[:3])]  # Non-decimal
                )
                fmt_date = (
                    f"{day} {month} {year_to_text(gd['year'])}"
                    if gd["year"]
                    else f"{day} {month}"
                )
                # Only replace date part, leave rest of string intact
                txt = txt[:start] + fmt_date + txt[end:]
                break
        return txt

    @classmethod
    @_empty_str
    def year(cls, txt: str) -> str:
        """Voicify a year."""
        return year_to_text(txt)

    @classmethod
    @_empty_str
    def years(cls, txt: str) -> str:
        """Voicify text containing multiple years."""
        return years_to_text(txt)

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
    # Pronunciation of some symbols
    _PUNCT_PRONUNCIATION: Mapping[str, str] = {
        " ": "bil",
        "~": "tilda",
        "`": "broddur",
        "!": "upphrópunarmerki",
        "@": "att merki",
        "#": "myllumerki",
        "$": "dollaramerki",
        "%": "prósentumerki",
        "^": "tvíbroddur",
        "&": "og merki",
        "*": "stjarna",
        "(": "vinstri svigi",
        ")": "hægri svigi",
        "-": "bandstrik",
        "_": "niðurstrik",
        "=": "jafnt og merki",
        "+": "plús",
        "[": "vinstri hornklofi",
        "{": "vinstri slaufusvigi",
        "]": "hægri hornklofi",
        "}": "hægri slaufusvigi",
        "\\": "bakstrik",
        "|": "pípumerki",
        ";": "semíkomma",
        ":": "tvípunktur",
        "'": "úrfellingarkomma",
        '"': "tvöföld gæsalöpp",
        ",": "komma",
        "<": "vinstri oddklofi",
        ".": "punktur",
        ">": "hægri oddklofi",
        "/": "skástrik",
        "?": "spurningarmerki",
        # Less common symbols
        "°": "gráðumerki",
        "±": "plús-mínus merki",
        "–": "stutt þankastrik",
        "—": "þankastrik",
        "…": "úrfellingarpunktar",
        "™": "vörumerki",
        "®": "skrásett vörumerki",
        "©": "höfundarréttarmerki",
    }

    @classmethod
    @_empty_str
    @_bool_args("literal")
    def spell(
        cls,
        txt: str,
        *,
        pause_length: Optional[str] = None,
        literal: bool = False,
    ) -> str:
        """
        Spell out a sequence of characters.
        If literal is set, also pronounce spaces and punctuation symbols.
        """
        pronounce: Callable[[str], str] = (
            lambda c: cls._CHAR_PRONUNCIATION.get(c.lower(), c)
            if not c.isspace()
            else ""
        )
        if literal:
            pronounce = lambda c: cls._CHAR_PRONUNCIATION.get(
                c.lower(), cls._PUNCT_PRONUNCIATION.get(c, c)
            )
        t = tuple(map(pronounce, txt))
        return (
            cls.vbreak(time="0.01s")
            + cls.vbreak(time=pause_length or "0.02s").join(t)
            + cls.vbreak(time="0.02s" if len(t) > 1 else "0.01s")
        )

    @classmethod
    @_empty_str
    def abbrev(cls, txt: str) -> str:
        """Expand an abbreviation."""
        meanings = tuple(
            filter(
                lambda m: m.fl != "erl",  # Only Icelandic abbrevs
                Abbreviations.get_meaning(txt) or [],
            )
        )
        if meanings:
            # Abbreviation has at least one known meaning, expand it
            return (
                cls.vbreak(time="0.01s") + meanings[0].stofn + cls.vbreak(time="0.05s")
            )

        # Fallbacks:
        # - Spell out, if any letter is uppercase (e.g. "MSc")
        if not txt.islower():
            return cls.spell(txt.replace(".", ""))
        # - Give up and keep as-is for all-lowercase txt
        # (e.g. "cand.med."),
        return txt

    @classmethod
    def amount(cls, txt: str) -> str:
        # TODO
        raise NotImplementedError()

    @classmethod
    def currency(cls, txt: str) -> str:
        # TODO
        raise NotImplementedError()

    @classmethod
    def measurement(cls, txt: str) -> str:
        # TODO
        raise NotImplementedError()

    @classmethod
    @_empty_str
    def molecule(cls, txt: str) -> str:
        """Voicify the name of a molecule"""
        return " ".join(
            cls.number(x, gender="kk") if x.isdecimal() else cls.spell(x, literal=True)
            for x in _split_substring_types(txt)
        )

    @classmethod
    @_empty_str
    def numalpha(cls, txt: str) -> str:
        """Voicify a alphanumeric string, spelling each character."""
        return " ".join(
            cls.digits(x) if x.isdecimal() else cls.spell(x)
            for x in _split_substring_types(txt)
        )

    @classmethod
    @_empty_str
    def username(cls, txt: str) -> str:
        """Voicify a username."""
        newtext: List[str] = []
        if txt.startswith("@"):
            txt = txt[1:]
            newtext.append("att")
        for x in _split_substring_types(txt):
            if x.isdecimal():
                if len(x) > 2:
                    # Spell out numbers of more than 2 digits
                    newtext.append(cls.digits(x))
                else:
                    newtext.append(cls.number(x))
            else:
                if x.isalpha() and len(x) > 2:
                    # Alphabetic string, longer than 2 chars, pronounce as is
                    newtext.append(x)
                else:
                    # Not recognized as number or Icelandic word,
                    # spell this literally (might include punctuation symbols)
                    newtext.append(cls.spell(x, literal=True))
        return " ".join(newtext)

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
    def domain(cls, txt: str) -> str:
        """Voicify a domain name."""
        newtext: List[str] = []
        for x in _split_substring_types(txt):
            if x in cls._DOMAIN_PRONUNCIATIONS:
                newtext.append(cls._DOMAIN_PRONUNCIATIONS[x])
            elif x.isdecimal():
                if len(x) > 2:
                    # Spell out numbers of more than 2 digits
                    newtext.append(cls.digits(x))
                else:
                    newtext.append(cls.number(x))
            else:
                if x.isalpha() and len(x) > 2:
                    # Alphabetic string, longer than 2 chars, pronounce as is
                    newtext.append(x)
                elif x == ".":
                    # Periods are common in domains/URLs,
                    # skip calling the spell method
                    newtext.append("punktur")
                else:
                    # Short and/or non-alphabetic string
                    # (might consist of punctuation symbols)
                    # Spell this literally
                    newtext.append(cls.spell(x, literal=True))
        return " ".join(newtext)

    @classmethod
    @_empty_str
    def email(cls, txt: str) -> str:
        """Voicify an email address."""
        user, at, domain = txt.partition("@")
        return f"{cls.username(user)}{' hjá ' if at else ''}{cls.domain(domain)}"

    # Hardcoded pronounciations,
    # should be overriden based on voice engine
    _ENTITY_PRONUNCIATIONS: Mapping[str, str] = {
        "ABBA": "ABBA",
        "BOYS": "BOYS",
        "BUGL": "BUGL",
        "BYKO": "BYKO",
        "CAVA": "CAVA",
        "CERN": "CERN",
        "CERT": "CERT",
        "EFTA": "EFTA",
        "ELKO": "ELKO",
        "NATO": "NATO",
        "NEW": "NEW",
        "NOVA": "NOVA",
        "PLAY": "PLAY",
        "PLUS": "PLUS",
        "RARIK": "RARIK",
        "RIFF": "RIFF",
        "RÚV": "RÚV",
        "SAAB": "SAAB",
        "SAAS": "SAAS",
        "SHAH": "SHAH",
        "SIRI": "SIRI",
        "UENO": "UENO",
        "YVES": "YVES",
    }

    # These parts of a entity name aren't necessarily
    # all uppercase or contain a period,
    # but should be spelled out
    _ENTITY_SPELL = frozenset(
        (
            "GmbH",
            "USS",
            "Ltd",
            "bs",
            "ehf",
            "h/f",
            "hf",
            "hses",
            "hsf",
            "ohf",
            "s/f",
            "ses",
            "sf",
            "slf",
            "slhf",
            "svf",
            "vlf",
            "vmf",
        )
    )

    @classmethod
    @_empty_str
    def entity(cls, txt: str) -> str:
        """Voicify an entity name."""
        parts = txt.split()
        with GreynirBin.get_db() as gbin:
            for i, p in enumerate(parts):
                if p in cls._ENTITY_PRONUNCIATIONS:
                    # Hardcoded pronunciation
                    parts[i] = cls._ENTITY_PRONUNCIATIONS[p]
                    continue
                if p.isdecimal():
                    # Number
                    parts[i] = cls.number(p)
                    continue

                spell_part = False
                p_nodots = p.replace(".", "")
                if p_nodots in cls._ENTITY_SPELL:
                    # We know this should be spelled out
                    spell_part = True
                elif p_nodots.isupper():
                    if gbin.lookup(p_nodots, auto_uppercase=True)[1]:
                        # Uppercase word has similar Icelandic word,
                        # pronounce it that way
                        parts[i] = p_nodots.capitalize()
                        continue
                    # No known Icelandic pronounciation, spell
                    spell_part = True
                if spell_part:
                    # Spell out this part of the entity name
                    parts[i] = cls.spell(p_nodots)
        return " ".join(parts)

    @classmethod
    @_empty_str
    @_bool_args("full_text")
    @lru_cache(maxsize=50)  # Caching, as this method could be slow
    def generic(cls, txt: str, *, full_text: bool = False) -> str:
        """
        Attempt to voicify some generic text.
        Parses text and calls other transcription handlers
        based on inferred meaning of words.
        if full_text is set to True,
        add paragraph and sentence markers.
        """
        if cls._greynir is None:
            cls._greynir = Greynir(no_sentence_start=True)
        p_result = cls._greynir.parse(txt)

        def _ordinal(tok: Tok, term: Optional[SimpleTree]) -> str:
            """Handles ordinals, e.g. '14.' or '2.'."""
            case, gender, number = "nf", "hk", "et"
            if term is not None:
                case = next(filter(lambda v: v in ALL_CASES, term.variants), "nf")
                gender = next(filter(lambda v: v in ALL_GENDERS, term.variants), "hk")
            if term is not None and term.index is not None:
                leaves = tuple(term.root.leaves)
                if len(leaves) > term.index + 1:
                    # Fetch the grammatical number of the following word
                    number = next(
                        filter(
                            lambda v: v in ALL_NUMBERS,
                            leaves[term.index + 1].variants,
                        ),
                        "et",
                    )
            return cls.ordinal(txt, case=case, gender=gender, number=number)

        def _number(tok: Tok, term: Optional[SimpleTree]) -> str:
            """Handles numbers, e.g. '135', '17,86' or 'fjörutíu og þrír'."""
            if not tok.txt.replace(".", "").replace(",", "").isdecimal():
                # Don't modify non-decimal numbers
                return tok.txt
            case, gender = "nf", "hk"
            if term is not None:
                case = next(filter(lambda v: v in ALL_CASES, term.variants), "nf")
                gender = next(filter(lambda v: v in ALL_GENDERS, term.variants), "hk")
            if "," in txt:
                return cls.float(txt, case=case, gender=gender)
            else:
                return cls.number(txt, case=case, gender=gender)

        def _percent(tok: Tok, term: Optional[SimpleTree]) -> str:
            """Handles a percentage, e.g. '15,6%' or '40 prósent'."""
            gender = "hk"
            n, cases, _ = cast(Tuple[float, Any, Any], tok.val)
            if cases is None:
                case = "nf"
            else:
                case = cases[0]
            if n.is_integer():
                val = cls.number(n, case=case, gender=gender)
            else:
                val = cls.float(n, case=case, gender=gender)
            if cases is None:
                # Uses "%" or "‰" instead of "prósent"
                # (permille value is converted to percentage by tokenizer)
                percent = "prósent"
            else:
                # Uses "prósent" in some form, keep as is
                percent = tok.txt.split(" ")[-1]
            return f"{val} {percent}"

        def _numwletter(tok: Tok, term: Optional[SimpleTree]) -> str:
            num = "".join(filter(lambda c: c.isdecimal(), tok.txt))
            return (
                cls.number(num, case="nf", gender="hk")
                + " "
                + cls.spell(tok.txt[len(num) + 1 :])
            )

        # Map certain terminals directly to transcription functions
        handler_map: Mapping[int, Callable[[Tok, Optional[SimpleTree]], str]] = {
            TOK.ENTITY: lambda tok, term: cls.entity(tok.txt),
            TOK.COMPANY: lambda tok, term: cls.entity(tok.txt),
            TOK.PERSON: lambda tok, term: cls.person(tok.txt),
            TOK.EMAIL: lambda tok, term: cls.email(tok.txt),
            TOK.HASHTAG: lambda tok, term: f"myllumerki {tok.txt[1:]}",
            TOK.TIME: lambda tok, term: cls.time(tok.txt),
            TOK.YEAR: lambda tok, term: cls.years(tok.txt),
            # TODO: Better handling of case for dates,
            # accusative is common though
            TOK.DATE: lambda tok, term: cls.date(tok.txt, case="þf"),
            TOK.DATEABS: lambda tok, term: cls.date(tok.txt, case="þf"),
            TOK.DATEREL: lambda tok, term: cls.date(tok.txt, case="þf"),
            TOK.TIMESTAMP: lambda tok, term: cls.time(cls.date(tok.txt, case="þf")),
            TOK.TIMESTAMPABS: lambda tok, term: cls.time(cls.date(tok.txt, case="þf")),
            TOK.TIMESTAMPREL: lambda tok, term: cls.time(cls.date(tok.txt, case="þf")),
            TOK.SSN: lambda tok, term: cls.digits(tok.txt),
            TOK.TELNO: lambda tok, term: cls.digits(tok.txt),
            TOK.SERIALNUMBER: lambda tok, term: cls.digits(tok.txt),
            TOK.MOLECULE: lambda tok, term: cls.molecule(tok.txt),
            TOK.USERNAME: lambda tok, term: cls.username(tok.txt),
            TOK.DOMAIN: lambda tok, term: cls.domain(tok.txt),
            TOK.URL: lambda tok, term: cls.domain(tok.txt),
            # TOK.AMOUNT: lambda tok, term: tok.txt,
            # TOK.CURRENCY: lambda tok, term: tok.txt, CURRENCY_SYMBOLS in tokenizer
            # TOK.MEASUREMENT: lambda tok, term: tok.txt, SI_UNITS in tokenizer
            TOK.NUMBER: _number,
            TOK.NUMWLETTER: _numwletter,
            TOK.ORDINAL: _ordinal,
            TOK.PERCENT: _percent,
        }

        parts: List[str] = []
        for s in p_result["sentences"]:
            s_parts: List[str] = []
            # List of (token, terminal node) pairs.
            # Terminal nodes can be None if the sentence wasn't parseable
            tk_term_list = tuple(
                zip(s.tokens, s.terminal_nodes or (None for _ in s.tokens))
            )
            for tok, term in tk_term_list:
                txt = tok.txt

                if tok.kind in handler_map:
                    # Found a handler for this token type
                    s_parts.append(handler_map[tok.kind](tok, term))
                    continue

                # Fallbacks if no handler found
                if txt.isupper():
                    # Fully uppercase string,
                    # might be part of an entity name
                    s_parts.append(cls.entity(txt))

                elif _ABBREV_RE.match(txt) and (
                    (term is not None and not _ABBREV_RE.match(term.lemma))
                    or any(not _ABBREV_RE.match(m.stofn) for m in tok.meanings)
                ):
                    # Probably an abbreviation such as "t.d." or "MSc"
                    s_parts.append(cls.abbrev(txt))

                # Check whether this is a hyphen denoting a range
                elif (
                    txt in _HYPHEN_SYMBOLS
                    and term is not None
                    and term.parent is not None
                    # Check whether parent nonterminal has at least 3 children (might be a range)
                    and len(term.parent) >= 3
                ):
                    # Hyphen found, probably denoting a range
                    if s.lemmas is not None and _SPORTS_LEMMAS.isdisjoint(s.lemmas):
                        # Probably not the result from a sports match
                        # (as the sentence doesn't contain sports-related lemmas),
                        # so replace the range-denoting hyphen with 'til'
                        s_parts.append("til")
                else:
                    # No transcribing happened
                    s_parts.append(txt)

            # Finished parsing a sentence
            sent = " ".join(s_parts).strip()
            parts.append(cls.sentence(sent) if full_text else sent)

        # Join sentences
        para = " ".join(parts)
        return cls.paragraph(para) if full_text else para

    _PERSON_PRONUNCIATION: Mapping[str, str] = {
        "Jr": "djúníor",
        "Jr.": "djúníor",
    }

    @classmethod
    @_empty_str
    def person(cls, txt: str) -> str:
        """Voicify the name of a person."""
        with GreynirBin.get_db() as gbin:
            gender = cast(GenderType, gbin.lookup_name_gender(txt))
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

    _VBREAK_STRENGTHS = frozenset(
        ("none", "x-weak", "weak", "medium", "strong", "x-strong")
    )

    @classmethod
    def vbreak(cls, time: Optional[str] = None, strength: Optional[str] = None) -> str:
        """Create a break in the voice/speech synthesis."""
        if time:
            return f'<break time="{time}" />'
        if strength:
            assert (
                strength in cls._VBREAK_STRENGTHS
            ), f"Break strength {strength} is invalid."
            return f'<break strength="{strength}" />'
        return f"<break />"

    @classmethod
    @_empty_str
    def paragraph(cls, txt: str) -> str:
        """Paragraph delimiter for speech synthesis."""
        return f"<p>{txt}</p>"

    @classmethod
    @_empty_str
    def sentence(cls, txt: str) -> str:
        """Sentence delimiter for speech synthesis."""
        return f"<s>{txt}</s>"
