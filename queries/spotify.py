from inspect import getargs
import requests
from datetime import datetime, timedelta
import flask
import random

from util import read_api_key
from queries import query_json_api, post_to_json_api, put_to_json_api
from query import Query
from typing import Dict

import json

# TODO Finna út af hverju self token virkar ekki
class SpotifyClient:
    def __init__(
        self,
        device_data: Dict[str, str],
        client_id: str,
        song_name=None,
        artist_name=None,
    ):
        self._client_id = client_id
        self._device_data = device_data
        self._encoded_credentials = read_api_key("SpotifyEncodedCredentials")
        self._code = self._device_data["credentials"]["code"]
        self._song_name = song_name
        self._artist_name = artist_name
        self._song_url = None
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

    def _create_token(self):
        """
        Create a new access token for the Spotify API.
        """
        host = flask.request.host
        url = f"https://accounts.spotify.com/api/token?grant_type=authorization_code&code={self._code}&redirect_uri=http://{host}/connect_spotify.api"

        payload = {}
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {self._encoded_credentials}",
            # "Cookie": "__Host-device_id=AQBxVApczxoXIW_roLoJ5nY1ND2wR8StM3lgCAP1SzmApFbSWeNGRpxDLjOtLaGOHTM-CpdxKbWCvXcc77StrhE1N4L5q21o2l0; __Secure-TPASESSION=AQB0Nywu3HtM0ccHT76ksjXMzzeDpIEIbYzytEhvu05ELAEfMRTsc0qyaxUphsBxE8qCN2Vsruz6Mo897xYLznaxfa0ZGdh5Jpw=; sp_sso_csrf_token=013acda7191871a43462f6a67f78e88cb74e9b5bc031363537353339303539343131; sp_tr=false",
        }

        response = post_to_json_api(url, payload, headers)
        self._access_token = response.get("access_token")
        self._refresh_token = response.get("refresh_token")
        self._timestamp = str(datetime.now())
        return response

    def _check_token_expiration(self):
        """
        Checks if access token is expired, and calls a function to refresh it if necessary.
        """
        print("check token expiration")
        try:
            timestamp = self._device_data["credentials"]["timestamp"]
        except (KeyError, TypeError):
            print("No timestamp found for Sonos token.")
            return
        timestamp = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S.%f")
        if (datetime.now() - timestamp) > timedelta(hours=1):
            print("more than 1 hour")
            self._update_sonos_token()

    def _update_sonos_token(self):
        """
        Updates the access token
        """
        print("update sonos token")
        self._refresh_expired_token()
        cred_dict = {
            "credentials": {
                "access_token": self._access_token,
                "timestamp": self._timestamp,
            }
        }
        self._store_data(cred_dict)

    def _refresh_expired_token(self):
        """
        Helper function for updating the access token.
        """
        print("_refresh_expired_token")

        url = f"https://accounts.spotify.com/api/token?grant_type=refresh_token&refresh_token={self._refresh_token}"

        payload = {}
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {self._encoded_credentials}",
            # "Cookie": "__Host-device_id=AQBxVApczxoXIW_roLoJ5nY1ND2wR8StM3lgCAP1SzmApFbSWeNGRpxDLjOtLaGOHTM-CpdxKbWCvXcc77StrhE1N4L5q21o2l0; __Secure-TPASESSION=AQB0Nywu3HtM0ccHT76ksjXMzzeDpIEIbYzytEhvu05ELAEfMRTsc0qyaxUphsBxE8qCN2Vsruz6Mo897xYLznaxfa0ZGdh5Jpw=; sp_sso_csrf_token=013acda7191871a43462f6a67f78e88cb74e9b5bc031363537353339303539343131; sp_tr=false",
        }

        response = post_to_json_api(url, payload, headers)
        self._access_token = response.get("access_token")
        self._timestamp = str(datetime.now())

    def _store_credentials(self):
        print("_store_smartthings_cred")
        # data_dict = self._create_sonos_data_dict()
        cred_dict = self._create_cred_dict()
        self._store_data(cred_dict)

    def _create_cred_dict(self):
        print("_create_spotify_cred_dict")
        cred_dict = {}
        cred_dict.update(
            {
                "access_token": self._access_token,
                "timestamp": self._timestamp,
            }
        )
        return cred_dict

    def _store_data(self, data):
        Query.store_query_data(self._client_id, "spotify", data, update_in_place=True)

    def _store_credentials(self):
        print("_store_spotify credentials")
        # data_dict = self._create_sonos_data_dict()
        cred_dict = self._create_cred_dict()
        spotify_dict = {}
        spotify_dict["credentials"] = cred_dict
        self._store_data(spotify_dict)

    def _create_cred_dict(self):
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

    def get_song_by_artist(self):
        print("get song by artist")
        print("accesss token get song; ", self._access_token)
        song_name = self._song_name.replace(" ", "%20")
        artist_name = self._artist_name.replace(" ", "%20")
        print("song name: ", song_name)
        print("artist name: ", artist_name)
        url = (
            f"https://api.spotify.com/v1/search?type=track&q={song_name}+{artist_name}"
        )
        print("url: ", url)

        payload = ""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._access_token}",
        }

        response = query_json_api(url, headers)
        print(response)
        try:
            self._song_url = response["tracks"]["items"][0]["external_urls"]["spotify"]
            self._song_uri = response["tracks"]["items"][0]["uri"]
        except IndexError:
            print("No song found.")
            return
        print("SONG URI: ", self._song_uri)

        return self._song_url

    def play_song_on_device(self):
        print("play song from device")
        print("accesss token play song; ", self._access_token)
        # self._devices = self._get_devices()
        print("exited get devices")
        url = "https://api.spotify.com/v1/me/player/play"

        payload = json.dumps(
            {
                "uris": [
                    f"{self._song_uri}",
                ]
            }
        )
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._access_token}",
        }

        response = put_to_json_api(url, payload, headers)

        print(response)
        return response

    def _get_devices(self):
        print("get devices")
        print("accesss token get devices; ", self._access_token)
        url = f"https://api.spotify.com/v1/me/player/devices"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._access_token}",
        }

        response = query_json_api(url, headers)
        print("devices: ", response)
        return response.get("devices")

    # def filter_devices(self):
    #     print("filter devices")
    #     filtered_devices = []
    #     for device in self._devices:
    #         if device["type"] == "Smartphone":
    #             filtered_devices.append(device)
    #     return filtered_devices
