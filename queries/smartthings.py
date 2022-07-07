from inspect import getargs
import requests
from datetime import datetime, timedelta
import flask
import random

from util import read_api_key
from queries import query_json_api, post_to_json_api
from query import Query
from typing import Dict

import json


class SmartThingsClient:
    def __init__(
        self,
        device_data: Dict[str, str],
        client_id: str,
    ):
        self._client_id = client_id
        self._device_data = device_data
        self._smartthings_encoded_credentials = read_api_key(
            "SmartThingsEncodedCredentials"
        )
        self._code = self._device_data["smartthings"]["credentials"]["code"]
        print("code :", self._code)
        self._timestamp = datetime.now()
        print("device data :", self._device_data)
        try:
            self._access_token = self._device_data["smartthings"]["credentials"][
                "access_token"
            ]
        except (KeyError, TypeError):
            self._create_token()
        # self._check_token_expiration()
        # self._households = self._get_households()
        # self._household_id = self._households[0]["id"]
        # self._groups = self._get_groups()
        # self._players = self._get_players()
        # self._group_id = self._get_group_id()
        # self._store_smartthings_data_and_credentials()
        self._store_credentials()

    def _create_token(self):

        url = "https://api.smartthings.com/v1/oauth/token"

        payload = f"code={self._code}&redirect_uri=http%3A%2F%2F192.168.1.69%3A5000%2Fconnect_smartthings.api&grant_type=authorization_code"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {self._smartthings_encoded_credentials}",
        }

        response = post_to_json_api(url, payload, headers)
        self._access_token = response.get("access_token")
        return response

    def _store_credentials(self):
        print("_store_smartthings_cred")
        # data_dict = self._create_sonos_data_dict()
        cred_dict = self._create_cred_dict()
        smartthings_dict = {}
        smartthings_dict["smartthings"] = {"credentials": cred_dict}
        self._store_data(smartthings_dict)

    def _create_cred_dict(self):
        print("_create_smartthings_cred_dict")
        cred_dict = {}
        cred_dict.update(
            {
                "access_token": self._access_token,
                "timestamp": str(datetime.now()),
            }
        )
        return cred_dict

    def _store_data(self, data):
        Query.store_query_data(self._client_id, "iot_hubs", data, update_in_place=True)

    def set_color(self):

        url = "https://api.smartthings.com/v1/devices/7d47b44f-057c-4320-9777-3d1eadca106e/commands"

        payload = json.dumps(
            {
                "commands": [
                    {
                        "component": "main",
                        "capability": "colorControl",
                        "command": "setColor",
                        "arguments": [[100, 50]],
                    }
                ]
            }
        )
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

        response = requests.request("POST", url, headers=headers, data=payload)

        print(response.text)
