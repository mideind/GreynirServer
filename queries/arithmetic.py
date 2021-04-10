"""

    Greynir: Natural language processing for Icelandic

    Arithmetic query response module

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


    This module handles arithmetic queries.

"""

from typing import Dict, Any, Mapping, Optional, Sequence, cast

import math
import json
import re
import logging
import random

from query import AnswerTuple, ContextDict, Query, QueryStateDict
from queries import iceformat_float, gen_answer
from tree import Result


_ARITHMETIC_QTYPE = "Arithmetic"


# Lemmas of keywords that could indicate that the user is trying to use this module
TOPIC_LEMMAS: Sequence[str] = [
    "plús",
    "mínus",
    "margfalda",
    "deila",
    "samlagning",
    "frádráttur",
    "margföldun",
    "kvaðratrót",
    "ferningsrót",
    "veldi",
    "prósent",
    "prósenta",
    "hundraðshluti",
    "hlutfall",
    "frádreginn",
    "viðbættur",
]


def help_text(lemma: str) -> str:
    """Help text to return when query.py is unable to parse a query but
    one of the above lemmas is found in it"""
    if lemma in ("kvaðratrót", "ferningsrót"):
        return "Ég get svarað ef þú spyrð til dæmis: {0}?".format(
            random.choice(
                ("Hver er kvaðratrótin af tuttugu", "Hver er ferningsrótin af áttatíu")
            )
        )
    return "Ég get svarað ef þú spyrð til dæmis: {0}?".format(
        random.choice(
            (
                "Hvað eru sautján sinnum þrjátíu og fjórir",
                "Hvað er tvö hundruð mínus sautján",
                "Hver er kvaðratrótin af tuttugu",
                "Hvað eru átján að frádregnum sjö",
                "Hvað er ellefu plús tvö hundruð og fimm",
                "Hvað eru níu prósent af tvö þúsund",
            )
        )
    )


_NUMBER_WORDS: Mapping[str, float] = {
    "núll": 0,
    "einn": 1,
    "einu": 1,
    "tveir": 2,
    "tveim": 2,
    "tvisvar sinnum": 2,
    "þrír": 3,
    "þrem": 3,
    "þremur": 3,
    "þrisvar sinnum": 3,
    "fjórir": 4,
    "fjórum": 4,
    "fjórum sinnum": 4,
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
    "hundruð": 100,
    "hundruðir": 100,
    "þúsund": 1000,
    "þúsundir": 1000,
    "milljón": 1e6,
    "milljónir": 1e6,
    "milljarður": 1e9,
    "milljarðar": 1e9,
}

_FRACTION_WORDS: Mapping[str, float] = {
    "helmingur": 1 / 2,
    "helmingurinn": 1 / 2,
    "þriðjungur": 1 / 3,
    "þriðjungurinn": 1 / 3,
    "fjórðungur": 1 / 4,
    "fjórðungurinn": 1 / 4,
    "fimmtungur": 1 / 5,
    "fimmtungurinn": 1 / 5,
    "sjöttungur": 1 / 6,
    "sjöttungurinn": 1 / 6,
}

# Ordinal words in the nominative case
_ORDINAL_WORDS_NOM: Mapping[str, float] = {
    "fyrsti": 1,
    "annar": 2,
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
    "átjándi": 18,
    "nítjándi": 19,
    "tuttugasti": 20,
    "þrítugasti": 30,
    "fertugasti": 40,
    "fimmtugasti": 50,
    "sextugasti": 60,
    "sjötugasti": 70,
    "áttatugasti": 80,
    "nítugasti": 90,
    "hundraðasti": 100,
    "þúsundasti": 1000,
    "milljónasti": 1e6,
}

# Ordinal words in the dative case
_ORDINAL_WORDS_DATIVE: Mapping[str, float] = {
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

# The grammar nonterminals this module wants to handle
QUERY_NONTERMINALS = {"QArithmetic", "QArPi"}

# The context-free grammar for the queries recognized by this plug-in module
# Uses "QAr" as prefix for grammar namespace
GRAMMAR = """

# A plug-in query grammar always starts with the following,
# adding one or more query productions to the Query nonterminal

Query →
    QArithmetic
    # 'Hvaða tala er pí'
    | QArPi

QArithmetic →
    QArithmeticQuery '?'?

QArPi →
    QArPiQuery '?'?

$score(+55) QArithmetic
$score(+55) QArPi

QArithmeticQuery →
    # 'Hvað er X sinnum/deilt með/plús/mínus Y'
    QArGenericPrefix QArStd

    # 'Hver er summan af X og Y'
    | QArAnyPrefix QArSum

    # 'Hvað er tvisvar/þrisvar/fjórum sinnum Y'
    | QArAnyPrefix QArMult

    # 'Hver/Hvað er kvaðratrótin af X'
    | QArAnyPrefix QArSqrt

    # 'Hvað er X í Y veldi?'
    | QArGenericPrefix QArPow

    # 'Hvað er(u) 12 prósent af 93'
    | QArGenericPrefix QArPercent

    # 'Hvað er fjórðungurinn af 1220'
    # 'Hvað er einn tuttugasti af 190'
    | QArAnyPrefix QArFraction

    # 'Hvað er 8900 með vaski/virðisaukaskatti'
    | QArGenericPrefix? QArVAT


/arfall = nf þgf

QArGenericPrefix → "hvað" "er"? | "hvað" "eru" | "reiknaðu" | "geturðu" "reiknað" | 0
QArSpecificPrefix → "hver" "er"? | "reiknaðu" | "geturðu" "reiknað" | 0
QArAnyPrefix → QArGenericPrefix | QArSpecificPrefix

QArStd → QArNumberWord_nf QArOperator/arfall QArNumberWord/arfall

QArOperator/arfall →
    QArPlusOperator/arfall
    | QArMinusOperator/arfall
    | QArMultiplicationOperator/arfall
QArOperator_þgf →
    QArDivisionOperator_þgf

# Infix operators
QArPlusOperator_nf → "plús" | "+"
QArPlusOperator_þgf → "að" "viðbættum"

QArMinusOperator_nf → "mínus" | "-"
QArMinusOperator_þgf → "að" "frádregnum"

QArMultiplicationOperator_nf → "sinnum" | "x"
QArMultiplicationOperator_þgf → "margfaldað" "með" | "margfaldaðir" "með"

QArDivisionOperator_þgf → "deilt" "með" | "skipt" "með" | "/"

QArSum → QArSumOperator QArNumberWordAny "og" QArNumberWordAny
QArMult → QArMultOperator QArNumberWord_nf
QArSqrt → QArSquareRootOperator QArNumberWordAny
QArPow → QArPowOperator
QArPercent → QArPercentOperator QArNumberWordAny
QArFraction → QArFractionOperator QArNumberWordAny
QArVAT → QArCurrencyOrNum QArWithVAT | QArCurrencyOrNum QArWithoutVAT

# Prevent nonterminal from being optimized out of the grammar
$tag(keep) QArPow

# Prefix operators
QArSumOperator → "summan" "af"
QArSquareRootOperator →
    "kvaðratrótin" "af" | "kvaðratrótina" "af" | "kvaðratrót" "af"
    | "ferningsrótin" "af" | "ferningsrót" "af"
QArPercentOperator → Prósenta "af"

QArFractionOperator →
    QArFractionWord_nf "af"

QArMultOperator →
    # 'hvað er tvisvar sinnum X?'
    # The following phrases are defined in reynir/config/Phrases.conf
    'tvisvar_sinnum' | 'þrisvar_sinnum' | 'fjórum_sinnum'

QArPowOperator →
    QArNumberWord_nf "í" QArOrdinalOrNumberWord_þgf "veldi"
    | QArNumberWord_nf "í" "veldinu" QArNumberWord_nf
    | QArNumberWord_nf "í" "veldi" QArNumberWord_nf

QArNumberWord/arfall →
    # to is a declinable number word ('tveir/tvo/tveim/tveggja')
    # töl is an undeclinable number word ('sautján')
    # tala is a number ('17')
    to/arfall | töl | tala | "pí" | 'milljarður:kk'/arfall

QArNumberWord_nf →
    "núll" | QArLastResult_nf

QArNumberWord_þgf →
    "núlli" | QArLastResult_þgf

QArLastResult/arfall →
    # Reference to last result
    'það:pfn'_et/arfall

QArNumberWordAny → QArNumberWord/arfall

QArFractionWord_nf →
    {0} | {1}

QArOrdinalWord_þgf →
    {2} | raðnr

QArOrdinalOrNumberWord_þgf →
    QArNumberWord_þgf | QArOrdinalWord_þgf

QArWithVAT →
    "með" "vaski" | "með" "vask" | "með" "virðisaukaskatti"

QArWithoutVAT →
    "án" "vasks" | "án" "vask" | "án" "virðisaukaskatts"

QArCurrencyOrNum →
    QArNumberWordAny | QArNumberWordAny "íslenskar"? "krónur" | amount

QArPiQuery →
    "hvað" "er" "pí"
    | "hvaða" "tala" "er" "pí"
    | "hver" "er" "talan"? "pí"
    | "skilgreindu" "töluna"? "pí"
    | "hvað" "eru" "margir" "aukastafir" "í" "tölunni"? "pí"
    | "hvað" "eru" "margir" "tölustafir" "í" "tölunni"? "pí"
    | "hvað" "hefur" "talan"? "pí" "marga" "aukastafi"
    | "hversu" "marga" "aukastafi" "hefur" "talan"? "pí"

""".format(
    " | ".join('"' + w + '"' for w in _FRACTION_WORDS.keys()),  # Fraction words
    " | ".join(
        '"einn" ' + '"' + w + '"' for w in _ORDINAL_WORDS_NOM.keys()  # Ordinals
    ),  # "einn þriðji" etc.
    " | ".join('"' + w + '"' for w in _ORDINAL_WORDS_DATIVE.keys()),  # OrdinalWord
)


def parse_num(num_str: str) -> float:
    """ Parse Icelandic number string to float or int """
    num = None
    try:
        # Pi
        if num_str == "pí":
            num = math.pi
        # Handle numbers w. Icelandic decimal places ("17,2")
        elif re.search(r"^\d+,\d+$", num_str):
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
        logging.warning("Unexpected exception: {0}".format(e))
        raise
    return num


def add_num(num, result: Result):
    """ Add a number to accumulated number args """
    if "numbers" not in result:
        result.numbers = []
    if isinstance(num, str):
        result.numbers.append(parse_num(num))
    else:
        result.numbers.append(num)


def terminal_num(t):
    """Extract numerical value from terminal token's auxiliary info,
    which is attached as a json-encoded array"""
    if t and t._node.aux:
        aux = json.loads(t._node.aux)
        if isinstance(aux, int) or isinstance(aux, float):
            return aux
        return aux[0]


def QArNumberWord(node, params, result: Result):
    result._canonical = result._text
    if "context_reference" in result or "error_context_reference" in result:
        # Already pushed the context reference
        # ('það', 'því'): we're done
        return
    d = result.find_descendant(t_base="tala")
    if d:
        add_num(terminal_num(d), result)
    else:
        add_num(result._nominative, result)


def QArOrdinalWord(node, params, result: Result):
    add_num(result._canonical, result)


def QArFractionWord(node, params, result: Result):
    fn = result._canonical.lower()
    fp = _FRACTION_WORDS.get(fn)
    if not fp:
        s = re.sub(r"^einn\s", "", fn)
        fp = _ORDINAL_WORDS_NOM.get(s)
        if fp:
            fp = 1 / int(fp)
    add_num(fp, result)


def QArMultOperator(node, params, result: Result):
    """ 'tvisvar_sinnum', 'þrisvar_sinnum', 'fjórum_sinnum' """
    add_num(result._nominative, result)
    result.operator = "multiply"


def QArLastResult(node, params, result: Result):
    """Reference to previous result, usually via the words
    'það' or 'því' ('Hvað er það sinnum sautján?')"""
    q = result.state.get("query")
    ctx = None if q is None else q.fetch_context()
    if ctx is None or "result" not in ctx:
        # There is a reference to a previous result
        # which is not available: flag an error
        result.error_context_reference = True
    else:
        add_num(ctx["result"], result)
        result.context_reference = True


def QArPlusOperator(node, params, result: Result):
    result.operator = "plus"


def QArSumOperator(node, params, result: Result):
    result.operator = "plus"


def QArMinusOperator(node, params, result: Result):
    result.operator = "minus"


def QArDivisionOperator(node, params, result: Result):
    result.operator = "divide"


def QArMultiplicationOperator(node, params, result: Result):
    """ 'Hvað er 17 sinnum 34?' """
    result.operator = "multiply"


def QArSquareRootOperator(node, params, result: Result):
    result.operator = "sqrt"


def QArPowOperator(node, params, result: Result):
    result.operator = "pow"


def QArPercentOperator(node, params, result: Result):
    result.operator = "percent"


def QArFractionOperator(node, params, result: Result):
    result.operator = "fraction"


def Prósenta(node, params, result: Result):
    # Find percentage terminal
    d = result.find_descendant(t_base="prósenta")
    if d:
        add_num(terminal_num(d), result)
    else:
        # We shouldn't be here. Something went horriby wrong somewhere.
        raise ValueError("No auxiliary information in percentage token")


def QArCurrencyOrNum(node, params, result: Result):
    amount = node.first_child(lambda n: n.has_t_base("amount"))
    if amount is not None:
        # Found an amount terminal node
        result.amount, curr = amount.contained_amount
        add_num(result.amount, result)


def QArStd(node, params, result: Result):
    # Used later for formatting voice answer string,
    # e.g. "[tveir plús tveir] er [fjórir]"
    result.desc = (
        result._canonical.replace("+", " plús ")
        .replace("-", " mínus ")
        .replace("/", " deilt með ")
        .replace(" x ", " sinnum ")
    )


def QArSum(node, params, result: Result):
    result.desc = result._canonical


def QArMult(node, params, result: Result):
    result.desc = result._canonical


def QArSqrt(node, params, result: Result):
    result.desc = result._canonical


def QArPow(node, params, result: Result):
    result.desc = result._canonical


def QArPercent(node, params, result: Result):
    result.desc = result._canonical


def QArFraction(node, params, result: Result):
    result.desc = result._canonical


def QArPiQuery(node, params, result: Result):
    result.qtype = "PI"


def QArWithVAT(node, params, result: Result):
    result.operator = "with_vat"


def QArWithoutVAT(node, params, result: Result):
    result.operator = "without_vat"


def QArVAT(node, params, result: Result):
    result.desc = result._canonical
    result.qtype = "VSK"


def QArithmetic(node, params, result: Result):
    # Set query type
    result.qtype = _ARITHMETIC_QTYPE


# Map operator name to corresponding python operator
_STD_OPERATORS: Mapping[str, str] = {
    "multiply": "*",
    "divide": "/",
    "plus": "+",
    "minus": "-",
}

# Number of args required for each operator
_OP_NUM_ARGS: Mapping[str, int] = {
    "multiply": 2,
    "divide": 2,
    "plus": 2,
    "minus": 2,
    "sqrt": 1,
    "pow": 2,
    "percent": 2,
    "fraction": 2,
    "with_vat": 1,
    "without_vat": 1,
}


# Value added tax multiplier
_VAT_MULT = 1.24


def calc_arithmetic(query: Query, result: Result) -> Optional[AnswerTuple]:
    """ Calculate the answer to an arithmetic query """
    operator = result.operator
    nums = result.numbers
    desc = result.desc

    if "error_context_reference" in result:
        # Used 'það' or 'því' without context
        return gen_answer("Ég veit ekki til hvers þú vísar.")

    # Ensure that we have the right number of
    # number args for the operation in question
    assert _OP_NUM_ARGS[operator] == len(nums)

    # Global namespace for eval
    # Block access to all builtins
    eval_globals: Dict[str, Any] = {"__builtins__": None}

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

    # Fraction
    elif operator == "fraction":
        s = "{0} * {1}".format(nums[0], nums[1])

    # Add VAT to sum
    elif operator == "with_vat":
        s = "{0} * {1}".format(nums[0], _VAT_MULT)

    # Subtract VAT from sum
    elif operator == "without_vat":
        s = "{0} / {1}".format(nums[0], _VAT_MULT)

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
    res: float = eval(s, eval_globals, {})

    if isinstance(res, float):
        # Convert result to Icelandic decimal format
        answer = iceformat_float(res)
    else:
        answer = str(res)

    response = dict(answer=answer, result=res)
    voice_answer = "{0} er {1}".format(desc, answer)

    return response, answer, voice_answer


def pi_answer(q: Query, result: Result) -> AnswerTuple:
    """ Define pi (π) """
    answer = "Talan π („pí“) er stærðfræðilegi fastinn 3,14159265359 eða þar um bil."
    voice = "Talan pí er stærðfræðilegi fastinn 3,14159265359 eða þar um bil."
    response = dict(answer=answer, result=math.pi)
    q.set_context(dict(result=3.14159265359))
    return response, answer, voice


def sentence(state: QueryStateDict, result: Result) -> None:
    """ Called when sentence processing is complete """
    q = state["query"]
    if "qtype" in result:
        # Successfully matched a query type
        q.set_qtype(result.qtype)

        try:
            r: Optional[AnswerTuple]
            if result.qtype == "PI":
                r = pi_answer(q, result)
            else:
                r = calc_arithmetic(q, result)
            if r is not None:
                q.set_answer(*r)
                q.set_key(result.get("qkey"))
                if "result" in r[0]:
                    # Pass the result into a query context having
                    # the 'result' property
                    res: float = cast(Any, r[0])["result"]
                    ctx = cast(ContextDict, dict(result=res))
                    q.set_context(ctx)
            else:
                raise Exception("Failed to answer arithmetic query")
        except Exception as e:
            logging.warning("Exception in arithmetic module: {0}".format(e))
            q.set_error("E_EXCEPTION: {0}".format(e))
    else:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
