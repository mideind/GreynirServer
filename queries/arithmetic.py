"""

    Reynir: Natural language processing for Icelandic

    Arithmetic query response module

    Copyright (C) 2019 Miðeind ehf.

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


    This module handles arithmetic queries.

"""


import math
import json
import re
import logging

from queries import format_icelandic_float, gen_answer


_ARITHMETIC_QTYPE = "Arithmetic"

_NUMBER_WORDS = {
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
    "milljón": 1e6,
    "milljarður": 1e9,
}

# Ordinal words in the accusative case
_ORDINAL_WORDS_DATIVE = {
    "fyrsta": 1,
    "öðru": 2,
    "þriðja": 3,
    "fjórða": 4,
    "fimmta": 5,
    "sjötta": 6,
    "sjöunda": 7,
    "áttunda": 8,
    "níunda": 9,
    "tíunda": 10,
    "ellefta": 11,
    "tólfta": 12,
    "þrettánda": 13,
    "fjórtánda": 14,
    "fimmtánda": 15,
    "sextánda": 16,
    "sautjánda": 17,
    "átjánda": 18,
    "nítjánda": 19,
    "tuttugasta": 20,
    "þrítugasta": 30,
    "fertugasta": 40,
    "fimmtugasta": 50,
    "sextugasta": 60,
    "sjötugasta": 70,
    "áttatugasta": 80,
    "nítugasta": 90,
    "hundraðasta": 100,
    "þúsundasta": 1000,
    "milljónasta": 1e6,
}

# Indicate that this module wants to handle parse trees for queries,
# as opposed to simple literal text strings
HANDLE_TREE = True

# The context-free grammar for the queries recognized by this plug-in module
GRAMMAR = """

# ----------------------------------------------
#
# Query grammar for arithmetic-related queries
#
# ----------------------------------------------

# A plug-in query grammar always starts with the following,
# adding one or more query productions to the Query nonterminal

Query →
    QArithmetic

# By convention, names of nonterminals in query grammars should
# start with an uppercase Q

QArithmetic →
    # 'Hvað er X sinnum/deilt með/plús/mínus Y?'
    QArGenericPrefix QArStd '?'?

    # 'Hver er summan af X og Y?'
    | QArAnyPrefix QArSum '?'?

    # 'Hver/Hvað er kvaðratrótin af X?'
    | QArAnyPrefix QArSqrt '?'?
    
    # 'Hvað er X í Y veldi?'
    | QArGenericPrefix QArPow '?'?

    # 'Hvað er(u) 12 prósent af 93'
    | QArGenericPrefix QArPercent '?'?

$score(35) QArithmetic

QArGenericPrefix → "hvað" "er" | "hvað" "eru" | 0
QArSpecificPrefix → "hver" "er" | 0
QArAnyPrefix → QArGenericPrefix | QArSpecificPrefix

QArStd → QArNumberWord QArOperator QArNumberWord
QArSum → QArPlusOperator QArNumberWord "og" QArNumberWord
QArSqrt → QArSquareRootOperator QArNumberWord
QArPow → QArNumberWord "í" QArOrdinalOrNumberWord QArPowOperator
QArPercent → QArPercentOperator QArNumberWord

QArNumberWord →
    # to is a declinable number word ('tveir/tvo/tveim/tveggja')
    # töl is an undeclinable number word ('sautján')
    # tala is a number ('17')
    to | töl | tala | "núlli" | "núll"

QArOrdinalWord →
    "{0}" | raðnr

QArOrdinalOrNumberWord →
    QArNumberWord | QArOrdinalWord

QArPlusOperator → "plús"
QArMinusOperator → "mínus" 
QArDivisionOperator → "deilt" "með" | "skipt" "með"
QArMultiplicationOperator → "sinnum" | "margfaldað" "með"

QArSquareRootOperator → "kvaðratrótin" "af" | "kvaðratrót" "af"
QArPowOperator → "veldi"
QArPercentOperator → Prósenta "af"

QArOperator → 
    QArPlusOperator 
    | QArMinusOperator
    | QArMultiplicationOperator 
    | QArDivisionOperator

""".format(
    " | ".join(['"' + w + '"' for w in _ORDINAL_WORDS_DATIVE.keys()])
)


def parse_num(num_str):
    """ Parse Icelandic number string to float or int """
    num = None
    try:
        # Handle numbers w. Icelandic decimal places ("17,2")
        if re.search(r"^\d+,\d+", num_str):
            num = float(num_str.replace(",", "."))
        # Handle digits ("17")
        else:
            num = float(num_str)
    except ValueError:
        # Handle number words ("sautján")
        if num_str in _NUMBER_WORDS:
            num = _NUMBER_WORDS[num_str]
        # Ordinal words in dative case ("sautjánda")
        elif num_str in _ORDINAL_WORDS_DATIVE:
            num = _ORDINAL_WORDS_DATIVE[num_str]
        # Ordinal number strings ("17.")
        elif re.search(r"^\d+\.$", num_str):
            num = int(num_str[:-1])
        else:
            num = 0
    except Exception as e:
        print("Unexpected exception: {0}".format(e))
        raise
    return num


def add_num(num, result):
    """ Add a number to accumulated number args """
    if "numbers" not in result:
        result.numbers = []
    if isinstance(num, str):
        result.numbers.append(parse_num(num))
    else:
        result.numbers.append(num)


def QArNumberWord(node, params, result):
    add_num(result._nominative, result)


def QArOrdinalWord(node, params, result):
    add_num(result._canonical, result)


def QArPlusOperator(node, params, result):
    result.operator = "plus"


def QArMinusOperator(node, params, result):
    result.operator = "minus"


def QArDivisionOperator(node, params, result):
    result.operator = "divide"


def QArMultiplicationOperator(node, params, result):
    result.operator = "multiply"


def QArSquareRootOperator(node, params, result):
    result.operator = "sqrt"


def QArPowOperator(node, params, result):
    result.operator = "pow"


def QArPercentOperator(node, params, result):
    result.operator = "percent"


def Prósenta(node, params, result):
    # Find percentage terminal
    d = result.find_descendant(t_base="prósenta")

    # Extract percentage number from the token's auxiliary information
    # which is attached to the node as a json-encoded array
    if d and d._node.aux:
        aux = json.loads(d._node.aux)
        add_num(aux[0], result)
    else:
        # We shouldn't be here. Something went horriby wrong somewhere.
        raise ValueError("No auxiliary information in percentage token")


def QArStd(node, params, result):
    # Used later for formatting voice answer string,
    # e.g. "[tveir plús tveir] er [fjórir]"
    result.desc = result._canonical


def QArSum(node, params, result):
    result.desc = result._canonical


def QArSqrt(node, params, result):
    result.desc = result._canonical


def QArPow(node, params, result):
    result.desc = result._canonical


def QArPercent(node, params, result):
    result.desc = result._canonical


def QArithmetic(node, params, result):
    # Set query type
    result.qtype = _ARITHMETIC_QTYPE


# Map operator name to python operator
_STD_OPERATORS = {"multiply": "*", "divide": "/", "plus": "+", "minus": "-"}

# Number of args required for each operator
_OP_NUM_ARGS = {
    "multiply": 2,
    "divide": 2,
    "plus": 2,
    "minus": 2,
    "sqrt": 1,
    "pow": 2,
    "percent": 2,
}


def calc_arithmetic(query, result):
    """ Calculate the answer to an arithmetic query """
    operator = result.operator
    nums = result.numbers
    desc = result.desc

    # Ensure that we have the right number of
    # number args for the operation in question
    assert _OP_NUM_ARGS[operator] == len(nums)

    # Global namespace for eval
    # Block access to all builtins
    eval_globals = {"__builtins__": None}

    # Square root calculation
    if operator == "sqrt":
        if len(str(nums[0])) > 100:
            return gen_answer("Þessi tala er of há.")
        # Allow sqrt function in eval namespace
        eval_globals["sqrt"] = math.sqrt
        s = "sqrt({0})".format(nums[0])

    # Pow
    elif operator == "pow":
        # Cap max pow
        if nums[1] > 50:
            return gen_answer("Þetta er of hátt veldi.")
        # Allow pow function in eval namespace
        eval_globals["pow"] = pow
        s = "pow({0},{1})".format(nums[0], nums[1])

    # Percent
    elif operator == "percent":
        s = "({0} * {1}) / 100.0".format(nums[0], nums[1])

    # Addition, subtraction, multiplication, division
    elif operator in _STD_OPERATORS:
        math_op = _STD_OPERATORS[operator]

        # Check for division by zero
        if math_op == "/" and nums[1] == 0:
            return gen_answer("Það er ekki hægt að deila með núlli.")

        s = "{0} {1} {2}".format(nums[0], math_op, nums[1])
    else:
        logging.warning("Unknown operator: {0}".format(operator))
        return None

    # Set arithmetic expression as query key
    result.qkey = s

    # Run eval on expression
    res = eval(s, eval_globals, {})

    if isinstance(res, float):
        # Convert result to Icelandic decimal format
        answer = format_icelandic_float(res)
    else:
        answer = str(res)

    response = dict(answer=answer)
    voice_answer = "{0} er {1}".format(desc, answer)

    return response, answer, voice_answer


def sentence(state, result):
    """ Called when sentence processing is complete """
    q = state["query"]
    if "qtype" in result:
        # Successfully matched a query type
        q.set_qtype(result.qtype)

        try:
            r = calc_arithmetic(q, result)
            if r is not None:
                q.set_answer(*r)
                q.set_key(result.get("qkey"))
            else:
                raise Exception("Arithmetic calculation failed")
        except Exception as e:
            q.set_error("E_EXCEPTION: {0}".format(e))
    else:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
