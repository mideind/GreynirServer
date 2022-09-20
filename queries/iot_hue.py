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
# TODO: substitution klósett -> baðherbergi, for common room names and alternative ways of saying
# TODO: Cut down javascript sent to Embla
# TODO: Two specified groups or lights.
# TODO: No specified location
# TODO: Fix scene issues
# TODO: Turning on lights without using "turn on"
# TODO: Add functionality for robot-like commands "ljós í eldhúsinu", "rautt í eldhúsinu"
# TODO: Mistakes 'gerðu ljósið kaldara' for the scene 'köld'

from typing import Dict, List, Optional, cast, FrozenSet
from typing_extensions import TypedDict

import logging
import random
import json
from pathlib import Path

from query import Query, QueryStateDict
from queries import gen_answer, read_jsfile, read_grammar_file
from tree import ParamList, Result, Node, TerminalNode


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
                "Kveiktu á ljósunum inni í eldhúsi",
                "Slökktu á leslampanum",
                "Breyttu lit lýsingarinnar í stofunni í bláan",
                "Gerðu ljósið í borðstofunni bjartara",
                "Stilltu á bjartasta niðri í kjallara",
            )
        )
    )


# This module wants to handle parse trees for queries
HANDLE_TREE = True

# The grammar nonterminals this module wants to handle
QUERY_NONTERMINALS = {"QIoT"}

_COLORS: Dict[str, List[float]] = {
    "appelsínugulur": [0.6195, 0.3624],
    "bleikur": [0.4443, 0.2006],
    "blár": [0.1545, 0.0981],
    "fjólublár": [0.2291, 0.0843],
    "grænn": [0.2458, 0.6431],
    "gulur": [0.4833, 0.4647],
    "hvítur": [0.3085, 0.3275],
    "ljósblár": [0.1581, 0.2395],
    "rauður": [0.7, 0.3],
}

# The context-free grammar for the queries recognized by this plug-in module
GRAMMAR = read_grammar_file(
    "iot_hue", color_names=" | ".join(f"'{color}:lo'" for color in _COLORS.keys())
)


def QIoTQuery(node: Node, params: ParamList, result: Result) -> None:
    result.qtype = _IoT_QTYPE


def QIoTColorWord(node: Node, params: ParamList, result: Result) -> None:
    result.changing_color = True


def QIoTSceneWord(node: Node, params: ParamList, result: Result) -> None:
    result.changing_scene = True


def QIoTBrightnessWord(node: Node, params: ParamList, result: Result) -> None:
    result.changing_brightness = True


def QIoTTurnOnLightsRest(node: Node, params: ParamList, result: Result) -> None:
    result.action = "turn_on"
    if "hue_obj" not in result:
        result["hue_obj"] = {"on": True}
    else:
        result["hue_obj"]["on"] = True


def QIoTTurnOffLightsRest(node: Node, params: ParamList, result: Result) -> None:
    result.action = "turn_off"
    if "hue_obj" not in result:
        result["hue_obj"] = {"on": False}
    else:
        result["hue_obj"]["on"] = False


def QIoTNewColor(node: Node, params: ParamList, result: Result) -> None:
    result.action = "set_color"
    color_hue = _COLORS.get(result.color_name, None)

    if color_hue is not None:
        if "hue_obj" not in result:
            result["hue_obj"] = {"on": True, "xy": color_hue}
        else:
            result["hue_obj"]["xy"] = color_hue
            result["hue_obj"]["on"] = True


def QIoTMoreBrighterOrHigher(node: Node, params: ParamList, result: Result) -> None:
    result.action = "increase_brightness"
    if "hue_obj" not in result:
        result["hue_obj"] = {"on": True, "bri_inc": 64}
    else:
        result["hue_obj"]["bri_inc"] = 64
        result["hue_obj"]["on"] = True


def QIoTLessDarkerOrLower(node: Node, params: ParamList, result: Result) -> None:
    result.action = "decrease_brightness"
    if "hue_obj" not in result:
        result["hue_obj"] = {"bri_inc": -64}
    else:
        result["hue_obj"]["bri_inc"] = -64


def QIoTIncreaseVerb(node: Node, params: ParamList, result: Result) -> None:
    result.action = "increase_brightness"
    if "hue_obj" not in result:
        result["hue_obj"] = {"on": True, "bri_inc": 64}
    else:
        result["hue_obj"]["bri_inc"] = 64
        result["hue_obj"]["on"] = True


def QIoTCooler(node: Node, params: ParamList, result: Result) -> None:
    result.action = "decrease_colortemp"
    result.changing_temp = True
    if "hue_obj" not in result:
        result["hue_obj"] = {"ct_inc": -30000}
    else:
        result["hue_obj"]["ct_inc"] = -30000


def QIoTWarmer(node: Node, params: ParamList, result: Result) -> None:
    result.action = "increase_colortemp"
    result.changing_temp = True
    if "hue_obj" not in result:
        result["hue_obj"] = {"ct_inc": 30000}
    else:
        result["hue_obj"]["ct_inc"] = 30000


def QIoTDecreaseVerb(node: Node, params: ParamList, result: Result) -> None:
    result.action = "decrease_brightness"
    if "hue_obj" not in result:
        result["hue_obj"] = {"bri_inc": -64}
    else:
        result["hue_obj"]["bri_inc"] = -64


def QIoTBrightest(node: Node, params: ParamList, result: Result) -> None:
    result.action = "increase_brightness"
    if "hue_obj" not in result:
        result["hue_obj"] = {"bri": 255}
    else:
        result["hue_obj"]["bri"] = 255


def QIoTDarkest(node: Node, params: ParamList, result: Result) -> None:
    result.action = "decrease_brightness"
    if "hue_obj" not in result:
        result["hue_obj"] = {"bri": 0}
    else:
        result["hue_obj"]["bri"] = 0


def QIoTNewScene(node: Node, params: ParamList, result: Result) -> None:
    result.action = "set_scene"
    scene_name = result.get("scene_name", None)
    if scene_name is not None:
        if "hue_obj" not in result:
            result["hue_obj"] = {"on": True, "scene": scene_name}
        else:
            result["hue_obj"]["scene"] = scene_name
            result["hue_obj"]["on"] = True


def QIoTColorName(node: Node, params: ParamList, result: Result) -> None:
    fc = node.first_child(lambda x: True)
    if fc:
        result["color_name"] = fc.string_self().strip("'").split(":")[0]


def QIoTSceneName(node: Node, params: ParamList, result: Result) -> None:
    result["scene_name"] = result._indefinite
    result["changing_scene"] = True
    print("scene: " + result.get("scene_name", None))


def QIoTGroupName(node: Node, params: ParamList, result: Result) -> None:
    result["group_name"] = result._indefinite


def QIoTLightName(node: Node, params: ParamList, result: Result) -> None:
    result["light_name"] = result._indefinite


def QIoTSpeakerHotwords(node: Node, params: ParamList, result: Result) -> None:
    print("lights banwords")
    result.abort = True


_SPEAKER_WORDS: FrozenSet[str] = frozenset(
    (
        "tónlist",
        "lag",
        "hátalari",
        "bylgja",
        "útvarp",
        "útvarpsstöð",
        "útvarp saga",
        "gullbylgja",
        "x-ið",
        "léttbylgjan",
        "rás 1",
        "rás 2",
        "rondo",
        "rondó",
        "fm 957",
        "fm957",
        "fm-957",
        "k-100",
        "k 100",
        "kk 100",
        "k hundrað",
        "kk hundrað",
        "x977",
        "x 977",
        "x-977",
        "x-ið 977",
        "x-ið",
        "retro",
        "kiss fm",
        "flassbakk",
        "flassbakk fm",
        "útvarp hundraðið",
        "útvarp 101",
        "útvarp hundraðogeinn",
        "útvarp hundrað og einn",
        "útvarp hundrað einn",
        "útvarp hundrað 1",
        "útvarp",
    )
)


def sentence(state: QueryStateDict, result: Result) -> None:
    """Called when sentence processing is complete"""
    q: Query = state["query"]
    if result.get("abort"):
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
        return

    # Extract matched terminals in grammar (used like lemmas in this case)
    lemmas = set(
        i[0].root(state, result.params)
        for i in result.enum_descendants(lambda x: isinstance(x, TerminalNode))
    )
    if not lemmas.isdisjoint(_SPEAKER_WORDS):
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
        return
    changing_color = result.get("changing_color", False)
    changing_scene = result.get("changing_scene", False)
    changing_brightness = result.get("changing_brightness", False)
    # changing_temp = result.get("changing_temp", False)
    if (
        sum((changing_color, changing_scene, changing_brightness)) > 1
        or "qtype" not in result
    ):
        print("Multiple options error?")
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
        return

    q.set_qtype(result.qtype)

    smartdevice_type = "iot"
    cd = q.client_data(smartdevice_type)
    device_data = None
    if cd:
        # Fetch relevant data from the device_data table to perform an action on the lights
        device_data = cast(Optional[DeviceData], cd.get("iot_lights"))

    hue_credentials: Optional[Dict[str, str]] = None

    if device_data is not None:
        dev = device_data
        assert dev is not None
        # TODO: Better error checking
        light = dev.get("philips_hue")
        hue_credentials = light.get("credentials")
        bridge_ip = hue_credentials.get("ip_address")
        username = hue_credentials.get("username")

    if not device_data or not hue_credentials:
        answer = "Það vantar að tengja Philips Hub-inn."
        q.set_answer(*gen_answer(answer))
        return

    try:
        # TODO: What if light and group is empty?
        light_or_group_name = result.get("light_name", result.get("group_name", ""))

        q.set_answer(
            {"answer": "Skal gert."},
            "Skal gert.",
            '<break time="2s"/>',
        )
        js = (
            read_jsfile(str(Path("Libraries", "fuse.js")))
            + f"var BRIDGE_IP = '{bridge_ip}';var USERNAME = '{username}';"
            + read_jsfile(str(Path("Philips_Hue", "fuse_search.js")))
            + read_jsfile(str(Path("Philips_Hue", "set_lights.js")))
        )
        js += f"return setLights('{light_or_group_name}', '{json.dumps(result.hue_obj)}');"
        q.set_command(js)
    except Exception as e:
        logging.warning("Exception while processing random query: {0}".format(e))
        q.set_error("E_EXCEPTION: {0}".format(e))
        raise
