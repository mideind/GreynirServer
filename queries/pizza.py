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
    DictResource,
    NumberResource,
    OrResource,
    Resource,
    ResourceState,
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
GRAMMAR = read_grammar_file("pizza")


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
    print("Generating pizza answer")
    print("Generate pizza resource name: ", resource.name)
    index = resource.name.split("_")[-1]
    type_resource: OrResource = cast(
        OrResource, dsm.get_resource("Type_{}".format(index))
    )
    print("Type state: {}".format(type_resource.state))
    size_resource: Resource = dsm.get_resource("Size_{}".format(index))
    print("Size state: {}".format(size_resource.state))
    crust_resource: Resource = dsm.get_resource("Crust_{}".format(index))
    print("Crust state: {}".format(crust_resource.state))
    if resource.is_unfulfilled:
        print("Unfulfilled pizza")
        return gen_answer(resource.prompts["initial"])
    if resource.is_partially_fulfilled:
        print("Partially fulfilled pizza")
        if type_resource.is_confirmed and size_resource.is_unfulfilled:
            print("Confirmed type, unfulfilled size")
            return gen_answer(resource.prompts["size"])
        if (
            type_resource.is_confirmed
            and size_resource.is_confirmed
            and crust_resource.is_unfulfilled
        ):
            return gen_answer(resource.prompts["crust"])


def _generate_type_answer(
    resource: WrapperResource, dsm: DialogueStateManager, result: Result
) -> Optional[AnswerTuple]:
    print("Generating type answer")
    print("Generate type resource name: ", resource.name)
    index = resource.name.split("_")[-1]
    pizza_resource: Resource = dsm.get_resource("Pizza_{}".format(index))
    print("Pizza state: {}".format(pizza_resource.state))
    if resource.is_unfulfilled:
        print("Unfulfilled type")
        return gen_answer(resource.prompts["initial"])


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
    type_resource: OrResource = cast(OrResource, dsm.current_resource)
    print("Current resource in topping list: ", type_resource.name)
    index = type_resource.name.split("_")[-1]
    toppings_resource = dsm.get_resource("Toppings_{}".format(index))
    pizza_resource = dsm.get_resource("Pizza_{}".format(index))
    print("Toppings resource: ", toppings_resource.name)
    for (topping, amount) in toppings.items():
        toppings_resource.data[topping] = amount
    print("Toppings in QPizzaToppingsList: ", toppings_resource.data)
    dsm.skip_other_resources(type_resource, toppings_resource)
    dsm.set_resource_state(toppings_resource.name, ResourceState.CONFIRMED)
    dsm.set_resource_state(type_resource.name, ResourceState.CONFIRMED)
    print("Updating wrapper state with state: ", pizza_resource.state)
    dsm.update_wrapper_state(cast(WrapperResource, pizza_resource))
    if pizza_resource.state == ResourceState.FULFILLED:
        dsm.set_resource_state(pizza_resource.name, ResourceState.CONFIRMED)


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


def QPizzaSizeLarge(node: Node, params: QueryStateDict, result: Result) -> None:
    dsm: DialogueStateManager = Query.get_dsm(result)
    # TODO: Maybe some wrappers should not be set as the current resource? (e.g. here, we have to go through extra steps to get the size resource)
    # TODO: Better to use Pizza_1 here, as the current resource might be Type_1 instead of Pizza_1 and cause an error
    size_resource: Resource = dsm.get_resource(
        [i for i in dsm.current_resource.requires if i.startswith("Size")][0]
    )
    size_resource.data = "stóra pítsu"
    dsm.set_resource_state(size_resource.name, ResourceState.CONFIRMED)
    dsm.update_wrapper_state(cast(WrapperResource, dsm.current_resource))
    if dsm.current_resource.state == ResourceState.FULFILLED:
        dsm.set_resource_state(dsm.current_resource.name, ResourceState.CONFIRMED)


def QPizzaSizeMedium(node: Node, params: QueryStateDict, result: Result) -> None:
    dsm: DialogueStateManager = Query.get_dsm(result)
    size_resource: Resource = dsm.get_resource(
        [i for i in dsm.current_resource.requires if i.startswith("Size")][0]
    )
    size_resource.data = "miðstærð af pítsu"
    dsm.set_resource_state(size_resource.name, ResourceState.CONFIRMED)
    dsm.update_wrapper_state(cast(WrapperResource, dsm.current_resource))
    if dsm.current_resource.state == ResourceState.FULFILLED:
        dsm.set_resource_state(dsm.current_resource.name, ResourceState.CONFIRMED)


def QPizzaMediumWord(node: Node, params: QueryStateDict, result: Result) -> None:
    dsm: DialogueStateManager = Query.get_dsm(result)
    size_resource: Resource = dsm.get_resource(
        [i for i in dsm.current_resource.requires if i.startswith("Size")][0]
    )
    size_resource.data = "miðstærð af pítsu"
    dsm.set_resource_state(size_resource.name, ResourceState.CONFIRMED)
    dsm.update_wrapper_state(cast(WrapperResource, dsm.current_resource))
    if dsm.current_resource.state == ResourceState.FULFILLED:
        dsm.set_resource_state(dsm.current_resource.name, ResourceState.CONFIRMED)


def QPizzaSizeSmall(node: Node, params: QueryStateDict, result: Result) -> None:
    dsm: DialogueStateManager = Query.get_dsm(result)
    size_resource: Resource = dsm.get_resource(
        [i for i in dsm.current_resource.requires if i.startswith("Size")][0]
    )
    size_resource.data = "litla pítsu"
    dsm.set_resource_state(size_resource.name, ResourceState.CONFIRMED)
    dsm.update_wrapper_state(cast(WrapperResource, dsm.current_resource))
    if dsm.current_resource.state == ResourceState.FULFILLED:
        dsm.set_resource_state(dsm.current_resource.name, ResourceState.CONFIRMED)


def QPizzaCrustType(node: Node, params: QueryStateDict, result: Result) -> None:
    dsm: DialogueStateManager = Query.get_dsm(result)
    crust_resource: Resource = dsm.get_resource(
        [i for i in dsm.current_resource.requires if i.startswith("Crust")][0]
    )
    crust_resource.data = result._text
    print("Crust resource data: ", crust_resource.data)
    dsm.set_resource_state(crust_resource.name, ResourceState.CONFIRMED)
    dsm.update_wrapper_state(cast(WrapperResource, dsm.current_resource))
    if dsm.current_resource.state == ResourceState.FULFILLED:
        dsm.set_resource_state(dsm.current_resource.name, ResourceState.CONFIRMED)


def QPizzaPepperoniWord(node: Node, params: QueryStateDict, result: Result) -> None:
    result.real_name = "pepperóní"


def QPizzaOliveWord(node: Node, params: QueryStateDict, result: Result) -> None:
    result.real_name = "ólífur"


def QPizzaMushroomWord(node: Node, params: QueryStateDict, result: Result) -> None:
    result.real_name = "sveppir"


_ANSWERING_FUNCTIONS: AnsweringFunctionMap = {
    "PizzaOrder": _generate_order_answer,
    "Pizza": _generate_pizza_answer,
    "Type": _generate_type_answer,
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
