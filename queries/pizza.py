"""

    Greynir: Natural language processing for Icelandic

    Randomness query response module

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

    This query module handles dialogue related to ordering pizza.
"""
from typing import Dict, Optional, Set, cast
import logging
import random

from query import Query, QueryStateDict
from tree import Result, Node
from queries import AnswerTuple, gen_answer, natlang_seq, parse_num, read_grammar_file
from queries.num import number_to_text, numbers_to_ordinal, numbers_to_text
from queries.resources import (
    FinalResource,
    ListResource,
    NumberResource,
    OrResource,
    Resource,
    WrapperResource,
)
from queries.dialogue import (
    AnsweringFunctionMap,
    DialogueStateManager,
)

_DIALOGUE_NAME = "pizza"
_PIZZA_QTYPE = "pizza"
_START_DIALOGUE_QTYPE = "pizza_start"

TOPIC_LEMMAS = ["pizza", "pitsa"]


def help_text(lemma: str) -> str:
    """Help text to return when query.py is unable to parse a query but
    one of the above lemmas is found in it"""
    return "Ég skil þig ef þú segir til dæmis: {0}.".format(
        random.choice(("Ég vil panta pizzu",))
    )


# This module wants to handle dialogue parse trees for queries
HANDLE_DIALOGUE = True

# This module involves dialogue functionality
DIALOGUE_NAME = "pizza"
HOTWORD_NONTERMINALS = {"QPizzaHotWord"}

# The grammar nonterminals this module wants to handle
QUERY_NONTERMINALS = {"QPizza"}.union(HOTWORD_NONTERMINALS)

# The context-free grammar for the queries recognized by this plug-in module
GRAMMAR = read_grammar_file(
    "pizza",
)


def banned_nonterminals(query: str) -> Set[str]:
    """
    Returns a set of nonterminals that are not
    allowed due to the state of the dialogue
    """
    # TODO: Implement this
    return set()


def _generate_order_answer(
    resource: WrapperResource, dsm: DialogueStateManager, result: Result
) -> Optional[AnswerTuple]:
    return gen_answer(resource.prompts["initial"])


def _generate_pizza_answer(
    resource: WrapperResource, dsm: DialogueStateManager, result: Result
) -> Optional[AnswerTuple]:
    (_, _, index) = resource.name.partition("_")
    type_resource: OrResource = cast(
        OrResource, dsm.get_resource("Type_{}".format(index))
    )
    size_resource: Resource = dsm.get_resource("Size_{}".format(index))
    crust_resource: Resource = dsm.get_resource("Crust_{}".format(index))
    if resource.is_unfulfilled:
        return gen_answer(resource.prompts["initial"])
    if resource.is_partially_fulfilled:
        if type_resource.is_confirmed and size_resource.is_unfulfilled:
            return gen_answer(resource.prompts["size"])
        if (
            type_resource.is_confirmed
            and size_resource.is_confirmed
            and crust_resource.is_unfulfilled
        ):
            return gen_answer(resource.prompts["crust"])


def QPizzaDialogue(node: Node, params: QueryStateDict, result: Result) -> None:
    if "qtype" not in result:
        result.qtype = _PIZZA_QTYPE


def QPizzaHotWord(node: Node, params: QueryStateDict, result: Result) -> None:
    result.qtype = _START_DIALOGUE_QTYPE
    print("ACTIVATING PIZZA MODULE")
    Query.get_dsm(result).hotword_activated()


def QPizzaNumberAnswer(node: Node, params: QueryStateDict, result: Result) -> None:
    dsm: DialogueStateManager = Query.get_dsm(result)
    # resource = dsm.get_resource("PizzaCount")
    number: int = result.get("number", 1)
    for _ in range(number):
        print("CCCCCCAAAAALLLLLLLLLLLLLL")
        dsm.add_dynamic_resource("Pizza", "PizzaOrder")
    print("Pizza Count: ", number)


def QPizzaToppingsList(node: Node, params: QueryStateDict, result: Result) -> None:
    print("Toppings in QPizzaToppingsList: ", result.get("toppings", {}))
    dsm: DialogueStateManager = Query.get_dsm(result)
    toppings: Dict[str, int] = result.get("toppings", {})
    resource = dsm.current_resource
    (_, _, index) = resource.name.partition("_")
    toppings_resource = dsm.get_resource("Toppings_{}".format(index))
    for topping in toppings:
        ...  # toppings_resource.data[topping] = toppings[topping]


def QPizzaToppingsWord(node: Node, params: QueryStateDict, result: Result) -> None:
    topping: str = result.dict.pop("real_name", result._nominative)
    if "toppings" not in result:
        result["toppings"] = {}
    result["toppings"][topping] = 1  # TODO: Add support for extra toppings


def QPizzaNum(node: Node, params: QueryStateDict, result: Result) -> None:
    number: int = int(parse_num(node, result._nominative))
    if "numbers" not in result:
        result["numbers"] = []
    result.numbers.append(number)
    result.number = number


def QPizzaPepperoniWord(node: Node, params: QueryStateDict, result: Result) -> None:
    result.real_name = "pepperóní"


def QPizzaOliveWord(node: Node, params: QueryStateDict, result: Result) -> None:
    result.real_name = "ólífur"


def QPizzaMushroomWord(node: Node, params: QueryStateDict, result: Result) -> None:
    result.real_name = "sveppir"


_ANSWERING_FUNCTIONS: AnsweringFunctionMap = {
    "PizzaOrder": _generate_order_answer,
    "Pizza": _generate_pizza_answer,
}


def sentence(state: QueryStateDict, result: Result) -> None:
    """Called when sentence processing is complete"""
    q: Query = state["query"]
    dsm: DialogueStateManager = q.dsm
    if dsm.not_in_dialogue():
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
        return

    try:
        print("A")
        ans: Optional[AnswerTuple] = dsm.get_answer(_ANSWERING_FUNCTIONS, result)
        if "pizza_options" not in result:
            q.query_is_command()
        print("D", ans)
        print("Current resource: ", dsm.current_resource)
        if not ans:
            print("No answer generated")
            q.set_error("E_QUERY_NOT_UNDERSTOOD")
            return

        q.set_qtype(result.qtype)
        q.set_answer(*ans)
    except Exception as e:
        logging.warning("Exception while processing random query: {0}".format(e))
        q.set_error("E_EXCEPTION: {0}".format(e))
        raise
