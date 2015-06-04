"""
    Reynir: Natural language processing for Icelandic

    Settings module

    Author: Vilhjalmur Thorsteinsson

    This software is at a very early development stage.
    While that is the case, it is:
    Copyright (c) 2015 Vilhjalmur Thorsteinsson
    All rights reserved

    This module is written in Python 3 for Python 3.4

"""

import codecs

class Abbreviations:

    """ Wrapper around dictionary of abbreviations, initialized from the config file """

    # Dictionary of abbreviations and their meanings
    DICT = { }

    @staticmethod
    def add (abbrev, meaning, gender, fl = None):
        """ Add a static phrase to the dictionary. Called from the config file handler. """

        # print("Adding abbrev {0} meaning {1} gender {2} fl {3}".format(abbrev, meaning, gender, fl))
        # Append the abbreviation and its meaning in tuple form
        Abbreviations.DICT[abbrev] = (meaning, 0, gender, "skst" if fl is None else fl, abbrev, "-")


class Verbs:

    """ Wrapper around dictionary of verbs, initialized from the config file """

    # Dictionary of verbs by argument number, 0, 1 or 2
    VERBS = [ { }, { }, { } ]

    @staticmethod
    def add (verb, args):
        """ Add a verb and its arguments. Called from the config file handler. """

        la = len(args)
        assert 0 <= la < 3
        Verbs.VERBS[la][verb] = args if la else None


class Prepositions:

    """ Wrapper around dictionary of prepositions, initialized from the config file """

    # Dictionary of prepositions: preposition -> case
    PP = { }

    @staticmethod
    def add (prep, case):
        """ Add a preposition and its case. Called from the config file handler. """
        if prep in Prepositions.PP:
            # Already there: add a case
            Prepositions.PP[prep].append(case)
        else:
            # Initialize the preposition with its case
            Prepositions.PP[prep] = [ case ]


class StaticPhrases:

    """ Wrapper around dictionary of static phrases, initialized from the config file """

    # Default meaning for static phrases
    MEANING = ("ao", "frasi", "-")
    # List of all static phrases and their meanings
    LIST = []
    # Parsing dictionary keyed by first word of phrase
    DICT = { }

    @staticmethod
    def add (phrase):
        """ Add a static phrase to the dictionary. Called from the config file handler. """

        # First add to phrase list
        ix = len(StaticPhrases.LIST)
        m = StaticPhrases.MEANING

        # Append the phrase as well as its meaning in tuple form
        StaticPhrases.LIST.append((phrase, (phrase, 0, m[0], m[1], phrase, m[2])))

        # Dictionary structure: dict { firstword: [ (restword_list, phrase_index) ] }

        # Split phrase into words
        wlist = phrase.split(" ")
        # Dictionary is keyed by first word
        w = wlist[0]
        d = StaticPhrases.DICT
        if w in d:
            # First word already there: add a subsequent list
            d[w].append((wlist[1:], ix))
        else:
            # Create a new entry for this first word
            d[w] = [ (wlist[1:], ix) ]

    @staticmethod
    def set_meaning(meaning):
        """ Set the default meaning for static phrases """
        StaticPhrases.MEANING = tuple(meaning)

    @staticmethod
    def get_meaning(ix):
        """ Return the meaning of the phrase with index ix """
        return [ StaticPhrases.LIST[ix][1] ]


# Global settings

class Settings:

    # DNS name of host for word database
    DB_HOSTNAME = "localhost"

    # Flask server host
    HOST = "127.0.0.1"

    # Flask debug parameter
    DEBUG = False

    # Configuration settings from the Reynir.conf file

    @staticmethod
    def _handle_settings(s):
        """ Handle config parameters in the settings section """
        a = s.lower().split('=', maxsplit=1)
        par = a[0].strip()
        val = a[1].strip()
        if val == 'none':
            val = None
        elif val == 'true':
            val = True
        elif val == 'false':
            val = False
        if par == 'db_hostname':
            Settings.DB_HOSTNAME = val
        elif par == 'host':
            Settings.HOST = val
        elif par == 'debug':
            Settings.DEBUG = bool(val)
        else:
            print("Ignoring unknown config parameter {0}".format(par))

    @staticmethod
    def _handle_static_phrases(s):
        """ Handle static phrases in the settings section """
        if s[0] == '\"' and s[-1] == '\"':
            StaticPhrases.add(s[1:-1])
            return
        # Check for a meaning spec
        a = s.lower().split('=', maxsplit=1)
        par = a[0].strip()
        val = a[1].strip()
        if par == 'meaning':
            m = val.split(" ")
            if len(m) == 3:
                StaticPhrases.set_meaning(m)
            else:
                print("Meaning in static_phrases should have 3 arguments")
        else:
            print("Ignoring unknown config parameter {0} in static_phrases".format(par))

    @staticmethod
    def _handle_abbreviations(s):
        """ Handle abbreviations in the settings section """
        # Format: abbrev = "meaning" gender (kk|kvk|hk)
        a = s.split('=', maxsplit=1)
        abbrev = a[0].strip()
        m = a[1].strip().split('\"')
        par = ""
        if len(m) >= 3:
            # Something follows the last quote
            par = m[-1].strip()
        gender = "hk" # Default gender is neutral
        fl = None # Default word category is None
        if par:
            p = par.split(' ')
            if len(p) >= 1:
                gender = p[0].strip()
            if len(p) >= 2:
                fl = p[1].strip()
        Abbreviations.add(abbrev, m[1], gender, fl)

    @staticmethod
    def _handle_verbs(s):
        """ Handle verb specifications in the settings section """
        # Format: verb [arg1] [arg2]
        a = s.split()
        if len(a) < 1 or len(a) > 3:
            print("Verb should have zero, one or two arguments")
            return
        verb = a[0]
        Verbs.add(verb, a[1:])

    @staticmethod
    def _handle_prepositions(s):
        """ Handle preposition specifications in the settings section """
        # Format: preposition case
        a = s.split()
        if len(a) != 2:
            print("Preposition should have a single case argument")
            return
        Prepositions.add(a[0], a[1])

    def read(fname):
        """ Read configuration file """

        CONFIG_HANDLERS = {
            "settings" : Settings._handle_settings,
            "static_phrases" : Settings._handle_static_phrases,
            "abbreviations" : Settings._handle_abbreviations,
            "verbs" : Settings._handle_verbs,
            "prepositions" : Settings._handle_prepositions
        }
        handler = None # Current section handler

        try:
            with codecs.open(fname, "r", "utf-8") as inp:
                # Read config file line-by-line
                for s in inp:
                    # Ignore comments
                    ix = s.find('#')
                    if ix >= 0:
                        s = s[0:ix]
                    s = s.strip()
                    if not s:
                        # Blank line: ignore
                        continue
                    if s[0] == '[' and s[-1] == ']':
                        # New section
                        section = s[1:-1].strip().lower()
                        if section in CONFIG_HANDLERS:
                            handler = CONFIG_HANDLERS[section]
                        else:
                            print("Unknown section name '{0}'".format(section))
                            handler = None
                        continue
                    if handler is None:
                        print("No handler for config line '{0}'".format(s))
                    else:
                        # Call the correct handler depending on the section
                        handler(s)

        except (IOError, OSError):
            print("Error while opening or reading config file '{0}'".format(fname))


