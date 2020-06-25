#!/usr/bin/env python
"""

    Greynir: Natural language processing for Icelandic

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


    Utility script that inspects articles in Greynir's database
    and removes those that are:

    * Duplicates (e.g. https & http URLs)
    * Non-Icelandic
    * Don't contain any sentences
    * Contain lots of "chaff", i.e. many very short sentences (prob. scraper issues)

"""

import os
import sys
import gc
from random import shuffle

# Hack to make this Python program executable from the utils subdirectory
basepath, _ = os.path.split(os.path.realpath(__file__))
_UTILS = os.sep + "utils"
if basepath.endswith(_UTILS):
    basepath = basepath[0 : -len(_UTILS)]
    sys.path.append(basepath)

from settings import Settings
from article import Article
from db.models import Article as ArticleModel

from db import SessionContext

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
        session.execute(ArticleModel.table().delete().where(ArticleModel.num_sentences == 0))

        # Non-Icelandic


        # Duplicates
        # For each article, check whether there is a corresponding 
        # article URL with https instead of http and vice versa

        # Chaff
        # ???

if __name__ == "__main__":
    main()
