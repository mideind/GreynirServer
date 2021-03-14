# type: ignore
"""
    Greynir: Natural language processing for Icelandic

    Settings module

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

    This module reads and interprets the Greynir.conf configuration file.
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


class NoIndexWords:

    """ Wrapper around set of word stems and categories that should
        not be indexed """

    SET = set() # Set of (stem, cat) tuples
    _CAT = "so" # Default category

    # The word categories that are indexed in the words table
    CATEGORIES_TO_INDEX = frozenset((
        "kk", "kvk", "hk", "person_kk", "person_kvk", "entity",
        "lo", "so"
    ))

    @staticmethod
    def set_cat(cat):
        """ Set the category for the following word stems """
        NoIndexWords._CAT = cat

    @staticmethod
    def add(stem):
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
    def add(word):
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


# Global settings

class Settings:

    # Postgres SQL database server hostname and port
    DB_HOSTNAME = os.environ.get('GREYNIR_DB_HOST', 'localhost')
    DB_PORT = os.environ.get('GREYNIR_DB_PORT', '5432') # Default PostgreSQL port
    DB_USERNAME = os.environ.get("GREYNIR_DB_USERNAME", "reynir")
    DB_PASSWORD = os.environ.get("GREYNIR_DB_PASSWORD", "reynir")

    try:
        DB_PORT = int(DB_PORT)
    except ValueError:
        raise ConfigError("Invalid environment variable value: DB_PORT = {0}".format(DB_PORT))

    # Flask server host and port
    HOST = os.environ.get('GREYNIR_HOST', 'localhost')
    PORT = os.environ.get('GREYNIR_PORT', '5000')
    try:
        PORT = int(PORT)
    except ValueError:
        raise ConfigError("Invalid environment variable value: GREYNIR_PORT = {0}".format(PORT))

    # Flask debug parameter
    DEBUG = False

    # Similarity server
    SIMSERVER_HOST = os.environ.get('SIMSERVER_HOST', 'localhost')
    SIMSERVER_PORT = os.environ.get('SIMSERVER_PORT', '5001')
    try:
        SIMSERVER_PORT = int(SIMSERVER_PORT)
    except ValueError:
        raise ConfigError("Invalid environment variable value: SIMSERVER_PORT = {0}".format(SIMSERVER_PORT))

    # Configuration settings from the Greynir.conf file

    @staticmethod
    def _handle_settings(s):
        """ Handle config parameters in the settings section """
        a = s.lower().split('=', maxsplit=1)
        par = a[0].strip().lower()
        val = a[1].strip()
        if val.lower() == 'none':
            val = None
        elif val.lower() == 'true':
            val = True
        elif val.lower() == 'false':
            val = False
        try:
            if par == 'db_hostname':
                Settings.DB_HOSTNAME = val
            elif par == 'db_port':
                Settings.DB_PORT = int(val)
            elif par == 'host':
                Settings.HOST = val
            elif par == 'port':
                Settings.PORT = int(val)
            elif par == 'simserver_host':
                Settings.SIMSERVER_HOST = val
            elif par == 'simserver_port':
                Settings.SIMSERVER_PORT = int(val)
            elif par == 'debug':
                Settings.DEBUG = bool(val)
            else:
                raise ConfigError("Unknown configuration parameter '{0}'".format(par))
        except ValueError:
            raise ConfigError("Invalid parameter value: {0} = {1}".format(par, val))

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
    def read(fname):
        """ Read configuration file """

        CONFIG_HANDLERS = {
            "settings" : Settings._handle_settings,
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
