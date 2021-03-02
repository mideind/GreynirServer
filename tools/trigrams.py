#!/usr/bin/env python
# type: ignore

"""
    Greynir: Natural language processing for Icelandic

    Trigrams module

    Copyright (C) 2021 Miðeind ehf

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

    This module reads parse trees from stored articles and processes the words therein,
    to create trigram lists and statistical data.

"""

import os
import sys
from itertools import islice, tee
from random import randint
import collections 


# Hack to make this Python program executable from the tools subdirectory
if __name__ == "__main__":
    basepath, _ = os.path.split(os.path.realpath(__file__))
    if basepath.endswith("/tools") or basepath.endswith("\\tools"):
        basepath = basepath[0:-6]
        sys.path.append(basepath)
else:
    basepath = ""

from settings import Settings, ConfigError
from tokenizer import correct_spaces
from reynir.bindb import BIN_Db
from db import SessionContext, DatabaseError
from db.models import Article, Trigram
from tree import TreeTokenList, TerminalDescriptor


CHANGING = set() # A set of all words we need to change
REPLACING = collections.defaultdict(str)    # fACE_SK.txt
DELETING = set()                            # d.txt
DOUBLING = collections.defaultdict(str)     # fMW.txt


def dump_tokens(limit):
    """ Iterate through parsed articles and print a list
        of tokens and their matched terminals """

    dtd = dict()
    with BIN_Db.get_db() as db, SessionContext(commit=True) as session:
        # Iterate through the articles
        q = (
            session.query(Article)
            .filter(Article.tree != None)
            .order_by(Article.timestamp)
        )
        if limit is None:
            q = q.all()
        else:
            q = q[0:limit]
        for a in q:
            print(
                "\nARTICLE\nHeading: '{0.heading}'\nURL: {0.url}\nTimestamp: {0.timestamp}"
                .format(a)
            )
            tree = TreeTokenList()
            tree.load(a.tree)
            for ix, toklist in tree.token_lists():
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


def make_trigrams(limit, output_tsv=False):
    """ Iterate through parsed articles and extract trigrams from
        successfully parsed sentences. If output_tsv is True, the
        trigrams are output to a tab-separated text file. Otherwise,
        they are 'upserted' into the trigrams table of the
        scraper database. """

    with SessionContext(commit=False) as session:

        if output_tsv:
            tsv_file = open(os.path.join(basepath, "resources", "trigrams.tsv"), "w")
        else:
            # Delete existing trigrams
            Trigram.delete_all(session)
            session.commit()
            tsv_file = None

        # Fill correction data structures
        def fill_corrections():
            """ Fills global data structures for correcting tokens """
            with open(os.path.join(basepath, "resources", "fACE_SK.txt"), 'r') as myfile:
                for line in myfile:
                    content = line.strip().split("\t")
                    REPLACING["\""+content[0]+"\""] = "\""+content[1]+"\""
                    CHANGING.add("\""+content[0]+"\"")
            with open(os.path.join(basepath, "resources", "d.txt"), 'r') as myfile:
                for line in myfile:
                    DELETING.add("\""+line.strip()+"\"")
                    CHANGING.add("\""+line.strip()+"\"")
            with open(os.path.join(basepath, "resources", "fMW.txt"), 'r') as myfile:
                for line in myfile:
                    content = line.strip().split("\t")
                    corr = content[1].replace(" ", "\" \"")
                    corr = "\""+corr+"\""
                    DOUBLING["\""+content[0]+"\""] = corr
                    CHANGING.add("\""+content[0]+"\"")
        fill_corrections()
        # Iterate through the articles
        q = (
            session.query(Article.url, Article.timestamp, Article.tree)
            .filter(Article.tree != None)
            .order_by(Article.timestamp)
        )
        if limit is None:
            q = q.yield_per(200)
        else:
            q = q[0:limit]

        def tokens(q):
            """ Generator for token stream """
            for a in q:
                #print("Processing article from {0.timestamp}: {0.url}".format(a))
                tree = TreeTokenList()
                tree.load(a.tree)
                for _, toklist in tree.token_lists():
                    if toklist and len(toklist) > 1:
                        # For each sentence, start and end with empty strings
                        yield ""
                        yield ""
                        for t in toklist:
                            if t.token in CHANGING:
                                # We take a closer look
                                # We assume multi-word tokens don´t need to be changed
                                if t.token in REPLACING: # Words we simply need to replace
                                    yield REPLACING[t.token]
                                elif t.token in DELETING: # Words that don't belong in trigrams
                                    pass
                                elif t.token in DOUBLING: # Words incorrectly in one token
                                    for each in DOUBLING[t.token].split(" "):
                                        yield each
                            else:
                                yield from t.token[1:-1].split()
                        yield ""
                        yield ""

        def trigrams(iterable):
            return zip(
                *((islice(seq, i, None) for i, seq in enumerate(tee(iterable, 3))))
            )

        FLUSH_THRESHOLD = 200  # Flush once every 200 records
        cnt = 0
        try:
            for tg in trigrams(tokens(q)):
                # print("{0}".format(tg))
                if any(w for w in tg):
                    try:
                        if output_tsv:
                            tsv_file.write("{0}\t{1}\t{2}\n".format(*tg))
                        else:
                            Trigram.upsert(session, *tg)
                            cnt += 1
                            if cnt >= FLUSH_THRESHOLD:
                                session.flush()
                                cnt = 0
                    except DatabaseError as ex:
                        print(
                            "*** Exception {0} on trigram {1}, skipped"
                            .format(ex, tg)
                        )
        finally:
            if output_tsv:
                tsv_file.close()
            else:
                session.commit()


def create_trigrams_csv():
    """ Read a text file generated by uniq -c < trigrams.sorted.tsv > trigrams.uniq.tsv
        and create a corresponding csv file for bulk load into PostgreSQL """

    def csv(s):
        """ Convert a string to CSV format, with double quotes and escaping """
        return '"' + s.replace('"', '""') + '"'

    ix = 0

    with open(
        os.path.join(basepath, "resources", "trigrams.uniq.tsv"), "r"
    ) as tsv_file:

        with open(os.path.join(basepath, "resources", "trigrams.csv"), "w") as csv_file:
            for line in tsv_file:
                if not line:
                    continue
                cnt = int(line[0:8])
                a = line[8:].rstrip().split("\t")
                if any(len(s) > 64 for s in a):
                    # Skip words longer than 64 characters, as they exceed
                    # the trigram table's column width
                    continue
                while len(a) < 3:
                    a.append("")
                csv_file.write(
                    "{0},{1},{2},{3}\n".format(csv(a[0]), csv(a[1]), csv(a[2]), cnt)
                )
                ix += 1
                if ix % 100000 == 0:
                    print("{0} lines processed".format(ix), end="\r")


def spin_trigrams(num):
    """ Spin random sentences out of trigrams """

    with SessionContext(commit=True) as session:
        print("Loading first candidates")
        q = session.execute(
            "select t3, frequency from trigrams where t1='' and t2='' order by frequency desc"
        )
        # DEBUG
        # from sqlalchemy.dialects import postgresql
        # print(str(q.statement.compile(dialect=postgresql.dialect())))
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
                            sent += " " + t3
                        else:
                            sent = t3
                        t1, t2 = t2, t3
                        q = session.execute(
                            "select t3, frequency from trigrams "
                            "where t1=:t1 and t2=:t2 order by frequency desc",
                            dict(t1=t1, t2=t2)
                        )
                        candidates = q.fetchall()
                        break
                    r -= freq
            return correct_spaces(sent)

        # Spin the sentences
        for _ in range(num):
            print("{0}".format(spin_trigram(first)))


def main():

    try:
        # Read configuration file
        Settings.read(os.path.join(basepath, "config", "GreynirSimple.conf"))
    except ConfigError as e:
        print("Configuration error: {0}".format(e))
        quit()

    #make_trigrams(limit=None, output_tsv=True)

    #create_trigrams_csv()

    # dump_tokens(limit = 10)

    spin_trigrams(25)


if __name__ == "__main__":

    main()
