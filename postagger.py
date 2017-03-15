#!/usr/bin/env python
"""

    Reynir: Natural language processing for Icelandic

    POS tagger module

    Copyright (C) 2017 Vilhjálmur Þorsteinsson

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


    This module implements a wrapper for Reynir's POS tagging
    functionality. It allows clients to simply and cleanly generate POS tags
    from plain text into a Python dict, which can then easily be converted to
    JSON if desired.

    Use as follows:

    from postagger import Tagger

    with Tagger.session() as tagger:
        for text in mytexts:
            d = tagger.tag(text)
            do_something_with(d["result"], d["stats"], d["register"])

    The session() context manager will automatically clean up after the
    tagging session, i.e. release a scraper database session and the
    parser with its memory caches. Tagging multiple sentences within one
    session is much more efficient than creating separate sessions for
    each one.

"""

from scraperdb import SessionContext
from treeutil import TreeUtility
from tokenizer import canonicalize_token
from settings import Settings, ConfigError
from contextlib import contextmanager
from fastparser import Fast_Parser


class Tagger:

    def __init__(self):
        # Make sure that the settings are loaded
        if not Settings.loaded:
            Settings.read("config/Reynir.conf")
        self._parser = None
        self._session = None

    def tag(self, text):
        """ Parse and POS-tag the given text, returning a dict """
        assert self._parser is not None, "Call Tagger.tag() inside 'with Tagger().context()'!"
        assert self._session is not None, "Call Tagger.tag() inside 'with Tagger().context()'!"
        pgs, stats, register = TreeUtility.raw_tag_text(self._parser, self._session, text)
        # Amalgamate the result into a single list of sentences
        if pgs:
            # Only process the first paragraph, if there are many of them
            if len(pgs) == 1:
                pgs = pgs[0]
            else:
                # More than one paragraph: gotta concatenate 'em all
                pa = []
                for pg in pgs:
                    pa.extend(pg)
                pgs = pa
        for sent in pgs:
            # Transform the token representation into a
            # nice canonical form for outside consumption
            for t in sent:
                canonicalize_token(t)
        return dict(result = pgs, stats = stats, register = register)

    @contextmanager
    def _create_session(self):
        """ Wrapper to make sure we have a fresh database session and a parser object
            to work with in a tagging session - and that they are properly cleaned up
            after use """
        if self._session is not None:
            # Already within a session: weird case, but allow it anyway
            assert self._parser is not None
            yield self
        else:
            with SessionContext(commit = True, read_only = True) as session, Fast_Parser() as parser:
                self._session = session
                self._parser = parser
                try:
                    # Nice trick enabled by the @contextmanager wrapper
                    yield self
                finally:
                    self._parser = None
                    self._session = None

    @classmethod
    def session(cls):
        return cls()._create_session()


class IFD_Tagset:

    """ Utility class to generate POS tags compatible with
        the Icelandic Frequency Dictionary (IFD) tagset
        (cf. http://www.malfong.is/files/ot_tagset_book_is.pdf) """

    # Strings that must be present in the grammatical form for variants
    BIN_TO_VARIANT = {
        "NF" : "nf", # Nefnifall / nominative
        "ÞF" : "þf", # Þolfall / accusative
        "ÞF2" : "þf", # Þolfall / accusative
        "ÞGF" : "þgf", # Þágufall / dative
        "ÞGF2" : "þgf", # Þágufall / dative
        "EF" : "ef", # Eignarfall / possessive
        "EF2" : "ef", # Eignarfall / possessive
        "KK" : "kk", # Karlkyn / masculine
        "KVK" : "kvk", # Kvenkyn / feminine
        "HK" : "hk", # Hvorugkyn / neutral
        "ET" : "et", # Eintala / singular
        "ET2" : "et", # Eintala / singular
        "FT" : "ft", # Fleirtala / plural
        "FT2" : "ft", # Fleirtala / plural
        "FSB" : "fsb", # Frumstig, sterk beyging
        "FVB" : "fvb", # Frumstig, veik beyging
        "MST" : "mst", # Miðstig / comparative
        "MST2" : "mst", # Miðstig / comparative
        "ESB" : "esb", # Efsta stig, sterk beyging / superlative
        "EVB" : "evb", # Efsta stig, veik beyging / superlative
        "EST" : "est", # Efsta stig / superlative
        "EST2" : "est", # Efsta stig / superlative
        "1P" : "p1", # Fyrsta persóna / first person
        "2P" : "p2", # Önnur persóna / second person
        "3P" : "p3", # Þriðja persóna / third person
        "OP" : "op", # Ópersónuleg sögn
        "GM" : "gm", # Germynd
        "MM" : "mm", # Miðmynd
        "SB" : "sb", # Sterk beyging
        "VB" : "vb", # Veik beyging
        "NH" : "nh", # Nafnháttur
        "FH" : "fh", # Framsöguháttur
        "BH" : "bh", # Boðháttur
        "LH" : "lh", # Lýsingarháttur (nútíðar)
        "VH" : "vh", # Viðtengingarháttur
        "NT" : "nt", # Nútíð
        "ÞT" : "þt", # Þátíð
        "SAGNB" : "sagnb", # Sagnbót ('vera' -> 'hefur verið')
        "SAGNB2" : "sagnb",
        "LHÞT" : "lhþt", # Lýsingarháttur þátíðar ('var lentur')
        "gr" : "gr", # Greinir
        "gr2" : "gr", # Greinir
    }

    # Create a list of BIN tags in descending order by length
    BIN_TAG_LIST = sorted(BIN_TO_VARIANT.keys(), key = lambda x: len(x), reverse = True)

    KIND_TO_TAG = {
        # !!! TBD: put in more precise tags
        "DATE" : "to",
        "TIME" : "to",
        "TIMESTAMP" : "to",
        "PUNCTUATION" : ""
    }

    CAT_TO_SCHEME = {
        "no" : "_n",
        "kk" : "_n",
        "kvk" : "_n",
        "hk" : "_n",
        "fn" : "_f",
        "abfn" : "_f",
        "pfn" : "_f",
        "gr" : "_g",
        "to" : "_t",
        "töl" : "_t",
        "tala" : "_number",
        "raðnr" : "_raðnr",
        "ártal" : "_year",
        "so" : "_s",
        "lo" : "_l",
        "ao" : "_a",
        "eo" : "_a",
        "fs" : "_a",
        "uh" : "_a",
        "st" : "_c",
        "stt" : "_c",
        "nhm" : "_c",
        "entity" : "_e",
        "prósenta" : "_t",
        "sérnafn" : "_n",
        "fyrirtæki" : "_n",
        "person" : "_n",
        "gata" : "_n"
    }

    FN_FL = {
        "sá": "a",
        "þessi": "a",
        "hinn": "a",
        "slíkur": "b",
        "sjálfur": "b",
        "samur": "b",
        "sami": "b", # ætti að vera samur
        "þvílíkur": "b",
        "minn": "e",
        "þinn": "e",
        "sinn": "e",
        "vor": "e",
        "einhver": "o",
        "sérhver": "o",
        "nokkur": "o",
        "allnokkur": "o",
        "hvorugur": "o",
        "allur": "o",
        "mestallur": "o",
        "flestallur": "o",
        "sumur": "o",
        "enginn": "o",
        "margur": "o",
        "flestir": "o", # æti að vera margur
        "einn": "o",
        "annar": "o",
        "neinn": "o",
        "sitthvað": "o",
        "ýmis": "o",
        "fáeinir": "o",
        "báðir": "o",
        "hver": "s",
        "hvor": "s",
        "hvaða": "s",
        "hvílíkur": "s"
    }
    FN_SAMFALL = { # Beygingarmyndir sem tilheyra bæði 'sá' og pfn.
        "það",
        "því",
        "þess",
        "þau",
        "þeir",
        "þá",
        "þær",
        "þeim",
        "þeirra"
    }
    FN_BÆÐI = { "sá", "það" }
    FN_PK = {
        "ég": "1",
        "þú": "2",
        "hann": "k",
        "hún": "v",
        "það": "h",
        "þér": "2",
        "vér": "1"
    }
    # Sjálfgefin fallstjórn forsetninga
    FS_FALL = {
        "frá" : "þ",
        "til" : "e",
        "í" : "þ",
        "að" : "þ",
        "vegna" : "e",
        "af" : "þ",
        "á" : "o",
        "með" : "þ",
        "um" : "o",
        "nær" : "þ",
        "utan" : "o",
        "innan" : "o",
        "við" : "o",
        "vestur" : "o",
        "austur" : "o",
        "suður" : "o",
        "norður" : "o",
        "gegnum" : "o",
        "meðal" : "e",
        "fyrir" : "o",
        "eftir" : "o"
    }

    def _n(self):
        return "n" + self._kyn() + self._tala() + self._fall() + self._greinir() + self._sérnöfn()

    def _l(self):
        return "l" + self._kyn() + self._tala() + self._fall() + self._beyging() + self._stig()

    def _f(self):
        return "f" + self._flokkur_f() + self._kyn_persóna() + self._tala() + self._fall()

    def _g(self):
        return "g" + self._kyn() + self._tala() + self._fall()

    def _t(self):
        return "t" + self._flokkur_t() + self._kyn() + self._tala(default = "f") + self._fall()

    def _s(self):
        if "lh" in self._tagset and "nt" in self._tagset:
            # Lýsingarháttur nútíðar
            return "slg" # Alltaf germynd - gæti hugsanlega verið miðmynd
        if "lhþt" in self._tagset:
            # Lýsingarháttur þátíðar
            return "sþ" + self._mynd() + self._kyn() + self._tala() + self._fall()
        if "nh" in self._tagset:
            # Nafnháttur
            if "þt" in self._tagset:
                return "sn" + self._mynd() + "--þ"
            return "sn" + self._mynd()
        if "bh" in self._tagset:
            # Boðháttur
            return "sb" + self._mynd() + "2" + self._tala() + "n" # Alltaf 2.p. nútíð
        if "sagnb" in self._tagset:
            # Sagnbót
            return "ss" + self._mynd()
        return "s" + self._háttur() + self._mynd() + self._persóna() + self._tala() + self._tíð()

    def _a(self):
        return "a" + self._flokkur_a() + self._stig_a()

    def _c(self):
        return "c" + self._flokkur_c()

    def _e(self):
        if self._txt[0].isupper():
            return "nxex-s" # Sérnafn, óþekkt kyn, óþekkt fall
        return "e"

    def _x(self):
        return "x"

    def _number(self):
        return "tfkfn" if self._v == 11 or self._v % 10 != 1 else "tfken"

    def _raðnr(self):
        return "lxexsf" # Lýsingarorð, eintala, sterk beyging, frumstig. Kyn og fall óþekkt

    def _year(self):
        return "ta"

    def _kyn(self):
        if "kk" in self._tagset:
            return "k"
        if "kvk" in self._tagset:
            return "v"
        if "hk" in self._tagset:
            return "h"
        return "x"

    def _tala(self, default = "e"):
        if "ft" in self._tagset:
            return "f"
        elif "et" in self._tagset:
            return "e"
        return default

    def _fall(self, default = "n"):
        if "nf" in self._tagset:
            return "n"
        if "þf" in self._tagset:
            return "o"
        if "þgf" in self._tagset:
            return "þ"
        if "ef" in self._tagset:
            return "e"
        return default

    def _greinir(self):
        return "g" if "gr" in self._tagset else ""

    def _sérnöfn(self):
        if not self._stem:
            return ""
        if self._fl == "örn":
            return "-ö"
        if self._kind == "PERSON":
            return "-m"
        if self._kind == "CURRENCY":
            # !!! TBD
            return "e" if "gr" in self._tagset else "-e"
        return "-s" if self._stem[0].isupper() else ""

    def _stig(self):
        if "esb" in self._tagset or "evb" in self._tagset:
            return "e"
        if "mst" in self._tagset:
            return "m"
        return "f"

    def _beyging(self):
        if "fsb" in self._tagset or "esb" in self._tagset:
            return "s"
        if "fvb" in self._tagset or "evb" in self._tagset or "mst" in self._tagset:
            return "v"
        return "o"

    def _flokkur_f(self):
        if self._cat == "abfn":
            return "p" # ??? Hefði þetta ekki átt að vera "a"?
        #if self._txt in self.FN_SAMFALL and self._stem in self.FN_BÆÐI:
        #    return "p"
        if self._cat == "pfn":
            return "p"
        return self.FN_FL.get(self._stem, "x")

    def _kyn_persóna(self):
        if self._stem in self.FN_PK:
            return self.FN_PK[self._stem]
        if "kk" in self._tagset:
            return "k"
        if "kvk" in self._tagset:
            return "v"
        if "hk" in self._tagset:
            return "h"
        if "p1" in self._tagset:
            return "1"
        if "p2" in self._tagset:
            return "2"
        return "x"

    def _flokkur_t(self):
        if self._kind == "PERCENT":
            return "p"
        return "f"

    def _mynd(self):
        return "m" if "mm" in self._tagset else "g"

    def _háttur(self):
        #if "nh" in self._tagset:
        #    return "n"
        if "bh" in self._tagset:
            return "b"
        if "vh" in self._tagset:
            return "v"
        #if "sagnb" in self._tagset:
        #    return "s"
        if "lh" in self._tagset and "nt" in self._tagset:
            return "l"
        return "f"

    def _tíð(self):
        return "þ" if "þt" in self._tagset else "n"

    def _persóna(self):
        if "op" in self._tagset:
            return "3"
        if "p1" in self._tagset:
            return "1"
        if "p2" in self._tagset:
            return "2"
        return "3"

    def _stig_a(self):
        if "mst" in self._tagset:
            return "m"
        if "est" in self._tagset:
            return "e"
        return ""

    def _flokkur_a(self):
        if self._cat == "uh":
            return "u"
        if self._cat == "fs":
            return self._fall(default = self.FS_FALL.get(self._stem, "o"))
        return "a"

    def _flokkur_c(self):
        if self._first == "stt":
            # 'sem', 'er' as connective conjunctions
            return "t"
        if self._cat == "nhm":
            return "n"
        return ""

    def __init__(self, t):
        # Initialize the tagset from the token
        self._cache = None
        self._kind = t.get("k")
        self._cat = t.get("c")
        self._fl = t.get("f")
        self._txt = t.get("x")
        if self._txt:
            self._txt = self._txt.lower()
        self._stem = t.get("s")
        self._v = t.get("v")
        if "t" in t:
            # Terminal: assemble the variants
            a = t["t"].split("_")
            self._first = a[0]
            self._tagset = set(a[1:])
        else:
            self._first = None
            self._tagset = set()
        if self._cat in { "kk", "kvk", "hk" }:
            self._tagset.add(self._cat)
        if "b" in t:
            # Mix the BIN tags into the set
            beyging = t["b"]
            for bin_tag in self.BIN_TAG_LIST:
                # This loop proceeds in descending order by tag length
                if bin_tag in beyging:
                    self._tagset.add(self.BIN_TO_VARIANT[bin_tag])
                    beyging = beyging.replace(bin_tag, "")
                    beyging = beyging.replace("--", "")
                    if not beyging:
                        break

    def _tagstring(self):
        """ Calculate the IFD tagstring from the tagset """
        if self._kind in self.KIND_TO_TAG:
            return self.KIND_TO_TAG[self._kind]
        key = self._first or self._cat or self._kind
        scheme = self.CAT_TO_SCHEME.get(key)
        if scheme is None:
            return "[" + key + "]" # !!! TODO
        func = getattr(self, scheme)
        return scheme[1:] if func is None else func()

    def has_tag(self, tag):
        return tag in self._tagset

    def __str__(self):
        """ Return the tags formatted as an IFD compatible string """
        if self._cache is None:
            self._cache = self._tagstring()
        return self._cache
