#!/usr/bin/env python
"""
    
    Reynir: Natural language processing for Icelandic

    Additional vocabulary utility

    Copyright (C) 2018 Miðeind ehf.
    Author: Vilhjálmur Þorsteinsson

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


    This utility generates a text file with an additional vocabulary
    for BÍN, i.e. entries that are missing from the regular BÍN .csv file.

    The source data is read from the Reynir.conf settings file,
    augmented from the BÍN database (accessed via SQL) and written
    to the file resources/ord.add.csv.

"""

import os
import sys

# Hack to make this Python program executable from the utils subdirectory
basepath, _ = os.path.split(os.path.realpath(__file__))
_UTILS = os.sep + "utils"
if basepath.endswith(_UTILS):
    basepath = basepath[0:-len(_UTILS)]
    sys.path.append(basepath)

from bindb import BIN_Db
from settings import Settings, Meanings, ConfigError

if __name__ == "__main__":

    print("Welcome to the Reynir additional vocabulary builder\n")

    try:
        # Read configuration file
        Settings.read(os.path.join(basepath, "config", "Reynir.conf"))
    except ConfigError as e:
        print("Configuration error: {0}".format(e))
        quit()

    try:
        fname = os.path.join(basepath, "resources", "ord.add.csv")
        print("Writing {0}".format(fname))
        with open(fname, "w") as f:
            for _, meanings in Meanings.DICT.items():
                for m in meanings:
                    stofn, utg, ordfl, fl, ordmynd, beyging = m
                    f.write("{0};{1};{2};{3};{4};{5}\n"
                        .format(stofn, utg, ordfl, fl, ordmynd, beyging)
                    )
        print("Done")
    finally:
        BIN_Db.cleanup()

