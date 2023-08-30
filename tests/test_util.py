"""

    Greynir: Natural language processing for Icelandic

    Copyright (C) 2023 Miðeind ehf.

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
    """Test functions in utility.py."""

    from utility import (
        GREYNIR_ROOT_DIR,
        QUERIES_DIR,
        QUERIES_UTIL_DIR,
        QUERIES_GRAMMAR_DIR,
        QUERIES_JS_DIR,
        QUERIES_UTIL_GRAMMAR_DIR,
        CONFIG_DIR,
        RESOURCES_DIR,
        STATIC_DIR,
        icelandic_asciify,
        sanitize_filename,
        modules_in_dir,
        cap_first,
        icequote,
    )

    # Test that the root directory is correctly structured
    assert (
        # utility should be in the root dir
        (GREYNIR_ROOT_DIR / "utility.py").is_file()
        # A few files that are found in the root dir
        and (GREYNIR_ROOT_DIR / "LICENSE.txt").is_file()
        and (GREYNIR_ROOT_DIR / "requirements.txt").is_file()
        and (GREYNIR_ROOT_DIR / "main.py").is_file()
    ), f"Was utility.py moved from the root folder?"

    assert CONFIG_DIR.exists() and CONFIG_DIR.is_dir()
    assert RESOURCES_DIR.exists() and RESOURCES_DIR.is_dir()
    assert STATIC_DIR.exists() and STATIC_DIR.is_dir()
    assert QUERIES_DIR.exists() and QUERIES_DIR.is_dir()
    assert QUERIES_GRAMMAR_DIR.exists() and QUERIES_GRAMMAR_DIR.is_dir()
    assert QUERIES_JS_DIR.exists() and QUERIES_JS_DIR.is_dir()
    assert QUERIES_UTIL_DIR.exists() and QUERIES_UTIL_DIR.is_dir()
    assert QUERIES_UTIL_GRAMMAR_DIR.exists() and QUERIES_UTIL_GRAMMAR_DIR.is_dir()

    # Test icelandic_asciify
    is2ascii = {
        "það mikið er þetta gaman": "thad mikid er thetta gaman",
        "HVAÐ ER EIGINLEGA Í GANGI?": "HVAD ER EIGINLEGA I GANGI?",
        "Örnólfur Gyrðir Möðvarsson": "Ornolfur Gyrdir Modvarsson",
        "Dóra": "Dora",
        "Álfur": "Alfur",
        "GUÐRÚN": "GUDRUN",
        "Guðrún": "Gudrun",
        "ÞÓRIR": "THORIR",
        "þÓRIR": "thORIR",
        "Þórir": "THorir",
        "Ævilöng Ánauð": "AEvilong Anaud",
    }
    for k, v in is2ascii.items():
        assert icelandic_asciify(k) == v

    # Test sanitize_filename
    unsan2san = {
        "Hvað er eiginlega í gangi?": "hvad_er_eiginlega_i_gangi",
        "ALDREI FÓR ÉG SUÐUR": "aldrei_for_eg_sudur",
        "ekki Benda á miG...": "ekki_benda_a_mig",
        "Þetta er bara einhver texti": "thetta_er_bara_einhver_texti",
        "Sæll vert þú, Þórir": "saell_vert_thu_thorir",
    }
    for k, v in unsan2san.items():
        assert sanitize_filename(k) == v

    # Test modules_in_dir
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

    assert cap_first("yolo") == "Yolo"
    assert cap_first("YOLO") == "YOLO"
    assert cap_first("yoLo") == "YoLo"
    assert cap_first("Yolo") == "Yolo"
    assert cap_first("þristur") == "Þristur"
    assert cap_first("illur ásetninguR") == "Illur ásetninguR"

    assert icequote("sæll") == "„sæll“"
    assert icequote(" Góðan daginn ") == "„Góðan daginn“"


def test_read_json_api_key():
    """Test reading API keys from JSON files."""

    from utility import read_json_api_key, GREYNIR_ROOT_DIR

    # Test reading a non-existent key
    assert read_json_api_key("nonexistent") == {}

    # Test reading a key from a JSON file
    assert read_json_api_key(
        "dummy_json_api_key", folder=GREYNIR_ROOT_DIR / "tests/files"
    ) == {"key": 123456789}


def test_read_txt_api_key():
    """Test reading API keys from .txt files."""

    from utility import read_txt_api_key, GREYNIR_ROOT_DIR

    # Test reading a non-existent key
    assert read_txt_api_key("nonexistent") == ""

    # Test reading a key from a .txt file
    assert (
        read_txt_api_key(
            "dummy_greynir_api_key", folder=GREYNIR_ROOT_DIR / "tests/files"
        )
        == "123456789"
    )
