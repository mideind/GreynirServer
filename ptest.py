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

Parser.print_parse_forest(forest)

print("------ Test 3 ---------")

g = Grammar()
g.read("Reynir.grammar")

print("Grammar:")
print(str(g))
print()

p = Parser.for_grammar(g)

tokens = parse_text("Páll fór með kött og Jón keypti graut")

class BIN_Token(Token):

    """ Token tuple:
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

    def matches(self, terminal):
        """ Return True if this token matches the given terminal """

        if self.t[0] == TOK.PERSON:
            # Handle a person name
            return terminal.matches(BIN_Token.kind[self.t[2][1]], self.t[1])

        def meaning_match(m):
            # print("meaning_match: kind {0}, val {1}".format(BIN_Token.kind[m[2]], m[4]))
            return terminal.matches(BIN_Token.kind[m[2]], m[4])
        # We have a match if any of the possible meanings
        # of this token match the terminal
        return any(meaning_match(m) for m in self.t[2])

    def __repr__(self):
        return self.t.__repr__()

def is_word(t):
    return t[0] < 10000

toklist = [ BIN_Token(t) for t in tokens if is_word(t) ]

print("Toklist:")
for t in toklist:
    print("{0}".format(t))

forest = p.go(toklist)
Parser.print_parse_forest(forest)
