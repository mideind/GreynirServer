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
# Dictionary of radio stations and their stream urls
_RADIO_STREAMS = {
    "Rás 1": "http://netradio.ruv.is/ras1.mp3",
    "Rás 2": "http://netradio.ruv.is/ras2.mp3",
    "Rondó": "http://netradio.ruv.is/rondo.mp3",
    "Bylgjan": "https://live.visir.is/hls-radio/bylgjan/playlist.m3u8",
    "Léttbylgjan": "https://live.visir.is/hls-radio/lettbylgjan/playlist.m3u8",
    "Gullbylgjan": "https://live.visir.is/hls-radio/gullbylgjan/playlist.m3u8",
    "80s Bylgjan": "https://live.visir.is/hls-radio/80s/chunklist_DVR.m3u8",
    "Íslenska Bylgjan": "https://live.visir.is/hls-radio/islenska/chunklist_DVR.m3u8",
    "FM957": "https://live.visir.is/hls-radio/fm957/playlist.m3u8",
    "Útvarp Saga": "https://stream.utvarpsaga.is/Hljodver",
    "K100": "https://k100streymi.mbl.is/beint/k100/tracks-v1a1/rewind-3600.m3u8",
    "X977": "https://live.visir.is/hls-radio/x977/playlist.m3u8",
    "Retro": "https://k100straumar.mbl.is/retromobile",
    "KissFM": "http://stream3.radio.is:443/kissfm",
    "Útvarp 101": "https://stream.101.live/audio/101/chunklist.m3u8",
    "Apparatið": "https://live.visir.is/hls-radio/apparatid/chunklist_DVR.m3u8",
    "FM Extra": "https://live.visir.is/hls-radio/fmextra/chunklist_DVR.m3u8",
    "Útvarp Suðurland": "http://ice-11.spilarinn.is/tsudurlandfm",
    "Flashback": "http://stream.radio.is:443/flashback",
    "70s Flashback": "http://stream3.radio.is:443/70flashback",
    "80s Flashback": "http://stream3.radio.is:443/80flashback",
    "90s Flashback": "http://stream3.radio.is:443/90flashback",
}


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


_IoT_QTYPE = "IoTSpeakers"

TOPIC_LEMMAS = [
    "tónlist",
    "spila",
]


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
QUERY_NONTERMINALS = {"QIoTSpeaker", "QIoTSpeakerQuery"}

# The context-free grammar for the queries recognized by this plug-in module

GRAMMAR = read_grammar_file(
    "iot_speakers",
)


def QIoTSpeaker(node: Node, params: QueryStateDict, result: Result) -> None:
    print("QTYPE")
    result.qtype = _IoT_QTYPE


def QIoTSpeakerIncreaseVerb(node: Node, params: QueryStateDict, result: Result) -> None:
    result["qkey"] = "increase_volume"


def QIoTSpeakerDecreaseVerb(node: Node, params: QueryStateDict, result: Result) -> None:
    result["qkey"] = "decrease_volume"


def QIoTSpeakerGroupName(node: Node, params: QueryStateDict, result: Result) -> None:
    result["group_name"] = result._indefinite


def QIoTMusicWord(node: Node, params: QueryStateDict, result: Result) -> None:
    result.target = "music"
    print("music")


def QIoTSpeakerTurnOnVerb(node: Node, params: QueryStateDict, result: Result) -> None:
    result["qkey"] = "play_music"


def QIoTSpeakerPauseVerb(node: Node, params: QueryStateDict, result: Result) -> None:
    print("PAUSE")
    result["qkey"] = "pause_music"


def QIoTSpeakerPlayVerb(node: Node, params: QueryStateDict, result: Result) -> None:
    result["qkey"] = "play_music"


def QIoTSpeakerRas1(node: Node, params: QueryStateDict, result: Result) -> None:
    result["qkey"] = "radio"
    result["station"] = "Rás 1"


def QIoTSpeakerRas2(node: Node, params: QueryStateDict, result: Result) -> None:
    result["qkey"] = "radio"
    result["station"] = "Rás 2"


def QIoTSpeakerRondo(node: Node, params: QueryStateDict, result: Result) -> None:
    result["qkey"] = "radio"
    result["station"] = "Rondó"


def QIoTSpeakerBylgjan(node: Node, params: QueryStateDict, result: Result) -> None:
    result["qkey"] = "radio"
    result["station"] = "Bylgjan"


def QIoTSpeakerFm957(node: Node, params: QueryStateDict, result: Result) -> None:
    result["qkey"] = "radio"
    result["station"] = "FM957"


def QIoTSpeakerUtvarpSaga(node: Node, params: QueryStateDict, result: Result) -> None:
    result["qkey"] = "radio"
    result["station"] = "Útvarp Saga"


def QIoTSpeakerGullbylgjan(node: Node, params: QueryStateDict, result: Result) -> None:
    result["qkey"] = "radio"
    result["station"] = "Gullbylgjan"


def QIoTSpeakerLettbylgjan(node: Node, params: QueryStateDict, result: Result) -> None:
    result["qkey"] = "radio"
    result["station"] = "Léttbylgjan"


def QIoTSpeakerXid(node: Node, params: QueryStateDict, result: Result) -> None:
    result["qkey"] = "radio"
    result["station"] = "X977"


def QIoTSpeakerKissfm(node: Node, params: QueryStateDict, result: Result) -> None:
    result["qkey"] = "radio"
    result["station"] = "KissFM"


def QIoTSpeakerFlassback(node: Node, params: QueryStateDict, result: Result) -> None:
    result["qkey"] = "radio"
    result["station"] = "Flashback"


def QIoTSpeakerRetro(node: Node, params: QueryStateDict, result: Result) -> None:
    result["qkey"] = "radio"
    result["station"] = "Retro"


def QIoTSpeakerUtvarp101(node: Node, params: QueryStateDict, result: Result) -> None:
    result["qkey"] = "radio"
    result["station"] = "Útvarp 101"


def QIoTSpeakerK100(node: Node, params: QueryStateDict, result: Result) -> None:
    result["qkey"] = "radio"
    result["station"] = "K100"


def QIoTSpeakerIslenskaBylgjan(
    node: Node, params: QueryStateDict, result: Result
) -> None:
    result["qkey"] = "radio"
    result["station"] = "Íslenska Bylgjan"


def QIoT80sBylgjan(node: Node, params: QueryStateDict, result: Result) -> None:
    result["qkey"] = "radio"
    result["station"] = "80s Bylgjan"


def QIoTSpeakerApparatid(node: Node, params: QueryStateDict, result: Result) -> None:
    result["qkey"] = "radio"
    result["station"] = "Apparatið"


def QIoTSpeakerFmExtra(node: Node, params: QueryStateDict, result: Result) -> None:
    result["qkey"] = "radio"
    result["station"] = "FM Extra"


def QIoTSpeaker70sFlashback(node: Node, params: QueryStateDict, result: Result) -> None:
    result["qkey"] = "radio"
    result["station"] = "70s Flashback"


def QIoTSpeaker80sFlashback(node: Node, params: QueryStateDict, result: Result) -> None:
    result["qkey"] = "radio"
    result["station"] = "80s Flashback"


def QIoTSpeaker90sFlashback(node: Node, params: QueryStateDict, result: Result) -> None:
    result["qkey"] = "radio"
    result["station"] = "90s Flashback"


def QIoTSpeakerUtvarpSudurland(
    node: Node, params: QueryStateDict, result: Result
) -> None:
    result["qkey"] = "radio"
    result["station"] = "Útvarp Suðurland"


def QIoTSpeakerGroupName(node: Node, params: QueryStateDict, result: Result) -> None:
    result["group_name"] = result._indefinite


def call_sonos_client(sonos_client, result):
    """Call the appropriate function in the SonosClient based on the result"""
    handler_func = _HANDLER_MAP[result.qkey][0]
    if result.get("station") is not None:
        radio_url = _RADIO_STREAMS.get(f"{result.station}")
        response = getattr(sonos_client, handler_func)(radio_url)
        return response
    else:
        response = getattr(sonos_client, handler_func)()
        return response
    return


# Map of query keys to handler functions and the corresponding answer string for Embla
_HANDLER_MAP = {
    "play_music": ["toggle_play", "Ég kveikti á tónlist"],
    "pause_music": ["toggle_pause", "Ég slökkti á tónlist"],
    "increase_volume": ["increase_volume", "Ég hækkaði í tónlistinni"],
    "decrease_volume": ["decrease_volume", "Ég lækkaði í tónlistinni"],
    "radio": ["play_radio_stream", "Ég setti á útvarpstöðina"],
}


def sentence(state: QueryStateDict, result: Result) -> None:
    """Called when sentence processing is complete"""
    print("sentence")
    q: Query = state["query"]
    if "qtype" in result and "qkey" in result:
        print("IF QTYPE AND QKEY")
        try:
            q.set_qtype(result.qtype)
            device_data = q.client_data("iot_speakers")
            if device_data is not None:
                print("JUST BEFORE SONOS CLIENT")
                sonos_client = SonosClient(
                    device_data, q.client_id, group_name=result.get("group_name")
                )
                print("JUST AFTER SONOS CLIENT")
                response = call_sonos_client(sonos_client, result)
                if response == "Group not found":
                    text_ans = f"Herbergið '{result.group_name}' fannst ekki. Vinsamlegast athugaðu í Sonos appinu hvort nafnið sé rétt."
                else:
                    handler_answer = _HANDLER_MAP[result.qkey][1]
                    text_ans = handler_answer

                answer = (
                    dict(answer=text_ans),
                    text_ans,
                    text_ans.replace("Sonos", "Sónos"),
                )
                q.set_answer(*answer)
                return
            else:
                print("No device data found for this account")
                return
        except Exception as e:
            logging.warning("Exception answering iot_speakers query: {0}".format(e))
            q.set_error("E_EXCEPTION: {0}".format(e))
            return
    else:
        print("ELSE")
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
        return

    # # TODO: Need to add check for if there are no registered devices to an account, probably when initilazing the querydata
