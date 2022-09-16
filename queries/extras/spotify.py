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


    Class which encapsulates communication with the Spotify API.

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

def put_to_json_api(
    url: str, json_data: Optional[Any] = None, headers: Optional[Dict[str, str]] = None
) -> Union[None, List[Any], Dict[str, Any]]:
    """Send a PUT request to the URL, expecting a JSON response which is
    parsed and returned as a Python data structure."""

    # Send request
    try:
        r = requests.put(url, data=json_data, headers=headers)
    except Exception as e:
        logging.warning(str(e))
        return None

    # Verify that status is OK
    if r.status_code not in range(200, 300):
        logging.warning("Received status {0} from API server".format(r.status_code))
        return None

    # Parse json API response
    try:
        if r.text:
            res = json.loads(r.text)
            return res
        return {}
    except Exception as e:
        logging.warning("Error parsing JSON API response: {0}".format(e))
    return None


# TODO Find a better way to play albums
# TODO - Remove debug print statements
# TODO - Testing and proper error handling
class SpotifyClient:
    def __init__(
        self,
        device_data: Dict[str, str],
        client_id: str,
        song_name: str = None,
        artist_name: str = None,
        album_name: str = None,
    ):
        self._api_url = "https://api.spotify.com/v1"
        self._client_id = client_id
        self._device_data = device_data
        self._encoded_credentials = read_api_key("SpotifyEncodedCredentials")
        self._code = self._device_data["credentials"]["code"]
        self._song_name = song_name
        self._artist_name = artist_name
        self._song_name = song_name
        self._song_uri = None
        self._album_name = album_name
        self._song_url = None
        self._album_url = None
        print("code :", self._code)
        self._timestamp = self._device_data.get("credentials").get("timestamp")
        print("device data :", self._device_data)
        try:
            self._access_token = self._device_data["credentials"]["access_token"]
            self._refresh_token = self._device_data["credentials"]["refresh_token"]
        except (KeyError, TypeError):
            self._create_token()
        self._check_token_expiration()
        self._store_credentials()

    def _create_token(self) -> Union[None, List[Any], Dict[str, Any]]:
        """
        Create a new access token for the Spotify API.
        """
        host = flask.request.host
        url = f"https://accounts.spotify.com/api/token?grant_type=authorization_code&code={self._code}&redirect_uri=http://{host}/connect_spotify.api"

        payload = {}
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {self._encoded_credentials}",
        }

        response = post_to_json_api(url, form_data=payload, headers=headers)
        self._access_token = response.get("access_token")
        self._refresh_token = response.get("refresh_token")
        self._timestamp = str(datetime.now())
        return response

    def _check_token_expiration(self) -> None:
        """
        Checks if access token is expired, and calls a function to refresh it if necessary.
        """
        print("check token expiration")
        try:
            timestamp = self._device_data["credentials"]["timestamp"]
        except (KeyError, TypeError):
            print("No timestamp found for spotify token.")
            return
        timestamp = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S.%f")
        if (datetime.now() - timestamp) > timedelta(hours=1):
            print("more than 1 hour")
            self._update_spotify_token()

    def _update_spotify_token(self) -> None:
        """
        Updates the access token
        """
        print("update spotify token")
        self._refresh_expired_token()

    def _refresh_expired_token(self) -> None:
        """
        Helper function for updating the access token.
        """
        print("_refresh_expired_token")

        url = f"https://accounts.spotify.com/api/token?grant_type=refresh_token&refresh_token={self._refresh_token}"

        payload = {}
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {self._encoded_credentials}",
        }

        response = post_to_json_api(url, form_data=payload, headers=headers)
        self._access_token = response.get("access_token")
        self._timestamp = str(datetime.now())

    def _store_credentials(self) -> None:
        print("_store_spotify_cred")
        cred_dict = self._create_cred_dict()
        self._store_data(cred_dict)

    def _create_cred_dict(self) -> Dict[str, str]:
        print("_create_spotify_cred_dict")
        cred_dict = {}
        cred_dict.update(
            {
                "access_token": self._access_token,
                "timestamp": self._timestamp,
            }
        )
        return cred_dict

    def _store_data(self, data: Dict[str, str]) -> None:
        new_dict = {"iot_streaming": {"spotify": data}}
        Query.store_query_data(self._client_id, "iot", new_dict, update_in_place=True)

    def _store_credentials(self) -> None:
        print("_store_spotify credentials")
        cred_dict = self._create_cred_dict()
        spotify_dict = {}
        spotify_dict["credentials"] = cred_dict
        self._store_data(spotify_dict)

    def _create_cred_dict(self) -> Dict[str, str]:
        print("_create_spotify_cred_dict")
        cred_dict = {}
        cred_dict.update(
            {
                "access_token": self._access_token,
                "refresh_token": self._refresh_token,
                "timestamp": self._timestamp,
            }
        )
        return cred_dict

    def get_song_by_artist(self) -> Optional[str]:
        print("get song by artist")
        print("accesss token get song; ", self._access_token)
        song_name = self._song_name.replace(" ", "%20")
        artist_name = self._artist_name.replace(" ", "%20")
        print("song name: ", song_name)
        print("artist name: ", artist_name)
        url = f"{self._api_url}/search?type=track&q={song_name}+{artist_name}"
        print("url: ", url)

        payload = ""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._access_token}",
        }
        response = query_json_api(url, headers)
        try:
            self._song_url = response["tracks"]["items"][0]["external_urls"]["spotify"]
            self._song_uri = response["tracks"]["items"][0]["uri"]
        except IndexError:
            print("No song found.")
            return
        print("SONG URI: ", self._song_url)

        return self._song_url

    def get_album_by_artist(self) -> Optional[str]:
        print("get albuym by artist")
        print("accesss token get song; ", self._access_token)
        album_name = self._album_name.replace(" ", "%20")
        artist_name = self._artist_name.replace(" ", "%20")
        print("song name: ", album_name)
        print("artist name: ", artist_name)
        url = f"{self._api_url}/search?type=album&q={album_name}+{artist_name}"
        print("url: ", url)

        payload = ""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._access_token}",
        }
        response = query_json_api(url, headers)
        try:
            self._album_id = response["albums"]["items"][0]["id"]
            self._album_url = response["albums"]["items"][0]["external_urls"]["spotify"]
            self._album_uri = response["albums"]["items"][0]["uri"]
        except IndexError:
            print("No song found.")
            return
        print("ALBUM URI: ", self._album_url)

        return self._album_url

    def get_first_track_on_album(self) -> Optional[str]:
        print("get first track on album")
        print("accesss token get song; ", self._access_token)
        album_name = self._album_name.replace(" ", "%20")
        artist_name = self._artist_name.replace(" ", "%20")
        print("song name: ", album_name)
        print("artist name: ", artist_name)
        url = f"{self._api_url}/albums/{self._album_id}/tracks"
        print("url: ", url)

        payload = ""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._access_token}",
        }
        response = query_json_api(url, headers)
        try:
            self._song_uri = response["items"][0]["uri"]
            self._first_album_track_url = response["items"][0]["external_urls"][
                "spotify"
            ]
        except IndexError:
            print("No song found.")
            return
        print("ALBUM URI: ", self._first_album_track_url)

        return self._first_album_track_url

    def play_song_on_device(self) -> Union[None, List[Any], Dict[str, Any]]:
        print("play song from device")
        print("accesss token play song; ", self._access_token)
        print("exited get devices")
        url = f"{self._api_url}/me/player/play"

        payload = json.dumps(
            {
                "context_uri": self._song_uri,
            }
        )
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._access_token}",
        }

        response = put_to_json_api(url, payload, headers)

        print(response)
        return response

    def play_album_on_device(self) -> Union[None, List[Any], Dict[str, Any]]:
        url = f"{self._api_url}/me/player/play"

        payload = json.dumps(
            {
                "context_uri": self._album_uri,
            }
        )
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._access_token}",
        }

        response = put_to_json_api(url, payload, headers)

        print(response)
        return response
