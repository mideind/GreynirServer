#!/usr/bin/env python
"""
    Reynir: Natural language processing for Icelandic

    Processor module to extract entity names & definitions

    Copyright (c) 2016 Vilhjalmur Thorsteinsson
    All rights reserved
    See the accompanying README.md file for further licensing and copyright information.

    This module implements a processor that looks at parsed sentence trees
    and extracts entity names and definitions.

    Example:

    'Danski byggingavörurisinn Bygma keypti Húsasmiðjuna árið 2009' ->
        { entity: 'Bygma', definition: 'danskur byggingavörurisi' }

    'Bygma er danskur byggingavörurisi' ->
        { entity: 'Bygma', definition: 'danskur byggingavörurisi' }

"""

from datetime import datetime
from scraperdb import Entity


MODULE_NAME = __name__

def article_begin(state):
    """ Called at the beginning of article processing """

    session = state["session"] # Database session
    url = state["url"] # URL of the article being processed
    # Delete all existing entities for this article
    session.execute(Entity.table().delete().where(Entity.article_url == url))

def article_end(state):
    """ Called at the end of article processing """
    pass

def sentence(state, result):
    """ Called at the end of sentence processing """

    session = state["session"] # Database session
    url = state["url"] # URL of the article being processed
    authority = state["authority"] # Authority of the article being processed

    if "entities" in result:
        # Entities were found
        for entity, verb, definition in result.entities:

            if len(entity) < 2 or len(definition) < 2:
                # Avoid chaff
                continue

            # Cut off ending punctuation
            while any(definition.endswith(p) for p in (" ,", " .", " :", " !", " ?")):
                definition = definition[:-2]

            print("Entity '{0}' {1} '{2}'".format(entity, verb, definition))

            e = Entity(
                article_url = url,
                name = entity,
                verb = verb,
                definition = definition,
                authority = authority,
                timestamp = datetime.utcnow()
            )
            session.add(e)


# Below are functions that have names corresponding to grammar nonterminals.
# They will be called during processing (depth-first) of a complete parsed
# tree for a sentence.

def EfLiður(node, params, result):
    """ Ekki láta sérnafn lifa í gegn um eignarfallslið """
    result.del_attribs(('sérnafn', 'sérnafn_nom'))


def Sérnafn(node, params, result):
    """ Sérnafn, stutt eða langt """
    result.sérnafn = result._text
    result.sérnafn_nom = result._nominative


def Fyrirtæki(node, params, result):
    """ Fyrirtækisnafn, þ.e. sérnafn + ehf./hf./Inc. o.s.frv. """
    result.sérnafn = result._text
    result.sérnafn_nom = result._nominative


def SamstættFall(node, params, result):
    """ 'Danska byggingavörukeðjan Bygma' """

    assert len(params) == 2

    if "sérnafn" in params[1]:
        sérnafn = params[1].sérnafn
        sérnafn_nom = params[1].sérnafn_nom
    else:

        # Gæti verið venjulegur nafnliður með upphafsstaf
        sérnafn = params[1]._text
        sérnafn_nom = params[1]._nominative

        # Athuga hvort allir hlutar nafnsins séu með upphafsstaf
        # Ef ekki, hætta við
        for part in sérnafn.split():
            if not part or not part[0].isupper():
                return

    definition = params[0]._indefinite # byggingavörukeðja

    if node.has_variant("nf"):
        # Nafnliðurinn er í nefnifalli: nota sérnafnið eins og það stendur
        entity = sérnafn
    else:
        # Nafnliðurinn stendur í aukafalli: breytum sérnafninu í nefnifall, ef það tekur beygingu
        # !!! TODO: þetta breytir of mörgu í nefnifall - á aðeins að hafa áhrif á hrein íslensk
        # !!! sérnöfn, þ.e. nafnorð sem finnast í BÍN
        entity = sérnafn_nom

    print("Definite: '{0}' er '{1}'".format(entity, definition))

    # Append to result list
    if "entities" not in result:
        result.entities = []

    result.entities.append((entity, "er", definition))


def ÓsamstættFall(node, params, result):
    """ '(Ég versla við) herrafataverslunina Smekkmaður' """

    SamstættFall(node, params, result)


def Setning(node, params, result):
    """ Meðhöndla setningar á forminu 'sérnafn fsliðir* er-sögn eitthvað' """

    try:

        frumlag = result.find_child(nt_base = "Nl", variant = "nf")
        if not frumlag:
            return

        #print("Frumlag er {0}".format(frumlag._text))

        entity = frumlag.get("sérnafn")

        if not entity:
            return

        # print("Entity er {0}".format(entity))

        fsliðir = result.all_children(nt_base = "FsAtv")
        sagnruna = result.find_child(nt_base = "SagnRuna")

        if not sagnruna:
            return

        # print("Sagnruna er {0}".format(sagnruna._text))

        sögn = sagnruna.find_descendant(nt_base = "Sögn", variant = "1")

        if not sögn:
            return

        sagnorð = sögn.find_descendant(t_base = "so")

        #print("Sagnorð er {0}".format(sagnorð._text))

        if not sagnorð or sagnorð._text not in { "er", "var", "sé" }:
            return

        andlag = sögn.find_child(nt_base = "Nl", variant = "nf")

        if not andlag:
            return

        #print("Andlag er {0}".format(andlag._text))

        print("Statement: '{0}' {2} '{1}'".format(entity, andlag._text, sagnorð._text))

        # Append to result list
        if "entities" not in result:
            result.entities = []

        result.entities.append((entity, sagnorð._text, andlag._text))

    finally:
        # Ekki senda sérnöfn upp í tréð ef þau hafa ekki verið höndluð nú þegar
        result.del_attribs(('sérnafn', 'sérnafn_nom'))

