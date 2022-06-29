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


    API routes
    Note: All routes ending with .api are configured not to be cached by nginx

"""

import requests
from datetime import datetime, timedelta
from util import read_api_key

# TODO: Refresh token functionality
class SonosClient:
    def __init__(self, device_data, q, query=None):
        self._q = q
        self._device_data = device_data
        self._query = query

        try:
            self._access_token = self._device_data["sonos"]["credentials"][
                "access_token"
            ]
            self._refresh_token = self._device_data["sonos"]["credentials"][
                "refresh_token"
            ]
            self.check_token_expiration()
            self._households = (
                self._device_data["sonos"]["data"]["households"]
                or self.get_households()
            )
            self._household_id = self.get_household_id()
            self._groups = (
                self._device_data["sonos"]["data"]["groups"][0]["Family Room"]
                or self.get_groups()
            )
            self._players = (
                self._device_data["sonos"]["data"]["players"][0]["Family Room"]
                or self.get_players()
            )
            self._group_id = self.get_group_id()
        except KeyError:
            print("Missing device data found for this account")

    def check_token_expiration(self):
        timestamp = self._device_data["sonos"]["credentials"]["timestamp"]
        timestamp = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S.%f")
        if (datetime.now() - timestamp) > timedelta(hours=24):
            self.update_sonos_token()

    def update_sonos_token(self):
        print("update sonos token")
        self._sonos_encoded_credentials = read_api_key("SonosEncodedCredentials")
        self._access_token = self.refresh_token()
        self._access_token = self._access_token["access_token"]
        sonos_dict = {
            "sonos": {
                "credentials": {
                    "access_token": self._access_token,
                    "timestamp": str(datetime.now()),
                }
            }
        }

        self._q.set_client_data("iot_speakers", sonos_dict, update_in_place=True)

    def refresh_token(self):
        """
        Refreshes token
        """
        url = f"https://api.sonos.com/login/v3/oauth/access?grant_type=refresh_token&refresh_token={self._refresh_token}"

        payload = {}
        headers = {"Authorization": f"Basic {self._sonos_encoded_credentials}"}

        response = requests.request("POST", url, headers=headers, data=payload)

        return response.json()

    def toggle_play_pause(self):
        """
        Toggles the play/pause of a group
        """
        url = f"https://api.ws.sonos.com/control/api/v1/groups/{self._group_id}/playback/togglePlayPause"

        payload = {}
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._access_token}",
        }

        response = requests.request("POST", url, headers=headers, data=payload)

        return response

    def get_households(self):
        """
        Returns the list of households of the user
        """
        url = f"https://api.ws.sonos.com/control/api/v1/households"

        payload = {}
        headers = {"Authorization": f"Bearer {self._access_token}"}

        response = requests.request("GET", url, headers=headers, data=payload)

        return response.json()

    def get_household_id(self):
        """
        Returns the household id for the given query
        """
        url = f"https://api.ws.sonos.com/control/api/v1/households"

        payload = {}
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._access_token}",
        }

        response = requests.request("GET", url, headers=headers, data=payload)

        return response.json()["households"][0]["id"]

    def get_groups(self):
        """
        Returns the list of groups of the user
        """
        url = f"https://api.ws.sonos.com/control/api/v1/households/{self.household_id}/groups"

        payload = {}
        headers = {"Authorization": f"Bearer {self._access_token}"}

        response = requests.request("GET", url, headers=headers, data=payload)

        return response.json()

    def get_group_id(self):
        """
        Returns the group id for the given query
        """
        url = f"https://api.ws.sonos.com/control/api/v1/households/{self._household_id}/groups"

        payload = {}
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._access_token}",
        }

        response = requests.request("GET", url, headers=headers, data=payload)

        return response.json()["groups"][0]["id"]


# TODO: Check whether this should return the ids themselves instead of the json response
def get_households(token):
    """
    Returns the list of households of the user
    """
    url = f"https://api.ws.sonos.com/control/api/v1/households"

    payload = {}
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.request("GET", url, headers=headers, data=payload)

    return response.json()


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


def refresh_token(sonos_encoded_credentials, refresh_token):
    """
    Refreshes token
    """
    url = f"https://api.sonos.com/login/v3/oauth/access?grant_type=refresh_token&refresh_token={refresh_token}"

    payload = {}
    headers = {"Authorization": f"Basic {sonos_encoded_credentials}"}

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


def update_sonos_token(q, device_data):
    print("update sonos token")
    sonos_encoded_credentials = read_api_key("SonosEncodedCredentials")
    refresh_token_str = device_data["sonos"]["credentials"]["refresh_token"]
    access_token = refresh_token(sonos_encoded_credentials, refresh_token_str).json()
    access_token = access_token["access_token"]
    sonos_dict = {
        "sonos": {
            "credentials": {
                "access_token": access_token,
                "timestamp": str(datetime.now()),
            }
        }
    }
    q.set_client_data("iot_speakers", sonos_dict, update_in_place=True)
