#!/usr/bin/env python3
#
# This program examines hardcoded queries in the special.py
# query module and checks if they can be improved.

import os
import sys

# Hack to make this Python program executable from the tools subdirectory
basepath, _ = os.path.split(os.path.realpath(__file__))
_TOOLS = os.sep + "tools"
if basepath.endswith(_TOOLS):
    basepath = basepath[0 : -len(_TOOLS)]
    sys.path.append(basepath)

from queries.special import _SPECIAL_QUERIES

_VERBS = {
    "geturðu": "getur þú",
    "viltu": "vilt þú",
    "helduru": "heldur þú",
    "kanntu": "kannt þú",
    "ertu": "ert þú",
    # "farðu": "far þú",
    "þekkirðu": "þekkir þú",
    "skilurðu": "skilur þú",
    "talarðu": "talar þú",
}


def main() -> None:
    special = _SPECIAL_QUERIES.keys()

    for s in special:
        for k, v in _VERBS.items():
            if s.startswith(k):
                i = s.replace(k, v)
                if i not in special:
                    print(s + " --> " + i)


if __name__ == "__main__":
    main()