#!/usr/bin/env python3
#
# This program reads all logged queries in the database and dumps
# various stats wrt. unanswered queries + more.

import os
import sys

# Hack to make this Python program executable from the tools subdirectory
basepath, _ = os.path.split(os.path.realpath(__file__))
_TOOLS = os.sep + "tools"
if basepath.endswith(_TOOLS):
    basepath = basepath[0 : -len(_TOOLS)]
    sys.path.append(basepath)

from collections import Counter
from pprint import pprint

from db import SessionContext
from db.models import QueryLog
from queries.special import _SPECIAL_QUERIES

from Levenshtein import StringMatcher


_MAX_DISTANCE = 5
_MIN_QUERY_LEN = 10


def main() -> None:

    uniq = set()
    special = _SPECIAL_QUERIES.keys()

    # Read all logged queries from database
    with SessionContext(read_only=True) as session:
        counter = Counter()

        ql = session.query(QueryLog).filter(QueryLog.answer == None)
        for q in ql:
            question = q.question
            # if (
            #     len(question) < _MIN_QUERY_LEN
            #     or (question in uniq)
            #     or (question in special)
            # ):
            #     continue
            # print(question)
            counter[question] += 1
            continue
            # print(q.question)
            uniq.add(question)
            # Run levenshtein comparison against every hardcoded special query
            for s in special:
                matcher = StringMatcher.StringMatcher(seq1=question, seq2=s)
                d = matcher.distance()
                # print(d)
                # if d <= _MAX_DISTANCE:
                print(f"{d} '{q.question}' ~ '{s}'")
        pprint(counter)


if __name__ == "__main__":
    main()