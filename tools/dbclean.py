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


    Utility script that inspects articles in Greynir's database
    and removes those that:

    * Don't contain any sentences
    * Are duplicates (e.g. https vs http URLs)
    * Are non-Icelandic
    * Contain lots of "chaff", i.e. many very short sentences (prob. scraper issues)

"""

import os
import sys
import re
from random import shuffle

# Hack to make this Python program executable from the tools subdirectory
basepath, _ = os.path.split(os.path.realpath(__file__))
_TOOLS = os.sep + "tools"
if basepath.endswith(_TOOLS):
    basepath = basepath[0 : -len(_TOOLS)]
    sys.path.append(basepath)

from settings import Settings, ConfigError
# from article import Article
from db import SessionContext
from db.models import Article as ArticleModel

from reynir.bintokenizer import tokens_are_foreign


def main():

    try:
        # Read configuration file
        Settings.read(os.path.join(basepath, "config", "GreynirSimple.conf"))
    except ConfigError as e:
        print("Configuration error: {0}".format(e))
        quit()

    with SessionContext(commit=True) as session:

        # Zero sentences
        print("Deleting all articles with zero sentences")
        res = session.execute(
            ArticleModel.table().delete().where(ArticleModel.num_sentences == 0)
        )
        print(str(res.rowcount) + " articles deleted")

        # Non-Icelandic
        # TODO: Implement me!

        # Duplicates
        # For each https article, check whether there is a corresponding
        # article URL with http URI scheme
        dupl = 0
        q = session.query(ArticleModel.url).filter(ArticleModel.url.like("https://%"))
        for r in q.all():
            url = re.sub(r"^https://", r"http://", r.url)
            # c = session.query(ArticleModel.url).filter(ArticleModel.url == url).count()
            res = session.execute(
                ArticleModel.table().delete().where(ArticleModel.url == url)
            )
            dupl += res.rowcount
        print("{0} duplicate URLs w. HTTP scheme removed".format(dupl))

        # Chaff
        # ???
        # TODO: Implement me!


if __name__ == "__main__":
    main()
