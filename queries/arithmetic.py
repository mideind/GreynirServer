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

"""

# TODO: Support "hvað er x í y veldi"


from math import sqrt

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

    # 'Hvað er nítjan sinnum 12?'
    # 'Hvað er sautján deilt með tveimur?'
    "hvað" "er" QArithmeticFirstNumber QArithmeticOperator QArithmeticSecondNumber '?'?
    | "hver" "er" QSquareRootOperator QArithmeticFirstNumber '?'?
#    | "hvað" "er" QArithmeticFirstNumber "í" QArithmeticSecondNumber "veldi" '?'?

QArithmeticNumberWord →

    # to is a declinable number word ('tveir/tvo/tveim/tveggja')
    # töl is an undeclinable number word ('sautján')
    # tala is a number ('17')
    "einn" | to | töl | tala

QArithmeticFirstNumber → QArithmeticNumberWord
QArithmeticSecondNumber → QArithmeticNumberWord

QArithmeticPlusOperator → "plús"
QArithmeticMinusOperator → "mínus" 
QArithmeticDivisionOperator → "deilt" "með"
QArithmeticMultiplicationOperator → "sinnum"

QSquareRootOperator → "kvaðratrótin" "af" | "kvaðratrót" "af"

QArithmeticOperator → 
    QArithmeticPlusOperator 
    | QArithmeticMinusOperator
    | QArithmeticMultiplicationOperator 
    | QArithmeticDivisionOperator

"""


def parse_num(number_str):
    num = None
    try:
        # Handle digits
        num = int(number_str)
    except ValueError:
        # Handle number words ("sautján")
        num = _NUMBER_WORDS.get(number_str, 0)
    except Exception as e:
        print("Unexpected exception: {0}".format(e))
        raise
    return num


def QArithmeticNumberWord(node, params, result):
    pass


def QArithmeticFirstNumber(node, params, result):
    print(result._canonical)
    result.first_num = parse_num(result._nominative)


def QArithmeticSecondNumber(node, params, result):
    result.second_num = parse_num(result._nominative)


def QSquareRootOperator(node, params, result):
    result.operator = result._canonical


def QArithmeticOperator(node, params, result):
    result.operator = result._canonical


def QArithmetic(node, params, result):
    """ Arithmetic query """
    # Set the query type
    result.qtype = "Arithmetic"
    result.qkey = "5"

    # if "bus_number" in result:
    #     # The bus number has been automatically
    #     # percolated upwards from a child node (see below).
    #     # Set the query key
    #     result.qkey = result.bus_number


_OPERATORS = {"sinnum": "*", "plús": "+", "mínus": "-", "deilt með": "/"}


def query_arithmetic(query, result):
    """ A query for arithmetic """

    eval_globals = {"__builtins__": None}

    operator = result.operator
    # Square root calculation
    if operator == "kvaðratrótin af":  # TODO: Ugh!
        # Allow sqrt function in eval namespace
        eval_globals["sqrt"] = sqrt

        # TODO: Size of number should be capped
        s = "sqrt({0})".format(result["first_num"])
    # Addition, subtraction, multiplication, division
    else:
        math_op = _OPERATORS.get(operator)

        # Check for division by zero
        if math_op == "/" and result["second_num"] == 0:
            # TODO: Handle this better
            return (None, None, None)

        s = "{0} {1} {2}".format(result["first_num"], math_op, result["second_num"])

    # TODO, safety checks here. This is eval!
    print(s)
    res = eval(s, eval_globals, {})
    print(res)

    if isinstance(res, float):
        # Convert to Icelandic decimal places
        answer = "{0:.2f}".format(res).replace(".", ",")
        # Strip trailing zeros
        while answer.endswith("0") or answer.endswith(","):
            answer = answer[:-1]
    else:
        answer = str(res)

    response = dict(answer=answer)
    voice_answer = (
        answer
    )  # "{0} {1} {2} er {3}".format(result["first_num"], operator, result["second_num"], answer)
    return response, answer, voice_answer


_QFUNC = {"Arithmetic": query_arithmetic}


def sentence(state, result):
    """ Called when sentence processing is complete """
    q = state["query"]
    if "qtype" in result:
        # Successfully matched a query type
        q.set_qtype(result.qtype)
        q.set_key(result.qkey)

        # Select a query function and execute it
        qfunc = _QFUNC.get(result.qtype)
        if qfunc is None:
            # Something weird going on - should not happen
            answer = result.qtype + ": " + result.qkey
            q.set_answer(dict(answer=answer), answer)
        else:
            try:
                (response, answer, voice_answer) = qfunc(q, result)
                q.set_answer(response, answer, voice_answer)
            except AssertionError:
                raise
            except Exception as e:
                raise
                q.set_error("E_EXCEPTION: {0}".format(e))
    else:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
