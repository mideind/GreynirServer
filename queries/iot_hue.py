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

from typing import Any, Callable, Dict, List, Optional, cast, FrozenSet
from typing_extensions import TypedDict

import logging
import random
import json
from pathlib import Path

from query import Query, QueryStateDict
from queries import read_jsfile, read_grammar_file
from tree import ParamList, Result, Node, TerminalNode


class _Creds(TypedDict):
    username: str
    ip_address: str


class _PhilipsHueData(TypedDict):
    credentials: _Creds


class _IoTDeviceData(TypedDict):
    philips_hue: _PhilipsHueData


_HUE_QTYPE = "Hue"

TOPIC_LEMMAS = [
    "ljós",
    "lampi",
    "útiljós",
    "kveikja",
    "slökkva",
    "litur",
    "birta",
    "hækka",
    "lækka",
    "sena",
    "stemmning",
    "stemming",
    "stemning",
]


def help_text(lemma: str) -> str:
    """Help text to return when query.py is unable to parse a query but
    one of the above lemmas is found in it"""
    return "Ég skil þig ef þú segir til dæmis: {0}.".format(
        random.choice(
            (
                "Breyttu lit lýsingarinnar í stofunni í bláan",
                "Gerðu ljósið í borðstofunni bjartara",
                "Stilltu á bjartasta niðri í kjallara",
                "Kveiktu á ljósunum inni í eldhúsi",
                "Slökktu á leslampanum",
            )
        )
    )


# This module wants to handle parse trees for queries
HANDLE_TREE = True

# The grammar nonterminals this module wants to handle
QUERY_NONTERMINALS = {"QHue"}

# Color name to [x,y] coordinates
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
    "sægrænn": [0.1664, 0.4621],
}

# The context-free grammar for the queries recognized by this plug-in module
GRAMMAR = read_grammar_file(
    "iot_hue",
    color_names=" | ".join(f"'{color}:lo'/fall" for color in _COLORS.keys()),
)


# Insert or update hue object kept in result
_upsert_hue_obj: Callable[[Result, Dict[str, Any]], None] = (
    lambda r, d: r.__setattr__("hue_obj", d)
    if "hue_obj" not in r
    else cast(Dict[str, Any], r["hue_obj"]).update(d)
)


def QHueQuery(node: Node, params: ParamList, result: Result) -> None:
    result.qtype = _HUE_QTYPE


def QHueTurnOnLights(node: Node, params: ParamList, result: Result) -> None:
    result.action = "turn_on"
    _upsert_hue_obj(result, {"on": True})


def QHueTurnOffLights(node: Node, params: ParamList, result: Result) -> None:
    result.action = "turn_off"
    _upsert_hue_obj(result, {"on": False})


def QHueChangeColor(node: Node, params: ParamList, result: Result) -> None:
    result.action = "set_color"
    color_hue = _COLORS.get(result.color_name, None)

    if color_hue is not None:
        _upsert_hue_obj(result, {"on": True, "xy": color_hue})


def QHueChangeScene(node: Node, params: ParamList, result: Result) -> None:
    result.action = "set_scene"
    scene_name = result.get("scene_name", None)

    if scene_name is not None:
        _upsert_hue_obj(result, {"on": True, "scene": scene_name})


def QHueIncreaseBrightness(node: Node, params: ParamList, result: Result) -> None:
    result.action = "increase_brightness"
    _upsert_hue_obj(result, {"on": True, "bri_inc": 64})


def QHueDecreaseBrightness(node: Node, params: ParamList, result: Result) -> None:
    result.action = "decrease_brightness"
    _upsert_hue_obj(result, {"bri_inc": -64})


def QHueCooler(node: Node, params: ParamList, result: Result) -> None:
    result.action = "decrease_colortemp"
    _upsert_hue_obj(result, {"ct_inc": -30000})


def QHueWarmer(node: Node, params: ParamList, result: Result) -> None:
    result.action = "increase_colortemp"
    _upsert_hue_obj(result, {"ct_inc": 30000})


def QHueBrightest(node: Node, params: ParamList, result: Result) -> None:
    result.action = "increase_brightness"
    _upsert_hue_obj(result, {"bri": 255})


def QHueDarkest(node: Node, params: ParamList, result: Result) -> None:
    result.action = "decrease_brightness"
    _upsert_hue_obj(result, {"bri": 0})


def QHueColorName(node: Node, params: ParamList, result: Result) -> None:
    fc = node.first_child(lambda x: True)
    if fc:
        result["color_name"] = fc.string_self().strip("'").split(":")[0]


def QHueSceneName(node: Node, params: ParamList, result: Result) -> None:
    result["scene_name"] = result._indefinite
    result["changing_scene"] = True


def QHueGroupName(node: Node, params: ParamList, result: Result) -> None:
    result["group_name"] = result._indefinite


def QHueEverywhere(node: Node, params: ParamList, result: Result) -> None:
    result["everywhere"] = True


def QHueAllLights(node: Node, params: ParamList, result: Result) -> None:
    result["everywhere"] = True


def QHueLightName(node: Node, params: ParamList, result: Result) -> None:
    result["light_name"] = result._indefinite


# Used to distinguish queries intended for music/radio/speaker modules
_SPEAKER_WORDS: FrozenSet[str] = frozenset(
    (
        "tónlist",
        "lag",
        "hljóð",
        "ljóð",
        "hátalari",
        "útvarp",
        "útvarpsstöð",
        "útvarp saga",
        "bylgja",
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
    )
)

# Used when grammar mistakes a generic word
# for lights as the name of a group
_PROBABLY_LIGHT_NAME: FrozenSet[str] = frozenset(
    (
        "ljós",
        "loftljós",
        "gólfljós",
        "veggljós",
        "lampi",
        "lampar",
        "borðlampi",
        "gólflampi",
        "vegglampi",
    )
)


def sentence(state: QueryStateDict, result: Result) -> None:
    """Called when sentence processing is complete"""
    q: Query = state["query"]

    # Extract matched terminals in grammar (used like lemmas in this case)
    lemmas = set(
        i[0].root(state, result.params)
        for i in result.enum_descendants(lambda x: isinstance(x, TerminalNode))
    )
    if not lemmas.isdisjoint(_SPEAKER_WORDS) or result.qtype != _HUE_QTYPE:
        # Uses a word that is associated with the sonos module
        # (or incorrect qtype)
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
        return

    q.set_qtype(result.qtype)
    if "action" in result:
        q.set_key(result.action)

    try:
        # TODO: Caching?
        cd = q.client_data("iot")
        device_data = (
            cast(Optional[_IoTDeviceData], cd.get("iot_lights")) if cd else None
        )

        bridge_ip: Optional[str] = None
        username: Optional[str] = None
        if device_data is not None:
            # TODO: Error checking
            bridge_ip = device_data["philips_hue"]["credentials"]["ip_address"]
            username = device_data["philips_hue"]["credentials"]["username"]

        if not device_data or not (bridge_ip and username):
            q.set_answer(
                {"answer": "Það vantar að tengja Philips Hue miðstöðina."},
                "Það vantar að tengja Philips Hue miðstöðina.",
                "Það vantar að tengja filips hjú miðstöðina.",
            )
            return

        light = result.get("light_name", "*")
        if light == "ljós":
            # Non-specific word for light, so we match all
            light = "*"

        group = result.get("group_name", "")
        if result.get("everywhere"):
            # Specifically asked for everywhere, match every group
            group = "*"

        # If group or scene name is more like the name of a light
        if group in _PROBABLY_LIGHT_NAME:
            light, group = group, light

        q.set_answer(
            {"answer": "Skal gert."},
            "Skal gert.",
            '<break time="2s"/>',
        )
        q.set_command(
            read_jsfile(str(Path("Libraries", "fuse.js")))
            + read_jsfile(str(Path("Philips_Hue", "set_lights.js")))
            + f"return await setLights('{bridge_ip}','{username}','{light}','{group}','{json.dumps(result.hue_obj)}');"
        )

    except Exception as e:
        logging.warning("Exception while processing iot_hue query: {0}".format(e))
        q.set_error("E_EXCEPTION: {0}".format(e))
        raise
