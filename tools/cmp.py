#!/usr/bin/env python
# type: ignore
"""

    Greynir: Natural language processing for Icelandic

    POS tagging accuracy measurement tool

    Copyright (C) 2021 Miðeind ehf.
    Original author: Hulda Óladóttir

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


    This module allows measurement of POS tagging accuracy for Greynir
    against the Icelandic Frequency Database (IFD), which is a hand-tagged
    corpus containing various types of text.

    By default, the code uses localhost:5000 as a JSON API server to
    tag text via the /postag.api/v1?t=xxx URL. To specify a different server,
    set the TAGGER environment variable. For instance,

    TAGGER=greynir.is python tools/cmp.py

    will use the main https://greynir.is server as a POS tagger. It is
    also possible to avoid HTTP RPC and use local, in-process tagging by
    invoking

    TAGGER=local python tools/cmp.py

"""

import json
import xml.etree.ElementTree as ET
import os
import sys
import json
import urllib.request

from urllib.parse import quote
from timeit import default_timer as timer
from contextlib import contextmanager

# Hack to make this Python program executable from the tools subdirectory
basepath, _ = os.path.split(os.path.realpath(__file__))
_UTILS = os.sep + "tools"
if basepath.endswith(_UTILS):
    basepath = basepath[0:-len(_UTILS)]
    sys.path.append(basepath)

from reynir import Abbreviations
from settings import Settings, StaticPhrases
from treeutil import TreeUtility
from postagger import IFD_Tagset, IFD_Corpus
from tokenizer import canonicalize_token
from fastparser import Fast_Parser
from db import SessionContext


# Stuff for deciding which POS tagging server (and what method) we will use

TAGGER = os.environ.get("TAGGER", "localhost:5000")
USE_IFD_TAGGER = bool(os.environ.get("IFD", False))
POS_PATH = ""
IFD_PATH = ""
USE_LOCAL_TAGGER = False

if TAGGER.lower() == "local":
    # Use in-process tagger
    USE_LOCAL_TAGGER = True
    USE_IFD_TAGGER = False # !!! TODO: Currently can't use the IFD tagger locally
else:
    if TAGGER == "greynir.is":
        # Use the main Greynir server, explicitly over HTTPS
        IFD_PATH = "https://greynir.is/ifdtag.api/v1"
        POS_PATH = "https://greynir.is/postag.api/v1"
    else:
        # Use the given server, by default localhost:5000, over HTTP
        IFD_PATH = "http://" + TAGGER + "/ifdtag.api/v1"
        POS_PATH = "http://" + TAGGER + "/postag.api/v1"

# The directory where the IFD corpus files are located
IFD_DIR = "ifd" 


# GREINARMERKI = {"!", "(", ")", ",", "-", ".", "...", "/", ":", ";", "?", "[", "]", "«", "»"} # Öll greinarmerki sem koma fyrir í OTB
VINSTRI_GREINARMERKI = "([„«#$€<"
MIÐJA_GREINARMERKI = '"*&+=@©|—'
HÆGRI_GREINARMERKI = ".,:;)]!%?“»”’…°>–"
EKKI_GREINARMERKI = "-/'~‘\\"
GREINARMERKI = VINSTRI_GREINARMERKI + MIÐJA_GREINARMERKI + HÆGRI_GREINARMERKI + EKKI_GREINARMERKI
FLOKKAR = {
    "PERCENT": "tp", 
    "NUMBER": "to", 
    "YEAR": "to", 
    "ORDINAL": "to", 
    "DATE": "to",
    "TIME": "to",
    "TIMESTAMP": "to",
    "ENTITY": "e"
    }
BÍN_MAP = {
    "NFET": "en",
    "NFETgr": "eng",
    "NFET2": "en",
    "NFETgr2": "eng",
    "NFET3": "en",
    "NFETgr3": "eng",
    "ÞFET": "eo",
    "ÞFETgr": "eog",
    "ÞFET2": "eo",
    "ÞFETgr2": "eog",
    "ÞFET3": "eo",
    "ÞFETgr3": "eog",
    "ÞGFET": "eþ",
    "ÞGFETgr": "eþg",
    "ÞGFET2": "eþ",
    "ÞGFETgr2": "eþg",
    "ÞGFET3": "eþ",
    "ÞGFETgr3": "eþg",
    "EFET": "ee",
    "EFETgr": "eeg",
    "EFET2": "ee",
    "EFETgr2": "eeg",
    "EFET3": "ee",
    "EFETgr3": "eeg",
    "NFFT": "fn",
    "NFFTgr": "fng",
    "NFFT2": "fn",
    "NFFTgr2": "fng",
    "NFFT3": "fn",
    "NFFTgr3": "fng",
    "ÞFFT": "fo",
    "ÞFFTgr": "fog",
    "ÞFFT2": "fo",
    "ÞFFTgr2": "fog",
    "ÞFFT3": "fo",
    "ÞFFTgr3": "fog",
    "ÞGFFT": "fþ",
    "ÞGFFTgr": "fþg",
    "ÞGFFT2": "fþ",
    "ÞGFFTgr2": "fþg",
    "ÞGFFT3": "fþ",
    "ÞGFFTgr3": "fþg",
    "EFFT": "fe",
    "EFFTgr": "feg",
    "EFFT2": "fe",
    "EFFTgr2": "feg",
    "FSB": "sf",
    "ESB": "se",
    "FVB": "vf",
    "EVB": "ve",
    "MST": "vm",
    "MST2": "vm",
    "MSTSB": "sm",
    "KK": "k",
    "ET": "e",
    "FT": "f",
    "ET2": "e",
    "FT2": "f",
    "KVK": "v",
    "HK": "h",
    "1P": "1",
    "2P": "2",
    "3P": "3",
    "NT": "n",
    "ÞT": "þ",
    "FH": "f",
    "VH": "v",
    "OSKH": "v", # Óskháttur, varpast í vh.
    "SAGNB": "s",
    "SAGNB2": "s",
    "NH": "n",
    "BH": "b",
    "LH": "l",
    "LHÞT": "þ",
    "ST": "e", # Stýfður boðháttur, sendi í eintölu
    "ST2": "e",
    "GM": "g",
    "MM": "m",
    "NF": "n",
    "ÞF": "o",
    "ÞGF": "þ",
    "EF": "e",
    "SB": "s",
    "VB": "v"
}
GrToOTB = {
    "kvk": "v",
    "kk": "k",
    "hk": "h",
    "nf": "n",
    "þf": "o",
    "þgf": "þ",
    "ef": "e",
    "et": "e",
    "ft": "f"
}
OTB_einfaldað = {
    "ct": "c", # Tilvísunartengingar flokkaðar með almennum tengingum
    "ta": "to", # Eitt mark fyrir tölufasta
    "aþm": "am", # Atviksorð í miðstigi sem stjórnar falli; höndlað sem forsetning
    "aþe": "ae" # Atviksorð í efsta stigi sem stjórnar falli; höndlað sem forsetning
}
# Listi af orðum sem geta bæði verið atviksorð og forsetningar. Í einföldun fá þau sama markið, "af".
EO = {
    "af", "austan", "að", "bakvið", "eftir", "fjarri", "fjær", "fjærst", "fram", "framar", "framhjá", "framúr", 
    "fremur", "frá", "fyrir", "gagnvart", "gegn", "gegnum", "handan", "hjá", "inn", "innan", "inní", "jafnframt", 
    "jafnhliða", "kringum", "lengi", "með", "meðal", "milli", "mót", "móti", "neðan", "niðrí", "niður", "norðan", 
    "nálægt", "nær", "nærri", "næst", "ofan", "ofaná", "ofar", "samhliða", "samsíða", "samtímis", "snemma", "sunnan", 
    "síðla", "til", "um", "undan", "undir", "upp", "uppá", "uppí", "uppúr", "utan", "vegna", "vestan", "við", 
    "víðsfjarri", "yfir", "á", "án", "ásamt", "í", "óháð", "ólíkt", "úr", "út", "útaf", "útfrá", "útundan", "útá", "útí"
}

ÓRLEM = { # Óreglulegar lemmur úr IFD, allir möguleikar eru gefnir í gildinu.
    "barsmíð(i)": ["barsmíð", "barsmíði"],
    "dollar(i)": ["dollar", "dollari"],
    "eigin(n)": ["eigin", "eiginn"],
    "eilífðarvélarsmíð(i)": ["eilífðarvélarsmíð", "eilífðarvélarsmíði"],
    "ey(ja)": ["ey", "eyja"],
    "flott(ur)": ["flottur"],
    "gagnrýninn/-rýnn": ["gagnrýnn", "gagnrýninn"],
    "hentugleiki/-ur": ["hentugleiki", "hentugleikur"],
    "hólmi/-ur": ["hólmi", "hólmur"],
    "járnsmíð(i)": ["járnsmíði", "járnsmíð"],
    "kærleiki/-ur": ["kærleikur", "kærleiki"],
    "lær(i)": ["læri", "lær"],
    "meir(a)": ["meira", "meir"],
    "meiðsl(i)": ["meiðsl", "meiðsli"],
    "mey(ja)/mær": ["mey", "meyja", "mær"],
    "reip(i)": ["reip", "reipi"],
    "skipasmíð(i)": ["skipasmíð", "skipasmíði"],
    "skipssmíð(i)": ["skipssmíð", "skipssmíði"],
    "skólasystkin(i)": ["skólasystkin", "skólasystkini"],
    "slagorðasmíð(i)": ["slagorðasmíð", "slagorðasmíði"],
    "smyrsl(i)": ["smyrsl", "smyrsli"],
    "smáhólmi/-ur": ["smáhólmi", "smáhólmur"],
    "smíð(i)": ["smíð", "smíði"],
    "smók(ur)": ["smók", "smókur"],
    "systkin(i)": ["systkin", "systkini"],
    "tónsmíð(i)": ["tónsmíð", "tónsmíði"],
    "umlukinn/-luktur": ["umlukinn", "umluktur"],
    "ungmey(ja)/-mær": ["ungmey", "ungmeyja", "ungmær"],
    "Vigursystkin(i)": ["Vigursystkin", "Vigursystkini"],
    "éta/eta": ["éta", "eta"],
    "óbrennishólmi/-ur": ["óbrennishólmi", "óbrennishólmur"],
    "foreldri": ["foreldri", "foreldrar"]
}

# Skammstafanir í OTB sem hafa verið slitnar í sundur. Gildi er leiðrétt skammstöfun
SKST_LEIÐRÉTTAR = { 
    "a. m. k." : "a.m.k.", # að minnsta kosti
    "e. t. v." : "e.t.v.", # ef til vill
    "F. Í." : "F.Í.", # Ferðafélag Íslands
    "f. Kr." : "f.Kr.", # fyrir Krist
    "m. a." : "m.a.", # meðal annars
    "millj. kr." : "millj.kr.", #milljónir króna
    "o. fl." : "o.fl.", # og fleiri/fleira
    "o. s. frv." : "o.s.frv.", # og svo framvegis
    "o. þ. h." : "o.þ.h.", #og þess háttar
    "o. þ. u. l." : "o.þ.u.l.", # og því um líkt
    "s. s." : "s.s.", # svo sem
    "t. a. m." : "t.a.m.", # til að mynda
    "t. d." : "t.d.", # til dæmis
    "u. þ. b." : "u.þ.b.", # um það bil
    "m y. s." : "m y.s.", # metrar yfir sjávarmáli
    "þ. e. a. s." : "þ.e.a.s.", # það er að segja
    #þ.e. er sleppt hér, tekið sérstaklega fyrir síðar til að koma í veg fyrir rugling við "þ. e. a. s."
}

SKST_LENGD = {
    "a.m.k." : 3,
    "e.t.v." : 3,
    "F.Í." : 2,
    "f.Kr." : 2,
    "m.a." : 2,
    "millj.kr." : 2,
    "o.fl." : 2,
    "o.s.frv." : 3,
    "o.þ.h." : 3,
    "o.þ.u.l." : 4,
    "s.s." : 2,
    "t.a.m." : 3,
    "t.d." : 2,
    "u.þ.b." : 3,
    "y.s." : 2,     # Engin þörf á að sleppa "m"
    "þ.e." : 2,
    "þ.e.a.s." : 4,
}
 
class Corpus(IFD_Corpus):

    """ Override the IFD_Corpus class to enumerate the IFD files
        with verbose output """

    def __init__(self):
        super().__init__(ifd_dir = IFD_DIR)

    def starting_file(self, filename, count, num_files):
        """ Output a progress header when starting to read from a file """
        print("Skjal {} af {}".format(count, num_files))
        print("*******************", filename, "**************************")


class Tagger:

    """ A utility class that wraps local POS tagging functionality. """

    def __init__(self):
        self._parser = None
        self._session = None
        self._tagger = None

    def tag(self, text):
        """ Parse and POS-tag the given text, returning a dict """
        assert self._parser is not None, "Call Tagger.tag() inside 'with Tagger.session()'!"
        assert self._session is not None, "Call Tagger.tag() inside 'with Tagger.session()'!"
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
            err = any("err" in t for t in sent)
            for t in sent:
                canonicalize_token(t)
                if not err:
                    ifd_tagset = str(IFD_Tagset(t))
                    if ifd_tagset:
                        t["i"] = ifd_tagset
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

class Comparison():

    def __init__(self):
        self.ógreindar_setningar = 0 # Geymir fjölda setninga sem ekki tókst að greina
        self.réttar_setningar = 0 # Setningar þar sem öll mörk og allar lemmur eru réttar
        self.rangar_setningar = 0 # Setningar þar sem a.m.k. eitt rangt mark eða ein röng lemma fannst
        self.orð_vantar = 0 # Geymir heildarfjölda orða í setningum sem ekki tókst að greina
        self.rétt_orð = 0 # Bæði mark og lemma rétt
        self.röng_orð = 0 # Annaðhvort mark eða lemma rangt eða bæði
        self.LR = 0 # Réttar lemmur
        self.LW = 0 # Rangar lemmur
        self.MR = 0 # Rétt mörk
        self.MP = 0 # Hlutrétt mörk (rangur orðflokkur en rétt annað)
        self.MW = 0 # Röng mörk
        self.GR = 0 # Rétt greinarmerki (kemur inn í útreikninga fyrir lemmur og mörk)
        self.GW = 0 # Röng greinarmerki. Þau geta ekki verið hlutrétt
        self.M_confmat = {} # Lykill er (x,y), x = mark frá Greyni, y = mark frá OTB. Gildi er tíðnin. TODO útfæra confusion matrix f. niðurstöður
        self.setnf = 0
        self.stikk = None # Úttaksskrá
        self.CANNOT_PARSE = 0 # Number of sentences postag.api can't parse and sends to ifdtag.api (if postag.api is selected)

    def úrvinnsla_stikkprufa(self, tagger, sent):
        stikk = self.stikk
        assert stikk is not None
        self.setnf += 1
        rétt_setning = True
        orðalisti, mörk_OTB, lemmur_OTB = self.OTB_lestur(sent)
        if tagger is None:
            all_words, setning = self.json_lestur(orðalisti)
        else:
            all_words, setning = self.tag_lestur(tagger, orðalisti)
        if not all_words: # Ekkert svar fékkst fyrir setningu
            return
        # Tekst að greina setninguna?
        if self.error(all_words):
            return
        i = 0 # Index fyrir orðalistann.
        stikk.write(str(self.setnf)+". "+setning+"\n")
        stikk.flush()
        for word in all_words: # Komin á dict frá Greyni með öllum flokkunum.

            if i < len(orðalisti) and not orðalisti[i]: # Tómur hnútur fremst/aftast í setningu
                i += 1
            if i >= len(orðalisti):
                break

            skst = word["x"]
            if word["x"] == "-" and orðalisti[i] != "-": # Ef bandstrikið er greint sérstaklega # NÝTT
                stikk.write("Fann bandstrik, fer í næsta orð\n")
                stikk.flush()
                continue
            elif not lemmur_OTB[i]: # Greinarmerki
                stikk.write("Fann greinarmerki: {}\n".format(mörk_OTB[i]))
                stikk.flush()
                rétt_setning = rétt_setning & self.sbrGreinarmerki(mörk_OTB[i], word)
            elif orðalisti[i].endswith("-"):
                print("Fann svona orð, greini samt: {}".format(orðalisti[i]))
                rétt_setning = rétt_setning & self.skrif_stikkprufa(word, lemmur_OTB[i], mörk_OTB[i], i) # Bæði og mark og lemma rétt
                i += 1
                continue
            elif skst in SKST_LENGD: # Leiðréttar skammstafanir, þurfa sérmeðhöndlun # NÝTT
                stikk.write("Fann endurhæfða skammstöfun: {}\n".format(skst))
                stikk.flush()
                if Abbreviations.has_meaning(skst):
                    stikk.write("\tFann skst í Abbreviations\n")
                    stikk.flush()
                    rétt_setning = rétt_setning & self.margorða_stikkprufa(word, lemmur_OTB, mörk_OTB, i, Abbreviations.get_meaning(skst))
                else:
                    stikk.write("\tFann ekki skst í Abbreviations ---{}---\n".format(SKST_ÚTSKRIFAÐAR[skst]))
                    stikk.flush()
                i += SKST_LENGD[skst]
                if i >= (len(orðalisti) - 1):
                    stikk.write("Síðasta orð í streng, hætti\n")
                    stikk.flush()
                    break
                continue
            else:
                orð = word["x"]
                lengd = max(len(orð.split(" ")), len(orð.split("-"))) #TODO breyta ef stuðningur við orð með bandstriki er útfærður.
                if lengd > 1: # Fleiri en eitt orð í streng Greynis
                    stikk.write("Fann margorða eind í Greyni: {}\n".format(word["x"]))
                    stikk.flush()
                    if StaticPhrases.has_details(word["x"].lower()): # Margorða frasi, fæ mörk úr orðabók, lemmur líka.
                        stikk.write("Fann í StaticPhrases\n")
                        stikk.flush()
                        rétt_setning = rétt_setning & self.margorða_stikkprufa(word, lemmur_OTB, mörk_OTB, i, None)
                        i += lengd
                        if i >= (len(orðalisti) - 1): #Getur gerst ef síðasta orð í streng
                            stikk.write("Síðasta orð í streng, hætti\n")
                            stikk.flush()
                            break
                        continue
                    else:
                        stikk.write("Fann ekki í MARGORÐA\n")
                        stikk.flush()
                    i = i + lengd -1 # Enda á síðasta orði í frasa
                    if i >= (len(orðalisti) - 1): #Getur gerst ef síðasta orð í streng
                        stikk.write("Síðasta orð í streng, hætti\n")
                        stikk.flush()
                        break
                elif not orðalisti[i].endswith(word["x"]): # orði skipt upp í Greyni en ekki OTB
                    stikk.write("Orði skipt upp í Greyni ({}) en ekki OTB ({})\n".format(word["x"], orðalisti[i]))
                    stikk.flush()
                    continue #Hægir mikið á öllu, e-r betri leið?
                if ("k" in word and (word["k"] == "PUNCTUATION" or word["k"] == "UNKNOWN")) \
                    or ("t" in word and word["t"] == "no"):
                    # Einstaka tilvik. PUNCTUATION hér er t.d. bandstrik sem OTB heldur í orðum en Greynir greinir sem stakt orð
                    i += 1
                    print("Eitthvað skrýtið á ferðinni. {}  -  {}\n".format(word["k"], word["x"]))
                    stikk.write("Eitthvað skrýtið á ferðinni. {}  -  {}\n".format(word["k"], word["x"]))
                    stikk.flush()
                    continue
                rétt_setning = rétt_setning & self.skrif_stikkprufa(word, lemmur_OTB[i], mörk_OTB[i], i) # Bæði og mark og lemma rétt
            stikk.write("\t\tEyk við i og held áfram!\n")
            stikk.flush()
            i += 1
        if rétt_setning:
            self.réttar_setningar += 1
        else:
            self.rangar_setningar += 1
        stikk.flush()

    def úrvinnsla(self, tagger, sent):
        self.setnf += 1
        rétt_setning = True
        orðalisti, mörk_OTB, lemmur_OTB = self.OTB_lestur(sent)
        if tagger is None:
            all_words, setning = self.json_lestur(orðalisti)
        else:
            all_words, setning = self.tag_lestur(tagger, orðalisti)
        if not all_words: # Ekkert svar fékkst fyrir setningu
            return
        # Tekst að greina setninguna?
        if self.error(all_words):
            return
        i = 0 # Index fyrir orðalistann.
        for word in all_words: # Komin á dict frá Greyni með öllum flokkunum.
            if i < len(orðalisti) and not orðalisti[i]: # Tómur hnútur fremst/aftast í setningu
                i += 1
            if i >= len(orðalisti):
                break

            if word["x"] == "Eiríkur Tse" or word["x"] == "Vincent Peale": # Ljót sértilvik þar sem OTB og Greynir skipta í tóka á ólíkan máta.
                i += 1
                continue
            if word["x"] == "-" and orðalisti[i] != "-": # Ef bandstrikið er greint sérstaklega
                continue
            skst = word["x"]
            if not lemmur_OTB[i]: # Greinarmerki
                rétt_setning = rétt_setning & self.sbrGreinarmerki(mörk_OTB[i], word)
            elif orðalisti[i].endswith("-"):
                print("Fann svona orð, greini samt: {}".format(orðalisti[i]))
                rétt_setning = rétt_setning & self.skrif_allt(word, lemmur_OTB[i], mörk_OTB[i], i) # Bæði og mark og lemma rétt
                i += 1
                continue
            elif skst in SKST_LENGD: # Leiðréttar skammstafanir, þurfa sérmeðhöndlun # NÝTT
                if Abbreviations.has_meaning(skst):
                    rétt_setning = rétt_setning & self.margorða_allt(word, lemmur_OTB, mörk_OTB, i, Abbreviations.get_meaning(skst))
                i += SKST_LENGD[skst]
                if i >= (len(orðalisti) - 1):
                    break
                continue
            else:
                lengd = max(len(word["x"].split(" ")), len(word["x"].split("-"))) #TODO breyta ef stuðningur við orð með bandstriki er útfærður.
                if lengd > 1: # Fleiri en eitt orð í streng Greynis # TODO breyta þegar set dict með MWE inn
                    if StaticPhrases.has_details(word["x"].lower()): # Margorða frasi, fæ mörk úr orðabók, lemmur líka.
                        rétt_setning = rétt_setning & self.margorða_allt(word, lemmur_OTB, mörk_OTB, i, None)
                        i += lengd
                        continue
                    i = i + lengd - 1 # Enda á síðasta orði í frasa # TODO taka þetta út?
                elif not orðalisti[i].endswith(word["x"]): # orði skipt upp í Greyni en ekki OTB
                    continue #Hægir mikið á öllu, e-r betri leið?
                if ("k" in word and (word["k"] == "PUNCTUATION" or word["k"] == "UNKNOWN")) \
                    or ("t" in word and word["t"] == "no"):
                    #print("Eitthvað skrýtið á ferðinni. {}\n\t{}\n".format(setning, word["x"]))
                    # Einstaka tilvik. PUNCTUATION hér er t.d. bandstrik sem OTB heldur í orðum en Greynir greinir sem stakt orð
                    i += 1
                    continue
                rétt_setning = rétt_setning & self.skrif_allt(word, lemmur_OTB[i], mörk_OTB[i], i) # Bæði og mark og lemma rétt
            i += 1
        if rétt_setning:
            self.réttar_setningar += 1
        else:
            self.rangar_setningar += 1

    def margorða_stikkprufa(self, word, lemmur_OTB, mörk_OTB, i, one):
        stikk = self.stikk
        assert stikk is not None
        wx = word["x"].lower() if not one else one
        if wx == "milljónir króna":
            mörk_Gr = "nvfþ nvfe"
            lemmur_Gr = "milljón króna"
        else:
            mörk_Gr = StaticPhrases.tags(wx)
            lemmur_Gr = StaticPhrases.lemmas(wx)
        öll_orð = wx.replace("-", " ").split()
        allt = zip(öll_orð, lemmur_Gr, mörk_Gr)
        rétt = True # Finnst eitthvað rangt í liðnum?
        for orð, lemma_Gr, mark_Gr in allt:
            lemma_bool = True
            mark_bool = True
            lemma_OTB = lemmur_OTB[i]
            mark_OTB = mörk_OTB[i]
            stikk.write(orð+"\n")
            stikk.write("\tLemma OTB: '{}'\tLemma Gr: '{}'\n".format(lemma_OTB, lemma_Gr))
            stikk.flush()
            if lemma_Gr == lemma_OTB:
                self.LR += 1
                lemma_bool = True
                stikk.write("\tRétt lemma\n")
                stikk.flush()
            else:
                self.LW += 1
                lemma_bool = False
                rétt = False
                stikk.write("\tRöng lemma\n")
                stikk.flush()
            stikk.write("\tMark OTB: '{}'\tMark GR: '{}'\n".format(mark_OTB, mark_Gr))
            stikk.flush()
            if orð in EO and mark_Gr[0] == "a": # Getur verið bæði forsetning og atviksorð
                if mark_OTB != "cn": #nafnháttarmerki
                    mark_OTB = "af"
                mark_Gr = "af"
            if mark_Gr and mark_OTB and mark_Gr[0] == mark_OTB[0]: # Sami orðflokkur
                if mark_Gr == mark_OTB:
                    self.MR += 1
                    stikk.write("\tRétt mark\n")
                    stikk.flush()
                else:
                    self.MP += 1
                    mark_bool = False
                    stikk.write("\tHlutrétt mark\n")
                    stikk.flush()
            else:
                self.MW += 1
                mark_bool = False
                stikk.write("\tRangt mark\n")
                stikk.flush()
            i += 1
            if lemma_bool and mark_bool: # Bæði mark og lemma rétt
                self.rétt_orð += 1
            else:
                self.röng_orð += 1
        stikk.flush()
        return rétt

    def margorða_allt(self, word, lemmur_OTB, mörk_OTB, i, one):
        wx = word["x"].lower() if not one else one
        if wx == "milljónir króna":
            mörk_Gr = "nvfþ nvfe"
            lemmur_Gr = "milljón króna"
        else:
            mörk_Gr = StaticPhrases.tags(wx)
            lemmur_Gr = StaticPhrases.lemmas(wx)
        öll_orð = wx.replace("-", " ").split()
        #print(word["x"])
        allt = zip(öll_orð, lemmur_Gr, mörk_Gr)
        rétt = True # Finnst eitthvað rangt í liðnum?
        for orð, lemma_Gr, mark_Gr in allt:
            lemma_bool = True
            mark_bool = True
            lemma_OTB = lemmur_OTB[i]
            mark_OTB = mörk_OTB[i]
            if lemma_Gr == lemma_OTB:
                self.LR += 1
                lemma_bool = True
            else:
                self.LW += 1
                lemma_bool = False
                rétt = False
            if orð in EO and mark_Gr[0] == "a": # Getur verið bæði forsetning og atviksorð
                if mark_OTB != "cn": #nafnháttarmerki
                    mark_OTB = "af"
                mark_Gr = "af"
            if mark_Gr and mark_OTB and mark_Gr[0] == mark_OTB[0]: # Sami orðflokkur
                if mark_Gr == mark_OTB:
                    self.MR += 1
                else:
                    self.MP += 1
                    mark_bool = False
            else:
                self.MW += 1
                mark_bool = False
            i += 1
            if lemma_bool and mark_bool: # Bæði mark og lemma rétt
                self.rétt_orð += 1
            else:
                self.röng_orð += 1
        return rétt
 
    def skrif_stikkprufa(self, word, lemma_OTB, mark_OTB, i):
        #Samanburður fer fram hér, safna tvenndum fyrir mörk í orðabók ásamt tíðni fyrir confusion matrix - TODO confmat
        # Safna í allar tölfræðibreyturnar
        stikk = self.stikk
        assert stikk is not None
        stikk.write(word["x"]+"\n")
        stikk.flush()
        if "s" in word:
            stikk.write("\tLemma OTB: '{}'\tLemma Gr: '{}'\n".format(lemma_OTB, word["s"]))
            stikk.flush()
        else:
            stikk.write("\tLemma OTB: '{}'\tLemma Gr: '{}'\n".format(lemma_OTB, word["x"].lower()))
            stikk.flush()
        lemma_bool = self.sbrlemma(lemma_OTB, word)
        if lemma_bool:
            stikk.write("\tRétt lemma\n")
            stikk.flush()
        else:
            stikk.write("\tRöng lemma\n")
            stikk.flush()
        mark_skil, mark_Gr = self.sbrmark(mark_OTB, word, i) # 0 = Rangt, 1 = Rétt, 2 = Hlutrétt
        stikk.write("\tMark OTB: '{}'\tMark GR: '{}'\n".format(mark_OTB, mark_Gr))
        stikk.flush()
        if mark_skil == 0:
            stikk.write("\tRangt mark\n")
            stikk.flush()
        elif mark_skil == 1:
            stikk.write("\tRétt mark\n")
            stikk.flush()
        elif mark_skil == 2:
            stikk.write("\tHlutrétt mark\n")
            stikk.flush()
        else:
            stikk.write("\tÓgild niðurstaða!\n")
            stikk.flush()
        stikk.flush()
        if lemma_bool and mark_skil > 0:
            self.rétt_orð += 1
            return True
        else:
            self.röng_orð += 1
            return False

    def skrif_allt(self, word, lemma_OTB, mark_OTB, i):
        #Samanburður fer fram hér, safna tvenndum fyrir mörk í orðabók ásamt tíðni fyrir confusion matrix - TODO confmat
        # Safna í allar tölfræðibreyturnar
        lemma_bool = self.sbrlemma(lemma_OTB, word)
        mark_skil, mark_Gr = self.sbrmark(mark_OTB, word, i) # 0 = Rangt, 1 = Rétt, 2 = Hlutrétt
        if lemma_bool and mark_skil > 0:
            self.rétt_orð += 1
            return True
        else:
            self.röng_orð += 1
            return False

    def vörpun(self, word):
        # Skilar orðflokki og frekari greiningu.
        # k = tegund, x = upprunalegt orð, s = orðstofn, c = orðflokkur, b = beygingarform, t = lauf, v = gildi, f = flokkur í BÍN
        greining = []   # Geymir vörpun á marki orðsins sem er sambærileg marki í OTB
        # Varpa í réttan orðflokk
        if word["k"] in FLOKKAR: 
            return FLOKKAR[word["k"]]
        elif "CURRENCY" in word["k"]:
            # greining = orðfl.+kyn+tala+fall+sérnafn  
            uppl = word["t"].split("_") # [0]: orðfl, [1]: tala [2]: fall, [3]: kyn
            greining.append("n") # orðflokkur
            # TODO breyta í BÍN mörk! Hvað kemur þar fram?
            if "gr" in uppl:
                uppl.remove("gr") #TODO get tekið út þegar samræmi mörkin. Sértilvik.
            greining.append(GrToOTB[uppl[3]]) # kyn
            greining.append(GrToOTB[uppl[1]]) # tala
            greining.append(GrToOTB[uppl[2]]) # fall
            greining.append("-e") # sérnafn
            return "".join(greining)
        elif "PERSON" in word["k"]:
            # TODO hvað sýnir BÍN?
            greining.append("n") # orðflokkur
            uppl = word["t"].split("_") # [0]: person, [1]: fall, [2]: kyn
            if "g" in word:
                kyn = word["g"]
            elif len(uppl) > 2:
                kyn = uppl[2]
            else:
                kyn = None # !!! Nota eitthvað kyn sem sjálfgefið?
            if kyn is not None:
                greining.append(GrToOTB[kyn])
            greining.append("e") # tala - G.r.f. eintölu
            greining.append(GrToOTB[uppl[1]]) # fall
            greining.append("-e") # G.r.f. engum greini
            return "".join(greining)
        elif "t" in word and "sérnafn" in word["t"]: # Samræma sérnöfnin í Greyni
            return "nxxn-e"
        if "c" in word:
            tegund = word["c"] #Sýnir orðflokk, á eftir að varpa í rétt.
        else:
            if "t" not in word: # Skrýtnar skammstafanir, TODO ætti að lagast þegar fleiri skammstöfunum hefur verið bætt við Main.conf
                return "x"
            if word["t"].split("_")[0] == "no": # Ekkert BÍN-mark. Stafsetningarvillur og annað
                #print("Hvað gerist hér??", word["t"], word["x"]) 
                tegund = word["t"].split("_")[-1]
                if "b" in word:
                    print("\tb:", word["b"])
            else:   # Ætti ekki að koma fyrir
                print("???", word["x"], word["k"], word["t"]) 
                if "b" in word:
                    print("b:", word["b"])
        if tegund in { "kvk","kk","hk" }: # Nafnorð
            greining.append("n") # orðflokkur
            # greining = orðfl.+kyn+tala+fall(+greinir)(+sérnafn)
            greining.append(GrToOTB[tegund]) #kyn
            if "b" not in word or word["b"] == "-": # Skammstöfun, einstakir stafir, ...? Fæ uppl. frá Greyni
                uppl = word["t"].split("_") # [0]: orðfl, [1]: tala, [2]: fall, [3] kyn
                if len(uppl) < 3:
                    return "x" # Aðrar skammstafanir
                greining.append(GrToOTB[uppl[1]]) # tala
                greining.append(GrToOTB[uppl[2]]) # fall
                return "".join(greining)
            greining.append(BÍN_MAP[word["b"]])  #tala+fall
            if ("f" in word and "örn" in word["f"] or "lönd" in word["f"] or "ism" in word["f"] or "föð" in word["f"] or "móð" in word["f"] or "göt" in word["f"]) or ("s" in word and word["s"][0].isupper()): # örnefni, lönd, mannanöfn, götuheiti, orð með stórum staf...
                if "b" in word and "gr" in word["b"]:
                    greining.append("e")
                else:
                    greining.append("-e")
            greining = "".join(greining)
        elif tegund == "lo": # Lýsingarorð
            greining.append("l")
            #greining = orðfl+kyn+tala+fall+beyging+stig
            formdeildir = word["b"].split("-") # [0]: stig+beyging, [1]: kyn, [2]: fall+tala
            if len(formdeildir) == 2: #Raðtala; [0]: kyn, [1]: fall+tala
                greining.extend(self.kyntalafall(formdeildir))
                greining.append("vf")
                return "".join(greining)
            greining.append(BÍN_MAP[formdeildir[1]]) # kyn
            greining.append(BÍN_MAP[formdeildir[2].strip()]) # meiru, fleiru, fleirum
            greining.append(BÍN_MAP[formdeildir[0]]) # stig + beyging
            greining = "".join(greining)
        elif tegund == "fn": # Fornöfn
            # ábfn., óákv.ábfn., efn., óákv.fn., spfn.
            # greining = orðfl+undirflokkur+kyn+tala+fall
            greining.append(self.undirflokkun(word))
            formdeildir = word["b"].replace("fn_", "").replace("-", "_").split("_") # [0]: kyn, [1]: fall+tala
            greining.extend(self.kyntalafall(formdeildir))
            greining = "".join(greining)
        elif tegund == "pfn": #persónufornöfn
            # greining = orðfl+undirfl+kyn/persóna+tala+fall
            greining.append(self.pk(word)) # orðfl.+ndirfkyn/persóna
            greining.append(BÍN_MAP[word["b"]]) # tala+fall
            greining = "".join(greining)
        elif tegund == "abfn": # Afturbeygð fornöfn
            greining.append("fpxe") # OTB greinir sem pfn. með kyni. Ég hef ekki.
            greining.append(BÍN_MAP[word["b"]]) # fall
            greining = "".join(greining)
        elif tegund == "gr": # Greinir
            #greining = orðfl+kyn+tala+fall
            # TODO skoða reglur
            greining.append("g")
            formdeildir = word["b"].split("_") # [0]]: kyn, [1]: fall+tala
            greining.extend(self.kyntalafall(formdeildir))
            greining = "".join(greining)
        elif tegund == "to": # Önnur töluorð
            greining.append("tf")
            # greining = orðfl+kyn+tala+fall
            formdeildir = word["b"].split("_") # [0]]: kyn, [1]: fall+tala
            greining.extend(self.kyntalafall(formdeildir))
            greining = "".join(greining)
        elif tegund == "so": # Sagnorð
            greining.append("s") # orðflokkur
            formdeildir = word["b"].split("-") 
            if formdeildir[0] == "LHÞT": #lh.þt.
                # greining = orðfl+háttur+mynd+kyn+tala+fall
                # lh.þt.: [0]: háttur+tíð, [1]: beyging, [2]: kyn, [3]: fall+tala
                greining.append("þg") # háttur og mynd, TODO fæ hvergi fram frá Greyni. Germynd er default.
                greining.append(BÍN_MAP[formdeildir[2]]) # kyn
                greining.append(BÍN_MAP[formdeildir[3]]) # tala+fall
                greining = "".join(greining)
            elif formdeildir[0] == "LH": #lh.nt.
                # greining = orðfl+háttur+mynd
                # lh.nt.: [0]: háttur, [1]: tíð
                greining = "slg" #TODO mynd kemur hvergi fram, set g í staðinn. "m" er alger undantekning.
            elif "SAGNB" in formdeildir[1]: # sagnbót. Bæði SAGNB og SAGNB2
                # greining = orðfl+háttur+mynd
                # sagnb.: [0]: mynd, [1]: háttur
                greining.extend(self.hátturmynd(formdeildir)) # háttur+mynd
                greining = "".join(greining)
            elif formdeildir[1] == "NH": #nh.
                # greining = orðfl+háttur+mynd(+"--þ" ef þátíð)
                # nh.: [0]: mynd, [1]: háttur, [2]: tíð ef til staðar(mundu, vildu, ...)
                greining.extend(self.hátturmynd(formdeildir)) # háttur+mynd
                if len(formdeildir) == 3: #þátíð
                    greining.append("--þ")
                greining = "".join(greining)
            elif formdeildir[1] == "BH": #bh.
                # greining = orðfl+háttur+mynd+persóna+tala+tíð
                # bh.: [0]: mynd, [1]: háttur, [2]: tala/stýfður
                greining.extend(self.hátturmynd(formdeildir)) # háttur+mynd
                greining.append("2en") # TODO persóna, tala og tíð koma hvergi fram í BÍN eða Greyni. Default er 1.p.et.nt. = 1en
                greining = "".join(greining)
            elif formdeildir[0] == "OP": # ópersónulegar sagnir
                # fh. og vh.: [0]: "OP" [1]: mynd, [2]: háttur, [3]: tíð, [4]: persóna, [5]: tala
                #greining = orðfl+háttur+mynd+persóna+tala+tíð
                greining.append(BÍN_MAP[formdeildir[2]]) # háttur
                greining.append(BÍN_MAP[formdeildir[1]]) # mynd
                greining.append("3") # persóna, alltaf 3. persóna
                greining.append(BÍN_MAP[formdeildir[5]]) # tala
                greining.append(BÍN_MAP[formdeildir[3]]) # tíð
                greining = "".join(greining)
            else: #fh. og vh. eða skammstafaðar sagnir
                # greining = orðfl+háttur+mynd+persóna+tala+tíð
                # fh. og vh.: [0]: mynd, [1]: háttur, [2]: tíð, [3]: persóna, [4]: tala
                # Ath. óskháttur varpast í vh.
                if word["b"] == "-" and word["t"] == "so": #Undantekningartilvik
                    return "sxxxxx"
                greining.extend(self.hátturmynd(formdeildir)) # háttur+mynd
                greining.append(BÍN_MAP[formdeildir[3]]) # persóna
                greining.append(BÍN_MAP[formdeildir[4]]) # tala
                greining.append(BÍN_MAP[formdeildir[2]]) # tíð
                greining = "".join(greining)
        elif tegund == "ao":
            greining = "aa"
            # greining = orðfl+stig
            # TODO næ ekki að merkja upphrópanir.
            if "MST" in word["b"]:
                greining = "aam"
            elif "EST" in word["b"]:
                greining = "aae"
            else:
                greining = "aa"
        elif tegund == "fs":
            greining.append("a")
            formdeildir = word["t"].split("_")
            if len(formdeildir) == 1: #vantar stýringu, get tekið út þegar hef samræmt Greynismörk - # TODO útfæra fyrir hvert og eitt núna
                greining.append("x")
            else:
                greining.append(GrToOTB[formdeildir[1]]) #stýring
            greining = "".join(greining)
        elif tegund == "st":
            return "c"
        elif tegund == "stt":
            return "ct"
        elif tegund == "nhm":
            return "cn"
        elif tegund == "töl": # TODO hvert er samband þessara töluorða við önnur töluorð?
            return "to"
        elif tegund == "uh":
            return "au"
        else:
            #print("Finn ekki greiningu:", tegund, word["k"], word["t"], word["x"])
            #if "b" in word:
                #print(word["b"])
            pass
        return greining

    def setningabygging(self, orðalisti):
        setning = []
        bil = True # Bil á undan núverandi staki
        for item in orðalisti:
            if not item: # Tómur hnútur fremst/aftast í setningu
                continue
            elif item in VINSTRI_GREINARMERKI: # Ekkert bil á eftir
                if bil:
                    setning.append(" ")
                setning.append(item)
                bil = False # Ekkert bil á eftir þessu
            elif item in MIÐJA_GREINARMERKI: # Hvorki bil á undan né á eftir
                setning.append(item)
                bil = False
            elif item in HÆGRI_GREINARMERKI: # Ekki bil á undan
                setning.append(item)
                bil = True
            else: # Venjulegt orð, bil á undan og á eftir nema annað komi til
                if bil:
                    setning.append(" ")
                setning.append(item)
                bil = True
        setning_sameinuð = "".join(setning)
        for item in SKST_LEIÐRÉTTAR:
            if item in setning_sameinuð:
                setning_sameinuð = setning_sameinuð.replace(item, SKST_LEIÐRÉTTAR[item])
        if "þ. e." in setning_sameinuð: # Til að rugla ekki saman við "þ.e.a.s."
            setning_sameinuð = setning_sameinuð.replace("þ. e.", "þ.e.")
        return setning_sameinuð
 
    def sbrlemma(self, lemma_OTB, word):
        #Fyllir út í self.tíðnibreytur
        #print("LEMMA OTB: {}".format(lemma_OTB))
        lemma_OTB = lemma_OTB.lower()
        if "s" in word:
            lemma_Gr = word["s"].replace("-", "").lower()
        else:
            lemma_Gr = word["x"].replace("-", "").lower()
        if lemma_Gr == "sami": # Sértilvik, BÍN skiptir í sundur
            lemma_Gr = "samur"
        if lemma_OTB in ÓRLEM: # Óregluleg lemma, býður upp á marga möguleika
            if lemma_Gr in ÓRLEM[lemma_OTB]:
                self.LR += 1
                return True
            else:
                self.LW += 1
                return False
        if lemma_Gr == lemma_OTB:
            self.LR += 1
            return True
        else:
            self.LW += 1
            return False

    def sbrmark(self, mark_OTB, word, i):
        # Fyllir út í self.tíðnibreytur fyrir mörkunarárangur
        #mark_Gr_eldra = self.vörpun(word)

        mark_Gr = word["i"] if "i" in word else str(IFD_Tagset(word))
        stofn_Gr = (word["s"] if "s" in word else word["x"]).lower()
        #print("{0:20} {1:20} {2:10}  {d1} {3:10}  {d2} {4:10}".format(word.get("x", ""), word.get("s", ""),
        #    mark_OTB, mark_Gr_eldra, mark_Gr,
        #    d1="*" if mark_Gr_eldra != mark_OTB else " ",
        #    d2="*" if mark_Gr != mark_OTB else " "))

        #if mark_OTB in OTB_einfaldað: # ct, ta, aþe, aþm - Afbrigði 10, 17 og 20 í einföldun
        #    mark_OTB = OTB_einfaldað[mark_OTB]
        #if mark_Gr in OTB_einfaldað:
        #    mark_Gr = OTB_einfaldað[mark_Gr]

        if mark_OTB == "ct":    # Afbrigði 17
            mark_OTB = "c"
        if mark_Gr == "ct":
            mark_Gr = "c"

        if mark_OTB.startswith("n") and mark_OTB.endswith(("m", "s", "ö")): # undirflokkun sérnafna - Afbrigði 8
            mark_OTB = mark_OTB[:-1] + "e"
        if mark_Gr.startswith("n"):
            if mark_Gr.endswith(("m", "s", "ö")): # undirflokkun sérnafna
                mark_Gr = mark_Gr[:-1] + "e"
            elif i > 0 and word["x"][0].isupper(): # Nafnorð með stórum staf í miðri setningu sögð sérnöfn
                # Ath. tekur ekki tillit til greinarmerkja í upphafi setningar, sbr. "- Samning X"
                #print("Fann nýtt sérnafn - {} - {}".format(word["x"], i))
                if mark_Gr.endswith("g"):
                    mark_Gr = mark_Gr + "e"
                else:
                    mark_Gr = mark_Gr + "-e"
        #if mark_OTB.startswith("s"): # Afbrigði 13 í einföldun
        #    mark_OTB = mark_OTB[:1] + mark_OTB[2:]
        #if mark_Gr.startswith("s"):
        #    mark_Gr = mark_Gr[:1] + mark_Gr[2:]

        #if mark_OTB.startswith("l"): # Afbrigði 15 í einföldun
        #    mark_OTB = mark_OTB[:4] + mark_OTB[5:]
        #if mark_Gr.startswith("l"):
        #    mark_Gr = mark_Gr[:4] + mark_Gr[5:]

        if stofn_Gr in EO and mark_Gr[0] == "a": # Afbrigði 19 í einföldun
            mark_Gr = "af"
            if mark_OTB.startswith("a") or mark_OTB.startswith("f"):
                mark_OTB = "af"

        if stofn_Gr in {"sig", "sér", "sín"} and mark_Gr.startswith("fp"): # afbrigði 25 í einföldun
            if mark_OTB.startswith("fp"):
                mark_OTB = mark_OTB[:2] + mark_OTB[4:]
            mark_Gr = mark_Gr[:2] + mark_Gr[4:]
        
        if word["x"].lower() in self.SAMFALL and mark_Gr.startswith(("fp", "fa")):
            if mark_OTB.startswith(("fp", "fa")):
                mark_OTB = "fm" + mark_OTB[2:]
            mark_Gr = "fm" + mark_Gr[2:]            
        #if word["x"].lower() in self.SAMFALL and (stofn_Gr in self.BÆÐI): # Samfall 'sá' og pfn - Afbrigði 5
        #    mark_Gr = "fm" + mark_Gr[2:]            
        #    mark_OTB = "fm" + mark_OTB[2:]

        #if mark_Gr.startswith("f"): # Sleppa undirflokkun fornafna - Afbrigði 7
        #    mark_Gr = mark_Gr[:1] + mark_Gr[2:]
        #if mark_OTB.startswith("f"):
        #    mark_OTB = mark_OTB[:1] + mark_OTB[2:]
        
        #föll = {"ao", "aþ", "ae"}   # Afbrigði 21
        #if mark_Gr in föll:
        #    mark_Gr = "a"
        #if mark_OTB in föll:
        #    mark_OTB = "a"
        
        einnannar = {"einn": "p", "annar": "r"}
        if stofn_Gr in einnannar:  # Afbrigði 22-24B
            if mark_OTB.startswith("l"): # greint sem lýsingarorð
                mark_OTB = einnannar[stofn_Gr] + mark_OTB[1] + mark_OTB[2] + mark_OTB[3]
            elif mark_OTB.startswith("f") or mark_OTB.startswith("tf"):
                mark_OTB = einnannar[stofn_Gr] + mark_OTB[2:]

            if mark_Gr.startswith("l"): # greint sem lýsingarorð
                mark_Gr = einnannar[stofn_Gr] + mark_Gr[1] + mark_Gr[2] + mark_Gr[3]
            elif mark_Gr.startswith("f") or mark_Gr.startswith("tf"):
                mark_Gr = einnannar[stofn_Gr] + mark_Gr[2:]

        if stofn_Gr is "fyrstur": # OTB kallar það efsta stig, Greynir kallar frumstig.
            if mark_OTB.startswith("l") and mark_OTB.endswith("e"):
                mark_OTB = mark_OTB[:-1] + "e"


        #tvennd = (mark_Gr, mark_OTB) # TODO setja aftur inn ef útfæri confusion matrix
        #if tvennd in self.M_confmat:
            #self.M_confmat[tvennd] += 1
        #else:
            ##self.M_confmat[tvennd] = 1
        if mark_Gr and mark_OTB and mark_Gr[0] == mark_OTB[0]: #Sami orðflokkur
            # Athuga hvort annað í markinu sé rétt
            if mark_Gr == mark_OTB:
                self.MR += 1
                return 1, mark_Gr
            else:
                self.MP += 1
                return 2, mark_Gr
        else:
            self.MW += 1
            return 0, mark_Gr

    def sbrGreinarmerki(self, OTB, word):
        if "s" in word:
            lemma_Gr = word["s"]
        elif "x" in word:
            lemma_Gr = word["x"]
        else:
            #print("Lemma finnst ekki: {}".format(*word))
            self.GW += 1
            return False
        lemma_Gr = lemma_Gr.replace("—", "-").replace("…", "...")
        if lemma_Gr and OTB and lemma_Gr == OTB:
            self.GR += 1
            return True
        else:
            self.GW += 1
            return False

    def hátturmynd(self, bín):
        markhluti = []
        markhluti.append(BÍN_MAP[bín[1]])
        markhluti.append(BÍN_MAP[bín[0]])
        return markhluti

    def kyntalafall(self, bín):
        markhluti = []
        markhluti.append(BÍN_MAP[bín[0]])
        markhluti.append(BÍN_MAP[bín[1]])
        return "".join(markhluti)

    PK = {
        "ég": "1",
        "þú": "2",
        "hann": "k",
        "hún": "v",
        "það": "h" ,
        "þér": "2",
        "vér": "1"
    }

    def pk(self, word):
        # Greinir persónu eða kyn
        if "s" in word:
            return "fp" + self.PK[word["s"]]
        else:
            return "fp" + self.PK[word["x"].lower()] # Ætti ekki að gerast
  
    FL = {
        "sá": "fa",
        "þessi": "fa",
        "hinn": "fa",
        "slíkur": "fb",
        "sjálfur": "fb",
        "samur": "fb",
        "sami": "fb", # ætti að vera samur
        "þvílíkur": "fb",
        "minn": "fe",
        "þinn": "fe",
        "sinn": "fe",
        "vor": "fe",
        "einhver": "fo",
        "sérhver": "fo",
        "nokkur": "fo",
        "allnokkur": "fo",
        "hvorugur": "fo",
        "allur": "fo",
        "mestallur": "fo",
        "flestallur": "fo",
        "sumur": "fo",
        "enginn": "fo",
        "margur": "fo",
        "flestir": "fo", # æti að vera margur
        "einn": "fo",
        "annar": "fo",
        "neinn": "fo",
        "sitthvað": "fo",
        "ýmis": "fo",
        "fáeinir": "fo",
        "báðir": "fo",
        "hver": "fs",
        "hvor": "fs",
        "hvaða": "fs",
        "hvílíkur": "fs"
    }
    SAMFALL = { # Beygingarmyndir sem tilheyra bæði 'sá' og pfn.
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
    BÆÐI = { "sá", "það" }

    def undirflokkun(self, word):
        if word["x"].lower() in self.SAMFALL and (word["s"] in self.BÆÐI):
            return "fm"
        elif word["s"] in self.FL:
            return self.FL[word["s"]]
        return "fx"

    def json_lestur(self, orðalisti):
        """ Invoke a remote tagger over HTTP/HTTPS """
        setning = self.setningabygging(orðalisti)
        setning_slóð = quote(setning.strip())
        if USE_IFD_TAGGER:
            fullpath = IFD_PATH + "?t=" + setning_slóð
        else:
            fullpath = POS_PATH + "?t=" + setning_slóð
        #senda inn í httpkall og breyta í json-hlut
        try:
            with urllib.request.urlopen(fullpath) as response:
                string = response.read().decode('utf-8')
        except urllib.error.HTTPError as e:
            print("Error {0} requesting URL {1}, skipping...".format(e, fullpath))
            return [], ""
        json_obj = json.loads(string)
        all_words = json_obj["result"][0]

        convert_from_ifd = False
        if USE_IFD_TAGGER:
            convert_from_ifd = True
        elif any("err" in d for d in all_words):
            # POS tagger: error found, fall back to the IFD tagger
            print("Error from postag.api: falling back to ifdtag.api for sentence\n   '{0}'".format(setning))
            self.CANNOT_PARSE += 1
            fullpath = IFD_PATH + "?t=" + setning_slóð
            try:
                with urllib.request.urlopen(fullpath) as response:
                    string = response.read().decode('utf-8')
            except urllib.error.HTTPError as e:
                print("Error {0} requesting URL {1}, skipping...".format(e, fullpath))
                return [], ""
            json_obj = json.loads(string)
            all_words = json_obj["result"][0]
            convert_from_ifd = True

        if convert_from_ifd:
            # Convert ifdtag.api output to a format roughly compatible with postag.api
            converted = []
            for word, tag in all_words:
                if tag.isalnum() or ('-' in tag and tag != '-'): # Allow nken-s, etc.
                    # This is a proper IFD mark
                    converted.append(dict(x = word, i = tag, k = "WORD"))
                else:
                    # This is punctuation
                    converted.append(dict(x = word, k = "PUNCTUATION"))
            all_words = converted

        return all_words, setning
 
    def tag_lestur(self, tagger, orðalisti):
        """ Invoke a local tagger """
        setning = self.setningabygging(orðalisti)
        d = tagger.tag(setning.strip())
        all_words = d["result"][0]
        return all_words, setning

    def OTB_lestur(self, sent):
        return tuple(zip(*sent)) # Orð, mörk, lemmur
        #mörk_OTB = [word.get("type") for word in sent.iter()]
        #lemmur_OTB = [word.get("lemma") for word in sent.iter()]
        #orðalisti = [word.text.strip() for word in sent.iter()]
        #return mörk_OTB, lemmur_OTB, orðalisti

    def error(self, all_words):
        if USE_IFD_TAGGER:
            # Assume that there are no errors in IFD tagged sentences
            return False
        error = any("err" in y for y in all_words)
        if error:
            self.ógreindar_setningar += 1
            self.orð_vantar = self.orð_vantar + len(all_words) # Ath. þetta tekur greinarmerkin með.
            return True
        return False

    def prenta(self):
        # Prenta fyrst tíðni
        # Svo reikna nákvæmni, heimt, F-mælingu
        #Setningar
        print("")
        print("******************** NIÐURSTÖÐUR **********************")
        if POS_PATH:
            print("{} setningar voru sendar í ifdtag.api\n".format(self.CANNOT_PARSE))
        print("")
        print("Réttar setningar:", self.réttar_setningar)
        print("Rangar setningar:", self.rangar_setningar)
        print("Ógreindar setningar:", self.ógreindar_setningar)
        if self.réttar_setningar == 0:
            SA = 0
        else:
            SA = self.réttar_setningar / (self.réttar_setningar + self.rangar_setningar + self.ógreindar_setningar) # Accuracy
        print("Nákvæmni (accuracy): {:.4f}".format(SA))
        print("")
        #Orð
        print("Rétt orð:", self.rétt_orð)
        print("Röng orð:", self.röng_orð)
        print("Orð vantar:", self.orð_vantar)
        if self.rétt_orð == 0:
            OA = 0
        else:
            OA = self.rétt_orð / (self.rétt_orð + self.röng_orð + self.orð_vantar)
        print("Nákvæmni (accuracy): {:.4f}".format(OA))
        print("")
        #Lemmur
        print("Réttar lemmur:", self.LR)
        print("Rangar lemmur:", self.LW)
        if self.LR == 0:
            LA = 0
        else:
            LA = self.LR / (self.LR + self.LW + self.orð_vantar) # Nákvæmni (accuracy)
        print("Nákvæmni (accuracy): {:.4f}".format(LA))
        print("")
        #Mörk
        print("Rétt mörk:", self.MR)
        print("Hlutrétt mörk (réttur orðflokkur):", self.MP)
        print("Röng mörk:", self.MW)
        if self.MR == 0:
            MA, MPA = 0, 0
        else:
            MA = self.MR / (self.MR + self.MP + self.MW + self.orð_vantar)
            MPA = (self.MR + self.MP) / (self.MR + self.MP + self.MW + self.orð_vantar)
        print("Nákvæmni (accuracy): {:.4f}\tMeð hlutréttu: {:.4f}".format(MA, MPA))
        print("*******************************************************")

        print("")
        # Geymi eina breytu fyrir greinarmerki; geri ráð fyrir að ef markið er rétt er lemman það líka.
        print("*********** NIÐURSTÖÐUR MEÐ GREINARMERKJUM *************")
        print("Rétt greinarmerki:", self.GR)
        print("Röng greinarmerki:", self.GW)
        print("")
        # Orð
        print("Rétt orð:", str(self.rétt_orð + self.GR))
        print("Röng orð:", str(self.röng_orð + self.GW))
        print("Orð vantar:", self.orð_vantar)
        if (self.rétt_orð + self.GR) == 0:
            GOA = 0
        else:
            GOA = (self.rétt_orð + self.GR) / (self.rétt_orð + self.GR + self.GW + self.röng_orð + self.orð_vantar)
        print("Nákvæmni (accuracy): {:.4f}".format(GOA))
        print("")
        # Lemmur
        print("Réttar lemmur:", str(self.LR + self.GR))
        print("Rangar lemmur:", str(self.LW + self.GW))
        if (self.LR + self.GR) == 0:
            GLA = 0
        else:
            GLA = (self.LR + self.GR) / (self.LR + self.GR + self.LW + self.GW + self.orð_vantar)
        print("Nákvæmni (accuracy): {:.4f}".format(GLA))
        print("")
        # Mörk
        print("Rétt mörk:", str(self.MR + self.GR))
        print("Hlutrétt mörk (réttur orðflokkur):", self.MP)
        print("Röng mörk:", str(self.MW + self.GW))
        if self.MR == 0:
            GMA, GMPA = 0, 0
        else:
            GMA = (self.MR + self.GR) / (self.MR + self.MP + self.GR + self.GW + self.MW + self.orð_vantar)
            GMPA = (self.MR + self.GR + self.MP) / (self.MR + self.MP + self.GR + self.GW + self.MW + self.orð_vantar)
        print("Nákvæmni (accuracy): {:.4f}\tMeð hlutréttu: {:.4f}".format(GMA, GMPA))
        print("*******************************************************")

    def start(self, process_func, filter_func = None, skip_func = None):
        corpus = Corpus()
        sentences = corpus.raw_sentence_stream(filter_func = filter_func, skip = skip_func)
        if USE_LOCAL_TAGGER:
            # Call the Greynir POS tagger directly in-process
            with Tagger.session() as tagger:
                for sent in sentences:
                    process_func(tagger, sent)
        else:
            # Use the Greynir HTTP JSON API for POS tagging (/postag.api)
            for sent in sentences:
                process_func(None, sent)
        self.prenta()
   
    def start_stikkprufa(self):
        úrtak = 50
        with open("stikkprufa.txt", "w") as stikk:
            self.stikk = stikk
            self.start(self.úrvinnsla_stikkprufa, skip_func = lambda n: n % úrtak != 0)
            self.stikk = None
   
    def start_allt(self):
        self.start(self.úrvinnsla)

    def start_fyllimengi(self):
        úrtak = 50
        self.start(self.úrvinnsla, skip_func = lambda n: n % úrtak == 0)

def start_flokkar():
    corpus = Corpus()

    def _run_flokkar(tagger):

        def _run_flokkur(filter_func, description):
            sents = corpus.raw_sentence_stream(filter_func = filter_func)
            comp = Comparison()
            for sent in sents:
                comp.úrvinnsla(tagger, sent)
            print("*** Niðurstöður fyrir {0} ***".format(description))
            comp.prenta()

        # Íslensk skáldverk
        f = lambda x: x.startswith("A1")
        _run_flokkur(f, "íslensk skáldverk")

        # Ævisögur
        f = lambda x: x.startswith("A3")
        _run_flokkur(f, "ævisögur")

        # Fræðslutextar - hugvísindi
        f = lambda x: x.startswith("A4") and x[2] in {"A", "B", "C", "D", "E", "F", "G", "H", "J"}
        _run_flokkur(f, "fræðslutexta - hugvísindi")

        #Fræðslutextar - raunvísindi
        f = lambda x: x.startswith("A4") and x[2] in {"K", "M", "N", "O", "Q", "R", "S"}
        _run_flokkur(f, "fræðslutexta - raunvísindi")

        # Barna- og unglingabækur
        f = lambda x: x.startswith("A5")
        _run_flokkur(f, "barna- og unglingabækur")

    if USE_LOCAL_TAGGER:
        with Tagger.session() as tagger:
            _run_flokkar(tagger)
    else:
        _run_flokkar(None)



if __name__ == "__main__":
    Settings.read("config/Greynir.conf")
    print("\nCMP.PY Copyright (C) 2017 Miðeind ehf.\n"
        "Mæling á mörkunarárangri Greynis með íslenska orðtíðnisafnið IFD sem viðmið\n")
    #for thing in StaticPhrases.DETAILS:
    #    print(StaticPhrases.DETAILS[thing])
    if USE_IFD_TAGGER:
        print("Þjónustan ifdtag.api verður notuð til að marka texta")
        print("Vefslóð mörkunarþjóns er {}".format(IFD_PATH))
    elif POS_PATH:
        print("Þjónustan postag.api verður notuð til að marka texta")
        print("Vefslóð mörkunarþjóns er {}".format(POS_PATH))
    else:
        print("Staðbundið forritasafn verður notað til mörkunar")
    response = input("\nHvað viltu prófa? Stikkprufu (S), allan texta (A), allt nema stikkprufu (R) eða allt eftir flokkum (F)?\n").lower()
    byrjun = timer()
    if response == "s": # Stikkprufa
        comp = Comparison()
        comp.start_stikkprufa()
    elif response == "a": # Allan texta
        comp = Comparison()
        comp.start_allt()
    elif response == "r": # Allt nema stikkprufa
        comp = Comparison()
        comp.start_fyllimengi()
    elif response == "f": # Niðurstöðum skipt eftir flokkum
        start_flokkar()
    lok = timer()
    liðið = lok - byrjun
    print("")
    print("Keyrslan tók {:.1f} sekúndur, eða {:.1f} mínútur.".format(liðið, (liðið / 60.0)))
