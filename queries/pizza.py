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
from typing import Any, Dict, List, Optional, cast
import logging
import random

from query import Query, QueryStateDict
from tree import ParamList, Result, Node
from queries import (
    AnswerTuple,
    gen_answer,
    parse_num,
    read_grammar_file,
    sing_or_plur,
)
from queries.num import number_to_text, numbers_to_text
from queries.extras.resources import (
    FinalResource,
    DictResource,
    OrResource,
    ResourceState,
    StringResource,
    WrapperResource,
)
from queries.extras.dialogue import (
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


def banned_nonterminals(q: Query) -> None:
    """
    Returns a set of nonterminals that are not
    allowed due to the state of the dialogue
    """
    # TODO: Implement this
    if q.active_dialogue != DIALOGUE_NAME:
        q.ban_nonterminal("QPizzaQuery")


def _generate_order_answer(
    resource: WrapperResource, dsm: DialogueStateManager, result: Result
) -> Optional[AnswerTuple]:
    ans: str = ""

    if dsm.extras.get("added_pizzas", False):
        total: int = dsm.extras["confirmed_pizzas"]
        number: int = dsm.extras["added_pizzas"]
        # r1 = dsm.get_resource("Pizza_1")
        # r2 = dsm.get_resource("Pizza_2")
        # print("Is r1 the same as r2: ", id(r1.state) is id(r2.state))
        print("Added pizzas", number)
        ans = resource.prompts["added_pizzas"].format(
            pizzas=numbers_to_text(
                sing_or_plur(number, "pítsu", "pítsum"), gender="kvk", case="þgf"
            ).capitalize(),
            total_pizzas=numbers_to_text(
                sing_or_plur(total, "fullkláraða pítsu", "fullkláraðar pítsur"),
                gender="kvk",
                case="þf",
            ),
        )
        dsm.extras["added_pizzas"] = 0
        return (dict(answer=ans), ans, ans)
    if dsm.extras.get("confirmed_pizzas", False):
        total: int = dsm.extras["confirmed_pizzas"]
        print("Total pizzas: ", total)
        ans = resource.prompts["confirmed_pizzas"]
        return (dict(answer=ans), ans, ans)
    return gen_answer(resource.prompts["initial"])


def _generate_pizza_answer(
    resource: WrapperResource, dsm: DialogueStateManager, result: Result
) -> Optional[AnswerTuple]:
    order_resource = dsm.get_resource("PizzaOrder")
    for child in dsm._resource_graph[order_resource]["children"]:
        print("!!!$$$$Pizza: ", child.name, child.state)
    print("Generating pizza answer")
    print("Generate pizza resource name: ", resource.name)
    type_resource: OrResource = cast(OrResource, dsm.get_children(resource)[0])
    print("Type state: {}".format(type_resource.data))
    size_resource: StringResource = cast(StringResource, dsm.get_children(resource)[1])
    print("Size state: {}".format(size_resource.data))
    crust_resource: StringResource = cast(StringResource, dsm.get_children(resource)[2])
    print("Crust state: {}".format(crust_resource.data))
    index: str = resource.name.split("_")[-1]
    number: int = int(index)
    # Pizza text formatting
    pizza_text: str = f"\n"
    if any(
        confirmed
        for confirmed in [
            type_resource.is_confirmed,
            size_resource.is_confirmed,
            crust_resource.is_confirmed,
        ]
    ):
        pizza_text += f"Pítsa {number}:\n"
    if size_resource.is_confirmed:
        pizza_text += f"   - {size_resource.data.capitalize()}\n"
    if crust_resource.is_confirmed:
        pizza_text += f"   - {crust_resource.data.capitalize()} botn\n"
    if type_resource.is_confirmed:
        toppings_resource: DictResource = cast(
            DictResource, dsm.get_children(type_resource)[0]
        )
        if toppings_resource.is_confirmed:
            pizza_text += f"   - Álegg: \n"
            for topping in toppings_resource.data:
                pizza_text += f"      - {topping.capitalize()}\n"
        else:
            menu_resource: StringResource = cast(
                StringResource, dsm.get_children(type_resource)[1]
            )
            pizza_text += f"   - Tegund: {menu_resource.data.capitalize()}\n"
    if resource.is_unfulfilled:
        print("Unfulfilled pizza")
        if number == 1:
            ans = resource.prompts["initial_single"]
            text_ans = ans + pizza_text
            return (dict(answer=text_ans), text_ans, ans)
        ans = resource.prompts["initial"].format(number=number_to_text(number))
        text_ans = ans + pizza_text
        return (dict(answer=text_ans), text_ans, ans)
    if resource.is_partially_fulfilled:
        print("Partially fulfilled pizza")
        if type_resource.is_unfulfilled:
            if number == 1:
                ans = resource.prompts["type_single"]
                text_ans = ans + pizza_text
                return (dict(answer=text_ans), text_ans, ans)
            ans = resource.prompts["type"].format(number=number_to_text(number))
            text_ans = ans + pizza_text
            return (dict(answer=text_ans), text_ans, ans)
        if type_resource.is_confirmed and size_resource.is_unfulfilled:
            print("Confirmed type, unfulfilled size")
            if number == 1:
                ans = resource.prompts["size_single"]
                text_ans = ans + pizza_text
                return (dict(answer=text_ans), text_ans, ans)
            ans = resource.prompts["size"].format(number=number_to_text(number))
            text_ans = ans + pizza_text
            return (dict(answer=text_ans), text_ans, ans)
        if (
            type_resource.is_confirmed
            and size_resource.is_confirmed
            and crust_resource.is_unfulfilled
        ):
            if number == 1:
                ans = resource.prompts["crust_single"]
                text_ans = ans + pizza_text
                return (dict(answer=text_ans), text_ans, ans)
            ans = resource.prompts["crust"].format(number=number_to_text(number))
            text_ans = ans + pizza_text
            return (dict(answer=text_ans), text_ans, ans)


def _generate_final_answer(
    resource: FinalResource, dsm: DialogueStateManager, result: Result
) -> Optional[AnswerTuple]:
    if resource.is_cancelled:
        return gen_answer(resource.prompts["cancelled"])

    return gen_answer(resource.prompts["final"])


def QPizzaDialogue(node: Node, params: ParamList, result: Result) -> None:
    if "qtype" not in result:
        result.qtype = _PIZZA_QTYPE


def QPizzaHotWord(node: Node, params: ParamList, result: Result) -> None:
    result.qtype = _START_DIALOGUE_QTYPE
    print("ACTIVATING PIZZA MODULE")
    Query.get_dsm(result).hotword_activated()


def QPizzaNumberAndSpecificationWrapper(
    node: Node, params: ParamList, result: Result
) -> None:
    """
    Dynamically adds a number of pizzas if there is no
    current pizza, otherwise adds ingredients to the current pizza.
    The specification of the pizzas is gotten from the result.
    """
    print("In number and specification wrapper")
    dsm: DialogueStateManager = Query.get_dsm(result)
    resource: WrapperResource = cast(WrapperResource, dsm.current_resource)
    pizzas: List[Dict[str, Any]] = result.get("pizzas", [])
    print("Current resource: ", resource.name)
    print("Resource.name == PizzaOrder", resource.name == "PizzaOrder")
    print(
        "(dsm.extras.pop(adding_pizzas, False): ",
        (dsm.extras.get("adding_pizzas", False)),
    )
    print("Pizzas: ", pizzas)
    for pizza in pizzas:
        print("Pizza: ", pizza)
        if resource.name == "PizzaOrder":
            # Create a new pizza
            print("Adding new pizza")
            dsm.add_dynamic_resource("Pizza", "PizzaOrder")
            # dsm.extras["adding_pizzas"] = True
            print("Done adding new pizza", dsm.get_children(resource)[-1])
            dsm.extras["total_pizzas"] = dsm.extras.get("total_pizzas", 0) + 1
            print("Done adding to total pizzas")
            pizza_resource: WrapperResource = cast(
                WrapperResource, dsm.get_children(resource)[-1]
            )
        else:
            resource = cast(WrapperResource, dsm.get_resource("PizzaOrder"))
            pizza_resource = cast(WrapperResource, dsm.current_resource)
        # Add to the pizza
        print(">>> Pizza resource: , ", pizza_resource.name)
        type_resource: OrResource = cast(
            OrResource, dsm.get_children(pizza_resource)[0]
        )
        toppings: Optional[Dict[str, int]] = pizza.get("toppings", None)
        if toppings:
            toppings_resource = cast(DictResource, dsm.get_children(type_resource)[0])
            for (topping, amount) in toppings.items():
                print("Topping in for loop: ", topping)
                toppings_resource.data[topping] = amount
            dsm.skip_other_resources(type_resource, toppings_resource)
            dsm.set_resource_state(toppings_resource.name, ResourceState.CONFIRMED)
            dsm.set_resource_state(type_resource.name, ResourceState.CONFIRMED)

        menu: Optional[str] = pizza.get("menu", None)
        if menu:
            menu_resource: StringResource = cast(
                StringResource, dsm.get_children(type_resource)[1]
            )
            menu_resource.data = menu
            dsm.skip_other_resources(type_resource, menu_resource)
            dsm.set_resource_state(menu_resource.name, ResourceState.CONFIRMED)
            dsm.set_resource_state(type_resource.name, ResourceState.CONFIRMED)
        size: Optional[str] = pizza.get("size", None)
        print("Size: ", size)
        if size:
            size_resource: StringResource = cast(
                StringResource, dsm.get_children(pizza_resource)[1]
            )
            print("Size resource name: ", size_resource.name)
            size_resource.data = size
            dsm.set_resource_state(size_resource.name, ResourceState.CONFIRMED)
            print("Size state: ", size_resource.state)

        crust: Optional[str] = pizza.get("crust", None)
        print("Crust: ", crust)
        if crust:
            crust_resource: StringResource = cast(
                StringResource, dsm.get_children(pizza_resource)[2]
            )
            crust_resource.data = crust
            dsm.set_resource_state(crust_resource.name, ResourceState.CONFIRMED)
        dsm.update_wrapper_state(pizza_resource)
        if pizza_resource.state == ResourceState.CONFIRMED:
            # dsm.set_resource_state(pizza_resource.name, ResourceState.CONFIRMED)
            dsm.extras["confirmed_pizzas"] = dsm.extras.get("confirmed_pizzas", 0) + 1
            dsm.extras["added_pizzas"] = dsm.extras.get("added_pizzas", 0) + 1
        result["new_pizza"] = pizza_resource

        number: int = pizza.get("count", 1) - 1
        print("Getting new pizza")
        for _ in range(number):
            dsm.duplicate_dynamic_resource(pizza_resource)
            print("Duplicating resource: ", pizza_resource.name)
            dsm.extras["total_pizzas"] = dsm.extras.get("total_pizzas", 0) + 1
            if pizza_resource.is_confirmed:
                dsm.extras["confirmed_pizzas"] = (
                    dsm.extras.get("confirmed_pizzas", 0) + 1
                )
                dsm.extras["added_pizzas"] = dsm.extras.get("added_pizzas", 0) + 1


def QPizzaNumberAndSpecification(node: Node, params: ParamList, result: Result) -> None:
    """
    Adds pizza information to the result.
    """
    print("QPizzaNumberAndSpecification")
    toppings: Optional[Dict[str, int]] = result.dict.pop("toppings", None)
    print("Toppings: ", toppings)
    menu: Optional[str] = result.dict.pop("menu", None)
    print("Menu: ", menu)
    size: Optional[str] = result.dict.pop("pizza_size", None)
    print("Size: ", size)
    crust: Optional[str] = result.dict.pop("crust", None)
    print("Crust: ", crust)
    number: int = result.get("number", 1)
    pizza: Dict[str, Any] = {
        "count": number,
        "toppings": toppings,
        "menu": menu,
        "size": size,
        "crust": crust,
    }
    print("Pizza in QPizzaNumberAndSpecification: ", pizza)
    result.pizzas = [pizza]


def QPizzaSpecification(node: Node, params: ParamList, result: Result) -> None:
    print("In QPizzaSpecification")


def QPizzaToppingsWord(node: Node, params: ParamList, result: Result) -> None:
    topping: str = result.dict.pop("real_name", result._nominative)
    if "toppings in QPizzaToppingsWord" not in result:
        result["toppings"] = {}
    result["toppings"][topping] = 1  # TODO: Add support for extra toppings


def QPizzaMenuWords(node: Node, params: ParamList, result: Result) -> None:
    result.menu = result._root
    # TODO: If multiple menu items added at the same time it will be in plural form


def QPizzaNum(node: Node, params: ParamList, result: Result) -> None:
    number: int = int(parse_num(node, result._nominative))
    if "numbers" not in result:
        result["numbers"] = []
    result.numbers.append(number)
    result.number = number


def QPizzaSizeLarge(node: Node, params: ParamList, result: Result) -> None:
    result.pizza_size = "stór"


def QPizzaSizeMedium(node: Node, params: ParamList, result: Result) -> None:
    result.pizza_size = "miðstærð"


def QPizzaMediumWord(node: Node, params: ParamList, result: Result) -> None:
    result.pizza_size = "miðstærð"


def QPizzaSizeSmall(node: Node, params: ParamList, result: Result) -> None:
    result.pizza_size = "lítil"


def QPizzaCrustType(node: Node, params: ParamList, result: Result) -> None:
    result.crust = result._root


def QPizzaPepperoni(node: Node, params: ParamList, result: Result) -> None:
    result.real_name = "pepperóní"


def QPizzaOlive(node: Node, params: ParamList, result: Result) -> None:
    result.real_name = "ólífur"


def QPizzaMushroom(node: Node, params: ParamList, result: Result) -> None:
    result.real_name = "sveppir"


def QPizzaNo(node: Node, params: ParamList, result: Result) -> None:
    dsm: DialogueStateManager = Query.get_dsm(result)
    resource: WrapperResource = cast(WrapperResource, dsm.current_resource)
    print("No resource: ", resource.name)
    if resource.name == "PizzaOrder":
        dsm.set_resource_state(resource.name, ResourceState.CONFIRMED)
        dsm.set_resource_state("Final", ResourceState.CONFIRMED)


def QPizzaStatus(node: Node, params: ParamList, result: Result) -> None:
    result.qtype = "QPizzaStatus"
    dsm: DialogueStateManager = Query.get_dsm(result)
    at = dsm.get_answer(_ANSWERING_FUNCTIONS, result)
    pizza_string: str = ""
    if "confirmed_pizzas" in dsm.extras:
        number = dsm.extras["confirmed_pizzas"]
        if dsm.extras["confirmed_pizzas"] > 0:
            pizza_string = "Pöntunin þín inniheldur {}".format(
                numbers_to_text(
                    sing_or_plur(number, "fullkláraða pítsu", "fullkláraðar pítsur"),
                    gender="kvk",
                    case="þf",
                )
            )
    print("Pizza status before total")
    if "total_pizzas" in dsm.extras:
        total = dsm.extras["total_pizzas"]
        confirmed = dsm.extras.get("confirmed_pizzas", 0)
        if confirmed == 0:
            pizza_string = "Pöntunin þín inniheldur"
        elif total - confirmed > 0:
            pizza_string += " og"
        if total - confirmed > 0:
            pizza_string += " {}".format(
                numbers_to_text(
                    sing_or_plur(
                        total - confirmed, "ókláraða pítsu", "ókláraðar pítsur"
                    ),
                    gender="kvk",
                    case="þf",
                )
            )
        if total > 0:
            pizza_string += ". "
    if len(pizza_string) == 0:
        pizza_string = "Hingað til eru engar vörur í pöntuninni. "
    if at:
        (_, ans, voice) = at
        ans = pizza_string + ans
        voice = pizza_string + voice
        dsm.set_answer((dict(answer=ans), ans, voice))


_ANSWERING_FUNCTIONS: AnsweringFunctionMap = {
    "PizzaOrder": _generate_order_answer,
    "Pizza": _generate_pizza_answer,
    "Final": _generate_final_answer,
}


def sentence(state: QueryStateDict, result: Result) -> None:
    """Called when sentence processing is complete"""
    q: Query = state["query"]
    dsm: DialogueStateManager = q.dsm
    if dsm.not_in_dialogue():
        print("Not in dialogue")
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
        print("E", result.qtype)
        q.set_qtype(result.qtype)
        print("F", ans)
        q.set_answer(*ans)
        print("G")
        q.set_beautified_query(
            q.beautified_query.replace("Panta", "panta").replace(
                "Hver er staðan.", "Hver er staðan?"
            )
        )
    except Exception as e:
        print("Exception: ", e)
        logging.warning("Exception while processing random query: {0}".format(e))
        q.set_error("E_EXCEPTION: {0}".format(e))
        raise
    return
