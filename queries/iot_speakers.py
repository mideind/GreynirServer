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

from typing import Dict, Mapping, Optional, cast
from typing_extensions import TypedDict

import logging
import random
import json
import flask

from query import Query, QueryStateDict, AnswerTuple
from queries import gen_answer, read_jsfile, read_grammar_file
from tree import Result, Node


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

GRAMMAR = f"""

/þgf = þgf
/ef = ef

Query →
    QIoTSpeaker '?'?

QIoTSpeaker → 
    QIoTSpeakerQuery

QIoTSpeakerQuery ->
    QIoTSpeakerMakeVerb QIoTSpeakerMakeRest
    | QIoTSpeakerSetVerb QIoTSpeakerSetRest
    | QIoTSpeakerChangeVerb QIoTSpeakerChangeRest
    | QIoTSpeakerLetVerb QIoTSpeakerLetRest
    | QIoTSpeakerTurnOnVerb QIoTSpeakerTurnOnRest
    | QIoTSpeakerTurnOffVerb QIoTSpeakerTurnOffRest
    | QIoTSpeakerIncreaseOrDecreaseVerb QIoTSpeakerIncreaseOrDecreaseRest

QIoTSpeakerMakeVerb ->
    'gera:so'_bh

QIoTSpeakerSetVerb ->
    'setja:so'_bh
    | 'stilla:so'_bh

QIoTSpeakerChangeVerb ->
    'breyta:so'_bh

QIoTSpeakerLetVerb ->
    'láta:so'_bh

QIoTSpeakerTurnOnVerb ->
    'kveikja:so'_bh

QIoTSpeakerTurnOffVerb ->
    'slökkva:so'_bh

QIoTSpeakerIncreaseOrDecreaseVerb ->
    QIoTSpeakerIncreaseVerb
    | QIoTSpeakerDecreaseVerb

QIoTSpeakerIncreaseVerb ->
    'hækka:so'_bh
    | 'auka:so'_bh

QIoTSpeakerDecreaseVerb ->
    'lækka:so'_bh
    | 'minnka:so'_bh

QCHANGEMakeRest ->
    # QCHANGESubject/þf QCHANGEHvar? QCHANGEHvernigMake
    # | QCHANGESubject/þf QCHANGEHvernigMake QCHANGEHvar?
    # | QCHANGEHvar? QCHANGESubject/þf QCHANGEHvernigMake
    # | QCHANGEHvar? QCHANGEHvernigMake QCHANGESubject/þf
    # | QCHANGEHvernigMake QCHANGESubject/þf QCHANGEHvar?
    # | QCHANGEHvernigMake QCHANGEHvar? QCHANGESubject/þf
    QIoTSpeakerMusicWord/þf QIoTSpeakerHvar?

# TODO: Add support for "stilltu rauðan lit á ljósið í eldhúsinu"
QCHANGESetRest ->
    # QCHANGESubject/þf QCHANGEHvar? QCHANGEHvernigSet
    # | QCHANGESubject/þf QCHANGEHvernigSet QCHANGEHvar?
    # | QCHANGEHvar? QCHANGESubject/þf QCHANGEHvernigSet
    # | QCHANGEHvar? QCHANGEHvernigSet QCHANGESubject/þf
    # | QCHANGEHvernigSet QCHANGESubject/þf QCHANGEHvar?
    # | QCHANGEHvernigSet QCHANGEHvar? QCHANGESubject/þf
    "á" QIoTSpeakerMusicWord/þf QIoTSpeakerHvar?

QCHANGEChangeRest ->
    # QCHANGESubjectOne/þgf QCHANGEHvar? QCHANGEHvernigChange
    # | QCHANGESubjectOne/þgf QCHANGEHvernigChange QCHANGEHvar?
    # | QCHANGEHvar? QCHANGESubjectOne/þgf QCHANGEHvernigChange
    # | QCHANGEHvar? QCHANGEHvernigChange QCHANGESubjectOne/þgf
    # | QCHANGEHvernigChange QCHANGESubjectOne/þgf QCHANGEHvar?
    # | QCHANGEHvernigChange QCHANGEHvar? QCHANGESubjectOne/þgf

QCHANGELetRest ->
    QCHANGESubject/þf QCHANGEHvar? QCHANGEHvernigLet
    | QCHANGESubject/þf QCHANGEHvernigLet QCHANGEHvar?
    | QCHANGEHvar? QCHANGESubject/þf QCHANGEHvernigLet
    | QCHANGEHvar? QCHANGEHvernigLet QCHANGESubject/þf
    | QCHANGEHvernigLet QCHANGESubject/þf QCHANGEHvar?
    | QCHANGEHvernigLet QCHANGEHvar? QCHANGESubject/þf
    "vera" QIoTSpeakerMusicWord/þf QIoTSpeakerHvar?

QCHANGETurnOnRest ->
    # QCHANGETurnOnLightsRest
    # | QCHANGEAHverju QCHANGEHvar?
    # | QCHANGEHvar? QCHANGEAHverju
    "á" QIoTSpeakerMusicWord/þgf QIoTSpeakerHvar?

# QCHANGETurnOnLightsRest ->
#     QCHANGELightSubject/þf QCHANGEHvar?
#     | QCHANGEHvar QCHANGELightSubject/þf?

# Would be good to add "slökktu á rauða litnum" functionality
QCHANGETurnOffRest ->
    # QCHANGETurnOffLightsRest
    "á" QIoTSpeakerMusicWord/þgf QIoTSpeakerHvar?

# QCHANGETurnOffLightsRest ->
#     QCHANGELightSubject/þf QCHANGEHvar?
#     | QCHANGEHvar QCHANGELightSubject/þf?

# TODO: Make the subject categorization cleaner
QCHANGEIncreaseOrDecreaseRest ->
    # QCHANGELightSubject/þf QCHANGEHvar?
    # | QCHANGEBrightnessSubject/þf QCHANGEHvar?
    QIoTSpeakerMusicWord/þf QIoTSpeakerHvar?
    | "í" QIoTSpeakerMusicWord/þgf QIoTSpeakerHvar?

# QCHANGESubject/fall ->
#     QCHANGESubjectOne/fall
#     | QCHANGESubjectTwo/fall

QIoTMusicWord ->
    'tónlist'/fall

# # TODO: Decide whether LightSubject/þgf should be accepted
# QCHANGESubjectOne/fall ->
#     QCHANGELightSubject/fall
#     | QCHANGEColorSubject/fall
#     | QCHANGEBrightnessSubject/fall
#     | QCHANGESceneSubject/fall

# QCHANGESubjectTwo/fall ->
#     QCHANGEGroupNameSubject/fall # á bara að styðja "gerðu eldhúsið rautt", "gerðu eldhúsið rómó" "gerðu eldhúsið bjartara", t.d.

QIoTSpeakerHvar ->
    QIoTSpeakerLocationPreposition QIoTSpeakerGroupName/þgf

# QCHANGEHvernigMake ->
#     QCHANGEAnnadAndlag # gerðu litinn rauðan í eldhúsinu EÐA gerðu birtuna meiri í eldhúsinu
#     | QCHANGEAdHverju # gerðu litinn að rauðum í eldhúsinu
#     | QCHANGEThannigAd

# QCHANGEHvernigSet ->
#     QCHANGEAHvad
#     | QCHANGEThannigAd

# QCHANGEHvernigChange ->
#     QCHANGEIHvad
#     | QCHANGEThannigAd

# QCHANGEHvernigLet ->
#     QCHANGEBecome QCHANGESomethingOrSomehow
#     | QCHANGEBe QCHANGESomehow

# QCHANGEThannigAd ->
#     "þannig" "að"? pfn_nf QCHANGEBeOrBecomeSubjunctive QCHANGEAnnadAndlag

# I think these verbs only appear in these forms. 
# In which case these terminals should be deleted and a direct reference should be made in the relevant non-terminals.
# QCHANGEBe ->
#     "vera"

# QCHANGEBecome ->
#     "verða"

# QCHANGEBeOrBecomeSubjunctive ->
#     "verði"
#     | "sé"

# QCHANGELightSubject/fall ->
#     QCHANGELight/fall

# QCHANGEColorSubject/fall ->
#     QCHANGEColorWord/fall QCHANGELight/ef?
#     | QCHANGEColorWord/fall "á" QCHANGELight/þgf

# QCHANGEBrightnessSubject/fall ->
#     QCHANGEBrightnessWord/fall QCHANGELight/ef?
#     | QCHANGEBrightnessWord/fall "á" QCHANGELight/þgf

# QCHANGESceneSubject/fall ->
#     QCHANGESceneWord/fall

# QCHANGEGroupNameSubject/fall ->
#     QCHANGEGroupName/fall

QIoTSpeakerLocationPreposition ->
    QIoTSpeakerLocationPrepositionFirstPart? QIoTSpeakerLocationPrepositionSecondPart

# The latter proverbs are grammatically incorrect, but common errors, both in speech and transcription.
# The list provided is taken from StefnuAtv in Greynir.grammar. That includes "aftur:ao", which is not applicable here.
QIoTSpeakerLocationPrepositionFirstPart ->
    StaðarAtv
    | "fram:ao"
    | "inn:ao"
    | "niður:ao"
    | "upp:ao"
    | "út:ao"

QIoTSpeakerLocationPrepositionSecondPart ->
    "á" | "í"

QIoTSpeakerGroupName/fall ->
    no/fall

# QCHANGELightName/fall ->
#     no/fall

# QCHANGEColorName ->
#     {" | ".join(f"'{color}:lo'" for color in _COLORS.keys())}

# QCHANGESceneName ->
#     no
#     | lo

# QCHANGEAnnadAndlag ->
#     QCHANGENewSetting/nf
#     | QCHANGESpyrjaHuldu/nf

# QCHANGEAdHverju ->
#     "að" QCHANGENewSetting/þgf

# QCHANGEAHvad ->
#     "á" QCHANGENewSetting/þf

# QCHANGEIHvad ->
#     "í" QCHANGENewSetting/þf

# QCHANGEAHverju ->
#     "á" QCHANGELight/þgf
#     | "á" QCHANGENewSetting/þgf

# QCHANGESomethingOrSomehow ->
#     QCHANGEAnnadAndlag
#     | QCHANGEAdHverju

# QCHANGESomehow ->
#     QCHANGEAnnadAndlag
#     | QCHANGEThannigAd

# QCHANGELight/fall ->
#     QCHANGELightName/fall
#     | QCHANGELightWord/fall

# # Should 'birta' be included
# QCHANGELightWord/fall ->
#     'ljós'/fall
#     | 'lýsing'/fall
#     | 'birta'/fall
#     | 'Birta'/fall

# QCHANGEColorWord/fall ->
#     'litur'/fall
#     | 'litblær'/fall
#     | 'blær'/fall

# QCHANGEBrightnessWords/fall ->
#     'bjartur'/fall
#     | QCHANGEBrightnessWord/fall

# QCHANGEBrightnessWord/fall ->
#     'birta'/fall
#     | 'Birta'/fall
#     | 'birtustig'/fall

# QCHANGESceneWord/fall ->
#     'sena'/fall
#     | 'stemning'/fall
#     | 'stemming'/fall
#     | 'stemmning'/fall

# # Need to ask Hulda how this works.
# QCHANGESpyrjaHuldu/fall ->
#     # QCHANGEHuldaColor/fall
#     QCHANGEHuldaBrightness/fall
#     # | QCHANGEHuldaScene/fall

# # Do I need a "new light state" non-terminal?
# QCHANGENewSetting/fall ->
#     QCHANGENewColor/fall
#     | QCHANGENewBrightness/fall
#     | QCHANGENewScene/fall

# # Missing "meira dimmt"
# QCHANGEHuldaBrightness/fall ->
#     QCHANGEMoreBrighterOrHigher/fall QCHANGEBrightnessWords/fall?
#     | QCHANGELessDarkerOrLower/fall QCHANGEBrightnessWords/fall?

# #Unsure about whether to include /fall after QCHANGEColorName
# QCHANGENewColor/fall ->
#     QCHANGEColorWord/fall QCHANGEColorName
#     | QCHANGEColorName QCHANGEColorWord/fall?

# QCHANGENewBrightness/fall ->
#     'sá'/fall? QCHANGEBrightestOrDarkest/fall
#     | QCHANGEBrightestOrDarkest/fall QCHANGEBrightnessOrSettingWord/fall

# QCHANGENewScene/fall ->
#     QCHANGESceneWord/fall QCHANGESceneName
#     | QCHANGESceneName QCHANGESceneWord/fall?

# QCHANGEMoreBrighterOrHigher/fall ->
#     'mikill:lo'_mst/fall
#     | 'bjartur:lo'_mst/fall
#     | 'ljós:lo'_mst/fall
#     | 'hár:lo'_mst/fall

# QCHANGELessDarkerOrLower/fall ->
#     'lítill:lo'_mst/fall
#     | 'dökkur:lo'_mst/fall
#     | 'dimmur:lo'_mst/fall
#     | 'lágur:lo'_mst/fall

# QCHANGEBrightestOrDarkest/fall ->
#     QCHANGEBrightest/fall
#     | QCHANGEDarkest/fall

# QCHANGEBrightest/fall ->
#     'bjartur:lo'_evb
#     | 'bjartur:lo'_esb
#     | 'ljós:lo'_evb
#     | 'ljós:lo'_esb

# QCHANGEDarkest/fall ->
#     'dimmur:lo'_evb
#     | 'dimmur:lo'_esb
#     | 'dökkur:lo'_evb
#     | 'dökkur:lo'_esb

# QCHANGEBrightnessOrSettingWord/fall ->
#     QCHANGEBrightnessWord/fall
#     | QCHANGESettingWord/fall

# QCHANGESettingWord/fall ->
#     'stilling'/fall

"""


def QIoTSpeakerIncreaseVerb(node: Node, params: QueryStateDict, result: Result) -> None:
    result.action = "increase_volume"


def QIoTSpeakerDecreaseVerb(node: Node, params: QueryStateDict, result: Result) -> None:
    result.action = "decrease_volume"


def QIoTSpeakerGroupName(node: Node, params: QueryStateDict, result: Result) -> None:
    result["group_name"] = result._indefinite


def sentence(state: QueryStateDict, result: Result) -> None:
    """Called when sentence processing is complete"""
    q: Query = state["query"]

    q.set_qtype(result.get["qtype"])

    smartdevice_type = "smartSpeaker"

    # Fetch relevant data from the device_data table to perform an action on the lights
    device_data = cast(Optional[DeviceData], q.client_data(smartdevice_type))


    if device_data is not None and smartdevice_type in device_data:
        dev = device_data[smartdevice_type]
        assert dev is not None
        selected_light = dev.get("selected_light")
        hue_credentials = dev.get("philips_hue")
        bridge_ip = hue_credentials.get("ipAddress")
        username = hue_credentials.get("username")

    if not device_data or not hue_credentials:
        answer = "Það vantar að tengja Philips Hub-inn."
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
