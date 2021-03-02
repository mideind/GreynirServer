#!/usr/bin/env python
# type: ignore

"""

    Greynir: Natural language processing for Icelandic

    POS tagger training program

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


    This program trains a TnT POS tagging model.
    Trained models are stored in the file `config/TnT-model.pickle`.

"""

import os
import sys
from contextlib import contextmanager
import time

# Hack to make this Python program executable from the tools subdirectory
basepath, _ = os.path.split(os.path.realpath(__file__))
_TOOLS = os.sep + "tools"
if basepath.endswith(_TOOLS):
    basepath = basepath[0:-len(_TOOLS)]
    sys.path.append(basepath)

from bindb import BIN_Db
from settings import Settings, ConfigError
from article import Article
from postagger import IFD_Corpus, IFD_Tagset
from tnttagger import TnT


_TNT_MODEL_FILE = os.path.join(basepath, "config", "TnT-model.pickle")


@contextmanager
def timeit(description = "Timing"):
    print("{0}: starting".format(description))
    t0 = time.time()
    yield
    t1 = time.time()
    print("{0}: completed in {1:.2f} seconds".format(description, t1 - t0))


def train_tagger():
    """ Train the TnT tagger and store its model in a pickle file """

    # Number of training and test sentences
    TRAINING_SET = 0 # 25000
    TEST_SET = 400
    BEAM_SIZE = 250 # A higher number does not seem to yield improved results

    tnt_tagger = TnT(N = BEAM_SIZE, C = True)
    if TRAINING_SET:
        with timeit(f"Train TnT tagger on {TRAINING_SET} sentences from articles"):
            # Get a sentence stream from parsed articles
            # Number of sentences, size of training set
            sentence_stream = Article.sentence_stream(limit = TRAINING_SET, skip = TEST_SET)
            word_tag_stream = IFD_Tagset.word_tag_stream(sentence_stream)
            tnt_tagger.train(word_tag_stream)
    with timeit(f"Train TnT tagger on IFD training set"):
        # Get a sentence stream from parsed articles
        # Number of sentences, size of training set
        sample_ratio = 50
        word_tag_stream = IFD_Corpus().word_tag_stream(skip = lambda n: n % sample_ratio == 0)
        tnt_tagger.train(word_tag_stream)
    with timeit(f"Store TnT model trained on {tnt_tagger.count} sentences"):
        tnt_tagger.store(_TNT_MODEL_FILE)


if __name__ == "__main__":

    print("Welcome to the Greynir POS tagging trainer\n")

    try:
        # Read configuration file
        Settings.read(os.path.join(basepath, "config", "Greynir.conf"))
    except ConfigError as e:
        print("Configuration error: {0}".format(e))
        quit()

    # This is always run as a main program
    try:
        with timeit("Training session"):
            train_tagger()
    finally:
        BIN_Db.cleanup()
