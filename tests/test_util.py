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


    Tests for utility code in the Greynir repository.

"""

import os
import sys
from pathlib import Path


# Shenanigans to enable Pytest to discover modules in the
# main workspace directory (the parent of /tests)
basepath, _ = os.path.split(os.path.realpath(__file__))
mainpath = os.path.join(basepath, "..")
if mainpath not in sys.path:
    sys.path.insert(0, mainpath)


def test_util():
    """Test functions in utility.py"""

    from utility import (
        icelandic_asciify,
        GREYNIR_ROOT_DIR,
        modules_in_dir,
        QUERIES_DIR,
        QUERIES_UTIL_DIR,
        QUERIES_GRAMMAR_DIR,
        QUERIES_JS_DIR,
        QUERIES_UTIL_GRAMMAR_DIR,
        CONFIG_DIR
    )

    is2ascii = {
        "það mikið er þetta gaman": "thad mikid er thetta gaman",
        "HVAÐ ER EIGINLEGA Í GANGI?": "HVAD ER EIGINLEGA I GANGI?",
        "Örnólfur Gyrðir Möðvarsson": "Ornolfur Gyrdir Modvarsson",
        "Dóra": "Dora",
        "Álfur": "Alfur",
        "GUÐRÚN": "GUDRUN",
    }
    for k, v in is2ascii.items():
        assert icelandic_asciify(k) == v

    assert (
        # utility should be in the root dir
        (GREYNIR_ROOT_DIR / "utility.py").is_file()
        # A few files that are found in the root dir
        and (GREYNIR_ROOT_DIR / "LICENSE.txt").is_file()
        and (GREYNIR_ROOT_DIR / "requirements.txt").is_file()
        and (GREYNIR_ROOT_DIR / "main.py").is_file()
    ), f"Was utility.py moved from the root folder?"

    assert CONFIG_DIR.exists() and CONFIG_DIR.is_dir()
    assert QUERIES_DIR.exists() and QUERIES_DIR.is_dir()
    assert QUERIES_GRAMMAR_DIR.exists() and QUERIES_GRAMMAR_DIR.is_dir()
    assert QUERIES_JS_DIR.exists() and QUERIES_JS_DIR.is_dir()
    assert QUERIES_UTIL_DIR.exists() and QUERIES_UTIL_DIR.is_dir()
    assert QUERIES_UTIL_GRAMMAR_DIR.exists() and QUERIES_UTIL_GRAMMAR_DIR.is_dir()

    def get_modules(*path: str):
        return [
            ".".join(i.relative_to(GREYNIR_ROOT_DIR).with_suffix("").parts)
            for i in (GREYNIR_ROOT_DIR.joinpath(*path)).glob("*.py")
            if not i.stem.startswith("_")
        ]

    assert modules_in_dir(Path("tests")) == get_modules("tests")
    assert modules_in_dir(Path("queries")) == get_modules("queries")
    assert modules_in_dir(QUERIES_UTIL_DIR.absolute()) == get_modules("queries", "util")
    assert modules_in_dir(
        QUERIES_UTIL_DIR.relative_to(GREYNIR_ROOT_DIR)
    ) == get_modules("queries", "util")

    # TODO: Test this function
    # from util import read_api_key
