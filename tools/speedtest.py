#!/usr/bin/env python
# type: ignore

# Quick and dirty parser speed test

import os
import sys

# Hack to make this Python program executable from the tools subdirectory
basepath, _ = os.path.split(os.path.realpath(__file__))
if basepath.endswith("/tools") or basepath.endswith("\\tools"):
    basepath = basepath[0:-6]
    sys.path.append(basepath)

import time

from settings import Settings
from db import SessionContext
from article import Article
from fastparser import Fast_Parser


def profile(func, *args, **kwargs):
    """ Profile a function call """
    import cProfile as profile
    filename = os.path.join(basepath, 'Reynir.profile')
    pr = profile.Profile()
    result = pr.runcall(func, *args, **kwargs)
    pr.dump_stats(filename)
    return result


def speed_test(uuid):
    try:
        print("Starting speed test")
        t0 = time.time()
        with SessionContext(commit = True) as session:
            # Load the article
            a = Article.load_from_uuid(uuid, session)
            if a is not None:
                # Parse it and store the updated version
                a.parse(session, verbose = True)
        t1 = time.time()
        print("Parsing finished in {0:.2f} seconds".format(t1 - t0))
    finally:
        Article.cleanup()


print("Welcome to speedtest")

Settings.read(os.path.join(basepath, "config/Greynir.conf"))
with Fast_Parser() as fp:
    pass

#speed_test("dbc585e4-736c-11e6-a2bb-04014c605401")
profile(speed_test, "dbc585e4-736c-11e6-a2bb-04014c605401")

print("speedtest done")
