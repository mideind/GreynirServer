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

    This query module handles queries related to the generation
    of random numbers, e.g. "Kastaðu tengingi", "Nefndu tölu milli 5 og 10", etc.

"""

# TODO: add "láttu", "hafðu", "litaðu", "kveiktu" functionality.
# TODO: make the objects of sentences more modular, so that the same structure doesn't need to be written for each action
# TODO: ditto the previous comment. make the initial non-terminals general and go into specifics at the terminal level instead.
# TODO: substituion klósett, baðherbergi hugmyndÆ senda lista i javascript og profa i röð
# TODO: Embla stores old javascript code cached which has caused errors
# TODO: Cut down javascript sent to Embla
# TODO: Two specified groups or lights.
# TODO: No specified location
# TODO: Fix scene issues

from os import access
from typing import Dict, Mapping, Optional, cast
from typing_extensions import TypedDict

import logging
import random
import json
import flask
from datetime import datetime, timedelta

from reynir.lemmatize import simple_lemmatize

from query import Query, QueryStateDict, AnswerTuple
from queries import gen_answer, read_jsfile, read_grammar_file
from queries.sonos import SonosClient
from tree import Result, Node, TerminalNode
from util import read_api_key


_IoT_QTYPE = "IoT"

TOPIC_LEMMAS = [
    "tónlist",
]

# def QIoTSpeakerIncreaseVerb(node: Node, params: QueryStateDict, result: Result) -> None:
#     result.action = "increase_volume"
#     if "hue_obj" not in result:
#         result["hue_obj"] = {"on": True, "bri_inc": 64}
#     else:
#         result["hue_obj"]["bri_inc"] = 64
#         result["hue_obj"]["on"] = True


def help_text(lemma: str) -> str:
    """Help text to return when query.py is unable to parse a query but
    one of the above lemmas is found in it"""
    return "Ég skil þig ef þú segir til dæmis: {0}.".format(
        random.choice(
            ("Hækkaðu í tónlistinni", "Kveiktu á tónlist", "Láttu vera tónlist")
        )
    )


# This module wants to handle parse trees for queries
HANDLE_TREE = True

# The grammar nonterminals this module wants to handle
QUERY_NONTERMINALS = {"QIoTSpeaker"}

# The context-free grammar for the queries recognized by this plug-in module
# GRAMMAR = read_grammar_file("iot_hue")

GRAMMAR = read_grammar_file("iot_speakers")


def QIoTSpeakerIncreaseVerb(node: Node, params: QueryStateDict, result: Result) -> None:
    result.action = "increase_volume"


def QIoTSpeakerDecreaseVerb(node: Node, params: QueryStateDict, result: Result) -> None:
    result.action = "decrease_volume"


def QIoTSpeakerGroupName(node: Node, params: QueryStateDict, result: Result) -> None:
    result["group_name"] = result._indefinite


def QIoTMusicWord(node: Node, params: QueryStateDict, result: Result) -> None:
    result.target = "music"
    print("music")


def sentence(state: QueryStateDict, result: Result) -> None:
    # try:
    print("sentence")
    print(
        "DESCENDANTS:",
        list(
            i[0].root(state, result.params)
            for i in result.enum_descendants(lambda x: isinstance(x, TerminalNode))
        ),
    )
    """Called when sentence processing is complete"""
    q: Query = state["query"]

    q.set_qtype(result.get("qtype"))

    # TODO: Find way to only catch playing commands
    if result.get("action") == None:
        result.action = "play_music"

    smartdevice_type = "smart_speaker"

    # Fetch relevant data from the device_data table to perform an action on the lights
    device_data = q.client_data("iot_speakers")
    print(device_data)

    # TODO: Need to add check for if there are no registered devices to an account, probably when initilazing the querydata
    if device_data is not None:
        sonos_client = SonosClient(device_data, q.client_id)
    else:
        print("No device data found for this account")
        return

    # Perform the action on the Sonos device
    if result.action == "play_music":
        sonos_client.toggle_play_pause()
        answer = "Ég kveikti á tónlist."
    # elif result.action == "increase_volume":
    #     sonos_client.increase_volume()
    # elif result.action == "decrease_volume":
    #     sonos_client.decrease_volume()
    # elif result.action == "set_volume":
    #     sonos_client.set_volume(result.get["volume"])

    answer_list = gen_answer(answer)
    answer_list[1].replace(
        "Sonos", "Sónos"
    )  # Accounting for Embla's Icelandic pronunciation
    q.set_answer(*answer_list)

    # f"var BRIDGE_IP = '192.168.1.68';var USERNAME = 'p3obluiXT13IbHMpp4X63ZvZnpNRdbqqMt723gy2';"
    # except Exception as e:
    #     print(e)
    #     print("Error in sentence")
