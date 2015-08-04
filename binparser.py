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
        t[2] For TOK.WORD: Meaning list, where each item is a tuple:
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
        "mst" : "MST", # Miðstig / comparative
        "p1" : "1P", # Fyrsta persóna / first person
        "p2" : "2P", # Önnur persóna / second person
        "p3" : "3P", # Þriðja persóna / third person
        "op" : "OP", # Ópersónuleg sögn
        "gm" : "GM", # Germynd
        "mm" : "MM", # Miðmynd
        "sb" : "SB", # Sterk beyging
        "nh" : "NH", # Nafnháttur
        "bh" : "BH", # Boðháttur
        "lh" : "LH", # Lýsingarháttur (nútíðar)
        "vh" : "VH", # Viðtengingarháttur
        "nt" : "NT", # Nútíð
        "þt" : "ÞT", # Nútíð
        "sagnb" : "SAGNB", # Sagnbeyging ('vera' -> 'verið')
        "lhþt" : "LHÞT" # Lýsingarháttur þátíðar ('var lentur')
    }

    _GENDERS = [ "kk", "kvk", "hk" ]
    _GENDERS_SET = set(_GENDERS)

    # Variants to be checked for verbs
    _VERB_VARIANTS = [ "p1", "p2", "p3", "nh", "vh", "lh", "bh",
        "sagnb", "lhþt", "nt", "kk", "kvk", "hk", "sb", "gm", "mm" ]
    # Pre-calculate a dictionary of associated BIN forms
    _VERB_FORMS = None # Initialized later

    # Set of adverbs that cannot be an "eo" (prepositions are already excluded)
    _NOT_EO = { "og", "eða", "sem" }
    # Prepositions that nevertheless must be allowed as adverbs
    _NOT_NOT_EO = { "inn" } # 'Fyrirtækið hefur skilað inn ársreikningi'

    def __init__(self, t):

        Token.__init__(self, TOK.descr[t[0]], t[1])
        self.t0 = t[0] # Token type (TOK.WORD, etc.)
        self.t1 = t[1] # Token text
        self.t1_lower = t[1].lower() # Token text, lower case
        self.t2 = t[2] # Token information, such as part-of-speech annotation, numbers, etc.
        self._hash = None # Cached hash

        # We store a cached check of whether this is an "eo". An "eo" is an adverb (atviksorð)
        # that cannot also be a preposition ("fs") and is therefore a possible non-ambiguous
        # prefix to a noun ("einkunn")
        self._is_eo = None

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
            return terminal.variant(-1) in VerbSubjects.VERBS.get(verb, set())
        if terminal.has_variant("et") and "FT" in form:
            # Can't use plural verb if singular terminal
            return False
        if terminal.has_variant("ft") and "ET" in form:
            # Can't use singular verb if plural terminal
            return False
        # print("verb_matches {0} terminal {1} form {2}".format(verb, terminal, form))
        # Check that person (1st, 2nd, 3rd) and other variant requirements match
        for v in terminal.variants():
            # Lookup variant to see if it is one of the required ones for verbs
            rq = BIN_Token._VERB_FORMS.get(v)
            if rq is not None and not rq in form:
                # If this is required variant that is not found in the form we have,
                # return False
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
            # The following is not consistent as some verbs take
            # legitimate arguments in 'miðmynd', such as 'krefjast', 'ábyrgjast'
            # 'undirgangast', 'minnast'. They are also not consistently
            # annotated in BIN; some of them are marked as MM and some not.
            #if BIN_Token._VARIANT["mm"] in form:
            #    # Don't accept verbs in 'miðmynd' if taking arguments
            #    # (unless the root form of the verb is in VerbObjects, to
            #    # compensate for errors in BÍN, cf. 'ábyrgjast')
            #    return False
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

    def matches_PERSON(self, terminal):
        """ Handle a person name token, matching it with a person_[case]_[gender] terminal """
        if not terminal.startswith("person"):
            return False
        # Check each PersonName tuple in the t2 list
        for p in self.t2:
            if terminal.variant(1) == p.gender and terminal.variant(0) == p.case:
                # Case and gender matches: we're good
                return True
        # No match found
        return False

    def matches_PUNCTUATION(self, terminal):
        """ Match a literal terminal with the same content as the punctuation token """
        return terminal.matches("punctuation", self.t1, self.t1)

    def matches_CURRENCY(self, terminal):
        """ A currency name token matches a noun terminal """
        if not terminal.startswith("no"):
            return False
        if terminal.has_variant("abbrev"):
            # A currency does not match an abbreviation
            return False
        if not self.t2[1]:
            # No associated case: match all cases
            return True
        # See whether any of the allowed cases match the terminal
        return terminal.num_variants() >= 2 and terminal.variant(1) in self.t2[1]

    def matches_AMOUNT(self, terminal):
        """ An amount token matches a noun terminal """
        if not terminal.startswith("no"):
            return False
        if terminal.has_variant("abbrev"):
            # An amount does not match an abbreviation
            return False
        if terminal.has_variant("et") and float(self.t2[1]) != 1.0:
            # Singular only matches an amount of one
            return False
        if terminal.has_variant("ft") and float(self.t2[1]) == 1.0:
            # Plural does not match an amount of one
            return False
        if self.t2[3] is None:
            # No gender: match neutral gender only
            if terminal.has_variant("kk") or terminal.has_variant("kvk"):
                return False
        else:
            # Associated gender
            for g in BIN_Token._GENDERS:
                if terminal.has_variant(g) and self.t2[3] != g:
                    return False
        if not self.t2[2]:
            # No associated case: match all cases
            return True
        # See whether any of the allowed cases match the terminal
        return terminal.num_variants() >= 2 and terminal.variant(1) in self.t2[2]

    def matches_NUMBER(self, terminal):
        """ A number token matches a number (töl) or noun terminal """
        if terminal.startswith("töl"):
            # Match number words if gender matches
            if self.t2[2] is not None:
                # Associated gender
                for g in BIN_Token._GENDERS:
                    if terminal.has_variant(g) and self.t2[2] != g:
                        return False
            return True
        if not terminal.startswith("no"):
            # Not noun: no match
            return False
        if terminal.has_variant("abbrev"):
            # A number does not match an abbreviation
            return False
        if terminal.has_variant("et") and float(self.t2[0]) != 1.0:
            # Singular only matches an amount of one
            return False
        if terminal.has_variant("ft") and float(self.t2[0]) == 1.0:
            # Plural does not match an amount of one
            return False
        if self.t2[2] is None:
            # No associated gender: match neutral gender only
            if terminal.has_variant("kk") or terminal.has_variant("kvk"):
                return False
        else:
            # Associated gender
            for g in BIN_Token._GENDERS:
                if terminal.has_variant(g) and self.t2[2] != g:
                    return False
        if not self.t2[1]:
            # No associated case: match all cases
            return True
        # See whether any of the allowed cases match the terminal
        return terminal.num_variants() >= 2 and terminal.variant(1) in self.t2[1]

    def matches_PERCENT(self, terminal):
        """ A percent token matches a number (töl) or noun terminal """
        if terminal.startswith("töl"):
            # Match number words without further ado
            return True
        if not terminal.startswith("no"):
            # Not noun: no match
            return False
        if terminal.has_variant("abbrev"):
            # A percentage does not match an abbreviation
            return False
        if terminal.has_variant("et") and float(self.t2) != 1.0:
            # Singular only matches an percentage of one
            return False
        if terminal.has_variant("ft") and float(self.t2) == 1.0:
            # Plural does not match an percentage of one
            return False
        if terminal.has_variant("kk") or terminal.has_variant("kvk"):
            # Percentages only match the neutral gender
            return False
        # No case associated with percentages: match all
        return True

    def matches_YEAR(self, terminal):
        """ A year token matches a number (töl), year (ártal) or noun terminal """
        if terminal.startswith("töl") or terminal.startswith("ártal"):
            # Match number words and years without further ado
            return True
        if not terminal.startswith("no"):
            # Not noun: no match
            return False
        if terminal.has_variant("abbrev"):
            # A year does not match an abbreviation
            return False
        if not terminal.has_variant("et"):
            # Only singular match ('2014 var gott ár', not '2014 voru góð ár')
            return False
        if terminal.has_variant("kk") or terminal.has_variant("kvk"):
            # Years only match the neutral gender
            return False
        # No case associated with year numbers: match all
        return True

    def matches_DATE(self, terminal):
        """ A date token matches a date (dags) terminal """
        return terminal.startswith("dags")

    def matches_TIME(self, terminal):
        """ A time token matches a time (tími) terminal """
        return terminal.startswith("tími")

    def matches_TIMESTAMP(self, terminal):
        """ A timestamp token matches a timestamp (tímapunktur) terminal """
        return terminal.startswith("tímapunktur")

    def matches_ORDINAL(self, terminal):
        """ An ordinal token matches an ordinal (raðnr) terminal """
        return terminal.startswith("raðnr")

    def matches_WORD(self, terminal):
        """ Match a word token, having the potential part-of-speech meanings
            from the BIN database, with the terminal """

        def meaning_match(m):
            """ Check for a match between a terminal and a single potential meaning
                of the word """
            # print("meaning_match: kind {0}, val {1}".format(BIN_Token.kind[m[2]], m[4]))

            if terminal.startswith("so"):
                # Check verb
                if m[2] != "so":
                    return False
                # Special case for verbs: match only the appropriate
                # argument number, i.e. so_0 for verbs having no noun argument,
                # so_1 for verbs having a single noun argument, and
                # so_2 for verbs with two noun arguments. A verb may
                # match more than one argument number category.
                return self.verb_matches(m[0], terminal, m[5])

            if terminal.startswith("no"):
                # Check noun
                if BIN_Token._KIND[m[2]] != "no":
                    return False
                if terminal.has_variant("abbrev"):
                    # Only match abbreviations; gender, case and number do not matter
                    return m[5] == "-"
                for v in terminal.variants():
                    if v in BIN_Token._GENDERS_SET:
                        if m[2] != v:
                            # Mismatched gender
                            return False
                    elif BIN_Token._VARIANT[v] not in m[5] and m[5] != "-":
                        # Case or number not matching
                        return False
                return True

            if terminal.startswith("eo"):
                # 'Einkunnarorð': adverb (atviksorð) that is not the same
                # as a preposition (forsetning)
                if m[2] != "ao":
                    return False
                # This token can match an adverb:
                # Cache whether it can also match a preposition
                if self._is_eo is None:
                    if self.t1_lower in BIN_Token._NOT_EO:
                        # Explicitly forbidden, no need to check further
                        self._is_eo = False
                    elif self.t1_lower in BIN_Token._NOT_NOT_EO:
                        # Explicitly allowed, no need to check further
                        self._is_eo = True
                    else:
                        # Check whether also a preposition and return False in that case
                        self._is_eo = not any(mm[2] == "fs" for mm in self.t2)
                # Return True if this token cannot also match a preposition
                return self._is_eo

            if terminal.startswith("fs") and terminal.num_variants() > 0:
                # Check preposition
                return self.prep_matches(self.t1_lower, terminal.variant(0))

            # Check other word categories
            if m[5] != "-": # Tokens without a form specifier are assumed to be universally matching
                for v in terminal.variants():
                    if BIN_Token._VARIANT[v] not in m[5]:
                        # Not matching
                        return False
            return terminal.matches_first(BIN_Token._KIND[m[2]], m[0], self.t1_lower)

        # We have a match if any of the possible part-of-speech meanings
        # of this token match the terminal
        if self.t2:
            return any(meaning_match(m) for m in self.t2)

        # Unknown word: allow it to match a singular, neutral noun in all cases
        return terminal.startswith("no") and terminal.has_variant("et") and \
            terminal.has_variant("hk")

    # Dispatch table for the token matching functions
    _MATCHING_FUNC = {
        TOK.PERSON: matches_PERSON,
        TOK.PUNCTUATION: matches_PUNCTUATION,
        TOK.CURRENCY: matches_CURRENCY,
        TOK.AMOUNT: matches_AMOUNT,
        TOK.NUMBER: matches_NUMBER,
        TOK.PERCENT: matches_PERCENT,
        TOK.YEAR: matches_YEAR,
        TOK.DATE: matches_DATE,
        TOK.TIME: matches_TIME,
        TOK.TIMESTAMP: matches_TIMESTAMP,
        TOK.WORD: matches_WORD
    }

    @classmethod
    def is_understood(cls, t):
        """ Return True if the token type is understood by the BIN Parser """
        if t[0] == TOK.PUNCTUATION:
            # A limited number of punctuation symbols is currently understood
            return t[1] in ".?,:–"
        return t[0] in cls._MATCHING_FUNC

    def matches(self, terminal):
        """ Return True if this token matches the given terminal """
        # Dispatch the token matching according to the dispatch table in _MATCHING_FUNC
        return BIN_Token._MATCHING_FUNC[self.t0](self, terminal)

    def __repr__(self):
        return "[" + TOK.descr[self.t0] + ": " + self.t1 + "]"

    def __str__(self):
        return "\'" + self.t1 + "\'"

    def __hash__(self):
        if self._hash is None:
            self._hash = hash((self.t0, self.t1))
        return self._hash

    @classmethod
    def init(cls):
        # Initialize cached dictionary of verb variant forms in BIN
        cls._VERB_FORMS = { v : cls._VARIANT[v] for v in cls._VERB_VARIANTS }

BIN_Token.init()


class BIN_Parser(Parser):

    """ BIN_Parser parses sentences according to the Icelandic
        grammar in the Reynir.grammar file. It subclasses Parser
        and wraps the interface between the BIN grammatical
        data on one hand and the tokens and grammar terminals on
        the other. """

    # A singleton instance of the parsed Reynir.grammar
    _grammar = None

    def __init__(self, strict = False):
        """ Load the shared BIN grammar if not already there, then initialize
            the Parser parent class """
        g = BIN_Parser._grammar
        if g is None:
            g = Grammar()
            g.read("Reynir.grammar", strict = strict)
            BIN_Parser._grammar = g
        Parser.__init__(self, g)

    def grammar(self):
        """ Return the grammar loaded from Reynir.grammar """
        return BIN_Parser._grammar

    def go(self, tokens):
        """ Parse the token list after wrapping each understood token in the BIN_Token class """

        # Remove stuff that won't be understood in any case
        # Start with runs of unknown words inside parentheses
        tlist = list(tokens)
        tlen = len(tlist)

        def scan_par(left):
            """ Scan tokens inside parentheses and remove'em all
                if they are only unknown words - perhaps starting with
                an abbreviation """
            right = left + 1
            while right < tlen:
                tok = tlist[right]
                if tok[0] == TOK.PUNCTUATION and tok[1] == ')':
                    # Check the contents of the token list from left+1 to right-1

                    def is_unknown(t):
                        """ A token is unknown if it is a TOK.UNKNOWN or if it is a
                            TOK.WORD with no meanings """
                        UNKNOWN = { "e.", "t.d.", "þ.e.", "m.a." } # Abbreviations and stuff that we ignore inside parentheses
                        return t[0] == TOK.UNKNOWN or (t[0] == TOK.WORD and not t[2]) or t[1] in UNKNOWN

                    if all(is_unknown(t) for t in tlist[left+1:right]):
                        # Only unknown tokens: erase'em, including the parentheses
                        for ix in range(left, right + 1):
                            tlist[ix] = None

                    return right + 1

                right += 1
            # No match: we're done
            return right

        ix = 0
        while ix < tlen:
            tok = tlist[ix]
            if tok[0] == TOK.PUNCTUATION and tok[1] == '(':
                ix = scan_par(ix) # Jumps to the right parenthesis, if found
            else:
                ix += 1

        # Wrap the sanitized token list in BIN_Token()
        bt = [ BIN_Token(t) for t in tlist if t is not None and BIN_Token.is_understood(t) ]

        # After wrapping, call the parent class go()
        return Parser.go(self, bt)

