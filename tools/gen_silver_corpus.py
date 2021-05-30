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
import hashlib
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

from reynir import ICELANDIC_RATIO  # noqa
from tokenizer import definitions  # noqa

# To make this work, clone Miðeind's Annotald repo, enter the Greynir
# virtualenv and run "python setup.py develop" from the Annotald repo root
# https://github.com/mideind/Annotald
from annotald.reynir_utils import simpleTree2NLTK  # noqa
from annotald.annotree import AnnoTree  # noqa


SENT_HASHES = set()

NONTERMDICT = defaultdict(int)  # non-terminal, [freq]
TERMDICT = defaultdict(int)  # terminal,     [freq]


def is_icelandic(sent):
    # Code mostly copied from annotate() in checker.py in GreynirCorrect
    words_in_bin = 0
    words_not_in_bin = 0
    for t in sent.leaves:
        kind = t._head.get("k")
        if kind == "WORD":
            if t._head.get("a"):
                words_in_bin += 1
            else:
                words_not_in_bin += 1
        elif kind == "PERSON":
            words_in_bin += 1
        elif kind == "ENTITY":
            words_not_in_bin += t._head.get("x").count(" ") + 1
    num_words = words_in_bin + words_not_in_bin
    if num_words > 2 and words_in_bin / num_words < ICELANDIC_RATIO:
        return False
    return True

def is_acceptable_article(art):
    if not art.root_domain or "lemurinn" in art.root_domain:
        return False
    return True

# Min num tokens in sentence
MIN_SENT_LENGTH = 5

def is_acceptable_sentence_tree(stree):
    # Generate hash of sentence text and add
    # it to SENT_HASHES to ensure uniqueness
    text = stree.text
    md5sum = hashlib.md5(text.encode("utf-8")).hexdigest()

    # Skip already processed identical sentence
    if md5sum in SENT_HASHES:
        print("\tA")
        return False

    # Skip sentences that don't contain enough Icelandic words
    if not is_icelandic(stree):
        print("\tB")
        return False

    # Skip uncapitalized sentences
    if text[0].islower():
        print("\tC")
        return False

    tokens = text.split()

    # Skip sentences with very few words
    if not len(tokens) >= MIN_SENT_LENGTH:
        print("\tD")
        return False

    # Skip sentences with only a single NP -- S0→NP
    if stree.match("S0 > [NP $]"):
        print("\tE")
        return False

    # OK, it has passed our criteria
    # Add sentence to hash set
    SENT_HASHES.add(md5sum)
    # print(text)
    print("\tF  fann rétt!")
    return True

def is_heading_sentence_tree(stree):
    if not stree.match("S0 >> VP"):
        return True
    if text[-1] not in definitions.END_OF_SENTENCE:
        return True
    return False

def gen_anno_tree(article, index, stree):
    # Create Annotald tree for sentence
    id_str = str(article.uuid) + "." + str(index)
    meta_node = AnnoTree(
        "META",
        [
            AnnoTree("ID-CORPUS", [id_str]),
            AnnoTree("URL", [article.url]),
            AnnoTree("COMMENT", [""]),
        ],
    )
    nltk_tree = simpleTree2NLTK(stree)
    return AnnoTree("", [meta_node, nltk_tree])

def old_info(stree):
    p = True
    for nonterm in stree.nonterminals:
        phrase = nonterm._head.get("i")
        if NONTERMDICT[phrase] < 100:
            # We want to add it!
            p = False
        NONTERMDICT[phrase] += 1

    for leaf in stree.leaves:
        cat = leaf._head.get("c")
        if TERMDICT[cat] < 1000:
            p = False
        TERMDICT[cat] += 1

    return p

def full_buckets(stree):
    for nonterm in NONTERMDICT:
        if NONTERMDICT[nonterm] < 100:
            return False
    for term in TERMDICT:
        if TERMDICT[term] < 1000:
            return False
    return True


NUM_SENT = 500000
LIMIT = 2000000     # Absolute limit of corpus size
BATCH_SIZE = 1000
OUT_FILENAME = "out.txt"
SEPARATOR = "\n\n"


def main():

    try:
        # Read configuration file
        Settings.read(os.path.join(basepath, "config", "GreynirSimple.conf"))
    except ConfigError as e:
        print("Configuration error: {0}".format(e))
        sys.exit(os.EX_CONFIG)

    # Output file
    file = open(OUT_FILENAME, "w", encoding="utf-8")

    total_sent = 0
    total_sent_skipped = 0

    total_arts = 0
    total_arts_skipped = 0

    accumulated = []

    for art in Article.articles({"random": True}):
        if not is_acceptable_article(art):
            total_arts_skipped += 1
            continue

        total_arts += 1

        # Load article tree
        try:
            tree = Tree(url=art.url, authority=art.authority)
            tree.load(art.tree)
        except Exception:
            continue

        # Load simple sentence trees for all sentences in article
        trees = None
        try:
            trees = tree.simple_trees()
        except Exception:
            continue

        # Iterate over each sentence tree, process
        for ix, stree in trees:
            if not is_acceptable_sentence_tree(stree):
                total_sent_skipped += 1
                continue
            elif is_heading_sentence_tree(stree):
                atree = gen_anno_tree(art, ix, stree)
                with open("heading.txt", "a", encoding="utf-8") as headingfile:
                    headingfile.write(str(atree) + SEPARATOR)
                continue
            # Both check if we find something new and add to buckets
            if old_info(stree):
                total_sent_skipped += 1
                continue

            # OK, it's acceptable
            annotree = gen_anno_tree(art, ix, stree)
            # print(annotree)
            accumulated.append(annotree)

        num_acc = len(accumulated)
        if num_acc >= BATCH_SIZE:
            total_sent += num_acc
            shuffle(accumulated)
            # Write sentence trees to file
            for s in accumulated:
                file.write(str(s) + SEPARATOR)
            # Empty our list of acc. sentences
            accumulated = []
            # Trigger manual garbage collection
            gc.collect()
            print(f"{total_sent} sentences accumulated")

        if total_sent >= NUM_SENT:
            # Time to check for missing info
            if not full_buckets():
                # Stop if we haven't stopped by 2M sents
                if total_sent >= LIMIT:
                    break
                continue
            else:
                break

    # All done
    file.close()
    print(f"Total articles: {total_arts}")
    print(f"Total articles skipped: {total_arts_skipped}")
    print(f"Total sentences: {total_sent}")
    print(f"Total sentences skipped: {total_sent_skipped}")


if __name__ == "__main__":
    main()
