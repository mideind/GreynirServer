"""
    Reynir: Natural language processing for Icelandic

    Parser test module

    Author: Vilhjalmur Thorsteinsson

    This software is at a very early development stage.
    While that is the case, it is:
    Copyright (c) 2015 Vilhjalmur Thorsteinsson
    All rights reserved
    See the accompanying README.md file for further licensing and copyright information.

"""

import codecs
import time

# from pprint import pprint as pp

from tokenizer import TOK, parse_text
from grammar import Nonterminal, Terminal, Token, Production, Grammar, GrammarError
from parser import Parser, ParseError
from binparser import BIN_Parser
from settings import Settings, Verbs, Prepositions, ConfigError


def test1():
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


def test2():

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


def test3():

    print("\n\n------ Test 3 ---------")

    p = BIN_Parser()
    g = p.grammar()

    print("Reynir.grammar has {0} nonterminals, {1} terminals, {2} productions"
        .format(g.num_nonterminals(), g.num_terminals(), g.num_productions()))

    #print(sorted(g._terminals.keys()))
    #print("Grammar:")
    #print(str(g))
    #print()

    TEXTS = [
        "Páll fór út með stóran kött og Jón keypti heitan graut.",
        "Unga fallega konan frá Garðabæ elti ljóta og feita karlinn rösklega og fumlaust í svörtu myrkrinu",
        "Kötturinn sem strákurinn átti veiddi feitu músina",
        "Gamla bláa kommóðan var máluð fjólublá með olíumálningu",
        "Landsframleiðslan hefur aukist frá því í fyrra",
        "Guðmundur og Guðrún kusu Framsóknarflokkinn",
        "Guðmundur og Guðrún kaus Framsóknarflokkinn",
        "Þú skalt fara til Danmerkur.",
        "Þú skalt fara til Danmörk.",
        "Ég og þú fórum til Frakklands í utanlandsferð",
        "Stóru bláu könnunni mun hafa verið fleygt í ruslið",
        "Már Guðmundsson segir margskonar misskilnings gæta hjá Hannesi Hólmsteini",
        "Már Guðmundsson seðlabankastjóri Íslands segir þetta við Morgunblaðið í dag.",
        "Þetta segir Már Guðmundsson seðlabankastjóri við Morgunblaðið í dag.",
        "Það er náttúrlega einungis í samfélögum sem eiga við býsna stór vandamál að stríða að ný stjórnmálaöfl geta snögglega sveiflast upp í þriðjungs fylgi."
    ]

    for txt in TEXTS:

        print("\n\"{0}\"".format(txt))

        tokens = parse_text(txt)

        try:
            t0 = time.time()
            forest = p.go(tokens)
            t1 = time.time()
        except ParseError as e:
            print("{0}".format(e))
            continue

        num = 0 if forest is None else Parser.num_combinations(forest)

        print("Parsed in {0:.4f} seconds, {1} combinations".format(t1 - t0, num))

        Parser.print_parse_forest(forest, detailed = False)


if __name__ == "__main__":

    # Read the configuration settings file

    try:
        Settings.read("Reynir.conf")
    except ConfigError as e:
        print("Configuration error: {0}".format(e))
        quit()

    # Run the tests

    # test1()

    # test2()

    test3()
