"""

    Reynir: Natural language processing for Icelandic

    Location query response module

    Copyright (C) 2019 Miðeind ehf.

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

"""

# TODO: Iceland street names should be in the accusative. Country name should also be declined.
# TODO: "staddur á" vs. "staddur í"

import requests
import json
import logging

MAPS_API_URL = "https://maps.googleapis.com/maps/api/geocode/json?latlng={0},{1}&key={2}&language=is"


# The Google API identifier (you must obtain your own key if you want to use this code)
_API_KEY = ""
_API_KEY_PATH = "resources/GoogleServerKey.txt"


def _get_API_key():
    """ Read Google API key from file """
    global _API_KEY
    if not _API_KEY:
        try:
            # You need to obtain your own key and put it in
            # _API_KEY_PATH if you want to use this code
            with open(_API_KEY_PATH) as f:
                _API_KEY = f.read().rstrip()
        except FileNotFoundError:
            _API_KEY = ""
    return _API_KEY


WHERE_AM_I_STRINGS = frozenset(
    ("hvar er ég", "hvar er ég núna", "hvar er ég staddur", "hver er staðsetning mín")
)
LOC_QTYPE = "Location"


def handle_plain_text(q):
    """ Handle a plain text query, contained in the q parameter
        which is an instance of the query.Query class.
        Returns True if the query was handled, and in that case
        the appropriate properties on the Query instance have
        been set, such as the answer and the query type (qtype).
        If the query is not recognized, returns False. """
    ql = q.query_lower

    if ql.endswith("?"):
        ql = ql[:-1]

    if ql not in WHERE_AM_I_STRINGS:
        return False

    loc = q.location
    if not loc:
        # We don't have a location associated with the query
        answer = "Ég veit ekkert um staðsetningu þína."
        response = dict(answer=answer)
        voice = answer
        q.set_qtype(LOC_QTYPE)
        q.set_answer(response, answer, voice)
        return True

    # Load API key
    key = _get_API_key()
    if not key:
        # No key, can't query Google location API
        logging.warning("No API key for location lookup")
        return False

    # Send API request
    url = MAPS_API_URL.format(loc[0], loc[1], key)
    try:
        r = requests.get(url)
    except Exception as e:
        logging.warning(str(e))
        return False

    if r.status_code != 200:
        return False

    # Parse json API response
    resp = json.loads(r.text)

    if (
        not resp
        or "results" not in resp
        or not len(resp["results"])
        or not resp["results"][0]
    ):
        return False

    top = resp["results"][0]

    try:
        comp = top["address_components"]

        # Extract address info
        num = comp[0]["long_name"]
        street = comp[1]["long_name"]
        locality = comp[3]["long_name"]

        # Create response string
        descr = "{1} {0} í {2}".format(num, street, locality)
    except Exception as e:
        logging.warning("Failed to create address string from API response")
        descr = top["formatted_address"]

    answer = descr
    response = dict(answer=answer)
    voice = "Þú ert staddur á {0}".format(answer)

    q.set_qtype(LOC_QTYPE)
    q.set_answer(response, answer, voice)

    return True
