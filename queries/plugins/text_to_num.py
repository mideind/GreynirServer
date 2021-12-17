"""

    Greynir: Natural language processing for Icelandic

    Natural language number parsing.

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


    Nonterminal for a single number written in natural language.
    Returns its value in the list result["numbers"].

"""

# TODO: Add to Vocab.conf numbers not in BÍN (see bottom of file)
# TODO: Deal with cases and genders of numbers (/fall/kyn/tala)
# TODO: Allow "tólf hundruð þúsund"? Allow "milljón milljónir"?
# TODO: Ordinals (TöluðRaðtala)
# TODO: "fjórir tugir", "tylft" & "á annan tug manna"?

from typing import Sequence
from query import QueryStateDict
from tree import Result, Node

# The context-free grammar for the queries recognized by this plug-in module
GRAMMAR = """

# Cardinal number
TöluðTala →
    TöluðTalaUndirOktilljón
    | TöluðTalaOktilljónir TöluðTalaUndirOktilljón?
    | TöluðTalaOktilljónir TöluðTalaOgUndirOktilljón
    | TöluðTala0

# OKTILLJÓNIR

TöluðTalaOktilljónir →
    TöluðTalaUndirOktilljón? TöluðTalaOktilljón

# SEPTILLJÓNIR

TöluðTalaUndirOktilljón →
    TöluðTalaSeptilljónir TöluðTalaUndirSeptilljón?
    | TöluðTalaSeptilljónir TöluðTalaOgUndirSeptilljón
    | TöluðTalaUndirSeptilljón

TöluðTalaOgUndirOktilljón →
    "og" TöluðTalaSeptilljónir
    | TöluðTalaOgUndirSeptilljón

TöluðTalaSeptilljónir →
    TöluðTalaUndirSeptilljón? TöluðTalaSeptilljón

# SEXTILLJÓNIR

TöluðTalaUndirSeptilljón →
    TöluðTalaSextilljónir TöluðTalaUndirSextilljón?
    | TöluðTalaSextilljónir TöluðTalaOgUndirSextilljón
    | TöluðTalaUndirSextilljón

TöluðTalaOgUndirSeptilljón →
    "og" TöluðTalaSextilljónir
    | TöluðTalaOgUndirSextilljón

TöluðTalaSextilljónir →
    TöluðTalaUndirSextilljón? TöluðTalaSextilljón

# KVINTILLJÓNIR

TöluðTalaUndirSextilljón →
    TöluðTalaKvintilljónir TöluðTalaUndirKvintilljón?
    | TöluðTalaKvintilljónir TöluðTalaOgUndirKvintilljón
    | TöluðTalaUndirKvintilljón

TöluðTalaOgUndirSextilljón →
    "og" TöluðTalaKvintilljónir
    | TöluðTalaOgUndirKvintilljón

TöluðTalaKvintilljónir →
    TöluðTalaUndirKvintilljón? TöluðTalaKvintilljón

# KVAÐRILLJARÐAR

TöluðTalaUndirKvintilljón →
    TöluðTalaKvaðrilljarðar TöluðTalaUndirKvaðrilljarði?
    | TöluðTalaKvaðrilljarðar TöluðTalaOgUndirKvaðrilljarði
    | TöluðTalaUndirKvaðrilljarði

TöluðTalaOgUndirKvintilljón →
    "og" TöluðTalaKvaðrilljarðar
    | TöluðTalaOgUndirKvaðrilljarði

TöluðTalaKvaðrilljarðar →
    TöluðTalaUndirKvaðrilljarði? TöluðTalaKvaðrilljarður

# KVAÐRILLJÓNIR

TöluðTalaUndirKvaðrilljarði →
    TöluðTalaKvaðrilljónir TöluðTalaUndirKvaðrilljón?
    | TöluðTalaKvaðrilljónir TöluðTalaOgUndirKvaðrilljón
    | TöluðTalaUndirKvaðrilljón

TöluðTalaOgUndirKvaðrilljarði →
    "og" TöluðTalaKvaðrilljónir
    | TöluðTalaOgUndirKvaðrilljón

TöluðTalaKvaðrilljónir →
    TöluðTalaUndirKvaðrilljón? TöluðTalaKvaðrilljón

# TRILLJARÐAR

TöluðTalaUndirKvaðrilljón →
    TöluðTalaTrilljarðar TöluðTalaUndirTrilljarði?
    | TöluðTalaTrilljarðar TöluðTalaOgUndirTrilljarði
    | TöluðTalaUndirTrilljarði

TöluðTalaOgUndirKvaðrilljón →
    "og" TöluðTalaTrilljarðar
    | TöluðTalaOgUndirTrilljarði

TöluðTalaTrilljarðar →
    TöluðTalaUndirTrilljarði? TöluðTalaTrilljarður

# TRILLJÓNIR

TöluðTalaUndirTrilljarði →
    TöluðTalaTrilljónir TöluðTalaUndirTrilljón?
    | TöluðTalaTrilljónir TöluðTalaOgUndirTrilljón
    | TöluðTalaUndirTrilljón

TöluðTalaOgUndirTrilljarði →
    "og" TöluðTalaTrilljónir
    | TöluðTalaOgUndirTrilljón

TöluðTalaTrilljónir →
    TöluðTalaUndirTrilljón? TöluðTalaTrilljón
    | TöluðTalaUndirMilljarði? TöluðTalaMilljarður TöluðTalaMilljarður

# BILLJARÐAR

TöluðTalaUndirTrilljón →
    TöluðTalaBilljarðar TöluðTalaUndirBilljarði?
    | TöluðTalaBilljarðar TöluðTalaOgUndirBilljarði
    | TöluðTalaUndirBilljarði

TöluðTalaOgUndirTrilljón →
    "og" TöluðTalaBilljarðar
    | TöluðTalaOgUndirBilljarði

TöluðTalaBilljarðar →
    TöluðTalaUndirBilljarði? TöluðTalaBilljarður
    | TöluðTalaUndirMilljón? TöluðTalaMilljón TöluðTalaMilljarður

# BILLJÓNIR

TöluðTalaUndirBilljarði →
    TöluðTalaBilljónir TöluðTalaUndirBilljón?
    | TöluðTalaBilljónir TöluðTalaOgUndirBilljón
    | TöluðTalaUndirBilljón

TöluðTalaOgUndirBilljarði →
    "og" TöluðTalaBilljónir
    | TöluðTalaOgUndirBilljón

TöluðTalaBilljónir →
    TöluðTalaUndirBilljón? TöluðTalaBilljón
    | TöluðTalaUndirMilljón? TöluðTalaMilljón TöluðTalaMilljón

# MILLJARÐAR

TöluðTalaUndirBilljón →
    TöluðTalaMilljarðar TöluðTalaUndirMilljarði?
    | TöluðTalaMilljarðar TöluðTalaOgUndirMilljarði
    | TöluðTalaUndirMilljarði

TöluðTalaOgUndirBilljón →
    "og" TöluðTalaMilljarðar
    | TöluðTalaOgUndirMilljarði

TöluðTalaMilljarðar →
    TöluðTalaUndirMilljarði? TöluðTalaMilljarður

# MILLJÓNIR

TöluðTalaUndirMilljarði →
    TöluðTalaMilljónir TöluðTalaUndirMilljón?
    | TöluðTalaMilljónir TöluðTalaOgUndirMilljón
    | TöluðTalaUndirMilljón

TöluðTalaOgUndirMilljarði →
    "og" TöluðTalaMilljónir
    | TöluðTalaOgUndirMilljón

TöluðTalaMilljónir →
    TöluðTalaUndirMilljón? TöluðTalaMilljón

# ÞÚSUND

TöluðTalaUndirMilljón →
    TöluðTalaÞúsundir TöluðTalaUndirÞúsund?
    | TöluðTalaÞúsundir TöluðTalaOgUndirÞúsund
    | TöluðTala10Til19Hundruð TöluðTalaUndirHundrað?
    | TöluðTala10Til19Hundruð TöluðTalaOgUndirHundrað?
    | TöluðTalaUndirÞúsund

TöluðTalaOgUndirMilljón →
    "og" TöluðTalaÞúsundir
    | TöluðTalaOgUndirÞúsund

TöluðTalaÞúsundir →
    TöluðTalaUndirÞúsund? TöluðTalaÞúsund

TöluðTala10Til19Hundruð →
    TöluðTala10Til19 TöluðTalaHundrað

# HUNDRUÐ

TöluðTalaUndirÞúsund →
    TöluðTalaHundruð TöluðTalaTugurOgEining?
    | TöluðTalaHundruð TöluðTalaOgUndirHundrað?
    | TöluðTalaUndirHundrað

TöluðTalaOgUndirÞúsund →
    "og" TöluðTalaHundruð
    | TöluðTalaOgUndirHundrað

TöluðTalaHundruð →
    TöluðTala1Til9? TöluðTalaHundrað

# UNDIR HUNDRAÐ

TöluðTalaUndirHundrað →
    TöluðTalaTugurOgEining
    | TöluðTalaTugir
    | TöluðTala10Til19
    | TöluðTala1Til9

TöluðTalaOgUndirHundrað →
    "og" TöluðTalaTugir
    | "og" TöluðTala10Til19
    | "og" TöluðTala1Til9

TöluðTalaTugurOgEining →
    TöluðTalaTugir "og" TöluðTala1Til9

###

TöluðTala0 → 'núll'

TöluðTala1Til9 →
    'einn:to'
    | 'tveir:to'
    | 'þrír:to'
    | 'fjórir:to'
    | "fimm"
    | "sex"
    | "sjö"
    | "átta"
    | "níu"

TöluðTala10Til19 →
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

TöluðTalaTugir →
    "tuttugu"
    | "þrjátíu"
    | "fjörutíu"
    | "fimmtíu"
    | "sextíu"
    | "sjötíu"
    | "áttatíu"
    | "níutíu"

TöluðTalaHundrað → 'hundrað'

TöluðTalaÞúsund → 'þúsund:töl'

TöluðTalaMilljón → 'milljón'

TöluðTalaMilljarður →
    'milljarður'
    | 'miljarður'

TöluðTalaBilljón → 'billjón'

TöluðTalaBilljarður → 'billjarður'

TöluðTalaTrilljón → 'trilljón'

TöluðTalaTrilljarður → 'trilljarður'

TöluðTalaKvaðrilljón → 'kvaðrilljón'

TöluðTalaKvaðrilljarður → 'kvaðrilljarður'

TöluðTalaKvintilljón → 'kvintilljón'

TöluðTalaSextilljón → 'sextilljón'

TöluðTalaSeptilljón → 'septilljón'

TöluðTalaOktilljón → 'oktilljón'

"""


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
    # Following numbers not in BÍN
    "kvaðrilljarður": 10 ** 27,
    "kvintilljón": 10 ** 30,
    "sextilljón": 10 ** 36,
    "septilljón": 10 ** 42,
    "oktilljón": 10 ** 48,
}


# (math.prod is only available for python 3.8+)
def _prod(li: Sequence[int]) -> int:
    """Take product of non-empty list."""
    p = li[0]
    for n in li[1:]:
        p *= n
    return p


# Function for nonterminals which have children that should be multiplied together
# e.g. "fimm" (5) and "hundruð" (100) -> "fimm hundruð" (500)
def _multiply_children(node: Node, params: QueryStateDict, result: Result) -> None:
    if "numbers" in result:
        result["numbers"] = [_prod(result["numbers"])]


# Plural named functions ("TöluðTalaMilljónir") take the product of the children nodes
(
    TöluðTalaHundruð,
    TöluðTala10Til19Hundruð,
    TöluðTalaÞúsundir,
    TöluðTalaMilljónir,
    TöluðTalaMilljarðar,
    TöluðTalaBilljónir,
    TöluðTalaBilljarðar,
    TöluðTalaTrilljónir,
    TöluðTalaTrilljarðar,
    TöluðTalaKvaðrilljónir,
    TöluðTalaKvaðrilljarðar,
    TöluðTalaKvintilljónir,
    TöluðTalaSextilljónir,
    TöluðTalaSeptilljónir,
    TöluðTalaOktilljónir,
) = [_multiply_children] * 15

# Function for nonterminals which have children that should be added together
# e.g. "sextíu" (60) and "átta" (8) -> "sextíu (og) átta" (68)
def _sum_children(node: Node, params: QueryStateDict, result: Result) -> None:
    if "numbers" in result:
        result["numbers"] = [sum(result["numbers"])]


# "TöluðTalaUndirX" functions take the sum of the children nodes,
# along with the root "TöluðTala"
(
    TöluðTala,
    TöluðTalaUndirHundrað,
    TöluðTalaUndirÞúsund,
    TöluðTalaUndirMilljón,
    TöluðTalaUndirMilljarði,
    TöluðTalaUndirBilljón,
    TöluðTalaUndirBilljarði,
    TöluðTalaUndirTrilljón,
    TöluðTalaUndirTrilljarði,
    TöluðTalaUndirKvaðrilljón,
    TöluðTalaUndirKvaðrilljarði,
    TöluðTalaUndirKvintilljón,
    TöluðTalaUndirSextilljón,
    TöluðTalaUndirSeptilljón,
    TöluðTalaUndirOktilljón,
) = [_sum_children] * 15


# Function for nonterminals where we can perform a value lookup
# e.g. "hundruð" (result._root = "hundrað") -> 100 
def _lookup_function(node: Node, params: QueryStateDict, result: Result) -> None:
    result["numbers"] = [_NUMBERS[result._root]]


# Define multiple functions with same functionality but different names
(
    TöluðTala0,
    TöluðTala1Til9,
    TöluðTala10Til19,
    TöluðTalaTugir,
    TöluðTalaHundrað,
    TöluðTalaÞúsund,
    TöluðTalaMilljón,
    TöluðTalaMilljarður,
    TöluðTalaBilljón,
    TöluðTalaBilljarður,
    TöluðTalaTrilljón,
    TöluðTalaTrilljarður,
    TöluðTalaKvaðrilljón,
    TöluðTalaKvaðrilljarður,
    TöluðTalaKvintilljón,
    TöluðTalaSextilljón,
    TöluðTalaSeptilljón,
    TöluðTalaOktilljón,
) = [_lookup_function] * 18


# BÍN additions in format for Vocab.conf

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
