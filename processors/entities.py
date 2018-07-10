#!/usr/bin/env python
"""
    Reynir: Natural language processing for Icelandic

    Processor module to extract entity names & definitions

    Copyright (C) 2016 Vilhjálmur Þorsteinsson

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
    and extracts entity names and definitions.

    Example:

    'Danski byggingavörurisinn Bygma keypti Húsasmiðjuna árið 2009' ->
        { entity: 'Bygma', definition: 'danskur byggingavörurisi' }

    'Bygma er danskur byggingavörurisi' ->
        { entity: 'Bygma', definition: 'danskur byggingavörurisi' }

"""

import re
from datetime import datetime

from scraperdb import Entity
from reynir import Abbreviations


MODULE_NAME = __name__

# Avoid chaff
NOT_DEFINITIONS = {
    "við", "ári", "ár", "sæti", "stig", "færi", "var", "varð"
    "fæddur", "fætt", "fædd",
    "spurður", "spurt", "spurð",
    "búinn", "búið", "búin",
    "sá", "sú", "það", "lán", "inna",
    "hjónin", "hjónanna"
}

NOT_ENTITIES = {
    "þeir", "þær", "þau", "sú", "þá", "þar", "þetta", "þessi", "þessu",
    "the", "to", "aðspurð", "aðspurður", "aðstaða", "aðstæður", "aftur",
    "þarna", "því", "þó", "hver", "hverju", "hvers", "ekki"
}


def article_begin(state):
    """ Called at the beginning of article processing """
    session = state["session"] # Database session
    url = state["url"] # URL of the article being processed
    # Delete all existing entities for this article
    session.execute(Entity.table().delete().where(Entity.article_url == url))
    # Create a name mapping dict for the article
    state["names"] = dict() # Last name -> full name


def article_end(state):
    """ Called at the end of article processing """
    pass


def sentence(state, result):
    """ Called at the end of sentence processing """

    if "entities" not in result:
        # Nothing to do
        return

    session = state["session"] # Database session
    url = state["url"] # URL of the article being processed
    authority = state["authority"] # Authority of the article being processed
    names = state["names"] # Mapping of last names to full names

    if "names" in result:
        # Names were found: add to name mapping dict
        for n in result.names:
            a = n.split()
            if len(a) > 2 and a[-2] in names:
                # Delete next-to-last name,
                # i.e. if we now have "Hillary Rodham Clinton", delete "Rodham->Hillary Rodham"
                del names[a[-2]]
            if len(a) > 1:
                # Map "Clinton->Hillary Rodham Clinton"
                names[a[-1]] = n

    # Process potential entities
    for entity, verb, definition in result.entities:

        # Cut off ending punctuation
        while any(entity.endswith(p) for p in (" ,", " .", " :", " !", " ?")):
            entity = entity[:-2]

        # Cut off ending punctuation
        while any(definition.endswith(p) for p in (" ,", " .", " :", " !", " ?")):
            definition = definition[:-2]

        if len(entity) < 2 or len(definition) < 2:
            # Avoid chaff
            continue

        # Cut phrases off the front
        for p in ("sem er ", "jafnframt er "):
            if definition.startswith(p):
                definition = definition[len(p):]
                break

        def def_ok(definition):
            """ Returns True if a definition meets basic sanity criteria """
            if definition.lower() in NOT_DEFINITIONS:
                return False
            # Check for a match with a number string, eventually followed by a % sign
            if re.match(r'-?\d+(\.\d\d\d)*(,\d+)?%?$', definition):
                return False
            return True

        def name_ok(entity):
            """ Returns True if an entity name meets basic sanity criteria """
            if entity.lower() in NOT_ENTITIES or entity in Abbreviations.DICT:
                # Don't redefine abbreviations
                return False
            # Entity names must start with an uppercase letter
            return entity[0].isupper()

        if def_ok(definition) and name_ok(entity):

            if entity in names:
                # Probably the last name of a longer-named entity:
                # define the full name, not the last name
                # (i.e. 'Clinton er forsetaframbjóðandi' ->
                #   'Hillary Rodham Clinton er forsetaframbjóðandi')
                # print("Mapping entity name '{0}' to full name '{1}'".format(entity, names[entity]))
                entity = names[entity]

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


def visit(state, node):
    """ Determine whether to visit a particular node """
    # We don't visit SetningSkilyrði or any of its children
    # because we know any assertions in there are conditional
    return not node.has_nt_base("SetningSkilyrði")


# Below are functions that have names corresponding to grammar nonterminals.
# They will be called during processing (depth-first) of a complete parsed
# tree for a sentence.


def EfLiður(node, params, result):
    """ Ekki láta sérnafn lifa í gegn um eignarfallslið """
    result.del_attribs(('sérnafn', 'sérnafn_nom'))
    # Ekki breyta eignarfallsliðum í nefnifall
    result._nominative = result._text


def NlSérnafnEf(node, params, result):
    # Ekki breyta eignarfallsliðum í nefnifall
    result._nominative = result._text


def OkkarFramhald(node, params, result):
    # Ekki breyta eignarfallsliðum í nefnifall
    # Þetta grípur 'einn okkar', 'hvorugur þeirra'
    result._nominative = result._text


def AtviksliðurEinkunn(node, params, result):
    # Ekki breyta atviksliðum í nefnifall
    result._nominative = result._text


def FsMeðFallstjórn(node, params, result):
    """ Ekki láta sérnafn lifa í gegn um forsetningarlið """
    result.del_attribs(('sérnafn', 'sérnafn_nom'))
    # Ekki breyta forsetningarliðum í nefnifall
    result._nominative = result._text


def TengiliðurMeðKommu(node, params, result):
    """ '...sem Jón í Múla taldi gott fé' - ekki breyta í nefnifall """
    result._nominative = result._text


def SetningÁnF(node, params, result):
    """ Ekki láta sérnafn lifa í gegn um setningu án frumlags """
    result.del_attribs(('sérnafn', 'sérnafn_nom'))


def SetningSo(node, params, result):
    """ Ekki láta sérnafn lifa í gegn um setningu sem hefst á sögn """
    result.del_attribs(('sérnafn', 'sérnafn_nom'))


def Sérnafn(node, params, result):
    """ Sérnafn, stutt eða langt """
    result.sérnafn = result._text
    result.sérnafn_nom = result._nominative
    result.sérnafn_eind_nom = result._nominative
    result.names = { result._nominative }


def Nafn(node, params, result):
    """ Við viljum ekki láta laufið Nafn skilgreina nafn á einingu (entity) """
    result.nafn_flag = True


def SérnafnEðaManneskja(node, params, result):
    """ Sérnafn eða mannsnafn, eða flóknari nafnliður (Nafn) """
    if "nafn_flag" in result:
        # Flóknari nafnliður: notum hann ekki sem nafn á Entity
        result.del_attribs(('sérnafn', 'sérnafn_nom', 'nafn_flag'))
        return
    if "sérnafn" not in result:
        result.sérnafn = result._text
        result.sérnafn_nom = result._nominative
    if "sérnafn_eind_nom" not in result:
        result.sérnafn_eind_nom = result._nominative
    result.eindir = [ result._nominative ] # Listar eru sameinaðir
    result.names = { result._nominative }


def Fyrirtæki(node, params, result):
    """ Fyrirtækisnafn, þ.e. sérnafn + ehf./hf./Inc. o.s.frv. """
    result.sérnafn = result._text
    result.sérnafn_nom = result._nominative


def SvigaInnihaldFsRuna(node, params, result):
    """ Svigainnihald sem er bara forsetningarruna er ekki brúklegt sem skilgreining """
    result._text = ""
    result._nominative = ""


def SvigaInnihald(node, params, result):
    if node.has_variant("et"):
        tengiliður = result.find_child(nt_base = "Tilvísunarsetning")
        if tengiliður:
            # '...sem framleiðir álumgjörina fyrir iPhone'
            tengisetning = tengiliður.find_child(nt_base = "Tengisetning")
            if tengisetning:
                setning_án_f = tengisetning.find_child(nt_base = "BeygingarliðurÁnF")
                if setning_án_f:
                    skilgr = setning_án_f._text
                    # Remove extraneous prefixes
                    for s in ("í dag",):
                        if skilgr.startswith(s + " "):
                            # Skera framan af
                            skilgr = skilgr[len(s) + 1:]
                            break
                    sögn = None
                    for s in ("er", "var", "sé", "hefur verið", "væri", "hefði orðið", "verður"):
                        if skilgr.startswith(s + " "):
                            # Skera framan af
                            sögn = s
                            skilgr = skilgr[len(s) + 1:]
                            break
                    if skilgr:
                        result.sviga_innihald = skilgr
                        if sögn:
                            result.sviga_sögn = sögn
        elif result.find_child(nt_base = "HreinYfirsetning") is not None:
            # Hrein yfirsetning: sleppa því að nota hana
            pass
        elif result.find_child(nt_base = "SvigaInnihaldFsRuna") is not None:
            # Forsetningaruna: sleppa því að nota hana
            pass
        elif result.find_child(nt_base = "SvigaInnihaldNl") is not None:
            # Nafnliður sem passar ekki við fall eða tölu: sleppa því að nota hann
            pass
        else:
            # Nl/fall/tala: OK
            result.sviga_innihald = result._nominative


def NlKjarni(node, params, result):
    result.del_attribs("sérnafn_eind_nom")


def Skst(node, params, result):
    """ Ekki láta 'fyrirtækið Apple-búðin' skila 'Apple er fyrirtæki' """
    result.del_attribs("sérnafn")
    result.del_attribs("sérnafn_nom")


def NlEind(node, params, result):
    """ Ef sérnafn og sviga_innihald eru rétt undir NlEind þá er það skilgreining """

    if len(params) == 2 and params[0].has_nt_base("NlStak") and params[1].has_nt_base("NlSkýring"):
        # Ef skýring fylgir sérnafni þá sleppum við henni
        if "sérnafn" in params[0]:
            result.sérnafn = params[0].sérnafn
            result.sérnafn_nom = params[0].sérnafn_nom
        else:
            # Gæti verið venjulegur nafnliður með upphafsstaf
            sérnafn = params[0]._text
            sérnafn_nom = params[0]._nominative

            # Athuga hvort allir hlutar nafnsins séu með upphafsstaf
            # Ef svo, túlka þá sem sérnafn
            if all(part and part[0].isupper() for part in sérnafn.split()):
                result.sérnafn = sérnafn
                result.sérnafn_nom = sérnafn_nom
                if "sérnafn_eind_nom" not in result:
                    result.sérnafn_eind_nom = sérnafn_nom
            else:
                result.del_attribs(("sérnafn", "sérnafn_nom"))
        # Drop the explanation, if any
        result._nominative = params[0]._nominative
        result._text = params[0]._text

    if "sérnafn_eind_nom" in result and "sviga_innihald" in result:

        entity = result.sérnafn_eind_nom
        definition = result.sviga_innihald
        verb = result.sviga_sögn if "sviga_sögn" in result else "er"

        if definition:

            # Append to result list
            if "entities" not in result:
                result.entities = []

            result.entities.append((entity, verb, definition))

    result.del_attribs(("sviga_innihald", "sérnafn_eind_nom"))


def SamstættFall(node, params, result):
    """ 'Danska byggingavörukeðjan Bygma' """

    assert len(params) >= 2

    if "sérnafn" in params[-1]:
        sérnafn = params[-1].sérnafn
        sérnafn_nom = params[-1].sérnafn_nom
    else:

        # Gæti verið venjulegur nafnliður með upphafsstaf
        sérnafn = params[-1]._text
        sérnafn_nom = params[-1]._nominative

        # Athuga hvort allir hlutar nafnsins séu með upphafsstaf
        # Ef ekki, hætta við
        for part in sérnafn.split():
            if not part or not part[0].isupper():
                return

    # Bæta við nafnamengi
    if "names" in result:
        result.names.add(sérnafn_nom)
    else:
        result.names = { sérnafn_nom }

    # Find the noun terminal parameter
    p_no = result.find_child(t_base = "no")

    if len(params) >= 3 and p_no is params[-3]:
        # An adjective follows the noun ('Lagahöfundurinn góðkunni Jónas Friðrik')
        pp = params[:]
        pp[-2], pp[-3] = pp[-3], pp[-2] # Swap word order
        definition = " ".join(p._indefinite for p in pp[0:-1]) # góðkunnur lagahöfundur
    else:
        definition = " ".join(p._indefinite for p in params[0:-1]) # dönsk byggingavörukeðja

    if node.has_variant("nf"):
        # Nafnliðurinn er í nefnifalli: nota sérnafnið eins og það stendur
        entity = sérnafn
    else:
        # Nafnliðurinn stendur í aukafalli: breytum sérnafninu í nefnifall, ef það tekur beygingu
        # !!! TODO: þetta breytir of mörgu í nefnifall - á aðeins að hafa áhrif á hrein íslensk
        # !!! sérnöfn, þ.e. nafnorð sem finnast í BÍN
        entity = sérnafn_nom

    # Append to result list
    if "entities" not in result:
        result.entities = []

    result.entities.append((entity, "er", definition))


def ÓsamstættFall(node, params, result):
    """ '(Ég versla við) herrafataverslunina Smekkmaður' """
    SamstættFall(node, params, result)


def Skilgreining(node, params, result):
    """ 'bandarísku sjóðirnir' """
    result.skilgreining = result._canonical # bandarískur sjóður


def FyrirbæriMeðGreini(node, params, result):
    if node.has_variant("ft"):
        # Listi af fyrirbærum: 'bandarísku sjóðirnir Autonomy og Eaton Vance'
        if "skilgreining" in result and "eindir" in result:
            if "entities" not in result:
                result.entities = []
            for eind in result.eindir:
                result.entities.append((eind, "er", result.skilgreining))
    result.del_attribs(("skilgreining", "eindir"))


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

        # fsliðir = result.all_children(nt_base = "FsAtv")
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

        # print("Statement: '{0}' {2} '{1}'".format(entity, andlag._text, sagnorð._text))

        # Append to result list
        if "entities" not in result:
            result.entities = []

        result.entities.append((entity, sagnorð._text, andlag._text))

    finally:
        # Ekki senda sérnöfn upp í tréð ef þau hafa ekki verið höndluð nú þegar
        result.del_attribs(('sérnafn', 'sérnafn_nom'))
        result.del_attribs(("skilgreining", "eindir"))

