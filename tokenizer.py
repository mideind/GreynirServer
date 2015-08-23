"""
    Reynir: Natural language processing for Icelandic

    Tokenizer module

    Author: Vilhjalmur Thorsteinsson

    This software is at a very early development stage.
    While that is the case, it is:
    Copyright (c) 2015 Vilhjalmur Thorsteinsson
    All rights reserved
    See the accompanying README.md file for further licensing and copyright information.

    This module is written in Python 3 for Python 3.4

    The function tokenize() consumes a text string and
    returns a generator of tokens. Each token is a tuple,
    typically having the form (type, word, meaning),
    where type is one of the constants specified in the
    TOK class, word is the original word found in the
    source text, and meaning is a list of tuples with
    potential interpretations of the word, as retrieved
    from the BIN database of word forms.

"""

from contextlib import closing
from functools import lru_cache
from collections import namedtuple

import re
import codecs
import datetime

# Import the Psycopg2 connector for PostgreSQL
try:
    # For CPython
    import psycopg2.extensions as psycopg2ext
    import psycopg2
except ImportError:
    # For PyPy
    import psycopg2cffi.extensions as psycopg2ext
    import psycopg2cffi as psycopg2

# Make Psycopg2 and PostgreSQL happy with UTF-8
psycopg2ext.register_type(psycopg2ext.UNICODE)
psycopg2ext.register_type(psycopg2ext.UNICODEARRAY)

from settings import Settings, StaticPhrases, Abbreviations, Meanings, AmbigPhrases
from dawgdictionary import Wordbase


# Recognized punctuation

LEFT_PUNCTUATION = "([„«#$€<"
RIGHT_PUNCTUATION = ".,:;)]!%?“»”’…°>"
CENTER_PUNCTUATION = "\"*&+=@©|—–-"
NONE_PUNCTUATION = "/\\'~"
PUNCTUATION = LEFT_PUNCTUATION + CENTER_PUNCTUATION + RIGHT_PUNCTUATION + NONE_PUNCTUATION

# Punctuation symbols that may occur at the end of a sentence, after the period
SENTENCE_FINISHERS = ")]“»”’"

CLOCK_WORD = "klukkan"
CLOCK_ABBREV = "kl"

# Punctuation types: left, center or right of word

TP_LEFT = 1   # Whitespace to the left
TP_CENTER = 2 # Whitespace to the left and right
TP_RIGHT = 3  # Whitespace to the right
TP_NONE = 4   # No whitespace

# Numeric digits

DIGITS = { d for d in "0123456789" } # Set of digit characters

# Set of all cases (nominative, accusative, dative, possessive)

ALL_CASES = { "nf", "þf", "þgf", "ef" }

# Named tuple for person names, including case and gender

PersonName = namedtuple('PersonName', ['name', 'gender', 'case'])

# Named tuple for tokens

Tok = namedtuple('Tok', ['kind', 'txt', 'val'])

# Named tuple for word meanings fetched from the BÍN database (lexicon)

BIN_Meaning = namedtuple('BIN_Meaning', ['stofn', 'utg', 'ordfl', 'fl', 'ordmynd', 'beyging'])

# Token types

class TOK:

    PUNCTUATION = 1
    TIME = 2
    DATE = 3
    YEAR = 4
    NUMBER = 5
    WORD = 6
    TELNO = 7
    PERCENT = 8
    URL = 9
    ORDINAL = 10
    TIMESTAMP = 11
    CURRENCY = 12
    AMOUNT = 13
    PERSON = 14
    UNKNOWN = 15

    P_BEGIN = 10001 # Paragraph begin
    P_END = 10002 # Paragraph end

    S_BEGIN = 11001 # Sentence begin
    S_END = 11002 # Sentence end

    # Token descriptive names

    descr = {
        PUNCTUATION: "PUNCTUATION",
        TIME: "TIME",
        TIMESTAMP: "TIMESTAMP",
        DATE: "DATE",
        YEAR: "YEAR",
        NUMBER: "NUMBER",
        CURRENCY: "CURRENCY",
        AMOUNT: "AMOUNT",
        PERSON: "PERSON",
        WORD: "WORD",
        UNKNOWN: "UNKNOWN",
        TELNO: "TELNO",
        PERCENT: "PERCENT",
        URL: "URL",
        ORDINAL: "ORDINAL",
        P_BEGIN: "BEGIN PARA",
        P_END: "END PARA",
        S_BEGIN: "BEGIN SENT",
        S_END: "END SENT"
    }

    # Token constructors

    def Punctuation(w):
        tp = TP_CENTER # Default punctuation type
        if w:
            if w[0] in LEFT_PUNCTUATION:
                tp = TP_LEFT
            elif w[0] in RIGHT_PUNCTUATION:
                tp = TP_RIGHT
            elif w[0] in NONE_PUNCTUATION:
                tp = TP_NONE
        return Tok(TOK.PUNCTUATION, w, tp)

    def Time(w, h, m, s):
        return Tok(TOK.TIME, w, (h, m, s))

    def Date(w, y, m, d):
        return Tok(TOK.DATE, w, (y, m, d))

    def Timestamp(w, y, mo, d, h, m, s):
        return Tok(TOK.TIMESTAMP, w, (y, mo, d, h, m, s))

    def Year(w, n):
        return Tok(TOK.YEAR, w, n)

    def Telno(w):
        return Tok(TOK.TELNO, w, None)

    def Number(w, n, cases=None, genders=None):
        """ cases is a list of possible cases for this number
            (if it was originally stated in words) """
        return Tok(TOK.NUMBER, w, (n, cases, genders))

    def Currency(w, iso, cases=None, genders=None):
        """ cases is a list of possible cases for this currency name
            (if it was originally stated in words, i.e. not abbreviated) """
        return Tok(TOK.CURRENCY, w, (iso, cases, genders))

    def Amount(w, iso, n, cases=None, genders=None):
        """ cases is a list of possible cases for this amount
            (if it was originally stated in words) """
        return Tok(TOK.AMOUNT, w, (iso, n, cases, genders))

    def Percent(w, n):
        return Tok(TOK.PERCENT, w, n)

    def Ordinal(w, n):
        return Tok(TOK.ORDINAL, w, n)

    def Url(w):
        return Tok(TOK.URL, w, None)

    def Word(w, m):
        """ m is a list of BIN_Meaning tuples fetched from the BÍN database """
        return Tok(TOK.WORD, w, m)

    def Unknown(w):
        return Tok(TOK.UNKNOWN, w, None)

    def Person(w, m):
        """ m is a list of PersonName tuples: (name, gender, case) """
        return Tok(TOK.PERSON, w, m)

    def Begin_Paragraph():
        return Tok(TOK.P_BEGIN, None, None)

    def End_Paragraph():
        return Tok(TOK.P_END, None, None)

    def Begin_Sentence(num_parses = 0, err_index = None):
        return Tok(TOK.S_BEGIN, None, (num_parses, err_index))

    def End_Sentence():
        return Tok(TOK.S_END, None, None)


def parse_digits(w):
    """ Parse a raw token starting with a digit """

    s = re.match(r'\d{1,2}:\d\d:\d\d', w)
    if s:
        # Looks like a 24-hour clock, H:M:S
        w = s.group()
        p = w.split(':')
        h = int(p[0])
        m = int(p[1])
        s = int(p[2])
        return TOK.Time(w, h, m, s), s.end()
    s = re.match(r'\d{1,2}:\d\d', w)
    if s:
        # Looks like a 24-hour clock, H:M
        w = s.group()
        p = w.split(':')
        h = int(p[0])
        m = int(p[1])
        return TOK.Time(w, h, m, 0), s.end()
    s = re.match(r'\d{1,2}\.\d{1,2}\.\d{2,4}', w) or re.match(r'\d{1,2}/\d{1,2}/\d{2,4}', w)
    if s:
        # Looks like a date
        w = s.group()
        if '/' in w:
            p = w.split('/')
        else:
            p = w.split('.')
        y = int(p[2])
        if y <= 99:
            y = 2000 + y
        m = int(p[1])
        d = int(p[0])
        if m > 12 and d <= 12:
            # Probably wrong way around
            m, d = d, m
        return TOK.Date(w, y, m, d), s.end()
    s = re.match(r'\d{1,2}/\d{1,2}', w) or re.match(r'\d{1,2}\.\d{1,2}', w)
    if s:
        # Looks like a date
        w = s.group()
        if '/' in w:
            p = w.split('/')
        else:
            p = w.split('.')
        m = int(p[1])
        d = int(p[0])
        if m > 12 and d <= 12:
            # Probably wrong way around
            m, d = d, m
        return TOK.Date(w, 0, m, d), s.end()
    s = re.match(r'\d\d\d\d$', w) or re.match(r'\d\d\d\d[^\d]', w)
    if s:
        n = int(w[0:4])
        if 1776 <= n <= 2100:
            # Looks like a year
            return TOK.Year(w[0:4], n), 4
    s = re.match(r'\d\d\d-\d\d\d\d', w)
    if s:
        # Looks like a telephone number
        return TOK.Telno(s.group()), s.end()
    s = re.match(r'\d+(\.\d\d\d)*,\d+', w)
    if s:
        # Real number formatted with decimal comma and possibly thousands separator
        w = s.group()
        n = re.sub(r'\.', '', w) # Eliminate thousands separators
        n = re.sub(r',', '.', n) # Convert decimal comma to point
        return TOK.Number(w, float(n)), s.end()
    s = re.match(r'\d+(\.\d\d\d)*', w)
    if s:
        # Integer, possibly with a '.' thousands separator
        w = s.group()
        n = re.sub(r'\.', '', w) # Eliminate thousands separators
        return TOK.Number(w, int(n)), s.end()
    s = re.match(r'\d+(,\d\d\d)*\.\d+', w)
    if s:
        # Real number, possibly with a thousands separator and decimal comma/point
        w = s.group()
        n = re.sub(r',', '', w) # Eliminate thousands separators
        return TOK.Number(w, float(n)), s.end()
    s = re.match(r'\d+(,\d\d\d)*', w)
    if s:
        # Integer, possibly with a ',' thousands separator
        w = s.group()
        n = re.sub(r',', '', w) # Eliminate thousands separators
        return TOK.Number(w, int(n)), s.end()
    # Strange thing
    return TOK.Unknown(w), len(w)


def parse_tokens(txt):
    """ Generator that parses contiguous text into a stream of tokens """

    rough = txt.split()

    for w in rough:
        # Handle each sequence of non-whitespace characters

        if w.isalpha():
            # Shortcut for most common case: pure word
            yield TOK.Word(w, None)
            continue

        # More complex case of mixed punctuation, letters and numbers
        while w:
            # Punctuation
            ate = False
            while w and w[0] in PUNCTUATION:
                ate = True
                if len(w) >= 3 and w[0:3] == "...":
                    # Treat ellipsis as one piece of punctuation
                    yield TOK.Punctuation("…")
                    w = w[3:]
                elif len(w) == 2 and (w == "[[" or w == "]]"):
                    # Begin or end paragraph marker
                    if w == "[[":
                        yield TOK.Begin_Paragraph()
                    else:
                        yield TOK.End_Paragraph()
                    w = w[2:]
                else:
                    yield TOK.Punctuation(w[0])
                    w = w[1:]
            # Numbers or other stuff starting with a digit
            if w and w[0] in DIGITS:
                ate = True
                t, eaten = parse_digits(w)
                yield t
                # Continue where the digits parser left off
                w = w[eaten:]
            # Alphabetic characters
            if w and w[0].isalpha():
                ate = True
                i = 1
                lw = len(w)
                while i < lw and (w[i].isalpha() or w[i] == '.'):
                    # We allow dots to occur inside words in the case of
                    # abbreviations
                    i += 1
                if w[i-1] == '.':
                    # Don't eat periods at the end of words
                    i -= 1
                yield TOK.Word(w[0:i], None)
                w = w[i:]
            if not ate:
                # Ensure that we eat everything, even unknown stuff
                yield TOK.Unknown(w[0])
                w = w[1:]


def parse_particles(token_stream):
    """ Parse a stream of tokens looking for 'particles'
        (simple token pairs and abbreviations) and making substitutions """

    token = None
    try:

        # Maintain a one-token lookahead
        token = next(token_stream)
        while True:
            next_token = next(token_stream)
            # Make the lookahead checks we're interested in

            clock = False

            # Check for $[number]
            if token.kind == TOK.PUNCTUATION and token.txt == '$' and \
                next_token.kind == TOK.NUMBER:

                token = TOK.Amount(token.txt + next_token.txt, "USD", next_token.val[0]) # Unknown gender
                next_token = next(token_stream)

            # Check for €[number]
            if token.kind == TOK.PUNCTUATION and token.txt == '€' and \
                next_token.kind == TOK.NUMBER:

                token = TOK.Amount(token.txt + next_token.txt, "EUR", next_token.val[0]) # Unknown gender
                next_token = next(token_stream)

            # Coalesce abbreviations ending with a period into a single
            # abbreviation token
            if next_token.kind == TOK.PUNCTUATION and next_token.txt == '.':
                if token.kind == TOK.WORD and ('.' in token.txt or
                    token.txt.lower() in Abbreviations.SINGLES or token.txt in Abbreviations.SINGLES):
                    # Abbreviation: make a special token for it
                    # and advance the input stream
                    clock = token.txt.lower() == CLOCK_ABBREV
                    token = TOK.Word("[" + token.txt + ".]", None)
                    next_token = next(token_stream)

            # Coalesce 'klukkan'/[kl.] + time or number into a time
            if (next_token.kind == TOK.TIME or next_token.kind == TOK.NUMBER):
                if clock or (token.kind == TOK.WORD and token.txt.lower() == CLOCK_WORD):
                    # Match: coalesce and step to next token
                    if next_token.kind == TOK.NUMBER:
                        token = TOK.Time(CLOCK_ABBREV + ". " + next_token.txt, next_token.val[0], 0, 0)
                    else:
                        token = TOK.Time(CLOCK_ABBREV + ". " + next_token.txt,
                            next_token.val[0], next_token.val[1], next_token.val[2])
                    next_token = next(token_stream)

            # Coalesce percentages into a single token
            if next_token.kind == TOK.PUNCTUATION and next_token.txt == '%':
                if token.kind == TOK.NUMBER:
                    # Percentage: convert to a percentage token
                    token = TOK.Percent(token.txt + '%', token.val[0])
                    next_token = next(token_stream)

            # Coalesce ordinals (1. = first, 2. = second...) into a single token
            # !!! TBD: look at one more token to see whether the period might
            # mean the end of a sentence rather than an ordinal
            if next_token.kind == TOK.PUNCTUATION and next_token.txt == '.':
                if token.kind == TOK.NUMBER and not ('.' in token.txt or ',' in token.txt):
                    # Ordinal, i.e. whole number followed by period: convert to an ordinal token
                    token = TOK.Ordinal(token.txt, token.val[0])
                    next_token = next(token_stream)

            # Yield the current token and advance to the lookahead
            yield token
            token = next_token

    except StopIteration:
        # Final token (previous lookahead)
        if token:
            yield token


def parse_sentences(token_stream):
    """ Parse a stream of tokens looking for sentences, i.e. substreams within
        blocks delimited by periods. """

    in_sentence = False
    token = None
    try:

        # Maintain a one-token lookahead
        token = next(token_stream)
        while True:
            next_token = next(token_stream)

            if token.kind == TOK.P_BEGIN or token.kind == TOK.P_END:
                # Block start or end: finish the current sentence, if any
                if in_sentence:
                    yield TOK.End_Sentence()
                    in_sentence = False
            elif token.kind == TOK.PUNCTUATION and (token.txt == '.' or token.txt == '?'):
                # We may be finishing a sentence with not only a period but also
                # right parenthesis and quotation marks
                while next_token.kind == TOK.PUNCTUATION and next_token.txt in SENTENCE_FINISHERS:
                    yield token
                    token = next_token
                    next_token = next(token_stream)
                # The sentence is definitely finished now
                if in_sentence:
                    yield token
                    token = TOK.End_Sentence()
                    in_sentence = False
            elif not in_sentence:
                # This token starts a new sentence
                yield TOK.Begin_Sentence()
                in_sentence = True

            yield token
            token = next_token

    except StopIteration:
        pass

    # Final token (previous lookahead)
    if token:
        yield token

    # Done with the input stream
    # If still inside a sentence, finish it
    if in_sentence:
        yield TOK.End_Sentence()


class Bin_DB:

    """ Encapsulates the BÍN database of word forms """

    def __init__(self):
        """ Initialize DB connection instance """
        self._conn = None # Connection
        self._c = None # Cursor

    def open(self, host):
        """ Open and initialize a database connection """
        self._conn = psycopg2.connect(dbname="bin", user="reynir", password="reynir",
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

    @lru_cache(maxsize = 512)
    def meanings(self, w):
        """ Return a list of all possible grammatical meanings of the given word """
        assert self._c is not None
        m = None
        try:
            self._c.execute("select stofn, utg, ordfl, fl, ordmynd, beyging " +
                "from ord where ordmynd=(%s);", [ w ])
            # Map the returned data from fetchall() to a list of instances
            # of the BIN_Meaning namedtuple
            m = list(map(BIN_Meaning._make, self._c.fetchall()))
            if w in Meanings.DICT:
                # There is an additional word meaning in the Meanings dictionary,
                # coming from the settings file: append it
                m.append(BIN_Meaning._make(Meanings.DICT[w]))
        except psycopg2.DataError as e:
            print("Word {0} causing DB exception".format(w))
            m = None
        return m


def lookup_abbreviation(w):
    """ Lookup abbreviation from abbreviation list """
    # Remove brackets, if any, before lookup
    clean_w = w[1:-1] if w[0] == '[' else w
    # Return a single-entity list with one meaning
    m = Abbreviations.DICT.get(clean_w, None)
    return None if m is None else [ BIN_Meaning._make(m) ]


def lookup_word(db, w, at_sentence_start):
    """ Lookup simple or compound word in database and return its meanings """

    # Start with a simple lookup
    m = db.meanings(w)

    if at_sentence_start or not m:
        # No meanings found in database, or at sentence start
        # Try a lowercase version of the word, if different
        lower_w = w.lower()
        if lower_w != w:
            # Do another lookup, this time for lowercase only
            if not m:
                m = db.meanings(lower_w)
            else:
                m.extend(db.meanings(lower_w))

        if not m and (lower_w != w or w[0] == '['):
            # Still nothing: check abbreviations
            m = lookup_abbreviation(w)
            if not m and w[0] == '[':
                # Could be an abbreviation with periods at the start of a sentence:
                # Lookup a lowercase version
                m = lookup_abbreviation(lower_w)
            if m and w[0] == '[':
                # Remove brackets from known abbreviations
                w = w[1:-1]

        if not m:
            # Still nothing: check compound words
            cw = Wordbase.dawg().slice_compound_word(lower_w)
            if cw:
                # This looks like a compound word:
                # use the meaning of its last part
                prefix = "-".join(cw[0:-1])
                m = db.meanings(cw[-1])
                m = [ BIN_Meaning(prefix + "-" + r.stofn, r.utg, r.ordfl, r.fl,
                    prefix + "-" + r.ordmynd, r.beyging)
                    for r in m]
    
    return (w, m)

# Singleton instance of the BIN database used for lookups
bin_db = Bin_DB()

def annotate(token_stream):
    """ Look up word forms in the BIN word database """

    # Open the word database
    with closing(bin_db.open(Settings.DB_HOSTNAME)) as db:

        at_sentence_start = False

        # Consume the iterable source in wlist (which may be a generator)
        for t in token_stream:
            if t.kind != TOK.WORD:
                # Not a word: relay the token unchanged
                yield t
                if t.kind == TOK.S_BEGIN or (t.kind == TOK.PUNCTUATION and t.txt == ':'):
                    at_sentence_start = True
                elif t.kind != TOK.PUNCTUATION and t.kind != TOK.ORDINAL:
                    at_sentence_start = False
                continue
            if t.val != None:
                # Already have a meaning
                yield t
                at_sentence_start = False
                continue
            # Look up word in BIN database
            w, m = lookup_word(db, t.txt, at_sentence_start)
            # Yield a word tuple with meanings
            yield TOK.Word(w, m)
            # No longer at sentence start
            at_sentence_start = False

        # print(Bin_DB.meanings.cache_info())

# Recognize words that multiply numbers
MULTIPLIERS = {
    #"núll": 0,
    #"hálfur": 0.5,
    #"helmingur": 0.5,
    #"þriðjungur": 1.0 / 3,
    #"fjórðungur": 1.0 / 4,
    #"fimmtungur": 1.0 / 5,
    "einn": 1,
    "tveir": 2,
    "þrír": 3,
    "fjórir": 4,
    "fimm": 5,
    "sex": 6,
    "sjö": 7,
    "átta": 8,
    "níu": 9,
    "tíu": 10,
    "ellefu": 11,
    "tólf": 12,
    "þrettán": 13,
    "fjórtán": 14,
    "fimmtán": 15,
    "sextán": 16,
    "sautján": 17,
    "seytján": 17,
    "átján": 18,
    "nítján": 19,
    "tuttugu": 20,
    "þrjátíu": 30,
    "fjörutíu": 40,
    "fimmtíu": 50,
    "sextíu": 60,
    "sjötíu": 70,
    "áttatíu": 80,
    "níutíu": 90,
    #"par": 2,
    #"tugur": 10,
    #"tylft": 12,
    "hundrað": 100,
    #"þúsund": 1000, # !!! Bæði hk og kvk!
    "þús.": 1000,
    "milljón": 1e6,
    "milla": 1e6,
    "milljarður": 1e9,
    "miljarður": 1e9,
    "ma.": 1e9
}

# Recognize words for fractions
FRACTIONS = {
    "þriðji": 1.0 / 3,
    "fjórði": 1.0 / 4,
    "fimmti": 1.0 / 5,
    "sjötti": 1.0 / 6,
    "sjöundi": 1.0 / 7,
    "áttundi": 1.0 / 8,
    "níundi": 1.0 / 9,
    "tíundi": 1.0 / 10,
    "tuttugasti": 1.0 / 20,
    "hundraðasti": 1.0 / 100,
    "þúsundasti": 1.0 / 1000,
    "milljónasti": 1.0 / 1e6
}

# Recognize words for percentages
PERCENTAGES = {
    "prósent": 1,
    "prósenta": 1,
    "hundraðshluti": 1,
    "prósentustig": 1
}

# Recognize month names
MONTHS = {
    "janúar": 1,
    "febrúar": 2,
    "mars": 3,
    "apríl": 4,
    "maí": 5,
    "júní": 6,
    "júlí": 7,
    "ágúst": 8,
    "september": 9,
    "október": 10,
    "nóvember": 11,
    "desember": 12
}

# Recognize words for nationalities (used for currencies)
NATIONALITIES = {
    "danskur": "dk",
    "enskur": "uk",
    "breskur": "uk",
    "bandarískur": "us",
    "kanadískur": "ca",
    "svissneskur": "ch",
    "sænskur": "se",
    "norskur": "no",
    "japanskur": "jp",
    "íslenskur": "is",
    "pólskur": "po",
    "kínverskur": "cn",
    "ástralskur": "au"
}

# Recognize words for currencies
CURRENCIES = {
    "króna": "ISK",
    "ISK": "ISK",
    "[kr.]": "ISK",
    "kr": "ISK",
    "pund": "GBP",
    "sterlingspund": "GBP",
    "GBP": "GBP",
    "dollari": "USD",
    "dalur": "USD",
    "bandaríkjadalur": "USD",
    "USD": "USD",
    "franki": "CHF",
    "CHF": "CHF",
    "jen": "JPY",
    "yen": "JPY",
    "JPY": "JPY",
    "zloty": "PLN",
    "PLN": "PLN",
    "júan": "CNY",
    "yuan": "CNY",
    "CNY": "CNY",
    "evra": "EUR",
    "EUR": "EUR"
}

# Valid currency combinations
ISO_CURRENCIES = {
    ("dk", "ISK"): "DKK",
    ("is", "ISK"): "ISK",
    ("no", "ISK"): "NOK",
    ("se", "ISK"): "SEK",
    ("uk", "GBP"): "GBP",
    ("us", "USD"): "USD",
    ("ca", "USD"): "CAD",
    ("au", "USD"): "AUD",
    ("ch", "CHF"): "CHF",
    ("jp", "JPY"): "JPY",
    ("po", "PLN"): "PLN",
    ("cn", "CNY"): "CNY"
}

# Amount abbreviations including 'kr' for the ISK
AMOUNT_ABBREV = {
    "þús.kr.": 1e3,
    "m.kr.": 1e6,
    "mkr.": 1e6,
    "ma.kr.": 1e9
}

# Number words can be marked as subjects (any gender) or as numbers
NUMBER_CATEGORIES = frozenset(["töl", "to", "kk", "kvk", "hk", "lo"])


def match_stem_list(token, stems, filter_func=None):
    """ Find the stem of a word token in given dict, or return None if not found """
    if token.kind != TOK.WORD:
        return None
    if not token.val:
        # No meanings: this might be a foreign or unknown word
        # However, if it is still in the stems list we return True
        return stems.get(token.txt, None)
    # Go through the meanings with their stems
    for m in token.val:
        # If a filter function is given, pass candidates to it
        try:
            if m.stofn in stems and (filter_func is None or filter_func(m)):
                return stems[m.stofn]
        except Exception as e:
            print("Exception {0} in match_stem_list\nToken: {1}\nStems: {2}".format(e, token, stems))
            raise e
    return None


def case(bin_spec, default="nf"):
    """ Return the case specified in the bin_spec string """
    c = default
    if "NF" in bin_spec:
        c = "nf"
    elif "ÞF" in bin_spec:
        c = "þf"
    elif "ÞGF" in bin_spec:
        c = "þgf"
    elif "EF" in bin_spec:
        c = "ef"
    return c


def add_cases(cases, bin_spec, default="nf"):
    """ Add the case specified in the bin_spec string, if any, to the cases set """
    c = case(bin_spec, default)
    if c:
        cases.add(c)


def all_cases(token):
    """ Return a list of all cases that the token can be in """
    cases = set()
    if token.kind == TOK.WORD:
        # Roll through the potential meanings and extract the cases therefrom
        if token.val:
            for m in token.val:
                add_cases(cases, m.beyging, None)
    return list(cases)


_GENDER_SET = { "kk", "kvk", "hk" }
_GENDER_DICT = { "KK": "kk", "KVK": "kvk", "HK": "hk" }

def all_genders(token):
    """ Return a list of the possible genders of the word in the token, if any """
    if token.kind != TOK.WORD:
        return None
    g = set()
    if token.val:
        for m in token.val:

            def find_gender(m):
                if m.ordfl in _GENDER_SET:
                    return m.ordfl # Plain noun
                # Probably number word ('töl' or 'to'): look at its spec
                for k, v in _GENDER_DICT.items():
                    if k in m.beyging:
                        return v
                return None

            gn = find_gender(m)
            if gn is not None:
               g.add(gn)
    return list(g)


def parse_phrases_1(token_stream):
    """ Parse a stream of tokens looking for phrases and making substitutions.
        First pass
    """

    token = None
    try:

        # Maintain a one-token lookahead
        token = next(token_stream)
        while True:
            next_token = next(token_stream)

            # Logic for numbers and fractions that are partially or entirely
            # written out in words

            def number_filter(meaning):
                """ Filter to apply to candidate number words before
                    accepting them as such """
                # Check that the word is a number word, marked with ordfl='töl' or 'to',
                # or a subject ('nafnorð' of any gender) - or adjective ('lo') in the
                # case of fractions such as half ('hálfur')
                return meaning.ordfl in NUMBER_CATEGORIES

            def number(token):
                """ If the token denotes a number, return that number - or None """
                return match_stem_list(token, MULTIPLIERS, filter_func = number_filter)

            def fraction(token):
                """ If the token denotes a fraction, return a corresponding number - or None """
                return match_stem_list(token, FRACTIONS)

            if token.kind == TOK.WORD:
                num = number(token)
                if num is not None:
                    if num == 1:
                        # Only replace number 'one' if the next word is also
                        # a number word
                        if next_token.kind == TOK.WORD:
                            if number(next_token) is not None:
                                token = TOK.Number(token.txt, num, all_cases(token), all_genders(token))
                            else:
                                # Check for fractions ('einn þriðji')
                                frac = fraction(next_token)
                                if frac is not None:
                                    # We have a fraction: eat it and return it,
                                    # but use the case of the first word in the fraction
                                    token = TOK.Number(token.txt + " " + next_token.txt, frac,
                                        all_cases(token), all_genders(token))
                                    next_token = next(token_stream)
                    else:
                        # Replace number word with number token,
                        # preserving its case
                        token = TOK.Number(token.txt, num, all_cases(token), all_genders(token))

            # Check for [number] 'hundred|thousand|million|billion'
            while token.kind == TOK.NUMBER and next_token.kind == TOK.WORD:

                multiplier = number(next_token)
                if multiplier is not None:
                    # Retain the case of the last multiplier
                    token = TOK.Number(token.txt + " " + next_token.txt,
                        token.val[0] * multiplier,
                        all_cases(next_token), all_genders(next_token))
                    # Eat the multiplier token
                    next_token = next(token_stream)
                elif next_token.txt in AMOUNT_ABBREV:
                    # Abbreviations for ISK amounts
                    # For abbreviations, we do not know the case,
                    # but we try to retain the previous case information if any
                    token = TOK.Amount(token.txt + " " + next_token.txt, "ISK",
                        token.val[0] * AMOUNT_ABBREV[next_token.txt], # Number
                        token.val[1], token.val[2]) # Cases and gender
                    next_token = next(token_stream)
                else:
                    # Check for [number] 'percent'
                    percentage = match_stem_list(next_token, PERCENTAGES)
                    if percentage is not None:
                        token = TOK.Percent(token.txt + " " + next_token.txt, token.val[0])
                        # Eat the percentage token
                        next_token = next(token_stream)
                    else:
                        break

            # Check for [number | ordinal] [month name]
            if (token.kind == TOK.ORDINAL or token.kind == TOK.NUMBER) and next_token.kind == TOK.WORD:

                month = match_stem_list(next_token, MONTHS)
                if month is not None:
                    token = TOK.Date(token.txt + " " + next_token.txt, y = 0, m = month,
                        d = token.val if token.kind == TOK.ORDINAL else token.val[0])
                    # Eat the month name token
                    next_token = next(token_stream)

            # Check for [date] [year]
            if token.kind == TOK.DATE and next_token.kind == TOK.YEAR:

                if not token.val[0]:
                    # No year yet: add it
                    token = TOK.Date(token.txt + " " + next_token.txt,
                        y = next_token.val, m = token.val[1], d = token.val[2])
                    # Eat the year token
                    next_token = next(token_stream)

            # Check for [date] [time]
            if token.kind == TOK.DATE and next_token.kind == TOK.TIME:

                # Create a time stamp
                y, mo, d = token.val
                h, m, s = next_token.val
                token = TOK.Timestamp(token.txt + " " + next_token.txt,
                    y = y, mo = mo, d = d, h = h, m = m, s = s)
                # Eat the time token
                next_token = next(token_stream)

            # Check for currency name doublets, for example
            # 'danish krona' or 'british pound'
            if token.kind == TOK.WORD and next_token.kind == TOK.WORD:
                nat = match_stem_list(token, NATIONALITIES)
                if nat is not None:
                    cur = match_stem_list(next_token, CURRENCIES)
                    if cur is not None:
                        if (nat, cur) in ISO_CURRENCIES:
                            # Match: accumulate the possible cases
                            token = TOK.Currency(token.txt + " "  + next_token.txt,
                                ISO_CURRENCIES[(nat, cur)], all_cases(token),
                                all_genders(next_token))
                            next_token = next(token_stream)

            # Yield the current token and advance to the lookahead
            yield token
            token = next_token

    except StopIteration:
        pass

    # Final token (previous lookahead)
    if token:
        yield token


def parse_phrases_2(token_stream):
    """ Parse a stream of tokens looking for phrases and making substitutions.
        Second pass
    """

    token = None
    try:

        # Maintain a one-token lookahead
        token = next(token_stream)

        # Maintain a set of full person names encountered
        names = set()

        at_sentence_start = False

        while True:
            next_token = next(token_stream)
            # Make the lookahead checks we're interested in

            # Check for [number] [currency] and convert to [amount]
            if token.kind == TOK.NUMBER and (next_token.kind == TOK.WORD or
                next_token.kind == TOK.CURRENCY):

                # Preserve the case of the currency name, if available
                # (krónur, krónum, króna)
                if next_token.kind == TOK.WORD:
                    # Try to find a currency name
                    cur = match_stem_list(next_token, CURRENCIES)
                else:
                    # Already have an ISO identifier for a currency
                    cur = next_token.val[0]

                if cur is not None:
                    # Create an amount
                    # Use the case and gender information from the number, if any
                    token = TOK.Amount(token.txt + " " + next_token.txt,
                        cur, token.val[0], token.val[1], token.val[2])
                    # Eat the currency token
                    next_token = next(token_stream)

            # Logic for human names

            def stems(token, category):
                """ If the token denotes a given name, return its possible
                    interpretations, as a list of PersonName tuples (name, case, gender) """
                if token.kind != TOK.WORD or not token.val:
                    return None
                # Look through the token meanings
                result = []
                for m in token.val:
                    # print("In_category checking {0}".format(m))
                    if m.fl == category:
                        # Note the stem ('stofn') and the gender from the word type ('ordfl')
                        result.append(PersonName(name = m.stofn, gender = m.ordfl, case = case(m.beyging)))
                return result if result else None

            def has_other_meaning(token, category):
                """ Return True if the token can denote something besides a given name """
                if token.kind != TOK.WORD or not token.val:
                    return True
                # Look through the token meanings
                for m in token.val:
                    if m.fl != category:
                        # Here is a different meaning, not a given name: return True
                        return True
                return False

            # Check for human names
            def given_names(token):
                """ Check for Icelandic person name (category 'ism') """
                if token.kind != TOK.WORD or not token.txt[0].isupper():
                    # Must be a word starting with an uppercase character
                    return None
                return stems(token, "ism")

            # Check for surnames
            def surnames(token):
                """ Check for Icelandic patronym (category 'föð) """
                if token.kind != TOK.WORD or not token.txt[0].isupper():
                    # Must be a word starting with an uppercase character
                    return None
                return stems(token, "föð")

            def given_names_or_middle_abbrev(token):
                """ Check for given name or middle abbreviation """
                gn = given_names(token)
                if gn is not None:
                    return gn
                if token.kind != TOK.WORD:
                    return None
                w = token.txt
                if w.startswith('['):
                    # Abbreviation: Cut off the brackets & trailing period
                    w = w[1:-2]
                if len(w) > 2 or not w[0].isupper():
                    return None
                # One or two letters, capitalized: accept as middle name abbrev,
                # all genders and cases possible
                return [PersonName(name = w, gender = None, case = None)]

            def compatible(p, np):
                """ Return True if the next PersonName (np) is compatible with the one we have (p) """
                if np.gender and (np.gender != p.gender):
                    return False
                if np.case and (np.case != p.case):
                    return False
                return True

            gn = given_names(token)

            if gn:
                # Found at least one given name: look for a sequence of given names
                # having compatible genders and cases
                w = token.txt
                patronym = False
                while True:
                    ngn = given_names_or_middle_abbrev(next_token)
                    if not ngn:
                        break
                    # Look through the stuff we got and see what is compatible
                    r = []
                    for p in gn:
                        for np in ngn:
                            if compatible(p, np):
                                # Compatible: add to result
                                r.append(PersonName(name = p.name + " " + np.name, gender = p.gender, case = p.case))
                    if not r:
                        # This next name is not compatible with what we already
                        # have: break
                        break
                    # Success: switch to new given name list
                    gn = r
                    w += " " + (ngn[0].name if next_token.txt[0] == '[' else next_token.txt)
                    next_token = next(token_stream)

                # Check whether the sequence of given names is followed
                # by a surname (patronym) of the same gender
                sn = surnames(next_token)
                if sn:
                    r = []
                    # Found surname: append it to the accumulated name, if compatible
                    for p in gn:
                        for np in sn:
                            if compatible(p, np):
                                r.append(PersonName(name = p.name + " " + np.name, gender = p.gender, case = p.case))
                    if r:
                        # Compatible: include it and advance to the next token
                        gn = r
                        w += " " + next_token.txt
                        patronym = True
                        next_token = next(token_stream)

                # Must have at least one possible name
                assert len(gn) >= 1

                found_name = False
                # If we have a full name with patronym, store it
                if patronym:
                    names |= set(gn)
                else:
                    # Look through earlier full names and see whether this one matches
                    for ix, p in enumerate(gn):
                        gnames = p.name.split(' ') # Given names
                        for lp in names:
                            match = (not p.gender) or (p.gender == lp.gender)
                            if match:
                                # The gender matches
                                lnames = set(lp.name.split(' ')[0:-1]) # Leave the patronym off
                                for n in gnames:
                                    if n not in lnames:
                                        # We have a given name that does not match the person
                                        match = False
                                        break
                            if match:
                                # All given names match: assign the previously seen full name
                                gn[ix] = PersonName(name = lp.name, gender = lp.gender, case = p.case)
                                found_name = True
                                break

                # If this is not a "strong" name, backtrack from recognizing it.
                # A "weak" name is (1) at the start of a sentence; (2) only one
                # word; (3) that word has a meaning that is not a name;
                # (4) the name has not been seen in a full form before.

                #if len(gnames) == 1:
                #    print("Checking name '{4}': at_sentence_start {0}, patronym {1}, found_name {2}, not_in_category {3}"
                #        .format(at_sentence_start, patronym, found_name, not_in_category(token, "ism"), w))

                weak = at_sentence_start and (' ' not in w) and not patronym and \
                    not found_name and has_other_meaning(token, "ism")

                if not weak:
                    # Return a person token with the accumulated name
                    # and the intersected set of possible cases
                    token = TOK.Person(w, gn)

            # Yield the current token and advance to the lookahead
            yield token

            if token.kind == TOK.S_BEGIN or (token.kind == TOK.PUNCTUATION and token.txt == ':'):
                at_sentence_start = True
            elif token.kind != TOK.PUNCTUATION and token.kind != TOK.ORDINAL:
                at_sentence_start = False
            token = next_token

    except StopIteration:
        pass

    # Final token (previous lookahead)
    if token:
        yield token


def parse_static_phrases(token_stream):
    """ Parse a stream of tokens looking for static multiword phrases
        (i.e. phrases that are not affected by inflection).
        The algorithm implements N-token lookahead where N is the
        length of the longest phrase.
    """

    tq = [] # Token queue
    state = { } # Phrases we're considering
    pdict = StaticPhrases.DICT # The phrase dictionary

    try:

        while True:

            token = next(token_stream)
            tq.append(token) # Add to lookahead token queue

            if token.kind != TOK.WORD:
                # Not a word: no match; discard state
                for t in tq: yield t
                tq = []
                state = { }
                continue

            # Look for matches in the current state and
            # build a new state
            newstate = { }
            w = token.txt.lower()

            def add_to_state(state, sl, ix):
                """ Add the list of subsequent words to the new parser state """
                w = sl[0]
                if w in state:
                    state[w].append((sl[1:], ix))
                else:
                    state[w] = [ (sl[1:], ix) ]

            if w in state:
                # This matches an expected token:
                # go through potential continuations
                for sl, ix in state[w]:
                    if not sl:
                        # No subsequent word: this is a complete match
                        # Reconstruct original text behind phrase
                        w = " ".join([t.txt for t in tq])
                        # Add the entire phrase as one 'word' to the token queue
                        tq = [ TOK.Word(w, [BIN_Meaning._make(r) for r in StaticPhrases.get_meaning(ix)]) ]
                        # Discard the state and start afresh
                        newstate = { }
                        # Note that it is possible to match even longer phrases
                        # by including a starting phrase in its entirety in
                        # the static phrase dictionary
                        break
                    add_to_state(newstate, sl, ix)

            # Add all possible new states for phrases that could be starting
            if w in pdict:
                # This word potentially starts a phrase
                for sl, ix in pdict[w]:
                    if not sl:
                        # Simple replace of a single word
                        w = " ".join([t.txt for t in tq])
                        tq = [ TOK.Word(w, [BIN_Meaning._make(r) for r in StaticPhrases.get_meaning(ix)]) ]
                        newstate = { }
                        break
                    add_to_state(newstate, sl, ix)

            # Transition to the new state
            state = newstate
            if not state:
                # No possible phrases: yield the token queue before continuing
                for t in tq: yield t
                tq = []

    except StopIteration:
        # Token stream is exhausted
        pass

    # Yield any tokens remaining in queue
    for t in tq: yield t


def disambiguate_phrases(token_stream):
    """ Parse a stream of tokens looking for common ambiguous multiword phrases
        (i.e. phrases that have a well known very likely interpretation but
        other extremely uncommon ones are also grammatically correct).
        The algorithm implements N-token lookahead where N is the
        length of the longest phrase.
    """

    tq = [] # Token queue
    state = { } # Phrases we're considering
    pdict = AmbigPhrases.DICT # The phrase dictionary

    try:

        while True:

            token = next(token_stream)
            tq.append(token) # Add to lookahead token queue

            if token.kind != TOK.WORD:
                # Not a word: no match; discard state
                for t in tq: yield t
                tq = []
                state = { }
                continue

            # Look for matches in the current state and
            # build a new state
            newstate = { }
            w = token.txt.lower()

            def add_to_state(state, sl, ix):
                """ Add the list of subsequent words to the new parser state """
                w = sl[0]
                if w in state:
                    state[w].append((sl[1:], ix))
                else:
                    state[w] = [ (sl[1:], ix) ]

            if w in state:
                # This matches an expected token:
                # go through potential continuations
                for sl, ix in state[w]:
                    if not sl:
                        # No subsequent word: this is a complete match
                        # Discard meanings of words in the token queue that are not
                        # compatible with the category list specified
                        for t, cat in zip(tq, AmbigPhrases.get_cats(ix)):
                            assert t.kind == TOK.WORD
                            # Yield a new token with fewer meanings for each original token in the queue
                            yield Tok(t.kind, t.txt, [m for m in t.val if m.ordfl == cat])
                        tq = []

                        # Discard the state and start afresh
                        newstate = { }
                        # Note that it is possible to match even longer phrases
                        # by including a starting phrase in its entirety in
                        # the static phrase dictionary
                        break
                    add_to_state(newstate, sl, ix)

            # Add all possible new states for phrases that could be starting
            if w in pdict:
                # This word potentially starts a phrase
                for sl, ix in pdict[w]:
                    assert sl
                    add_to_state(newstate, sl, ix)

            # Transition to the new state
            state = newstate
            if not state:
                # No possible phrases: yield the token queue before continuing
                for t in tq: yield t
                tq = []

    except StopIteration:
        # Token stream is exhausted
        pass

    # Yield any tokens remaining in queue
    for t in tq: yield t


def tokenize(text):
    """ Tokenize text in several phases, returning a generator (iterable sequence) of tokens
        that processes tokens on-demand """

    # Thank you Python for enabling this programming pattern ;-)

    token_stream = parse_tokens(text)

    token_stream = parse_particles(token_stream)

    token_stream = parse_sentences(token_stream)

    token_stream = parse_static_phrases(token_stream) # Static multiword phrases

    token_stream = annotate(token_stream) # Lookup meanings from dictionary

    token_stream = parse_phrases_1(token_stream) # First phrase pass

    token_stream = parse_phrases_2(token_stream) # Second phrase pass

    token_stream = disambiguate_phrases(token_stream) # Eliminate very uncommon meanings

    return token_stream

