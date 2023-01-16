"""

    Greynir: Natural language processing for Icelandic

    Number parsing grammar.

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


    Utility module
    Exposes nonterminal "URaðtala" for parsing ordinal
    numbers either written in natural language or in digits,
    Constructs the value of the ordinal number in result["numbers"],
    and returns the ordinal number in result["ordinals"].

"""

# TODO: Support "einn fjórði" etc.

from tree import Result, ParamList, Node
from queries.util import read_utility_grammar_file
from queries.util.cardinals import (
    _sum_children,
    _multiply_children,
    _lookup_function_generator,
)

# The context-free grammar for number utterances recognized by this utility module
GRAMMAR = read_utility_grammar_file("ordinals")

_ORDINAL_NUMBERS = {
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


def URaðtala(node: Node, params: ParamList, result: Result) -> None:
    # Check if a number was specified in digits instead of written out
    tala = node.first_child(lambda n: n.has_t_base("tala"))
    if tala is not None and tala.contained_number is not None:
        result["numbers"] = [int(tala.contained_number)]
    result["ordinals"] = [result.numbers[0]]


# Plural named functions (e.g. "UTöluðRaðtalaMilljónir") take the product of the children nodes
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


# "UTöluðRaðtalaUndirX" functions take the sum of the children nodes,
# along with the root "UTöluðRaðtala"
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


# Singular named functions (e.g. "UTöluðTalaHundrað") find the corresponding numeric value of the word
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
) = [_lookup_function_generator(_ORDINAL_NUMBERS)] * 19
