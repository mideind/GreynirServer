"""
    Reynir: Natural language processing for Icelandic

    Settings module

    Copyright (c) 2016 Vilhjalmur Thorsteinsson

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

    This module reads and interprets the Reynir.conf configuration file.
    The file can include other files using the $include directive,
    making it easier to arrange configuration sections into logical
    and manageable pieces.

    Sections are identified like so: [ SectionName ]

    Comments start with # signs.

    Sections are interpreted by section handlers.

"""

import os
import codecs
import locale

from contextlib import contextmanager, closing
from collections import defaultdict
from threading import Lock


# The sorting locale used by default in the changedlocale function
_DEFAULT_SORT_LOCALE = ('IS_is', 'UTF-8')
# A set of all valid argument cases
_ALL_CASES = frozenset(("nf", "þf", "þgf", "ef"))
_ALL_GENDERS = frozenset(("kk", "kvk", "hk"))

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
                        # Do some path magic to allow the included path
                        # to be relative to the current file path, or a
                        # fresh (absolute) path by itself
                        head, _ = os.path.split(self._fname)
                        iname = os.path.join(head, iname)
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
    # Potential sentence finishers, i.e. those with a dot at the end, marked with an asterisk
    # in the config file
    FINISHERS = set()

    @staticmethod
    def add (abbrev, meaning, gender, fl = None):
        """ Add an abbreviation to the dictionary. Called from the config file handler. """
        # Check for sentence finishers
        if abbrev.endswith("*"):
            finisher = True
            abbrev = abbrev[0:-1]
            if not abbrev.endswith("."):
                raise ConfigError("Only abbreviations ending with periods can be sentence finishers")
        else:
            finisher = False
        # Append the abbreviation and its meaning in tuple form
        Abbreviations.DICT[abbrev] = (meaning, 0, gender, "skst" if fl is None else fl, abbrev, "-")
        if abbrev[-1] == '.' and '.' not in abbrev[0:-1]:
            # Only one dot, at the end
            Abbreviations.SINGLES.add(abbrev[0:-1]) # Lookup is without the dot
        if finisher:
            Abbreviations.FINISHERS.add(abbrev)


class Meanings:

    """ Wrapper around list of additional word meanings, initialized from the config file """

    # Dictionary of additional words and their meanings
    DICT = defaultdict(list) # Keyed by word form
    ROOT = defaultdict(list) # Keyed by word root (stem)

    @staticmethod
    def add (stofn, ordmynd, ordfl, fl, beyging):
        """ Add word meaning to the dictionary. Called from the config file handler. """

        # Append the word and its meaning in tuple form
        assert ordmynd is not None
        assert ordfl is not None
        if not stofn:
            stofn = ordmynd
        Meanings.DICT[ordmynd].append(
            (stofn, 0, ordfl, fl or "ob", ordmynd, beyging or "-"))
        Meanings.ROOT[stofn].append(
            (stofn, 0, ordfl, fl or "ob", ordmynd, beyging or "-"))

    @staticmethod
    def add_composite (stofn, ordfl):
        """ Add composite word forms by putting a prefix on existing BIN word forms.
            Called from the config file handler. """

        from bindb import BIN_Db

        assert stofn is not None
        assert ordfl is not None
        a = stofn.split("-")
        if len(a) != 2:
            raise ConfigError("Composite word meaning must contain a single hyphen")
        with closing(BIN_Db.get_db()) as db:
            prefix = a[0]
            stem = a[1]
            m = db._forms(stem)
            if m:
                for w in m:
                    if w.ordfl == ordfl:
                        t = (prefix + w.stofn, 0, ordfl, w.fl, prefix + w.ordmynd, w.beyging)
                        Meanings.DICT[prefix + w.ordmynd].append(t)
                        Meanings.ROOT[prefix + w.stofn].append(t)


class VerbObjects:

    """ Wrapper around dictionary of verbs and their objects,
        initialized from the config file """

    # Dictionary of verbs by object (argument) number, 0, 1 or 2
    # Verbs can control zero, one or two arguments (noun phrases),
    # where each argument must have a particular case
    VERBS = [ set(), defaultdict(list), defaultdict(list) ]
    # Dictionary of verb forms with associated scores
    # The key is the normal form of the verb + the associated cases,
    # separated by underscores, e.g. "vera_þgf_ef"
    SCORES = dict()
    # Dictionary of verbs where, for each verb + argument cases, we store a set of
    # preposition_case keys, i.e. "frá_þgf"
    PREPOSITIONS = defaultdict(set)

    @staticmethod
    def add (verb, args, pronouns):
        """ Add a verb and its objects (arguments). Called from the config file handler. """
        la = len(args)
        assert 0 <= la < 4
        score = 0
        if la > 0 and args[-1].startswith("$score(") and args[-1].endswith(")"):
            # There is an associated score with this verb form, to be taken
            # into consideration by the reducer
            s = args[-1][7:-1]
            try:
                score = int(s)
            except ValueError:
                raise ConfigError("Invalid score for verb form")
            # Cut the score off the end
            args = args[0:-1]
            la -= 1
        if la:
            for case in args:
                if case not in _ALL_CASES:
                    raise ConfigError("Invalid case for verb object: '{0}'".format(case))
            # Append a possible argument list
            arglists = VerbObjects.VERBS[la][verb]
            if args not in arglists:
                # Avoid adding the same argument list twice
                arglists.append(args)
        else:
            # Note that the verb can be argument-free
            VerbObjects.VERBS[0].add(verb)
        # Store the score, if nonzero
        verb_with_cases = "_".join([ verb ] + args)
        if score != 0:
            VerbObjects.SCORES[verb_with_cases] = score
        # pronouns is a list of tuples: (pronoun, case), e.g. ("í", "þgf")
        for p, case in pronouns:
            VerbObjects.PREPOSITIONS[verb_with_cases].add(p + "_" + case)

    @staticmethod
    def verb_matches_preposition(verb_with_cases, prep_with_case):
        """ Does the given preposition with the given case fit the verb? """
        if False: # Settings.DEBUG:
            print("verb_matches_preposition: verb {0}, prep {1}, verb found {2}, prep found {3}"
                .format(verb_with_cases, prep_with_case,
                    verb_with_cases in VerbObjects.PREPOSITIONS,
                    verb_with_cases in VerbObjects.PREPOSITIONS and
                    prep_with_case in VerbObjects.PREPOSITIONS[verb_with_cases]))
        return verb_with_cases in VerbObjects.PREPOSITIONS and \
            prep_with_case in VerbObjects.PREPOSITIONS[verb_with_cases]


class VerbSubjects:

    """ Wrapper around dictionary of verbs and their subjects,
        initialized from the config file """

    # Dictionary of verbs and their associated set of subject cases
    VERBS = defaultdict(set)
    _CASE = "þgf" # Default subject case

    @staticmethod
    def set_case(case):
        """ Set the case of the subject for the following verbs """
        #if case not in { "þf", "þgf", "ef", "none", "lhþt" }:
        #    raise ConfigError("Unknown verb subject case '{0}' in verb_subjects".format(case))
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


class DisallowedNames:

    """ Wrapper around list of disallowed person name forms """

    # Dictionary of name stems : sets of cases
    STEMS = { }

    @classmethod
    def add (cls, name, cases):
        """ Add an adjective ending and its associated form. """
        cls.STEMS[name] = set(cases)


class StaticPhrases:

    """ Wrapper around dictionary of static phrases, initialized from the config file """

    # Default meaning for static phrases
    MEANING = ("ao", "frasi", "-")
    # Dictionary of the static phrases with their meanings
    MAP = { }
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

        mtuple = (phrase, 0, m[0], m[1], phrase, m[2])

        # Append the phrase as well as its meaning in tuple form
        StaticPhrases.LIST.append((phrase, mtuple))

        # Add to the main phrase dictionary
        StaticPhrases.MAP[phrase] = mtuple

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

    @staticmethod
    def lookup(phrase):
        """ Lookup an entire phrase """
        return StaticPhrases.MAP.get(phrase)


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


class NoIndexWords:

    """ Wrapper around set of word stems and categories that should
        not be indexed """

    SET = set() # Set of (stem, cat) tuples
    _CAT = "so" # Default category

    @staticmethod
    def set_cat(cat):
        """ Set the category for the following word stems """
        NoIndexWords._CAT = cat

    @staticmethod
    def add (stem):
        """ Add a word stem and its category. Called from the config file handler. """
        NoIndexWords.SET.add((stem, NoIndexWords._CAT))


class Topics:

    """ Wrapper around topics, represented as a dict (name: set) """

    DICT = defaultdict(set) # Dict of topic name: set
    ID = dict() # Dict of identifier: topic name
    THRESHOLD = dict() # Dict of identifier: threshold (as a float)
    _name = None

    @staticmethod
    def set_name(name):
        """ Set the topic name for the words that follow """
        a = name.split('|')
        Topics._name = tname = a[0].strip()
        identifier = a[1].strip() if len(a) > 1 else None
        if identifier is not None and not identifier.isidentifier():
            raise ConfigError("Topic identifier must be a valid Python identifier")
        try:
            threshold = float(a[2].strip()) if len(a) > 2 else None
        except ValueError:
            raise ConfigError("Topic threshold must be a floating point number")
        Topics.ID[tname] = identifier
        Topics.THRESHOLD[tname] = threshold

    @staticmethod
    def add (word):
        """ Add a word stem and its category. Called from the config file handler. """
        if Topics._name is None:
            raise ConfigError("Must set topic name (topic = X) before specifying topic words")
        if '/' not in word:
            raise ConfigError("Topic words must include a slash '/' and a word category")
        cat = word.split('/', maxsplit = 1)[1]
        if cat not in { "kk", "kvk", "hk", "lo", "so", "entity", "person", "person_kk", "person_kvk" }:
            raise ConfigError("Topic words must be nouns, verbs, adjectives, entities or persons")
        # Add to topic set, after replacing spaces with underscores
        Topics.DICT[Topics._name].add(word.replace(" ", "_"))


# Magic stuff to change locale context temporarily

@contextmanager
def changedlocale(new_locale = None):
    """ Change locale for collation temporarily within a context (with-statement) """
    # The newone locale parameter should be a tuple: ('is_IS', 'UTF-8')
    old_locale = locale.getlocale(locale.LC_COLLATE)
    try:
        locale.setlocale(locale.LC_COLLATE, new_locale or _DEFAULT_SORT_LOCALE)
        yield locale.strxfrm # Function to transform string for sorting
    finally:
        locale.setlocale(locale.LC_COLLATE, old_locale)

def sort_strings(strings, loc = None):
    """ Sort a list of strings using the specified locale's collation order """
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
            vl = sort_strings(list(cls._unknown))
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


class NounPreferences:

    """ Wrapper for noun preferences, i.e. to assign priorities to different
        noun stems that can have identical word forms. """

    # This is a dict of noun word forms, giving the relative priorities
    # of different genders
    DICT = defaultdict(dict)

    @staticmethod
    def add (word, worse, better):
        """ Add a preference to the dictionary. Called from the config file handler. """
        if worse not in _ALL_GENDERS or better not in _ALL_GENDERS:
            raise ConfigError("Noun priorities must specify genders (kk, kvk, hk)")
        d = NounPreferences.DICT[word]
        worse_score = d.get(worse)
        better_score = d.get(better)
        if worse_score is not None:
            if better_score is not None:
                raise ConfigError("Conflicting priorities for noun {0}".format(word))
            better_score = worse_score + 2
        elif better_score is not None:
            worse_score = better_score - 2
        else:
            worse_score = -1
            better_score = 1
        d[worse] = worse_score
        d[better] = better_score


# Global settings

class Settings:

    # DNS name of host for word database
    DB_HOSTNAME = "localhost"
    DB_PORT = os.environ.get('GREYNIR_DB_PORT', '5432')

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
        elif par == 'db_port':
            Settings.DB_PORT = val
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
        a = s.split('=', maxsplit=1)
        par = a[0].strip()
        val = a[1].strip()
        if par.lower() == 'meaning':
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
        # Format: abbrev[*] = "meaning" gender (kk|kvk|hk)
        # An asterisk after an abbreviation ending with a period
        # indicates that the abbreviation may finish a sentence
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

        if len(a) == 2 and "-" in ordmynd:
            # Creating new meanings by prefixing existing ones
            Meanings.add_composite(ordmynd, ordfl)
        else:
            Meanings.add(stofn, ordmynd, ordfl, fl, beyging)

    @staticmethod
    def _handle_verb_objects(s):
        """ Handle verb object specifications in the settings section """
        # Format: verb [arg1] [arg2] [/pronoun arg]...
        pronouns = []
        # Process pronoun arguments, if any
        ap = s.split("/")
        s = ap[0]
        ix = 1
        while len(ap) > ix:
            # We expect something like 'af þgf'
            p = ap[ix].strip()
            parg = p.split()
            if len(parg) != 2:
                raise ConfigError("Pronoun should have exactly one argument")
            if parg[1] not in _ALL_CASES:
                raise ConfigError("Unknown argument case for pronoun")
            pronouns.append((parg[0], parg[1]))
            ix += 1
        a = s.split()
        if len(a) < 1 or len(a) > 4:
            raise ConfigError("Verb should have zero, one or two arguments and an optional score")
        verb = a[0]
        if not verb.isidentifier():
            raise ConfigError("Verb '{0}' is not a valid word".format(verb))
        VerbObjects.add(verb, a[1:], pronouns)

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
    def _handle_noindex_words(s):
        """ Handle no index instructions in the settings section """
        # Format: category = [cat] followed by word stem list
        a = s.lower().split("=", maxsplit = 1)
        par = a[0].strip()
        if len(a) == 2:
            val = a[1].strip()
            if par == 'category':
                NoIndexWords.set_cat(val)
            else:
                raise ConfigError("Unknown setting '{0}' in noindex_words".format(par))
            return
        assert len(a) == 1
        NoIndexWords.add(par)

    @staticmethod
    def _handle_topics(s):
        """ Handle topic specifications """
        # Format: name = [topic name] followed by word stem list in the form word/cat
        a = s.split("=", maxsplit = 1)
        par = a[0].strip()
        if len(a) == 2:
            val = a[1].strip()
            if par.lower() == 'topic':
                Topics.set_name(val)
            else:
                raise ConfigError("Unknown setting '{0}' in topics".format(par))
            return
        assert len(a) == 1
        Topics.add(par)

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
        # If two less-than signs are used, the preference is even stronger (tripled)
        factor = 3
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
    def _handle_noun_preferences(s):
        """ Handle noun preference hints in the settings section """
        # Format: noun worse1 worse2... < better
        # The worse and better specifiers are gender names (kk, kvk, hk)
        a = s.lower().split("<", maxsplit = 1)
        if len(a) != 2:
            raise ConfigError("Noun preference missing less-than sign '<'")
        w = a[0].split()
        if len(w) != 2:
            raise ConfigError("Noun preference must have exactly one 'worse' gender")
        b = a[1].split()
        if len(b) != 1:
            raise ConfigError("Noun preference must have exactly one 'better' gender")
        NounPreferences.add(w[0], w[1], b[0])

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

    @staticmethod
    def _handle_disallowed_names(s):
        """ Handle disallowed person name forms from the settings section """
        # Format: Name-stem case1 case2...
        a = s.split()
        if len(a) < 2:
            raise ConfigError("Disallowed names must specify a name and at least one case")
        DisallowedNames.add(a[0], a[1:])

    @staticmethod
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
            "noun_preferences" : Settings._handle_noun_preferences,
            "ambiguous_phrases" : Settings._handle_ambiguous_phrases,
            "meanings" : Settings._handle_meanings,
            "adjective_template" : Settings._handle_adjective_template,
            "disallowed_names" : Settings._handle_disallowed_names,
            "noindex_words" : Settings._handle_noindex_words,
            "topics" : Settings._handle_topics
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

