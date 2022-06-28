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

    This query module handles dialogue related to theater tickets.
"""

from typing import Any, Callable, Optional
import logging
import random

from query import Query, QueryStateDict
from tree import Result, Node
from queries import gen_answer, parse_num, query_json_api
from queries.dialogue import DialogueStateManager, ListResource, Resource, ResourceState

_THEATER_DIALOGUE_NAME = "theater"
_THEATER_QTYPE = "theater"
_START_DIALOGUE_QTYPE = "theater_start"

TOPIC_LEMMAS = ["leikhús", "sýning"]


def help_text(lemma: str) -> str:
    """Help text to return when query.py is unable to parse a query but
    one of the above lemmas is found in it"""
    return "Ég skil þig ef þú segir til dæmis: {0}.".format(
        random.choice(("Hvaða sýningar eru í boði",))
    )


# This module wants to handle parse trees for queries
HANDLE_TREE = True

# The grammar nonterminals this module wants to handle
QUERY_NONTERMINALS = {"QTheater"}

# The context-free grammar for the queries recognized by this plug-in module
GRAMMAR = """

Query →
    QTheater

QTheater → QTheaterQuery '?'?

QTheaterQuery →
    QTheaterHotWord | QTheaterDialogue

QTheaterHotWord →
    "leikhús"
    | "þjóðleikhúsið"
    | "þjóðleikhús"
    | 'Þjóðleikhúsið'
    | 'Þjóðleikhús'
    | QTheaterEgVil? "kaupa" "leikhúsmiða"
    | QTheaterEgVil? "fara" "í" "leikhús"
    | QTheaterEgVil? "fara" "á" "leikhússýningu"

QTheaterDialogue → 
    QTheaterShowQuery
    | QTheaterShowDateQuery
    | QTheaterShowSeatsQuery
    | QTheaterShowLocationQuery
    | QTheaterShowOptions
    | QYes
    | QNo
    | QCancel
    # TODO: Hvað er í boði, ég vil sýningu X, dagsetningu X, X mörg sæti, staðsetningu X

QTheaterShowQuery → QTheaterEgVil? "velja" 'sýning' QTheaterShowName > QTheaterShowName

QTheaterShowName → Nl

QTheaterShowDateQuery →
    "ég"? "vil"? "fara"? "á" 'sýning'? QTheaterShowDate

QTheaterShowDate →
    QTheaterDateTime | QTheaterDate

QTheaterDateTime →
    tímapunkturafs

QTheaterDate →
    dagsafs
    | dagsföst

QTheaterShowSeatsQuery →
    "ég"? "vil"? "fá"? QNum "sæti"?

QTheaterShowLocationQuery →
    "ég"? "vil"? "sæti"? QNum til? QNum "í" "röð" QNum
    | "bekkur" QNum "sæti" QNum "til"? QNum

QTheaterShowOptions → "sýningar" 
    | "hvaða" "sýningar" "eru" "í" "boði"
    | "hvað" "er" "í" "boði"
    | "hverjir"? "eru"? "valmöguleikarnir"
    | "hvert" "er" "úrvalið"


QTheaterEgVil →
    "ég"? "vil"
    | "ég" "vill"
    | "mig" "langar" "að"

QNum →
    # to is a declinable number word ('tveir/tvo/tveim/tveggja')
    # töl is an undeclinable number word ('sautján')
    # tala is a number ('17')
    to | töl | tala

QYes → "já" "já"* | "endilega" | "já" "takk" | "játakk" | "já" "þakka" "þér" "fyrir" | "já" "takk" "kærlega" "fyrir"? | "jább" "takk"?

QNo → "nei" "takk"? | "nei" "nei"* | "neitakk" | "ómögulega"

QCancel → "ég" "hætti" "við"
    | "ég" "vil" "hætta" "við" "pöntunina"
    | "ég" "vill" "hætta" "við" "pöntunina"

"""


def _generate_show_answer(
    resource: ListResource, dsm: DialogueStateManager
) -> Optional[str]:
    result = dsm.get_result()
    if result.get("showOptions"):
        return resource.prompts["options"].format(
            options=", ".join(dsm.get_result().shows)
        )
    if resource.is_unfulfilled:
        return resource.prompts["initial"]
    if resource.is_fulfilled:
        return resource.prompts["confirm"].format(show=resource.data[0])
    return None


def _generate_date_answer(
    resource: ListResource, dsm: DialogueStateManager
) -> Optional[str]:
    result = dsm.get_result()
    if result.get("dateOptions"):
        return resource.prompts["options"]
    if resource.is_unfulfilled:
        return resource.prompts["initial"]
    if resource.is_fulfilled:
        return resource.prompts["confirm"].format(date=result.get("date"))


def _generate_seat_answer(
    resource: ListResource, dsm: DialogueStateManager
) -> Optional[str]:
    result = dsm.get_result()
    if resource.is_unfulfilled:
        return resource.prompts["initial"]
    if resource.is_fulfilled:
        return resource.prompts["confirm"].format(seats=result.get("seats"))


def _generate_location_answer(
    resource: ListResource, dsm: DialogueStateManager
) -> Optional[str]:
    result = dsm.get_result()
    if result.get("locationOptions"):
        return resource.prompts["options"]
    if resource.is_unfulfilled:
        return resource.prompts["initial"]
    if resource.is_fulfilled:
        return resource.prompts["confirm"].format(location=result.get("location"))


def _generate_final_answer(
    resource: ListResource, dsm: DialogueStateManager
) -> Optional[str]:
    if resource.is_cancelled:
        return resource.prompts["cancelled"]

    resource.state = ResourceState.CONFIRMED
    seat_resource = dsm.get_resource("ShowSeats")
    location_resource = dsm.get_resource("ShowLocation")
    date_resource = dsm.get_resource("ShowDate")
    show_resource = dsm.get_resource("Show")
    ans = resource.prompts["final"].format(
        seats=seat_resource.data,
        location=location_resource.data[0],
        show=show_resource.data[0],
        date=date_resource.data[0],
    )
    return ans


def QTheaterDialogue(node: Node, params: QueryStateDict, result: Result) -> None:
    result.qtype = _THEATER_QTYPE


def QTheaterHotWord(node: Node, params: QueryStateDict, result: Result) -> None:
    result.qtype = _START_DIALOGUE_QTYPE


def QTheaterShowQuery(node: Node, params: QueryStateDict, result: Result) -> None:
    def _add_show(
        resource: Resource, dsm: DialogueStateManager, result: Result
    ) -> None:
        resource.data = [dsm.get_result().show_name]
        resource.state = ResourceState.FULFILLED
        print("Show resource data: ", resource.data)

    if "callbacks" not in result:
        result["callbacks"] = []
    filter_func: Callable[[Resource], bool] = lambda r: r.name == "Show"
    result.callbacks.append((filter_func, _add_show))


def QTheaterShowDateQuery(node: Node, params: QueryStateDict, result: Result) -> None:
    pass


def QTheaterShowSeatsQuery(node: Node, params: QueryStateDict, result: Result) -> None:
    pass


def QTheaterShowLocationQuery(
    node: Node, params: QueryStateDict, result: Result
) -> None:
    pass


def QTheaterShowOptions(node: Node, params: QueryStateDict, result: Result) -> None:
    result.showOptions = True


def QTheaterShowName(node: Node, params: QueryStateDict, result: Result) -> None:
    result.show_name = (
        " ".join(result._text.split()[1:])
        if result._text.startswith("sýning")
        else result._text
    )


def QNum(node: Node, params: QueryStateDict, result: Result):
    fruitnumber = int(parse_num(node, result._nominative))
    if fruitnumber is not None:
        result.fruitnumber = fruitnumber
    else:
        result.fruitnumber = 1


def QCancel(node: Node, params: QueryStateDict, result: Result):
    def _cancel_order(
        resource: Resource, dsm: DialogueStateManager, result: Result
    ) -> None:
        resource.state = ResourceState.CANCELLED

    result.qtype = "QCancel"
    if "callbacks" not in result:
        result["callbacks"] = []
    filter_func: Callable[[Resource], bool] = lambda r: r.name == "Final"
    result.callbacks.append((filter_func, _cancel_order))


SHOW_URL = "https://leikhusid.is/wp-json/shows/v1/categories/938"


def _fetch_shows() -> Any:
    resp = query_json_api(SHOW_URL)
    if resp:
        assert isinstance(resp, list)
        return [s["title"] for s in resp]


_ANSWERING_FUNCTIONS = {
    "Show": _generate_show_answer,
    "ShowDate": _generate_date_answer,
    "ShowSeats": _generate_seat_answer,
    "SeatLocation": _generate_location_answer,
    "Final": _generate_final_answer,
}


def sentence(state: QueryStateDict, result: Result) -> None:
    """Called when sentence processing is complete"""
    q: Query = state["query"]
    dsm: DialogueStateManager = DialogueStateManager(
        _THEATER_DIALOGUE_NAME, _START_DIALOGUE_QTYPE, q, result
    )
    if dsm.not_in_dialogue():
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
        return

    try:
        print("A")
        result.shows = _fetch_shows()
        dsm.setup_dialogue(_ANSWERING_FUNCTIONS)
        if result.qtype == _START_DIALOGUE_QTYPE:
            print("B")
            dsm.start_dialogue()
        print("C")
        print(dsm._resources)
        ans = dsm.get_answer()
        print("D")
        if not ans:
            print("No answer generated")
            q.set_error("E_QUERY_NOT_UNDERSTOOD")
            return

        q.set_qtype(result.qtype)
        q.set_answer(*gen_answer(ans))
    except Exception as e:
        logging.warning("Exception while processing random query: {0}".format(e))
        q.set_error("E_EXCEPTION: {0}".format(e))
        raise
