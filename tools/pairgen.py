#!/usr/bin/env python
# type: ignore
"""

    Greynir: Natural language processing for Icelandic

    Text and parse tree pair generator

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


    This utility program generates pairs of sentences and parse trees
    in flat text format, suitable inter alia for training a neural network.

"""

import os
import sys
import random
from datetime import datetime

# Hack to make this Python program executable from the tools subdirectory
basepath, _ = os.path.split(os.path.realpath(__file__))
_TOOLS = os.sep + "tools"
if basepath.endswith(_TOOLS):
    basepath = basepath[0:-len(_TOOLS)]
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
        for ix, stree in tree.simple_trees():
            yield stree, tree.score(ix), tree.length(ix)


def gen_flat_trees(generator):
    """ Generate (text, flat tree) tuples that we want to include
        in the file being generated """
    # Exclude sentences containing English words
    STOP_WORDS = frozenset([
        "the", "a", "is", "each", "year", "our", "on", "in",
        "and", "this", "that", "s", "t", "don't", "isn't", "big",
        "cheese", "steak", "email", "search"
    ])
    for stree, score, length in generator:
        flat, text = stree.flat_with_all_variants, stree.text
        tokens = text.split()
        # Exclude sentences with 2 or fewer tokens
        if len(tokens) > 2:
            wordset = set([t.lower() for t in tokens])
            if wordset & STOP_WORDS:
                print(f"Skipping sentence '{text}'")
            else:
                yield text, flat, score, length


def write_file(outfile, generator, size, scores):
    """ Generate an output file from articles that match the criteria """
    written = 0
    with open(outfile, "w") as f:
        for text, flat, score, length in gen_flat_trees(generator):
            # Write the (input, output) training data pair, separated by a tab character (\t)
            if scores:
                f.write(f"{text}\t{flat}\t{score}\n")
            else:
                f.write(f"{text}\t{flat}\n")
            written += 1
            if written >= size:
                break
    return written


def write_shuffled_files(outfile_dev, outfile_train, generator, dev_size, train_size, scores):
    """ Generate a randomly shuffled output file from articles that
        match the criteria. Note that the shuffle is done in memory. """
    written = 0
    lines = []
    size = dev_size + train_size
    print(f"Reading up to {size} lines from the source corpus")
    try:
        for text, flat, score, length in gen_flat_trees(generator):
            # Accumulate the (input, output) training data pairs, separated by a tab character (\t)
            if scores:
                lines.append(f"{text}\t{flat}\t{score}\n")
            else:
                lines.append(f"{text}\t{flat}\n")
            written += 1
            if written >= size:
                break
    except Exception as e:
        print(f"Exception {e} after {written} generated lines")
        return 0
    if written:
        print(f"Shuffling {written} lines from the source corpus")
        random.shuffle(lines)
        dev_set = lines[0:dev_size]
        train_set = lines[dev_size:dev_size + train_size]
        print(f"Final dev set is {len(dev_set)} lines, train set is {len(train_set)} lines")
        if dev_set:
            print(f"Writing dev set to {outfile_dev}")
            with open(outfile_dev, "w") as f:
                for line in dev_set:
                    f.write(line)
        else:
            print(f"Dev set is empty, so {outfile_dev} was not written")
        if train_set:
            print(f"Writing train set to {outfile_train}")
            with open(outfile_train, "w") as f:
                for line in train_set:
                    f.write(line)
        else:
            print(f"Train set is empty, so {outfile_train} was not written")
    return written


def main(dev_size, train_size, shuffle, scores, parse_date_gt=None):

    print("Welcome to the Greynir text and parse tree pair generator")

    try:
        # Read configuration file
        Settings.read(os.path.join(basepath, "config/GreynirSimple.conf"))
    except ConfigError as e:
        print("Configuration error: {0}".format(e))
        quit()

    # Generate the parse trees from visible roots only,
    # in descending order by time of parse
    stats = { "parsed" : datetime.utcnow() }

    criteria = { "order_by_parse" : True, "visible" : True }
    if parse_date_gt is not None:
        criteria['parse_date_gt'] = parse_date_gt

    gen = gen_simple_trees(criteria, stats)

    if shuffle:

        # Write both sets
        written = write_shuffled_files(OUTFILE_DEV, OUTFILE_TRAIN, gen, dev_size, train_size, scores)

    else:

        # Development set
        if dev_size:
            print(f"\nWriting {dev_size} {'shuffled ' if shuffle else ''}sentences to {OUTFILE_DEV}")
            written = write_file(OUTFILE_DEV, gen, dev_size, scores)
            print(f"{written} sentences written")

        # Training set
        if train_size:
            print(f"\nWriting {train_size} {'shuffled ' if shuffle else ''}sentences to {OUTFILE_TRAIN}")
            written = write_file(OUTFILE_TRAIN, gen, train_size, scores)
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
        help="number of sentences in the training set (default 1,500,000)", default=1500000)
    parser.add_argument('--noshuffle', dest='NO_SHUFFLE', action="store_true",
        help="do not shuffle output", default=False)
    parser.add_argument('--scores', dest='SCORES', action="store_true",
        help="include sentence scores", default=False)
    parser.add_argument('--parse_date_gt', dest='PARSE_DATE_GT', type=str,
                        help="Cutoff date for parsed field, format YYYY-MM-DD.", default=None)

    args = parser.parse_args()

    main(
        dev_size = args.DEV_SIZE,
        train_size = args.TRAIN_SIZE,
        shuffle = not args.NO_SHUFFLE,
        scores = args.SCORES,
        parse_date_gt = args.PARSE_DATE_GT
    )

