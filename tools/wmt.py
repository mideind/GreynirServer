#!/usr/bin/env python
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


    This utility extracts the text of all articles on a given day, with
    associated metadata such as URL, title, timestamp, etc.

"""

import os
import sys
import json
from datetime import datetime


# Hack to make this Python program executable from the tools subdirectory
basepath, _ = os.path.split(os.path.realpath(__file__))
_TOOLS = os.sep + "tools"
if basepath.endswith(_TOOLS):
    basepath = basepath[0 : -len(_TOOLS)]
    sys.path.append(basepath)


from settings import Settings, ConfigError
from db import SessionContext
from db.models import Article
from tokenizer import correct_spaces

def main():

    try:
        # Read configuration file
        Settings.read(os.path.join(basepath, "config", "GreynirSimple.conf"))
    except ConfigError as e:
        print("Configuration error: {0}".format(e))
        exit()

    with SessionContext(commit=False) as session:
        bef = datetime(2020, 7, 26, 0, 0, 1)
        aft = datetime(2020, 7, 27, 0, 0, 1)
        q = (
            session.query(
                Article.url, Article.timestamp, Article.heading, Article.tokens
            )
            .filter(Article.timestamp > bef)
            .filter(Article.timestamp < aft)
            .order_by(Article.timestamp)
        )
        items = list()
        for r in q.all():
            (url, ts, title, tokens) = r
            text = ""
            tokens = json.loads(tokens)
            if not tokens:
                continue
            # Paragraphs
            for p in tokens:
                # Sentences
                for s in p:
                    # Tokens
                    for t in s:
                        text += t["x"] + " "

            d = dict(url=url, timestamp=ts.isoformat(), title=title, text=text)
            d["text"] = correct_spaces(d["text"])
            items.append(d)
            # print(d)
            # print(text)
            # print("____________________________")

        print(json.dumps(items, ensure_ascii=False, sort_keys=True, indent=4))


if __name__ == "__main__":
    main()
