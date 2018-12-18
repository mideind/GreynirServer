#!/usr/bin/env python
"""
	Look up all UN country names (in Icelandic) in BÍN.
	Print if country name is not found or has wrong category.
"""

from reynir.bindb import BIN_Db
from country_list import countries_for_language

bindb = BIN_Db()
countries = countries_for_language("is")

for iso_code, name in countries:
    meanings = bindb.meanings(name)

    if not len(meanings):
        print("MISSING: {0}".format(name))
        continue

    fl = [m.fl for m in meanings]
    if not "lönd" in fl:
        print("Category not 'lönd' for '{0}'".format(name))
        print(fl)
