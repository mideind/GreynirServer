#!/usr/bin/env python
# type: ignore
"""

    Greynir: Natural language processing for Icelandic

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


    This utility program generates sentence trees for GreynirCorpus.

        https://github.com/mideind/GreynirCorpus

    Depends on Miðeind's fork of the Annotald parse tree annotation tool.

        https://github.com/mideind/Annotald

    The output format is similar to that of the Penn Treebank.

"""

import os
import sys
import gc
from random import shuffle
from collections import defaultdict

# Hack to make this Python program executable from the tools subdirectory
basepath, _ = os.path.split(os.path.realpath(__file__))
_TOOLS = os.sep + "tools"
if basepath.endswith(_TOOLS):
    basepath = basepath[0 : -len(_TOOLS)]
    sys.path.append(basepath)

from settings import Settings, ConfigError  # noqa
from article import Article  # noqa
from tree import Tree  # noqa

# To make this work, clone Miðeind's Annotald repo, enter the Greynir
# virtualenv and run "python setup.py develop" from the Annotald repo root
# https://github.com/mideind/Annotald
from annotald.reynir_utils import simpleTree2NLTK  # noqa
from annotald.annotree import AnnoTree  # noqa

from reynir import ICELANDIC_RATIO  # noqa

from tokenizer import definitions, TOK, Tok  # noqa

# Min num tokens in sentence
MIN_SENT_LENGTH = 5

# Num sentences to batch and shuffle
# Controls memory usage i.e. how many sentences
# are accumulated in memory prior to shuffling.
MAX_BATCH = 10000

# Separator for sentence trees in output file
SEPARATOR = "\n\n"

CUMUDICT = defaultdict(list)  # code, [sents]

BUCKDICT = defaultdict(int)  # terminal/non-terminal, [freq]

# Skip sentences containing these tokens
ENGLISH_WORDS = frozenset(
    [
        "the",
        "she",
        "each",
        "year",
        "our",
        "on",
        "in",
        "and",
        "this",
        "that",
        "they",
        "what",
        "when",
        "which",
        "how",
        "why",
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
BIGSET = set()


def sieve(ix, stree):
    """ Judge which sentences make sense for each subcorpora """
    text = stree.text
    tokens = text.split()
    code = "silver"  # Default value
    # Make sure it has enough tokens
    while True:

        code = leavescheck(stree)
        if code == "copper":
            print("\t1 - copper")
            break

        code = phrasecheck(stree)
        if code == "copper":
            print("\t2 - copper")
            break

        if not len(tokens) >= MIN_SENT_LENGTH:
            print("\t3 - copper")
            code = "copper"
            break

        # Skip sentences that don't contain enough Icelandic words
        if unicelandic(stree):
            #    print("\t4 - copper")
            code = "copper"
            break

        # Skip sentences containing something in our bag of English words
        wordset = set([t.lower() for t in tokens])
        if wordset & ENGLISH_WORDS:
            print("\t5 - copper")
            code = "copper"
            break

        # Skip uncapitalized sentences
        if text[0].islower():
            print("\t6 - copper")
            code = "copper"
            break

        # Skip sentences with only a single NP -- S0→NP
        if stree.match("S0 > [NP $]"):
            print("\t7 - copper")
            code = "copper"
            break

        # Skip sentences not containing a VP
        if not stree.match("S0 >> VP"):
            print("\t8 - heading")
            code = "heading"
            break

        # Skip sentences not ending in sentence ending punctuation
        if text[-1] not in definitions.END_OF_SENTENCE:
            print("\t9 - heading")
            code = "heading"
            break

        # Skip sentence if we have seen an equivalent sentence before
        # hashnorm = hash(normalize(text))
        # if hashnorm in BIGSET:
        #    print("\t10 - copper")
        #    code = "copper"
        #    break
        # else:
        #    BIGSET.add(hashnorm)
    print(code)
    return code


def unicelandic(sent):
    # Code mostly copied from annotate() in checker.py in GreynirCorrect
    words_in_bin = 0
    words_not_in_bin = 0
    for t in sent.leaves:
        if "k" in t:
            if t["k"] == "WORD":
                if "a" in t:
                    words_in_bin += 1
                else:
                    words_not_in_bin += 1
            elif t["k"] == "PERSON":
                words_in_bin += 1
            elif t["k"] == "ENTITY":
                words_not_in_bin += t["x"].count(" ") + 1
    num_words = words_in_bin + words_not_in_bin
    print("{}:{}".format(words_in_bin, words_not_in_bin))
    if num_words > 2 and words_in_bin / num_words < ICELANDIC_RATIO:
        print("Unicelandic: {}:{}".format(words_in_bin, words_not_in_bin))
        return False
    return True


def normalize(text):
    # Generalize information in sentence to ensure unique sentences in set
    text = text.lower()
    for item in definitions.PUNCTUATION:
        text = text.replace(item, "")
    for num in "0123456789":
        text = text.replace(num, "0")
    text = text.replace(" ", "")


def leavescheck(stree):
    # Check if old info
    # Check if at least 3 word, entity or person tokens
    # Add to BUCKDICT
    p = True
    cnt = 0
    for term in stree.leaves:
        if "c" in term:
            print(BUCKDICT[term["c"]])
            if BUCKDICT[term["c"]] < 1000:
                p = False
            BUCKDICT[term["c"]] += 1
        if "k" in term and term["k"] in ["WORD", "PERSON", "ENTITY"]:
            cnt += 1
    if p or cnt < 3:
        return "copper"
    return "silver"


def phrasecheck(stree):
    p = True
    for term in stree.nonterminals:
        if "i" in term:
            print(BUCKDICT[term["i"]])
            if BUCKDICT["i"] < 100:
                p = False
            BUCKDICT["i"] += 1
    return p


def main(num_sent, parse_date_gt, outfile, count, rand):

    try:
        # Read configuration file
        Settings.read(os.path.join(basepath, "config", "GreynirSimple.conf"))
    except ConfigError as e:
        print("Configuration error: {0}".format(e))
        sys.exit(os.EX_CONFIG)

    # Generate parse trees from visible roots only,
    # in descending order by time of parse
    criteria = {"order_by_parse": True, "visible": True}
    if parse_date_gt is not None:
        criteria["parse_date_gt"] = parse_date_gt

    # Generator for articles
    def gen():
        yield from Article.articles(criteria)

    silvertotal = 0
    total = 0
    arts = 0
    for art in gen():
        # Skip articles from certain websites
        aid = art.uuid
        aurl = art.url
        if arts % 100 == 0:
            print("{} articles done".format(arts))
        arts += 1
        if (
            not art.root_domain
            or "lemurinn" in art.root_domain
        ):
            # print("\t1")
            continue
        trees = None
        try:
            tree = Tree(url=art.url, authority=art.authority)
            tree.load(art.tree)

        except Exception:
            continue

        try:
            trees = tree.simple_trees()
        except Exception:
            continue

        for ix, stree in trees:
            score = tree.score(ix)
            ln = tree.length(ix)
            if rand:
                code = "random"
                print(aid)
                if aid.endswith("9"):
                    print("Fann grein!")
                    continue
            else:
                code = sieve(ix, stree)
            # Create Annotald tree
            id_str = str(aid) + "." + str(ix)
            meta_node = AnnoTree(
                "META",
                [
                    AnnoTree("ID-CORPUS", [id_str]),
                    AnnoTree("ID-LOCAL", [outfile]),
                    AnnoTree("URL", [aurl]),
                    AnnoTree("COMMENT", [""]),
                ],
            )
            nltk_tree = simpleTree2NLTK(stree)
            meta_tree = AnnoTree("", [meta_node, nltk_tree])

            # Accumulate tree strings until we have enough
            CUMUDICT[code].append(str(meta_tree) + SEPARATOR)
            accnum = len(CUMUDICT[code])
            final_batch = (accnum + total) >= num_sent
            if len(CUMUDICT["silver"]) >= num_sent:
                final_batch = True

            # We have a batch
            if accnum == MAX_BATCH or final_batch:
                fh = open(code + ".txt", "a", encoding="utf-8")
                # Shuffle and write to file
                accumulated = CUMUDICT[code]
                shuffle(accumulated)
                for tree_str in accumulated:
                    fh.write(tree_str)

                total += accnum
                CUMUDICT[code] = []
                fh.close()
                gc.collect()  # Trigger manual garbage collection

                # print("Dumping sentence trees: %d\r" % total, end="")

            if final_batch:
                break

            # print("Skipped {0}".format(skipped))
            # fsize = os.path.getsize(outfile) / pow(1024.0, 2)
            # print("\nDumped {0} trees to file '{1}' ({2:.1f} MB)".format(total, outfile, fsize))


if __name__ == "__main__":

    import argparse

    parser = argparse.ArgumentParser(description="Generates GreynirCorpus file")
    parser.add_argument(
        "--num",
        dest="NUM_SENT",
        type=int,
        help="Number of sentences in corpus (default 1,000,000)",
        default=1_000_000,
    )
    parser.add_argument(
        "--parse_date_gt",
        dest="PARSE_DATE_GT",
        type=str,
        help="Cutoff date for parsed field, format YYYY-MM-DD.",
        default="1970-01-01",
    )
    parser.add_argument("--outfile", dest="OUTFILE", type=str, help="Output filename")
    parser.add_argument(
        "--count",
        dest="COUNT",
        type=str,
        help="Count the number of available sentences meeting criteria, print and exit",
    )

    parser.add_argument(
        "-r", dest="RANDOM", action="store_true", help="Only collect random"
    )

    args = parser.parse_args()

    main(args.NUM_SENT, args.PARSE_DATE_GT, args.OUTFILE, args.COUNT, args.RANDOM)
