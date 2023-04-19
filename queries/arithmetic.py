"""

    Greynir: Natural language processing for Icelandic

    Arithmetic query response module

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


    This module handles arithmetic queries.

"""

# TODO: Hvað er X með Y aukastöfum?
# TODO: Hvað er kvaðratrótin af mínus 1? :)
# TODO: Styðja hvað er X þúsund "kall" með vask?

from typing import (
    Callable,
    Any,
    List,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    Union,
    cast,
)

import math
import operator
import json
import re
import logging
import random

from queries import AnswerTuple, ContextDict, Query, QueryStateDict
from queries.util import iceformat_float, gen_answer, read_grammar_file
from tree import Result, Node, TerminalNode
from speech.trans import gssml


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
    "frádreginn",
    "viðbættur",
]


def help_text(lemma: str) -> str:
    """Help text to return when query processor is unable to parse a query but
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
    "eitt": 1,
    "ein": 1,
    "einu": 1,
    "einum": 1,
    "einni": 1,
    "tveir": 2,
    "tvö": 2,
    "tvær": 2,
    "tveim": 2,
    "tveimur": 2,
    "tvisvar sinnum": 2,
    "þrír": 3,
    "þrjár": 3,
    "þrjú": 3,
    "þrem": 3,
    "þremur": 3,
    "þrisvar sinnum": 3,
    "fjórir": 4,
    "fjögur": 4,
    "fjórar": 4,
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
GRAMMAR = read_grammar_file(
    "arithmetic",
    # Fraction words
    fraction_words=" | ".join('"' + w + '"' for w in _FRACTION_WORDS.keys()),
    # "einn þriðji" etc. ("einn" followed by an ordinal)
    one_xth_words=" | ".join(
        '"einn" ' + '"' + w + '"' for w in _ORDINAL_WORDS_NOM.keys()
    ),
    # OrdinalWord
    ordinal_words=" | ".join('"' + w + '"' for w in _ORDINAL_WORDS_DATIVE.keys()),
)


def parse_num(num_str: str) -> float:
    """Parse Icelandic number string to float or int"""
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
        logging.warning(f"Unexpected exception parsing num: {e}")
        raise
    return num


def add_num(num: Optional[Union[str, int, float]], result: Result):
    """Add a number to accumulated number args"""
    if "numbers" not in result:
        result.numbers = []
    rn = cast(List[float], result.numbers)
    if isinstance(num, str):
        rn.append(parse_num(num))
    elif num is not None:
        rn.append(num)


def terminal_num(t: Optional[Result]) -> Optional[Union[str, int, float]]:
    """Extract numerical value from terminal token's auxiliary info,
    which is attached as a json-encoded array"""
    if t:
        tnode = cast(TerminalNode, t._node)
        if tnode:
            aux = json.loads(tnode.aux)
            if isinstance(aux, int) or isinstance(aux, float):
                return aux
            return aux[0]
    return None


def QArNumberWord(node: Node, params: QueryStateDict, result: Result) -> None:
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


def QArOrdinalWord(node: Node, params: QueryStateDict, result: Result) -> None:
    add_num(result._canonical, result)


def QArFractionWord(node: Node, params: QueryStateDict, result: Result) -> None:
    fn = result._canonical.lower()
    fp = _FRACTION_WORDS.get(fn)
    if not fp:
        s = re.sub(r"^einn\s", "", fn)
        fp = _ORDINAL_WORDS_NOM.get(s)
        if fp:
            fp = 1 / int(fp)
    add_num(fp, result)
    result.frac_desc = fn  # Used in voice answer


def QArMultOperator(node: Node, params: QueryStateDict, result: Result) -> None:
    """'tvisvar_sinnum', 'þrisvar_sinnum', 'fjórum_sinnum'"""
    add_num(result._nominative, result)
    result.op = "multiply"


def QArLastResult(node: Node, params: QueryStateDict, result: Result) -> None:
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


def QArPlusOperator(node: Node, params: QueryStateDict, result: Result) -> None:
    result.op = "plus"


def QArSumOperator(node: Node, params: QueryStateDict, result: Result) -> None:
    result.op = "plus"


def QArMinusOperator(node: Node, params: QueryStateDict, result: Result) -> None:
    result.op = "minus"


def QArDivisionOperator(node: Node, params: QueryStateDict, result: Result) -> None:
    result.op = "divide"


def QArMultiplicationOperator(
    node: Node, params: QueryStateDict, result: Result
) -> None:
    result.op = "multiply"


def QArSquareRootOperator(node: Node, params: QueryStateDict, result: Result) -> None:
    result.op = "sqrt"


def QArPowOperator(node: Node, params: QueryStateDict, result: Result) -> None:
    result.op = "pow"


def QArPercentOperator(node: Node, params: QueryStateDict, result: Result) -> None:
    result.op = "percent"


def QArFractionOperator(node: Node, params: QueryStateDict, result: Result) -> None:
    result.op = "fraction"


def Prósenta(node: Node, params: QueryStateDict, result: Result) -> None:
    # Find percentage terminal
    d = result.find_descendant(t_base="prósenta")
    if d:
        add_num(terminal_num(d), result)
    else:
        # We shouldn't be here. Something went horriby wrong somewhere.
        raise ValueError("No auxiliary information in percentage token")


def QArCurrencyOrNum(node: Node, params: QueryStateDict, result: Result) -> None:
    amount: Optional[Node] = node.first_child(lambda n: n.has_t_base("amount"))
    if amount is not None:
        # Found an amount terminal node
        amt = amount.contained_amount
        if amt:
            result.amount, _ = amt
            add_num(result.amount, result)


def QArPiQuery(node: Node, params: QueryStateDict, result: Result) -> None:
    result.qtype = "PI"


def QArWithVAT(node: Node, params: QueryStateDict, result: Result) -> None:
    result.op = "with_vat"


def QArWithoutVAT(node: Node, params: QueryStateDict, result: Result) -> None:
    result.op = "without_vat"


def QArVAT(node: Node, params: QueryStateDict, result: Result) -> None:
    result.qtype = "VSK"


def QArithmetic(node: Node, params: QueryStateDict, result: Result) -> None:
    # Set query type
    result.qtype = _ARITHMETIC_QTYPE


# Map operator name to corresponding
# operator function, voice version and symbol
_STD_OPERATORS: Mapping[str, Tuple[Callable[[Any, Any], Any], str, str]] = {
    "plus": (operator.add, "plús", "+"),
    "minus": (operator.sub, "mínus", "-"),
    "multiply": (operator.mul, "sinnum", "*"),
    "divide": (operator.truediv, "deilt með", "/"),
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
    """Calculate the answer to an arithmetic query"""
    op: str = result.op
    nums = cast(List[float], result.numbers)

    # Shorter names for common gssml function calls
    fmt_num: Callable[..., str] = lambda f, **kw: gssml(
        f,
        type="float",
        gender=kw.get("gender", "kk"),
        case=kw.get("case", "nf"),
    )
    fmt_ord: Callable[..., str] = lambda f, **kw: gssml(
        f,
        type="ordinal",
        gender=kw.get("gender", "kk"),
        case=kw.get("case", "nf"),
    )
    if "error_context_reference" in result:
        # Used 'það' or 'því' without context
        return gen_answer("Ég veit ekki til hvers þú vísar.")

    # Ensure that we have the right number of
    # number args for the operation in question
    assert _OP_NUM_ARGS[op] == len(
        nums
    ), f"Incorrect number of arguments: {_OP_NUM_ARGS[op]} != {len(nums)}"

    # Square root calculation
    if op == "sqrt":
        if len(str(nums[0])) > 100:
            return gen_answer("Þessi tala er of há.")
        res = round(math.sqrt(nums[0]), 2)
        s = f"sqrt({nums[0]})"
        voice = f"Kvaðratrótin af {fmt_num(nums[0])} er {fmt_num(res)}"

    # Pow
    elif op == "pow":
        # Cap max pow
        if nums[1] > 50:
            return gen_answer("Þetta er of hátt veldi.")
        res = pow(nums[0], nums[1])
        s = f"pow({nums[0]}, {nums[1]})"
        voice = (
            f"{fmt_num(nums[0])} í "
            f"{fmt_ord(nums[1], gender='hk', case='þgf')} veldi "
            f"er {fmt_num(res)}"
        )

    # Percent
    elif op == "percent":
        res = (nums[0] * nums[1]) / 100.0
        s = f"({nums[0]} * {nums[1]}) / 100.0"
        voice = (
            f"{fmt_num(nums[0], gender='hk')} "
            f"prósent af {fmt_num(nums[1])} "
            f"er {fmt_num(res, comma_null=True)}"
        )

    # Fraction
    elif op == "fraction":
        res = nums[0] * nums[1]
        s = f"{nums[0]} * {nums[1]}"
        voice = f"{result.frac_desc} af {fmt_num(nums[1])} er {fmt_num(res)}"

    # Add VAT to sum
    elif op == "with_vat":
        res = nums[0] * _VAT_MULT
        s = f"{nums[0]} * {_VAT_MULT}"
        voice = f"{fmt_num(nums[0])} með virðisaukaskatti er {fmt_num(res)}"

    # Subtract VAT from sum
    elif op == "without_vat":
        res = nums[0] / _VAT_MULT
        s = f"{nums[0]} / {_VAT_MULT}"
        voice = f"{fmt_num(nums[0])} án virðisaukaskatts er {fmt_num(res)}"

    # Addition, subtraction, multiplication, division
    elif op in _STD_OPERATORS:
        op_func, op_voice, op_symbol = _STD_OPERATORS[op]

        # Check for division by zero
        if op_func == operator.truediv and nums[1] == 0:
            return gen_answer("Það er ekki hægt að deila með núlli.")

        res = op_func(nums[0], nums[1])
        s = f"{nums[0]} {op_symbol} {nums[1]}"
        voice = (
            fmt_num(nums[0])
            + f" {op_voice} "
            + fmt_num(nums[1], case="þgf" if op_func == operator.truediv else "nf")
            + f" er {fmt_num(res, comma_null=True)}"
        )
    else:
        logging.warning(f"Unknown operator: {op}")
        return None

    # Set arithmetic expression as query key
    result.qkey = s

    if isinstance(res, float):
        # Convert result to Icelandic decimal format
        answer = iceformat_float(res)
    else:
        answer = str(res)

    return dict(answer=answer, result=res), answer, voice


def pi_answer(q: Query, result: Result) -> AnswerTuple:
    """Define pi (π)"""
    answer = "Talan π („pí“) er stærðfræðilegi fastinn 3,14159265359 eða þar um bil."
    voice = f"Talan pí er stærðfræðilegi fastinn {gssml(3.14159265359, type='float', gender='kk')} eða þar um bil."

    q.set_context(dict(result=3.14159265359))
    return dict(answer=answer, result=math.pi), answer, voice


def sentence(state: QueryStateDict, result: Result) -> None:
    """Called when sentence processing is complete"""
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
            logging.warning(f"Exception in arithmetic module: {e}")
            q.set_error(f"E_EXCEPTION: {e}")
    else:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
