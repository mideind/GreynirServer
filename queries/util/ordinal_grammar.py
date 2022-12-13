"""

    Greynir: Natural language processing for Icelandic

    Number parsing grammar.

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


    Utility module
    Exposes nonterminal "UHeilTala" for parsing
    numbers either written in natural language or in digits,
    along with "UBrotaTala" for parsing floats ("(number) 'komma' (numbers)")
    written in natural language.
    Returns the number values in the list result["numbers"].

"""

# TODO: Deal better with cases and genders of numbers
# TODO: Allow "tólf hundruð þúsund" & "hundruðir" (need to add hundruðir to ord.add/auka.csv)
# TODO: 1 - Ordinal numbers
# TODO: 2 - Fractions

from typing import Any

from functools import reduce
from operator import mul

from tree import Result
from queries.util import read_utility_grammar_file

# The context-free grammar for number utterances recognized by this utility module
GRAMMAR = read_utility_grammar_file("ordinal")

_NUMBERS = {
    "núll": 0,
    "núllti": 0,
    "einn": 1,
    "fyrstur": 1,
    "tveir": 2,
    "annar": 2,
    "þrír": 3,
    "þriðji": 3,
    "fjórir": 4,
    "fjórði": 4,
    "fimm": 5,
    "fimmti": 5,
    "sex": 6,
    "sjötti": 6,
    "sjö": 7,
    "sjöundi": 7,
    "átta": 8,
    "áttundi": 8,
    "níu": 9,
    "níundi": 9,
    "tíu": 10,
    "tíundi": 10,
    "ellefu": 11,
    "ellefti": 11,
    "tólf": 12,
    "tólfti": 12,
    "þrettán": 13,
    "þrettándi": 13,
    "fjórtán": 14,
    "fjórtándi": 14,
    "fimmtán": 15,
    "fimmtándi": 15,
    "sextán": 16,
    "sextándi": 16,
    "sautján": 17,
    "sautjándi": 17,
    "seytján": 17,
    "seytjándi": 17,
    "átján": 18,
    "átjándi": 18,
    "nítján": 19,
    "nítjándi": 19,
    "tuttugu": 20,
    "tuttugasti": 20,
    "þrjátíu": 30,
    "þrítugasti": 30,
    "fjörutíu": 40,
    "fertugasti": 40,
    "fimmtíu": 50,
    "fimmtugasti": 50,
    "sextíu": 60,
    "sextugasti": 60,
    "sjötíu": 70,
    "sjötugasti": 70,
    "áttatíu": 80,
    "átttugasti": 80,
    "níutíu": 90,
    "nítugasti": 90,
    "hundrað": 100,
    "hundraðasti": 100,
    "hundruð": 100,
    "hundruðasti": 100,
    "þúsund": 1000,
    "þúsundasti": 1000,
    "milljón": 10**6,
    "milljónasti": 10**6,
    "miljarður": 10**9,
    "miljarðasti": 10**9,
    "milljarður": 10**9,
    "milljarðasti": 10**9,
    "billjón": 10**12,
    "billjónasti": 10**12,
    "billjarður": 10**15,
    "billjarðasti": 10**15,
    "trilljón": 10**18,
    "trilljónasti": 10**18,
    "trilljarður": 10**21,
    "trilljarðasti": 10**21,
    "kvaðrilljón": 10**24,
    "kvaðrilljónasti": 10**24,
    "kvaðrilljarður": 10**27,
    "kvaðrilljarðasti": 10**27,
    "kvintilljón": 10**30,
    "kvintilljónasti": 10**30,
    "sextilljón": 10**36,
    "sextilljónasti": 10**36,
    "septilljón": 10**42,
    "septilljónasti": 10**42,
    "oktilljón": 10**48,
    "oktilljónasti": 10**48,
}


# Function for nonterminals which have children that should be multiplied together
# e.g. "fimm" (5) and "hundruð" (100) -> "fimm hundruð" (500)
def _multiply_children(node: Any, params: Any, result: Result) -> None:
    if "numbers" in result:
        result["numbers"] = [reduce(mul, result["numbers"])]
    print("multiply_children")


# Plural named functions (e.g. "UTöluðTalaMilljónir") take the product of the children nodes
(
    UTöluðTalaHundruð,
    UTöluðTala10Til19Hundruð,
    UTöluðTalaÞúsundir,
    UTöluðTalaMilljónir,
    UTöluðTalaMilljarðar,
    UTöluðTalaBilljónir,
    UTöluðTalaBilljarðar,
    UTöluðTalaTrilljónir,
    UTöluðTalaTrilljarðar,
    UTöluðTalaKvaðrilljónir,
    UTöluðTalaKvaðrilljarðar,
    UTöluðTalaKvintilljónir,
    UTöluðTalaSextilljónir,
    UTöluðTalaSeptilljónir,
    UTöluðTalaOktilljónir,
) = [_multiply_children] * 15

# Plural named functions (e.g. "UTöluðTalaMilljónir") take the product of the children nodes
(
    UTöluðRaðtalaHundruð,
    UTöluðRaðtala10Til19Hundruð,
    UTöluðRaðtalaÞúsundir,
    UTöluðRaðtalaMilljónir,
    UTöluðRaðtalaMilljarðar,
    UTöluðRaðtalaBilljónir,
    UTöluðRaðtalaBilljarðar,
    UTöluðRaðtalaTrilljónir,
    UTöluðRaðtalaTrilljarðar,
    UTöluðRaðtalaKvaðrilljónir,
    UTöluðRaðtalaKvaðrilljarðar,
    UTöluðRaðtalaKvintilljónir,
    UTöluðRaðtalaSextilljónir,
    UTöluðRaðtalaSeptilljónir,
    UTöluðRaðtalaOktilljónir,
) = [_multiply_children] * 15

# Function for nonterminals which have children that should be added together
# e.g. "sextíu" (60) and "átta" (8) -> "sextíu (og) átta" (68)
def _sum_children(node: Any, params: Any, result: Result) -> None:
    if "numbers" in result:
        result["numbers"] = [sum(result["numbers"])]
    print("sum_children")


# "UTöluðTalaUndirX" functions take the sum of the children nodes,
# along with the root "UTöluðTala"
(
    UTöluðTala,
    UTöluðTalaUndirHundrað,
    UTöluðTalaUndirÞúsund,
    UTöluðTalaUndirMilljón,
    UTöluðTalaUndirMilljarði,
    UTöluðTalaUndirBilljón,
    UTöluðTalaUndirBilljarði,
    UTöluðTalaUndirTrilljón,
    UTöluðTalaUndirTrilljarði,
    UTöluðTalaUndirKvaðrilljón,
    UTöluðTalaUndirKvaðrilljarði,
    UTöluðTalaUndirKvintilljón,
    UTöluðTalaUndirSextilljón,
    UTöluðTalaUndirSeptilljón,
    UTöluðTalaUndirOktilljón,
) = [_sum_children] * 15

# "UTöluðTalaUndirX" functions take the sum of the children nodes,
# along with the root "UTöluðTala"
(
    UTöluðRaðtala,
    UTöluðRaðtalaUndirHundrað,
    UTöluðRaðtalaUndirÞúsund,
    UTöluðRaðtalaUndirMilljón,
    UTöluðRaðtalaUndirMilljarði,
    UTöluðRaðtalaUndirBilljón,
    UTöluðRaðtalaUndirBilljarði,
    UTöluðRaðtalaUndirTrilljón,
    UTöluðRaðtalaUndirTrilljarði,
    UTöluðRaðtalaUndirKvaðrilljón,
    UTöluðRaðtalaUndirKvaðrilljarði,
    UTöluðRaðtalaUndirKvintilljón,
    UTöluðRaðtalaUndirSextilljón,
    UTöluðRaðtalaUndirSeptilljón,
    UTöluðRaðtalaUndirOktilljón,
) = [_sum_children] * 15


# Function for nonterminals where we can perform a value lookup
# e.g. "hundraðasti" (result._root = "hundraðasti") -> 100
# Lowercase to avoid "Annar" auto-capitalization.
# TODO: Fix that issue.
def _lookup_function(node: Any, params: Any, result: Result) -> None:
    result["numbers"] = [_NUMBERS[result._root.lower()]]
    print("lookup_function")


# Define multiple functions with same functionality but different names
(
    UTöluðTala0,
    UTöluðTala1,
    UTöluðTala2Til9,
    UTöluðTala10Til19,
    UTöluðTalaTugir,
    UTöluðTalaHundrað,
    UTöluðTalaÞúsund,
    UTöluðTalaÞúsundHk,
    UTöluðTalaÞúsundKvk,
    UTöluðTalaMilljón,
    UTöluðTalaMilljarður,
    UTöluðTalaBilljón,
    UTöluðTalaBilljarður,
    UTöluðTalaTrilljón,
    UTöluðTalaTrilljarður,
    UTöluðTalaKvaðrilljón,
    UTöluðTalaKvaðrilljarður,
    UTöluðTalaKvintilljón,
    UTöluðTalaSextilljón,
    UTöluðTalaSeptilljón,
    UTöluðTalaOktilljón,
) = [_lookup_function] * 21

# Define multiple functions with same functionality but different names
(
    UTöluðRaðtala0,
    UTöluðRaðtala1,
    UTöluðRaðtala2Til9,
    UTöluðRaðtala10Til19,
    UTöluðRaðtalaTugir,
    UTöluðRaðtalaHundrað,
    UTöluðRaðtalaÞúsund,
    UTöluðRaðtalaMilljón,
    UTöluðRaðtalaMilljarður,
    UTöluðRaðtalaBilljón,
    UTöluðRaðtalaBilljarður,
    UTöluðRaðtalaTrilljón,
    UTöluðRaðtalaTrilljarður,
    UTöluðRaðtalaKvaðrilljón,
    UTöluðRaðtalaKvaðrilljarður,
    UTöluðRaðtalaKvintilljón,
    UTöluðRaðtalaSextilljón,
    UTöluðRaðtalaSeptilljón,
    UTöluðRaðtalaOktilljón,
) = [_lookup_function] * 19
