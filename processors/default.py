#!/usr/bin/env python
"""
    Reynir: Natural language processing for Icelandic

    Default tree processor module

    Copyright (c) 2015 Vilhjalmur Thorsteinsson
    All rights reserved
    See the accompanying README.md file for further licensing and copyright information.

    This module implements a default processor for parsed sentence trees.

    The processor consists of a set of functions, each having the base name (without
    variants) of a nonterminal in the Reynir context-free grammar. These functions
    will be invoked in turn during a depth-first traversal of the tree. The functions
    are called with three parameters:

    * node, which is the tree node corresponding to the function name. node.nt is
      the original nonterminal name being matched, with variants.
    * params, which is a list of positional parameters, where each is a dictionary
      of results from child nodes in the tree
    * result, which is a dictionary of result values from this nonterminal node.
      The dictionary comes with the attribute/key "_text" that contains
      a string with the combined text of the child nodes, and the attribute/key
      "_root" that yields a string with the lemmas (canonical word forms)
      of that text.

    This particular processor collects information about persons and their titles,
    and abbreviations and their meanings.

    TODO:

    Reassign prepositions that probably don't belong with names
        * Retain 'á'+þgf ('fulltrúi á loftslagsráðstefnunni')
        * Retain 'í'+þgf ('félagi í samtökunum')
        * Retain 'við'+þf ('dósent við Kaupmannahafnarháskóla')

"""

from datetime import datetime
from scraperdb import Person


MODULE_NAME = __name__

def article_begin(state):
    """ Called at the beginning of article processing """

    session = state["session"] # Database session
    url = state["url"] # URL of the article being processed
    # Delete all existing persons for this article
    session.execute(Person.table().delete().where(Person.article_url == url))
    #persons = session.query(Person).filter_by(article_url = url).all()
    #for person in persons:
    #    session.delete(person)

def article_end(state):
    """ Called at the end of article processing """
    pass

def sentence(state, result):
    """ Called at the end of sentence processing """

    session = state["session"] # Database session
    url = state["url"] # URL of the article being processed

    if "nöfn" in result:
        # Nöfn og titlar fundust í málsgreininni
        for nafn, titill in result.nöfn:
            print("Nafn: '{0}' Titill: '{1}'".format(nafn, titill))
            person = Person(
                article_url = url,
                name = nafn,
                title = titill,
                authority = 1.0,
                timestamp = datetime.utcnow()
            )
            session.add(person)


# Below are functions that have names corresponding to grammar nonterminals.
# They will be called during processing (depth-first) of a complete parsed
# tree for a sentence.


def Manneskja(node, params, result):
    """ Mannsnafn, e.t.v. með titli """
    #print("Mannsnafn: {0}".format(result["_text"]))
    result.mannsnafn = result._nominative
    result.del_attribs("efliður")

def Titill(node, params, result):
    """ Titill á eftir nafni """
    #print("Titill: {0}".format(result["_text"]))
    result.titill = result._nominative

def Ávarp(node, params, result):
    """ Ávarp á undan nafni (herra, frú, séra...) """
    result.ávarp = result._nominative

def EfLiður(node, params, result):
    """ Eignarfallsliður eftir nafnlið """
    result.efliður = result._text
    # Leyfa eignarfallslið að standa óbreyttum í titli
    result._nominative = result._text

def FsLiður(node, params, result):
    """ Forsetningarliður """
    # Leyfa forsetningarlið að standa óbreyttum í titli
    result._nominative = result._text

def NlKjarni(node, params, result):
    """ Skoða mannsnöfn með titlum sem kunna að þurfa viðbót úr eignarfallslið """
    if "_et" in node.nt:
        # Eintala
        mannsnafn = result.get("mannsnafn")
        if mannsnafn:
            ávarp = result.get("ávarp")
            if ávarp:
                # Skera ávarpið framan af mannsnafninu
                mannsnafn = mannsnafn[len(ávarp) + 1:]
            titill = result.get("titill")
            #print("Looking at mannsnafn '{0}' titill '{1}'".format(mannsnafn, titill))
            if titill is None:
                # Enginn titill aftan við nafnið
                titill = ""
            else:
                # Skera titilinn (og eitt stafabil) aftan af mannsnafninu
                mannsnafn = mannsnafn[0 : - 1 - len(titill)]
                # Bæta eignarfallslið aftan á titilinn:
                # 'bankastjóri Seðlabanka Íslands'
                efliður = result.get("efliður")
                #print("After cut, mannsnafn is '{0}' and efliður is '{1}'".format(mannsnafn, efliður))
                if efliður:
                    titill += " " + efliður
                if titill.startswith(", "):
                    titill = titill[2:]
                if titill.endswith(" ,"):
                    titill = titill[0:-2]

            #print("In check, mannsnafn is '{0}' and titill is '{1}'".format(mannsnafn, titill))

            if (" " in mannsnafn) and titill:
                # Bæta nafni og titli við nafnalista
                if "nöfn" not in result:
                    result.nöfn = []
                #print("Appending mannsnafn '{0}' titill '{1}'".format(mannsnafn, titill))
                result.nöfn.append((mannsnafn, titill))

    result.del_attribs(("mannsnafn", "titill", "ávarp", "efliður"))

