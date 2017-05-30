#!/usr/bin/env python
"""
    Reynir: Natural language processing for Icelandic

    Utility program to populate the gender column of the persons table

    Copyright (c) 2016 Vilhjalmur Thorsteinsson
    All rights reserved
    See the accompanying README.md file for further licensing and copyright information.

    This module is written in Python 3

"""

from settings import Settings, ConfigError
from scraperdb import SessionContext, Person
from bindb import BIN_Db

try:
    # Read configuration file
    Settings.read("config/Reynir.conf")
except ConfigError as e:
    print("Configuration error: {0}".format(e))
    quit()

with SessionContext(commit = True) as session, BIN_Db.get_db() as bdb:

    # Iterate through the persons
    q = session.query(Person) \
        .filter((Person.gender == None) | (Person.gender == 'hk')) \
        .order_by(Person.name) \
        .yield_per(200)

    lastname = ""

    for p in q:

        p.gender = bdb.lookup_name_gender(p.name)
        if p.name != lastname:
            print("{0} {1}".format(p.gender, p.name))
            lastname = p.name


