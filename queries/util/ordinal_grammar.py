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
    "núllti": 0,
    "fyrstur": 1,
    "annar": 2,
    "annars": 2,
    "þriðji": 3,
    "fjórði": 4,
    "fimmti": 5,
    "sjötti": 6,
    "sjöundi": 7,
    "áttundi": 8,
    "níundi": 9,
    "tíundi": 10,
    "ellefti": 11,
    "tólfti": 12,
    "þrettándi": 13,
    "fjórtándi": 14,
    "fimmtándi": 15,
    "sextándi": 16,
    "sautjándi": 17,
    "seytjándi": 17,
    "átjándi": 18,
    "nítjándi": 19,
    "tuttugasti": 20,
    "þrítugasti": 30,
    "fertugasti": 40,
    "fimmtugasti": 50,
    "sextugasti": 60,
    "sjötugasti": 70,
    "átttugasti": 80,
    "nítugasti": 90,
    "hundraðasti": 100,
    "hundruðasti": 100,
    "þúsundasti": 1000,
    "milljónasti": 10**6,
    "miljarðasti": 10**9,
    "milljarðasti": 10**9,
    "billjónasti": 10**12,
    "billjarðasti": 10**15,
    "trilljónasti": 10**18,
    "trilljarðasti": 10**21,
    "kvaðrilljónasti": 10**24,
}


# Function for nonterminals which have children that should be multiplied together
# e.g. "fimm" (5) and "hundruð" (100) -> "fimm hundruð" (500)
def _multiply_children(node: Any, params: Any, result: Result) -> None:
    if "numbers" in result:
        result["numbers"] = [reduce(mul, result["numbers"])]
    print("multiply_children")


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
