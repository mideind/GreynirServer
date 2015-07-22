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
from parser import Parser, ParseError
from settings import VerbObjects, VerbSubjects, Prepositions

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
        "kk" : "KK", # Karlkyn / masculine
        "kvk" : "KVK", # Kvenkyn / feminine
        "hk" : "HK", # Hvorugkyn / neutral
        "et" : "ET", # Eintala / singular
        "ft" : "FT", # Fleirtala / plural
        "p1" : "1P", # Fyrsta persóna / first person
        "p2" : "2P", # Önnur persóna / second person
        "p3" : "3P", # Þriðja persóna / third person
        "op" : "OP", # Ópersónuleg sögn
        "gm" : "GM", # Germynd
        "mm" : "MM", # Miðmynd
        "sb" : "SB", # Sterk beyging
        "nh" : "NH", # Nafnháttur
        "lh" : "LH", # Lýsingarháttur (nútíðar)
        "vh" : "VH", # Viðtengingarháttur
        "nt" : "NT", # Nútíð
        "þt" : "ÞT", # Nútíð
        "sagnb" : "SAGNB", # Sagnbeyging ('vera' -> 'verið')
        "lhþt" : "LHÞT" # Lýsingarháttur þátíðar ('var lentur')
    }

    _GENDERS = [ "kk", "kvk", "hk" ]


    def __init__(self, t):

        Token.__init__(self, TOK.descr[t[0]], t[1])
        self.t = t
        self._hash = None

    def verb_matches(self, verb, terminal, form):
        """ Return True if the verb in question matches the verb category,
            where the category is one of so_0, so_1, so_2 depending on
            the allowable number of noun phrase arguments """
        if terminal.has_variant("subj"):
            # Verb subject in non-nominative case
            if terminal.has_variant("nh"):
                if "NH" not in form:
                    # Nominative mode (nafnháttur)
                    return False
            #elif "OP" not in form:
            #    # !!! BIN seems to be not 100% consistent in the OP annotation
            #    return False
            if terminal.has_variant("mm"):
                # Central form of verb ('miðmynd')
                return "MM" in form
            if terminal.has_variant("et") and not "ET" in form:
                # Require singular
                return False
            if terminal.has_variant("ft") and not "FT" in form:
                # Require plural
                return False
            # Make sure that the subject case (last variant) matches the terminal
            return VerbSubjects.VERBS.get(verb, "") == terminal.variant(-1)
        if terminal.has_variant("et") and "FT" in form:
            # Can't use plural verb if singular terminal
            return False
        if terminal.has_variant("ft") and "ET" in form:
            # Can't use singular verb if plural terminal
            return False
        # print("verb_matches {0} terminal {1} form {2}".format(verb, terminal, form))
        # Check that person (1st, 2nd, 3rd) and other variant requirements match
        for v in [ "p1", "p2", "p3", "nh", "vh", "lh", "sagnb", "lhþt", "nt", "kk", "kvk", "hk", "sb", "gm", "mm" ]:
            if terminal.has_variant(v) and not BIN_Token._VARIANT[v] in form:
                return False
        # Check restrictive variants, i.e. we don't accept meanings
        # that have those unless they are explicitly present in the terminal
        for v in [ "sagnb", "lhþt" ]: # Be careful with "lh" here - !!! add mm?
            if BIN_Token._VARIANT[v] in form and not terminal.has_variant(v):
                return False
        if terminal.has_variant("lhþt") and "VB" in form:
            # We want only the strong declinations ("SB") of lhþt, not the weak ones
            return False
        # Check whether the verb token can potentially match the argument number
        # of the terminal in question. If the verb is known to take fewer
        # arguments than the terminal wants, this is not a match.
        if terminal.variant(0) not in "012":
            # No argument number: all verbs match
            return True
        nargs = int(terminal.variant(0))
        if verb in VerbObjects.VERBS[nargs]:
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
            for argspec in VerbObjects.VERBS[nargs][verb]:
                if all(terminal.variant(1 + ix) == c for ix, c in enumerate(argspec)):
                    # All variants match this spec: we're fine
                    return True
            # No match: return False
            return False
        # It's not there with the correct number of arguments:
        # see if it definitely has fewer ones
        for i in range(0, nargs):
            if verb in VerbObjects.VERBS[i]:
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

        t0, t1, t2 = self.t

        if t0 == TOK.PERSON:
            # Handle a person name, matching it with a singular noun
            if not terminal.startswith("person"):
                return False
            # Check each PersonName tuple in the t2 list
            for p in t2:
                if terminal.variant(1) == p.gender and terminal.variant(0) == p.case:
                    # Case and gender matches: we're good
                    return True
            # No match found
            return False

        if t0 == TOK.PUNCTUATION:
            return terminal.matches("punctuation", t1)

        if t0 == TOK.CURRENCY:
            # A currency name matches a noun
            if not terminal.startswith("no"):
                return False
            if terminal.has_variant("abbrev"):
                # A currency does not match an abbreviation
                return False
            if t2[1] is None:
                # No associated case: match all cases
                return True
            # See whether any of the allowed cases match the terminal
            return terminal.num_variants() >= 2 and terminal.variant(1) in t2[1]

        if t0 == TOK.AMOUNT:
            # An amount matches a noun
            if not terminal.startswith("no"):
                return False
            if terminal.has_variant("abbrev"):
                # An amount does not match an abbreviation
                return False
            if terminal.has_variant("et") and float(t2[1]) != 1.0:
                # Singular only matches an amount of one
                return False
            if terminal.has_variant("ft") and float(t2[1]) == 1.0:
                # Plural does not match an amount of one
                return False
            if t2[3] is not None:
                # Associated gender
                for g in BIN_Token._GENDERS:
                    if terminal.has_variant(g) and t2[3] != g:
                        return False
            if t2[2] is None:
                # No associated case: match all cases
                return True
            # See whether any of the allowed cases match the terminal
            return terminal.num_variants() >= 2 and terminal.variant(1) in t2[2]

        if t0 == TOK.NUMBER:
            if terminal.startswith("töl"):
                # Match number words if gender matches
                if t2[2] is not None:
                    # Associated gender
                    for g in BIN_Token._GENDERS:
                        if terminal.has_variant(g) and t2[2] != g:
                            return False
                return True
            if not terminal.startswith("no"):
                # Not noun: no match
                return False
            if terminal.has_variant("abbrev"):
                # A number does not match an abbreviation
                return False
            if terminal.has_variant("et") and float(t2[0]) != 1.0:
                # Singular only matches an amount of one
                return False
            if terminal.has_variant("ft") and float(t2[0]) == 1.0:
                # Plural does not match an amount of one
                return False
            if t2[2] is not None:
                # Associated gender
                for g in BIN_Token._GENDERS:
                    if terminal.has_variant(g) and t2[2] != g:
                        return False
            if t2[1] is None:
                # No associated case: match all cases
                return True
            # See whether any of the allowed cases match the terminal
            return terminal.num_variants() >= 2 and terminal.variant(1) in t2[1]

        if t0 == TOK.PERCENT:
            if terminal.startswith("töl"):
                # Match number words without further ado
                return True
            if not terminal.startswith("no"):
                # Not noun: no match
                return False
            if terminal.has_variant("abbrev"):
                # A percentage does not match an abbreviation
                return False
            if terminal.has_variant("et") and float(t2) != 1.0:
                # Singular only matches an percentage of one
                return False
            if terminal.has_variant("ft") and float(t2) == 1.0:
                # Plural does not match an percentage of one
                return False
            if terminal.has_variant("kk") or terminal.has_variant("kvk"):
                # Percentages only match the neutral gender
                return False
            # No case associated with percentages: match all
            return True

        if t0 == TOK.DATE:
            return terminal.startswith("dags")

        if t0 == TOK.ORDINAL:
            return terminal.startswith("raðnr")

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
            if terminal.startswith("fs") and terminal.num_variants() > 0:
                return self.prep_matches(t1.lower(), terminal.variant(0))
                # return self.prep_matches(m[0], terminal.variant(0))
            if terminal.startswith("no"):
                # Check noun
                if BIN_Token._KIND[m[2]] != "no":
                    return False
                if terminal.has_variant("abbrev"):
                    # Only match abbreviations; gender, case and number do not matter
                    return m[5] == "-"
                for v in terminal.variants():
                    if v in { "kk", "kvk", "hk"}:
                        if m[2] != v:
                            # Mismatched gender
                            return False
                    elif BIN_Token._VARIANT[v] not in m[5] and m[5] != "-":
                        # Case or number not matching
                        return False
                return True
            # Check other word categories
            if m[5] != "-": # Tokens without a form specifier are assumed to be universally matching
                for v in terminal.variants():
                    if BIN_Token._VARIANT[v] not in m[5]:
                        # Not matching
                        return False
            return terminal.matches_first(BIN_Token._KIND[m[2]], m[0])

        # We have a match if any of the possible meanings
        # of this token match the terminal
        return any(meaning_match(m) for m in t2) if t2 else False

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
    _UNDERSTOOD = { TOK.WORD, TOK.PERSON, TOK.DATE,
        TOK.CURRENCY, TOK.AMOUNT, TOK.NUMBER, TOK.PERCENT,
        TOK.ORDINAL }

    def __init__(self):
        """ Load the shared BIN grammar if not already there, then initialize
            the Parser parent class """
        g = BIN_Parser._grammar
        if g is None:
            g = Grammar()
            g.read("Reynir.grammar")
            BIN_Parser._grammar = g
        Parser.__init__(self, g)

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
                return t[1] in ".?,„“"
            return False

        bt = [BIN_Token(t) for t in tokens if is_understood(t)]
        # Count the tokens, excluding punctuation
        cw = sum(1 if t.t[0] != TOK.PUNCTUATION else 0 for t in bt)
        # After wrapping, call the parent class go()
        return Parser.go(self, bt)

