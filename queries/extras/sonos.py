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
from typing_extensions import TypedDict
import flask
import requests
from datetime import datetime, timedelta

from utility import read_api_key
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


# Translate various icelandic room names to
# preset room names available in the Sonos app
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
    "gangur": "Hallway",
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


class _Creds(TypedDict):
    code: str
    timestamp: str
    access_token: str
    refresh_token: str


class _SonosSpeakerData(TypedDict):
    credentials: _Creds


class SonosDeviceData(TypedDict):
    sonos: _SonosSpeakerData


_OAUTH_ACCESS_ENDPOINT = "https://api.sonos.com/login/v3/oauth/access"
_API_ENDPOINT = "https://api.ws.sonos.com/control/api/v1"
_HOUSEHOLDS_ENDPOINT = f"{_API_ENDPOINT}/households"
_GROUP_ENDPOINT = f"{_API_ENDPOINT}/groups"
_PLAYER_ENDPOINT = f"{_API_ENDPOINT}/players"
_PLAYBACKSESSIONS_ENDPOINT = f"{_API_ENDPOINT}/playbackSessions"
_VOLUME_INCREMENT = 20

# TODO - Decide what should happen if user does not designate a speaker but owns multiple speakers
# TODO - Remove debug print statements
# TODO - Testing and proper error handling
# TODO - Implement a cleaner create_or_join_session function that doesn't rely on recursion
class SonosClient:
    _encoded_credentials: str = read_api_key("SonosEncodedCredentials")

    def __init__(
        self,
        device_data: SonosDeviceData,
        client_id: str,
        group_name: Optional[str] = None,
        radio_name: Optional[str] = None,
    ):
        self._client_id: str = client_id
        self._device_data = device_data
        self._group_name: Optional[str] = group_name
        self._radio_name: Optional[str] = radio_name
        self._code: str = self._device_data["sonos"]["credentials"]["code"]
        self._timestamp: Optional[str] = self._device_data["sonos"]["credentials"].get(
            "timestamp"
        )

        self._access_token: str
        self._refresh_token: str
        try:
            self._access_token = self._device_data["sonos"]["credentials"][
                "access_token"
            ]
            self._refresh_token = self._device_data["sonos"]["credentials"][
                "refresh_token"
            ]
        except (KeyError, TypeError):
            self._create_token()
        self._check_token_expiration()
        self._headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._access_token}",
        }
        self._households = self._get_households()
        self._household_id = self._households[0]["id"]
        self._groups = self._get_groups()
        self._players = self._get_players()
        self._group_id = self._get_group_id()
        self._store_data_and_credentials()

    def _check_token_expiration(self) -> None:
        """
        Checks if access token is expired,
        and calls a function to refresh it if necessary.
        """
        timestamp = datetime.strptime(self._timestamp, "%Y-%m-%d %H:%M:%S.%f")
        if (datetime.now() - timestamp) > timedelta(hours=24):
            self._update_sonos_token()

    def _update_sonos_token(self) -> None:
        """
        Updates the access token.
        """
        self._refresh_expired_token()

        sonos_dict: SonosDeviceData = {
            "sonos": {
                "credentials": {
                    "code": self._code,
                    "timestamp": self._timestamp,
                    "access_token": self._access_token,
                    "refresh_token": self._refresh_token,
                }
            }
        }

        self._store_data(sonos_dict)

    def _refresh_expired_token(self) -> Union[None, List[Any], Dict[str, Any]]:
        """
        Helper function for updating the access token.
        """
        r = requests.post(
            _OAUTH_ACCESS_ENDPOINT,
            params={
                "grant_type": "refresh_token",
                "refresh_token": self._refresh_token,
            },
            headers={"Authorization": f"Basic {self._encoded_credentials}"},
        )
        response = json.loads(r.text)

        self._access_token = response["access_token"]
        self._timestamp = str(datetime.now())

        return response

    def _create_token(self) -> Union[None, List[Any], Dict[str, Any]]:
        """
        Creates a token given a code
        """
        host = str(flask.request.host)
        r = requests.post(
            _OAUTH_ACCESS_ENDPOINT,
            params={
                "grant_type": "authorization_code",
                "code": self._code,
                "redirect_uri": f"http://{host}/connect_sonos.api",
            },
            headers={"Authorization": f"Basic {self._encoded_credentials}"},
        )
        response = json.loads(r.text)
        self._access_token = response.get("access_token")
        self._refresh_token = response.get("refresh_token")
        self._timestamp = str(datetime.now())
        return response

    def _get_households(self) -> List[Dict[str, str]]:
        """
        Returns the list of households of the user
        """
        response = query_json_api(_HOUSEHOLDS_ENDPOINT, headers=self._headers)
        return response["households"]

    def _get_groups(self) -> Dict[str, str]:
        """
        Returns the list of groups of the user
        """
        cleaned_groups_dict = {}
        for _ in range(len(self._households)):
            url = f"{_HOUSEHOLDS_ENDPOINT}/{self._household_id}/groups"

            response = query_json_api(url, headers=self._headers)
            cleaned_groups_dict = self._create_groupdict_for_db(response["groups"])
        return cleaned_groups_dict

    def _get_group_id(self) -> str:
        """
        Returns the group id for the given query
        """
        try:
            if self._group_name is not None:
                translated_group_name = self._translate_group_name()
                group_id = self._groups.get(translated_group_name.casefold())
                if group_id:
                    return group_id
            return list(self._groups.values())[0]
        except (KeyError, TypeError):
            url = f"{_HOUSEHOLDS_ENDPOINT}/{self._household_id}/groups"

            response = query_json_api(url, headers=self._headers)
            return response["groups"][0]["id"]

    def _translate_group_name(self) -> str:
        """
        Translates the group name to the correct group name
        """
        try:
            english_group_name = _GROUPS_DICT[self._group_name]
            return english_group_name
        except (KeyError, TypeError):
            return self._group_name

    def _get_players(self) -> Dict[str, str]:
        """
        Returns the list of groups of the user
        """
        for _ in range(len(self._households)):
            url = f"{_HOUSEHOLDS_ENDPOINT}/{self._household_id}/groups"

            response = query_json_api(url, headers=self._headers)
            cleaned_players_dict = self._create_playerdict_for_db(response["players"])
            return cleaned_players_dict

    def _get_player_id(self) -> str:
        """
        Returns the player id for the given query
        """
        try:
            player_id = self._players[0]["id"]
            return player_id
        except (KeyError, TypeError):
            url = f"{_HOUSEHOLDS_ENDPOINT}/{self._household_id}/groups"

            response = query_json_api(url, headers=self._headers)
            return response["players"][0]["id"]

    def _create_data_dict(self) -> Dict[str, str]:
        data_dict = {"households": self._households}
        for i in range(len(self._households)):
            groups_dict = self._groups
            players_dict = self._players

        data_dict["groups"] = groups_dict
        data_dict["players"] = players_dict
        return data_dict

    def _create_cred_dict(self) -> Dict[str, str]:
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
        cred_dict = self._create_cred_dict()
        sonos_dict = {}
        sonos_dict["sonos"] = {"credentials": cred_dict}
        self._store_data(sonos_dict)

    def _store_data(self, data: SonosDeviceData) -> None:
        new_dict = {"iot_speakers": data}
        Query.store_query_data(self._client_id, "iot", new_dict, update_in_place=True)

    def _create_groupdict_for_db(self, groups: list) -> Dict[str, str]:
        groups_dict = {}
        for i in range(len(groups)):
            groups_dict[groups[i]["name"].casefold()] = groups[i]["id"]
        return groups_dict

    def _create_playerdict_for_db(self, players: list) -> Dict[str, str]:
        players_dict = {}
        for i in range(len(players)):
            players_dict[players[i]["name"]] = players[i]["id"]
        return players_dict

    def _create_or_join_session(self, recursion=None) -> Optional[str]:
        url = f"{_GROUP_ENDPOINT}/{self._group_id}/playbackSession/joinOrCreate"

        payload = json.dumps(
            {"appId": "com.mideind.embla", "appContext": "embla123"}
        )  # FIXME: Use something else than embla123

        response = post_to_json_api(url, form_data=payload, headers=self._headers)
        if response is None:
            self.toggle_pause()
            if recursion is None:
                response = self._create_or_join_session(recursion=True)
            else:
                return None
            session_id = response

        else:
            session_id = response["sessionId"]
        return session_id

    def play_radio_stream(self, radio_url: Optional[str]) -> Optional[str]:
        session_id = self._create_or_join_session()
        if radio_url is None:
            try:
                radio_url = self._device_data["sonos"]["data"]["last_radio_url"]
            except KeyError:
                radio_url = "http://netradio.ruv.is/rondo.mp3"

        url = f"{_PLAYBACKSESSIONS_ENDPOINT}/{session_id}/playbackSession/loadStreamUrl"

        payload = json.dumps(
            {
                "streamUrl": radio_url,
                "playOnCompletion": True,
                # "stationMetadata": {"name": f"{radio_name}"},
                "itemId": "StreamItemId",
            }
        )

        response = post_to_json_api(url, form_data=payload, headers=self._headers)
        if response is None:
            return "Group not found"
        data_dict = {"sonos": {"data": {"last_radio_url": radio_url}}}
        self._store_data(data_dict)

    def increase_volume(self) -> None:
        url = f"{_GROUP_ENDPOINT}/{self._group_id}/groupVolume/relative"

        payload = json.dumps({"volumeDelta": _VOLUME_INCREMENT})
        post_to_json_api(url, form_data=payload, headers=self._headers)

    def decrease_volume(self) -> None:
        url = f"{_GROUP_ENDPOINT}/{self._group_id}/groupVolume/relative"

        payload = json.dumps({"volumeDelta": -_VOLUME_INCREMENT})
        post_to_json_api(url, form_data=payload, headers=self._headers)

    def toggle_play(self) -> Union[None, List[Any], Dict[str, Any]]:
        """
        Toggles play/pause of a group
        """
        url = f"{_GROUP_ENDPOINT}/{self._group_id}/playback/play"

        response = post_to_json_api(url, headers=self._headers)
        return response

    def toggle_pause(self) -> Union[None, List[Any], Dict[str, Any]]:
        """
        Toggles play/pause of a group
        """
        url = f"{_GROUP_ENDPOINT}/{self._group_id}/playback/pause"

        response = post_to_json_api(url, headers=self._headers)
        return response

    def play_audio_clip(
        self, audioclip_url: str
    ) -> Union[None, List[Any], Dict[str, Any]]:
        """
        Plays an audioclip from link to .mp3 file
        """
        player_id = self._get_player_id()
        url = f"{_PLAYER_ENDPOINT}/{player_id}/audioClip"

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

        response = post_to_json_api(url, form_data=payload, headers=self._headers)
        return response

    def play_chime(self) -> Union[None, List[Any], Dict[str, Any]]:
        player_id = self._get_player_id()
        url = f"{_PLAYER_ENDPOINT}/{player_id}/audioClip"

        payload = json.dumps(
            {
                "name": "Embla",
                "appId": "com.acme.app",
                "volume": 30,
                "priority": "HIGH",
                "clipType": "CHIME",
            }
        )

        response = post_to_json_api(url, form_data=payload, headers=self._headers)
        return response

    def next_song(self) -> Union[None, List[Any], Dict[str, Any]]:
        url = f"{_GROUP_ENDPOINT}/{self._group_id}/playback/skipToNextTrack"

        response = post_to_json_api(url, headers=self._headers)
        return response

    def prev_song(self) -> Union[None, List[Any], Dict[str, Any]]:
        url = f"{_GROUP_ENDPOINT}/{self._group_id}/playback/skipToPreviousTrack"

        response = post_to_json_api(url, headers=self._headers)
        return response
