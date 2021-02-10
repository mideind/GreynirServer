"""

    Greynir: Natural language processing for Icelandic

    Copyright (C) 2021 Miðeind ehf.

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


    This module handles Ja.is API queries.

"""

from typing import Dict, Optional

import os
import logging
from urllib.parse import urlencode

from . import query_json_api, gen_answer
from query import Query


_JA_API_KEY: Optional[str] = None
_JA_API_KEY_PATH = os.path.join(
    os.path.dirname(__file__), "..", "resources", "JaServerKey.txt"
)


def ja_api_key() -> str:
    """ Lazy-load API key from file. """
    global _JA_API_KEY
    if _JA_API_KEY is None:
        try:
            with open(_JA_API_KEY_PATH) as f:
                _JA_API_KEY = f.read().strip()
        except FileNotFoundError:
            _JA_API_KEY = ""
    return _JA_API_KEY


_JA_API_URL = "https://api.ja.is/search/v6/?{0}"


def query_ja_api(q: str) -> Optional[Dict]:
    """ Send query to ja.is API. """
    key = ja_api_key()
    if not key:
        # No key, can't query the API
        logging.warning("No API key for ja.is")
        return None

    qd = {"q": q}
    headers = {"Authorization": key}

    # Send API request, get back parsed JSON
    url = _JA_API_URL.format(urlencode(qd))
    res = query_json_api(url, headers=headers)

    return res


def handle_plain_text(q: Query) -> bool:
    """Handle a plain text query, contained in the q parameter
    which is an instance of the query.Query class."""
    ql = q.query_lower.rstrip("?")
    if ql == "hvar býr sveinbjörn þórðarson":
        print(_JA_API_KEY_PATH)
        print(query_ja_api("Sveinbjörn Þórðarson"))
        q.set_answer(*gen_answer("Öldugötu?"))
        return True
    return False
