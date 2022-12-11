#!/usr/bin/env python3
#
# Given a list of URLs, fetch the corresponding articles
# from the database and write them to a JSON file.
#

import sys, os, json

# Look for modules in parent directory
sys.path.insert(1, os.path.join(sys.path[0], ".."))

from db import SessionContext
from db.models import Article
from tokenizer import correct_spaces


def tokens2text(tokens):
    """Reassemble text from tokens."""
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


def main():
    # Read list of URLs from file
    with open("urls.txt", "r") as f:
        lines = f.readlines()

    articles = list()

    with SessionContext(read_only=True) as session:
        for i in lines:
            try:
                # Fetch article from database and add to list
                url = i
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

                articles.append(item)
            except Exception as e:
                print(f"Error processing {i}: {e}")

    with open("articles.json", "w") as f:
        json.dump(articles, f, indent=4, ensure_ascii=False)


if __name__ == "__main__":
    main()
