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
_BREAK_LENGTH = 5  # Seconds
_BREAK_SSML = '<break time="{0}s"/>'.format(_BREAK_LENGTH)

from typing import Dict, Mapping, Optional, cast
from typing_extensions import TypedDict

import logging
import random
import json
import flask
import requests
import time

from query import Query, QueryStateDict, AnswerTuple
from queries import gen_answer, read_jsfile, read_grammar_file
from tree import Result, Node
from routes import better_jsonify
from util import read_api_key
from speech import text_to_audio_url


class SpeakerCredentials(TypedDict):
    tokens: Dict[str, str]


class DeviceData(TypedDict):
    sonos: SpeakerCredentials


_IoT_QTYPE = "IoTConnect"

TOPIC_LEMMAS = [
    "tengja",
]


def help_text(lemma: str) -> str:
    """Help text to return when query.py is unable to parse a query but
    one of the above lemmas is found in it"""
    return "Ég skil þig ef þú segir til dæmis: {0}.".format(
        random.choice(("Tengu miðstöðina", "Tengdu ljósin" "Tengdu hátalarann"))
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
    | QIoTConnectSpeaker
    | QIoTCreateSpeakerToken
    
QIoTConnectLights →
    "tengdu" "ljósin"

QIoTConnectHub →
    "tengdu" "miðstöðina"

QIoTConnectSpeaker →
    "tengdu" "hátalarann"

QIoTCreateSpeakerToken →
    "skapaðu" "tóka"

"""


def QIoTConnectLights(node: Node, params: QueryStateDict, result: Result) -> None:
    result.qtype = "connect_lights"
    result.action = "connect_lights"


def QIoTConnectHub(node: Node, params: QueryStateDict, result: Result) -> None:
    print("Connect Hub")
    result.qtype = "connect_hub"
    result.action = "connect_hub"


def QIoTConnectSpeaker(node: Node, params: QueryStateDict, result: Result) -> None:
    print("Connect Speaker")
    result.qtype = "connect_speaker"
    result.action = "connect_speaker"


def QIoTCreateSpeakerToken(node: Node, params: QueryStateDict, result: Result) -> None:
    print("Create Token")
    result.qtype = "create_speaker_token"
    result.action = "create_speaker_token"


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
    host = str(flask.request.host)
    client_id = str(q.client_id)

    if result.qtype == "connect_lights":
        js = read_jsfile("IoT_Embla/Philips_Hue/hub.js")
        js += f"syncConnectHub('{client_id}','{host}');"
        answer = "Philips Hue miðstöðin hefur verið tengd"
        voice_answer = answer
        # audioClip(text_to_audio_url(voice_answer))
        response = dict(answer=answer)
        q.set_answer(response, answer, voice_answer)
        q.set_command(js)
        return

    elif result.qtype == "connect_hub":
        js = read_jsfile("IoT_Embla/Smart_Things/st_connecthub.js")
        js += f"syncConnectHub('{client_id}','{host}');"
        answer = "Smart Things miðstöðin hefur verið tengd"
        voice_answer, response = answer, dict(answer=answer)
        q.set_answer(response, answer, voice_answer)
        q.set_command(js)
        return

    elif result.qtype == "connect_speaker":
        sonos_key = read_api_key("SonosKey")
        answer = "Skráðu þig inn hjá Sonos"
        voice_answer, response = answer, dict(answer=answer)
        q.set_answer(response, answer, voice_answer)
        q.set_url(
            f"https://api.sonos.com/login/v3/oauth?client_id={sonos_key}&response_type=code&state={client_id}&scope=playback-control-all&redirect_uri=http://{host}/connect_sonos.api"
        )
        return

    elif result.qtype == "create_speaker_token":
        code = str(q.client_data("sonos_code"))
        sonos_encoded_credentials = read_api_key("SonosEncodedCredentials")
        response = create_token(code, sonos_encoded_credentials, host)
        if response.status_code != 200:
            print("Error:", response.status_code)
            print(response.text)
            print("Invalid request usually means that the code is invalid")
            return
        response_json = response.json()
        access_token, refresh_token = (
            response_json.get("access_token"),
            response_json.get("refresh_token"),
        )
        data_dict = create_sonos_data_dict(access_token, q)
        cred_dict = create_sonos_cred_dict(access_token, refresh_token, q)
        store_sonos_data_and_credentials(data_dict, cred_dict, q)
        answer = "Ég bjó til tóka frá Sónos"
        voice_answer = answer
        # voice_answer = f"Ég ætla að tengja Sónos hátalarann. Hlustaðu vel. {_BREAK_SSML} Ég tengdi Sónos hátalarann. Góða skemmtun."
        # sonos_voice_clip = (
        #     f"{_BREAK_SSML} Hæ!, ég er búin að tengja þennan Sónos hátalara."
        # )
        # audio_clip(
        #     text_to_audio_url(sonos_voice_clip),
        #     sonos_dict["player_id"],
        #     sonos_dict["access_token"],
        # )
        q.set_answer(response, answer, voice_answer)
        return


def create_sonos_data_dict(access_token, q):
    data_dict = {}
    households = get_households(access_token).json()
    data_dict.update(households)
    groups_list = []
    players_list = []
    for i in range(len(households)):
        groups_object = get_groups(
            households["households"][i]["id"], access_token
        ).json()
        groups_raw = groups_object.get("groups")
        players_raw = groups_object.get("players")
        groups_list += create_grouplist_for_db(groups_raw)
        players_list += create_playerlist_for_db(players_raw)

    data_dict["groups"] = groups_list
    data_dict["players"] = players_list
    return data_dict


def create_sonos_cred_dict(access_token, refresh_token, q):
    cred_dict = {}
    cred_dict.update(
        {
            "access_token": access_token,
            "refresh_token": refresh_token,
        }
    )
    return cred_dict


def store_sonos_data_and_credentials(data_dict, cred_dict, q):
    sonos_dict = {}
    sonos_dict["sonos"] = {"credentials": cred_dict, "data": data_dict}
    q.update_client_data("iot_speakers", sonos_dict)


def create_grouplist_for_db(groups):
    groups_list = []
    for i in range(len(groups)):
        groups_list.append({groups[i]["name"]: groups[i]["id"]})
    return groups_list


def create_playerlist_for_db(players):
    player_list = []
    for i in range(len(players)):
        player_list.append({players[i]["name"]: players[i]["id"]})
    return player_list


# put this in a separate file
def get_households(token):
    """
    Returns the list of households of the user
    """
    url = f"https://api.ws.sonos.com/control/api/v1/households"

    payload = {}
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.request("GET", url, headers=headers, data=payload)

    return response


def get_groups(household_id, token):
    """
    Returns the list of groups of the user
    """
    url = f"https://api.ws.sonos.com/control/api/v1/households/{household_id}/groups"

    payload = {}
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.request("GET", url, headers=headers, data=payload)

    return response


def create_token(code, sonos_encoded_credentials, host):
    """
    Creates a token given a code
    """
    url = f"https://api.sonos.com/login/v3/oauth/access?grant_type=authorization_code&code={code}&redirect_uri=http://{host}/connect_sonos.api"

    payload = {}
    headers = {
        "Authorization": f"Basic {sonos_encoded_credentials}",
        "Cookie": "JSESSIONID=F710019AF0A3B7126A8702577C883B5F; AWSELB=69BFEFC914A689BF6DC8E4652748D7B501ED60290D5EA56F2E543ABD7CF357A5F65186AEBCFB059E28075D83A700FD504C030A53CC28683B515BE3DCA3CC587AFAF606E171; AWSELBCORS=69BFEFC914A689BF6DC8E4652748D7B501ED60290D5EA56F2E543ABD7CF357A5F65186AEBCFB059E28075D83A700FD504C030A53CC28683B515BE3DCA3CC587AFAF606E171",
    }

    response = requests.request("POST", url, headers=headers, data=payload)

    return response


def toggle_play_pause(group_id, token):
    """
    Toggles the play/pause of a group
    """
    url = (
        f"https://api.ws.sonos.com/control/api/v1/groups/{group_id}/playback/playPause"
    )

    payload = {}
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}

    response = requests.request("POST", url, headers=headers, data=payload)

    return response


def audio_clip(audioclip_url, player_id, token):
    """
    Plays an audioclip from link to .mp3 file
    """
    import requests
    import json

    url = f"https://api.ws.sonos.com/control/api/v1/players/{player_id}/audioClip"

    payload = json.dumps(
        {
            "name": "Embla",
            "appId": "com.acme.app",
            "streamUrl": f"{audioclip_url}",
            "volume": 50,
            "priority": "HIGH",
            "clipType": "CUSTOM",
        }
    )
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }

    response = requests.request("POST", url, headers=headers, data=payload)
