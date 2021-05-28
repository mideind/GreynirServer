"""

    Greynir: Natural language processing for Icelandic

    Copyright (C) 2021 Miðeind ehf.

       This program is free software: you can redistribute it and/or modify
       it under the terms of the GNU General Public License as published by
       the Free Software Foundation, either version 3 of the License, or
       (at your option) any later version.
       This program is distributed in the hope that it will be useful,
       but WITHOUT ANY WARRANTY; without even the implied warranty of
       MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
       GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see http://www.gnu.org/licenses/.


    Tests for the tree processors in the processors/ directory

"""

from typing import cast

import os
import sys

from collections import OrderedDict

# Shenanigans to enable Pytest to discover modules in the
# main workspace directory (the parent of /tests)
basepath, _ = os.path.split(os.path.realpath(__file__))
mainpath = os.path.join(basepath, "..")
if mainpath not in sys.path:
    sys.path.insert(0, mainpath)

from reynir import tokenize  # noqa
from reynir.incparser import IncrementalParser  # noqa
from reynir.fastparser import Fast_Parser, ParseForestDumper  # noqa
from tree import Tree, Session  # noqa
from treeutil import TreeUtility  # noqa

import processors.entities as entities  # noqa
import processors.persons as persons  # noqa
import processors.locations as locations  # noqa


class SessionShim:

    """ Shim (wrapper) that fakes an SQLAlchemy session class """

    def __init__(self):
        # Accumulate rows that are added to the session
        self.defs = set()

    def execute(self, command):
        """ Shim out SQLAlchemy execute() calls """
        pass

    def add(self, row):
        """ Shim out SQLAlchemy add() calls """
        self.defs.add((row.name, row.verb, row.definition))

    def check(self, t):
        """Check whether the tuple t is in the defs set, and
        removes it if it is, or raises an exception otherwise"""
        self.defs.remove(t)

    def is_empty(self):
        return not self.defs

    def __contains__(self, t):
        return t in self.defs


def make_tree(text: str) -> Tree:
    """Tokenize and parse text, create tree representation string
    from all the parse trees, return as Tree object."""
    toklist = tokenize(text)
    fp = Fast_Parser(verbose=False)
    ip = IncrementalParser(fp, toklist, verbose=False)
    # Dict of parse trees in string dump format,
    # stored by sentence index (1-based)
    trees = OrderedDict()
    num_sent = 0
    for p in ip.paragraphs():
        for sent in p.sentences():
            num_sent += 1
            num_tokens = len(sent)
            assert sent.parse(), "Sentence does not parse: " + sent.text
            # Obtain a text representation of the parse tree
            token_dicts = TreeUtility.dump_tokens(sent.tokens, sent.tree)
            # Create a verbose text representation of
            # the highest scoring parse tree
            assert sent.tree is not None
            tree = ParseForestDumper.dump_forest(sent.tree, token_dicts=token_dicts)
            # Add information about the sentence tree's score
            # and the number of tokens
            trees[num_sent] = "\n".join(
                ["C{0}".format(sent.score), "L{0}".format(num_tokens), tree]
            )
    # Create a tree representation string out of
    # all the accumulated parse trees
    tree_string = "".join("S{0}\n{1}\n".format(key, val) for key, val in trees.items())

    tree = Tree()
    tree.load(tree_string)
    return tree


def test_entities():
    text = """

       Ég skipti við flugfélagið AirBerlin áður en það varð gjaldþrota.

       Danska byggingavörukeðjan Bygma hefur keypt íslenska
       verslunarfyrirtækið Húsasmiðjuna.

       Bandarísku fjárfestingarsjóðirnir Attestor Capital og Goldman Sachs
       eru hluthafar í Arion banka.

       Fosshótel, stór hótelkeðja, var rekin með tapi í fyrra.
       Lax, stór fiskur af ætt laxfiska, er veiddur í íslenskum ám.
       Silfraður lax, fiskur af ætt laxfiska, er veiddur í íslenskum ám.
       Ég ræddi við fulltrúa Norðuráls (álverksmiðjunnar í Hvalfirði) í gær.
       Ég ræddi við fulltrúa Norðuráls (í Hvalfirði) í gær.

       Primera Air var íslenskt flugfélag.
       Ef veðrið er gott þá fullyrði ég að Primera Air sé danskt flugfélag.

       Villeneuve-Loubet er franskt þorp.

       Það er hægt að fá bragðgóðan ís í ísbúðinni Valdísi úti á Granda.

       Í miðbæ Reykjavíkur er herrafataverslunin Geysir.

       Mér er sagt að Geysir sé hættur að gjósa.

       Geysir er hættur að gjósa.

       Geysir er gamall goshver.

       Fyrirtækið Apple-búðin selur Apple Mac tölvur.
       Fyrirtækið Origo selur IBM tölvur.

       Íslendingar stofnuðu skipafélagið Eimskipafélag Íslands.

    """

    tree = make_tree(text)
    session = SessionShim()
    tree.process(cast(Session, session), entities)

    session.check(("Bygma", "er", "dönsk byggingavörukeðja"))
    session.check(("Húsasmiðjan", "er", "íslenskt verslunarfyrirtæki"))
    session.check(("Goldman Sachs", "er", "bandarískur fjárfestingarsjóður"))
    session.check(("Attestor Capital", "er", "bandarískur fjárfestingarsjóður"))
    session.check(("Primera Air", "var", "íslenskt flugfélag"))
    session.check(("Villeneuve-Loubet", "er", "franskt þorp"))
    session.check(("Valdís", "er", "ísbúð"))
    session.check(("Fosshótel", "var", "rekin með tapi"))
    session.check(("Fosshótel", "er", "stór hótelkeðja"))
    session.check(("Norðurál", "er", "álverksmiðjan í Hvalfirði"))
    session.check(("Lax", "er", "stór fiskur af ætt laxfiska"))
    session.check(("Geysir", "er", "gamall goshver"))
    session.check(("Eimskipafélag Íslands", "er", "skipafélag"))
    session.check(("Origo", "er", "fyrirtæki"))
    session.check(("Apple-búðin", "er", "fyrirtæki"))
    session.check(("AirBerlin", "er", "flugfélag"))

    assert session.is_empty()

    text = """
    Ég segi að Kópavogur (vinalegur staður) og Hafnarfjörður (einstakur bær)
    séu efst á vinsældalistanum.
    Til samanburðar áttu þau nágrannasveitafélög höfuðborgarinnar sem koma þar næst,
    Kópavogur (436 félagslegar íbúðir) og Hafnarfjörður (245 félagslegar íbúðir)
    samtals 681 félagslega íbúð í lok árs 2016.
    """

    tree = make_tree(text)
    session = SessionShim()
    tree.process(cast(Session, session), entities)

    session.check(("Kópavogur", "er", "vinalegur staður"))
    session.check(("Hafnarfjörður", "er", "einstakur bær"))

    # We are inter alia checking that the system is not inferring that
    # Kópavogur is '436 félagslegar íbúðir'.
    assert session.is_empty()


def test_persons():
    text = """

    Katrín Jakobsdóttir forsætisráðherra ávarpaði Alþingi í dag ásamt Helga Hrafni
    þingmanni og Jóni Jónssyni, sérstökum álitsgjafa Sameinuðu þjóðanna.

    Joe Biden (forseti Bandaríkjanna) segir að Albert Bourla, forstjóri
    Pfizer, vilji afhenda um tvo milljarða skammta á næstu 18 mánuðum.

    Nikulás Tesla (1856-1943) var serbneskur uppfinningamaður og eðlisfræðingur.

    """

    # tree = make_tree(text)
    # session = SessionShim()
    # tree.process(cast(Session, session), persons)


def test_locations():
    text = """

    Hans starfaði á Fiskislóð 31. Fiskislóð er úti á Granda í Reykjavík, sem er að
    sjálfsögðu höfuðborg Íslands.   Rússland og Norður-Kórea keppa í glímu á föstudag.
    Liverpool og Manchester eru borgir í Englandi sem stækkuðu á tímum iðnbyltingar.

    Hvannadalshnjúkur í Öræfajökli er hæsti tindur landsins þótt ekki allir viðurkenni
    það, eða sjálfstæði Palestínu. Húsið stóð á sléttunni. Mark Hollendingsins útkljáði
    viðureignina í Svarfaðardal. "Við munum ávallt hafa París," sagði Bogart eitt sinn.

    """

    # tree = make_tree(text)
    # session = SessionShim()
    # tree.process(cast(Session, session), locations)


if __name__ == "__main__":
    test_entities()
    test_persons()
    test_locations()
