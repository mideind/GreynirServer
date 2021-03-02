#!/usr/bin/env python3
"""

    Greynir: Natural language processing for Icelandic

    Additional vocabulary utility

    Copyright (C) 2021 Miðeind ehf.
    Original author: Vilhjálmur Þorsteinsson

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


    This utility generates a text file with an additional vocabulary
    for BÍN, i.e. entries that are missing from the regular BÍN .csv file.

    The source data is read from the [meanings] section in the Vocab.conf
    settings file (which is usually included in Greynir.conf) and written
    to the file resources/ord.add.csv. That file is then read by the
    bincompress.py program, merged with the main BÍN file (ord.csv) and
    compressed into the binary trie file ord.compressed.

"""

import os
import sys
import re
from collections import defaultdict, namedtuple

# Import the Psycopg2 connector for PostgreSQL
try:
    # Prefer Psycopg2cffi, which should work both for PyPy and CPython
    import psycopg2cffi.extensions as psycopg2ext
    import psycopg2cffi as psycopg2
except ImportError:
    # Try plain Psycopg2 for CPython
    import psycopg2.extensions as psycopg2ext  # type: ignore
    import psycopg2  # type: ignore


# Make Psycopg2 and PostgreSQL happy with UTF-8
psycopg2ext.register_type(psycopg2ext.UNICODE)
psycopg2ext.register_type(psycopg2ext.UNICODEARRAY)

# Hack to make this Python program executable from the tools subdirectory
basepath, _ = os.path.split(os.path.realpath(__file__))
_TOOLS = os.sep + "tools"
if basepath.endswith(_TOOLS):
    basepath = basepath[0 : -len(_TOOLS)]
    sys.path.append(basepath)


# Note: We can't use settings from GreynirPackage because it
# reads package resource streams, not plain text files
from settings import Settings, LineReader, ConfigError


BIN_Meaning = namedtuple(
    "BIN_Meaning", ["stofn", "utg", "ordfl", "fl", "ordmynd", "beyging"]
)


class Meanings:

    """ Wrapper around list of additional word meanings, initialized from the config file """

    DICT = defaultdict(set)  # Keyed by word form
    ROOT = defaultdict(set)  # Keyed by word root (stem)

    _conn = None
    _cursor = None
    _DB_NAME = "bin"
    # This user typically has only SELECT privileges on the database
    _DB_USER = Settings.DB_USERNAME
    _DB_PWD = Settings.DB_PASSWORD
    _DB_TABLE = "ord"
    _DB_Q_FORMS = (
        "SELECT stofn, utg, ordfl, fl, ordmynd, beyging "
        "FROM " + _DB_TABLE + " WHERE stofn=(%s);"
    )

    # All possible declination forms of adjectives (48 in total)
    _UNDECLINED_ADJECTIVE_TEMPLATE = [
        "FVB-HK-EFFT",
        "FVB-HK-ÞGFFT",
        "FVB-HK-ÞFFT",
        "FVB-HK-NFFT",
        "FVB-HK-EFET",
        "FVB-HK-ÞGFET",
        "FVB-HK-ÞFET",
        "FVB-HK-NFET",
        "FVB-KVK-EFFT",
        "FVB-KVK-ÞGFFT",
        "FVB-KVK-ÞFFT",
        "FVB-KVK-NFFT",
        "FVB-KVK-EFET",
        "FVB-KVK-ÞGFET",
        "FVB-KVK-ÞFET",
        "FVB-KVK-NFET",
        "FVB-KK-EFFT",
        "FVB-KK-ÞGFFT",
        "FVB-KK-ÞFFT",
        "FVB-KK-NFFT",
        "FVB-KK-EFET",
        "FVB-KK-ÞGFET",
        "FVB-KK-ÞFET",
        "FVB-KK-NFET",
        "FSB-HK-EFFT",
        "FSB-HK-ÞGFFT",
        "FSB-HK-ÞFFT",
        "FSB-HK-NFFT",
        "FSB-HK-EFET",
        "FSB-HK-ÞGFET",
        "FSB-HK-ÞFET",
        "FSB-HK-NFET",
        "FSB-KVK-EFFT",
        "FSB-KVK-ÞGFFT",
        "FSB-KVK-ÞFFT",
        "FSB-KVK-NFFT",
        "FSB-KVK-EFET",
        "FSB-KVK-ÞGFET",
        "FSB-KVK-ÞFET",
        "FSB-KVK-NFET",
        "FSB-KK-EFFT",
        "FSB-KK-ÞGFFT",
        "FSB-KK-ÞFFT",
        "FSB-KK-NFFT",
        "FSB-KK-EFET",
        "FSB-KK-ÞGFET",
        "FSB-KK-ÞFET",
        "FSB-KK-NFET",
    ]

    _CAT_SET = None  # BIN_Token word categories

    @staticmethod
    def open_db(host, port):
        c = Meanings._conn = psycopg2.connect(
            dbname=Meanings._DB_NAME,
            user=Meanings._DB_USER,
            password=Meanings._DB_PWD,
            host=host,
            port=port,
            client_encoding="utf8",
        )
        c.autocommit = True
        Meanings._cursor = c.cursor()

    @staticmethod
    def close_db():
        Meanings._cursor.close()
        Meanings._conn.close()

    @staticmethod
    def forms(w):
        """ Return a list of all possible forms of a particular root (stem) """
        c = Meanings._cursor
        assert c is not None
        m = None
        try:
            c.execute(Meanings._DB_Q_FORMS, [w])
            # Map the returned data from fetchall() to a list of instances
            # of the BIN_Meaning namedtuple
            g = c.fetchall()
            if g is not None:
                m = list(map(BIN_Meaning._make, g))
        except (psycopg2.DataError, psycopg2.ProgrammingError) as e:
            print("Word '{0}' caused DB exception {1}".format(w, e))
            m = None
        return m

    @staticmethod
    def add(stofn, ordmynd, ordfl, fl, beyging):
        """ Add word meaning to the dictionary. Called from the config file handler. """
        assert ordmynd is not None
        assert ordfl is not None
        if not stofn:
            stofn = ordmynd
        # Append the word and its meaning in tuple form
        if ordfl == "lo" and not beyging:
            # Special case for undeclined adjectives:
            # create all 48 forms
            for b in Meanings._UNDECLINED_ADJECTIVE_TEMPLATE:
                m = (stofn, -1, ordfl, fl or "ob", ordmynd, b)
                Meanings.DICT[ordmynd].add(m)
                Meanings.ROOT[stofn].add(m)
        else:
            m = (stofn, -1, ordfl, fl or "ob", ordmynd, beyging or "-")
            Meanings.DICT[ordmynd].add(m)
            Meanings.ROOT[stofn].add(m)

    @staticmethod
    def add_composite(stofn, ordfl, fl, *, utg=None):
        """ Add composite word forms by putting a prefix on existing BIN word forms.
            Called from the config file handler. """
        assert stofn is not None
        assert ordfl is not None
        # Handle cases like 'Suður-Ameríku-ríki' correctly
        a = stofn.rsplit("-", maxsplit=1)
        assert len(a) == 2
        stem = a[1]
        if stem[0].isupper():
            # Uppercase stem (such as 'Norður-Makedónía'): keep the hyphen
            prefix = a[0] + "-"
        else:
            prefix = a[0]
        m = Meanings.forms(stem)
        if m:
            last_utg = None
            for w in m:
                if w.ordfl == ordfl and (utg is None or utg == w.utg):
                    # Check for ambiguity between different lemmas
                    if last_utg is None:
                        last_utg = w.utg
                    elif w.utg != last_utg:
                        # We are encountering two different ids (utg):
                        # this probably needs to be disambiguated
                        raise ConfigError(
                            "Ambiguous word stem: {0}/{1}".format(w.stofn, w.ordfl)
                        )
                    # Matches the requested category and also the
                    # id number (utg), if given: create a new entry in the
                    # Meanings dict, having id -1
                    t = (
                        prefix + w.stofn,
                        -1,
                        ordfl,
                        fl or w.fl,
                        prefix + w.ordmynd,
                        w.beyging,
                    )
                    Meanings.DICT[prefix + w.ordmynd].add(t)
                    Meanings.ROOT[prefix + w.stofn].add(t)

    @staticmethod
    def add_entry(s):
        """ Handle additional word meanings in the settings section """
        # Format: stofn ordmynd ordfl fl (default ob) beyging (default -)
        a = s.split()
        if len(a) < 2 or len(a) > 5:
            raise ConfigError(
                "Meaning should have two to five arguments, {0} given".format(len(a))
            )
        stofn = None
        fl = None
        beyging = None
        utg = None
        if 3 <= len(a) <= 4 and re.match(r"\d+$", a[-1]):
            # An id number (utg) is being given in the last argument
            utg = int(a[-1])
            # Cut it off the end and proceed
            a = a[:-1]
        if len(a) <= 3:
            # Short format: ordmynd ordfl [fl]
            ordmynd = a[0]
            ordfl = a[1]
            if len(a) == 3:
                fl = a[2]
        else:
            # Full format: at least four arguments, stofn ordmynd ordfl fl
            if utg is not None:
                raise ConfigError(
                    "An id number (utg) can't be specified with a full meaning"
                )
            stofn = a[0]
            ordmynd = a[1]
            ordfl = a[2]
            fl = a[3]
            beyging = a[4] if len(a) >= 5 else None

        if utg is not None and "-" not in ordmynd:
            raise ConfigError(
                "An id number (utg) should only be specified for a composite word"
            )
        if len(a) <= 3 and "-" in ordmynd:
            # Creating new meanings by prefixing existing ones
            Meanings.add_composite(ordmynd, ordfl, fl, utg=utg)
        else:
            assert utg is None
            Meanings.add(stofn, ordmynd, ordfl, fl, beyging)

    @staticmethod
    def read_config(fname):
        rdr = None
        try:
            rdr = LineReader(fname)
            for s in rdr.lines():
                # Ignore comments
                ix = s.find("#")
                if ix >= 0:
                    s = s[0:ix]
                s = s.strip()
                if not s:
                    # Blank line: ignore
                    continue
                if s[0] == "[" and s[-1] == "]":
                    # Handle section name, if found (it is redundant in this case)
                    section = s[1:-1].strip().lower()
                    if section != "meanings":
                        raise ConfigError("Unknown section name '{0}'".format(section))
                    continue
                Meanings.add_entry(s)
        except ConfigError as e:
            # Add file name and line number information to the exception
            # if it's not already there
            if rdr is not None:
                e.set_pos(rdr.fname(), rdr.line())
            raise e

    @staticmethod
    def read_family_names(fname):
        """ Read config/FamilyNames.conf and create corresponding family
            name entries in the output file. Family names are identical
            in all cases, and are listed as having neutral gender. """
        with open(fname, "r") as f:
            for s in f:
                # Ignore comments
                ix = s.find("#")
                if ix >= 0:
                    s = s[0:ix]
                s = s.strip()
                if not s:
                    # Blank line: ignore
                    continue
                # Check whether the family name is already in the database
                mm = Meanings.forms(s)
                fl_set = set(m.fl for m in mm)
                if fl_set & {"ism", "föð", "móð", "ætt"}:
                    # Already known as a name: skip it
                    continue
                # Add the family name in all four cases, singular, neutral gender
                for case in ("NF", "ÞF", "ÞGF", "EF"):
                    # Format: stofn ordmynd ordfl fl (default ob) beyging (default -)
                    Meanings.add(s, s, "hk", "ætt", case + "ET")


if __name__ == "__main__":

    print("Welcome to the Greynir additional vocabulary builder\n")

    src = os.path.join(basepath, "config", "Vocab.conf")
    family_names = os.path.join(basepath, "config", "FamilyNames.conf")
    fname = os.path.join(basepath, "resources", "ord.add.csv")
    print("Reading from {0} and {1}".format(src, family_names))
    print("Writing to {0}".format(fname))

    try:
        # Read configuration file
        Settings.read(os.path.join(basepath, "config", "GreynirSimple.conf"))
        print(
            "Accessing BÍN database at {0}:{1}"
            .format(Settings.DB_HOSTNAME, Settings.DB_PORT)
        )
        Meanings.open_db(Settings.DB_HOSTNAME, Settings.DB_PORT)
        Meanings.read_config(src)
        Meanings.read_family_names(family_names)
        Meanings.close_db()
    except ConfigError as e:
        print("Configuration error: {0}".format(e))
        quit()

    if len(Meanings.DICT) == 0:
        print(
            "No vocabulary entries ([meanings] section) found in "
            "Vocab.conf file"
        )
        quit()

    with open(fname, "w") as f:
        for _, meanings in Meanings.DICT.items():
            for m in meanings:
                stofn, utg, ordfl, fl, ordmynd, beyging = m
                f.write(
                    "{0};{1};{2};{3};{4};{5}\n".format(
                        stofn, utg, ordfl, fl, ordmynd, beyging
                    )
                )
    print("\nDone")
