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


from typing import Dict, Mapping, Optional, cast
from typing_extensions import TypedDict

import logging
import random
import json
import flask

from query import Query, QueryStateDict, AnswerTuple
from queries import gen_answer, read_jsfile, read_grammar_file
from tree import Result, Node


class SmartLights(TypedDict):
    selected_light: str
    philips_hue: Dict[str, str]


class DeviceData(TypedDict):
    smartlights: SmartLights


_IoT_QTYPE = "IoTConnect"

TOPIC_LEMMAS = [
    "tengja",
]


def help_text(lemma: str) -> str:
    """Help text to return when query.py is unable to parse a query but
    one of the above lemmas is found in it"""
    return "Ég skil þig ef þú segir til dæmis: {0}.".format(
        random.choice(
            (
                "Tengu miðstöðina",
                "Tengdu ljósin"
            )
        )
    )



# This module wants to handle parse trees for queries
HANDLE_TREE = True

# The grammar nonterminals this module wants to handle
QUERY_NONTERMINALS = {"QIoTConnect"}

# The context-free grammar for the queries recognized by this plug-in module
# GRAMMAR = read_grammar_file("iot_hue")

GRAMMAR = f"""

/þgf = þgf
/ef = ef

Query →
    QIoTConnect '?'?

QIoTConnect → 
    QIoTConnectLights
    | QIoTConnectHub
    

QIoTConnectLights →
    "tengdu" "ljósin"

QIoTConnectHub →
    "tengdu" "miðstöðina"

"""

def QIoTConnectLights(node: Node, params: QueryStateDict, result: Result) -> None:
    result.qtype = "connect_lights"
    result.action = "connect_lights"

def QIoTConnectHub(node: Node, params: QueryStateDict, result: Result) -> None:
    print("Connect Hub")
    result.qtype = "connect_hub"
    result.action = "connect_hub"


def sentence(state: QueryStateDict, result: Result) -> None:
    """Called when sentence processing is complete"""
    q: Query = state["query"]
    changing_color = result.get("changing_color", False)
    changing_scene = result.get("changing_scene", False)
    changing_brightness = result.get("changing_brightness", False)
    print("error?", sum((changing_color, changing_scene, changing_brightness)) > 1)
    if (
        sum((changing_color, changing_scene, changing_brightness)) > 1
        or "qtype" not in result
    ):
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
        return

    q.set_qtype(result.qtype)
    if result.qtype == "connect_lights":
        host = str(flask.request.host)
        print("host: ", host)
        smartdevice_type = "smartlight"
        client_id = str(q.client_id)
        print("client_id:", client_id)
        js = read_jsfile("IoT_Embla/Philips_Hue/hub.js")
        js += f"syncConnectHub('{client_id}','{host}');"
        answer = "Philips Hue miðstöðin hefur verið tengd"
        voice_answer = answer
        response = dict(answer=answer)
        q.set_answer(response, answer, voice_answer)
        q.set_command(js)
        return
    elif result.qtype == "connect_hub":
        host = str(flask.request.host)
        print("host: ", host)
        smartdevice_type = "smarthub"
        client_id = str(q.client_id)
        print("client_id:", client_id)
        js = read_jsfile("IoT_Embla/Smart_Things/st_connecthub.js")
        js += f"syncConnectHub('{client_id}','{host}');"
        answer = "Smart Things miðstöðin hefur verið tengd"
        voice_answer = answer
        response = dict(answer=answer)
        q.set_answer(response, answer, voice_answer)
        q.set_command(js)
        return


    # smartdevice_type = "smartlights"
    # client_id = str(q.client_id)
    # print("client_id:", client_id)

    # # Fetch relevant data from the device_data table to perform an action on the lights
    # device_data = cast(Optional[DeviceData], q.client_data(smartdevice_type))
    # print("device data :", device_data)

    # selected_light: Optional[str] = None
    # hue_credentials: Optional[Dict[str, str]] = None

    # if device_data is not None and smartdevice_type in device_data:
    #     dev = device_data[smartdevice_type]
    #     assert dev is not None
    #     selected_light = dev.get("selected_light")
    #     hue_credentials = dev.get("philips_hue")
    #     bridge_ip = hue_credentials.get("ipAddress")
    #     username = hue_credentials.get("username")

    # if not device_data or not hue_credentials:
    #     answer = "ég var að kveikja ljósin! "
    #     q.set_answer(*gen_answer(answer))
    #     return

    # # Successfully matched a query type
    # print("bridge_ip: ", bridge_ip)
    # print("username: ", username)
    # print("selected light :", selected_light)
    # print("hue credentials :", hue_credentials)



    # f"var BRIDGE_IP = '192.168.1.68';var USERNAME = 'p3obluiXT13IbHMpp4X63ZvZnpNRdbqqMt723gy2';"
