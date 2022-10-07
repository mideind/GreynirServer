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


def _find_greynir_root_folder() -> Path:
    """Small helper function to find the root folder of Greynir."""
    p = Path(__file__).resolve()
    # Search for LICENSE.txt file (should be in root folder)
    while not (p / "LICENSE.txt").is_file() and p.parent != p:
        p = p.parent
    assert (
        p.parent != p
    ), "Can't find root project folder. Was the LICENSE.txt file moved?"
    return p.resolve()


GREYNIR_ROOT_PATH: Path = _find_greynir_root_folder()


@lru_cache(maxsize=32)
def read_api_key(key_name: str) -> str:
    """Read the given key from a text file in resources directory. Cached."""
    p = GREYNIR_ROOT_PATH / "resources" / f"{key_name}.txt"
    try:
        return p.read_text().strip()
    except FileNotFoundError:
        pass
    return ""


def modules_in_dir(*args: str) -> List[str]:
    """Find the import names of all python modules in a given directory."""
    folder = GREYNIR_ROOT_PATH / Path(*args)
    assert (
        folder.exists() and folder.is_dir()
    ), f"Directory {folder} not found when calling modules_in_dir()"
    module_parents = ".".join(folder.relative_to(GREYNIR_ROOT_PATH).parts)

    return [
        f"{module_parents}.{pyfile.stem}"
        for pyfile in folder.glob("*.py")
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
