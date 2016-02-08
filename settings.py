"""
    Reynir: Natural language processing for Icelandic

    Settings module

    Copyright (c) 2015 Vilhjalmur Thorsteinsson
    All rights reserved
    See the accompanying README.md file for further licensing and copyright information.

    This module is written in Python 3 for Python 3.4

"""

import codecs
import locale

from contextlib import contextmanager
from collections import defaultdict
from threading import Lock


class ConfigError(Exception):

    """ Exception class for configuration errors """

    def __init__(self, s):
        Exception.__init__(self, s)
        self.fname = None
        self.line = 0

    def set_pos(self, fname, line):
        """ Set file name and line information, if not already set """
        if not self.fname:
            self.fname = fname
            self.line = line

    def __str__(self):
        """ Return a string representation of this exception """
        s = Exception.__str__(self)
        if not self.fname:
            return s
        return "File {0}, line {1}: {2}".format(self.fname, self.line, s)


class LineReader:
    """ Read lines from a text file, recognizing $include directives """

    def __init__(self, fname, outer_fname = None, outer_line = 0):
        self._fname = fname
        self._line = 0
        self._outer_fname = outer_fname
        self._outer_line = outer_line

    def fname(self):
        return self._fname

    def line(self):
        return self._line

    def lines(self):
        """ Generator yielding lines from a text file """
        self._line = 0
        try:
            with codecs.open(self._fname, "r", "utf-8") as inp:
                # Read config file line-by-line
                for s in inp:
                    self._line += 1
                    # Check for include directive: $include filename.txt
                    if s.startswith("$") and s.lower().startswith("$include "):
                        iname = s.split(maxsplit = 1)[1].strip()
                        rdr = LineReader(iname, self._fname, self._line)
                        # Successfully opened the include file: switch context to it
                        save = (self._line, self._fname)
                        self._line = 0
                        self._fname = iname
                        for incl_s in rdr.lines():
                            self._line += 1
                            yield incl_s
                        self._line, self._fname = save
                    else:
                        yield s
        except (IOError, OSError):
            if self._outer_fname:
                # This is an include file within an outer config file
                c = ConfigError("Error while opening or reading include file '{0}'".format(self._fname))
                c.set_pos(self._outer_fname, self._outer_line)
            else:
                # This is an outermost config file
                c = ConfigError("Error while opening or reading config file '{0}'".format(self._fname))
            raise c


class Abbreviations:

    """ Wrapper around dictionary of abbreviations, initialized from the config file """

    # Dictionary of abbreviations and their meanings
    DICT = { }
    # Single-word abbreviations, i.e. those with only one dot at the end
    SINGLES = set()

    @staticmethod
    def add (abbrev, meaning, gender, fl = None):
        """ Add an abbreviation to the dictionary. Called from the config file handler. """

        # print("Adding abbrev {0} meaning {1} gender {2} fl {3}".format(abbrev, meaning, gender, fl))
        # Append the abbreviation and its meaning in tuple form
        Abbreviations.DICT[abbrev] = (meaning, 0, gender, "skst" if fl is None else fl, abbrev, "-")
        if abbrev[-1] == '.' and '.' not in abbrev[0:-1]:
            # Only one dot, at the end
            Abbreviations.SINGLES.add(abbrev[0:-1]) # Lookup is without the dot


class Meanings:

    """ Wrapper around list of additional word meanings, initialized from the config file """

    # Dictionary of additional words and their meanings
    DICT = defaultdict(list)

    @staticmethod
    def add (stofn, ordmynd, ordfl, fl, beyging):
        """ Add word meaning to the dictionary. Called from the config file handler. """

        # Append the word and its meaning in tuple form
        assert ordmynd is not None
        assert ordfl is not None
        Meanings.DICT[ordmynd].append(
            (stofn or ordmynd, 0, ordfl, fl or "ob", ordmynd, beyging or "-"))


class VerbObjects:

    """ Wrapper around dictionary of verbs and their objects,
        initialized from the config file """

    # Dictionary of verbs by object (argument) number, 0, 1 or 2
    # Verbs can control zero, one or two arguments (noun phrases),
    # where each argument must have a particular case
    VERBS = [ set(), defaultdict(list), defaultdict(list) ]

    @staticmethod
    def add (verb, args):
        """ Add a verb and its objects (arguments). Called from the config file handler. """
        la = len(args)
        assert 0 <= la < 3
        if la:
            # Append a possible argument list
            VerbObjects.VERBS[la][verb].append(args)
        else:
            # Note that the verb can be argument-free
            VerbObjects.VERBS[0].add(verb)


class VerbSubjects:

    """ Wrapper around dictionary of verbs and their subjects,
        initialized from the config file """

    # Dictionary of verbs and their associated set of subject cases
    VERBS = defaultdict(set)
    _CASE = "þgf" # Default subject case

    @staticmethod
    def set_case(case):
        """ Set the case of the subject for the following verbs """
        if case not in { "þf", "þgf", "ef", "none", "lhþt" }:
            raise ConfigError("Unknown verb subject case '{0}' in verb_subjects".format(case))
        VerbSubjects._CASE = case

    @staticmethod
    def add (verb):
        """ Add a verb and its arguments. Called from the config file handler. """
        VerbSubjects.VERBS[verb].add(VerbSubjects._CASE)


class Prepositions:

    """ Wrapper around dictionary of prepositions, initialized from the config file """

    # Dictionary of prepositions: preposition -> { set of cases that it controls }
    PP = { }

    @staticmethod
    def add (prep, case):
        """ Add a preposition and its case. Called from the config file handler. """
        if prep in Prepositions.PP:
            # Already there: add a case to the set of controlled cases
            Prepositions.PP[prep].add(case)
        else:
            # Initialize the preposition with its controlled case
            Prepositions.PP[prep] = { case }


class AdjectiveTemplate:

    """ Wrapper around template list of adjective endings """

    # List of tuples: (ending, form_spec)
    ENDINGS = [ ]

    @classmethod
    def add (cls, ending, form):
        """ Add an adjective ending and its associated form. """
        cls.ENDINGS.append((ending, form))


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
        wlist = phrase.split()
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


class AmbigPhrases:

    """ Wrapper around dictionary of potentially ambiguous phrases, initialized from the config file """

    # List of tuples of ambiguous phrases and their word category lists
    LIST = []
    # Parsing dictionary keyed by first word of phrase
    DICT = defaultdict(list)

    @staticmethod
    def add (words, cats):
        """ Add an ambiguous phrase to the dictionary. Called from the config file handler. """

        # First add to phrase list
        ix = len(AmbigPhrases.LIST)

        # Append the phrase as well as its meaning in tuple form
        AmbigPhrases.LIST.append((words, cats))

        # Dictionary structure: dict { firstword: [ (restword_list, phrase_index) ] }
        AmbigPhrases.DICT[words[0]].append((words[1:], ix))

    @staticmethod
    def get_cats(ix):
        """ Return the word categories for the phrase with index ix """
        return AmbigPhrases.LIST[ix][1]


# Magic stuff to change locale context temporarily

@contextmanager
def changedlocale(new_locale):
    """ Change locale for collation temporarily within a context (with-statement) """
    # The newone locale parameter should be a tuple: ('is_IS', 'UTF-8')
    old_locale = locale.getlocale(locale.LC_COLLATE)
    try:
        locale.setlocale(locale.LC_COLLATE, new_locale)
        yield locale.strxfrm # Function to transform string for sorting
    finally:
        locale.setlocale(locale.LC_COLLATE, old_locale)

def sort_strings(strings, loc = None):
    """ Sort a list of strings using the specified locale's collation order """
    if loc is None:
        # Normal sort
        return sorted(strings)
    # Change locale temporarily for the sort
    with changedlocale(loc) as strxfrm:
        return sorted(strings, key = strxfrm)


class UnknownVerbs:

    """ Singleton class that wraps a set of unknown verbs encountered during parsing """

    _FILE = "UnknownVerbs.txt"
    _unknown = None
    _lock = Lock()

    @classmethod
    def add(cls, verb):
        """ Add a single verb to the unknown set """
        with cls._lock:
            if cls._unknown is None:
                cls._read_with_lock()
            cls._unknown.add(verb)

    @classmethod
    def read(cls):
        with cls._lock():
            cls._read_with_lock()

    @classmethod
    def _read_with_lock(cls):
        """ Read the unknown set from a file """
        cls._unknown = set()
        try:
            with codecs.open(cls._FILE, "r", "utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        cls._unknown.add(line)
        except (IOError, OSError):
            pass

    @classmethod
    def write(cls):
        """ Write the unknown set to a file """
        with cls._lock:
            if not cls._unknown:
                return
            vl = sort_strings(list(cls._unknown), ('is_IS', 'UTF-8'))
            with codecs.open(cls._FILE, "w", "utf-8") as f:
                for line in vl:
                    if line:
                        print(line, file = f)
            # Clear the unknown set so we don't add duplicate verbs to the file
            cls._unknown = None


class Preferences:

    """ Wrapper around disambiguation hints, initialized from the config file """

    # Dictionary keyed by word containing a list of tuples (worse, better)
    # where each is a list of terminal prefixes
    DICT = defaultdict(list)

    @staticmethod
    def add (word, worse, better, factor):
        """ Add a preference to the dictionary. Called from the config file handler. """
        Preferences.DICT[word].append((worse, better, factor))

    @staticmethod
    def get(word):
        """ Return a list of (worse, better, factor) tuples for the given word """
        return Preferences.DICT.get(word, None)


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
            raise ConfigError("Unknown configuration parameter '{0}'".format(par))

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
            m = val.split()
            if len(m) == 3:
                StaticPhrases.set_meaning(m)
            else:
                raise ConfigError("Meaning in static_phrases should have 3 arguments")
        else:
            raise ConfigError("Unknown configuration parameter '{0}' in static_phrases".format(par))

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
            p = par.split()
            if len(p) >= 1:
                gender = p[0].strip()
            if len(p) >= 2:
                fl = p[1].strip()
        Abbreviations.add(abbrev, m[1], gender, fl)

    @staticmethod
    def _handle_meanings(s):
        """ Handle additional word meanings in the settings section """
        # Format: stofn ordmynd ordfl fl (default ob) beyging (default -)
        a = s.split()
        if len(a) < 2 or len(a) > 5:
            print("{0}".format(s))
            print("{0}".format(a))
            raise ConfigError("Meaning should have two to five arguments, {0} given".format(len(a)))
        stofn = None
        fl = None
        beyging = None
        if len(a) == 2:
            # Short format: only ordmynd and ordfl
            ordmynd = a[0]
            ordfl = a[1]
        else:
            # Full format: at least three arguments, stofn ordmynd ordfl
            stofn = a[0]
            ordmynd = a[1]
            ordfl = a[2]
            fl = a[3] if len(a) >= 4 else None
            beyging = a[4] if len(a) >= 5 else None
        Meanings.add(stofn, ordmynd, ordfl, fl, beyging)

    @staticmethod
    def _handle_verb_objects(s):
        """ Handle verb object specifications in the settings section """
        # Format: verb [arg1] [arg2]
        a = s.split()
        if len(a) < 1 or len(a) > 3:
            raise ConfigError("Verb should have zero, one or two arguments")
        verb = a[0]
        VerbObjects.add(verb, a[1:])

    @staticmethod
    def _handle_verb_subjects(s):
        """ Handle verb subject specifications in the settings section """
        # Format: subject = [case] followed by verb list
        a = s.lower().split("=", maxsplit = 1)
        par = a[0].strip()
        if len(a) == 2:
            val = a[1].strip()
            if par == 'subject':
                VerbSubjects.set_case(val)
            else:
                raise ConfigError("Unknown setting '{0}' in verb_subjects".format(par))
            return
        assert len(a) == 1
        VerbSubjects.add(par)

    @staticmethod
    def _handle_prepositions(s):
        """ Handle preposition specifications in the settings section """
        # Format: preposition case
        a = s.split()
        if len(a) != 2:
            raise ConfigError("Preposition should have a single case argument")
        Prepositions.add(a[0], a[1])

    @staticmethod
    def _handle_preferences(s):
        """ Handle ambiguity preference hints in the settings section """
        # Format: word worse1 worse2... < better
        # If two less-than signs are used, the preference is even stronger (doubled)
        factor = 2
        a = s.lower().split("<<", maxsplit = 1)
        if len(a) != 2:
            # Not doubled preference: try a normal one
            a = s.lower().split("<", maxsplit = 1)
            factor = 1
        if len(a) != 2:
            raise ConfigError("Ambiguity preference missing less-than sign '<'")
        w = a[0].split()
        if len(w) < 2:
            raise ConfigError("Ambiguity preference must have at least one 'worse' category")
        b = a[1].split()
        if len(b) < 1:
            raise ConfigError("Ambiguity preference must have at least one 'better' category")
        Preferences.add(w[0], w[1:], b, factor)

    @staticmethod
    def _handle_ambiguous_phrases(s):
        """ Handle ambiguous phrase guidance in the settings section """
        # Format: "word1 word2..." cat1 cat2...
        if s[0] != '"':
            raise ConfigError("Ambiguous phrase must be enclosed in double quotes")
        q = s.rfind('"')
        if q <= 0:
            raise ConfigError("Ambiguous phrase must be enclosed in double quotes")
        # Obtain a list of the words in the phrase
        words = s[1:q].strip().lower().split()
        # Obtain a list of the corresponding word categories
        cats = s[q + 1:].strip().lower().split()
        if len(words) != len(cats):
            raise ConfigError("Ambiguous phrase has {0} words but {1} categories"
                .format(len(words), len(cats)))
        if len(words) < 2:
            raise ConfigError("Ambiguous phrase must contain at least two words")
        AmbigPhrases.add(words, cats)

    @staticmethod
    def _handle_adjective_template(s):
        """ Handle the template for new adjectives in the settings section """
        # Format: adjective-ending bin-meaning
        a = s.split()
        if len(a) != 2:
            raise ConfigError("Adjective template should have an ending and a form specifier")
        AdjectiveTemplate.add(a[0], a[1])


    def read(fname):
        """ Read configuration file """

        CONFIG_HANDLERS = {
            "settings" : Settings._handle_settings,
            "static_phrases" : Settings._handle_static_phrases,
            "abbreviations" : Settings._handle_abbreviations,
            "verb_objects" : Settings._handle_verb_objects,
            "verb_subjects" : Settings._handle_verb_subjects,
            "prepositions" : Settings._handle_prepositions,
            "preferences" : Settings._handle_preferences,
            "ambiguous_phrases" : Settings._handle_ambiguous_phrases,
            "meanings" : Settings._handle_meanings,
            "adjective_template" : Settings._handle_adjective_template
        }
        handler = None # Current section handler

        rdr = None
        try:
            rdr = LineReader(fname)
            for s in rdr.lines():
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
                        continue
                    raise ConfigError("Unknown section name '{0}'".format(section))
                if handler is None:
                    raise ConfigError("No handler for config line '{0}'".format(s))
                # Call the correct handler depending on the section
                handler(s)

        except ConfigError as e:
            # Add file name and line number information to the exception
            if rdr:
                e.set_pos(rdr.fname(), rdr.line())
            raise e

