#!/usr/bin/env python
# type: ignore
"""
    Greynir: Natural language processing for Icelandic

    Utility program to populate the gender column of the persons table

    Copyright (C) 2021 Miðeind ehf.

       This program is free software: you can redistribute it and/or modify
       it under the terms of the GNU General Public License as published by
       the Free Software Foundation, either version 3 of the License, or
       (at your option) any later version.
       This program is distributed in the hope that it will be useful,
       but WITHOUT ANY WARRANTY; without even the implied warranty of
       MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
       GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see http://www.gnu.org/licenses/.


    This module is written in Python 3

"""

from settings import Settings, ConfigError
from db import SessionContext
from db.models import Person
from bindb import BIN_Db

try:
    # Read configuration file
    Settings.read("config/Greynir.conf")
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


