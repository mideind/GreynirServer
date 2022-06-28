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
from datetime import datetime, timedelta

from query import Query, QueryStateDict, AnswerTuple
from queries import gen_answer, read_jsfile, read_grammar_file
from queries.sonos import SonosClient
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
    # | QIoTSpeakerChangeVerb QIoTSpeakerChangeRest
    | QIoTSpeakerLetVerb QIoTSpeakerLetRest
    | QIoTSpeakerTurnOnVerb QIoTSpeakerTurnOnRest
    | QIoTSpeakerTurnOffVerb QIoTSpeakerTurnOffRest
    | QIoTSpeakerPlayVerb QIoTSpeakerPlayRest
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

QIoTSpeakerPlayVerb ->
    'spila:so'_bh
    | "spilaðu"

QIoTSpeakerIncreaseOrDecreaseVerb ->
    QIoTSpeakerIncreaseVerb
    | QIoTSpeakerDecreaseVerb

QIoTSpeakerIncreaseVerb ->
    'hækka:so'_bh
    | 'auka:so'_bh

QIoTSpeakerDecreaseVerb ->
    'lækka:so'_bh
    | 'minnka:so'_bh

QIoTSpeakerMakeRest ->
    # QCHANGESubject/þf QCHANGEHvar? QCHANGEHvernigMake
    # | QCHANGESubject/þf QCHANGEHvernigMake QCHANGEHvar?
    # | QCHANGEHvar? QCHANGESubject/þf QCHANGEHvernigMake
    # | QCHANGEHvar? QCHANGEHvernigMake QCHANGESubject/þf
    # | QCHANGEHvernigMake QCHANGESubject/þf QCHANGEHvar?
    # | QCHANGEHvernigMake QCHANGEHvar? QCHANGESubject/þf
    QIoTSpeakerMusicWord/þf QIoTSpeakerHvar?

# TODO: Add support for "stilltu rauðan lit á ljósið í eldhúsinu"
QIoTSpeakerSetRest ->
    # QCHANGESubject/þf QCHANGEHvar? QCHANGEHvernigSet
    # | QCHANGESubject/þf QCHANGEHvernigSet QCHANGEHvar?
    # | QCHANGEHvar? QCHANGESubject/þf QCHANGEHvernigSet
    # | QCHANGEHvar? QCHANGEHvernigSet QCHANGESubject/þf
    # | QCHANGEHvernigSet QCHANGESubject/þf QCHANGEHvar?
    # | QCHANGEHvernigSet QCHANGEHvar? QCHANGESubject/þf
    "á" QIoTSpeakerMusicWord/þf QIoTSpeakerHvar?

# QIoTSpeakerChangeRest ->
    # QCHANGESubjectOne/þgf QCHANGEHvar? QCHANGEHvernigChange
    # | QCHANGESubjectOne/þgf QCHANGEHvernigChange QCHANGEHvar?
    # | QCHANGEHvar? QCHANGESubjectOne/þgf QCHANGEHvernigChange
    # | QCHANGEHvar? QCHANGEHvernigChange QCHANGESubjectOne/þgf
    # | QCHANGEHvernigChange QCHANGESubjectOne/þgf QCHANGEHvar?
    # | QCHANGEHvernigChange QCHANGEHvar? QCHANGESubjectOne/þgf

QIoTSpeakerLetRest ->
    # QCHANGESubject/þf QCHANGEHvar? QCHANGEHvernigLet
    # | QCHANGESubject/þf QCHANGEHvernigLet QCHANGEHvar?
    # | QCHANGEHvar? QCHANGESubject/þf QCHANGEHvernigLet
    # | QCHANGEHvar? QCHANGEHvernigLet QCHANGESubject/þf
    # | QCHANGEHvernigLet QCHANGESubject/þf QCHANGEHvar?
    # | QCHANGEHvernigLet QCHANGEHvar? QCHANGESubject/þf
    "vera" QIoTSpeakerMusicWord/þf QIoTSpeakerHvar?
    | "á" QIoTSpeakerMusicWord/þf QIoTSpeakerHvar?

QIoTSpeakerTurnOnRest ->
    # QCHANGETurnOnLightsRest
    # | QCHANGEAHverju QCHANGEHvar?
    # | QCHANGEHvar? QCHANGEAHverju
    "á" QIoTSpeakerMusicWord/þgf QIoTSpeakerHvar?

# QCHANGETurnOnLightsRest ->
#     QCHANGELightSubject/þf QCHANGEHvar?
#     | QCHANGEHvar QCHANGELightSubject/þf?

# Would be good to add "slökktu á rauða litnum" functionality
QIoTSpeakerTurnOffRest ->
    # QCHANGETurnOffLightsRest
    "á" QIoTSpeakerMusicWord/þgf QIoTSpeakerHvar?

# QCHANGETurnOffLightsRest ->
#     QCHANGELightSubject/þf QCHANGEHvar?
#     | QCHANGEHvar QCHANGELightSubject/þf?

QIoTSpeakerPlayRest ->
    QIoTSpeakerMusicWord/þf QIoTSpeakerHvar?
    | "tónlist"

# TODO: Make the subject categorization cleaner
QIoTSpeakerIncreaseOrDecreaseRest ->
    # QCHANGELightSubject/þf QCHANGEHvar?
    # | QCHANGEBrightnessSubject/þf QCHANGEHvar?
    QIoTSpeakerMusicWord/þf QIoTSpeakerHvar?
    | "í" QIoTSpeakerMusicWord/þgf QIoTSpeakerHvar?

# QCHANGESubject/fall ->
#     QCHANGESubjectOne/fall
#     | QCHANGESubjectTwo/fall

QIoTSpeakerMusicWord/fall ->
    'tónlist:no'/fall

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


def QIoTMusicWord(node: Node, params: QueryStateDict, result: Result) -> None:
    result.target = "music"
    print("music")


def sentence(state: QueryStateDict, result: Result) -> None:
    # try:
    print("sentence")
    """Called when sentence processing is complete"""
    q: Query = state["query"]

    q.set_qtype(result.get("qtype"))

    # TODO: Find way to only catch playing commands
    if result.get("action") == None:
        result.action = "play_music"

    smartdevice_type = "smart_speaker"

    # Fetch relevant data from the device_data table to perform an action on the lights
    # sonos_code = q.client_data("sonos_code")
    device_data = q.client_data("iot_speakers")
    print(device_data)

    # TODO: Need to add check for if there are no registered devices to an account, probably when initilazing the querydata
    if device_data is not None:
        timestamp  = device_data["sonos"]["credentials"]["timestamp"]
        timestamp.datetime.strftime("%Y-%m-%d %H:%M:%S")
        if (datetime.now() - datetime_date) > timedelta(hours=4):
        print("It has been more than 4 seconds since the last update")
        print("if clause")
        try:
            access_token = device_data["sonos"]["credentials"]["access_token"]
            refresh_token = device_data["sonos"]["credentials"]["refresh_token"]
            household_id = device_data["sonos"]["data"]["households"][0]["id"]
            group_id = device_data["sonos"]["data"]["groups"][0]["Family Room"]
            player_id = device_data["sonos"]["data"]["players"][0]["Family Room"]
        except KeyError:
            print("No device data found for this account")

    # Successfully fetched data from the device_data table
    print("access_token: " + access_token)
    print("refresh_token: " + refresh_token)
    print("household_id: " + household_id)
    print("group_id: " + group_id)
    print("player_id: " + player_id)

    # Create a SonosClient object
    sonos_client = SonosClient(
        access_token=access_token,
        refresh_token=refresh_token,
        household_id=household_id,
        group_id=group_id,
        player_id=player_id,
    )

    # Perform the action on the Sonos device
    if result.action == "play_music":
        sonos_client.toggle_play_spause()
        answer = "Ég kveikti á tónlist."
    # elif result.action == "increase_volume":
    #     sonos_client.increase_volume()
    # elif result.action == "decrease_volume":
    #     sonos_client.decrease_volume()
    # elif result.action == "set_volume":
    #     sonos_client.set_volume(result.get["volume"])

    answer_list = gen_answer(answer)
    answer_list[1].replace("Sonos", "Sónos")
    q.set_answer(*answer_list)

    # f"var BRIDGE_IP = '192.168.1.68';var USERNAME = 'p3obluiXT13IbHMpp4X63ZvZnpNRdbqqMt723gy2';"
    # except Exception as e:
    #     print(e)
    #     print("Error in sentence")
