#!/usr/bin/env python
# type: ignore
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

KNOWNTERMINALS = [
    "abfn",
    "amount",
    "ao",
    "dagsafs",
    "dagsfast",
    "entity",
    "eo",
    "exp",
    "fn",
    "fs",
    "fyrirtæki",
    "gr",
    "grm",
    "kennitala",
    "lo",
    "lén",
    "myllumerki",
    "mælieining",
    "nhm",
    "no",
    "notandanafn",
    "person",
    "pfn",
    "prósenta",
    "raðnr",
    "sameind",
    "so",
    "st",
    "stt",
    "sérnafn",
    "símanúmer",
    "tala",
    "talameðbókstaf",
    "to",
    "tímapunkturafs",
    "tímapunkturfast",
    "tími",
    "töl",
    "tölvupóstfang",
    "uh",
    "vefslóð",
    "vörunúmer",
    "ártal",
]

KNOWNNONTERMINALS = [
    "S0",
    "S-MAIN",
    "S-QUOTE",
    "S-HEADING",
    "S-PREFIX",
    "S-EXPLAIN",
    "S-QUE",
    "CP-THT",
    "CP-THT-SUBJ",
    "CP-THT-OBJ",
    "CP-THT-IOBJ",
    "CP-THT-PRD",
    "CP-QUE",
    "CP-QUE-SUBJ",
    "CP-QUE-OBJ",
    "CP-QUE-IOBJ",
    "CP-QUE-PRD",
    "CP-REL",
    "CP-ADV-ACK",
    "CP-ADV-CAUSE",
    "CP-ADV-CMP",
    "CP-ADV-COND",
    "CP-ADV-CONS",
    "CP-ADV-PURP",
    "CP-ADV-TEMP",
    "CP-QUOTE",
    "CP-SOURCE",
    "CP-EXPLAIN",
    "IP",
    "IP-INF",
    "IP-INF-SUBJ",
    "IP-INF-OBJ",
    "IP-INF-IOBJ",
    "IP-INF-PRD",
    "VP",
    "VP-AUX",
    "NP-SUBJ",
    "NP-ES",
    "NP-OBJ",
    "NP-IOBJ",
    "NP-PRD",
    "NP-EXPLAIN",
    "NP-POSS",
    "NP-DAT",
    "NP-ADP",
    "NP-AGE",
    "NP-TITLE",
    "NP-PREFIX",
    "NP-AGE",
    "NP-MEASURE",
    "NP-EXCEPT",
    "ADJP",
    "ADVP",
    "ADVP-DIR",
    "ADVP-LOC",
    "ADVP-DATE-ABS",
    "ADVP-DATE-REL",
    "ADVP-TIMESTAMP-ABS",
    "ADVP-TIMESTAMP-REL",
    "ADVP-TMP-SET",
    "ADVP-DUR-ABS",
    "ADVP-DUR-REL",
    "ADVP-DUR-TIME",
    "ADVP-PCL",
    "PP",
    "PP-LOC",
    "PP-DIR",
    "P",
    "TO",
    "C",
    "URL",
]


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
    # Generate hash of normalized sentence text and add
    # it to SENT_HASHES to ensure uniqueness
    text = stree.text
    norm = normalize(text)
    if not norm:
        return False

    md5sum = hashlib.md5(norm.encode("utf-8")).hexdigest()

    # Skip already processed identical sentence
    if md5sum in SENT_HASHES:
        return False

    # Skip sentences that don't contain enough Icelandic words
    if not is_icelandic(stree):
        return False

    # Skip uncapitalized sentences
    if text[0].islower():
        return False

    tokens = text.split()

    # Skip sentences with very few words
    if not len(tokens) >= MIN_SENT_LENGTH:
        return False

    # Skip sentences with only a single NP -- S0→NP
    if stree.match("S0 > [NP $]"):
        return False

    # OK, it has passed our criteria
    # Add sentence to hash set
    SENT_HASHES.add(md5sum)
    # print(text)
    return True


def is_heading_sentence_tree(stree):
    text = stree.text
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

    # TODO halda utan um þær fötur sem eru ekki fullar
    # Þá er hægt að safna í fötur hér
    # Svo er mjög lítið fall sem tékkar á listanum yfir ófullar fötur
    # og ákvarðar hvort þetta sé old_info / full_buckets
    # Hefur í för með sér að hættir að safna þegar fötur eru fullar,
    # endurspeglar ekki sanntíðni
    # Má geyma þær fötur sem eru ekki fullar í set()
    # Þá er fljótt hægt að tékka if bucketset, and set(stree.nonterminal)&bucketset
    # Þarf bara að pæla hvernig tek ákveðið stak úr menginu þegar sú fata fyllist.
    # Byrja svo ekki að tékka á fötunum fyrr en eftir 500þ setningar,
    # ætti ekki að vera mikið um ófullar fötur.
    p = True
    for nonterm in stree.nonterminals:
        phrase = nonterm._head.get("i")
        if NONTERMDICT[phrase] < 1000:
            # We want to add it!
            p = False
        NONTERMDICT[phrase] += 1

    for leaf in stree.leaves:
        cat = leaf._head.get("c")
        if TERMDICT[cat] < 10000:
            p = False
        TERMDICT[cat] += 1

    return p


def full_buckets():
    for nonterm in NONTERMDICT:
        if NONTERMDICT[nonterm] < 100:
            return False
    for term in TERMDICT:
        if TERMDICT[term] < 1000:
            return False
    return True


def initialize_buckets():
    """Assign values to known phrases and leaves"""
    for every in KNOWNNONTERMINALS:
        NONTERMDICT[every] = 0

    for each in KNOWNTERMINALS:
        TERMDICT[each] = 0


def first_threshold(total_sent):
    if total_sent >= NUM_SENT:
        return True
    return False


def last_threshold(total_sent):
    if total_sent >= LIMIT:
        return True
    return False


def normalize(text):
    # Generalize information in sentence to ensure unique sentences in set
    text = text.lower()
    for item in definitions.PUNCTUATION:
        text = text.replace(item, "")
    for num in "0123456789":
        text = text.replace(num, "0")
    text = text.replace(" ", "")
    return text


NUM_SENT = 500000  # 500000
LIMIT = 2000000  # 2000000     # Absolute limit of corpus size
BATCH_SIZE = 1000  # 1000
OUT_FILENAME = "silver.txt"
SEPARATOR = "\n\n"


def main():

    try:
        # Read configuration file
        Settings.read(os.path.join(basepath, "config", "GreynirSimple.conf"))
    except ConfigError as e:
        print("Configuration error: {0}".format(e))
        sys.exit(os.EX_CONFIG)

    initialize_buckets()

    # Output file
    file = open(OUT_FILENAME, "w", encoding="utf-8")

    total_sent = 0
    total_sent_skipped = 0

    total_arts = 0
    total_arts_skipped = 0

    accumulated = []

    for art in Article.articles({"random": True}):
        # if total_sent % 1001 == 1:
        #    print(total_sent)
        if not is_acceptable_article(art):
            total_arts_skipped += 1
            continue

        total_arts += 1

        # Load article tree
        try:
            tree = Tree(url=art.url, authority=art.authority)
            tree.load(art.tree)
        except Exception:
            total_arts_skipped += 1
            continue

        # Load simple sentence trees for all sentences in article
        trees = None
        try:
            trees = tree.simple_trees()
        except Exception:
            total_arts_skipped += 1
            continue

        # Iterate over each sentence tree, process
        for ix, stree in trees:
            if not stree:
                total_sent_skipped += 1
                continue
            if not is_acceptable_sentence_tree(stree):
                total_sent_skipped += 1
                continue
            elif is_heading_sentence_tree(stree):
                atree = gen_anno_tree(art, ix, stree)
                with open("heading.txt", "a", encoding="utf-8") as headingfile:
                    headingfile.write(str(atree) + SEPARATOR)
                continue
            # Both check if we find something new and add to buckets
            if old_info(stree) and first_threshold(total_sent):
                total_sent_skipped += 1
                continue

            # OK, it's acceptable
            annotree = gen_anno_tree(art, ix, stree)
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
            print(f"\t{total_sent_skipped} sentences skipped")

        if last_threshold(total_sent) or total_sent + total_sent_skipped > 12000000:
            # Stop if we've checked 12M total sentences
            break
        elif first_threshold(total_sent) and full_buckets():
            break

    # All done
    file.close()
    with open("stats_silver.txt", "a") as stats:
        stats.write(f"Total articles: {total_arts}\n")
        stats.write(f"Total articles skipped: {total_arts_skipped}\n")
        stats.write(f"Total sentences: {total_sent}\n")
        stats.write(f"Total sentences skipped: {total_sent_skipped}\n")
        for each in NONTERMDICT:
            stats.write(f"{each}:  {NONTERMDICT[each]}\n")

        for each in TERMDICT:
            stats.write(f"{each}:  {TERMDICT[each]}\n")


if __name__ == "__main__":
    main()
