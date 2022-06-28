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

from typing import Any, Optional
import logging
import random

from query import Query, QueryStateDict
from tree import Result, Node
from queries import gen_answer, query_json_api
from queries.dialogue import DialogueStateManager, ListResource

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

QTheaterDialogue → "sýningar"
    # TODO: Hvað er í boði, ég vil sýningu X, dagsetningu X, X mörg sæti, staðsetningu X

QTheaterEgVil →
    "ég"? "vil"
    | "mig" "langar" "að"

"""


def _generate_show_answer(
    resource: ListResource, dsm: DialogueStateManager
) -> Optional[str]:
    # if resource.is_unfulfilled:
    #     return resource.prompts["initial"]
    return resource.prompts["options"].format(options=", ".join(dsm.get_result().shows))
    return None


def QTheaterDialogue(node: Node, params: QueryStateDict, result: Result) -> None:
    result.qtype = _THEATER_QTYPE


def QTheaterHotWord(node: Node, params: QueryStateDict, result: Result) -> None:
    result.qtype = _START_DIALOGUE_QTYPE


SHOW_URL = "https://leikhusid.is/wp-json/shows/v1/categories/938"


def _fetch_shows() -> Any:
    resp = query_json_api(SHOW_URL)
    if resp:
        assert isinstance(resp, list)
        return [s["title"] for s in resp]


_ANSWERING_FUNCTIONS = {
    "Show": _generate_show_answer,
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
