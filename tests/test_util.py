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


# Shenanigans to enable Pytest to discover modules in the
# main workspace directory (the parent of /tests)
basepath, _ = os.path.split(os.path.realpath(__file__))
mainpath = os.path.join(basepath, "..")
if mainpath not in sys.path:
    sys.path.insert(0, mainpath)


def test_util():
    """Test functions in util.py"""

    from util import icelandic_asciify

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

    # TODO: Test this function
    # from util import read_api_key