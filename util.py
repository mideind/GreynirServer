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


    Utility functions used in various places in the codebase.

"""

import os
from functools import lru_cache


@lru_cache(maxsize=32)
def read_api_key(key_name: str) -> str:
    """Read the given key from a text file in resources directory. Cached."""
    path = os.path.join(os.path.dirname(__file__), "resources", key_name + ".txt")
    try:
        with open(path) as f:
            return f.read().strip()
    except FileNotFoundError:
        pass
    return ""


def icelandic_asciify(text: str) -> str:
    """Convert Icelandic characters to their ASCII equivalent
    and remove all Unicode characters."""

    ICECHARS_TO_ASCII = {
        "ð": "d",
        "Ð": "D",
        "á": "a",
        "Á": "A",
        "ú": "u",
        "Ú": "U",
        "í": "i",
        "Í": "I",
        "é": "e",
        "É": "E",
        "þ": "th",
        "Þ": "TH",
        "ó": "o",
        "Ó": "O",
        "ý": "y",
        "Ý": "Y",
        "ö": "o",
        "Ö": "O",
        "æ": "ae",
        "Æ": "AE",
    }

    # Substitute all Icelandic chars for ASCII equivalents
    t = text
    for k, v in ICECHARS_TO_ASCII.items():
        t = t.replace(k, v)

    # Remove any remaining Unicode chars
    t = t.encode("ascii", "ignore").decode()

    return t
