#!/usr/bin/env python

import os
import sys
import json
from contextlib import contextmanager
import time

import xml.etree.ElementTree as ET

# Hack to make this Python program executable from the utils subdirectory
basepath, _ = os.path.split(os.path.realpath(__file__))
_UTILS = os.sep + "utils"
if basepath.endswith(_UTILS):
    basepath = basepath[0:-len(_UTILS)]
    sys.path.append(basepath)

from bindb import BIN_Db
from settings import Settings, ConfigError
from tokenizer import tokenize, TOK
from scraperdb import SessionContext, desc, Article as ArticleRow
from article import Article
from postagger import NgramTagger, IFD_Tagset
from tnttagger import TnT


_TNT_MODEL_FILE = "config" + os.sep + "TnT-model.pickle"


@contextmanager
def timeit(description = "Timing"):
    t0 = time.time()
    yield
    t1 = time.time()
    print("{0}: {1:.2f} seconds".format(description, t1 - t0))


class IFD_Corpus:

    def __init__(self, ifd_dir = "ifd"):
        self._ifd_full_dir = os.path.join(os.getcwd(), ifd_dir)
        self._xml_files = [ x for x in os.listdir(self._ifd_full_dir) if x.startswith("A") and x.endswith(".xml") ]
        self._xml_files.sort()

    def raw_sentence_stream(self, limit = None, skip = None):
        """ Generator of sentences from the IFD XML files.
            Each sentence consists of (word, tag, lemma) triples. """
        count = 0
        skipped = 0
        for each in self._xml_files:
            filename = os.path.join(self._ifd_full_dir, each)
            tree = ET.parse(filename)
            root = tree.getroot()
            for sent in root.iter("s"):
                if len(sent): # Using a straight Bool test here gives a warning
                    if skip is not None and skipped < skip:
                        # If a skip parameter was given, skip that number of sentences up front
                        skipped += 1
                        continue
                    yield [
                        (word.text.strip(), word.get("type") or "", word.get("lemma") or word.text.strip())
                        for word in sent
                    ]
                    count += 1
                    if limit is not None and count >= limit:
                        return

    def sentence_stream(self, limit = None, skip = None):
        """ Generator of sentences from the IFD XML files.
            Each sentence is a list of words. """
        for sent in self.raw_sentence_stream(limit, skip):
            yield [ w for (w, _, _) in sent ]

    def word_tag_stream(self, limit = None, skip = None):
        """ Generator of sentences from the IFD XML files.
            Each sentence consists of (word, tag) pairs. """
        for sent in self.raw_sentence_stream(limit, skip):
            yield [ (w, t) for (w, t, _) in sent ]


def test_tagger():

    TEST_SENTENCE = """
Við þá vinnu hefur meðal annars verið unnið á grundvelli niðurstaðna sérfræðihóps sem skilaði
greinargerð um samkeppnishæfni þjóðarbúsins í ljósi styrkingar krónunnar til ráðherranefndar
um efnahagsmál í byrjun febrúar.
 """

# Jón bauð forsætisráðherra á fund

#Ögmundur Jónasson fyrrverandi ráðherra og þingmaður vill bjóða Bjarna Benediktssyni forsætisráðherra
#á fund í Iðnó á morgun.

#Jón og Guðmundur greiddu atkvæði gegn málinu enda eru þeir sannfærðir um að betri lausn muni finnast.

    print("Initializing tagger")

    # Number of training and test sentences
    TRAINING_SET = 500
    IFD_TRAINING_SET = 21000 # There are only about 20.800 sentences in the IFD corpus
    TEST_SET = 400
    BEAM_SIZE = 250 # A higher number does not seem to yield improved results


    if False:
        tnt_tagger = TnT(N = BEAM_SIZE, C = True)
        tagger = NgramTagger(n = 3, verbose = False)
        # Create a new model and store it
        with timeit("Train NgramTagger"):
            # Get a sentence stream from parsed articles
            # Number of sentences, size of training set
            sentence_stream = Article.sentence_stream(limit = TRAINING_SET, skip = TEST_SET)
            tagger.train(sentence_stream)
        with timeit("Train TnT_Tagger on articles"):
            # Get a sentence stream from parsed articles
            # Number of sentences, size of training set
            sentence_stream = Article.sentence_stream(limit = TRAINING_SET, skip = TEST_SET)
            word_tag_stream = IFD_Tagset.word_tag_stream(sentence_stream)
            tnt_tagger.train(word_tag_stream)
        with timeit("Train TnT_Tagger on IFD"):
            # Get a sentence stream from parsed articles
            # Number of sentences, size of training set
            word_tag_stream = IFD_Corpus().word_tag_stream(limit = IFD_TRAINING_SET, skip = TEST_SET)
            tnt_tagger.train(word_tag_stream)
        with timeit("Store TnT model"):
            tnt_tagger.store(_TNT_MODEL_FILE)
    else:
        tagger = None
        # Load an existing model
        with timeit("load_model()"):
            tnt_tagger = TnT.load(_TNT_MODEL_FILE)
            if tnt_tagger is None:
                print(f"Unable to load TnT model from {_TNT_MODEL_FILE}, test aborted")
                return
    #tagger.show_model()
    #return

    total_tags = 0
    correct_tag = 0
    partial_tag = 0
    missing_tag = 0
    correct_tag_tnt = 0
    partial_tag_tnt = 0
    missing_tag_tnt = 0


    def simple_test(session):
        txt = "Þau segja að börn hafi gott af því."
        toklist = tokenize(txt, enclosing_session = session)
        dlist = tagger.tag(toklist)
        print("Sentence: '{0}'".format(txt))
        print("Tagging result:\n{0}".format("\n".join(str(d) for d in dlist)))


    def article_test(session):
        sentence_stream = Article.sentence_stream(limit = TEST_SET)
        for sent in sentence_stream:
            txt = " ".join(t["x"] for t in sent if "x" in t)
            if txt:
                toklist = tokenize(txt, enclosing_session = session)
                dlist = tagger.tag(toklist)
                print("Sentence: '{0}'".format(txt))
                print("Tagging result:\n{0}".format("\n".join(str(d) for d in dlist)))


    def test_ifd_file(session):
        print("\n\n*** IFD TEST SET ***\n\n")
        gen = IFD_Corpus().raw_sentence_stream(limit = TEST_SET)
        dlist = None
        for sent in gen:
            orðalisti = [ triple[0] for triple in sent ]
            mörk_OTB = [ triple[1] for triple in sent ]
            lemmur_OTB = [ triple[2] for triple in sent ]
            txt = " ".join(orðalisti)
            if tagger is not None:
                toklist = tokenize(txt, enclosing_session = session)
                dlist = tagger.tag(toklist)
            tntlist = tnt_tagger.tag(orðalisti)
            ix = 0
            print("\n{0}\n".format(txt))
            for tag, lemma, word, tnt_wt in zip(mörk_OTB, lemmur_OTB, orðalisti, tntlist):
                tnt_tag = tnt_wt[1]
                j = ix
                if dlist is None:
                    gtag = "?"
                else:
                    while j < len(dlist) and dlist[j].get("x", "") != word:
                        j += 1
                    if j < len(dlist):
                        ix = j
                        gtag = dlist[ix].get("i", "?")
                        if gtag == "?" and dlist[ix].get("k") == TOK.PUNCTUATION:
                            gtag = word
                        ix += 1
                    else:
                        gtag = "?"

                def grade(gtag):
                    if gtag == "?" and tag != "?":
                        return "M"
                    if gtag == tag:
                        return " "
                    if gtag[0] == tag[0]:
                        return "P"
                    return "E"

                grade_g = grade(gtag)
                grade_tnt = grade(tnt_tag)

                print("{0:20} | {1:20} | {2:8} | {3:8} | {4} | {5:8} | {6}"
                    .format(word, lemma or word, tag, gtag, grade(gtag), tnt_tag, grade(tnt_tag)))
                nonlocal total_tags, missing_tag, correct_tag, partial_tag
                nonlocal missing_tag_tnt, correct_tag_tnt, partial_tag_tnt
                total_tags += 1
                if grade_g == "M":
                    missing_tag += 1
                elif grade_g == " ":
                    correct_tag += 1
                elif grade_g == "P":
                    partial_tag += 1
                if grade_tnt == "M":
                    missing_tag_tnt += 1
                elif grade_tnt == " ":
                    correct_tag_tnt += 1
                elif grade_tnt == "P":
                    partial_tag_tnt += 1

    with SessionContext(read_only = True, commit = True) as session:

        #simple_test(session)

        #article_test(session)

        test_ifd_file(session)

    if total_tags:
        print("\n-----------------------------------\n")
        print("Total tags:   {0:8}".format(total_tags))
        print("\nNgram tagger:\n")
        print("Missing tags: {0:8} {1:6.2f}%"
            .format(missing_tag, 100.0 * missing_tag / total_tags))
        print("Tagged:       {0:8} {1:6.2f}%"
            .format(total_tags - missing_tag, 100.0 * (total_tags - missing_tag) / total_tags))
        print("Correct tags: {0:8} {1:6.2f}%"
            .format(correct_tag, 100.0 * correct_tag / total_tags))
        print("Partial tags: {0:8} {1:6.2f}%"
            .format(partial_tag + correct_tag, 100.0 * (partial_tag + correct_tag) / total_tags))
        print("Partial prec: {0:8} {1:6.2f}%"
            .format("", 100.0 * (partial_tag + correct_tag) / (total_tags - missing_tag)))
        print("Precision:    {0:8} {1:6.2f}%"
            .format("", 100.0 * correct_tag / (total_tags - missing_tag)))
        print("\nTnT tagger:\n")
        print("Missing tags: {0:8} {1:6.2f}%"
            .format(missing_tag_tnt, 100.0 * missing_tag_tnt / total_tags))
        print("Tagged:       {0:8} {1:6.2f}%"
            .format(total_tags - missing_tag_tnt, 100.0 * (total_tags - missing_tag_tnt) / total_tags))
        print("Correct tags: {0:8} {1:6.2f}%"
            .format(correct_tag_tnt, 100.0 * correct_tag_tnt / total_tags))
        print("Partial tags: {0:8} {1:6.2f}%"
            .format(partial_tag_tnt + correct_tag_tnt, 100.0 * (partial_tag_tnt + correct_tag_tnt) / total_tags))
        print("Partial prec: {0:8} {1:6.2f}%"
            .format("", 100.0 * (partial_tag_tnt + correct_tag_tnt) / (total_tags - missing_tag_tnt)))
        print("Precision:    {0:8} {1:6.2f}%"
            .format("", 100.0 * correct_tag_tnt / (total_tags - missing_tag_tnt)))
        print("\n-----------------------------------\n")


if __name__ == "__main__":

    try:
        # Read configuration file
        Settings.read(os.path.join(basepath, "config/Reynir.conf"))
    except ConfigError as e:
        print("Configuration error: {0}".format(e))
        quit()

    # This is always run as a main program
    try:
        with timeit("test_tagger()"):
            test_tagger()
    finally:
        BIN_Db.cleanup()
