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

from typing import Any, Callable, List, Match, Mapping, Optional, Tuple, Union, cast

import re
from functools import lru_cache

from tokenizer import Abbreviations
from tokenizer.definitions import HYPHENS
from islenska.basics import ALL_CASES, ALL_GENDERS, ALL_NUMBERS
from reynir.bindb import GreynirBin
from reynir import Greynir

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

# Icelandic/English alphabet, uppercased
_ICE_ENG_ALPHA = "".join(c.upper() for c in _CHAR_PRONUNCIATION.keys())


def spell_out(s: str) -> str:
    """Spell out a sequence of characters, e.g. "LTB" -> "ell té bé".
    Useful for controlling speech synthesis of serial numbers, etc."""
    if not s:
        return ""
    t = [_CHAR_PRONUNCIATION.get(c.lower(), c) if not c.isspace() else "" for c in s]
    return " ".join(t).replace("  ", " ").strip()


# Matches e.g. "klukkan 14:30", "kl. 2:23:31", "02:15"
_TIME_REGEX = re.compile(
    r"((?P<klukkan>(kl\.|klukkan)) )?(?P<hour>\d{1,2}):"
    r"(?P<minute>\d\d)(:(?P<second>\d\d))?"
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


# Regex for splitting string when float/ordinal number encountered
_NUM_RE = re.compile(r"([0-9]+,[0-9]+|[0-9]+)")
# Matches letter followed by period or two uppercase letters side-by-side
_ABBREV_RE = re.compile(
    rf"([{_ICE_ENG_ALPHA + _ICE_ENG_ALPHA.lower()}]\."
    rf"|[{_ICE_ENG_ALPHA}][{_ICE_ENG_ALPHA}])"
)

# Terms common in sentences which refer to results from sports
_SPORTS_LEMMAS = frozenset(("leikur", "vinna", "tapa", "sigra"))
_HYPHEN_SYMBOLS = frozenset(HYPHENS)

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

    # Singleton Greynir instance
    _greynir: Optional[Greynir] = None
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
    def timespan(cls, seconds: str) -> str:
        """Voicify a span of time, specified in seconds."""
        # TODO: Replace time_period_desc in queries/util/__init__.py
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
    def date(cls, txt: str, case: str = "nf") -> str:
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
    @lru_cache(maxsize=50)  # Caching, as this method could be slow
    def generic(cls, txt: str) -> str:
        """
        Attempt to voicify some generic text.
        Parses text and calls other normalization handlers
        based on inferred meaning of words.
        """
        if cls._greynir is None:
            cls._greynir = Greynir(no_sentence_start=True)
        p_result = cls._greynir.parse(txt)

        # Map certain terminals directly to normalization functions
        handler_map: Mapping[str, NormMethod] = {
            "entity": cls.entity,
            "fyrirtæki": cls.entity,
            "sérnafn": cls.entity,
            "kennitala": cls.digits,
            "person": cls.person,
            "tími": cls.time,
            "ártal": cls.year,
            "tölvupóstfang": cls.email,
            "myllumerki": lambda t: f"hashtagg {t[1:]}",
            # TODO: Better handling of case for dates,
            # accusative is common though
            "dagsafs": lambda t: cls.time(cls.date(t, case="þf")),
            "dagsföst": lambda t: cls.time(cls.date(t, case="þf")),
            "tímapunktur": lambda t: cls.time(cls.date(t, case="þf")),
            "tímapunkturafs": lambda t: cls.time(cls.date(t, case="þf")),
            "tímapunkturfast": lambda t: cls.time(cls.date(t, case="þf")),
            "símanúmer": cls.digits,
            # TODO: Other terminals we probably want to handle
            # "amount": lambda t: t,
            # "gata": lambda t: t,
            # "grm": lambda t: t, # Greinarmerki
            # "lén": lambda t: t,
            # "mælieining": lambda t: t,
            # "notandanafn": lambda t: t,
            # "sameind": lambda t: t,
            # "sequence": lambda t: t,
            # "vefslóð": lambda t: t,
            # "vörunúmer": lambda t: t,
        }

        parts: List[str] = []
        for s in p_result["sentences"]:
            s_parts: List[str] = []
            # List of (token, terminal node) pairs.
            # Terminal nodes can be None if the sentence wasn't parseable
            tk_term_list = list(
                zip(s.tokens, s.terminal_nodes or (None for _ in s.tokens))
            )
            for i, tk_term in enumerate(tk_term_list):
                tok, term = tk_term
                cat = term.tcat if term is not None else None
                txt = tok.txt

                if cat in handler_map:
                    # Found a handler for this token
                    s_parts.append(handler_map[cat](txt))
                    continue
                if txt.isupper():
                    # Fully uppercase string, probably part of an entity name
                    s_parts.append(cls.entity(txt))
                    continue

                if _ABBREV_RE.match(txt) and (
                    (term is not None and not _ABBREV_RE.match(term.lemma))
                    or any(not _ABBREV_RE.match(m.stofn) for m in tok.meanings)
                ):
                    # Probably an abbreviation such as "t.d." or "MSc"
                    s_parts.append(cls.abbrev(txt))
                    continue

                # Next terminal
                next_term = (
                    tk_term_list[i + 1][1] if i + 1 < len(tk_term_list) else None
                )
                if next_term is None and txt == ".":
                    # Period at end of sentence
                    if s_parts:
                        # If we already have some text,
                        # add it the last string,
                        # otherwise just ignore
                        s_parts[-1] += "."
                    continue

                if _NUM_RE.match(txt):
                    # Text contains some form of a number

                    # Try to deduce correct declension of the number
                    case, gender = "nf", "hk"
                    if term is not None:
                        case = next(
                            filter(lambda v: v in ALL_CASES, term.variants), "nf"
                        )
                        gender = next(
                            filter(lambda v: v in ALL_GENDERS, term.variants), "hk"
                        )

                    if cat == "tala":
                        # Cardinal, e.g. "14", "135" or "17,86"
                        if "," in txt:
                            s_parts.append(cls.float(txt, case=case, gender=gender))
                        else:
                            s_parts.append(cls.number(txt, case=case, gender=gender))
                        continue
                    if cat == "raðnr":
                        # Ordinal, e.g. "14.", "2."
                        number = "et"
                        if next_term is not None:
                            # Fetch the grammatical number of the following word
                            number = next(
                                filter(lambda v: v in ALL_NUMBERS, next_term.variants),
                                "et",
                            )
                        s_parts.append(
                            cls.ordinal(txt, case=case, gender=gender, number=number)
                        )
                        continue
                    if cat == "talameðbókstaf":
                        # Number with letter, e.g. "15B", "42A"
                        for p in _NUM_RE.split(txt):
                            # e.g. "15B" -> ["", "15", "B"]
                            if p:
                                if p.isdecimal():
                                    s_parts.append(
                                        cls.number(p, case="nf", gender="hk")
                                    )
                                elif p.isupper():
                                    s_parts.append(cls.spell(p))
                                else:
                                    s_parts.append(p)
                        continue
                    if cat == "prósenta" or "%" in txt or " prósent" in txt:
                        # Percentage
                        gender = "hk"
                        case = "nf" if "%" in txt else case
                        for p in _NUM_RE.split(txt):
                            if p:
                                if "," in p:
                                    s_parts.append(
                                        cls.float(p, case=case, gender=gender)
                                    )
                                elif p.isdecimal():
                                    s_parts.append(
                                        cls.number(p, case=case, gender=gender)
                                    )
                                elif p.strip() == "%":
                                    s_parts.append("prósent")
                                else:
                                    s_parts.append(p)
                        continue

                # Check whether this is a hyphen denoting a range
                if (
                    txt in _HYPHEN_SYMBOLS
                    and term is not None
                    and term.parent is not None
                    # Check whether parent nonterminal has at least 3 children (might be a range)
                    and len(term.parent) >= 3
                    # Check whether middle sibling is a hyphen
                    # and filter(,term.parent.children)
                ):
                    # Hyphen found, probably denoting a range
                    if s.lemmas is not None and _SPORTS_LEMMAS.isdisjoint(s.lemmas):
                        # Probably not the result from a sports match
                        # (as the sentence doesn't contain sports-related lemmas),
                        # so replace the range-denoting hyphen with 'til'
                        s_parts.append("til")
                    continue

                # No normalization happened
                s_parts.append(txt)

            # Finished parsing a sentence
            parts.append(" ".join(s_parts))
        # Join sentences
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
        """Paragraph delimiter for speech synthesis."""
        return f"<p>{txt}</p>"

    @classmethod
    @_empty_str
    def sentence(cls, txt: str) -> str:
        """Sentence delimiter for speech synthesis."""
        return f"<s>{txt}</s>"
