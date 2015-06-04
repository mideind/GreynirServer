"""
    Reynir: Natural language processing for Icelandic

    Tokenizer module

    Author: Vilhjalmur Thorsteinsson

    This software is at a very early development stage.
    While that is the case, it is:
    Copyright (c) 2015 Vilhjalmur Thorsteinsson
    All rights reserved

    This module is written in Python 3 for Python 3.4

    The function parse_text() consumes a text string and
    yields a generator of tokens. Each token is a tuple,
    typically having the form (type, word, meaning),
    where type is one of the 

"""

from contextlib import closing
from functools import lru_cache

import re
import codecs
import datetime

import psycopg2
import psycopg2.extensions

# Make Psycopg2 and PostgreSQL happy with UTF-8

psycopg2.extensions.register_type(psycopg2.extensions.UNICODE)
psycopg2.extensions.register_type(psycopg2.extensions.UNICODEARRAY)

from settings import Settings, StaticPhrases, Abbreviations
from dawgdictionary import Wordbase


# Recognized punctuation

LEFT_PUNCTUATION = "([„«#$€<"
RIGHT_PUNCTUATION = ".,:;)]!%?“»”’…°>"
CENTER_PUNCTUATION = "\"*&+=@©|—–"
NONE_PUNCTUATION = "/-\\'~"
PUNCTUATION = LEFT_PUNCTUATION + CENTER_PUNCTUATION + RIGHT_PUNCTUATION + NONE_PUNCTUATION

# Punctuation symbols that may occur at the end of a sentence, after the period
SENTENCE_FINISHERS = ")]“»”’"

# Single-word abbreviations (i.e. those that don't contain an embedded period)
ABBREV = frozenset([
    "bls", "skv", "nk", "sbr", "ca", "ath", "e", "kl", "kr",
    "þús", "ma", "sl", "gr", "nr", "pr", "fv", "mkr", "ehf",
    # Note that 'Ð' is excluded from single-letter abbreviations
    "A", "Á", "B", "C", "D", "E", "É", "F", "G", "H", "I", "Í", "J", "K",
    "L", "M", "N", "O", "Ó", "P", "Q", "R", "S", "T", "U", "V", "W",
    "X", "Y", "Z", "Þ", "Æ", "Ö", "Th", "St", "Fr"
])

CLOCK_ABBREV = "kl"

# Punctuation types: left, center or right of word

TP_LEFT = 1
TP_CENTER = 2
TP_RIGHT = 3
TP_NONE = 4 # No whitespace

# Numeric digits

DIGITS = "0123456789"

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
        return (TOK.PUNCTUATION, w, tp)

    def Time(w, h, m, s):
        return (TOK.TIME, w, (h, m, s))

    def Date(w, y, m, d):
        return (TOK.DATE, w, (y, m, d))

    def Timestamp(w, y, mo, d, h, m, s):
        return (TOK.TIMESTAMP, w, (y, mo, d, h, m, s))

    def Year(w, n):
        return (TOK.YEAR, w, n)

    def Telno(w):
        return (TOK.TELNO, w)

    def Number(w, n):
        return (TOK.NUMBER, w, n)

    def Currency(w, iso):
        return (TOK.CURRENCY, w, iso)

    def Amount(w, iso, n):
        return (TOK.AMOUNT, w, (iso, n))

    def Percent(w, n):
        return (TOK.PERCENT, w, n)

    def Ordinal(w, n):
        return (TOK.ORDINAL, w, n)

    def Url(w):
        return (TOK.URL, w)

    def Word(w, m):
        return (TOK.WORD, w, m)

    def Unknown(w):
        return (TOK.UNKNOWN, w)

    def Person(w, name, gender):
        return (TOK.PERSON, w, (name, gender))

    def Begin_Paragraph():
        return (TOK.P_BEGIN, None)

    def End_Paragraph():
        return (TOK.P_END, None)

    def Begin_Sentence():
        return (TOK.S_BEGIN, None)

    def End_Sentence():
        return (TOK.S_END, None)


def parse_digits(w):
    """ Parse a raw token starting with a digit """

    if re.match(r'\d{1,2}:\d\d$', w):
        # Looks like a 24-hour clock
        p = w.split(':')
        h = int(p[0])
        m = int(p[1])
        return TOK.Time(w, h, m, 0), len(w)
    if re.match(r'\d{1,2}:\d\d:\d\d$', w):
        # Looks like a 24-hour clock
        p = w.split(':')
        h = int(p[0])
        m = int(p[1])
        s = int(p[2])
        return TOK.Time(w, h, m, s), len(w)
    if re.match(r'\d{1,2}/\d{1,2}/\d{2,4}$', w) or re.match(r'\d{1,2}\.\d{1,2}\.\d{2,4}$', w):
        # Looks like a date
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
        return TOK.Date(w, y, m, d), len(w)
    if re.match(r'\d{1,2}/\d{1,2}$', w) or re.match(r'\d{1,2}\.\d{1,2}$', w):
        # Looks like a date
        if '/' in w:
            p = w.split('/')
        else:
            p = w.split('.')
        m = int(p[1])
        d = int(p[0])
        if m > 12 and d <= 12:
            # Probably wrong way around
            m, d = d, m
        return TOK.Date(w, 0, m, d), len(w)
    m = re.match(r'\d\d\d\d$', w) or re.match(r'\d\d\d\d[^\d]', w)
    if m:
        n = int(w[0:4])
        if 1776 <= n <= 2100:
            # Looks like a year
            return TOK.Year(w[0:4], n), 4
    if re.match(r'\d\d\d-\d\d\d\d$', w):
        # Looks like a telephone number
        return TOK.Telno(w), len(w)
    m = re.match(r'\d+(\.\d\d\d)*,\d+', w)
    if m:
        # Real number formatted with decimal comma and possibly thousands separator
        w = w[0:m.end()]
        n = re.sub(r'\.', '', w) # Eliminate thousands separators
        n = re.sub(r',', '.', n) # Convert decimal comma to point
        return TOK.Number(w, float(n)), m.end()
    m = re.match(r'\d+(\.\d\d\d)*', w)
    if m:
        # Integer, possibly with a '.' thousands separator
        w = w[0:m.end()]
        n = re.sub(r'\.', '', w) # Eliminate thousands separators
        return TOK.Number(w, int(n)), m.end()
    m = re.match(r'\d+(,\d\d\d)*\.\d+', w)
    if m:
        # Real number, possibly with a thousands separator and decimal comma/point
        w = w[0:m.end()]
        n = re.sub(r',', '', w) # Eliminate thousands separators
        return TOK.Number(w, float(n)), m.end()
    m = re.match(r'\d+(,\d\d\d)*', w)
    if m:
        # Integer, possibly with a ',' thousands separator
        w = w[0:m.end()]
        n = re.sub(r',', '', w) # Eliminate thousands separators
        return TOK.Number(w, int(n)), m.end()
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
            if token[0] == TOK.PUNCTUATION and token[1] == '$' and \
                next_token[0] == TOK.NUMBER:

                token = TOK.Amount(token[1] + next_token[1], "USD", next_token[2])
                next_token = next(token_stream)

            # Check for €[number]
            if token[0] == TOK.PUNCTUATION and token[1] == '€' and \
                next_token[0] == TOK.NUMBER:

                token = TOK.Amount(token[1] + next_token[1], "EUR", next_token[2])
                next_token = next(token_stream)

            # Coalesce abbreviations ending with a period into a single
            # abbreviation token
            if next_token[0] == TOK.PUNCTUATION and next_token[1] == '.':
                if token[0] == TOK.WORD and ('.' in token[1] or token[1].lower() in ABBREV or token[1] in ABBREV):
                    # Abbreviation: make a special token for it
                    # and advance the input stream
                    clock = token[1].lower() == CLOCK_ABBREV
                    token = TOK.Word("[" + token[1] + ".]", None)
                    next_token = next(token_stream)

            # Coalesce [kl.] + time or number into a time
            if clock and (next_token[0] == TOK.TIME or next_token[0] == TOK.NUMBER):
                if next_token[0] == TOK.NUMBER:
                    token = TOK.Time(CLOCK_ABBREV + " " + next_token[1], next_token[2], 0, 0)
                else:
                    token = TOK.Time(CLOCK_ABBREV + " " + next_token[1],
                        next_token[2][0], next_token[2][1], next_token[2][2])
                next_token = next(token_stream)

            # Coalesce percentages into a single token
            if next_token[0] == TOK.PUNCTUATION and next_token[1] == '%':
                if token[0] == TOK.NUMBER:
                    # Percentage: convert to a percentage token
                    token = TOK.Percent(token[1] + '%', token[2])
                    next_token = next(token_stream)

            # Coalesce ordinals (1. = first, 2. = second...) into a single token
            # !!! TBD: look at one more token to see whether the period might
            # mean the end of a sentence rather than an ordinal
            if next_token[0] == TOK.PUNCTUATION and next_token[1] == '.':
                if token[0] == TOK.NUMBER and not ('.' in token[1] or ',' in token[1]):
                    # Ordinal, i.e. whole number followed by period: convert to an ordinal token
                    token = TOK.Ordinal(token[1], token[2])
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

            if token[0] == TOK.P_BEGIN or token[0] == TOK.P_END:
                # Block start or end: finish the current sentence, if any
                if in_sentence:
                    yield TOK.End_Sentence()
                    in_sentence = False
            elif token[0] == TOK.PUNCTUATION and (token[1] == '.' or token[1] == '?'):
                # We may be finishing a sentence with not only a period but also
                # right parenthesis and quotation marks
                while next_token[0] == TOK.PUNCTUATION and next_token[1] in SENTENCE_FINISHERS:
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

    """ Encapsulates the database of word forms """

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
            self._c.execute("select * from ord where ordmynd=(%s);", [ w ])
            m = self._c.fetchall()
        except psycopg2.DataError as e:
            print(" Word {0} causing DB exception".format(w).encode('utf-8'))
            # Fall through with m set to None
        return m


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
                m = [ (prefix + "-" + stem, ix, wtype, wcat, prefix + "-" + wform, gform)
                    for stem, ix, wtype, wcat, wform, gform in m]
    return m


def lookup_abbreviation(w):
    """ Lookup abbreviation from abbreviation list """
    return [ Abbreviations.DICT[w] ] if w in Abbreviations.DICT else None


def annotate(token_stream):
    """ Look up word forms in the BIN word database """

    # Open the word database
    with closing(Bin_DB().open(Settings.DB_HOSTNAME)) as db:

        at_sentence_start = False

        # Consume the iterable source in wlist (which may be a generator)
        for t in token_stream:
            if t[0] != TOK.WORD:
                # Not a word: relay the token unchanged
                yield t
                if t[0] == TOK.S_BEGIN or (t[0] == TOK.PUNCTUATION and t[1] == ':'):
                    at_sentence_start = True
                elif t[0] != TOK.PUNCTUATION and t[0] != TOK.ORDINAL:
                    at_sentence_start = False
                continue
            if t[2] != None:
                # Already have a meaning
                yield t
                at_sentence_start = False
                continue
            # Look up word in BIN database
            w = t[1]
            m = lookup_word(db, w, at_sentence_start)
            # Yield a word tuple with meanings
            yield TOK.Word(w, m)
            # No longer at sentence start
            at_sentence_start = False

        # print(Bin_DB.meanings.cache_info())

# Recognize words that multiply numbers
MULTIPLIERS = {
    "núll": 0,
    "hálfur": 0.5,
    "helmingur": 0.5,
    "þriðjungur": 1.0 / 3,
    "fjórðungur": 1.0 / 4,
    "fimmtungur": 1.0 / 5,
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
    "par": 2,
    "tugur": 10,
    "tylft": 12,
    "hundrað": 100,
    "þúsund": 1000,
    "[þús.]": 1000,
    "milljón": 1e6,
    "milla": 1e6,
    "milljarður": 1e9,
    "miljarður": 1e9,
    "[ma.]": 1e9
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
    "[þús.kr.]": 1e3,
    "þús.kr.": 1e3,
    "[m.kr.]": 1e6,
    "m.kr.": 1e6,
    "[mkr.]": 1e6,
    "mkr.": 1e6,
    "[ma.kr.]": 1e9,
    "ma.kr.": 1e9
}

# Number words can be marked as subjects (any gender) or as numbers
NUMBER_CATEGORIES = frozenset(["töl", "to", "kk", "kvk", "hk", "lo"])


def match_stem_list(token, stems, filter_func=None):
    """ Find the stem of a word token in given dict, or return None if not found """
    if token[0] != TOK.WORD:
        return None
    if not token[2]:
        # No meanings: this might be a foreign or unknown word
        # However, if it is still in the stems list we return True
        return stems.get(token[1], None)
    # Go through the meanings with their stems
    for m in token[2]:
        # If a filter function is given, pass candidates to it
        if m[0] in stems and (filter_func is None or filter_func(m)):
            return stems[m[0]]
    return None


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
                return meaning[2] in NUMBER_CATEGORIES

            def number(token):
                """ If the token denotes a number, return that number - or None """
                return match_stem_list(token, MULTIPLIERS, filter_func = number_filter)

            def fraction(token):
                """ If the token denotes a fraction, return a corresponding number - or None """
                return match_stem_list(token, FRACTIONS)

            if token[0] == TOK.WORD:
                num = number(token)
                if num is not None:
                    if num == 1:
                        # Only replace number 'one' if the next word is also
                        # a number word
                        if next_token[0] == TOK.WORD:
                            if number(next_token) is not None:
                                token = TOK.Number(token[1], num)
                            else:
                                # Check for fractions ('einn þriðji')
                                frac = fraction(next_token)
                                if frac is not None:
                                    # We have a fraction: eat it and return it
                                    token = TOK.Number(token[1] + " " + next_token[1], frac)
                                    next_token = next(token_stream)
                    else:
                        # Replace number word with number token
                        token = TOK.Number(token[1], num)

            # Check for [number] 'hundred|thousand|million|billion'
            while token[0] == TOK.NUMBER and next_token[0] == TOK.WORD:

                multiplier = number(next_token)
                if multiplier is not None:
                    token = TOK.Number(token[1] + " " + next_token[1], token[2] * multiplier)
                    # Eat the multiplier token
                    next_token = next(token_stream)
                elif next_token[1] in AMOUNT_ABBREV:
                    # Abbreviations for ISK amounts
                    token = TOK.Amount(token[1] + " " + next_token[1], "ISK",
                        token[2] * AMOUNT_ABBREV[next_token[1]])
                    next_token = next(token_stream)
                else:
                    # Check for [number] 'percent'
                    percentage = match_stem_list(next_token, PERCENTAGES)
                    if percentage is not None:
                        token = TOK.Percent(token[1] + " " + next_token[1], token[2])
                        # Eat the percentage token
                        next_token = next(token_stream)
                    else:
                        break

            # Check for [number | ordinal] [month name]
            if (token[0] == TOK.ORDINAL or token[0] == TOK.NUMBER) and next_token[0] == TOK.WORD:

                month = match_stem_list(next_token, MONTHS)
                if month is not None:
                    token = TOK.Date(token[1] + " " + next_token[1], y=0, m=month, d=token[2])
                    # Eat the month name token
                    next_token = next(token_stream)

            # Check for [date] [year]
            if token[0] == TOK.DATE and next_token[0] == TOK.YEAR:

                if not token[2][0]:
                    # No year yet: add it
                    token = TOK.Date(token[1] + " " + next_token[1],
                        y=next_token[2], m=token[2][1], d=token[2][2])
                    # Eat the year token
                    next_token = next(token_stream)

            # Check for [date] [time]
            if token[0] == TOK.DATE and next_token[0] == TOK.TIME:

                # Create a time stamp
                y, mo, d = token[2]
                h, m, s = next_token[2]
                token = TOK.Timestamp(token[1] + " " + next_token[1],
                    y=y, mo=mo, d=d, h=h, m=m, s=s)
                # Eat the time token
                next_token = next(token_stream)

            # Check for currency name doublets, for example
            # 'danish krona' or 'british pound'
            if token[0] == TOK.WORD and next_token[0] == TOK.WORD:
                nat = match_stem_list(token, NATIONALITIES)
                if nat is not None:
                    cur = match_stem_list(next_token, CURRENCIES)
                    if cur is not None:
                        if (nat, cur) in ISO_CURRENCIES:
                            token = TOK.Currency(token[1] + " "  + next_token[1],
                                ISO_CURRENCIES[(nat, cur)])
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

        # Maintain a dict of full person names and genders encountered
        names = dict()

        # Maintain a dict of the last full person name of each gender encountered
        genders = dict()

        at_sentence_start = False

        while True:
            next_token = next(token_stream)
            # Make the lookahead checks we're interested in

            # Check for [number] [currency] and convert to [amount]
            if token[0] == TOK.NUMBER and (next_token[0] == TOK.WORD or
                next_token[0] == TOK.CURRENCY):

                if next_token[0] == TOK.WORD:
                    # Try to find a currency name
                    cur = match_stem_list(next_token, CURRENCIES)
                else:
                    # Already have an ISO identifier for a currency
                    cur = next_token[2]

                if cur is not None:
                    # Create an amount
                    token = TOK.Amount(token[1] + " " + next_token[1], cur, token[2])
                    # Eat the currency token
                    next_token = next(token_stream)

            # Logic for human names

            def in_category(token, category):
                """ If the token denotes a given name, return its stem and gender """
                if token[0] != TOK.WORD or not token[2]:
                    return None
                # Look through the token meanings
                gender = None
                stem = None
                for m in token[2]:
                    # print("In_category checking {0}".format(m))
                    if m[3] == category:
                        # Note the stem ('stofn') and the word type ('ordfl')
                        stem = m[0]
                        if gender is None:
                            gender = m[2]
                        elif gender != m[2]:
                            gender = "" # Multiple genders
                return None if stem is None else (stem, gender)

            def not_in_category(token, category):
                """ Return True if the token can denote something besides a given name """
                if token[0] != TOK.WORD or not token[2]:
                    return True
                # Look through the token meanings
                for m in token[2]:
                    if m[3] != category:
                        # Here is a different meaning, not a given name: return True
                        return True
                return False

            # Check for human names
            def given_name(token):
                """ Check for Icelandic person name (category 'ism') """
                if token[0] != TOK.WORD or not token[1][0].isupper():
                    # Must be a word starting with an uppercase character
                    return None
                return in_category(token, "ism")

            def given_name_or_middle_abbrev(token):
                """ Check for given name or middle abbreviation """
                gn = given_name(token)
                if gn is not None:
                    return gn
                if token[0] != TOK.WORD:
                    return None
                w = token[1]
                if w.startswith('['):
                    # Abbreviation: Cut off the brackets & trailing period
                    w = w[1:-2]
                if len(w) > 2 or not w[0].isupper():
                    return None
                # One or two letters, capitalized: accept as middle name abbrev
                # (no gender)
                return (w, "")

            # Check for surnames
            def surname(token):
                """ Check for Icelandic patronym (category 'föð) """
                if token[0] != TOK.WORD or not token[1][0].isupper():
                    # Must be a word starting with an uppercase character
                    return None
                return in_category(token, "föð")

            gn = given_name(token)
            if gn is not None:
                # Found a given name: look for a sequence of given names
                # of the same gender
                w = token[1]
                name, gender = gn
                patronym = False
                gnames = [ name ] # Accumulate list of given names
                while True:
                    gn = given_name_or_middle_abbrev(next_token)
                    if gn is None:
                        break
                    if gender and gn[1] and gn[1] != gender:
                        # We already had a definitive gender and this name
                        # doesn't match it: break
                        break
                    if gn[1] and not gender:
                        gender = gn[1]
                    # Found a directly following given name of the same gender:
                    # append it to the accumulated name and continue
                    w += " " + (gn[0] if next_token[1][0] == '[' else next_token[1])
                    name += " " + gn[0]
                    gnames.append(gn[0])
                    next_token = next(token_stream)
                # Check whether the sequence of given names is followed
                # by a surname (patronym) of the same gender
                sn = surname(next_token)
                if sn is not None and (not gender or sn[1] == gender):
                    # Found surname: append it to the accumulated name
                    name += " " + sn[0]
                    w += " " + next_token[1]
                    if not gender:
                        # We did not learn the gender from the first names:
                        # use the surname gender if available
                        gender = sn[1]
                    patronym = True
                    next_token = next(token_stream)

                found_name = None
                # If we have a full name with patronym, store it
                if patronym:
                    names[name] = (gender, gnames)
                    genders[gender] = name
                else:
                    # Look through earlier full names and see whether this one matches
                    for key, val in names.items():
                        ge, gn_list = val
                        match = gender and (ge == gender)
                        if match:
                            for gn in gnames:
                                if gn not in gn_list:
                                    # We have a given name that does not match the person
                                    match = False
                                    break
                        if match:
                            # !!! TODO: Handle case where more than one name matches
                            found_name = key
                            if not gender:
                                gender = ge
                    if found_name is not None:
                        name = found_name
                        # Reset gender reference to this newly found name
                        genders[gender] = name

                # If this is not a "strong" name, backtrack from recognizing it.
                # A "weak" name is (1) at the start of a sentence; (2) only one
                # word; (3) that word has a meaning that is not a name;
                # (4) the name has not been seen in a full form before.

                #if len(gnames) == 1:
                #    print("Checking name '{4}': at_sentence_start {0}, patronym {1}, found_name {2}, not_in_category {3}"
                #        .format(at_sentence_start, patronym, found_name, not_in_category(token, "ism"), w))

                weak = at_sentence_start and len(gnames) == 1 and not patronym and \
                    found_name is None and not_in_category(token, "ism")

                if not weak:
                    # Return a person token with the accumulated name
                    token = TOK.Person(w, name, gender)

            # Yield the current token and advance to the lookahead
            yield token

            if token[0] == TOK.S_BEGIN or (token[0] == TOK.PUNCTUATION and token[1] == ':'):
                at_sentence_start = True
            elif token[0] != TOK.PUNCTUATION and token[0] != TOK.ORDINAL:
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

            if token[0] != TOK.WORD:
                # Not a word: no match; discard state
                for t in tq: yield t
                tq = []
                state = { }
                continue

            # Look for matches in the current state and
            # build a new state
            newstate = { }
            w = token[1].lower()

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
                        w = " ".join([t[1] for t in tq])
                        # Add the entire phrase as one 'word' to the token queue
                        tq = [ TOK.Word(w, StaticPhrases.get_meaning(ix)) ]
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
                        w = " ".join([t[1] for t in tq])
                        tq = [ TOK.Word(w, StaticPhrases.get_meaning(ix)) ]
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


def parse_text(text):
    """ Parse text into a generator (iterable sequence) of tokens """

    token_stream = parse_tokens(text)

    token_stream = parse_particles(token_stream)

    token_stream = parse_sentences(token_stream)

    token_stream = parse_static_phrases(token_stream) # Static multiword phrases

    token_stream = annotate(token_stream) # Lookup meanings from dictionary

    token_stream = parse_phrases_1(token_stream) # First phrase pass

    token_stream = parse_phrases_2(token_stream) # Second phrase pass

    return token_stream


def dump_tokens_to_file(fname, tokens):
    """ Dump a token list to a text file """

    with codecs.open(fname, "w", "utf-8") as out:

        for token in tokens:
            t = token[0]
            w = token[1]
            if t == TOK.P_BEGIN or t == TOK.P_END:
                print("[{0}]".format(TOK.descr[t]), file=out)
            elif t == TOK.S_BEGIN or t == TOK.S_END:
                print("[{0}]".format(TOK.descr[t]), file=out)
            else:
                print("[{0}] '{1}'".format(TOK.descr[t], w or ""), file=out)
    #            if forms:
    #                for f in forms:
    #                    stofn = "" + f[0]
    #                    ordfl = "" + f[2]
    #                    beyging = "" + f[5]
    #                    print("   {0} '{1}' {2}".format(ordfl, stofn, beyging).encode("utf-8"))

