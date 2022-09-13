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
from typing import Dict
from typing_extensions import TypedDict

import random
import flask

from query import Query, QueryStateDict
from queries import gen_answer, read_jsfile
from queries.sonos import SonosClient
from tree import Result, Node

from util import read_api_key
from speech import text_to_audio_url

_BREAK_LENGTH = 5  # Seconds
_BREAK_SSML = f'<break time="{_BREAK_LENGTH}s"/>'


class SpeakerCredentials(TypedDict):
    tokens: Dict[str, str]


class DeviceData(TypedDict):
    sonos: SpeakerCredentials


TOPIC_LEMMAS = [
    "tengja",
]


def help_text(lemma: str) -> str:
    """Help text to return when query.py is unable to parse a query but
    one of the above lemmas is found in it"""
    return "Ég skil þig ef þú segir til dæmis: {0}.".format(
        random.choice(
            (
                "Tengdu ljósin",
                "Tengdu hátalarann",
            )
        )
    )


# This module wants to handle parse trees for queries
HANDLE_TREE = True

# The grammar nonterminals this module wants to handle
QUERY_NONTERMINALS = {"QIoTConnect"}

# The context-free grammar for the queries recognized by this plug-in module
GRAMMAR = f"""

/þgf = þgf
/ef = ef

Query →
    QIoTConnect '?'?

QIoTConnect → 
    QIoTConnectLights
    | QIoTConnectSpeaker
    | QIoTCreateSpeakerToken
    | QIoTConnectSpotify
    
QIoTConnectLights →
    "tengdu" "ljósin"

QIoTConnectSpeaker →
    "tengdu" "hátalarann"

QIoTCreateSpeakerToken →
    "skapaðu" "tóka"

QIoTConnectSpotify →
    "tengdu" "spotify"

"""


def QIoTConnectLights(node: Node, params: QueryStateDict, result: Result) -> None:
    result.qtype = "connect_lights"
    result.action = "connect_lights"


def QIoTConnectSpeaker(node: Node, params: QueryStateDict, result: Result) -> None:
    print("Connect Speaker")
    result.qtype = "connect_speaker"
    result.action = "connect_speaker"


def QIoTCreateSpeakerToken(node: Node, params: QueryStateDict, result: Result) -> None:
    print("Create Token")
    result.qtype = "create_speaker_token"
    result.action = "create_speaker_token"


def QIoTConnectSpotify(node: Node, params: QueryStateDict, result: Result) -> None:
    print("Connect Spotify")
    result.qtype = "connect_spotify"
    result.action = "connect_spotify"


def sentence(state: QueryStateDict, result: Result) -> None:
    """Called when sentence processing is complete"""
    q: Query = state["query"]
    if "qtype" not in result:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
        return

    q.set_qtype(result.qtype)
    host = str(flask.request.host)
    client_id = str(q.client_id)

    if result.qtype == "connect_lights":
        js = read_jsfile("Philips_Hue/hub.js")
        js += f"return connectHub('{client_id}','{host}');"
        q.set_answer(*gen_answer("Philips Hue miðstöðin hefur verið tengd."))
        q.set_command(js)
        return

    elif result.qtype == "connect_speaker":
        sonos_key = read_api_key("SonosKey")
        q.set_answer(*gen_answer("Skráðu þig inn hjá Sonos"))
        # Redirect the user to a Sonos login screen
        q.set_url(
            f"https://api.sonos.com/login/v3/oauth?client_id={sonos_key}&response_type=code&state={client_id}&scope=playback-control-all&redirect_uri=http://{host}/connect_sonos.api"
        )
        return

    elif result.qtype == "create_speaker_token":
        device_data = q.client_data("iot_speakers")
        try:
            code = device_data.get("sonos").get("credentials").get("code") or None
        except AttributeError:
            print("Missing device data")
        if device_data is None or code is None:
            print("Missing device data or code")
            q.set_error("Missing sonos code")
            return
        sonos_client = SonosClient(device_data, q)
        sonos_client.set_data()
        sonos_client.store_sonos_data_and_credentials()

        answer = "Ég bjó til tóka frá Sónos"
        response = dict(answer=answer)
        voice_answer = f"Ég ætla að tengja Sónos hátalarann. Hlustaðu vel. {_BREAK_SSML} Ég tengdi Sónos hátalarann. Góða skemmtun."
        sonos_voice_clip = (
            f"{_BREAK_SSML} Hæ!, ég er búin að tengja þennan Sónos hátalara."
        )
        sonos_client.audio_clip(text_to_audio_url(sonos_voice_clip))
        q.set_answer(response, answer, voice_answer)
        return

    elif result.qtype == "connect_spotify":
        spotify_key = read_api_key("SpotifyKey")
        q.set_answer(*gen_answer("Skráðu þig inn hjá Spotify"))
        q.set_url(
            f"https://accounts.spotify.com/authorize?client_id={spotify_key}&response_type=code&redirect_uri=http://{host}/connect_spotify.api&state={client_id}&scope=user-read-playback-state+user-modify-playback-state+user-read-playback-position+user-read-recently-played+app-remote-control+user-top-read+user-read-currently-playing+playlist-read-private+streaming"
        )
        return
