"""
    Greynir: Natural language processing for Icelandic

    Tree processor module for extraction of person names and titles

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


    This module implements a processor for parsed sentence trees that
    extracts person names and titles.

    The processor consists of a set of functions, each having the base name (without
    variants) of a nonterminal in the Greynir context-free grammar. These functions
    will be invoked in turn during a depth-first traversal of the tree. The functions
    are called with three parameters:

    * node, which is the tree node corresponding to the function name. node.nt is
      the original nonterminal name being matched, with variants.

    * params, which is a list of positional parameters, where each is a dictionary
      of results from child nodes in the tree

    * result, which is a dictionary of result values from this nonterminal node.
      The dictionary comes pre-assigned with the following attributes/keys:

      _text: a string with the combined text of the child nodes
      _root: a string with the lemmas (word roots) of _text
      _nominative: a string with the words of _text in nominative case

      Additionally, the result dictionary contains an amalgamation of
      attributes/keys that were set by child nodes.

    A function can add attributes/keys to the result dictionary, passing them on to
    upper levels in the tree. If multiple children assign to the same attribute/key,
    the parent will receive the leftmost value - except in the case of lists,
    dictionaries and sets, which will be combined into one merged/extended value
    (again with left precedence in the case of dictionaries).

    --------------

    This particular processor collects information about persons and their titles.
    It handles structures such as:

    'Már Guðmundsson seðlabankastjóri segir að krónan sé sterk um þessar mundir.'
    --> name 'Már Guðmundsson', title 'seðlabankastjóri'

    'Jóhanna Dalberg, sölustjóri félagsins, telur ekki ástæðu til að örvænta.'
    --> name 'Jóhanna Dalberg', title 'sölustjóri félagsins'

    'Rætt var við Pál Eiríksson, sem leikur Gunnar á Hlíðarenda.'
    --> name 'Páll Eiríksson', title 'leikur Gunnar á Hlíðarenda'

    'Hetja dagsins var Guðrún Gunnarsdóttir (markvörður norska liðsins Brann)
    en hún átti stórleik.'
    --> name 'Guðrún Gunnarsdóttir', title 'markvörður norska liðsins Brann'

    TODO:

    Reassign prepositions that probably don't belong with names
        * Retain 'á'+þgf ('fulltrúi á loftslagsráðstefnunni')
        * Retain 'í'+þgf ('félagi í samtökunum')
        * Retain 'við'+þf ('dósent við Kaupmannahafnarháskóla')

"""

import re
from datetime import datetime
from typing import Any, cast

from reynir import NounPhrase

from db.models import Person

from queries import QueryStateDict
from tree import NonterminalNode, ParamList, Result, TreeStateDict


MODULE_NAME = __name__
PROCESSOR_TYPE = "tree"

INVALID_TITLES = {
    "sig",
    "væri",
    "orðið",
    "ávísun",
    "hér heima",
    "lán",
    "úr láni",
    "bar",
    "ver",
    "bætir",
    "býr",
    "get",
    "vera",
    "eiga",
    "var",
    "búa",
    "setur",
    "heggur",
    "átt",
    "keppa",
    "rétt",
    "ráðning",
    "sætti",
    "hlaut",
    "mynd",
    "myndband",
    "já",
    "nei",
    "segi",
    "sem",
    "hjónin",
    "verið",
    "lið",
    "munur",
    "verður",
    "gerði",
    "boðið",
    "leikur",
    "staðfesti",
    "veit",
    "hafi",
    "kona",
    "konan",
    "maður",
    "maðurinn",
    "slysið",
    "met",
    "frest",
    "sent",
}

# Phrases to cut off the ends of titles
CUT_ENDINGS = (
    "í tilkynningu",
    "í tilkynningunni",
    "í fréttatilkynningu",
    "í fréttatilkynningunni",
    "í afkomutilkynningu",
    "í afkomutilkynningunni",
    "í fjölmiðlum",
    "í samtali",
    "í samtalinu",
    "í viðtali",
    "í viðtalinu",
    "í Kastljósi",
    "í þættinum",
    "í grein",
    "í greininni",
    " sem",
    "-",
)

# Forskeyti sem klippt eru framan af streng og e.t.v. annað sett í staðinn
SEM_PREFIXES = [
    # Keep this in increasing order by length
    ("er", None),
    ("sé", None),
    ("var", None),
    ("væri", None),
    ("nú er", None),
    ("ekki er", "ekki"),
    ("ekki var", "var ekki"),
    ("mun vera", None),
    ("í dag er", None),
    ("ekki væri", "ekki"),
    ("einnig er", None),
    ("verið hefur", "hefur verið"),
    ("hefur verið", None),
]

# Textar sem ekki eru teknir gildir sem skýringar
NOT_EXPLANATION = {"myndskeið"}

DELIMITERS = {" )": " ( ", " ]": " [ ", " -": " - ", " ,": " , ", " .": " , "}


def article_begin(state: TreeStateDict) -> None:
    """Called at the beginning of article processing"""

    session = state["session"]  # Database session
    url = state["url"]  # URL of the article being processed
    # Delete all existing persons for this article
    ptab = cast(Any, Person).table()
    session.execute(ptab.delete().where(Person.article_url == url))


def article_end(state: TreeStateDict) -> None:
    """Called at the end of article processing"""
    pass


def sentence(state: QueryStateDict, result: Result) -> None:
    """Called at the end of sentence processing"""

    session = state["session"]  # Database session
    url = state["url"]  # URL of the article being processed
    authority = state.get("authority", 1.0)  # Authority of the source

    if "nöfn" in result:
        # Nöfn og titlar fundust í málsgreininni
        for nafn, titill, kyn in result.nöfn:
            print("Nafn: '{0}' Kyn: '{2}' Titill: '{1}'".format(nafn, titill, kyn))
            person = Person(
                article_url=url,
                name=nafn,
                # Try to get nominative form, otherwise fall back to raw text
                title=NounPhrase(titill).nominative or titill,
                title_lc=titill.lower(),
                gender=kyn,
                authority=authority,
                timestamp=datetime.utcnow(),
            )
            session.add(person)


def _add_name(result: Result, mannsnafn: str, titill: str, kyn: str) -> bool:
    """Add a name to the resulting name list"""
    if not titill:
        return False
    if " " not in mannsnafn:
        # We do not store single names
        return False
    if "..." in titill or "[" in titill:
        return False
    # Eliminate consecutive whitespace
    titill = re.sub(r"\s+", " ", titill.strip())
    # Cut off ending punctuation
    cut = True
    while titill and cut:
        cut = False
        while any(titill.endswith(p) for p in (" .", "..", " ,", " :", " !", " ?")):
            titill = titill[:-2]
            cut = True
        # Cut off common endings that don't belong in a title
        if titill:
            for s in CUT_ENDINGS:
                if titill.endswith(s):
                    titill = titill[: -len(s) - (0 if s[0] == " " else 1)]
                    cut = True
    if len(titill) <= 2 or titill.lower() in INVALID_TITLES:
        # Last security check
        return False
    if "nöfn" not in result:
        result.nöfn = []
    result.nöfn.append((mannsnafn, titill, kyn))
    return True


# Below are functions that have names corresponding to grammar nonterminals.
# They will be called during processing (depth-first) of a complete parsed
# tree for a sentence.


def Manneskja(node: NonterminalNode, params: ParamList, result: Result):
    """Mannsnafn, e.t.v. með titli"""
    # print("Mannsnafn: {0}".format(result["_text"]))
    result.del_attribs("efliður")
    if (
        "mannsnafn" in result
        and "titlar" in result
        and "kommu_titill" in result
        and "kyn" in result
    ):
        # Margir titlar innan kommu með 'og' á milli: bæta þeim við hverjum fyrir sig
        for titill in result.titlar:
            _add_name(result, result.mannsnafn, titill, result.kyn)
        result.del_attribs(
            ("mannsnafn", "titlar", "titill", "ekki_titill", "kommu_titill", "kyn")
        )


def Mannsnafn(node: NonterminalNode, params: ParamList, result: Result):
    result.mannsnafn = result._nominative
    if node.has_variant("kk"):
        result.kyn = "kk"
    elif node.has_variant("kvk"):
        result.kyn = "kvk"
    else:
        print("No gender for name {0}".format(result.mannsnafn))
        result.kyn = "hk"


def Titill(node: NonterminalNode, params: ParamList, result: Result):
    """Titill á eftir nafni"""
    # print("Titill: {0}".format(result["_text"]))
    if "ekki_titill" not in result:
        result.titill = result._text


def KommuTitill(node: NonterminalNode, params: ParamList, result: Result):
    """Ef titill er afmarkaður með kommum bætum við ekki eignarfallslið aftan á hann"""
    result.kommu_titill = True


def NlTitill(node: NonterminalNode, params: ParamList, result: Result):
    """Nafnliður titils"""
    # Fyrirbyggja að prósenta sé skilin sem titill
    if (
        len(params) == 1
        and "_tokentype" in params[0]
        and params[0]._tokentype == "PERCENT"
    ):
        result.ekki_titill = True


def EinnTitill(node: NonterminalNode, params: ParamList, result: Result):
    """Einn titill af hugsanlega fleirum í lista"""
    if "ekki_titill" not in result:
        result.titlar = [result._text]


def EfLiður(node: NonterminalNode, params: ParamList, result: Result):
    """Eignarfallsliður eftir nafnlið"""
    result.efliður = result._text
    # Leyfa eignarfallslið að standa óbreyttum í titli
    result._nominative = result._text
    # Ekki senda skýringu eða mannsnafn í gegn um eignarfallslið
    result.del_attribs(("skýring", "skýring_nafn", "mannsnafn", "kyn"))


def NlSérnafnEf(node: NonterminalNode, params: ParamList, result: Result):
    # Leyfa eignarfallslið að standa óbreyttum í titli
    result._nominative = result._text


def OkkarFramhald(node: NonterminalNode, params: ParamList, result: Result):
    # Ekki breyta eignarfallsliðum í nefnifall
    # Þetta grípur 'einn okkar', 'hvorugur þeirra'
    result._nominative = result._text


def AtviksliðurEinkunn(node: NonterminalNode, params: ParamList, result: Result):
    # Ekki breyta atviksliðum í nefnifall
    result._nominative = result._text


def FsLiður(node: NonterminalNode, params: ParamList, result: Result):
    """Forsetningarliður"""
    # Leyfa forsetningarlið að standa óbreyttum í titli
    result._nominative = result._text
    # Ekki leyfa skýringu eða mannsnafni að fara í gegn um forsetningarlið
    result.del_attribs(("skýring", "skýring_nafn", "skýring_kyn", "mannsnafn", "kyn"))


def Tengisetning(node: NonterminalNode, params: ParamList, result: Result):
    """Tengisetning ("sem" setning)"""
    # Ekki leyfa mannsnafni að fara í gegn um tengisetningu
    result.del_attribs(("mannsnafn", "kyn"))


def Setning(node: NonterminalNode, params: ParamList, result: Result):
    """Undirsetning: láta standa óbreytta"""
    result._nominative = result._text
    result.del_attribs(("skýring", "skýring_nafn", "skýring_kyn"))


def SetningSo(node: NonterminalNode, params: ParamList, result: Result):
    """Setning sem byrjar á sögn: eyða út"""
    result._text = ""
    result._nominative = ""
    result.del_attribs(("skýring", "skýring_nafn", "skýring_kyn"))


def SetningÁnF(node: NonterminalNode, params: ParamList, result: Result):
    """Ekki fara með skýringu upp úr setningu án frumlags"""
    result._nominative = result._text
    result.del_attribs(("skýring", "skýring_nafn", "skýring_kyn"))


def SvigaInnihaldNl(node: NonterminalNode, params: ParamList, result: Result):
    """Svigainnihald eða skýring sem er ekki í sama falli og foreldri: eyða út"""
    result._text = ""
    result._nominative = ""
    result.del_attribs(("skýring", "skýring_nafn", "skýring_kyn"))


def SvigaInnihald(node: NonterminalNode, params: ParamList, result: Result):
    """Ef innihald sviga er hrein yfirsetning, þá er það líklega ekki titill: eyða út"""
    if node.child_has_nt_base("HreinYfirsetning"):
        result._text = ""
        result._nominative = ""
        result.del_attribs(("skýring", "skýring_nafn", "skýring_kyn"))
    else:
        # Don't modify cases inside the explanation
        result._nominative = result._text


def NlSkýring(node: NonterminalNode, params: ParamList, result: Result):
    """Skýring nafnliðar (innan sviga eða komma)"""

    def cut(s: str) -> str:
        if s.startswith(", ") or s.startswith("( "):
            s = s[2:]
        while (
            s.endswith(" ,") or s.endswith(" )") or s.endswith(" .") or s.endswith(" (")
        ):
            s = s[:-2]
        return s

    s = cut(result._text)
    if s.startswith("sem "):
        # Jón, sem er heimsmethafi í hástökki,
        s = s[4:]
        for prefix, replacement in reversed(SEM_PREFIXES):
            if s.startswith(prefix + " "):
                if replacement:
                    s = replacement + " " + s[len(prefix) + 1 :]
                else:
                    s = s[len(prefix) + 1 :]
                break
        # Reverse word order such as "sem kallaður er" -> "er kallaður",
        # "sem talinn er líklegastur" -> "er talinn líklegastur"
        words = s.split()
        if len(words) > 2 and words[1] in {"er", "var", "væri", "yrði"}:
            # Juxtapose the first and second words
            s = " ".join([words[1], words[0]] + words[2:])
    else:
        # Ég talaði við Jón (heimsmethafa í hástökki)
        s = cut(result._text)

    if s.lower() in NOT_EXPLANATION:
        s = None

    if s:
        result.skýring = s
        mannsnafn = result.get("mannsnafn")
        if s == mannsnafn:
            # Mannsnafn sem skýring á nafnlið: gæti verið gagnlegt
            result.skýring_nafn = mannsnafn
            result.skýring_kyn = result.get("kyn")
    # Ekki senda mannsnafn innan úr skýringunni upp tréð
    result.del_attribs(("mannsnafn", "kyn"))


def NlEind(node: NonterminalNode, params: ParamList, result: Result):
    """Nafnliðareind"""
    mannsnafn = result.get("mannsnafn")
    kyn = result.get("kyn")
    skýring = result.get("skýring")
    if mannsnafn and skýring and kyn:
        # Fullt nafn með skýringu: bæta því við gagnagrunninn
        _add_name(result, mannsnafn, skýring, kyn)
        result.del_attribs(("skýring", "mannsnafn", "kyn"))


def NlKjarni(node: NonterminalNode, params: ParamList, result: Result):
    """Skoða mannsnöfn með titlum sem kunna að þurfa viðbót úr eignarfallslið"""

    if "_et" in node.nt:
        # Höfum aðeins áhuga á eintölu

        mannsnafn = result.get("mannsnafn")
        if mannsnafn:
            kyn = result.get("kyn")
            titill = result.get("titill")
            # print("Looking at mannsnafn '{0}' titill '{1}'".format(mannsnafn, titill))
            if titill is None:
                # Enginn titill aftan við nafnið
                titill = ""
            else:
                if "kommu_titill" not in result:
                    # Bæta eignarfallslið aftan á titilinn:
                    # 'bankastjóri Seðlabanka Íslands'
                    efliður = result.get("efliður")
                    # print("After cut, mannsnafn is '{0}' and efliður is '{1}'".format(mannsnafn, efliður))
                    if efliður:
                        titill += " " + efliður
                if titill.startswith(", "):
                    titill = titill[2:]
                if titill.endswith(" ,") or titill.endswith(" ."):
                    titill = titill[0:-2]

            # print("In check, mannsnafn is '{0}' and titill is '{1}'".format(mannsnafn, titill))

            if _add_name(result, mannsnafn, titill, kyn):
                # Búið að afgreiða þetta nafn
                result.del_attribs(("mannsnafn", "titill", "kommu_titill", "kyn"))

        else:
            mannsnafn = result.get("skýring_nafn")
            kyn = result.get("skýring_kyn")
            if mannsnafn and kyn:
                # print("NlKjarni: mannsnafn úr skýringu er '{0}', allur texti er '{1}'".format(mannsnafn, result._nominative))
                titill = result._text
                # Skera nafnið og tákn (sviga/hornklofa/bandstrik/kommur) aftan af
                rdelim = titill[-2:]
                titill = titill[:-2]
                ldelim = DELIMITERS.get(rdelim)
                if ldelim:
                    titill = titill[0 : titill.rfind(ldelim)]
                # print("NlKjarni: nafn '{0}', titill '{1}'".format(mannsnafn, titill))
                _add_name(result, mannsnafn, titill, kyn)
                result.del_attribs(("skýring_nafn", "skýring_kyn", "skýring"))

    # Leyfa mannsnafni að ferðast áfram upp tréð ef við
    # fundum ekki titil á það hér
    result.del_attribs(("titill", "efliður", "kommu_titill"))
