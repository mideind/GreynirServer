#!/usr/bin/env python

"""
    Read tokens for all articles in database, look for nouns
    and check if they could be found in vocabulary. If not,
    add them to a dictionary and spit it out.
"""

import json, sys, os
from datetime import datetime
from collections import defaultdict
from pprint import pprint

# Look for modules in parent directory
sys.path.insert(1, os.path.join(sys.path[0], '..'))

from db import SessionContext, desc
from db.models import Article

with SessionContext(read_only=True) as session:
    q = (
        session.query(Article.id, Article.timestamp, Article.tokens)
        .filter(Article.tree != None)
        .filter(Article.timestamp != None)
        .filter(Article.timestamp <= datetime.utcnow())
        .filter(Article.heading > "")
        .filter(Article.num_sentences > 0)
    )

    nouns = defaultdict(int)

    for i, a in enumerate(q.yield_per(100)):
        print("%d\r" % i, end="")
        tokens = json.loads(a.tokens)
        # Paragraphs
        for p in tokens:
            # Sentences
            for s in p:
                # Tokens
                for t in s:
                    if (
                        "t" in t
                        and t["t"].startswith("no_")
                        and not t.get("m")
                        and not t.get("v")
                    ):
                        # print(t["x"])
                        # print(t)
                        nouns[t["x"]] += 1

    ordered = sorted(nouns.items(), key=lambda kv: kv[1])

    pprint(ordered)
