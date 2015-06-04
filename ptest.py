"""
    Reynir: Natural language processing for Icelandic

    Parser test module

    Author: Vilhjalmur Thorsteinsson

    This software is at a very early development stage.
    While that is the case, it is:
    Copyright (c) 2015 Vilhjalmur Thorsteinsson
    All rights reserved

"""

import codecs

from pprint import pprint as pp

from tokenizer import TOK, parse_text
from grammar import Nonterminal, Terminal, Token, Production, Grammar, GrammarError
from parser import Parser, ParseError
from settings import Settings, Verbs, Prepositions, ConfigError


# Read the configuration settings file

try:
    Settings.read("Reynir.conf")
except ConfigError as e:
    print("Configuration error: {0}".format(e))
    quit()

# Test grammar 1

print("------ Test 1 ---------")

# Abbreviations
NT = Nonterminal
TERM = Terminal

# Hard-coded test case - grammar not read from file

E = NT ('E')
T = NT ('T')
P = NT ('P')
plus = TERM ('+')
mult = TERM ('*')
ident = TERM ('ident')

g = {
    E: [Production(rhs=[E,plus,T]), Production(rhs=[T])],
    T: [Production(rhs=[T,mult,P]), Production(rhs=[P])],
    P: [Production(rhs=[ident])],
}

p = Parser(g, E)
s = [
    Token('ident', 'a'),
    Token('*', '*'),
    Token('ident', 'b'),
    Token('+', '+'),
    Token('ident', 'c'),
    Token('*', '*'),
    Token('ident', 'd'),
    Token('+', '+'),
    Token('ident', 'e'),
    Token('+', '+'),
    Token('ident', 'f')
]

forest = p.go(s)

print("Parse combinations: {0}".format(Parser.num_combinations(forest)))

Parser.print_parse_forest(forest)

print("\n\n------ Test 2 ---------")

# Test grammar 2 - read from file

g = Grammar()
g.read("Reynir.test.grammar")

#print("Grammar:")
#print(str(g))
#print()

# s = "Villi leit út eða Anna og köttur komu beint heim og kona eða maður fóru snemma inn"
s = "kona með kött myrti mann með hálsbindi með hund og Páll fór út"
# s = "kona með kött myrti mann með hund og Villi fór út"
# s = "Villi leit út"

class NameToken(Token):

    NÖFN_NF = ["Villi", "Anna", "Hlín", "Páll"]
    NÖFN_ÞF = ["Villa", "Önnu", "Hlín", "Pál"]
    NÖFN_ÞGF = ["Villa", "Önnu", "Hlín", "Páli"]

    def matches(self, terminal):
        """ Does this token match the given terminal? """
        if not terminal.name.startswith("nafn_"):
            return False
        if terminal.name.endswith("_nf"):
            return self.val in NameToken.NÖFN_NF
        if terminal.name.endswith("_þf"):
            return self.val in NameToken.NÖFN_ÞF
        if terminal.name.endswith("_þgf"):
            return self.val in NameToken.NÖFN_ÞGF
        return False

def make_token(w):
    if w[0].isupper():
        return NameToken('nafn', w)
    return Token('orð', w)

toklist = [make_token(w) for w in s.split()]

p = Parser.for_grammar(g)

forest = p.go(toklist)

print("Parse combinations: {0}".format(Parser.num_combinations(forest)))

Parser.print_parse_forest(forest)

print("\n\n------ Test 3 ---------")

g = Grammar()

try:
    g.read("Reynir.grammar")
except GrammarError as e:
    print("{0}".format(e))
    quit()

#print("Grammar:")
#print(str(g))
#rint()

p = Parser.for_grammar(g)

class BIN_Token(Token):

    """
        Wrapper class for a token to be processed by the parser

        Token tuple:
        t[0] Token type (TOK.WORD, etc.)
        t[1] Token text
        t[2] Meaning list, where each item is a tuple:
            m[0] Word stem
            m[1] BIN index (integer)
            m[2] Word type (kk/kvk/hk, so, lo, ao, fs, etc.)
            m[3] Word category (alm/fyr/ism etc.)
            m[4] Word form (in most cases identical to t[1])
            m[5] Grammatical form (declension, tense, etc.)
    """

    # Map word types to those used in the grammar
    KIND = {
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
    VARIANT = {
        "nf" : "NF",
        "þf" : "ÞF",
        "þgf" : "ÞGF",
        "ef" : "EF",
        "et" : "ET",
        "ft" : "FT"
    }

    def __init__(self, t):

        Token.__init__(self, TOK.descr[t[0]], t[1])
        self.t = t
        self._hash = None

    def verb_matches(self, verb, category, form):
        """ Return True if the verb in question matches the verb category,
            where the category is one of so_0, so_1, so_2 depending on
            the allowable number of noun arguments """
        if category[-3:] == "_et" and "FT" in form:
            # Can't use plural verb if singular terminal
            return False
        if category[-3:] == "_ft" and "ET" in form:
            # Can't use singular verb if plural terminal
            return False
        nargs = int(category[3:4])
        for i in range(0, nargs):
            if verb in Verbs.VERBS[i]:
                # Prevent verb from taking more arguments than allowed
                return False
        # Unknown verb or arguments not too many: consider this a match
        return True

    def prep_matches(self, prep, case):
        # Check whether a preposition matches this terminal
        if prep not in Prepositions.PP:
            # Not recognized as a preposition
            return False
        # Fine if the case matches
        return case in Prepositions.PP[prep]

    def matches(self, terminal):
        """ Return True if this token matches the given terminal """

        if self.t[0] == TOK.PERSON:
            # Handle a person name, matching it with a noun
            # !!! TBD !!! missing case information with TOK_PERSON
            return terminal.name.startswith("no_et_")
            #return terminal.matches("no", self.t[1])

        def meaning_match(m):
            """ Check for a match between a terminal and a single potential meaning
                of the word """
            # print("meaning_match: kind {0}, val {1}".format(BIN_Token.kind[m[2]], m[4]))
            if terminal.name.startswith("so_"):
                if m[2] != "so":
                    return False
                # Special case for verbs: match only the appropriate
                # argument number, i.e. so_0 for verbs having no noun argument,
                # so_1 for verbs having a single noun argument, and
                # so_2 for verbs with two noun arguments. A verb may
                # match more than one argument number category.
                return self.verb_matches(m[0], terminal.name, m[5])
            elif terminal.name.startswith("fs_"):
                return self.prep_matches(m[0], terminal.name[3:])
            tn = terminal.name.split("_")
            for v in tn[1:]:
                if BIN_Token.VARIANT[v] not in m[5]:
                    # Not matching
                    return False
            k = BIN_Token.KIND[m[2]]
            if len(tn) > 1:
                k = "_".join([ k ] + tn[1:])
            return terminal.matches(k, m[0])

        # We have a match if any of the possible meanings
        # of this token match the terminal
        return any(meaning_match(m) for m in self.t[2])

    def __repr__(self):
        return repr(self.t)

    def __str__(self):
        return "\'" + self.t[1] + "\'"

    def __hash__(self):
        if self._hash is None:
            self._hash = hash((self.t[0], self.t[1]))
        return self._hash


def is_word(t):
    return t[0] < 10000


TEXTS = [
    "Páll fór út með stóran kött og Jón keypti heitan graut",
    "Konan elti feita karlinn",
    "Kötturinn sem strákurinn átti veiddi feitu músina",
    "Gamla bláa kommóðan var máluð fjólublá með olíumálningu",
    "Landsframleiðslan hefur aukist frá því í fyrra",
    "Guðmundur og Guðrún kusu Framsóknarflokkinn",
    "Guðmundur og Guðrún kaus Framsóknarflokkinn",
    "Þú skalt fara til Danmerkur",
    "Þú skalt fara til Danmörk",
    "Ég og þú fórum til Frakklands í utanlandsferð",
    "Stóru bláu könnunni mun hafa verið fleygt í ruslið",
    "Már Guðmundsson segir margskonar misskilnings gæta hjá Hannesi Hólmsteini",
    "Þetta segir Már Guðmundsson seðlabankastjóri við Morgunblaðið í dag"
]

for txt in TEXTS:

    print("\n\"{0}\"".format(txt))

    tokens = parse_text(txt)

    toklist = [ BIN_Token(t) for t in tokens if is_word(t) ]

    #print("Toklist:")
    #for t in toklist:
    #    print("{0}".format(t))

    try:
        forest = p.go(toklist)
    except ParseError as e:
        print("{0}".format(e))
        continue

    num = 0 if forest is None else Parser.num_combinations(forest)

    print("Parse combinations: {0}".format(num))

    Parser.print_parse_forest(forest, detailed = False)

