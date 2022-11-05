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


    Utility functions used in various places in the codebase.

"""
from typing import List

from functools import lru_cache
from pathlib import Path

# Path which points to the root folder of Greynir
GREYNIR_ROOT_DIR: Path = Path(__file__).parent.resolve()

# Other useful paths
CONFIG_DIR = GREYNIR_ROOT_DIR / "config"

RESOURCES_DIR = GREYNIR_ROOT_DIR / "resources"

STATIC_DIR = GREYNIR_ROOT_DIR / "static"

QUERIES_DIR = GREYNIR_ROOT_DIR / "queries"
QUERIES_GRAMMAR_DIR = QUERIES_DIR / "grammars"
QUERIES_JS_DIR = QUERIES_DIR / "js"
QUERIES_UTIL_DIR = QUERIES_DIR / "util"
QUERIES_UTIL_GRAMMAR_DIR = QUERIES_UTIL_DIR / "grammars"
QUERIES_DIALOGUE_DIR = QUERIES_DIR / "dialogues"


@lru_cache(maxsize=32)
def read_api_key(key_name: str) -> str:
    """Read the given key from a text file in resources directory. Cached."""
    p = RESOURCES_DIR / f"{key_name}.txt"
    try:
        return p.read_text().strip()
    except FileNotFoundError:
        pass
    return ""


def modules_in_dir(p: Path) -> List[str]:
    """
    Find the import names of all python modules
    in a given directory given a path to a folder
    (can be relative to GREYNIR_ROOT_PATH or absolute).
    """
    p = p.resolve()  # Fully resolve path before working with it
    assert (
        p.exists() and p.is_dir()
    ), f"Directory {str(p)} not found when searching for modules"

    # Return list of python files in
    # import-like format ('.' instead of '/', no '.py')
    return [
        ".".join(pyfile.with_suffix("").parts)
        for pyfile in p.relative_to(GREYNIR_ROOT_DIR).glob("*.py")
        if not pyfile.name.startswith("_")
    ]


def icelandic_asciify(text: str) -> str:
    """Convert Icelandic characters to their ASCII equivalent
    and then remove all non-ASCII characters."""

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

    # Substitute all Icelandic chars for their ASCII equivalents
    t = text
    for k, v in ICECHARS_TO_ASCII.items():
        t = t.replace(k, v)

    # Remove any remaining non-ASCII chars
    t = t.encode("ascii", "ignore").decode()

    return t
