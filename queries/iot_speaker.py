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
from typing import Dict, cast

import logging
import random

from query import Query, QueryStateDict
from queries import read_grammar_file
from queries.extras.sonos import SonosClient, SonosDeviceData
from tree import ParamList, Result, Node

# Dictionary of radio stations and their stream urls
_RADIO_STREAMS: Dict[str, str] = {
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


_SPEAKER_QTYPE = "IoTSpeakers"

TOPIC_LEMMAS = [
    "tónlist",
    "spila",
    "útvarp",
    "útvarpsstöð",
]


def help_text(lemma: str) -> str:
    """Help text to return when query.py is unable to parse a query but
    one of the above lemmas is found in it"""
    return "Ég skil þig ef þú segir til dæmis: {0}.".format(
        random.choice(
            (
                "Hækkaðu í tónlistinni",
                "Kveiktu á tónlist",
            )
        )
    )


# This module wants to handle parse trees for queries
HANDLE_TREE = True

# The grammar nonterminals this module wants to handle
QUERY_NONTERMINALS = {"QIoTSpeaker", "QIoTSpeakerQuery"}

# The context-free grammar for the queries recognized by this plug-in module
GRAMMAR = read_grammar_file("iot_speaker")


def QIoTSpeaker(node: Node, params: ParamList, result: Result) -> None:
    result.qtype = _SPEAKER_QTYPE


def QIoTSpeakerTurnOnVerb(node: Node, params: ParamList, result: Result) -> None:
    result.qkey = "turn_on"


def QIoTSpeakerTurnOffVerb(node: Node, params: ParamList, result: Result) -> None:
    result.qkey = "turn_off"


def QIoTSpeakerPlayVerb(node: Node, params: ParamList, result: Result) -> None:
    result.qkey = "turn_on"


def QIoTSpeakerPauseVerb(node: Node, params: ParamList, result: Result) -> None:
    result.qkey = "turn_off"


def QIoTSpeakerSkipVerb(node: Node, params: ParamList, result: Result) -> None:
    result.qkey = "next_song"


def QIoTSpeakerNewPlay(node: Node, params: ParamList, result: Result) -> None:
    result.qkey = "turn_on"


def QIoTSpeakerNewPause(node: Node, params: ParamList, result: Result) -> None:
    result.qkey = "turn_off"


def QIoTSpeakerNewNext(node: Node, params: ParamList, result: Result) -> None:
    result.qkey = "next_song"


def QIoTSpeakerNewPrevious(node: Node, params: ParamList, result: Result) -> None:
    result.qkey = "prev_song"


def QIoTSpeakerIncreaseVerb(node: Node, params: ParamList, result: Result) -> None:
    result.qkey = "increase_volume"


def QIoTSpeakerDecreaseVerb(node: Node, params: ParamList, result: Result) -> None:
    result.qkey = "decrease_volume"


def QIoTSpeakerMoreOrHigher(node: Node, params: ParamList, result: Result) -> None:
    result.qkey = "increase_volume"


def QIoTSpeakerLessOrLower(node: Node, params: ParamList, result: Result) -> None:
    result.qkey = "decrease_volume"


def QIoTSpeakerMusicWord(node: Node, params: ParamList, result: Result) -> None:
    result.target = "music"


def QIoTSpeakerSpeakerWord(node: Node, params: ParamList, result: Result) -> None:
    result.target = "speaker"


def QIoTSpeakerRadioWord(node: Node, params: ParamList, result: Result) -> None:
    result.target = "radio"


def QIoTSpeakerGroupName(node: Node, params: ParamList, result: Result) -> None:
    result.group_name = result._indefinite


def QIoTSpeakerRas1(node: Node, params: ParamList, result: Result) -> None:
    result.target = "radio"
    result.station = "Rás 1"


def QIoTSpeakerRas2(node: Node, params: ParamList, result: Result) -> None:
    result.target = "radio"
    result.station = "Rás 2"


def QIoTSpeakerRondo(node: Node, params: ParamList, result: Result) -> None:
    result.target = "radio"
    result.station = "Rondó"


def QIoTSpeakerBylgjan(node: Node, params: ParamList, result: Result) -> None:
    result.target = "radio"
    result.station = "Bylgjan"


def QIoTSpeakerFm957(node: Node, params: ParamList, result: Result) -> None:
    result.target = "radio"
    result.station = "FM957"


def QIoTSpeakerUtvarpSaga(node: Node, params: ParamList, result: Result) -> None:
    result.target = "radio"
    result.station = "Útvarp Saga"


def QIoTSpeakerGullbylgjan(node: Node, params: ParamList, result: Result) -> None:
    result.target = "radio"
    result.station = "Gullbylgjan"


def QIoTSpeakerLettbylgjan(node: Node, params: ParamList, result: Result) -> None:
    result.target = "radio"
    result.station = "Léttbylgjan"


def QIoTSpeakerXid(node: Node, params: ParamList, result: Result) -> None:
    result.target = "radio"
    result.station = "X977"


def QIoTSpeakerKissfm(node: Node, params: ParamList, result: Result) -> None:
    result.target = "radio"
    result.station = "KissFM"


def QIoTSpeakerFlassback(node: Node, params: ParamList, result: Result) -> None:
    result.target = "radio"
    result.station = "Flashback"


def QIoTSpeakerRetro(node: Node, params: ParamList, result: Result) -> None:
    result.target = "radio"
    result.station = "Retro"


def QIoTSpeakerUtvarp101(node: Node, params: ParamList, result: Result) -> None:
    result.target = "radio"
    result.station = "Útvarp 101"


def QIoTSpeakerK100(node: Node, params: ParamList, result: Result) -> None:
    result.target = "radio"
    result.station = "K100"


def QIoTSpeakerIslenskaBylgjan(node: Node, params: ParamList, result: Result) -> None:
    result.target = "radio"
    result.station = "Íslenska Bylgjan"


def QIoTSpeaker80sBylgjan(node: Node, params: ParamList, result: Result) -> None:
    result.target = "radio"
    result.station = "80s Bylgjan"


def QIoTSpeakerApparatid(node: Node, params: ParamList, result: Result) -> None:
    result.target = "radio"
    result.station = "Apparatið"


def QIoTSpeakerFmExtra(node: Node, params: ParamList, result: Result) -> None:
    result.target = "radio"
    result.station = "FM Extra"


def QIoTSpeaker70sFlashback(node: Node, params: ParamList, result: Result) -> None:
    result.target = "radio"
    result.station = "70s Flashback"


def QIoTSpeaker80sFlashback(node: Node, params: ParamList, result: Result) -> None:
    result.target = "radio"
    result.station = "80s Flashback"


def QIoTSpeaker90sFlashback(node: Node, params: ParamList, result: Result) -> None:
    result.target = "radio"
    result.station = "90s Flashback"


def QIoTSpeakerUtvarpSudurland(node: Node, params: ParamList, result: Result) -> None:
    result.target = "radio"
    result.station = "Útvarp Suðurland"


def sentence(state: QueryStateDict, result: Result) -> None:
    """Called when sentence processing is complete"""
    q: Query = state["query"]

    if result.get("qtype") != _SPEAKER_QTYPE or not q.client_id:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
        return

    if "qkey" not in result:
        result.qkey = "turn_on"

    qk: str = result.qkey
    if qk == "turn_on" and result.get("target") == "radio":
        qk = "radio"

    try:
        q.set_qtype(result.qtype)
        cd = q.client_data("iot")
        device_data = None
        if cd:
            device_data = cd.get("iot_speakers")
        if device_data is not None:
            sonos_client = SonosClient(
                cast(SonosDeviceData, device_data),
                q.client_id,
                group_name=result.get("group_name"),
            )

            answer: str
            if qk == "turn_on":
                sonos_client.toggle_play()
                answer = "Ég kveikti á tónlistinni"
            elif qk == "turn_off":
                sonos_client.toggle_pause()
                answer = "Ég slökkti á tónlistinni"
            elif qk == "increase_volume":
                sonos_client.increase_volume()
                answer = "Ég hækkaði í tónlistinni"
            elif qk == "decrease_volume":
                sonos_client.decrease_volume()
                answer = "Ég lækkaði í tónlistinni"
            elif qk == "radio":
                # TODO: Error checking
                station = result.get("station")
                radio_url = _RADIO_STREAMS[station]
                sonos_client.play_radio_stream(radio_url)
                answer = "Ég setti á útvarpstöðina"
            elif qk == "next_song":
                sonos_client.next_song()
                answer = "Ég skipti í næsta lag"
            elif qk == "prev_song":
                sonos_client.prev_song()
                answer = "Ég skipti í fyrra lag"
            else:
                logging.warning("Incorrect qkey in speaker module")
                return

            q.set_answer(
                dict(answer=answer),
                answer,
                answer.replace("Sonos", "Sónos"),
            )
            return
    except Exception as e:
        logging.warning("Exception answering iot_speakers query: {0}".format(e))
        q.set_error("E_EXCEPTION: {0}".format(e))
        return

    # TODO: Need to add check for if there are no registered devices to an account, probably when initilazing the querydata
