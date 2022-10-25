#!/usr/bin/python

import sys, os, json

# Look for modules in parent directory
sys.path.insert(1, os.path.join(sys.path[0], ".."))

from db import SessionContext, desc
from db.models import Article
from tokenizer import correct_spaces

with open("urls.json", "r") as f:
    items = json.load(f)


def tokens2text(tokens):
    text = ""
    if not tokens:
        return text
    tokens = json.loads(tokens)
    if not tokens:
        return text
    # Paragraphs
    for p in tokens:
        tx = ""
        # Sentences
        for s in p:
            # Tokens
            for t in s:
                tx += t["x"] + " "
        tx = correct_spaces(tx)
        text += tx + "\n\n"
    return text


polish = list()

with SessionContext(read_only=True) as session:

    for i in items:
        url = i["url"]
        q = (
            session.query(
                Article.url, Article.timestamp, Article.tokens, Article.heading
            )
            .filter(Article.url == url)
            .all()
        )
        if len(q) != 1:
            continue

        r = q[0]

        item = {
            "url": r.url,
            "timestamp": r.timestamp.isoformat(),
            "title": r.heading,
            "text": tokens2text(r.tokens),
        }

        polish.append(item)

with open("polish.json", "w") as f:
    json.dump(polish, f, indent=4, ensure_ascii=False)
