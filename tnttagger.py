#!/usr/bin/env python
"""

    Greynir: Natural language processing for Icelandic

    TnT Tagger module

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


    This module is based on the TnT Tagger module from the NLTK Project.
    It has been extensively simplified, adapted and optimized for speed.

    The NLTK copyright notice and license follow:
    --------------------------------------------------------------------

    Natural Language Toolkit: TnT Tagger

    Copyright (C) 2001-2017 NLTK Project
    Author: Sam Huston <sjh900@gmail.com>
    URL: <http://nltk.org/>

    Licensed under the Apache License, Version 2.0 (the 'License');
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an 'AS IS' BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.

    Implementation of 'TnT - A Statistical Part of Speech Tagger'
    by Thorsten Brants
    http://acl.ldc.upenn.edu/A/A00/A00-1031.pdf

"""

from typing import Optional

import os
import time
import pickle
import logging

from math import log
from collections import defaultdict
from contextlib import contextmanager

from reynir.bindb import BIN_Db
from reynir.bintokenizer import raw_tokenize, parse_tokens, paragraphs, TOK
from postagger import NgramTagger


@contextmanager
def timeit(description="Timing"):
    t0 = time.time()
    yield
    t1 = time.time()
    print("{0}: {1:.2f} seconds".format(description, t1 - t0))


class FreqDist(defaultdict):

    """ A frequency distribution for the outcomes of an experiment.  A
        frequency distribution records the number of times each outcome of
        an experiment has occurred. """

    def __init__(
        self, cls=int
    ):  # Note: the cls parameter seems to be required for pickling to work
        """ Construct a new frequency distribution.  If ``samples`` is
            given, then the frequency distribution will be initialized
            with the count of each object in ``samples``; otherwise, it
            will be initialized to be empty. """
        super().__init__(cls)

    def N(self):
        """ Return the total number of sample outcomes that have been
            recorded by this FreqDist. """
        return sum(self.values())

    def freeze_N(self):
        """ Set N permanently to its current value, avoiding multiple recalculations """
        n = self.N()
        setattr(self, "N", lambda: n)

    def freq(self, sample):
        """ Return the frequency of a given sample. """
        n = self.N()
        if n == 0:
            return 0
        return self.get(sample, 0) / n


class ConditionalFreqDist(defaultdict):
    """ A collection of frequency distributions for a single experiment
        run under different conditions. """

    def __init__(
        self, cls=FreqDist
    ):  # Note: the cls parameter seems to be required for pickling to work
        """ Construct a new empty conditional frequency distribution. """
        super().__init__(cls)

    def N(self):
        """ Return the total number of sample outcomes """
        return sum(fdist.N() for fdist in self.values())

    def freeze_N(self):
        """ Freeze the total number of sample outcomes at the current value """
        for fdist in self.values():
            fdist.freeze_N()
        n = self.N()
        setattr(self, "N", lambda: n)


class UnknownWordTagger:

    def __init__(self):
        self._ngram_tagger = NgramTagger()

    def tagset(self, word, at_sentence_start=False):
        """ Return a list of (probability, tag) tuples for the given word """
        toklist = list(parse_tokens(" ".join(word)))
        token = toklist[0]
        w = word[0]
        if token.kind == TOK.WORD and token.val is None:
            try:
                with BIN_Db.get_db() as db:
                    w, m = db.lookup_word(token.txt, at_sentence_start)
            except Exception:
                w, m = token.txt, []
            token = TOK.Word(w, m)
        return self._ngram_tagger.tag_single_token(token)

    def tag(self, word, at_sentence_start=False):
        """ Return a list with a single (word, tag) tuple for the given
            word list, containing a single word """
        taglist = self.tagset(word, at_sentence_start)
        w = word[0]
        if taglist:
            # Sort in descending order of probability
            taglist.sort(key=lambda x: x[1], reverse=True)
            # Return the most likely tag
            return [(w, taglist[0][0])]
        # No taglist: give up and return 'Unk' as the tag
        return [(w, "Unk")]


class TnT:
    """
    TnT - Statistical POS tagger
    (Description from original NLTK source)
    TnT uses a second order Markov model to produce tags for
    a sequence of input, specifically:
      argmax [Proj(P(t_i|t_i-1,t_i-2)P(w_i|t_i))] P(t_T+1 | t_T)
    IE: the maximum projection of a set of probabilities
    The set of possible tags for a given word is derived
    from the training data. It is the set of all tags
    that exact word has been assigned.
    To speed up and get more precision, we can use log addition
    to instead multiplication, specifically:
      argmax [Sigma(log(P(t_i|t_i-1,t_i-2))+log(P(w_i|t_i)))] +
             log(P(t_T+1|t_T))
    The probability of a tag for a given word is the linear
    interpolation of 3 markov models; a zero-order, first-order,
    and a second order model.
      P(t_i| t_i-1, t_i-2) = l1*P(t_i) + l2*P(t_i| t_i-1) +
                             l3*P(t_i| t_i-1, t_i-2)
    A beam search is used to limit the memory usage of the algorithm.
    The degree of the beam can be changed using N in the initialization.
    N represents the maximum number of possible solutions to maintain
    while tagging.
    It is possible to differentiate the tags which are assigned to
    capitalized words. However this does not result in a significant
    gain in the accuracy of the results.
    """

    def __init__(self, N=1000, C=False):
        """
        Construct a TnT statistical tagger. Tagger must be trained
        before being used to tag input.
        :param unk: instance of a POS tagger, conforms to TaggerI
        :type  unk:(TaggerI)
        :param N: Beam search degree (see above)
        :type  N:(int)
        :param C: Capitalization flag
        :type  C: boolean
        Initializer, creates frequency distributions to be used
        for tagging
        _lx values represent the portion of the tri/bi/uni taggers
        to be used to calculate the probability
        N value is the number of possible solutions to maintain
        while tagging. A good value for this is 1000
        C is a boolean value which specifies to use or
        not use the Capitalization of the word as additional
        information for tagging.
        NOTE: using capitalization may not increase the accuracy
        of the tagger
        """
        self._uni = FreqDist()
        self._bi = ConditionalFreqDist()
        self._tri = ConditionalFreqDist()
        self._wd = ConditionalFreqDist()
        self._l1 = 0.0
        self._l2 = 0.0
        self._l3 = 0.0
        self._N = N
        self._C = C

        self._unk = UnknownWordTagger()

        self._training = True  # In training phase?
        self._count = 0  # Trained sentences

        # statistical tools (ignore or delete me)
        self.unknown = 0
        self.known = 0

    def __getstate__(self):
        """ Obtain the state of this object to be pickled """
        state = self.__dict__.copy()
        del state["_unk"]
        return state

    def __setstate__(self, state):
        """ Restore the state of this object from a pickle """
        self.__dict__.update(state)
        self._unk = UnknownWordTagger()

    def _freeze_N(self):
        """ Make sure all contained FreqDicts are 'frozen' """
        self._uni.freeze_N()
        self._bi.freeze_N()
        self._tri.freeze_N()
        self._wd.freeze_N()

    def _finish_training(self):
        """ Freeze the current frequency counts and compute lambdas """
        if self._training:
            self._freeze_N()
            self._compute_lambda()
            # Training completed
            self._training = False

    @property
    def count(self):
        return self._count

    def store(self, filename):
        """ Store a previously trained model in a file """
        self._finish_training()
        with open(filename, "wb") as file:
            pickle.dump(self, file, protocol=pickle.HIGHEST_PROTOCOL)

    @staticmethod
    def load(filename):
        """ Load a previously trained and stored model from file """
        try:
            with open(filename, "rb") as file:
                tagger = pickle.load(file)
            assert not tagger._training
            tagger._freeze_N()
            return tagger
        except OSError:
            return None

    def train(self, sentences):
        """
        Uses a set of tagged data to train the tagger.
        :param data: List of lists of (word, tag) tuples
        :type data: tuple(str)
        """
        for sent in sentences:
            history = (("BOS", False), ("BOS", False))
            self._count += 1
            for w, t in sent:

                # if capitalization is requested,
                # and the word begins with a capital
                # set local flag C to True
                C = self._C and w[0].isupper()
                tC = (t, C)

                self._wd[w][t] += 1
                self._uni[tC] += 1
                self._bi[history[1]][tC] += 1
                self._tri[history][tC] += 1

                history = (history[1], tC)

    def _compute_lambda(self):
        """
        creates lambda values based upon training data
        NOTE: no need to explicitly reference C,
        it is contained within the tag variable :: tag == (tag,C)
        for each tag trigram (t1, t2, t3)
        depending on the maximum value of
        - f(t1,t2,t3)-1 / f(t1,t2)-1
        - f(t2,t3)-1 / f(t2)-1
        - f(t3)-1 / N-1
        increment l3,l2, or l1 by f(t1,t2,t3)
        ISSUES -- Resolutions:
        if 2 values are equal, increment both lambda values
        by (f(t1,t2,t3) / 2)
        """

        # temporary lambda variables
        tl1 = 0.0
        tl2 = 0.0
        tl3 = 0.0

        uni_N = self._uni.N() - 1

        # for each t1,t2 in system
        for history in self._tri:
            (_, h2) = history

            bi = self._bi[h2]
            bi_N = bi.N() - 1
            tri = self._tri[history]
            tri_N = tri.N() - 1

            # for each t3 given t1,t2 in system
            # (NOTE: tag actually represents (tag,C))
            # However no effect within this function
            for tag in tri:

                # if there has only been 1 occurrence of this tag in the data
                # then ignore this trigram.
                uni = self._uni[tag]
                if uni == 1:
                    continue

                # safe_div provides a safe floating point division
                # it returns -1 if the denominator is 0
                c3 = self._safe_div(tri[tag] - 1, tri_N)
                c2 = self._safe_div(bi[tag] - 1, bi_N)
                c1 = self._safe_div(uni - 1, uni_N)

                # if c1 is the maximum value:
                if (c1 > c3) and (c1 > c2):
                    tl1 += tri[tag]

                # if c2 is the maximum value
                elif (c2 > c3) and (c2 > c1):
                    tl2 += tri[tag]

                # if c3 is the maximum value
                elif (c3 > c2) and (c3 > c1):
                    tl3 += tri[tag]

                # if c3, and c2 are equal and larger than c1
                elif (c3 == c2) and (c3 > c1):
                    half = tri[tag] / 2.0
                    tl2 += half
                    tl3 += half

                # if c1, and c2 are equal and larger than c3
                # this might be a dumb thing to do....(not sure yet)
                elif (c2 == c1) and (c1 > c3):
                    half = tri[tag] / 2.0
                    tl1 += half
                    tl2 += half

                # otherwise there might be a problem
                # eg: all values = 0
                else:
                    # print "Problem", c1, c2 ,c3
                    pass

        # Lambda normalisation:
        # ensures that l1+l2+l3 = 1
        self._l1 = tl1 / (tl1 + tl2 + tl3)
        self._l2 = tl2 / (tl1 + tl2 + tl3)
        self._l3 = tl3 / (tl1 + tl2 + tl3)

    def _safe_div(self, v1, v2):
        """
        Safe floating point division function, does not allow division by 0
        returns -1 if the denominator is 0
        """
        return -1 if v2 == 0 else v1 / v2

    def tag_sents(self, sentences):
        """
        Tags each sentence in a list of sentences
        :param data:list of list of words
        :type data: [[string,],]
        :return: list of list of (word, tag) tuples
        Invokes tag(sent) function for each sentence
        compiles the results into a list of tagged sentences
        each tagged sentence is a list of (word, tag) tuples
        """
        return [self.tag(sent) for sent in sentences]

    def tag(self, sentence):
        """
        Tags a single sentence
        :param data: list of words
        :type data: [string,]
        :return: [(word, tag),]
        Calls recursive function '_tagword'
        to produce a list of tags
        Associates the sequence of returned tags
        with the correct words in the input sequence
        returns a list of (word, tag) tuples
        """
        if self._training:
            self._finish_training()

        sent = list(sentence)
        _wd = self._wd
        _uni = self._uni
        _bi = self._bi
        _tri = self._tri
        _C = self._C

        current_state = [(0.0, [("BOS", False), ("BOS", False)])]
        keyfunc = lambda x: x[0]

        for index, word in enumerate(sent):

            new_state = []

            # if the Capitalisation is requested,
            # initalise the flag for this word
            C = _C and word[0].isupper()

            # if word is known
            # compute the set of possible tags
            # and their associated log probabilities
            if word in _wd:
                self.known += 1

                for (curr_sent_logprob, history) in current_state:

                    h1 = history[-1]
                    h2 = tuple(history[-2:])

                    for t in _wd[word]:
                        tC = (t, C)
                        p_uni = _uni.freq(tC)
                        p_bi = _bi[h1].freq(tC)
                        p_tri = _tri[h2].freq(tC)
                        p_wd = _wd[word][t] / _uni[tC]
                        p = self._l1 * p_uni + self._l2 * p_bi + self._l3 * p_tri
                        p2 = log(p) + log(p_wd)

                        new_state.append((curr_sent_logprob + p2, history + [tC]))

            else:
                # otherwise a new word, set of possible tags is unknown
                self.unknown += 1

                taglist = None
                if self._unk is not None:
                    # Apply the unknown word tagger
                    taglist = self._unk.tagset([word], index == 0)
                if not taglist:
                    # if no unknown word tagger has been specified
                    # or no tag is found, use the tag 'Unk'
                    taglist = [("Unk", 1.0)]

                for (curr_sent_logprob, history) in current_state:
                    for t, prob in taglist:
                        new_state.append(
                            (curr_sent_logprob + log(prob), history + [(t, C)])
                        )

            # now have computed a set of possible new_states

            # sort states by log prob
            new_state.sort(reverse=True, key=keyfunc)

            # set is now ordered greatest to least log probability
            # del everything after N (threshold)
            # this is the beam search cut
            current_state = new_state[0 : self._N]

        # return the most probable tag history
        tags = current_state[0][1]
        return [(w, tags[i + 2][0]) for i, w in enumerate(sent)]


# Global tagger singleton instance
_TAGGER = None  # type: Optional[TnT]

# Translation dictionary
_XLT = {"—": "-", "–": "-"}


def ifd_tag(text):
    """ Tokenize the given text and use a global singleton TnT tagger to tag it """
    global _TAGGER
    if _TAGGER is None:
        # Load the tagger from a pickle the first time it's used
        fname = os.path.join("config", "TnT-model.pickle")
        logging.info("Loading TnT model from {0}".format(fname))
        _TAGGER = TnT.load(fname)
        if _TAGGER is None:
            return []  # No tagger model - unable to tag

    token_stream = raw_tokenize(text)
    result = []

    def xlt(txt):
        """ Translate the token text as required before tagging it """
        if txt[0] == "[" and txt[-1] == "]":
            # Abbreviation enclosed in square brackets: remove'em
            return txt[1:-1]
        return _XLT.get(txt, txt)

    for pg in paragraphs(token_stream):
        for _, sent in pg:
            toklist = [xlt(t.txt) for t in sent if t.txt]
            # print(f"Toklist: {toklist}")
            tagged = _TAGGER.tag(toklist)
            result.append(tagged)

    # Return a list of paragraphs, consisting of sentences, consisting of tokens
    return result
