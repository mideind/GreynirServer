#!/usr/bin/env python
"""

    Reynir: Natural language processing for Icelandic

    TnT Tagger module

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


    This module is based on the TnT Tagger module from the NLTK Project.
    It has been simplified, adapted and optimized for speed.

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

import time
import operator
from functools import reduce
from itertools import chain
from contextlib import closing

from math import log
from operator import itemgetter
from collections import defaultdict, Counter
from contextlib import contextmanager

from bindb import BIN_Db
from tokenizer import canonicalize_token, parse_tokens, TOK
from article import Article
from postagger import IFD_Tagset, NgramTagger


@contextmanager
def timeit(description = "Timing"):
    t0 = time.time()
    yield
    t1 = time.time()
    print("{0}: {1:.2f} seconds".format(description, t1 - t0))


class FreqDist(Counter):
    
    """ A frequency distribution for the outcomes of an experiment.  A
        frequency distribution records the number of times each outcome of
        an experiment has occurred. """

    def __init__(self, samples=None):
        """ Construct a new frequency distribution.  If ``samples`` is
            given, then the frequency distribution will be initialized
            with the count of each object in ``samples``; otherwise, it
            will be initialized to be empty. """
        super().__init__(samples)

    def N(self):
        """ Return the total number of sample outcomes that have been
            recorded by this FreqDist. """
        return sum(self.values())

    def freeze_N(self):
        """ Set N permanently to its current value, avoiding multiple recalculations """
        n = self.N()
        self.N = lambda: n

    def freq(self, sample):
        """ Return the frequency of a given sample. """
        n = self.N()
        if n == 0:
            return 0
        return self.get(sample, 0) / n


class ConditionalFreqDist(defaultdict):
    """ A collection of frequency distributions for a single experiment
        run under different conditions. """

    def __init__(self):
        """ Construct a new empty conditional frequency distribution. """
        super().__init__(FreqDist)

    def N(self):
        """ Return the total number of sample outcomes """
        return sum(fdist.N() for fdist in self.values())

    def freeze_N(self):
        """ Freeze the total number of sample outcomes at the current value """
        for fdist in self.values():
            fdist.freeze_N()
        n = self.N()
        self.N = lambda: n


class UnknownWordTagger:

    def __init__(self):
        self._ngram_tagger = NgramTagger()

    def tag(self, word, at_sentence_start = False):
        """ Given a list of unknown words (which currently always has length 1),
            return a list of (word, tag) tuples """
        toklist = list(parse_tokens(" ".join(word)))
        token = toklist[0]
        w = word[0]
        if token.kind == TOK.WORD and token.val is None:
            with closing(BIN_Db.get_db()) as db:
                w, m = db.lookup_word(token.txt, at_sentence_start)
            token = TOK.Word(w, m)
        taglist = self._ngram_tagger.tag_single_token(token)
        if taglist:
            # Sort in descending order of probability
            taglist.sort(key = lambda x: x[1], reverse = True)
            # Return the most likely tag
            #print(f"UnknownWordTagger('{word}') returning {(w, taglist[0][0])}")
            return [ (w, taglist[0][0]) ]
        # No taglist: give up and return 'Unk' as the tag
        #print(f"UnknownWordTagger('{word}') returning {(w, 'Unk')}")
        return [ (w, 'Unk') ]


class TnT:
    '''
    TnT - Statistical POS tagger
    IMPORTANT NOTES:
    * DOES NOT AUTOMATICALLY DEAL WITH UNSEEN WORDS
      - It is possible to provide an untrained POS tagger to
        create tags for unknown words, see __init__ function
    * SHOULD BE USED WITH SENTENCE-DELIMITED INPUT
      - Due to the nature of this tagger, it works best when
        trained over sentence delimited input.
      - However it still produces good results if the training
        data and testing data are separated on all punctuation eg: [,.?!]
      - Input for training is expected to be a list of sentences
        where each sentence is a list of (word, tag) tuples
      - Input for tag function is a single sentence
        Input for tagdata function is a list of sentences
        Output is of a similar form
    * Function provided to process text that is unsegmented
      - Please see basic_sent_chop()
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
    '''

    def __init__(self, unk=None, N=1000, C=False):
        '''
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
        '''
        self._uni  = FreqDist()
        self._bi   = ConditionalFreqDist()
        self._tri  = ConditionalFreqDist()
        self._wd   = ConditionalFreqDist()
        self._l1   = 0.0
        self._l2   = 0.0
        self._l3   = 0.0
        self._N    = N
        self._C    = C

        self._unk = UnknownWordTagger() if unk is None else unk

        # statistical tools (ignore or delete me)
        self.unknown = 0
        self.known = 0

    def train(self, sentences):
        '''
        Uses a set of tagged data to train the tagger.
        If an unknown word tagger is specified,
        it is trained on the same data.
        :param data: List of lists of (word, tag) tuples
        :type data: tuple(str)
        '''
        count = 0
        for sent in sentences:
            history = (('BOS',False), ('BOS',False))
            count += 1
            for w, t in sent:

                # if capitalization is requested,
                # and the word begins with a capital
                # set local flag C to True
                C = self._C and w[0].isupper()
                tC = (t,C)

                self._wd[w][t] += 1
                self._uni[tC] += 1
                self._bi[history[1]][tC] += 1
                self._tri[history][tC] += 1

                history = (history[1], tC)

        # Freeze the current total counts
        self._uni.freeze_N()
        self._bi.freeze_N()
        self._tri.freeze_N()
        self._wd.freeze_N()

        # compute lambda values from the trained frequency distributions
        self._compute_lambda()
        print(f"Training session finished; {count} sentences processed")

    def _compute_lambda(self):
        '''
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
        '''

        # temporary lambda variables
        tl1 = 0.0
        tl2 = 0.0
        tl3 = 0.0

        # for each t1,t2 in system
        for history in self._tri.keys():
            (h1, h2) = history

            # for each t3 given t1,t2 in system
            # (NOTE: tag actually represents (tag,C))
            # However no effect within this function
            for tag in self._tri[history].keys():

                # if there has only been 1 occurrence of this tag in the data
                # then ignore this trigram.
                if self._uni[tag] == 1:
                    continue

                # safe_div provides a safe floating point division
                # it returns -1 if the denominator is 0
                c3 = self._safe_div((self._tri[history][tag]-1), (self._tri[history].N()-1))
                c2 = self._safe_div((self._bi[h2][tag]-1), (self._bi[h2].N()-1))
                c1 = self._safe_div((self._uni[tag]-1), (self._uni.N()-1))

                # if c1 is the maximum value:
                if (c1 > c3) and (c1 > c2):
                    tl1 += self._tri[history][tag]

                # if c2 is the maximum value
                elif (c2 > c3) and (c2 > c1):
                    tl2 += self._tri[history][tag]

                # if c3 is the maximum value
                elif (c3 > c2) and (c3 > c1):
                    tl3 += self._tri[history][tag]

                # if c3, and c2 are equal and larger than c1
                elif (c3 == c2) and (c3 > c1):
                    half = self._tri[history][tag] / 2.0
                    tl2 += half
                    tl3 += half

                # if c1, and c2 are equal and larger than c3
                # this might be a dumb thing to do....(not sure yet)
                elif (c2 == c1) and (c1 > c3):
                    half = self._tri[history][tag] / 2.0
                    tl1 += half
                    tl2 += half

                # otherwise there might be a problem
                # eg: all values = 0
                else:
                    #print "Problem", c1, c2 ,c3
                    pass

        # Lambda normalisation:
        # ensures that l1+l2+l3 = 1
        self._l1 = tl1 / (tl1 + tl2 + tl3)
        self._l2 = tl2 / (tl1 + tl2 + tl3)
        self._l3 = tl3 / (tl1 + tl2 + tl3)

    def _safe_div(self, v1, v2):
        '''
        Safe floating point division function, does not allow division by 0
        returns -1 if the denominator is 0
        '''
        return -1 if v2 == 0 else v1 / v2

    def tag_sents(self, sentences):
        '''
        Tags each sentence in a list of sentences
        :param data:list of list of words
        :type data: [[string,],]
        :return: list of list of (word, tag) tuples
        Invokes tag(sent) function for each sentence
        compiles the results into a list of tagged sentences
        each tagged sentence is a list of (word, tag) tuples
        '''
        return [ self.tag(sent) for sent in sentences ]

    def tag(self, sentence):
        '''
        Tags a single sentence
        :param data: list of words
        :type data: [string,]
        :return: [(word, tag),]
        Calls recursive function '_tagword'
        to produce a list of tags
        Associates the sequence of returned tags
        with the correct words in the input sequence
        returns a list of (word, tag) tuples
        '''
        sent = list(sentence)
        len_sent = len(sent)
        _wd = self._wd
        _uni = self._uni
        _bi = self._bi
        _tri = self._tri
        _C = self._C

        def _tagword(index, current_states):
            """ Tags the indicated word in the sentence and
                recursively tags the reminder of sentence
                Uses formula specified above to calculate the probability
                of a particular tag """

            # if this word marks the end of the sentance,
            # return the most probable tag
            if index >= len_sent:
                (history, logp) = current_states[0]
                return history

            # otherwise there are more words to be tagged
            word = sent[index]
            new_states = []

            # if the Capitalisation is requested,
            # initalise the flag for this word
            C = _C and word[0].isupper()

            # if word is known
            # compute the set of possible tags
            # and their associated log probabilities
            if word in _wd:
                self.known += 1

                for (history, curr_sent_logprob) in current_states:

                    h1 = history[-1]
                    h2 = tuple(history[-2:])

                    for t in _wd[word].keys():
                        tC = (t,C)
                        p_uni = _uni.freq(tC)
                        p_bi = _bi[h1].freq(tC)
                        p_tri = _tri[h2].freq(tC)
                        p_wd = _wd[word][t] / _uni[tC]
                        p = self._l1 * p_uni + self._l2 * p_bi + self._l3 * p_tri
                        p2 = log(p) + log(p_wd)

                        new_states.append((history + [ tC ], curr_sent_logprob + p2))

            else:
                # otherwise a new word, set of possible tags is unknown
                self.unknown += 1

                # if no unknown word tagger has been specified
                # then use the tag 'Unk'
                if self._unk is None:
                    tag = ('Unk',C)
                else:
                    # otherwise apply the unknown word tagger
                    [(_w, t)] = list(self._unk.tag([word], index == 0))
                    tag = (t,C)

                for (history, logprob) in current_states:
                    history.append(tag)

                new_states = current_states

            # now have computed a set of possible new_states

            # sort states by log prob
            # set is now ordered greatest to least log probability
            new_states.sort(reverse=True, key=itemgetter(1))

            # del everything after N (threshold)
            # this is the beam search cut
            if len(new_states) > self._N:
                new_states = new_states[:self._N]

            # compute the tags for the rest of the sentence
            # return the best list of tags for the sentence
            return _tagword(index + 1, new_states)

        current_state = [([('BOS',False), ('BOS',False)], 0.0)]
        tags = _tagword(0, current_state)
        return [ (w, tags[i + 2][0]) for i, w in enumerate(sent) ]

    def evaluate(self, gold):
        """
        Score the accuracy of the tagger against the gold standard.
        Strip the tags from the gold standard text, retag it using
        the tagger, then compute the accuracy score.
        :type gold: list(list(tuple(str, str)))
        :param gold: The list of tagged sentences to score the tagger on.
        :rtype: float
        """
        def accuracy(reference, test):
            """
            Given a list of reference values and a corresponding list of test
            values, return the fraction of corresponding values that are
            equal.  In particular, return the fraction of indices
            ``0<i<=len(test)`` such that ``test[i] == reference[i]``.
            :type reference: list
            :param reference: An ordered list of reference values.
            :type test: list
            :param test: A list of values to compare against the corresponding
                reference values.
            :raise ValueError: If ``reference`` and ``length`` do not have the
                same length.
            """
            if len(reference) != len(test):
                raise ValueError("Lists must have the same length.")
            return sum(x == y for x, y in zip(reference, test)) / len(test)

        def untag(tagged_sentence):
            """
            Given a tagged sentence, return an untagged version of that
            sentence.  I.e., return a list containing the first element
            of each tuple in *tagged_sentence*.
                >>> from nltk.tag.util import untag
                >>> untag([('John', 'NNP'), ('saw', 'VBD'), ('Mary', 'NNP')])
                ['John', 'saw', 'Mary']
            """
            return [ w for (w, t) in tagged_sentence ]

        tagged_sents = self.tag_sents(untag(sent) for sent in gold)
        gold_tokens = list(chain(*gold))
        test_tokens = list(chain(*tagged_sents))
        return accuracy(gold_tokens, test_tokens)


def demo():

    N = 400000
    print("TnT tagging test using {0} raw sentences".format(N))

    with timeit("Collecting raw data"):
        raw_sents = [ s for s in Article.sentence_stream(limit = N) ]

    print("{0} raw sentences read".format(len(raw_sents)))

    def tagged_sents(slist):
        for s in slist:
            if not s:
                continue
            r = []
            for t in s:
                if "x" in t:
                    x = t["x"]
                    k = t.get("k", TOK.WORD)
                    if k == TOK.PUNCTUATION:
                        r.append((x, x))
                    else:
                        canonicalize_token(t)
                        tag = str(IFD_Tagset(t))
                        # Split up person names, compounds ('fjármála- og efnahagsráðuneyti'),
                        # multi-word phrases, dates, etc.
                        if " " in x:
                            for part in x.split():
                                # !!! TODO: this needs to be made more intelligent and detailed
                                if part in { "og", "eða" }:
                                    r.append((part, "c"))
                                else:
                                    r.append((part, tag or "[UNKNOWN]"))
                        else:
                            r.append((x, tag or "[UNKNOWN]"))
            if r:
                yield r

    def untagged_sents(slist):
        for s in slist:
            if s:
                yield reduce(operator.add, [ t["x"].split() for t in s if "x" in t ])

    with timeit("Tag training sentences"):
        sents = [ s for s in tagged_sents(raw_sents) ]
    with timeit("Collect 200 test sentences"):
        test = [ s for s in untagged_sents(raw_sents[0:200]) ]

    print("{0} tagged training sentences read".format(len(sents)))
    print("{0} untagged test sentences read".format(len(test)))

    # create and train the tagger
    tagger = TnT(N = 1000)
    with timeit("Train TnT tagger"):
        tagger.train(sents[200:])

    print("\nResult:\n")

    T = 200
    with timeit("Tag {0} sentences".format(T)):
        tacc = tagger.evaluate(sents[0:T])
    tp_un = tagger.unknown / (tagger.known + tagger.unknown)
    tp_kn = tagger.known / (tagger.known + tagger.unknown)

    print("Accuracy:                  {0:6.2f}%".format(tacc * 100.0))
    print('Percentage known:          {0:6.2f}%'.format(tp_kn * 100.0))
    print('Percentage unknown:        {0:6.2f}%'.format(tp_un * 100.0))
    print('Accuracy over known words: {0:6.2f}%'.format((tacc / tp_kn) * 100.0))

    if False:
        # print results
        for sent_tagged, sent_test in zip(tagged_data, sents):
            for si, ti in zip(sent_tagged, sent_test):
                print(si, '--', ti)
            print()


def demo2():
    from nltk.corpus import treebank

    d = list(treebank.tagged_sents())

    t = TnT(N=1000, C=False)
    s = TnT(N=1000, C=True)
    t.train(d[(11)*100:])
    s.train(d[(11)*100:])

    for i in range(10):
        tacc = t.evaluate(d[i*100:((i+1)*100)])
        tp_un = t.unknown / (t.known + t.unknown)
        tp_kn = t.known / (t.known + t.unknown)
        t.unknown = 0
        t.known = 0

        print('Capitalization off:')
        print('Accuracy:', tacc)
        print('Percentage known:', tp_kn)
        print('Percentage unknown:', tp_un)
        print('Accuracy over known words:', (tacc / tp_kn))

        sacc = s.evaluate(d[i*100:((i+1)*100)])
        sp_un = s.unknown / (s.known + s.unknown)
        sp_kn = s.known / (s.known + s.unknown)
        s.unknown = 0
        s.known = 0

        print('Capitalization on:')
        print('Accuracy:', sacc)
        print('Percentage known:', sp_kn)
        print('Percentage unknown:', sp_un)
        print('Accuracy over known words:', (sacc / sp_kn))

def demo3():
    from nltk.corpus import treebank, brown

    d = list(treebank.tagged_sents())
    e = list(brown.tagged_sents())

    d = d[:1000]
    e = e[:1000]

    d10 = int(len(d)*0.1)
    e10 = int(len(e)*0.1)

    tknacc = 0
    sknacc = 0
    tallacc = 0
    sallacc = 0
    tknown = 0
    sknown = 0

    for i in range(10):

        t = TnT(N=1000, C=False)
        s = TnT(N=1000, C=False)

        dtest = d[(i*d10):((i+1)*d10)]
        etest = e[(i*e10):((i+1)*e10)]

        dtrain = d[:(i*d10)] + d[((i+1)*d10):]
        etrain = e[:(i*e10)] + e[((i+1)*e10):]

        t.train(dtrain)
        s.train(etrain)

        tacc = t.evaluate(dtest)
        tp_un = t.unknown / (t.known + t.unknown)
        tp_kn = t.known / (t.known + t.unknown)
        tknown += tp_kn
        t.unknown = 0
        t.known = 0

        sacc = s.evaluate(etest)
        sp_un = s.unknown / (s.known + s.unknown)
        sp_kn = s.known / (s.known + s.unknown)
        sknown += sp_kn
        s.unknown = 0
        s.known = 0

        tknacc += (tacc / tp_kn)
        sknacc += (sacc / tp_kn)
        tallacc += tacc
        sallacc += sacc

        #print i+1, (tacc / tp_kn), i+1, (sacc / tp_kn), i+1, tacc, i+1, sacc


    print("brown: acc over words known:", 10 * tknacc)
    print("     : overall accuracy:", 10 * tallacc)
    print("     : words known:", 10 * tknown)
    print("treebank: acc over words known:", 10 * sknacc)
    print("        : overall accuracy:", 10 * sallacc)
    print("        : words known:", 10 * sknown)


if __name__ == "__main__":
    from settings import Settings
    Settings.read("config/ReynirSimple.conf")
    demo()
