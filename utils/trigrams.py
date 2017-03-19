#!/usr/bin/env python
"""
    Reynir: Natural language processing for Icelandic

    Trigrams module

    Copyright (c) 2016 Vilhjalmur Thorsteinsson
    All rights reserved
    See the accompanying README.md file for further licensing and copyright information.

    This module reads parse trees from stored articles and processes the words therein,
    to create trigram lists and statistical data.

"""

import os
import sys
from itertools import islice, tee
from contextlib import closing
from collections import defaultdict
from random import randint
import json
import math
import pickle

# Hack to make this Python program executable from the utils subdirectory
if __name__ == "__main__":
    basepath, _ = os.path.split(os.path.realpath(__file__))
    if basepath.endswith("/utils") or basepath.endswith("\\utils"):
        basepath = basepath[0:-6]
        sys.path.append(basepath)
else:
    basepath = ""

from settings import Settings, ConfigError, Prepositions
from tokenizer import tokenize, correct_spaces, canonicalize_token, TOK
from bindb import BIN_Db
from scraperdb import SessionContext, Article, Trigram, DatabaseError, desc
from tree import TreeTokenList, TerminalDescriptor
from treeutil import TreeUtility
from postagger import IFD_Tagset


def dump_tokens(limit):
    """ Iterate through parsed articles and print a list
        of tokens and their matched terminals """

    dtd = dict()
    with closing(BIN_Db.get_db()) as db:
        with SessionContext(commit = True) as session:
            # Iterate through the articles
            q = session.query(Article) \
                .filter(Article.tree != None) \
                .order_by(Article.timestamp)
            if limit is None:
                q = q.all()
            else:
                q = q[0:limit]
            for a in q:
                print("\nARTICLE\nHeading: '{0.heading}'\nURL: {0.url}\nTimestamp: {0.timestamp}".format(a))
                tree = TreeTokenList()
                tree.load(a.tree)
                for ix, toklist in tree.sentences():
                    print("\nSentence {0}:".format(ix))
                    at_start = True
                    for t in toklist:
                        if t.tokentype == "WORD":
                            wrd = t.token[1:-1]
                            td = dtd.get(t.terminal)
                            if td is None:
                                td = TerminalDescriptor(t.terminal)
                                dtd[t.terminal] = td
                            stem = td.stem(db, wrd, at_start)
                            at_start = False
                            print("    {0} {1} {2}".format(wrd, stem, t.terminal))
                        else:
                            print("    {0.token} {0.cat} {0.terminal}".format(t))


def make_trigrams(limit):
    """ Iterate through parsed articles and extract trigrams from
        successfully parsed sentences """

    with SessionContext(commit = True) as session:

        # Delete existing trigrams
        Trigram.delete_all(session)
        # Iterate through the articles
        q = session.query(Article.url, Article.timestamp, Article.tree) \
            .filter(Article.tree != None) \
            .order_by(Article.timestamp)
        if limit is None:
            q = q.yield_per(200)
        else:
            q = q[0:limit]

        def tokens(q):
            """ Generator for token stream """
            for a in q:
                print("Processing article from {0.timestamp}: {0.url}".format(a))
                tree = TreeTokenList()
                tree.load(a.tree)
                for ix, toklist in tree.sentences():
                    if toklist:
                        # For each sentence, start and end with empty strings
                        yield ""
                        yield ""
                        for t in toklist:
                            yield t.token[1:-1]
                        yield ""
                        yield ""

        def trigrams(iterable):
            return zip(*((islice(seq, i, None) for i, seq in enumerate(tee(iterable, 3)))))

        FLUSH_THRESHOLD = 0 # 200 # Flush once every 200 records
        cnt = 0
        for tg in trigrams(tokens(q)):
            # print("{0}".format(tg))
            if any(w for w in tg):
                try:
                    Trigram.upsert(session, *tg)
                    cnt += 1
                    if cnt == FLUSH_THRESHOLD:
                        session.flush()
                        cnt = 0
                except DatabaseError as ex:
                    print("*** Exception {0} on trigram {1}, skipped".format(ex, tg))


def spin_trigrams(num):
    """ Spin random sentences out of trigrams """

    with SessionContext(commit = True) as session:
        print("Loading first candidates")
        q = session.execute(
            "select t3, frequency from trigrams where t1='' and t2='' order by frequency desc"
        )
        # DEBUG
        #from sqlalchemy.dialects import postgresql
        #print(str(q.statement.compile(dialect=postgresql.dialect())))
        # DEBUG
        first = q.fetchall()
        print("{0} first candidates loaded".format(len(first)))

        def spin_trigram(first):
            t1 = t2 = ""
            candidates = first
            sent = ""
            while candidates:
                sumfreq = sum(freq for _, freq in candidates)
                r = randint(0, sumfreq - 1)
                for t3, freq in candidates:
                    if r < freq:
                        if not t3:
                            # End of sentence
                            candidates = []
                            break
                        if sent:
                            sent += ' ' + t3
                        else:
                            sent = t3
                        t1, t2 = t2, t3
                        q = session.execute(
                            "select t3, frequency from trigrams where t1=:t1 and t2=:t2 order by frequency desc",
                            dict(t1 = t1, t2 = t2)
                        )
                        candidates = q.fetchall()
                        break
                    r -= freq
            return correct_spaces(sent)

        # Spin the sentences
        for i in range(num):
            print("{0}".format(spin_trigram(first)))


class NgramTagger:

    """ A class to assign Icelandic Frequency Dictionary (IFD) tags
        to sentences consisting of 'raw' tokens coming out of the
        tokenizer. A parse tree is not required, so the class can
        also tag sentences for which there is no parse. The tagging
        is based on n-gram and lemma statistics harvested from
        the Reynir article database. """

    def __init__(self, n = 3):
        """ n indicates the n-gram size, i.e. 3 for trigrams, etc. """
        self.n = n
        self.EMPTY = tuple([""] * n)
        # ngram count
        self.cnt = defaultdict(int)
        # prefix (n-1-gram) count
        self.prefix_cnt = defaultdict(int)
        # { lemma: { tag : count} }
        self.lemma_cnt = defaultdict(lambda: defaultdict(int))

    def lemma_tags(self, lemma):
        """ Return a dict of tags and counts for this lemma """
        return self.lemma_cnt.get(lemma, dict())

    def lemma_count(self, lemma):
        """ Return the total occurrence count for a lemma """
        d = self.lemma_cnt.get(lemma)
        return 0 if d is None else sum(d.values())

    def init_model(self, limit = None):
        """ Iterate through parsed articles and extract tag trigrams from
            successfully parsed sentences """

        with SessionContext(commit = True, read_only = True) as session:

            # Iterate through the articles
            q = session.query(Article.url, Article.parsed, Article.tokens) \
                .filter(Article.tokens != None) \
                .order_by(desc(Article.parsed))
            if limit is None:
                q = q.yield_per(200)
            else:
                q = q[0:limit]

            n = self.n

            def tags(q):
                """ Generator for tag stream """
                acnt = 0
                for a in q:
                    # print("Processing article from {0.timestamp}: {0.url}".format(a))
                    if acnt % 50 == 0:
                        # Show progress
                        print(".", end = "", flush = True)
                    acnt += 1
                    doc = json.loads(a.tokens)
                    for pg in doc:
                        for sent in pg:
                            if any("err" in t for t in sent):
                                # Skip error sentences
                                continue
                            # For each sentence, start and end with empty strings
                            for i in range(n - 1):
                                yield ""
                            for t in sent:
                                # Skip punctuation
                                if t.get("k", TOK.WORD) != TOK.PUNCTUATION:
                                    canonicalize_token(t)
                                    tag = str(IFD_Tagset(t))
                                    if tag:
                                        self.lemma_cnt[t["x"]][tag] += 1
                                        yield tag
                            for i in range(n - 1):
                                yield ""

                print("", flush = True)

            def ngrams(iterable):
                return zip(*((islice(seq, i, None) for i, seq in enumerate(tee(iterable, n)))))

            # Count the n-grams
            cnt = self.cnt
            prefix_cnt = self.prefix_cnt
            EMPTY = self.EMPTY
            for ngram in ngrams(tags(q)):
                if ngram != EMPTY:
                    cnt[ngram] += 1
                    prefix_cnt[ngram[:-1]] += 1

        # Cut off lemma/tag counts <= 1
        lemmas_to_delete = []
        for lemma, d in self.lemma_cnt.items():
            tags_to_delete = [ tag for tag, cnt in d.items() if cnt == 1 ]
            for tag in tags_to_delete:
                del d[tag]
            if len(d) == 0:
                lemmas_to_delete.append(lemma)
        for lemma in lemmas_to_delete:
            del self.lemma_cnt[lemma]

        return self

    def store_model(self):
        """ Store the model in a pickle file """
        if len(self.cnt):
            # Don't store an empty count
            with open("ngram-{0}-count.pickle".format(self.n), "wb") as f:
                pickle.dump(self.lemma_cnt, f)
                pickle.dump(self.cnt, f)

    def load_model(self):
        """ Load the model from a pickle file """
        with open("ngram-{0}-count.pickle".format(self.n), "rb") as f:
            self.lemma_cnt = pickle.load(f)
            self.cnt = pickle.load(f)
            for ngram, c in self.cnt.items():
                self.prefix_cnt[ngram[:-1]] += c

    def show_model(self):
        """ Dump the tag count statistics """
        print("\nLemmas are {0}".format(len(self.lemma_cnt)))
        print("\nCount contains {0} ({1} distinct) {2}-grams"
            .format(sum(self.cnt.values()), len(self.cnt), self.n))
        print("Top 20 follow:")
        for ngram, cnt in sorted(self.cnt.items(), key=lambda x: x[1], reverse = True)[:20]:
            print("{0:5} {1}".format(cnt, ngram))
        print("\n")

    def _most_likely(self, tokens):
        """ Find the most likely tag sequence through the possible tags of each token """
        cnt = self.cnt
        prefix_cnt = self.prefix_cnt
        n = self.n
        history = self.EMPTY
        best_path = []
        best_prob = []
        len_tokens = len(tokens)

        def fwd_prob(ix, history, depth):
            """ Find the most probable tag from the tagset at position ix,
                using the history and looking forward up to depth tokens """
            if ix >= len_tokens:
                # Looking past the token string: return a log prob of 0.0
                return (0, 0.0)
            tagset = tokens[ix]
            prev = history[1:]
            if len(tagset) == 1:
                # Short circuit if only one tag is possible
                if depth > 0:
                    # Relay the forward probability upwards, unchanged
                    _, fwd_p = fwd_prob(ix + 1, prev + (tagset[0][0],), depth - 1)
                    return 0, fwd_p
                # Log prob is 0.0 (i.e. the probability is 1.0)
                return 0, 0.0
            cnt_tags = sum(cnt.get(prev + (tag,), 0) + 1 for tag, _ in tagset)
            log_p_tags = math.log(cnt_tags) + math.log(sum(lex_p for _, lex_p in tagset))
            best_ix, best_prob = None, None
            for tag_ix, tp in enumerate(tagset):
                tag, lex_p = tp
                ngram = prev + (tag,)
                log_p_tag = math.log(lex_p) + math.log(cnt.get(ngram, 0) + 1) - log_p_tags
                if best_prob is not None and log_p_tag < best_prob:
                    # Already too low prob to become the best one: skip this tag
                    continue
                _, fwd_p = fwd_prob(ix + 1, ngram, depth - 1) if depth > 0 else (0, 0.0)
                total_p = log_p_tag + fwd_p
                if best_prob is None or total_p > best_prob:
                    best_ix = tag_ix
                    best_prob = total_p
            return best_ix, best_prob

        for ix, tagset in enumerate(tokens):
            ix_pick, prob = fwd_prob(ix, history, n - 1)
            pick = tagset[ix_pick][0]
            best_path.append(pick)
            best_prob.append(prob)
            history = history[1:] + (pick,)

        return math.exp(sum(best_prob)), best_path

    def _old_most_likely(self, tokens):
        """ Find the most likely tag sequence through the possible tags of each token """

        len_tokens = len(tokens)
        cnt = self.cnt
        prefix_cnt = self.prefix_cnt

        def _most_likely_from(start, history, prev_best):
            """ Return the most likely tag sequence from and including the start """
            if start >= len_tokens:
                # Completed the token list:
                # the end probability is 1.0 (whose log is 0.0)
                return 0.0, []
            tagset = tokens[start]
            prev = history[1:]
            if len(tagset) == 1:
                # Short circuit if only one tag is possible
                tag = tagset[0][0]
                best_prob, best_tail = _most_likely_from(start + 1, prev + (tag,), prev_best)
                if best_tail is None:
                    return None, None
                best_tail.append(tag)
                return best_prob, best_tail
            # Create list of (tag, count) tuples for this tagset,
            # given the history (i.e. the previous n-1 proposed tags)
            tagprob = [(tag, (cnt.get(prev + (tag,), 0) + 1) * prob) for tag, prob in tagset]
            # Count the total number of ngrams that match this tagset
            #p_tags = sum(tp[1] for tp in tagprob)
            p_tags = (prefix_cnt[prev] + len(tagset)) * sum(prob for _, prob in tagset)
            if p_tags == 0:
                # No open options here: quit
                return None, None
            log_tags = math.log(p_tags)
            best_prob, best_tag, best_tail = None, None, None
            # Loop over the tags in descending order by count, to maximize
            # the chances of being able to short-circuit the recursion
            for tag, p in sorted(tagprob, key = lambda tp: tp[1], reverse = True):
                if p == 0:
                    # No instances of this n-gram in the database:
                    # this is not a candidate for best probability
                    #print("No instance of ngram {0}".format(h))
                    # All subsequent tags must also have zero count,
                    # so we're done
                    break
                # Calculate log(p / p_tags) = log(p) - log(p_tags) = log(p) - log_tags
                prob = math.log(p) - log_tags
                #print("{2}Looking at {0} with prob {1:.4f}".format((prev + (tag,)), math.exp(prob), " " * start))
                if best_prob is not None and prob < best_prob:
                    # p by itself is already worse than a candidate we
                    # have: we don't need to look at the tail, since
                    # it can only reduce p further
                    #print("{2}Breaking because prob {0:.4f} < {1:.4f}".format(math.exp(prob), math.exp(best_prob), " " * start))
                    break
                if prev_best is not None and prob < prev_best:
                    # p has gotten worse than a best case we already had
                    # further up the tree: give up on this branch
                    break
                # Recurse into the tail with the updated history
                p_tail, tail = _most_likely_from(start + 1, prev + (tag,), best_prob)
                if p_tail is None:
                    # Zero likelihood of this tail
                    continue
                if best_prob is None or prob + p_tail > best_prob:
                    # This is the best path found so far
                    # By adding the log probabilities, we're multiplying the probabilities
                    best_prob = prob + p_tail
                    best_tag = tag
                    best_tail = tail
            #print("{2}Returning tail {0} with prob {1:.4f}".format(best_tail, math.exp(best_prob), " " * start))
            if best_tail is None:
                return None, None
            best_tail.append(best_tag)
            return best_prob, best_tail

        log_prob, seq = _most_likely_from(0, self.EMPTY, None)
        if log_prob is None:
            # No consistent path found
            return 0.0, []
        # Return the probability and the tag sequence (after reversing it)
        return math.exp(log_prob), seq[::-1]

    def tag(self, toklist_or_text):
        """ Assign IFD tags to the given toklist, putting the tag in the
            "i" field of each non-punctuation token. If a string is passed,
            tokenize it first. Return the toklist so modified. """
        if isinstance(toklist_or_text, str):
            toklist = list(tokenize(toklist_or_text))
        else:
            toklist = list(toklist_or_text)

        CONJ_REF = frozenset(["sem", "er"])

        def ifd_tag(kind, txt, m):
            i = IFD_Tagset(
                k = TOK.descr[kind],
                c = m.ordfl,
                t = m.ordfl,
                f = m.fl,
                x = txt,
                s = m.stofn,
                b = m.beyging
            )
            return str(i)

        def ifd_taglist_entity(txt):
            i = IFD_Tagset(
                c = "entity",
                x = txt
            )
            return [ (str(i), 1.0) ]

        def ifd_tag_person(txt, p):
            i = IFD_Tagset(
                k = "PERSON",
                c = "person",
                g = p.gender,
                x = txt,
                s = p.name,
                t = "person_" + p.gender + "_" + p.case
            )
            return str(i)

        def ifd_taglist_person(txt, val):
            s = set(ifd_tag_person(txt, p) for p in val)
            # We simply assume that all possible tags for
            # a person name are equally likely
            prob = 1.0 / len(s)
            return [ (tag, prob) for tag in s ]

        CASE_TO_TAG = {
            "þf" : "ao",
            "þgf" : "aþ",
            "ef" : "ae"
        }

        def ifd_taglist_word(kind, txt, mlist):
            s = set(ifd_tag(kind, txt, m) for m in mlist)
            ltxt = txt.lower()
            if ltxt in Prepositions.PP:
                for case in Prepositions.PP[ltxt]:
                    if case in CASE_TO_TAG:
                        s.add(CASE_TO_TAG[case])
            if ltxt in CONJ_REF:
                # For referential conjunctions,
                # add 'ct' as a possibility (it does not come directly from a BÍN mark)
                s.add("ct")
            # Add a +1 bias to the counts so that no lemma/tag pairs have zero frequency
            prob = self.lemma_count(txt) + len(s)
            d = self.lemma_tags(txt)
            # It is possible for the probabilities of the tags in set s
            # not to add up to 1.0. This can happen if the tokenizer has
            # eliminated certain BÍN meanings due to updated settings
            # in Pref.conf.
            return [ (tag, (d.get(tag, 0) + 1) / prob) for tag in s ]

        tagsets = []
        for t in toklist:
            if not t.txt:
                continue
            if t.kind == TOK.WORD:
                taglist = ifd_taglist_word(t.kind, t.txt, t.val)
            elif t.kind == TOK.ENTITY:
                taglist = ifd_taglist_entity(t.txt)
            elif t.kind == TOK.PERSON:
                taglist = ifd_taglist_person(t.txt, t.val)
            elif t.kind == TOK.NUMBER:
                taglist = [ ("tfkfn", 1.0) ] # !!!
            else:
                taglist = []
            if taglist:
                display = " | ".join("{0} {1:.2f}".format(w, p) for w, p in taglist)
                print("{0:20}: {1}".format(t.txt, display))
                tagsets.append(taglist)

        _, tags = self._most_likely(tagsets)

        if not tags:
            return []

        ix = 0
        tokens = []
        for t in toklist:
            if not t.txt:
                continue
            # The code below should correspond to TreeUtility._describe_token()
            d = dict(x = t.txt)
            if t.kind == TOK.WORD:
                # set d["m"] to the meaning
                pass
            else:
                d["k"] = t.kind
            if t.val is not None and t.kind not in { TOK.WORD, TOK.ENTITY, TOK.PUNCTUATION }:
                # For tokens except words, entities and punctuation, include the val field
                if t.kind == TOK.PERSON:
                    d["v"], d["g"] = TreeUtility.choose_full_name(t.val, case = None, gender = None)
                else:
                    d["v"] = t.val
            if t.kind == TOK.WORD or t.kind == TOK.ENTITY or \
                t.kind == TOK.PERSON or t.kind == TOK.NUMBER:
                d["i"] = tags[ix]
                ix += 1
            tokens.append(d)

        return tokens


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
    tagger = NgramTagger(n = 5)#.init_model(limit = 50000)
    #tagger = NgramTagger(n = 3) # .init_model(limit = 20000)
    #tagger.store_model()
    tagger.load_model()
    tagger.show_model()

    toklist = tokenize(TEST_SENTENCE)
    print("\nTagging result:\n{0}".format("\n".join(str(d) for d in tagger.tag(toklist))))
    return tagger


def main():

    try:
        # Read configuration file
        Settings.read(os.path.join(basepath, "config/Reynir.conf"))
    except ConfigError as e:
        print("Configuration error: {0}".format(e))
        quit()

    #make_trigrams(limit = None)
    #dump_tokens(limit = 10)

    #spin_trigrams(25)

    return test_tagger()


if __name__ == "__main__":

    main()
