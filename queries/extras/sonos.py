"""

    Greynir: Natural language processing for Icelandic

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


    Class which encapsulates communication with the Sonos API.

"""
from typing import Dict, Optional, Union, List, Any

import logging
import json
import flask
import requests
from datetime import datetime, timedelta

from util import read_api_key
from queries import query_json_api
from query import Query


def post_to_json_api(
    url: str,
    *,
    form_data: Optional[Any] = None,
    json_data: Optional[Any] = None,
    headers: Optional[Dict[str, str]] = None,
) -> Union[None, List[Any], Dict[str, Any]]:
    """Send a POST request to the URL, expecting a JSON response which is
    parsed and returned as a Python data structure."""

    # Send request
    try:
        r = requests.post(url, data=form_data, json=json_data, headers=headers)
    except Exception as e:
        logging.warning(str(e))
        return None

    # Verify that status is OK
    if r.status_code not in range(200, 300):
        logging.warning("Received status {0} from API server".format(r.status_code))
        return None

    # Parse json API response
    try:
        res = json.loads(r.text)
        return res
    except Exception as e:
        logging.warning("Error parsing JSON API response: {0}".format(e))
    return None
_GROUPS_DICT = {
    "fjölskylduherbergi": "Family Room",
    "fjölskyldu herbergi": "Family Room",
    "stofa": "Living Room",
    "eldhús": "Kitchen",
    "bað": "Bathroom",
    "klósett": "Bathroom",
    "svefnherbergi": "Bedroom",
    "svefn herbergi": "Bedroom",
    "herbergi": "Bedroom",
    "skrifstofa": "Office",
    "bílskúr": "Garage",
    "skúr": "Garage",
    "garður": "Garden",
    "gangur": "hallway",
    "borðstofa": "Dining Room",
    "gestasvefnherbergi": "Guest Room",
    "gesta svefnherbergi": "Guest Room",
    "gestaherbergi": "Guest Room",
    "gesta herbergi": "Guest Room",
    "leikherbergi": "Playroom",
    "leik herbergi": "Playroom",
    "sundlaug": "Pool",
    "laug": "Pool",
    "sjónvarpsherbergi": "TV Room",
    "sjóvarps herbergi": "TV Room",
    "ferðahátalari": "Portable",
    "ferða hátalari": "Portable",
    "verönd": "Patio",
    "pallur": "Patio",
    "altan": "Patio",
    "sjónvarpsherbergi": "Media Room",
    "sjónvarps herbergi": "Media Room",
    "hjónaherbergi": "Main Bedroom",
    "hjóna herbergi": "Main Bedroom",
    "anddyri": "Foyer",
    "forstofa": "Foyer",
    "inngangur": "Foyer",
    "húsbóndaherbergi": "Den",
    "húsbónda herbergi": "Den",
    "hosiló": "Den",
    "bókasafn": "Library",
    "bókaherbergi": "Library",
    "bóka herbergi": "Library",
}


# TODO - Decide what should happen if user does not designate a speaker but owns multiple speakers
# TODO - Remove debug print statements
# TODO - Testing and proper error handling
# TODO - Implement a cleaner create_or_join_session function that doesn't rely on recursion
class SonosClient:
    def __init__(
        self,
        device_data: Dict[str, str],
        client_id: str,
        group_name: str = None,
        radio_name: str = None,
    ):
        self._client_id = client_id
        self._device_data = device_data
        self._group_name = group_name
        self._radio_name = radio_name
        self._encoded_credentials = read_api_key("SonosEncodedCredentials")
        self._code = self._device_data["sonos"]["credentials"]["code"]
        print("code :", self._code)
        self._timestamp = (
            self._device_data.get("sonos").get("credentials").get("timestamp")
        )
        print("device data :", self._device_data)
        try:
            print("Trying to get access token")
            self._access_token = self._device_data["sonos"]["credentials"][
                "access_token"
            ]
            print("access token :", self._access_token)
            self._refresh_token = self._device_data["sonos"]["credentials"][
                "refresh_token"
            ]
            print("refresh token :", self._refresh_token)
        except (KeyError, TypeError):
            print("No access token found for Sonos.")
            self._create_token()
        self._check_token_expiration()
        self._households = self._get_households()
        self._household_id = self._households[0]["id"]
        self._groups = self._get_groups()
        self._players = self._get_players()
        self._group_id = self._get_group_id()
        self._store_data_and_credentials()

    """
    ------------------------------------- PRIVATE METHODS --------------------------------------------------------------------------------
    """

    def _check_token_expiration(self) -> None:
        """
        Checks if access token is expired, and calls a function to refresh it if necessary.
        """
        try:
            timestamp = self._device_data["sonos"]["credentials"]["timestamp"]
        except (KeyError, TypeError):
            print("No timestamp found for Sonos token.")
            return
        timestamp = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S.%f")
        if (datetime.now() - timestamp) > timedelta(hours=24):
            self._update_sonos_token()

    def _update_sonos_token(self) -> None:
        """
        Updates the access token
        """
        print("update sonos token")
        self._encoded_credentials = read_api_key("SonosEncodedCredentials")
        self._refresh_expired_token()
        sonos_dict = {
            "sonos": {
                "credentials": {
                    "access_token": self._access_token,
                    "timestamp": self._timestamp,
                }
            }
        }

        self._store_data(sonos_dict)

    def _refresh_expired_token(self) -> Union[None, List[Any], Dict[str, Any]]:
        """
        Helper function for updating the access token.
        """
        print("_refresh_expired_token")
        url = f"https://api.sonos.com/login/v3/oauth/access?grant_type=refresh_token&refresh_token={self._refresh_token}"
        headers = {"Authorization": f"Basic {self._encoded_credentials}"}

        response = post_to_json_api(url, headers=headers)

        self._access_token = response["access_token"]
        self._timestamp = str(datetime.now())

        return response

    def _create_token(self) -> Union[None, List[Any], Dict[str, Any]]:
        """
        Creates a token given a code
        """
        print("_create_token")
        host = str(flask.request.host)
        url = f"https://api.sonos.com/login/v3/oauth/access?grant_type=authorization_code&code={self._code}&redirect_uri=http://{host}/connect_sonos.api"
        headers = {
            "Authorization": f"Basic {self._encoded_credentials}",
        }

        response = post_to_json_api(url, headers=headers)
        print("Reponse :", response)
        self._access_token = response.get("access_token")
        print("access token :", self._access_token)
        self._refresh_token = response.get("refresh_token")
        self._timestamp = str(datetime.now())
        return response

    def _get_households(self) -> Dict[str, str]:
        """
        Returns the list of households of the user
        """
        print("get households")
        url = f"https://api.ws.sonos.com/control/api/v1/households"
        headers = {"Authorization": f"Bearer {self._access_token}"}

        response = query_json_api(url, headers=headers)
        return response["households"]

    def _get_household_id(self) -> str:
        """
        Returns the household id for the given query
        """
        print("get household id")
        url = f"https://api.ws.sonos.com/control/api/v1/households"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._access_token}",
        }

        response = query_json_api(url, headers)
        return response["households"][0]["id"]

    def _get_groups(self) -> Dict[str, str]:
        """
        Returns the list of groups of the user
        """
        print("get groups")
        for i in range(len(self._households)):
            url = f"https://api.ws.sonos.com/control/api/v1/households/{self._household_id}/groups"
            headers = {"Authorization": f"Bearer {self._access_token}"}

            response = query_json_api(url, headers=headers)
            cleaned_groups_dict = self._create_groupdict_for_db(response["groups"])
        return cleaned_groups_dict

    def _get_group_id(self) -> str:
        """
        Returns the group id for the given query
        """
        print("get group_id")
        try:
            if self._group_name is not None:
                print("GROUP NAME NOT NONE")
                translated_group_name = self._translate_group_name()
                print("Self groups :", self._groups)
                print("GROUP NAME :", self._group_name)
                print("GROUPS NAME :", self._group_name)
                group_id = self._groups.get(translated_group_name.casefold())
                print("GROUP ID :", group_id)
                return group_id
            else:
                print("GROUP NAME IS NONE")
                if len(self._groups) == 1:
                    print("LEN 1")
                    group_name = iter(self._groups[0])
                    return self._groups[0][group_name]
        except (KeyError, TypeError):
            print("GROUP EXCEPT")
            url = f"https://api.ws.sonos.com/control/api/v1/households/{self._household_id}/groups"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._access_token}",
            }

            response = query_json_api(url, headers)
            return response["groups"][0]["id"]

    def _translate_group_name(self) -> str:
        """
        Translates the group name to the correct group name
        """
        print("Translate group name")
        try:
            english_group_name = _GROUPS_DICT[self._group_name]
            print("TRANSLATED GROUP NAME :", english_group_name)
            return english_group_name
        except (KeyError, TypeError):
            return self._group_name

    def _get_players(self) -> Dict[str, str]:
        """
        Returns the list of groups of the user
        """
        print("get players")
        for i in range(len(self._households)):
            url = f"https://api.ws.sonos.com/control/api/v1/households/{self._household_id}/groups"
            headers = {"Authorization": f"Bearer {self._access_token}"}

            response = query_json_api(url, headers)
            cleaned_players_dict = self._create_playerdict_for_db(response["players"])
            return cleaned_players_dict

    def _get_player_id(self) -> str:
        """
        Returns the player id for the given query
        """
        print("get player_id")
        try:
            player_id = self._players[0]["id"]
            return player_id
        except (KeyError, TypeError):
            url = f"https://api.ws.sonos.com/control/api/v1/households/{self._household_id}/groups"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._access_token}",
            }

            response = query_json_api(url, headers)

            return response["players"][0]["id"]

    def _create_data_dict(self) -> Dict[str, str]:
        print("_create_data_dict")
        data_dict = {"households": self._households}
        for i in range(len(self._households)):
            groups_dict = self._groups
            players_dict = self._players

        data_dict["groups"] = groups_dict
        data_dict["players"] = players_dict
        return data_dict

    def _create_cred_dict(self) -> Dict[str, str]:
        print("_create_cred_dict")
        cred_dict = {}
        cred_dict.update(
            {
                "access_token": self._access_token,
                "refresh_token": self._refresh_token,
                "timestamp": self._timestamp,
            }
        )
        return cred_dict

    def _store_data_and_credentials(self) -> None:
        print("_store_data_and_credentials")
        cred_dict = self._create_cred_dict()
        sonos_dict = {}
        sonos_dict["sonos"] = {"credentials": cred_dict}
        self._store_data(sonos_dict)

    def _store_data(self, data: Dict) -> None:
        new_dict = {"iot_speakers": data}
        Query.store_query_data(self._client_id, "iot", new_dict, update_in_place=True)

    def _create_groupdict_for_db(self, groups: list) -> Dict[str, str]:
        print("create_groupdict_for_db")
        groups_dict = {}
        for i in range(len(groups)):
            groups_dict[groups[i]["name"].casefold()] = groups[i]["id"]
        return groups_dict

    def _create_playerdict_for_db(self, players: list) -> Dict[str, str]:
        print("create_playerdict_for_db")
        players_dict = {}
        for i in range(len(players)):
            players_dict[players[i]["name"]] = players[i]["id"]
        return players_dict

    def _create_or_join_session(self, recursion=None) -> Optional[str]:
        print("_create_or_join_session")
        url = f"https://api.ws.sonos.com/control/api/v1/groups/{self._group_id}/playbackSession/joinOrCreate"

        payload = json.dumps({"appId": "com.mideind.embla", "appContext": "embla123"})
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._access_token}",
        }

        response = post_to_json_api(url, form_data=payload, headers=headers)
        print(response)
        if response is None:
            self.toggle_pause()
            if recursion is None:
                response = self._create_or_join_session(recursion=True)
            else:
                return None
            print("response was none , so we created a new session")
            session_id = response

        else:
            session_id = response["sessionId"]
        print("response after loop:", response)
        print("session_id :", session_id)
        return session_id

    """
    ------------------------------------- PUBLIC METHODS --------------------------------------------------------------------------------
    """

    def play_radio_stream(self, radio_url: str) -> Optional[str]:
        print("play radio stream")
        session_id = self._create_or_join_session()
        print("exited create or join session")
        if radio_url is None:
            try:
                radio_url = self._device_data["sonos"]["data"]["last_radio_url"]
            except KeyError:
                radio_url = "http://netradio.ruv.is/rondo.mp3"

        url = f"https://api.ws.sonos.com/control/api/v1//playbackSessions/{session_id}/playbackSession/loadStreamUrl?"
        print("RADIO URL :", radio_url)
        payload = json.dumps(
            {
                "streamUrl": f"{radio_url}",
                "playOnCompletion": True,
                # "stationMetadata": {"name": f"{radio_name}"},
                "itemId": "StreamItemId",
            }
        )
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._access_token}",
        }

        response = post_to_json_api(url, form_data=payload, headers=headers)
        if response is None:
            return "Group not found"
        data_dict = {"sonos": {"data": {"last_radio_url": radio_url}}}
        self._store_data(data_dict)
        print(response.get("text"))

    def increase_volume(self) -> None:
        print("increase_volume")
        url = f"https://api.ws.sonos.com/control/api/v1/groups/{self._group_id}/groupVolume/relative"

        payload = json.dumps({"volumeDelta": 10})
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._access_token}",
        }

        response = post_to_json_api(url, form_data=payload, headers=headers)
        if response is None:
            self._refresh_data("increase_volume")
        print(response.get("text"))

    def decrease_volume(self) -> None:
        print("decrease volume")
        group_id = self._get_group_id()
        url = f"https://api.ws.sonos.com/control/api/v1/groups/{group_id}/groupVolume/relative"

        payload = json.dumps({"volumeDelta": -10})
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._access_token}",
        }

        response = post_to_json_api(url, form_data=payload, headers=headers)
        if response is None:
            return "Group not found"
        print(response.get("text"))

    def toggle_play(self) -> Union[None, List[Any], Dict[str, Any]]:
        """
        Toggles play/pause of a group
        """
        print("toggle playpause")
        print("exited group_id")
        url = f"https://api.ws.sonos.com/control/api/v1/groups/{self._group_id}/playback/play"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._access_token}",
        }

        response = post_to_json_api(url, headers=headers)
        print("response :", response)
        if response is None:
            return "Group not found"

        return response

    def toggle_pause(self) -> Union[None, List[Any], Dict[str, Any]]:
        """
        Toggles play/pause of a group
        """
        print("toggle playpause")
        # group_id = self._get_group_id()
        print("exited group_id")
        url = f"https://api.ws.sonos.com/control/api/v1/groups/{self._group_id}/playback/pause"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._access_token}",
        }

        # response = requests.request("POST", url, headers=headers, data=payload)
        response = post_to_json_api(url, headers=headers)
        print("response :", response)
        if response is None:
            return "Group not found"

        return response

    def play_audio_clip(
        self, audioclip_url: str
    ) -> Union[None, List[Any], Dict[str, Any]]:
        """
        Plays an audioclip from link to .mp3 file
        """
        print("play_audio_clip")
        player_id = self._get_player_id()
        url = f"https://api.ws.sonos.com/control/api/v1/players/{player_id}/audioClip"

        payload = json.dumps(
            {
                "name": "Embla",
                "appId": "com.acme.app",
                "streamUrl": f"{audioclip_url}",
                "volume": 30,
                "priority": "HIGH",
                "clipType": "CUSTOM",
            }
        )
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._access_token}",
        }

        response = post_to_json_api(url, form_data=payload, headers=headers)
        if response is None:
            return "Group not found"
        return response

    def play_chime(self) -> Union[None, List[Any], Dict[str, Any]]:
        player_id = self._get_player_id()
        url = f"https://api.ws.sonos.com/control/api/v1/players/{player_id}/audioClip"

        payload = json.dumps(
            {
                "name": "Embla",
                "appId": "com.acme.app",
                "volume": 30,
                "priority": "HIGH",
                "clipType": "CHIME",
            }
        )
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._access_token}",
        }

        response = post_to_json_api(url, form_data=payload, headers=headers)

        return response

    def next_song(self) -> Union[None, List[Any], Dict[str, Any]]:
        url = f"https://api.ws.sonos.com/control/api/v1/groups/{self._group_id}/playback/skipToNextTrack"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._access_token}",
        }

        response = post_to_json_api(url, headers=headers)

        return response

    def prev_song(self) -> Union[None, List[Any], Dict[str, Any]]:
        url = f"https://api.ws.sonos.com/control/api/v1/groups/{self._group_id}/playback/skipToPreviousTrack"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._access_token}",
        }

        response = post_to_json_api(url, headers=headers)

        return response
