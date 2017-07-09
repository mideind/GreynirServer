#!/usr/bin/env python
"""

    Reynir: Natural language processing for Icelandic

    Text and parse tree pair generator

    Copyright (C) 2017 Miðeind ehf.

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


    This utility program generates pairs of sentences and parse trees
    in flat text format, suitable inter alia for training a neural network.

"""

import os
import sys
from datetime import datetime

# Hack to make this Python program executable from the utils subdirectory
basepath, _ = os.path.split(os.path.realpath(__file__))
_UTILS = os.sep + "utils"
if basepath.endswith(_UTILS):
    basepath = basepath[0:-len(_UTILS)]
    sys.path.append(basepath)

from settings import Settings
from article import Article
from tree import Tree

OUTFILE_DEV = "parsing_dev.pairs"
OUTFILE_TRAIN = "parsing_train.pairs"

def gen_simple_trees(criteria):
    """ Generate simplified parse trees from articles matching the criteria """
    for a in Article.articles(criteria):
        if not a.root_domain or "raduneyti" in a.root_domain:
            # Skip ministry websites due to amount of chaff found there
            continue
        tree = Tree(url = a.url, authority = a.authority)
        tree.load(a.tree)
        for _, stree in tree.simple_trees():
            yield stree

def gen_file(outfile, criteria):
    """ Generate an output file from articles that match the criteria """
    numlines = 0
    print(f"Generating {outfile}")
    with open(outfile, "w") as f:
        for stree in gen_simple_trees(criteria):
            f.write("{0}\t{1}\n".format(stree.text, stree.flat))
            numlines += 1
    print(f"{numlines} lines written to {outfile}")

def main():

    print("Welcome to the text and parse tree pair generator")
    try:
        # Read configuration file
        Settings.read(os.path.join(basepath, "config/ReynirSimple.conf"))
    except ConfigError as e:
        print("Configuration error: {0}".format(e))
        quit()

    criteria_dev = {
        # From, to date
        "timestamp": (
            datetime(year=2017, month=6, day=25), # From 2017-06-25
            datetime(year=2017, month=7, day=1)   # To 2017-07-01 (not inclusive)
        )
    }
    criteria_train = {
        # From, to date
        "timestamp": (
            datetime(year=2017, month=1, day=1),  # From 2017-01-01
            datetime(year=2017, month=6, day=25)  # To 2017-06-25 (not inclusive)
        )
    }
    gen_file(OUTFILE_DEV, criteria_dev)
    gen_file(OUTFILE_TRAIN, criteria_train)
    print("Pair generation completed")

if __name__ == "__main__":

    main()
