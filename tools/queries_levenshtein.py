#!/usr/bin/env python3
#
# This program reads the query strings handled by the special.py qmodule,
# compares them to all logged queries in the database using Levenshtein
# edit distance and dumps all logged queries that are *somewhat* close to
# queries handled by the module.
#

import os
import sys

# Hack to make this Python program executable from the tools subdirectory
basepath, _ = os.path.split(os.path.realpath(__file__))
_TOOLS = os.sep + "tools"
if basepath.endswith(_TOOLS):
    basepath = basepath[0 : -len(_TOOLS)]
    sys.path.append(basepath)


from db.models import Query
from queries.special import _SPECIAL_QUERIES

from Levenshtein import StringMatcher


_MAX_DISTANCE = 5


def main() -> None:
    # Read all logged queries from database
    # queries = read_queries()
    # special = _SPECIAL_QUERIES.keys()
    # Run levenshtein comparison against every hardcoded special query
    # for q in queries:
    #    for s in special:
    #       s = StringMatcher(seq1=q, seq2=s)
    #       d = s.distance()
    #       if d <= _MAX_DISTANCE:
    #           print(q)


if __name__ == "__main__":
    main()