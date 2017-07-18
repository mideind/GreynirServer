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

def gen_simple_trees(criteria, stats):
    """ Generate simplified parse trees from articles matching the criteria """
    for a in Article.articles(criteria):
        if not a.root_domain or "raduneyti" in a.root_domain:
            # Skip ministry websites due to amount of chaff found there
            continue
        tree = Tree(url = a.url, authority = a.authority)
        # Note the parse timestamp
        stats["parsed"] = a.parsed
        tree.load(a.tree)
        for _, stree in tree.simple_trees():
            yield stree

def gen_file(outfile, generator, size):
    """ Generate an output file from articles that match the criteria """
    written = 0
    with open(outfile, "w") as f:
        for stree in generator:
            flat = stree.flat
            # Hack to sidestep bug in older parses
            if '"' not in flat:
                f.write(f"{stree.text}\t{flat}\n")
                written += 1
                if written >= size:
                    break
    return written

def main(dev_size, train_size):

    print("Welcome to the text and parse tree pair generator")

    try:
        # Read configuration file
        Settings.read(os.path.join(basepath, "config/ReynirSimple.conf"))
    except ConfigError as e:
        print("Configuration error: {0}".format(e))
        quit()

    # Generate the parse trees in descending order by time of parse
    stats = { "parsed" : datetime.utcnow() }
    gen = gen_simple_trees({ "order_by_parse" : True }, stats)

    print(f"\nWriting {dev_size} sentences to {OUTFILE_DEV}")
    written = gen_file(OUTFILE_DEV, gen, dev_size)
    print(f"{written} sentences written")

    print(f"\nWriting {train_size} sentences to {OUTFILE_TRAIN}")
    written = gen_file(OUTFILE_TRAIN, gen, train_size)
    print(f"{written} sentences written")

    last_parsed = stats["parsed"]
    print(f"\nThe last article processed was parsed at {last_parsed}")
    print("\nPair generation completed")

if __name__ == "__main__":

    import argparse

    parser = argparse.ArgumentParser(description='Generates training data files')
    parser.add_argument('--dev', dest='DEV_SIZE', type=int,
        help="number of sentences in the development set (default 20,000)", default=20000)
    parser.add_argument('--train', dest='TRAIN_SIZE', type=int,
        help="number of sentences in the training set (default 1,000,000)", default=1000000)

    args = parser.parse_args()

    main(dev_size = args.DEV_SIZE, train_size = args.TRAIN_SIZE)
