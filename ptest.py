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
from settings import Settings, Verbs


Settings.read("Reynir.conf")

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

print("------ Test 2 ---------")

# Test grammar 2 - read from file

g = Grammar()
g.read("Reynir.test.grammar")

# pp(g.grammar())

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

print("------ Test 3 ---------")

g = Grammar()
g.read("Reynir.grammar")

print("Grammar:")
print(str(g))
print()

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
    kind = {
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

    def __init__(self, t):

        Token.__init__(self, TOK.descr[t[0]], t[1])
        self.t = t
        self._hash = None

    def verb_matches(self, verb, category):
        """ Return True if the verb in question matches the verb category,
            where the category is one of so_0, so_1, so_2 depending on
            the allowable number of noun arguments """
        nargs = int(category[3:])
        for i in range(0, nargs):
            if verb in Verbs.VERBS[i]:
                # Prevent verb from taking more arguments than allowed
                return False
        # Unknown verb or arguments not too many: consider this a match
        return True

    def matches(self, terminal):
        """ Return True if this token matches the given terminal """

        if self.t[0] == TOK.PERSON:
            # Handle a person name
            return terminal.matches(BIN_Token.kind[self.t[2][1]], self.t[1])

        def meaning_match(m):
            """ Check for a match between a terminal and a single potential meaning
                of the word """
            # print("meaning_match: kind {0}, val {1}".format(BIN_Token.kind[m[2]], m[4]))
            if m[2] == "so" and terminal.name.startswith("so_"):
                # Special case for verbs: match only the appropriate
                # argument number, i.e. so_0 for verbs having no noun argument,
                # so_1 for verbs having a single noun argument, and
                # so_2 for verbs with two noun arguments. A verb may
                # match more than one argument number category.
                return self.verb_matches(m[0], terminal.name)
            return terminal.matches(BIN_Token.kind[m[2]], m[0])

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
    "Gamla bláa kommóðan var máluð gul með olíumálningu",
    "Landsframleiðslan hefur aukist frá því í fyrra",
    "Þú skalt fara til Danmerkur",
    "Ég og þú fórum til Frakklands í utanlandsferð",
    "Stóru bláu könnunni mun hafa verið fleygt í ruslið"
]

for txt in TEXTS:

    print("\"{0}\"".format(txt))

    tokens = parse_text(txt)

    toklist = [ BIN_Token(t) for t in tokens if is_word(t) ]

    #print("Toklist:")
    #for t in toklist:
    #    print("{0}".format(t))

    forest = p.go_no_exc(toklist)

    num = 0 if forest is None else Parser.num_combinations(forest)

    print("Parse combinations: {0}".format(num))

    Parser.print_parse_forest(forest, detailed = False)
