#!/usr/bin/env python

"""
    Fetch all Icelandic placenames (örnefni) from iceaddr database
    and try to look them up using GreynirPackage's bindb module.
    Print any placenames that could not be found in either
    BÍN proper or using the word combinator (samsetjari).
"""

import sys
import sqlite3

from reynir.bindb import BIN_Db

if __name__ == "__main__":
    """ Invocation via command line. """
    db_path = sys.argv[1] if len(sys.argv) > 1 else None
    if not db_path:
        print("No db path")
        sys.exit(1)

    db_conn = sqlite3.connect(db_path, check_same_thread=False)
    db_conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))

    q = "SELECT DISTINCT nafn FROM ornefni;"

    res = db_conn.cursor().execute(q)

    matches = [row["nafn"] for row in res]

    num_bin = 0
    num_comb = 0
    num_fail = 0

    with BIN_Db.get_db() as db:
        for m in matches:
            w = m.strip()
            if " " in w or "-" in w or "-" in w:
                continue

            # Direct BÍN lookup
            meanings = db.meanings(w)
            if meanings:
                num_bin += 1
                continue

            # Lookup using BÍN and combinator
            _, meanings = db.lookup_word(w, auto_uppercase=True)
            if meanings:
                num_comb += 1
                continue

            print(w)
            num_fail += 1

    print("Num  BÍN: {0}".format(num_bin))
    print("Num comb: {0}".format(num_comb))
    print("Num fail: {0}".format(num_fail))
