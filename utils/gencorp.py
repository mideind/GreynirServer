#!/usr/bin/env python
"""

    Greynir: Natural language processing for Icelandic

    Text and parse tree pair generator

    Copyright (C) 2020 Miðeind ehf.

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


    This utility program generates sentence trees for GreynirCorpus.

        https://github.com/mideind/GreynirCorpus

    Depends on Miðeind's fork of the Annotald parse tree annotation tool.

        https://github.com/mideind/Annotald

    The output format is similar to that of the Penn Treebank.

"""

import os
import sys
import random
from datetime import datetime
import gc

# Hack to make this Python program executable from the utils subdirectory
basepath, _ = os.path.split(os.path.realpath(__file__))
_UTILS = os.sep + "utils"
if basepath.endswith(_UTILS):
    basepath = basepath[0 : -len(_UTILS)]
    sys.path.append(basepath)

from settings import Settings
from article import Article
from tree import Tree

from annotald.reynir_utils import reynir_sentence_to_annotree, simpleTree2NLTK
from annotald.annotree import AnnoTree


ENGLISH_WORDS = frozenset(
    [
        "the",
        "a",
        "is",
        "each",
        "year",
        "our",
        "on",
        "in",
        "and",
        "this",
        "that",
        "they",
        "s",
        "t",
        "don't",
        "isn't",
        "big",
        "cheese",
        "steak",
        "email",
        "search",
        "please",
    ]
)


def gen_simple_trees(criteria):
    """ Generate simplified parse trees from articles matching the criteria """
    for a in Article.articles(criteria):
        # Skip articles from certain websites
        if (
            not a.root_domain
            or "raduneyti" in a.root_domain
            or "lemurinn" in a.root_domain
        ):
            continue

        tree = Tree(url=a.url, authority=a.authority)
        # Note the parse timestamp
        tree.load(a.tree)
        for ix, stree in tree.simple_trees():
            text = stree.text
            tokens = text.split()
            if len(tokens) > 2:
                wordset = set([t.lower() for t in tokens])
                # Only return sentences without our bag of English words
                if not (wordset & ENGLISH_WORDS):
                    yield stree, tree.score(ix), tree.length(ix), a.uuid, a.url, ix


MIN_SENT_LENGTH = 3
MAX_BATCH = 10000  # Num sentences per batch to shuffle
SEPARATOR = "\n\n"


def main(num_sent, parse_date_gt, outfile):

    try:
        # Read configuration file
        Settings.read(os.path.join(basepath, "config/GreynirSimple.conf"))
    except ConfigError as e:
        print("Configuration error: {0}".format(e))
        quit()

    # Generate the parse trees from visible roots only,
    # in descending order by time of parse
    criteria = {"order_by_parse": True, "visible": True}
    if parse_date_gt is not None:
        criteria["parse_date_gt"] = parse_date_gt

    # Generator for articles
    gen = gen_simple_trees(criteria)

    accumulated = []
    total = 0
    skipped = 0

    with open(outfile, "w") as f:
        # Consume from generator
        for i, (tree, score, ln, aid, aurl, snum) in enumerate(gen):
            if ln < MIN_SENT_LENGTH:
                skipped += 1
                continue

            # Create Annotald tree
            meta_node = AnnoTree(
                "META",
                [
                    AnnoTree("ID-CORPUS", [str(aid) + "." + str(snum)]),
                    # AnnoTree("ID-LOCAL", [outfile]),
                    AnnoTree("URL", [aurl]),
                    # AnnoTree("COMMENT", [""]),
                ],
            )
            nltk_tree = simpleTree2NLTK(tree)
            meta_tree = AnnoTree("", [meta_node, nltk_tree])

            # print(meta_tree)
            # print("")

            # Accumulate tree strings until we have enough
            accumulated.append(meta_tree.__str__() + SEPARATOR)
            accnum = len(accumulated)
            final_batch = (accnum + total) >= num_sent

            if accnum == MAX_BATCH or final_batch:
                # Shuffle the batch
                random.shuffle(accumulated)

                # Write to file
                for tree_str in accumulated:
                    f.write(tree_str)

                total += len(accumulated)
                accumulated = []
                gc.collect()

                print("Dumping sentence trees: %d\r" % total, end="")

            if final_batch:
                break

    # print("Skipped {0}".format(skipped))
    print("\nDumped {0} trees to file '{1}'".format(total, outfile))


if __name__ == "__main__":

    import argparse

    parser = argparse.ArgumentParser(description="Generates training data files")
    parser.add_argument(
        "--num",
        dest="NUM_SENT",
        type=int,
        help="Number of sentences in corpus (default 7,000,000)",
        default=7_000_000,
    )
    parser.add_argument(
        "--parse_date_gt",
        dest="PARSE_DATE_GT",
        type=str,
        help="Cutoff date for parsed field, format YYYY-MM-DD.",
        default="1970-01-01",
    )
    parser.add_argument(
        "--outfile",
        dest="OUTFILE",
        type=str,
        help="Output filename",
        default=7_000_000,
        required=True,
    )

    args = parser.parse_args()

    main(args.NUM_SENT, args.PARSE_DATE_GT, args.OUTFILE)
