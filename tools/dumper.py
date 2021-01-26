#!/usr/bin/env python
"""

    Greynir: Natural language processing for Icelandic

    Dumper module

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


    This module dumps article text to a text file. Each sentence is
    put on a separate line. Entity and person names are coded with
    embedded underscores instead of spaces.

"""

import getopt
import sys
import time
import json

from contextlib import closing
from datetime import datetime

from settings import Settings, ConfigError
from db import Scraper_DB
from db.models import Article
from tokenizer import TOK


# Default output file name
OUTPUT_FILE = "reynir_dump.txt"


class Dumper:

    """ The worker class that processes parsed articles """

    def __init__(self):
        pass


    class AbortSentence(RuntimeError):
        """ Signal that we want to abort the current sentence,
            i.e. not to write it to the output """
        pass


    def dump(self, tokens_json, file):
        """ Dump the sentences of a single article to a text file,
            one sentence per line """
        tokens = json.loads(tokens_json)
        skip_punctuation = frozenset(( '„', '“', '”' ))
        abort_punctuation = frozenset(( '…', '|', '#', '@' ))
        for p in tokens:
            for sent in p:
                try:
                    out = []
                    wcnt = 0
                    err = False
                    for t in sent:
                        if "err" in t:
                            err = True
                            break
                        kind = t.get("k")
                        text = t.get("x")
                        m = t.get("m")
                        if text:
                            # Person and entity names may contain spaces,
                            # but we want to keep them together as single tokens,
                            # so we replace the spaces with underscores
                            if kind == TOK.PERSON:
                                out.append(text.replace(" ", "_") + "/p")
                                wcnt += 1
                            elif kind == TOK.ENTITY:
                                out.append(text.replace(" ", "_") + "/e")
                                wcnt += 1
                            elif kind == TOK.PUNCTUATION:
                                # Skip insignificant punctuation, such as double quotes
                                if text in abort_punctuation:
                                    raise Dumper.AbortSentence()
                                elif text not in skip_punctuation:
                                    out.append(text)
                            elif kind == TOK.YEAR:
                                out.append(text + "/y")
                                wcnt += 1
                            elif kind == TOK.AMOUNT:
                                out.append(text.replace(" ", "_") + "/amt")
                                wcnt += 1
                            elif kind == TOK.NUMBER:
                                out.append(text.replace(" ", "_") + "/n")
                                wcnt += 1
                            elif kind == TOK.PERCENT:
                                out.append(text.replace(" ", "_") + "/pc")
                                wcnt += 1
                            elif kind == TOK.CURRENCY:
                                out.append(text.replace(" ", "_") + "/c")
                                wcnt += 1
                            elif kind == TOK.DATE:
                                out.append(text.replace(" ", "_") + "/d")
                                wcnt += 1
                            elif kind == TOK.TIME:
                                out.append(text.replace(" ", "_") + "/t")
                                wcnt += 1
                            elif kind == TOK.TIMESTAMP:
                                out.append(text.replace(" ", "_") + "/ts")
                                wcnt += 1
                            elif kind == TOK.EMAIL:
                                out.append(text + "/email")
                                wcnt += 1
                            elif kind == TOK.URL:
                                out.append(text + "/url")
                                wcnt += 1
                            elif kind == TOK.TELNO:
                                out.append(text + "/tel")
                                wcnt += 1
                            elif kind == TOK.ORDINAL:
                                out.append(text + "/o")
                                wcnt += 1
                            else:
                                if wcnt == 0 and text[0].isupper():
                                    # First word in sentence, uppercase and we
                                    # know its stem: check whether the stem is lowercase
                                    # and if so, output the word in lowercase as well
                                    if m is None or not m[0][0].isupper():
                                        original = text
                                        text = text[0].lower() + text[1:]
                                if m is None:
                                    terminal = t.get("t")
                                    if terminal is not None:
                                        if terminal.startswith("sérnafn"):
                                            out.append(text.replace(" ", "_") + "/s")
                                        else:
                                            out.append(text.replace(" ", "_") + "/" + terminal.split("_")[0])
                                    else:
                                        # print("No meaning associated with {0}".format(t))
                                        out.append(text.replace(" ", "_") + "/x")
                                else:
                                    out.append(text.replace(" ", "_") + "/" + m[1])  # Add word category
                                wcnt += 1
                    if out and not err:
                        line = " ".join(out)
                        if line != "." and not line.startswith("mbl.is/unk /"):
                            print(line, file = file)
                except Dumper.AbortSentence:
                    # If a sentence contains particular 'stop tokens',
                    # don't write it to the result file
                    pass


    def go(self, output, limit):
        """ Process already parsed articles from the database """

        db = Scraper_DB()
        with closing(db.session) as session, open(output, "w") as file:

            """ Go through parsed articles and process them """
            q = session.query(Article.tokens).filter(Article.tree != None)
            if limit > 0:
                q = q[0:limit]
            else:
                q = q.yield_per(4096)
            cnt = 0
            for a in q:
                if cnt % 1000 == 0:
                    print("Dumped {0} articles".format(cnt), end=chr(13))
                self.dump(a.tokens, file)
                cnt += 1
            print("Dumped {0} articles".format(cnt), end=chr(13))


def process_articles(limit = 0):

    print("------ Greynir starting dump -------")
    print("Output file: {0}".format(OUTPUT_FILE))
    if limit:
        print("Limit: {0} articles".format(limit))
    ts = "{0}".format(datetime.utcnow())[0:19]
    print("Time: {0}\n".format(ts))

    t0 = time.time()

    Dumper().go(output = OUTPUT_FILE, limit = limit)

    t1 = time.time()

    print("\n------ Dump completed -------")
    print("Total time: {0:.2f} seconds".format(t1 - t0))
    ts = "{0}".format(datetime.utcnow())[0:19]
    print("Time: {0}\n".format(ts))


class Usage(Exception):

    def __init__(self, msg):
        self.msg = msg


__doc__ = """

    Greynir - Natural language processing for Icelandic

    Dumper module

    Usage:
        python dumper.py [options]

    Options:
        -h, --help: Show this help text
        -l N, --limit=N: Limit dump to N articles
        -o filename, --output=filename: Output to the given file (default is reynir_dump.txt)

"""

def main(argv = None):
    """ Guido van Rossum's pattern for a Python main function """

    if argv is None:
        argv = sys.argv
    try:
        try:
            opts, args = getopt.getopt(argv[1:], "hl:o:",
                ["help", "limit=", "output="])
        except getopt.error as msg:
             raise Usage(msg)
        limit = 10 # !!! DEBUG default limit on number of articles to parse, unless otherwise specified
        # Process options
        for o, a in opts:
            if o in ("-h", "--help"):
                print(__doc__)
                return 0
            elif o in ("-l", "--limit"):
                # Maximum number of articles to parse
                try:
                    limit = int(a)
                except ValueError as e:
                    pass
            elif o in ("-o", "--output"):
                if a:
                    global OUTPUT_FILE
                    OUTPUT_FILE = a
                else:
                    raise Usage("Output file name must be nonempty")

        # Process arguments
        for arg in args:
            pass

        # Read the configuration settings file

        try:
            Settings.read("config/GreynirSimple.conf")
            # Don't run the processor in debug mode
            Settings.DEBUG = False
        except ConfigError as e:
            print("Configuration error: {0}".format(e), file = sys.stderr)
            return 2

        process_articles(limit = limit)

    except Usage as err:
        print(err.msg, file = sys.stderr)
        print("For help use --help", file = sys.stderr)
        return 2

    # Completed with no error
    return 0


if __name__ == "__main__":
    sys.exit(main())
