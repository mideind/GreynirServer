"""

    Greynir: Natural language processing for Icelandic

    Opinion query response module

    Copyright (C) 2021 Miðeind ehf.

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


    Matches a single number in written form and returns its value.

"""

from typing import Sequence
from query import Query, QueryStateDict
from tree import Result, Node

from queries import gen_answer


_NUM_QTYPE = "Number"


# Indicate that this module wants to handle parse trees for queries,
# as opposed to simple literal text strings
HANDLE_TREE = True

# The grammar nonterminals this module wants to handle
QUERY_NONTERMINALS = {"QNumQuery"}

# The context-free grammar for the queries recognized by this plug-in module
GRAMMAR = """

Query →
    QNumQuery

QNumQuery →
    QNumber '?'?

QNumber →
    QNumUndirOktilljón | QNumOktilljónir QNumUndirOktilljón? | QNumOktilljónir QNumOgUndirOktilljón

#################
# NON-TERMINALS #
#################

#### OKTILLJÓNIR ####

QNumOktilljónir →
    QNumUndirOktilljón? QNumOktilljón

#### SEPTILLJÓNIR ####

QNumUndirOktilljón →
    QNumSeptilljónir QNumUndirSeptilljón?
    | QNumSeptilljónir QNumOgUndirSeptilljón
    | QNumUndirSeptilljón

QNumOgUndirOktilljón →
    "og" QNumSeptilljónir
    | QNumOgUndirSeptilljón

QNumSeptilljónir →
    QNumUndirSeptilljón? QNumSeptilljón

#### SEXTILLJÓNIR ####

QNumUndirSeptilljón →
    QNumSextilljónir QNumUndirSextilljón?
    | QNumSextilljónir QNumOgUndirSextilljón
    | QNumUndirSextilljón

QNumOgUndirSeptilljón →
    "og" QNumSextilljónir
    | QNumOgUndirSextilljón

QNumSextilljónir →
    QNumUndirSextilljón? QNumSextilljón

#### KVINTILLJÓNIR ####

QNumUndirSextilljón →
    QNumKvintilljónir QNumUndirKvintilljón?
    | QNumKvintilljónir QNumOgUndirKvintilljón
    | QNumUndirKvintilljón

QNumOgUndirSextilljón →
    "og" QNumKvintilljónir
    | QNumOgUndirKvintilljón

QNumKvintilljónir →
    QNumUndirKvintilljón? QNumKvintilljón

#### KVAÐRILLJARÐAR ####

QNumUndirKvintilljón →
    QNumKvaðrilljarðar QNumUndirKvaðrilljarði?
    | QNumKvaðrilljarðar QNumOgUndirKvaðrilljarði
    | QNumUndirKvaðrilljarði

QNumOgUndirKvintilljón →
    "og" QNumKvaðrilljarðar
    | QNumOgUndirKvaðrilljarði

QNumKvaðrilljarðar →
    QNumUndirKvaðrilljarði? QNumKvaðrilljarður

#### KVAÐRILLJÓNIR ####

QNumUndirKvaðrilljarði →
    QNumKvaðrilljónir QNumUndirKvaðrilljón?
    | QNumKvaðrilljónir QNumOgUndirKvaðrilljón
    | QNumUndirKvaðrilljón

QNumOgUndirKvaðrilljarði →
    "og" QNumKvaðrilljónir
    | QNumOgUndirKvaðrilljón

QNumKvaðrilljónir →
    QNumUndirKvaðrilljón? QNumKvaðrilljón

#### TRILLJARÐAR ####

QNumUndirKvaðrilljón →
    QNumTrilljarðar QNumUndirTrilljarði?
    | QNumTrilljarðar QNumOgUndirTrilljarði
    | QNumUndirTrilljarði

QNumOgUndirKvaðrilljón →
    "og" QNumTrilljarðar
    | QNumOgUndirTrilljarði

QNumTrilljarðar →
    QNumUndirTrilljarði? QNumTrilljarður

#### TRILLJÓNIR ####

QNumUndirTrilljarði →
    QNumTrilljónir QNumUndirTrilljón?
    | QNumTrilljónir QNumOgUndirTrilljón
    | QNumUndirTrilljón

QNumOgUndirTrilljarði →
    "og" QNumTrilljónir
    | QNumOgUndirTrilljón

QNumTrilljónir →
    QNumUndirTrilljón? QNumTrilljón
    | QNumUndirMilljarði? QNumMilljarður QNumMilljarður

#### BILLJARÐAR ####

QNumUndirTrilljón →
    QNumBilljarðar QNumUndirBilljarði?
    | QNumBilljarðar QNumOgUndirBilljarði
    | QNumUndirBilljarði

QNumOgUndirTrilljón →
    "og" QNumBilljarðar
    | QNumOgUndirBilljarði

QNumBilljarðar →
    QNumUndirBilljarði? QNumBilljarður
    | QNumUndirMilljón? QNumMilljón QNumMilljarður

#### BILLJÓNIR ####

QNumUndirBilljarði →
    QNumBilljónir QNumUndirBilljón?
    | QNumBilljónir QNumOgUndirBilljón
    | QNumUndirBilljón

QNumOgUndirBilljarði →
    "og" QNumBilljónir
    | QNumOgUndirBilljón

QNumBilljónir →
    QNumUndirBilljón? QNumBilljón
    | QNumUndirMilljón? QNumMilljón QNumMilljón

#### MILLJARÐAR ####

QNumUndirBilljón →
    QNumMilljarðar QNumUndirMilljarði?
    | QNumMilljarðar QNumOgUndirMilljarði
    | QNumUndirMilljarði

QNumOgUndirBilljón →
    "og" QNumMilljarðar
    | QNumOgUndirMilljarði

QNumMilljarðar →
    QNumUndirMilljarði? QNumMilljarður

#### MILLJÓNIR ####

QNumUndirMilljarði →
    QNumMilljónir QNumUndirMilljón?
    | QNumMilljónir QNumOgUndirMilljón
    | QNumUndirMilljón

QNumOgUndirMilljarði →
    "og" QNumMilljónir
    | QNumOgUndirMilljón

QNumMilljónir →
    QNumUndirMilljón? QNumMilljón

#### ÞÚSUND ####

QNumUndirMilljón →
    QNumÞúsundir QNumUndirÞúsund?
    | QNumÞúsundir QNumOgUndirÞúsund
    | QNum10Til19Hundruð QNumUndirHundrað?
    | QNum10Til19Hundruð QNumOgUndirHundrað?
    | QNumUndirÞúsund

QNumOgUndirMilljón →
    "og" QNumÞúsundir
    | QNumOgUndirÞúsund

QNumÞúsundir →
    QNumUndirÞúsund? QNumÞúsund

QNum10Til19Hundruð →
    QNum10Til19 QNumHundrað

#### HUNDRUÐ ####

QNumUndirÞúsund →
    QNumHundruð QNumTugurOgEining?
    | QNumHundruð QNumOgUndirHundrað?
    | QNumUndirHundrað

QNumOgUndirÞúsund →
    "og" QNumHundruð
    | QNumOgUndirHundrað

QNumHundruð →
    QNum1Til9? QNumHundrað

#### UNDIR HUNDRAÐ ####

QNumUndirHundrað →
    QNumTugurOgEining
    | QNumTugir
    | QNum10Til19
    | QNum1Til9

QNumOgUndirHundrað →
    "og" QNumTugir
    | "og" QNum10Til19
    | "og" QNum1Til9

QNumTugurOgEining →
    QNumTugir "og" QNum1Til9

#############
# TERMINALS #
#############

QNumAllTerminals →
    QNum0
    | QNum1Til9
    | QNum10Til19
    | QNumHundrað
    | QNumÞúsund
    | QNumMilljón
    | QNumMilljarður
    | QNumBilljón
    | QNumBilljarður
    | QNumTrilljón
    | QNumTrilljarður
    | QNumKvaðrilljón
    | QNumKvaðrilljarður
    | QNumKvintilljón
    | QNumSextilljón
    | QNumSeptilljón
    | QNumOktilljón

QNum0 →
    'núll'

QNum1Til9 →
    # 'einn'/fall/tala/kyn  # FIXME: Catch different cases of 1,2,3 and 4
    # | 'tveir'/fall/tala/kyn
    # | 'þrír'/fall/tala/kyn
    # | 'fjórir'/fall/tala/kyn
    to/tala/fall/kyn
    | "fimm"
    | "sex"
    | "sjö"
    | "átta"
    | "níu"

QNum10Til19 →
    "tíu"
    | "ellefu"
    | "tólf"
    | "þrettán"
    | "fjórtán"
    | "fimmtán"
    | "sextán"
    | "sautján"
    | "átján"
    | "nítján"

QNumTugir →
    "tuttugu"
    | "þrjátíu"
    | "fjörutíu"
    | "fimmtíu"
    | "sextíu"
    | "sjötíu"
    | "áttatíu"
    | "níutíu"

QNumHundrað →
    'hundrað'

QNumÞúsund →
    'þúsund'

QNumMilljón →
    'milljón'

QNumMilljarður →
    'milljarður' | 'miljarður'

QNumBilljón →
    'billjón'

QNumBilljarður →
    'billjarður'

QNumTrilljón →
    'trilljón'

QNumTrilljarður →
    'trilljarður'

QNumKvaðrilljón →
    'kvaðrilljón'

QNumKvaðrilljarður →
    'kvaðrilljarður'

QNumKvintilljón →
    'kvintilljón'

QNumSextilljón →
    'sextilljón'

QNumSeptilljón →
    'septilljón'

QNumOktilljón →
    'oktilljón'


"""
# TODO: CATCH CASES AND GENDER OF NUMBERS !!! Bæta inn í Vocab.conf töluorðum fyrir tölur ekki í BÍN

# TODO: "oktilljón og milljón septilljónir" og "septilljón og milljón sextilljónir",
#       Spyrja hvort eigi að leyfa eða ekki t.d. milljarður septilljóna == eh margar oktilljónir í staðinn

# TODO: "tólf hundruð þúsund"?
# TODO: Ordinals
# TODO: "á annan tug manna"? "fjórir tugir"


_NUMBERS = {
    "núll": 0,
    "einn": 1,
    "tveir": 2,
    "þrír": 3,
    "fjórir": 4,
    "fimm": 5,
    "sex": 6,
    "sjö": 7,
    "átta": 8,
    "níu": 9,
    "tíu": 10,
    "ellefu": 11,
    "tólf": 12,
    "þrettán": 13,
    "fjórtán": 14,
    "fimmtán": 15,
    "sextán": 16,
    "sautján": 17,
    "seytján": 17,
    "átján": 18,
    "nítján": 19,
    "tuttugu": 20,
    "þrjátíu": 30,
    "fjörutíu": 40,
    "fimmtíu": 50,
    "sextíu": 60,
    "sjötíu": 70,
    "áttatíu": 80,
    "níutíu": 90,
    "hundrað": 100,
    "þúsund": 1000,
    "milljón": 10 ** 6,
    "miljarður": 10 ** 9,
    "milljarður": 10 ** 9,
    "billjón": 10 ** 12,
    "billjarður": 10 ** 15,
    "trilljón": 10 ** 18,
    "trilljarður": 10 ** 21,
    "kvaðrilljón": 10 ** 24,
    # TODO: Add to BÍN
    "kvaðrilljarður": 10 ** 27,
    "kvintilljón": 10 ** 30,
    "sextilljón": 10 ** 36,
    "septilljón": 10 ** 42,
    "oktilljón": 10 ** 48,
}


def _text_to_num(root: str) -> int:
    """Return integer value for number word root."""
    return _NUMBERS[root]


def _product(li: Sequence[int]) -> int:
    """Take product of non-empty list."""
    p = li[0]
    for n in li[1:]:
        p *= n
    return p


def QNumQuery(node: Node, params: QueryStateDict, result: Result) -> None:
    result["qtype"] = _NUM_QTYPE


####################
# COMBINED NUMBERS #
####################

# "Undir" (below) functions take the sum of the children nodes
# Plural named functions take the product of the children nodes


def QNumUndirHundrað(node: Node, params: QueryStateDict, result: Result) -> None:
    if "numbers" in result:
        result["numbers"] = [sum(result["numbers"])]


def QNumHundruð(node: Node, params: QueryStateDict, result: Result) -> None:
    if "numbers" in result:
        result["numbers"] = [_product(result["numbers"])]


def QNum10Til19Hundruð(node: Node, params: QueryStateDict, result: Result) -> None:
    if "numbers" in result:
        result["numbers"] = [_product(result["numbers"])]


def QNumUndirÞúsund(node: Node, params: QueryStateDict, result: Result) -> None:
    if "numbers" in result:
        result["numbers"] = [sum(result["numbers"])]


def QNumÞúsundir(node: Node, params: QueryStateDict, result: Result) -> None:
    if "numbers" in result:
        result["numbers"] = [_product(result["numbers"])]


def QNumUndirMilljón(node: Node, params: QueryStateDict, result: Result) -> None:
    if "numbers" in result:
        result["numbers"] = [sum(result["numbers"])]


def QNumMilljónir(node: Node, params: QueryStateDict, result: Result) -> None:
    if "numbers" in result:
        result["numbers"] = [_product(result["numbers"])]


def QNumUndirMilljarði(node: Node, params: QueryStateDict, result: Result) -> None:
    if "numbers" in result:
        result["numbers"] = [sum(result["numbers"])]


def QNumMilljarðar(node: Node, params: QueryStateDict, result: Result) -> None:
    if "numbers" in result:
        result["numbers"] = [_product(result["numbers"])]


def QNumUndirBilljón(node: Node, params: QueryStateDict, result: Result) -> None:
    if "numbers" in result:
        result["numbers"] = [sum(result["numbers"])]


def QNumBilljónir(node: Node, params: QueryStateDict, result: Result) -> None:
    if "numbers" in result:
        result["numbers"] = [_product(result["numbers"])]


def QNumUndirBilljarði(node: Node, params: QueryStateDict, result: Result) -> None:
    if "numbers" in result:
        result["numbers"] = [sum(result["numbers"])]


def QNumBilljarðar(node: Node, params: QueryStateDict, result: Result) -> None:
    if "numbers" in result:
        result["numbers"] = [_product(result["numbers"])]


def QNumUndirTrilljón(node: Node, params: QueryStateDict, result: Result) -> None:
    if "numbers" in result:
        result["numbers"] = [sum(result["numbers"])]


def QNumTrilljónir(node: Node, params: QueryStateDict, result: Result) -> None:
    if "numbers" in result:
        result["numbers"] = [_product(result["numbers"])]


def QNumUndirTrilljarði(node: Node, params: QueryStateDict, result: Result) -> None:
    if "numbers" in result:
        result["numbers"] = [sum(result["numbers"])]


def QNumTrilljarðar(node: Node, params: QueryStateDict, result: Result) -> None:
    if "numbers" in result:
        result["numbers"] = [_product(result["numbers"])]


def QNumUndirKvaðrilljón(node: Node, params: QueryStateDict, result: Result) -> None:
    if "numbers" in result:
        result["numbers"] = [sum(result["numbers"])]


def QNumKvaðrilljónir(node: Node, params: QueryStateDict, result: Result) -> None:
    if "numbers" in result:
        result["numbers"] = [_product(result["numbers"])]


def QNumUndirKvaðrilljarði(node: Node, params: QueryStateDict, result: Result) -> None:
    if "numbers" in result:
        result["numbers"] = [sum(result["numbers"])]


def QNumKvaðrilljarðar(node: Node, params: QueryStateDict, result: Result) -> None:
    if "numbers" in result:
        result["numbers"] = [_product(result["numbers"])]


def QNumUndirKvintilljón(node: Node, params: QueryStateDict, result: Result) -> None:
    if "numbers" in result:
        result["numbers"] = [sum(result["numbers"])]


def QNumKvintilljónir(node: Node, params: QueryStateDict, result: Result) -> None:
    if "numbers" in result:
        result["numbers"] = [_product(result["numbers"])]


def QNumUndirSextilljón(node: Node, params: QueryStateDict, result: Result) -> None:
    if "numbers" in result:
        result["numbers"] = [sum(result["numbers"])]


def QNumSextilljónir(node: Node, params: QueryStateDict, result: Result) -> None:
    if "numbers" in result:
        result["numbers"] = [_product(result["numbers"])]


def QNumUndirSeptilljón(node: Node, params: QueryStateDict, result: Result) -> None:
    if "numbers" in result:
        result["numbers"] = [sum(result["numbers"])]


def QNumSeptilljónir(node: Node, params: QueryStateDict, result: Result) -> None:
    if "numbers" in result:
        result["numbers"] = [_product(result["numbers"])]


def QNumUndirOktilljón(node: Node, params: QueryStateDict, result: Result) -> None:
    if "numbers" in result:
        result["numbers"] = [sum(result["numbers"])]


def QNumOktilljónir(node: Node, params: QueryStateDict, result: Result) -> None:
    if "numbers" in result:
        result["numbers"] = [_product(result["numbers"])]


def QNumber(node: Node, params: QueryStateDict, result: Result) -> None:
    if "numbers" in result:
        result["numbers"] = [sum(result["numbers"])]


#############
# TERMINALS #
#############


def QNum0(node: Node, params: QueryStateDict, result: Result) -> None:
    result["numbers"] = [0]


def QNum1Til9(node: Node, params: QueryStateDict, result: Result) -> None:
    result["numbers"] = [_text_to_num(result._root)]


def QNum10Til19(node: Node, params: QueryStateDict, result: Result) -> None:
    result["numbers"] = [_text_to_num(result._root)]


def QNumTugir(node: Node, params: QueryStateDict, result: Result) -> None:
    result["numbers"] = [_text_to_num(result._root)]


def QNumHundrað(node: Node, params: QueryStateDict, result: Result) -> None:
    result["numbers"] = [_text_to_num(result._root)]


def QNumÞúsund(node: Node, params: QueryStateDict, result: Result) -> None:
    result["numbers"] = [_text_to_num(result._root)]


def QNumMilljón(node: Node, params: QueryStateDict, result: Result) -> None:
    result["numbers"] = [_text_to_num(result._root)]


def QNumMilljarður(node: Node, params: QueryStateDict, result: Result) -> None:
    result["numbers"] = [_text_to_num(result._root)]


def QNumBilljón(node: Node, params: QueryStateDict, result: Result) -> None:
    result["numbers"] = [_text_to_num(result._root)]


def QNumBilljarður(node: Node, params: QueryStateDict, result: Result) -> None:
    result["numbers"] = [_text_to_num(result._root)]


def QNumTrilljón(node: Node, params: QueryStateDict, result: Result) -> None:
    result["numbers"] = [_text_to_num(result._root)]


def QNumTrilljarður(node: Node, params: QueryStateDict, result: Result) -> None:
    result["numbers"] = [_text_to_num(result._root)]


def QNumKvaðrilljón(node: Node, params: QueryStateDict, result: Result) -> None:
    result["numbers"] = [_text_to_num(result._root)]


def QNumKvaðrilljarður(node: Node, params: QueryStateDict, result: Result) -> None:
    result["numbers"] = [_text_to_num(result._root)]


def QNumKvintilljón(node: Node, params: QueryStateDict, result: Result) -> None:
    result["numbers"] = [_text_to_num(result._root)]


def QNumSextilljón(node: Node, params: QueryStateDict, result: Result) -> None:
    result["numbers"] = [_text_to_num(result._root)]


def QNumSeptilljón(node: Node, params: QueryStateDict, result: Result) -> None:
    result["numbers"] = [_text_to_num(result._root)]


def QNumOktilljón(node: Node, params: QueryStateDict, result: Result) -> None:
    result["numbers"] = [_text_to_num(result._root)]


def sentence(state: QueryStateDict, result: Result) -> None:
    """Called when sentence processing is complete"""
    q: Query = state["query"]

    if "qtype" not in result:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
        return

    answer = ", ".join(str(i) for i in result.get("numbers"))

    q.set_answer(*gen_answer(answer))
    q.set_qtype(_NUM_QTYPE)


# kvaðrilljarður    kvaðrilljarður        kk alm NFET
# kvaðrilljarður    kvaðrilljarð          kk alm ÞFET
# kvaðrilljarður    kvaðrilljarði         kk alm ÞGFET
# kvaðrilljarður    kvaðrilljarðs         kk alm EFET

# kvaðrilljarður    kvaðrilljarðurinn     kk alm NFETgr
# kvaðrilljarður    kvaðrilljarðinn       kk alm ÞFETgr
# kvaðrilljarður    kvaðrilljarðinum      kk alm ÞGFETgr
# kvaðrilljarður    kvaðrilljarðsins      kk alm EFETgr

# kvaðrilljarður    kvaðrilljarðar        kk alm NFFT
# kvaðrilljarður    kvaðrilljarða         kk alm ÞFFT
# kvaðrilljarður    kvaðrilljörðum        kk alm ÞGFFT
# kvaðrilljarður    kvaðrilljarða         kk alm EFFT

# kvaðrilljarður    kvaðrilljarðarnir     kk alm NFFTgr
# kvaðrilljarður    kvaðrilljarðana       kk alm ÞFFTgr
# kvaðrilljarður    kvaðrilljörðunum      kk alm ÞGFFTgr
# kvaðrilljarður    kvaðrilljarðanna      kk alm EFFTgr


# kvintilljón    kvintilljón         kvk alm NFET
# kvintilljón    kvintilljón         kvk alm ÞFET
# kvintilljón    kvintilljón         kvk alm ÞGFET
# kvintilljón    kvintilljónar       kvk alm EFET

# kvintilljón    kvintilljónin       kvk alm NFETgr
# kvintilljón    kvintilljónina      kvk alm ÞFETgr
# kvintilljón    kvintilljóninni     kvk alm ÞGFETgr
# kvintilljón    kvintilljónarinnar  kvk alm EFETgr

# kvintilljón    kvintilljónir       kvk alm NFFT
# kvintilljón    kvintilljónir       kvk alm ÞFFT
# kvintilljón    kvintilljónum       kvk alm ÞGFFT
# kvintilljón    kvintilljóna        kvk alm EFFT

# kvintilljón    kvintilljónirnar    kvk alm NFFTgr
# kvintilljón    kvintilljónirnar    kvk alm ÞFFTgr
# kvintilljón    kvintilljónunum     kvk alm ÞGFFTgr
# kvintilljón    kvintilljónanna     kvk alm EFFTgr


# sextilljón    sextilljón         kvk alm NFET
# sextilljón    sextilljón         kvk alm ÞFET
# sextilljón    sextilljón         kvk alm ÞGFET
# sextilljón    sextilljónar       kvk alm EFET

# sextilljón    sextilljónin       kvk alm NFETgr
# sextilljón    sextilljónina      kvk alm ÞFETgr
# sextilljón    sextilljóninni     kvk alm ÞGFETgr
# sextilljón    sextilljónarinnar  kvk alm EFETgr

# sextilljón    sextilljónir       kvk alm NFFT
# sextilljón    sextilljónir       kvk alm ÞFFT
# sextilljón    sextilljónum       kvk alm ÞGFFT
# sextilljón    sextilljóna        kvk alm EFFT

# sextilljón    sextilljónirnar    kvk alm NFFTgr
# sextilljón    sextilljónirnar    kvk alm ÞFFTgr
# sextilljón    sextilljónunum     kvk alm ÞGFFTgr
# sextilljón    sextilljónanna     kvk alm EFFTgr


# septilljón    septilljón         kvk alm NFET
# septilljón    septilljón         kvk alm ÞFET
# septilljón    septilljón         kvk alm ÞGFET
# septilljón    septilljónar       kvk alm EFET

# septilljón    septilljónin       kvk alm NFETgr
# septilljón    septilljónina      kvk alm ÞFETgr
# septilljón    septilljóninni     kvk alm ÞGFETgr
# septilljón    septilljónarinnar  kvk alm EFETgr

# septilljón    septilljónir       kvk alm NFFT
# septilljón    septilljónir       kvk alm ÞFFT
# septilljón    septilljónum       kvk alm ÞGFFT
# septilljón    septilljóna        kvk alm EFFT

# septilljón    septilljónirnar    kvk alm NFFTgr
# septilljón    septilljónirnar    kvk alm ÞFFTgr
# septilljón    septilljónunum     kvk alm ÞGFFTgr
# septilljón    septilljónanna     kvk alm EFFTgr


# oktilljón    oktilljón         kvk alm NFET
# oktilljón    oktilljón         kvk alm ÞFET
# oktilljón    oktilljón         kvk alm ÞGFET
# oktilljón    oktilljónar       kvk alm EFET

# oktilljón    oktilljónin       kvk alm NFETgr
# oktilljón    oktilljónina      kvk alm ÞFETgr
# oktilljón    oktilljóninni     kvk alm ÞGFETgr
# oktilljón    oktilljónarinnar  kvk alm EFETgr

# oktilljón    oktilljónir       kvk alm NFFT
# oktilljón    oktilljónir       kvk alm ÞFFT
# oktilljón    oktilljónum       kvk alm ÞGFFT
# oktilljón    oktilljóna        kvk alm EFFT

# oktilljón    oktilljónirnar    kvk alm NFFTgr
# oktilljón    oktilljónirnar    kvk alm ÞFFTgr
# oktilljón    oktilljónunum     kvk alm ÞGFFTgr
# oktilljón    oktilljónanna     kvk alm EFFTgr
