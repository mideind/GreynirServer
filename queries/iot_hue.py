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


_IoT_QTYPE = "IoT"

TOPIC_LEMMAS = [
    "ljós",
    "kveikja",
    "litur",
    "birta",
    "hækka",
    "stemmning",
    "sena",
    "stemming",
    "stemning",
]


def help_text(lemma: str) -> str:
    """Help text to return when query.py is unable to parse a query but
    one of the above lemmas is found in it"""
    return "Ég skil þig ef þú segir til dæmis: {0}.".format(
        random.choice(
            (
                "Kveiktu á ljósunum inni í eldhúsi.",
                "Slökktu á leslampanum.",
                "Breyttu lit lýsingarinnar í stofunni í bláan.",
                "Gerðu ljósið í borðstofunni bjartara.",
                "Stilltu á bjartasta niðri í kjallara.",
            )
        )
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
# GRAMMAR = read_grammar_file("iot_hue")

GRAMMAR = f"""

/þgf = þgf
/ef = ef

Query →
    QIoT

QIoT → 
    QIoTQuery '?'? 
    | QIoTConnectLights '?'?

QIoTConnectLights →
    "tengdu" "ljósin"

QIoTQuery ->
    QIoTMakeVerb QIoTMakeRest
    | QIoTSetVerb QIoTSetRest
    | QIoTChangeVerb QIoTChangeRest
    | QIoTLetVerb QIoTLetRest
    | QIoTTurnOnVerb QIoTTurnOnRest
    | QIoTTurnOffVerb QIoTTurnOffRest
    | QIoTIncreaseOrDecreaseVerb QIoTIncreaseOrDecreaseRest

QIoTMakeVerb ->
    'gera:so'_bh

QIoTSetVerb ->
    'setja:so'_bh
    | 'stilla:so'_bh

QIoTChangeVerb ->
    'breyta:so'_bh

QIoTLetVerb ->
    'láta:so'_bh

QIoTTurnOnVerb ->
    'kveikja:so'_bh

QIoTTurnOffVerb ->
    'slökkva:so'_bh

QIoTIncreaseOrDecreaseVerb ->
    QIoTIncreaseVerb
    | QIoTDecreaseVerb

QIoTIncreaseVerb ->
    'hækka:so'_bh
    | 'auka:so'_bh

QIoTDecreaseVerb ->
    'lækka:so'_bh
    | 'minnka:so'_bh

QIoTMakeRest ->
    QIoTSubject/þf QIoTHvar? QIoTHvernigMake
    | QIoTSubject/þf QIoTHvernigMake QIoTHvar?
    | QIoTHvar? QIoTSubject/þf QIoTHvernigMake
    | QIoTHvar? QIoTHvernigMake QIoTSubject/þf
    | QIoTHvernigMake QIoTSubject/þf QIoTHvar?
    | QIoTHvernigMake QIoTHvar? QIoTSubject/þf

# TODO: Add support for "stilltu rauðan lit á ljósið í eldhúsinu"
QIoTSetRest ->
    QIoTSubject/þf QIoTHvar? QIoTHvernigSet
    | QIoTSubject/þf QIoTHvernigSet QIoTHvar?
    | QIoTHvar? QIoTSubject/þf QIoTHvernigSet
    | QIoTHvar? QIoTHvernigSet QIoTSubject/þf
    | QIoTHvernigSet QIoTSubject/þf QIoTHvar?
    | QIoTHvernigSet QIoTHvar? QIoTSubject/þf

QIoTChangeRest ->
    QIoTSubjectOne/þgf QIoTHvar? QIoTHvernigChange
    | QIoTSubjectOne/þgf QIoTHvernigChange QIoTHvar?
    | QIoTHvar? QIoTSubjectOne/þgf QIoTHvernigChange
    | QIoTHvar? QIoTHvernigChange QIoTSubjectOne/þgf
    | QIoTHvernigChange QIoTSubjectOne/þgf QIoTHvar?
    | QIoTHvernigChange QIoTHvar? QIoTSubjectOne/þgf

QIoTLetRest ->
    QIoTSubject/þf QIoTHvar? QIoTHvernigLet
    | QIoTSubject/þf QIoTHvernigLet QIoTHvar?
    | QIoTHvar? QIoTSubject/þf QIoTHvernigLet
    | QIoTHvar? QIoTHvernigLet QIoTSubject/þf
    | QIoTHvernigLet QIoTSubject/þf QIoTHvar?
    | QIoTHvernigLet QIoTHvar? QIoTSubject/þf

QIoTTurnOnRest ->
    QIoTTurnOnLightsRest
    | QIoTAHverju QIoTHvar?
    | QIoTHvar? QIoTAHverju

QIoTTurnOnLightsRest ->
    QIoTLightSubject/þf QIoTHvar?
    | QIoTHvar? QIoTLightSubject/þf

# Would be good to add "slökktu á rauða litnum" functionality
QIoTTurnOffRest ->
    QIoTTurnOffLightsRest

QIoTTurnOffLightsRest ->
    QIoTLightSubject/þf QIoTHvar?
    | QIoTHvar? QIoTLightSubject/þf

# TODO: Make the subject categorization cleaner
QIoTIncreaseOrDecreaseRest ->
    QIoTLightSubject/þf QIoTHvar?
    | QIoTBrightnessSubject/þf QIoTHvar?

QIoTSubject/fall ->
    QIoTSubjectOne/fall
    | QIoTSubjectTwo/fall

# TODO: Decide whether LightSubject/þgf should be accepted
QIoTSubjectOne/fall ->
    QIoTLightSubject/fall
    | QIoTColorSubject/fall
    | QIoTBrightnessSubject/fall
    | QIoTSceneSubject/fall

QIoTSubjectTwo/fall ->
    QIoTGroupNameSubject/fall # á bara að styðja "gerðu eldhúsið rautt", "gerðu eldhúsið rómó" "gerðu eldhúsið bjartara", t.d.

QIoTHvar ->
    QIoTLocationPreposition QIoTGroupName/þgf

QIoTHvernigMake ->
    QIoTAnnadAndlag # gerðu litinn rauðan í eldhúsinu EÐA gerðu birtuna meiri í eldhúsinu
    | QIoTAdHverju # gerðu litinn að rauðum í eldhúsinu

QIoTHvernigSet ->
    QIoTAHvad

QIoTHvernigChange ->
    QIoTIHvad

QIoTHvernigLet ->
    QIoTBecome QIoTSomethingOrSomehow
    | QIoTBe QIoTSomehow

# I think these verbs only appear in these forms. 
# In which case these terminals should be deleted and a direct reference should be made in the relevant non-terminals.
QIoTBe ->
    "vera"

QIoTBecome ->
    "verða"

QIoTLightSubject/fall ->
    QIoTLight/fall

QIoTColorSubject/fall ->
    QIoTColorWord/fall QIoTLight/ef?
    | QIoTColorWord/fall "á" QIoTLight/þgf

QIoTBrightnessSubject/fall ->
    QIoTBrightnessWord/fall QIoTLight/ef?
    | QIoTBrightnessWord/fall "á" QIoTLight/þgf

QIoTSceneSubject/fall ->
    QIoTSceneWord/fall

QIoTGroupNameSubject/fall ->
    QIoTGroupName/fall

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

QIoTGroupName/fall ->
    no/fall

QIoTLightName/fall ->
    no/fall

QIoTColorName ->
    {" | ".join(f"'{color}:lo'" for color in _COLORS.keys())}

QIoTSceneName ->
    no

QIoTAnnadAndlag ->
    QIoTNewSetting/nf
    | QIoTSpyrjaHuldu/nf

QIoTAdHverju ->
    "að" QIoTNewSetting/þgf

QIoTAHvad ->
    "á" QIoTNewSetting/þf

QIoTIHvad ->
    "í" QIoTNewSetting/þf

QIoTAHverju ->
    "á" QIoTLight/þgf
    | "á" QIoTNewSetting/þgf

QIoTSomethingOrSomehow ->
    QIoTAnnadAndlag
    | QIoTAdHverju

QIoTSomehow ->
    QIoTAnnadAndlag

QIoTLight/fall ->
    QIoTLightName/fall
    | QIoTLightWord/fall

# Should 'birta' be included
QIoTLightWord/fall ->
    'ljós'/fall
    | 'lýsing'/fall
    | 'birta'/fall
    | 'Birta'/fall

QIoTColorWord/fall ->
    'litur'/fall
    | 'litblær'/fall
    | 'blær'/fall

QIoTBrightnessWords/fall ->
    'bjartur'/fall
    | QIoTBrightnessWord/fall

QIoTBrightnessWord/fall ->
    'birta'/fall
    | 'Birta'/fall
    | 'birtustig'/fall

QIoTSceneWord/fall ->
    'sena'/fall
    | 'stemning'/fall
    | 'stemming'/fall
    | 'stemmning'/fall

# Need to ask Hulda how this works.
QIoTSpyrjaHuldu/fall ->
    # QIoTHuldaColor/fall
    QIoTHuldaBrightness/fall
    # | QIoTHuldaScene/fall

# Do I need a "new light state" non-terminal?
QIoTNewSetting/fall ->
    QIoTNewColor/fall
    | QIoTNewBrightness/fall
    | QIoTNewScene/fall

# Missing "meira dimmt"
QIoTHuldaBrightness/fall ->
    QIoTMoreBrighterOrHigher/fall QIoTBrightnessWords/fall?
    | QIoTLessDarkerOrLower/fall QIoTBrightnessWords/fall?

#Unsure about whether to include /fall after QIoTColorName
QIoTNewColor/fall ->
    QIoTColorWord/fall QIoTColorName
    | QIoTColorName QIoTColorWord/fall?

QIoTNewBrightness/fall ->
    'sá'/fall? QIoTBrightestOrDarkest/fall
    | QIoTBrightestOrDarkest/fall QIoTBrightnessOrSettingWord/fall

QIoTNewScene/fall ->
    QIoTSceneWord/fall QIoTSceneName
    | QIoTSceneName QIoTSceneWord/fall

QIoTMoreBrighterOrHigher/fall ->
    'mikill:lo'_mst/fall
    | 'bjartur:lo'_mst/fall
    | 'ljós:lo'_mst/fall
    | 'hár:lo'_mst/fall

QIoTLessDarkerOrLower/fall ->
    'lítill:lo'_mst/fall
    | 'dökkur:lo'_mst/fall
    | 'dimmur:lo'_mst/fall
    | 'lágur:lo'_mst/fall

QIoTBrightestOrDarkest/fall ->
    QIoTBrightest/fall
    | QIoTDarkest/fall

QIoTBrightest/fall ->
    'bjartur:lo'_evb
    | 'bjartur:lo'_esb
    | 'ljós:lo'_evb
    | 'ljós:lo'_esb

QIoTDarkest/fall ->
    'dimmur:lo'_evb
    | 'dimmur:lo'_esb
    | 'dökkur:lo'_evb
    | 'dökkur:lo'_esb

QIoTBrightnessOrSettingWord/fall ->
    QIoTBrightnessWord/fall
    | QIoTSettingWord/fall

QIoTSettingWord/fall ->
    'stilling'/fall

"""


def QIoTColorWord(node: Node, params: QueryStateDict, result: Result) -> None:
    result.changing_color = True


def QIoTSceneWord(node: Node, params: QueryStateDict, result: Result) -> None:
    result.changing_scene = True


def QIoTBrightnessWord(node: Node, params: QueryStateDict, result: Result) -> None:
    result.changing_brightness = True


def QIoTQuery(node: Node, params: QueryStateDict, result: Result) -> None:
    result.qtype = _IoT_QTYPE


def QIoTTurnOnLightsRest(node: Node, params: QueryStateDict, result: Result) -> None:
    result.action = "turn_on"
    if "hue_obj" not in result:
        result["hue_obj"] = {"on": True}
    else:
        result["hue_obj"]["on"] = True


def QIoTTurnOffLightsRest(node: Node, params: QueryStateDict, result: Result) -> None:
    result.action = "turn_off"
    if "hue_obj" not in result:
        result["hue_obj"] = {"on": False}
    else:
        result["hue_obj"]["on"] = False


def QIoTNewColor(node: Node, params: QueryStateDict, result: Result) -> None:
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


def QIoTMoreBrighterOrHigher(
    node: Node, params: QueryStateDict, result: Result
) -> None:
    result.action = "increase_brightness"
    if "hue_obj" not in result:
        result["hue_obj"] = {"on": True, "bri_inc": 64}
    else:
        result["hue_obj"]["bri_inc"] = 64
        result["hue_obj"]["on"] = True


def QIoTLessDarkerOrLower(node: Node, params: QueryStateDict, result: Result) -> None:
    result.action = "decrease_brightness"
    if "hue_obj" not in result:
        result["hue_obj"] = {"bri_inc": -64}
    else:
        result["hue_obj"]["bri_inc"] = -64


def QIoTIncreaseVerb(node: Node, params: QueryStateDict, result: Result) -> None:
    result.action = "increase_brightness"
    if "hue_obj" not in result:
        result["hue_obj"] = {"on": True, "bri_inc": 64}
    else:
        result["hue_obj"]["bri_inc"] = 64
        result["hue_obj"]["on"] = True


def QIoTDecreaseVerb(node: Node, params: QueryStateDict, result: Result) -> None:
    result.action = "decrease_brightness"
    if "hue_obj" not in result:
        result["hue_obj"] = {"bri_inc": -64}
    else:
        result["hue_obj"]["bri_inc"] = -64


def QIoTBrightest(node: Node, params: QueryStateDict, result: Result) -> None:
    result.action = "decrease_brightness"
    if "hue_obj" not in result:
        result["hue_obj"] = {"bri": 255}
    else:
        result["hue_obj"]["bri"] = 255


def QIoTDarkest(node: Node, params: QueryStateDict, result: Result) -> None:
    result.action = "decrease_brightness"
    if "hue_obj" not in result:
        result["hue_obj"] = {"bri": 0}
    else:
        result["hue_obj"]["bri"] = 0


def QIoTNewScene(node: Node, params: QueryStateDict, result: Result) -> None:
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


def QIoTConnectLights(node: Node, params: QueryStateDict, result: Result) -> None:
    result.qtype = "connect_lights"
    result.action = "connect_lights"


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
        smartdevice_type = "smartlights"
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

    smartdevice_type = "smartlights"
    client_id = str(q.client_id)
    print("client_id:", client_id)

    # Fetch relevant data from the device_data table to perform an action on the lights
    device_data = cast(Optional[DeviceData], q.client_data(smartdevice_type))
    print("device data :", device_data)

    selected_light: Optional[str] = None
    hue_credentials: Optional[Dict[str, str]] = None

    if device_data is not None and smartdevice_type in device_data:
        dev = device_data[smartdevice_type]
        assert dev is not None
        selected_light = dev.get("selected_light")
        hue_credentials = dev.get("philips_hue")
        bridge_ip = hue_credentials.get("ipAddress")
        username = hue_credentials.get("username")

    if not device_data or not hue_credentials:
        answer = "ég var að kveikja ljósin! "
        q.set_answer(*gen_answer(answer))
        return

    # Successfully matched a query type
    print("bridge_ip: ", bridge_ip)
    print("username: ", username)
    print("selected light :", selected_light)
    print("hue credentials :", hue_credentials)

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
            read_jsfile("IoT_Embla/fuse.js")
            + f"var BRIDGE_IP = '{bridge_ip}';var USERNAME = '{username}';"
            + read_jsfile("IoT_Embla/Philips_Hue/fuse_search.js")
            + read_jsfile("IoT_Embla/Philips_Hue/lights.js")
            + read_jsfile("IoT_Embla/Philips_Hue/set_lights.js")
        )
        js += f"setLights('{light_or_group_name}', '{json.dumps(result.hue_obj)}');"
        q.set_command(js)
    except Exception as e:
        logging.warning("Exception while processing random query: {0}".format(e))
        q.set_error("E_EXCEPTION: {0}".format(e))
        raise

    # f"var BRIDGE_IP = '192.168.1.68';var USERNAME = 'p3obluiXT13IbHMpp4X63ZvZnpNRdbqqMt723gy2';"
