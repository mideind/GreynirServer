"""
    Reynir: Natural language processing for Icelandic

    BIN parser module

    Author: Vilhjalmur Thorsteinsson

    This software is at a very early development stage.
    While that is the case, it is:
    Copyright (c) 2015 Vilhjalmur Thorsteinsson
    All rights reserved
    See the accompanying README.md file for further licensing and copyright information.

    This module implements the BIN_Parser class, deriving from Parser.
    BIN_Parser parses sentences in Icelandic according to the grammar
    in the file Reynir.grammar.

    BIN refers to 'Beygingarlýsing íslensks nútímamáls', the database of
    word forms in modern Icelandic.

"""

from tokenizer import TOK
from grammar import Terminal, Token, Grammar
from parser import Parser
from settings import Verbs, Prepositions

from flask import current_app

def debug():
    # Call this to trigger the Flask debugger on purpose
    assert current_app.debug == False, "Don't panic! You're here by request of debug()"


class BIN_Token(Token):

    """
        Wrapper class for a token to be processed by the parser

        The layout of a token tuple coming from the tokenizer is
        as follows:

        t[0] Token type (TOK.WORD, etc.)
        t[1] Token text
        t[2] Meaning list, where each item is a tuple:
            m[0] Word stem
            m[1] BIN index (integer)
            m[2] Word type (kk/kvk/hk (=noun), so, lo, ao, fs, etc.)
            m[3] Word category (alm/fyr/ism etc.)
            m[4] Word form (in most cases identical to t[1])
            m[5] Grammatical form (case, gender, number, etc.)

    """

    # Map word types to those used in the grammar
    _KIND = {
        "kk": "no",
        "kvk": "no",
        "hk": "no",
        "so": "so",
        "ao": "ao",
        "fs": "fs",
        "lo": "lo",
        "fn": "fn",
        "pfn": "pfn",
        "gr": "gr",
        "to": "to",
        "töl": "töl",
        "uh": "uh",
        "st": "st",
        "abfn": "abfn",
        "nhm": "nhm"
    }

    # Strings that must be present in the grammatical form for variants
    _VARIANT = {
        "nf" : "NF", # Nefnifall / nominative
        "þf" : "ÞF", # Þolfall / accusative
        "þgf" : "ÞGF", # Þágufall / dative
        "ef" : "EF", # Eignarfall / possessive
        "et" : "ET", # Eintala / singular
        "ft" : "FT", # Fleirtala / plural
        "p1" : "1P", # Fyrsta persóna / first person
        "p2" : "2P", # Önnur persóna / second person
        "p3" : "3P", # Þriðja persóna / third person
        "nh" : "NH", # Nafnháttur
        "sagnb" : "SAGNB", # Sagnbeyging ('vera' -> 'verið')
        "lhþt" : "LHÞT" # Lýsingarháttur þátíðar ('var lentur')
    }

    def __init__(self, t):

        Token.__init__(self, TOK.descr[t[0]], t[1])
        self.t = t
        self._hash = None

    def verb_matches(self, verb, terminal, form):
        """ Return True if the verb in question matches the verb category,
            where the category is one of so_0, so_1, so_2 depending on
            the allowable number of noun phrase arguments """
        # print("verb_matches {0} terminal {1} form {2}".format(verb, terminal, form))
        if terminal.has_variant("et") and "FT" in form:
            # Can't use plural verb if singular terminal
            return False
        if terminal.has_variant("ft") and "ET" in form:
            # Can't use singular verb if plural terminal
            return False
        # Check that person (1st, 2nd, 3rd) and other variant requirements match
        for v in [ "p1", "p2", "p3", "nh", "sagnb", "lhþt"]:
            if terminal.has_variant(v) and not BIN_Token._VARIANT[v] in form:
                return False
        # Check whether the verb token can potentially match the argument number
        # of the terminal in question. If the verb is known to take fewer
        # arguments than the terminal wants, this is not a match.
        if terminal.variant(0) not in "012":
            # No argument number: all verbs match
            return True
        nargs = int(terminal.variant(0))
        if verb in Verbs.VERBS[nargs]:
            # Seems to take the correct number of arguments:
            # do a further check on the supported cases
            if nargs == 0:
                # Zero arguments: that's simple
                return True
            # Does this terminal require argument cases?
            if terminal.num_variants() < 2:
                # No: we don't need to check further
                return True
            # Check whether the parameters of this verb
            # match up with the requirements of the terminal
            # as specified in its variants at indices 1 and onward
            for ix, c in enumerate(Verbs.VERBS[nargs][verb]):
                if terminal.variant(1 + ix) != c:
                    return False
            # No mismatch so far: this verb fulfills the requirements
            return True
        # It's not there with the correct number of arguments:
        # see if it definitely has fewer ones
        for i in range(0, nargs):
            if verb in Verbs.VERBS[i]:
                # Prevent verb from matching a terminal if it
                # doesn't have all the arguments that the terminal requires
                return False
        # Unknown verb or arguments not too many: consider this a match
        return True

    def prep_matches(self, prep, case):
        """ Check whether a preposition matches this terminal """
        if prep not in Prepositions.PP:
            # Not recognized as a preposition
            return False
        # Fine if the case matches
        return case in Prepositions.PP[prep]

    def matches(self, terminal):
        """ Return True if this token matches the given terminal """

        if self.t[0] == TOK.PERSON:
            # Handle a person name, matching it with a singular noun
            if not terminal.startswith("person"):
                return False
            # The case must also be correct
            # For a TOK.PERSON, t[2][2] contains a list of possible cases
            return terminal.variant(0) in self.t[2][2]

        if self.t[0] == TOK.PUNCTUATION:
            return terminal.matches("punctuation", self.t[1])

        if self.t[0] == TOK.CURRENCY:
            # A currency name matches a noun
            if not terminal.startswith("no"):
                return False
            if self.t[2][1] is None:
                # No associated case: match all cases
                return True
            # See whether any of the allowed cases match the terminal
            return terminal.variant(1) in self.t[2][1]

        if self.t[0] == TOK.AMOUNT:
            # An amount matches a noun
            if not terminal.startswith("no"):
                return False
            if terminal.variant(0) == "et" and float(self.t[2][1]) != 1.0:
                # Singular only matches an amount of one
                return False
            if terminal.variant(0) == "ft" and float(self.t[2][1]) == 1.0:
                # Plural does not match an amount of one
                return False
            if self.t[2][2] is None:
                # No associated case: match all cases
                return True
            # See whether any of the allowed cases match the terminal
            return terminal.variant(1) in self.t[2][2]

        def meaning_match(m):
            """ Check for a match between a terminal and a single potential meaning
                of the word """
            # print("meaning_match: kind {0}, val {1}".format(BIN_Token.kind[m[2]], m[4]))
            if terminal.startswith("so"):
                if m[2] != "so":
                    return False
                # Special case for verbs: match only the appropriate
                # argument number, i.e. so_0 for verbs having no noun argument,
                # so_1 for verbs having a single noun argument, and
                # so_2 for verbs with two noun arguments. A verb may
                # match more than one argument number category.
                return self.verb_matches(m[0], terminal, m[5])
            elif terminal.startswith("fs") and terminal.num_variants() > 0:
                return self.prep_matches(m[0], terminal.variant(0))
            if m[5] != "-": # Tokens without a form specifier are assumed to be universally matching
                for v in terminal.variants():
                    if BIN_Token._VARIANT[v] not in m[5]:
                        # Not matching
                        return False
            return terminal.matches_first(BIN_Token._KIND[m[2]], m[0])

        # We have a match if any of the possible meanings
        # of this token match the terminal
        return any(meaning_match(m) for m in self.t[2]) if self.t[2] else False

    def __repr__(self):
        return "[" + TOK.descr[self.t[0]] + ": " + self.t[1] + "]"

    def __str__(self):
        return "\'" + self.t[1] + "\'"

    def __hash__(self):
        if self._hash is None:
            self._hash = hash((self.t[0], self.t[1]))
        return self._hash


class BIN_Parser(Parser):

    """ BIN_Parser parses sentences according to the Icelandic
        grammar in the Reynir.grammar file. It subclasses Parser
        and wraps the interface between the BIN grammatical
        data on one hand and the tokens and grammar terminals on
        the other. """

    # A singleton instance of the parsed Reynir.grammar
    _grammar = None

    # The token types that the parser currently knows how to handle
    _UNDERSTOOD = { TOK.WORD, TOK.PERSON,
        TOK.CURRENCY, TOK.AMOUNT }

    def __init__(self):
        """ Load the shared BIN grammar if not already there, then initialize
            the Parser parent class """
        g = BIN_Parser._grammar
        if g is None:
            g = Grammar()
            g.read("Reynir.grammar")
            BIN_Parser._grammar = g
        Parser.__init__(self, g.nt_dict(), g.root())

    def grammar(self):
        """ Return the grammar loaded from Reynir.grammar """
        return BIN_Parser._grammar

    def go(self, tokens):
        """ Parse the token list after wrapping each understood token in the BIN_Token class """

        def is_understood(t):
            if t[0] in BIN_Parser._UNDERSTOOD:
                return True
            if t[0] == TOK.PUNCTUATION:
                # A limited number of punctuation symbols is currently understood
                return t[1] in ".?" # „“
            return False

        # After wrapping, call the parent class go()
        return Parser.go(self, [BIN_Token(t) for t in tokens if is_understood(t)])

