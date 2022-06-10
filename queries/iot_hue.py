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

from typing import Dict, Mapping, Optional, cast
from typing_extensions import TypedDict

import logging
import random
import json

from query import Query, QueryStateDict, AnswerTuple
from queries import gen_answer, read_jsfile
from tree import Result, Node


class SmartLights(TypedDict):
    selected_light: str
    philips_hue: Dict[str, str]


class DeviceData(TypedDict):
    smartlights: SmartLights


_IoT_QTYPE = "IoT"

TOPIC_LEMMAS = ["ljós", "kveikja", "litur", "birta"]


def help_text(lemma: str) -> str:
    """Help text to return when query.py is unable to parse a query but
    one of the above lemmas is found in it"""
    return "Ég skil þig ef þú segir til dæmis: {0}.".format(
        random.choice(("Kveiktu á ljósunum inni í eldhúsi.",
        "Slökktu á leslampanum.",
        "Breyttu lit lýsingarinnar í stofunni í bláan.",
        "Gerðu ljósið í borðstofunni bjartara.",
        "Stilltu á bjartasta niðri í kjallara."))
    )


_COLORS = {
    "gulur": 60 * 65535 / 360,
    "rauður": 360 * 65535 / 360,
    "grænn": 120 * 65535 / 360,
    "blár": 240 * 65535 / 360,
    "ljósblár": 180 * 65535 / 360,
    "bleikur": 300 * 65535 / 360,
    "hvítur": [],
    "fjólublár": [],
    "brúnn": [],
    "appelsínugulur": [],
}


# This module wants to handle parse trees for queries
HANDLE_TREE = True

# The grammar nonterminals this module wants to handle
QUERY_NONTERMINALS = {"QIoT"}

# The context-free grammar for the queries recognized by this plug-in module
GRAMMAR = f"""

Query →
    QIoT

QIoT → QIoTQuery '?'?

QIoTQuery →
    QIoTTurnOn 
    | QIoTTurnOff 
    | QIoTSetColor 
    | QIoTIncreaseBrightness 
    | QIoTDecreaseBrightness 
    | QIoTMaxBrightness 
    | QIoTMinBrightness
    | QIoTSetScene

QIoTTurnOn ->
    "kveiktu" QIoTLightPhrase
    | "kveiktu" "á" QIoTLightPhrase

QIoTTurnOff ->
    "slökktu" QIoTLightPhrase
    | "slökktu" "á" QIoTLightPhrase

QIoTSetColor ->
    QIoTMakeVerb? QIoTMakeColorObject
    | QIoTSetVerb QIoTSetColorObject
    | QIoTChangeVerb QIoTChangeColorObject

QIoTMakeColorObject ->
    QIoTColorLightPhrase "að"? QIoTColorNamePhrase
    | QIoTColorLight "að"? QIoTColorNamePhrase QIoTGroupNamePhrase?
    | QIoTColorNamePhrase QIoTGroupNamePhrase?
    | QIoTColorNamePhrase QIoTLocationPreposition QIoTLightPhrase

QIoTSetColorObject ->
    QIoTColorLightPhrase "á" QIoTColorNamePhrase
    | QIoTColorLight "á" QIoTColorNamePhrase QIoTGroupNamePhrase?
    | "á"? QIoTColorNamePhrase QIoTGroupNamePhrase?
    | "á"? QIoTColorNamePhrase QIoTLocationPreposition QIoTLightPhrase  

QIoTChangeColorObject ->
    QIoTColorLightPhrase "í" QIoTColorNamePhrase
    | QIoTColorLight "í" QIoTColorNamePhrase QIoTGroupNamePhrase?
    | "í" QIoTColorNamePhrase QIoTGroupNamePhrase?
    | "í" QIoTColorNamePhrase QIoTLocationPreposition QIoTLightPhrase

# Need to add "gerðu minni birtu" functionality.
QIoTIncreaseBrightness ->
    QIoTIncrease QIoTBrightness QIoTLightPhrase?
    | QIoTMakeVerb? QIoTMakeBrighterObject
    # | QIoTSetVerb QIoTSetBrightObject

QIoTMakeBrighterObject -> 
    QIoTBrightnessLightPhrase QIoTBrighterPhrase
    | QIoTBrightnessLight QIoTMoreOrBrighter QIoTGroupNamePhrase?
    | QIoTMoreBrightness QIoTGroupNamePhrase?
    | QIoTMoreBrightness QIoTLocationPreposition QIoTLightPhrase

# QIoTSetBrightObject ->
#     QIoTColorLightPhrase "á" QIoTColorNamePhrase
#     | QIoTColorLight "á" QIoTColorNamePhrase QIoTGroupNamePhrase?
#     | "á"? QIoTColorNamePhrase QIoTGroupNamePhrase?
#     | "á"? QIoTColorNamePhrase QIoTLocationPreposition QIoTLightPhrase  

QIoTDecreaseBrightness ->
    QIoTDecrease QIoTBrightness QIoTLightPhrase?
    | QIoTMakeVerb? QIoTMakeDarkerObject

QIoTMakeDarkerObject -> 
    QIoTBrightnessLightPhrase QIoTDarkerPhrase
    | QIoTBrightnessLight QIoTLessOrDarker QIoTGroupNamePhrase?
    | QIoTLessOrDarker QIoTGroupNamePhrase?
    | QIoTLessOrDarker QIoTLocationPreposition QIoTLightPhrase

QIoTMaxBrightness ->
    # ?QIoTMakeVerb QIoTMakeBrightestObject
    QIoTSetVerb QIoTSetBrightestObject 

# QIoTMakeBrightestObject -> 
#     QIoTBrightnessLightPhrase QIoTMoreOrBrighter
#     | QIoTBrightnessLight QIoTMoreOrBrighter QIoTGroupNamePhrase?
#     | QIoTMoreBrightness QIoTGroupNamePhrase?
#     | QIoTMoreBrightness QIoTLocationPreposition QIoTLightPhrase

QIoTSetBrightestObject ->
    QIoTBrightnessLightPhrase "á" QIoTMostOrBrightest
    | QIoTBrightnessLight "á" QIoTMostOrHighest QIoTGroupNamePhrase?
    | "á"? QIoTBrightestPhrase QIoTGroupNamePhrase?
    | "á"? QIoTBrightestPhrase QIoTLocationPreposition QIoTLightPhrase  

QIoTMinBrightness ->
    # ?QIoTMakeVerb QIoTMakeBrightestObject
    QIoTSetVerb QIoTSetDarkestObject 

# QIoTMakeDarkestObject -> 
#     QIoTBrightnessLightPhrase QIoTMoreOrBrighter
#     | QIoTBrightnessLight QIoTMoreOrBrighter QIoTGroupNamePhrase?
#     | QIoTMoreBrightness QIoTGroupNamePhrase?
#     | QIoTMoreBrightness QIoTLocationPreposition QIoTLightPhrase

QIoTSetDarkestObject ->
    QIoTBrightnessLightPhrase "á" QIoTLeastOrDarkest
    | QIoTBrightnessLight "á" QIoTLeastOrLowest QIoTGroupNamePhrase?
    | "á"? QIoTDarkestPhrase QIoTGroupNamePhrase?
    | "á"? QIoTDarkestPhrase QIoTLocationPreposition QIoTLightPhrase  

QIoTSetScene ->
    QIoTMakeVerb QIoTMakeSceneObject
    | QIoTSetVerb QIoTSetSceneObject
    | QIoTChangeVerb QIoTChangeSceneObject

QIoTMakeSceneObject ->
    QIoTSceneLightPhrase "að"? QIoTSceneNamePhrase
    | QIoTScene "að"? QIoTSceneNamePhrase QIoTGroupNamePhrase?
    | QIoTSceneNamePhrase QIoTGroupNamePhrase
    | QIoTSceneNamePhrase QIoTLocationPreposition QIoTLightPhrase

QIoTSetSceneObject ->
    QIoTSceneLightPhrase "á" QIoTSceneNamePhrase
    | QIoTScene "á" QIoTSceneNamePhrase QIoTGroupNamePhrase?
    | "á"? QIoTSceneNamePhrase QIoTGroupNamePhrase?
    | "á"? QIoTSceneNamePhrase QIoTLocationPreposition QIoTLightPhrase  

QIoTChangeSceneObject ->
    QIoTSceneLightPhrase "í" QIoTSceneNamePhrase
    | QIoTScene "í" QIoTSceneNamePhrase QIoTGroupNamePhrase?
    | "í" QIoTSceneNamePhrase QIoTGroupNamePhrase?
    | "í" QIoTSceneNamePhrase QIoTLocationPreposition QIoTLightPhrase

QIoTLeastOrDarkest ->
    QIoTLeastOrLowest
    | QIoTDarkestPhrase

QIoTLeastOrLowest ->
    QIoTLeast
    | QIoTLowest

QIoTDarkestPhrase ->
    QIoTDarkest
    | QIoTLeastOrLowest QIoTBrightness
    | QIoTMostOrHighest QIoTDarkness

QIoTMostOrBrightest ->
    QIoTMostOrHighest
    | QIoTBrightestPhrase

QIoTMostOrHighest ->
    QIoTMost
    | QIoTHighest

QIoTBrightestPhrase ->
    QIoTBrightest
    | QIoTMostOrHighest QIoTBrightness
    | QIoTLeastOrLowest QIoTDarkness

QIoTMoreBrightness ->
    QIoTMoreOrHigher QIoTBrightness
    | QIoTBrighterPhrase

QIoTMoreOrHigher ->
    'mikill:lo'_mst
    | 'hár:lo'_mst

QIoTMoreOrBrighter ->
    QIoTMore
    | QIoTBrighterPhrase

QIoTBrighterPhrase ->
    QIoTBrighter
    | QIoTMore QIoTBright
    | QIoTLess QIoTDark

QIoTLessOrDarker ->
    QIoTDarker
    | QIoTLess
    | QIoTLess QIoTBright
    | QIoTMore QIoTDark

QIoTLessOrDarker ->
    QIoTLess
    | QIoTDarkerPhrase

QIoTDarkerPhrase ->
    QIoTDarker
    | QIoTMore QIoTDark
    | QIoTLess QIoTBright

QIoTBrightnessLightPhrase ->
    QIoTBrightnessLight QIoTGroupNamePhrase?
    | QIoTGroupName

QIoTBrightnessLight ->
    QIoTBrightness? QIoTLight
    | QIoTBrightness "á" QIoTLight
    | QIoTBrightness

QIoTColorLightPhrase ->
    QIoTColorLight QIoTGroupNamePhrase?
    | QIoTGroupName

# Separate cases for "lit ljóssins" and "litinn á ljósinu", to be precise. But it is not ideal as is
QIoTColorLight ->
    QIoTColor? QIoTLight
    | QIoTColor "á" QIoTLight
    | QIoTColor

QIoTSceneLightPhrase ->
    QIoTScene QIoTGroupNamePhrase

QIoTLightPhrase ->
    QIoTLight QIoTGroupNamePhrase?
    | QIoTGroupNamePhrase

# tried making this 'ljós:no' to avoid ambiguity, but all queries failed as a result
QIoTLight ->
    QIoTLightWord
    | QIoTLightName

QIoTColorName ->
    {" | ".join(f"'{color}:lo'" for color in _COLORS.keys())}

QIoTColorNamePhrase ->
    QIoTColor? QIoTColorName
    | QIoTColorName QIoTColor?
    | QIoTColorName QIoTLight?

QIoTSceneName ->
    no

QIoTSceneNamePhrase ->
    QIoTScene? QIoTSceneName
    | QIoTSceneName QIoTScene?
    | QIoTSceneName QIoTLight?

QIoTGroupNamePhrase ->
    QIoTLocationPreposition QIoTGroupName

# The Nl, noun phrase, is too greedy, e.g. parsing "ljósin í eldhúsinu" as the group name.
# But no, noun, is too strict, e.g. "herbergið hans Loga" could be a user-made group name. 
QIoTGroupName ->
    no

QIoTLightName ->
    no

QIoTLocationPreposition ->
    QIoTLocationPrepositionFirstPart? QIoTLocationPrepositionSecondPart

# The latter proverbs are grammatically incorrect, but common errors, both in speech and transcription.
# The list provided is taken from StefnuAtv in Greynir.grammar. That includes "aftur:ao", which is not applicable here.
QIoTLocationPrepositionFirstPart ->
    StaðarAtv
    | "fram:ao"
    | "inn:ao"
    | "niður:ao"
    | "upp:ao"
    | "út:ao"

QIoTLocationPrepositionSecondPart ->
    "á" | "í"

QIoTBright ->
    'bjartur:lo'_fst 
    | 'ljós:lo'_fst
    | "Bjart"
    | "bjart"

QIoTDarkest ->
    'dimmur:lo'_evb
    | 'dimmur:lo'_esb
    | 'dökkur:lo'_evb
    | 'dökkur:lo'_esb

QIoTLeast ->
    'lítill:lo'_evb
    | 'lítill:lo'_esb
    | 'lítið:ao'_est

QIoTLowest ->
    'lágur:lo'_evb
    | 'lágur:lo'_esb

QIoTBrightest ->
    'bjartur:lo'_evb
    | 'bjartur:lo'_esb
    | 'ljós:lo'_evb
    | 'ljós:lo'_esb

QIoTMost ->
    'mikill:lo'_evb
    | 'mikill:lo'_esb
    | 'mikið:ao'_est

QIoTHighest ->
    'hár:lo'_evb
    | 'hár:lo'_esb

QIoTBrighter ->
    'bjartur:lo'_mst
    | 'ljós:lo'_mst

QIoTDark ->
    'dimmur:lo'_fst 
    | 'dökkur:lo'_fst

QIoTDarker ->
    'dimmur:lo'_mst
    | 'dökkur:lo'_mst

QIoTLessOrLower ->
    'lítill:lo'_mst
    | 'lágur:lo'_mst

QIoTIncrease ->
    'hækka:so'_bh
    | 'auka:so'_bh

QIoTDecrease ->
    'lækka:so'_bh
    | 'minnka:so'_bh

QIoTMore ->
    "meiri"
    | "meira"

QIoTLess ->
    "minni"
    | "minna"

QIoTSetVerb ->
    'setja:so'_bh
    | 'stilla:so'_bh

QIoTMakeVerb ->
    'gera:so'_bh

QIoTChangeVerb ->
    'breyta:so'_bh

QIoTLightWord ->
    'ljós'
    | 'lýsing'

QIoTColor ->
    'litur'
    | 'litblær'
    | 'blær'

QIoTScene ->
    'sena'
    | 'stemning'
    | 'stemming'
    | 'stemmning'

QIoTDarkness ->
    'myrkur'

QIoTBrightness ->
    'birta'
    | 'birtustig'
"""


def QIoTQuery(node: Node, params: QueryStateDict, result: Result) -> None:
    result.qtype = _IoT_QTYPE


def QIoTTurnOn(node: Node, params: QueryStateDict, result: Result) -> None:
    result.action = "turn_on"
    if "hue_obj" not in result:
        result["hue_obj"] = {"on": True}
    else:
        result["hue_obj"]["on"] = True


def QIoTTurnOff(node: Node, params: QueryStateDict, result: Result) -> None:
    result.action = "turn_off"
    if "hue_obj" not in result:
        result["hue_obj"] = {"on": False}
    else:
        result["hue_obj"]["on"] = False


def QIoTSetColor(node: Node, params: QueryStateDict, result: Result) -> None:
    result.action = "set_color"
    print(result.color_name)
    color_hue = _COLORS.get(result.color_name, None)
    print(color_hue)
    if color_hue is not None:
        if "hue_obj" not in result:
            result["hue_obj"] = {"on": True, "hue": int(color_hue)}
        else:
            result["hue_obj"]["hue"] = int(color_hue)
            result["hue_obj"]["on"] = True


def QIoTIncreaseBrightness(node: Node, params: QueryStateDict, result: Result) -> None:
    result.action = "increase_brightness"
    if "hue_obj" not in result:
        result["hue_obj"] = {"on": True, "bri_inc": 64}
    else:
        result["hue_obj"]["bri_inc"] = 64
        result["hue_obj"]["on"] = True


def QIoTDecreaseBrightness(node: Node, params: QueryStateDict, result: Result) -> None:
    result.action = "decrease_brightness"
    if "hue_obj" not in result:
        result["hue_obj"] = {"bri_inc": -64}
    else:
        result["hue_obj"]["bri_inc"] = -64


def QIoTMaxBrightness(node: Node, params: QueryStateDict, result: Result) -> None:
    result.action = "decrease_brightness"
    if "hue_obj" not in result:
        result["hue_obj"] = {"bri": 255}
    else:
        result["hue_obj"]["bri"] = 255


def QIoTMinBrightness(node: Node, params: QueryStateDict, result: Result) -> None:
    result.action = "decrease_brightness"
    if "hue_obj" not in result:
        result["hue_obj"] = {"bri": 0}
    else:
        result["hue_obj"]["bri"] = 0


def QIoTSetScene(node: Node, params: QueryStateDict, result: Result) -> None:
    result.action = "set_scene"
    scene_name = result.get("scene_name", None)
    print(scene_name)
    if scene_name is not None:
        if "hue_obj" not in result:
            result["hue_obj"] = {"on": True, "scene": scene_name}
        else:
            result["hue_obj"]["scene"] = scene_name
            result["hue_obj"]["on"] = True


def QIoTColorName(node: Node, params: QueryStateDict, result: Result) -> None:
    result["color_name"] = (
        node.first_child(lambda x: True).string_self().strip("'").split(":")[0]
    )


def QIoTSceneName(node: Node, params: QueryStateDict, result: Result) -> None:
    result["scene_name"] = result._indefinite


def QIoTGroupName(node: Node, params: QueryStateDict, result: Result) -> None:
    result["group_name"] = result._indefinite


def QIoTLightName(node: Node, params: QueryStateDict, result: Result) -> None:
    result["light_name"] = result._indefinite


# Convert color name into hue
# Taken from home.py
_COLOR_NAME_TO_CIE: Mapping[str, float] = {
    "gulur": 60 * 65535 / 360,
    "grænn": 120 * 65535 / 360,
    "ljósblár": 180 * 65535 / 360,
    "blár": 240 * 65535 / 360,
    "bleikur": 300 * 65535 / 360,
    "rauður": 360 * 65535 / 360,
    # "Rauð": 360 * 65535 / 360,
}


def sentence(state: QueryStateDict, result: Result) -> None:
    """Called when sentence processing is complete"""
    q: Query = state["query"]
    if "qtype" not in result:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
        return

    # host = str(flask.request.host)
    # smartdevice_type = "smartlights"
    # client_id = str(q.client_id)

    # # Fetch relevant data from the device_data table to perform an action on the lights
    # device_data = cast(Optional[DeviceData], q.client_data(smartdevice_type))
    # print(device_data)

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
        
    #     js = read_jsfile("IoT_Embla/Philips_Hue/hub.js")
    #     js += f"syncConnectHub('{host}','{client_id}');"
    #     q.set_answer(*gen_answer("blabla"))
    #     q.set_command(js)
    #     return

    # Successfully matched a query type

    q.set_qtype(result.qtype)

    try:
        # kalla í javascripts stuff
        light_or_group_name = result.get("light_name", result.get("group_name", ""))        
        color_name = result.get("color_name", "")
        print("GROUP NAME:", light_or_group_name)
        print("COLOR NAME:", color_name)
        print(result.hue_obj)
        q.set_answer(
            *gen_answer(
                "ég var að kveikja ljósin! "
                # + group_name
                # + " "
                # + color_name
                # + " "
                # + result.action
                # + " "
                # + str(result.hue_obj.get("hue", "enginn litur"))
            )
        )
        js = (
            f"var BRIDGE_IP = '192.168.1.68';var USERNAME = 'q2jNarhGHO9izO0xZZXcoww5GYANGi6mZyJYgMdL';"
            + read_jsfile("IoT_Embla/Philips_Hue/lights.js")
            + read_jsfile("IoT_Embla/Philips_Hue/set_lights.js")
        )
        js += f"syncSetLights('{light_or_group_name}', '{json.dumps(result.hue_obj)}');"
        q.set_command(js)
    except Exception as e:
        logging.warning("Exception while processing random query: {0}".format(e))
        q.set_error("E_EXCEPTION: {0}".format(e))
        raise
