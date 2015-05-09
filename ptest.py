# -*- coding: utf-8 -*-

""" Reynir: Natural language processing for Icelandic

    Parser test module

    Author: Vilhjalmur Thorsteinsson

    This software is at a very early development stage.
    While that is the case, it is:
    Copyright (c) 2015 Vilhjalmur Thorsteinsson
    All rights reserved

"""

import codecs

from pprint import pprint as pp

from grammar import Nonterminal, Terminal, Token, Production, Grammar, GrammarError
from parser import Parser, ParseError


# Test grammar 1

print("------ Test 1 ---------")

# Abbreviations
NT = Nonterminal
TERM = Terminal
TOK = Token

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
    TOK('ident', 'a'),
    TOK('*', '*'),
    TOK ('ident', 'b'),
    TOK ('+', '+'),
    TOK ('ident', 'c'),
    TOK ('*', '*'),
    TOK ('ident', 'd'),
    TOK ('+', '+'),
    TOK ('ident', 'e'),
    TOK ('+', '+'),
    TOK ('ident', 'f')
]
forest = p.go(s)
Parser.print_parse_forest(forest)

print("------ Test 2 ---------")

# Test grammar 2 - read from file

g = Grammar()
g.read("Reynir.grammar")

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
    return TOK('orð', w)

toklist = [make_token(w) for w in s.split()]

p = Parser.for_grammar(g)

forest = p.go(toklist)

Parser.print_parse_forest(forest)
