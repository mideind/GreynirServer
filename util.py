"""

    Greynir: Natural language processing for Icelandic

    Copyright (C) 2020 Miðeind ehf.

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


    Utility functions used in various places in the codebase.

"""

from typing import Optional

import os

# Greynir API key, used to control client access to certain API endpoints
_GREYNIR_API_KEY: Optional[str] = None
_GREYNIR_API_KEY_PATH = os.path.join(
    os.path.dirname(__file__), "resources", "GreynirServerKey.txt"
)


def greynir_api_key() -> str:
    """ Lazy-load Greynir API key from file. """
    global _GREYNIR_API_KEY
    if _GREYNIR_API_KEY is None:
        try:
            with open(_GREYNIR_API_KEY_PATH) as f:
                _GREYNIR_API_KEY = f.read().strip()
        except FileNotFoundError:
            _GREYNIR_API_KEY = ""
    return _GREYNIR_API_KEY


# Google API key (you must obtain your own key if you want to use this code)
_GOOGLE_API_KEY = ""
_GOOGLE_API_KEY_PATH = os.path.join(
    os.path.dirname(__file__), "resources", "GoogleServerKey.txt"
)


def google_api_key() -> str:
    """ Lazy-load Google API key from file """
    global _GOOGLE_API_KEY
    if not _GOOGLE_API_KEY:
        try:
            with open(_GOOGLE_API_KEY_PATH) as f:
                _GOOGLE_API_KEY = f.read().rstrip()
        except FileNotFoundError:
            _GOOGLE_API_KEY = ""
    return _GOOGLE_API_KEY
