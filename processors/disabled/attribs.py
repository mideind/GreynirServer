#!/usr/bin/env python
"""
    Greynir: Natural language processing for Icelandic

    Processor module to extract attributes of objects

    Copyright (C) 2023 Miðeind ehf.

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


    This module implements a processor that looks at parsed sentence trees
    and extracts attributes of objects from sentences of the form
    '[attribute] [object in the genitive case] [prepositions*] [is-verb] [attribute value].'

    Examples:
    'Verg landsframleiðsla Íslands árið 2005 var 420 milljarðar króna.' ->
    {
        Object: 'Ísland',
        Attribute: 'Verg landsframleiðsla',
        Qualifiers: ['Árið 2005'],
        Verb: 'Var',
        Value: { text: '420 milljarðar króna', amount: 420e9, currency: 'ISK' }
    }
    'Ályktun Alþingis um aðild að Evrópusambandinu var samþykkt samhljóða.' ->
    {
        Object: 'Alþingi',
        Attribute: 'Ályktun',
        Qualifiers: ['um aðild að Evrópusambandinu'],
        Verb: 'Var',
        Value: { text: 'samþykkt samhljóða' }
    }

"""

from __future__ import annotations

from queries import QueryStateDict
from tree import Node, ParamList, Result, TreeStateDict

# from db import Attribute


MODULE_NAME = __name__
PROCESSOR_TYPE = "tree"


def article_begin(state: TreeStateDict) -> None:
    """Called at the beginning of article processing"""

    # session = state["session"] # Database session
    # url = state["url"] # URL of the article being processed
    # Delete all existing attributes for this article
    # session.execute(Attribute.table().delete().where(Attribute.article_url == url))
    pass


def article_end(state: TreeStateDict) -> None:
    """Called at the end of article processing"""
    pass


def sentence(state: QueryStateDict, result: Result) -> None:
    """Called at the end of sentence processing"""

    # session = state["session"]  # Database session
    # url = state["url"]  # URL of the article being processed

    _ = """
    if "attribs" in result:
        # Attributes were found
        for a in result.attribs:
            # print("Attribute: '{0}'".format(attrib))
            attrib = Attribute(
                article_url = url,
                obj = a.obj,
                attrib = a.attrib,
                qualifiers = a.qualifiers,
                verb = a.verb,
                value = a.value,
                authority = 1.0,
                timestamp = datetime.utcnow()
            )
            session.add(attrib)
    """


# Below are functions that have names corresponding to grammar nonterminals.
# They will be called during processing (depth-first) of a complete parsed
# tree for a sentence.


def FsLiður(node: Node, params: ParamList, result: Result):
    """Ekki breyta forsetningarliðum í nefnifall"""
    result._nominative = result._text
    # Ekki leyfa eignarfallsliðum að lifa í gegn um forsetningarliði á
    # leið upp tréð
    result.del_attribs(("ef_nom", "ef_text"))


def EfLiður(node: Node, params: ParamList, result: Result):
    """Eignarfallsliður eftir nafnlið"""
    result.ef_nom = result._nominative
    result.ef_text = result._text


def Tengiliður(node: Node, params: ParamList, result: Result):
    """Tengiliður ("sem" setning)"""
    result.del_attribs(("ef_nom", "ef_text"))


def SvigaInnihald(node: Node, params: ParamList, result: Result):
    """Tengiliður ("sem" setning)"""
    result.del_attribs(("ef_nom", "ef_text"))


def Setning(node: Node, params: ParamList, result: Result):
    """Meðhöndla setningar á forminu 'eitthvað einhvers fsliðir* er-sögn eitthvað'"""

    # return # !!! TODO - DEBUG

    frumlag = result.find_child(nt_base="Nl", variant="nf")
    if not frumlag:
        return

    # print("Frumlag er {0}".format(frumlag._text))

    einhvers = frumlag.get("ef_nom")

    if not einhvers:
        return

    fsliðir = result.all_children(nt_base="FsAtv")
    sagnruna = result.find_child(nt_base="SagnRuna")

    if not sagnruna:
        return

    # print("Frumlag er '{0}', einhvers er '{1}'".format(frumlag._text, einhvers))
    # print("Sagnruna er '{0}'".format(sagnruna._text))

    sögn = sagnruna.find_descendant(nt_base="Sögn", variant="1")

    if not sögn:
        return

    sagnorð = sögn.find_descendant(t_base="so")

    # if sagnorð:
    #    print("Sagnorð er '{0}'".format(sagnorð._text))

    if not sagnorð or sagnorð._text not in {"er", "eru", "var", "voru", "sé", "séu"}:
        return

    andlag = sögn.find_child(nt_base="Nl", variant="nf")

    if not andlag:
        return

    # print("Andlag er '{0}'".format(andlag._text))

    # Reikna út endanlegt frumlag
    frumlag_text = frumlag._text
    # print("Frumlag_text er '{0}', frumlag.ef_text er '{1}'".format(frumlag_text, frumlag.ef_text))
    frumlag_text = frumlag_text[: -1 - len(frumlag.ef_text)]

    # Halda forsetningarliðum til haga
    qual = ""
    if fsliðir:
        qual = " (" + ", ".join(f._text for f in fsliðir) + ")"

    print(
        "'{0}'->'{1}'{2} {4} '{3}'".format(
            einhvers, frumlag_text, qual, andlag._text, sagnorð._text
        )
    )
