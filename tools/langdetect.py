#!/usr/bin/env python3
# Find all English or Polish articles in the database and print their URLs

import os
import sys

# Hack to make this Python program executable from the tools subdirectory
basepath, _ = os.path.split(os.path.realpath(__file__))
_TOOLS = os.sep + "tools"
if basepath.endswith(_TOOLS):
    basepath = basepath[0 : -len(_TOOLS)]
    sys.path.append(basepath)

from settings import Settings, ConfigError

from db import SessionContext
from db.models import Article

from langdetect import detect as langdetect
from tokenizer import correct_spaces

from get_articles_by_url import tokens2text


LANG = "en"


def main():
    try:
        # Read configuration file
        Settings.read(os.path.join(basepath, "config", "GreynirSimple.conf"))
    except ConfigError as e:
        print("Configuration error: {0}".format(e))
        quit()

    with SessionContext(commit=True) as session:

        q = (
            session.query(Article.url, Article.heading, Article.tokens)
            # .filter(Article.root_id == 7)
            .order_by(Article.timestamp)
        )
        for r in q:
            try:
                (url, heading, tokens) = r
                text = tokens2text(tokens)
                # print(text)
                # print("------------------")
                headlang = langdetect(heading)
                txtlang = langdetect(text)
                if headlang == LANG and txtlang == LANG:
                    print(f"{url}")
            except:
                pass


if __name__ == "__main__":
    main()
