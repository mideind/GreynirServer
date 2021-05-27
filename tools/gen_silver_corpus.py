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
from random import shuffle

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


SENT_HASHES = set()


def is_acceptable_article(art):
    if not art.root_domain or "lemurinn" in art.root_domain:
        return False
    return True


def is_acceptable_sentence_tree(stree):
    # Generate hash of sentence text to SENT_HASHES to ensure uniqueness
    txt = stree.text
    md5sum = hashlib.md5(txt.encode("utf-8")).hexdigest()
    if md5sum in SENT_HASHES:
        return False  # Already processed identical sentence

    SENT_HASHES.add(md5sum)

    return True


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


NUM_SENT = 1000
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

    accumulated = []
    total_num_arts = 0

    for art in Article.articles({"random": True}):
        if not is_acceptable_article(art):
            continue

        total_num_arts += 1

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
                # print(stree.text)
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

        if total_sent >= NUM_SENT:
            break


if __name__ == "__main__":
    main()
