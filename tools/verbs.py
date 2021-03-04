#!/usr/bin/env python
# type: ignore

"""

    Greynir: Natural language processing for Icelandic

    Verb information collector

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


    This module reads information about Icelandic verbs from a text
    file and emits it in a format usable by Greynir.

"""

import sys
import locale
from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime

from settings import (
    Settings, changedlocale, sort_strings, ConfigError,
    VerbObjects, Prepositions
)


class Verb:

    """ Describe a single verb """

    CASEMAP = { "NOM" : "nf", "ACC" : "þf", "DAT" : "þgf", "GEN" : "ef",
        "sig" : "þf", "sér" : "þgf", "sín" : "ef",
        "þess" : "ef" }

    def __init__(self, nom):
        # Nominal form of verb ("að X")
        self.nom = nom
        # For each case combination (e.g. "", "þf", "þf þgf"),
        # we store a set of possible prepositions ("í þf", "til ef")
        self.cases = defaultdict(set)

    def __str__(self):

        if self.cases:
            # Return one line per combination of cases
            def pad(s, field = 16):
                l = len(s)
                return s if l > field else s + (field - l) * ' '

            return "\n".join(pad(self.nom) + (" " if c else "") + \
                c + ("".join(" /" + prep for prep in self.cases[c])) \
                for c in sort_strings(self.cases.keys()))

        return self.nom

    def add(self, first, args):
        """ Add new information about a verb """
        if first in { "NOM", "NOM FT" }:
            # Normal nominal form: Páll [sagnorð] viðfang1 viðfang2... fs1 fs2...
            c = [] # Cases
            p = set() # Prepositions
            for i, a in enumerate(args):
                g = self.CASEMAP.get(a)
                if g is None:
                    # Next token is not indicative of an argument case
                    if a.islower():
                        if a not in Prepositions.PP:
                            # An unknown word follows: don't use this
                            return
                        # One or more preposition follows
                        while i < len(args) and args[i] in Prepositions.PP:
                            prep = args[i]
                            i += 1
                            if i < len(args):
                                pcase = self.CASEMAP.get(args[i])
                                if pcase is None:
                                    break
                                p.add(prep + " " + pcase)
                                i += 1
                    break
                c.append(g)
            self.cases[" ".join(c)] |= p

    def enum_cases(self):
        """ Generator for all argument cases of this verb, yielded as lists """
        for c in self.cases.keys():
            yield c.split()

    def enum_cases_and_preps(self):
        """ Generator for argument cases and prepositions, yielded as tuples of (cases, preps) """
        for c in sort_strings(self.cases.keys()):
            yield (c, self.cases[c])


def add(verbs, line):
    """ Process a single text line """
    if line.startswith("( )"):
        firstpart = "( )"
        line = line[4:]
        rest = line.split()
    else:
        rest = line.split()
        firstpart, *rest = rest # Note Python 3 syntax
    # Move plural indicator, if any, into the first part
    if rest and rest[0] == "FT":
        firstpart += " " + rest[0]
        rest = rest[1:]
    if firstpart in { "NOM", "NOM FT" } and rest and "/" not in rest[0]: # Skip "viðrar/viðraði" and similar forms
        if rest[0] in verbs:
            v = verbs[rest[0]]
        else:
            v = verbs[rest[0]] = Verb(rest[0])
        v.add(firstpart, rest[1:])


def read_verbs(fname):
    """ Read the given text file with verb descriptors """
    verbs = dict()
    with open(fname, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                add(verbs, line)
    return verbs


def display(verbs):
    """ Display a list of verbs """
    for v in verbs:
        print("{0}".format(v))


def check_missing(verbs):
    """ Lookup verbs in Verbs.conf and report missing or different ones """
    count = 0
    for v in verbs:
        for cases in v.enum_cases():
            lc = len(cases)
            d = VerbObjects.VERBS[lc]

            def matches(nom):
                if not nom in d:
                    return False
                if lc == 0:
                    return True
                for clist in d[nom]:
                    if all(cases[i] == clist[i] for i in range(lc)):
                        return True
                return False

            if not matches(v.nom):
                print("# Verbs.conf missing {0} {1}".format(v.nom, " ".join(cases)))
                #if count < 20:
                #    print("v.nom in d is {0}, lc is {1}, cases is {2}, d[v.nom] is {3}"
                #        .format(v.nom in d, lc, cases, d[v.nom] if v.nom in d and lc > 0 else "N/A"))
                count += 1
    return count


def main():
    """ Main program """
    try:
        Settings.read("config/Greynir.conf")
    except ConfigError as e:
        print("Configuration error: {0}".format(e), file = sys.stderr)
        return 2

    verbs = read_verbs("resources/sagnir.txt")
    with changedlocale() as strxfrm:
        verbs_sorted = sorted(verbs.values(), key = lambda x: strxfrm(x.nom))
    print("#\n# Verb list generated by verbs.py from resources/sagnir.txt")
    print("#", str(datetime.utcnow())[0:19], "\n#\n")
    display(verbs_sorted)
    print("\n# Total: {0} distinct verbs\n".format(len(verbs)))

    # Check which verbs are missing or different in Verbs.conf
    #count = check_missing(verbs_sorted)
    #print("\n# Total: {0} missing verb forms\n".format(count))

    return 0


if __name__ == "__main__":
    sys.exit(main())

