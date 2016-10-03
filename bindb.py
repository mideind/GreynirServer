"""
    Reynir: Natural language processing for Icelandic

    BIN database access module

    Copyright (c) 2016 Vilhjalmur Thorsteinsson
    All rights reserved
    See the accompanying README.md file for further licensing and copyright information.

    This module encapsulates access to the BIN (Beygingarlýsing íslensks nútímamáls)
    database of word forms, including lookup of abbreviations and basic strategies
    for handling missing words.

    The database is assumed to be stored in PostgreSQL. It is accessed via
    the Psycopg2 connector.

"""

from functools import lru_cache
from collections import namedtuple
from heapq import nsmallest
from operator import itemgetter
import threading

# Import the Psycopg2 connector for PostgreSQL
try:
    # For CPython
    import psycopg2.extensions as psycopg2ext
    import psycopg2
except ImportError:
    # For PyPy
    import psycopg2cffi.extensions as psycopg2ext
    import psycopg2cffi as psycopg2

from settings import Settings, Abbreviations, AdjectiveTemplate, Meanings, StaticPhrases
from dawgdictionary import Wordbase

# Make Psycopg2 and PostgreSQL happy with UTF-8
psycopg2ext.register_type(psycopg2ext.UNICODE)
psycopg2ext.register_type(psycopg2ext.UNICODEARRAY)


# Size of LRU cache for word lookups
CACHE_SIZE = 512
CACHE_SIZE_MEANINGS = 1024 # Most common lookup function (meanings of a particular word form)

# Named tuple for word meanings fetched from the BÍN database (lexicon)
BIN_Meaning = namedtuple('BIN_Meaning', ['stofn', 'utg', 'ordfl', 'fl', 'ordmynd', 'beyging'])


class LFU_Cache:

    """ Least-frequently-used (LFU) cache for word lookups.
        Based on a pattern by Raymond Hettinger:
        http://code.activestate.com/recipes/498245-lru-and-lfu-cache-decorators/
    """

    class Counter(dict):
        """ Mapping where default values are zero """
        def __missing__(self, key):
            return 0

    def __init__(self, maxsize = CACHE_SIZE):
        self.cache = {}                     # Mapping of keys to results
        self.use_count = self.Counter()     # Times each key has been accessed
        self.maxsize = maxsize
        self.hits = self.misses = 0
        self.lock = threading.Lock()        # The cache may be accessed in parallel by multiple threads

    def lookup(self, key, func):
        """ Lookup a key in the cache, calling func(key) to obtain the data if not already there """
        with self.lock:
            self.use_count[key] += 1
            # Get cache entry or compute if not found
            try:
                result = self.cache[key]
                self.hits += 1
            except KeyError:
                result = func(key)
                self.cache[key] = result
                self.misses += 1

                # Purge the 10% least frequently used cache entries
                if len(self.cache) > self.maxsize:
                    for key, _ in nsmallest(self.maxsize // 10,
                        self.use_count.items(), key = itemgetter(1)):

                        del self.cache[key], self.use_count[key]

            return result


class BIN_Db:

    """ Encapsulates the BÍN database of word forms """

    # Thread local storage - used for database connections
    tls = threading.local()

    # Database connection parameters
    _DB_NAME = "bin"
    _DB_USER = "reynir" # This user typically has only SELECT privileges on the database
    _DB_PWD = "reynir"
    _DB_TABLE = "ord2"

    # Query strings
    _DB_Q_MEANINGS = "select stofn, utg, ordfl, fl, ordmynd, beyging " \
        "from " + _DB_TABLE + " where ordmynd=(%s);"
    _DB_Q_FORMS = "select stofn, utg, ordfl, fl, ordmynd, beyging " \
        "from " + _DB_TABLE + " where stofn=(%s);"
    _DB_Q_UTG = "select stofn, utg, ordfl, fl, ordmynd, beyging " \
        "from " + _DB_TABLE + " where utg=(%s);"
    _DB_Q_UTG_BEYGING = "select stofn, utg, ordfl, fl, ordmynd, beyging " \
        "from " + _DB_TABLE + " where utg=(%s) and beyging=(%s);"
    _DB_Q_NAMES = "select stofn, utg, ordfl, fl, ordmynd, beyging " \
        "from " + _DB_TABLE + " where stofn=(%s) and fl='ism';"

    # Adjective endings
    _ADJECTIVE_TEST = "leg" # Check for adjective if word contains 'leg'

    # Singleton LFU caches for word meaning and form lookups
    _meanings_cache = LFU_Cache(maxsize = CACHE_SIZE_MEANINGS)
    _forms_cache = LFU_Cache()

    @classmethod
    def get_db(cls):
        """ Obtain a database connection instance """
        # We have one DB connection and cursor per thread.
        db = None
        if hasattr(cls.tls, "bin_db"):
            # Connection already established in this thread: re-use it
            db = cls.tls.bin_db

        if db is None:
            # New connection in this thread
            db = cls.tls.bin_db = cls().open(Settings.DB_HOSTNAME)

        if db is None:
            raise Exception("Could not open BIN database on host {0}".format(Settings.DB_HOSTNAME))

        return db

    def __init__(self):
        """ Initialize DB connection instance """
        self._conn = None # Connection
        self._c = None # Cursor
        # Cache descriptors for the lookup functions
        self._meanings_func = lambda key: self._meanings_cache.lookup(key, getattr(self, "_meanings"))
        self._forms_func = lambda key: self._forms_cache.lookup(key, getattr(self, "_forms"))

    def open(self, host):
        """ Open and initialize a database connection """
        self._conn = psycopg2.connect(dbname=BIN_Db._DB_NAME,
            user=BIN_Db._DB_USER, password=BIN_Db._DB_PWD,
            host=host, client_encoding="utf8")

        if not self._conn:
            print("Unable to open connection to database")
            return None

        # Ask for automatic commit after all operations
        # We're doing only reads, so this is fine and makes things less complicated
        self._conn.autocommit = True
        self._c = self._conn.cursor()
        return None if self._c is None else self

    def close(self):
        """ Close the DB connection and the associated cursor """
        self._c.close()
        self._conn.close()
        self._c = self._conn = None
        if BIN_Db.tls.bin_db is self:
            BIN_Db.tls.bin_db = None

    def _meanings(self, w):
        """ Return a list of all possible grammatical meanings of the given word """
        assert self._c is not None
        m = None
        try:
            self._c.execute(BIN_Db._DB_Q_MEANINGS, [ w ])
            # Map the returned data from fetchall() to a list of instances
            # of the BIN_Meaning namedtuple
            g = self._c.fetchall()
            if g is not None:
                # Order the meanings by priority, so that the most
                # common/likely ones are first in the list and thus
                # matched more readily than the less common ones
                def priority(m):
                    # Order "VH" verbs (viðtengingarháttur) after other forms
                    # Also order past tense ("ÞT") after present tense
                    # and plural after singular
                    if m.ordfl != "so":
                        return 0
                    prio = 4 if "VH" in m.beyging else 0
                    prio += 2 if "ÞT" in m.beyging else 0
                    prio += 1 if "FT" in m.beyging else 0
                    return prio
                m = sorted(map(BIN_Meaning._make, g), key = priority)
                if w in Meanings.DICT:
                    # There are additional word meanings in the Meanings dictionary,
                    # coming from the settings file: append them
                    m.extend([ BIN_Meaning._make(add_m) for add_m in Meanings.DICT[w] ])
        except (psycopg2.DataError, psycopg2.ProgrammingError) as e:
            print("Word {0} causing DB exception {1}".format(w, e))
            m = None
        return m

    def _forms(self, w):
        """ Return a list of all possible forms of a particular root (stem) """
        assert self._c is not None
        m = None
        try:
            self._c.execute(BIN_Db._DB_Q_FORMS, [ w ])
            # Map the returned data from fetchall() to a list of instances
            # of the BIN_Meaning namedtuple
            g = self._c.fetchall()
            if g is not None:
                m = list(map(BIN_Meaning._make, g))
                if w in Meanings.ROOT:
                    # There are additional word meanings in the Meanings dictionary,
                    # coming from the settings file: append them
                    m.extend([ BIN_Meaning._make(add_m) for add_m in Meanings.ROOT[w] ])
        except (psycopg2.DataError, psycopg2.ProgrammingError) as e:
            print("Word {0} causing DB exception {1}".format(w, e))
            m = None
        return m

    @lru_cache(maxsize = CACHE_SIZE)
    def lookup_utg(self, utg, beyging = None):
        """ Return a list of meanings with the given integer id ('utg' column) """
        assert self._c is not None
        m = None
        try:
            if beyging:
                self._c.execute(BIN_Db._DB_Q_UTG_BEYGING, [ utg, beyging ])
            else:
                self._c.execute(BIN_Db._DB_Q_UTG, [ utg ])
            # Map the returned data from fetchall() to a list of instances
            # of the BIN_Meaning namedtuple
            g = self._c.fetchall()
            if g is not None:
                m = list(map(BIN_Meaning._make, g))
        except (psycopg2.DataError, psycopg2.ProgrammingError) as e:
            print("Query for utg {0} causing DB exception {1}".format(utg, e))
            m = None
        return m

    def lookup_word(self, w, at_sentence_start, auto_uppercase = False):
        """ Given a word form, look up all its possible meanings """
        return self._lookup(w, at_sentence_start, auto_uppercase, self._meanings_func)

    def lookup_form(self, w, at_sentence_start):
        """ Given a word root (stem), look up all its forms """
        return self._lookup(w, at_sentence_start, False, self._forms_func)

    @lru_cache(maxsize = CACHE_SIZE)
    def lookup_name_gender(self, name):
        """ Given a person name, lookup its gender """
        assert self._c is not None
        if not name:
            return "hk" # Unknown gender
        w = name.split(maxsplit = 1)[0] # First name
        try:
            # Query the database for the first name
            self._c.execute(BIN_Db._DB_Q_NAMES, [ w ])
            g = self._c.fetchall()
            if g is not None:
                # Appear to have found some ism entries where stofn=w
                m = next(map(BIN_Meaning._make, g), None)
                if m:
                    # Return the ordfl of the first one
                    return m.ordfl
            # Not found in the database: try the manual additions from Main.conf
            if w in Meanings.ROOT:
                # First name found?
                g = (BIN_Meaning._make(add_m) for add_m in Meanings.ROOT[w])
                m = next((x for x in g if x.fl in { "ism", "nafn" }), None)
                if m:
                    # Found a meaning with fl='ism' or fl='nafn'
                    return m.ordfl
            # The first name was not found: check whether the full name is
            # in the static phrases
            m = StaticPhrases.lookup(name)
            if m is not None:
                m = BIN_Meaning._make(m)
                if m.fl in { "ism", "nafn" }:
                    return m.ordfl
        except (psycopg2.DataError, psycopg2.ProgrammingError) as e:
            print("Word {0} causing DB exception {1}".format(w, e))
        return "hk" # Unknown gender

    @staticmethod
    def prefix_meanings(mlist, prefix):
        """ Return a meaning list with a prefix added to the stofn and ordmynd attributes """
        return [
            BIN_Meaning(prefix + "-" + r.stofn, r.utg, r.ordfl, r.fl,
            prefix + "-" + r.ordmynd, r.beyging)
            for r in mlist
        ] if prefix else mlist

    @staticmethod
    def _lookup(w, at_sentence_start, auto_uppercase, lookup):
        """ Lookup a simple or compound word in the database and return its meaning(s) """

        def lookup_abbreviation(w):
            """ Lookup abbreviation from abbreviation list """
            # Remove brackets, if any, before lookup
            if w[0] == '[':
                clean_w = w[1:-1]
                # Check for abbreviation that also ended a sentence and
                # therefore had its end period cut off
                if not clean_w.endswith('.'):
                    clean_w += '.'
            else:
                clean_w = w
            # Return a single-entity list with one meaning
            m = Abbreviations.DICT.get(clean_w, None)
            return None if m is None else [ BIN_Meaning._make(m) ]

        # Start with a straightforward lookup of the word

        if auto_uppercase and w.islower():
            if len(w) == 1:
                # Special case for single letter words:
                # if they exist in BÍN, don't convert them
                m = lookup(w)
                if not m:
                    # If they don't exist in BÍN, treat them as uppercase
                    # abbreviations (probably middle names)
                    w = w.upper() + '.'
            else:
                # Check whether this word has an uppercase form in the database
                w_upper = w.capitalize()
                m = lookup(w_upper)
                if m:
                    # Yes: assume it should be uppercase
                    w = w_upper
                    at_sentence_start = False # No need for special case here
                else:
                    # No: go for the regular lookup
                    m = lookup(w)
        else:
            m = lookup(w)

        if at_sentence_start or not m:
            # No meanings found in database, or at sentence start
            # Try a lowercase version of the word, if different
            lower_w = w.lower()
            if lower_w != w:
                # Do another lookup, this time for lowercase only
                if not m:
                    # This is a word that contains uppercase letters
                    # and was not found in BÍN in its original form
                    # Try an abbreviation before doing a lowercase lookup
                    # (since some abbreviations are also words, i.e. LÍN)
                    m = lookup_abbreviation(w)
                    if not m:
                        m = lookup(lower_w)
                    elif w[0] == '[':
                        # Remove brackets from known abbreviations
                        w = w[1:-1]
                else:
                    m.extend(lookup(lower_w))

        if m:
            # Most common path out of this function
            return (w, m)

        if (lower_w != w or w[0] == '['):
            # Still nothing: check abbreviations
            m = lookup_abbreviation(w)
            if not m and w[0] == '[':
                # Could be an abbreviation with periods at the start of a sentence:
                # Lookup a lowercase version
                m = lookup_abbreviation(lower_w)
            if m and w[0] == '[':
                # Remove brackets from known abbreviations
                w = w[1:-1]

        if not m and BIN_Db._ADJECTIVE_TEST in lower_w:
            # Not found: Check whether this might be an adjective
            # ending in 'legur'/'leg'/'legt'/'legir'/'legar' etc.
            llw = len(lower_w)
            for aend, beyging in AdjectiveTemplate.ENDINGS:
                if lower_w.endswith(aend) and llw > len(aend):
                    prefix = lower_w[0 : llw - len(aend)]
                    # Construct an adjective descriptor
                    if m is None:
                        m = []
                    m.append(BIN_Meaning(prefix + "legur", 0, "lo", "alm", lower_w, beyging))
            if lower_w.endswith("lega") and llw > 4:
                # For words ending with "lega", add a possible adverb meaning
                if m is None:
                    m = []
                m.append(BIN_Meaning(lower_w, 0, "ao", "ob", lower_w, "-"))

        if not m:
            # Still nothing: check compound words
            cw = Wordbase.dawg().slice_compound_word(w)
            if not cw and lower_w != w:
                # If not able to slice in original case, try lower case
                cw = Wordbase.dawg().slice_compound_word(lower_w)
            if cw:
                # This looks like a compound word:
                # use the meaning of its last part
                prefix = "-".join(cw[0:-1])
                m = lookup(cw[-1])
                m = BIN_Db.prefix_meanings(m, prefix)

        if not m and lower_w.startswith('ó'):
            # Check whether an adjective without the 'ó' prefix is found in BÍN
            # (i.e. create 'óhefðbundinn' from 'hefðbundinn')
            suffix = lower_w[1:]
            if suffix:
                om = lookup(suffix)
                if om:
                    m = [ BIN_Meaning("ó" + r.stofn, r.utg, r.ordfl, r.fl,
                            "ó" + r.ordmynd, r.beyging)
                            for r in om if r.ordfl == "lo" ]

        if not m and auto_uppercase and w.islower():
            # If no meaning found and we're auto-uppercasing,
            # convert this to upper case (could very well be a name
            # of a person or entity)
            w = w.capitalize()

        # noinspection PyRedundantParentheses
        return (w, m)


