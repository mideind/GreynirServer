#!/usr/bin/env python
"""
    Reynir: Natural language processing for Icelandic

    Default tree processor module

    Copyright (c) 2016 Vilhjalmur Thorsteinsson
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
      The dictionary comes pre-assigned with the following attributes/keys:

      _text: a string with the combined text of the child nodes
      _root: a string with the lemmas (word roots) of _text
      _nominative: a string with the words of _text in nominative case

      Additionally, the result dictionary contains an amalgamation of
      attributes/keys that were set by child nodes.

    A function can add attributes/keys to the result dictionary, passing them on to
    upper levels in the tree. If multiple children assign to the same attribute/key,
    the parent will receive the leftmost value - except in the case of lists,
    dictionaries and sets, which will be combined into one merged/extended value
    (again with left precedence in the case of dictionaries).

    --------------

    This particular processor collects information about persons and their titles.
    It handles structures such as:

    'Már Guðmundsson seðlabankastjóri segir að krónan sé sterk um þessar mundir.'
    --> name 'Már Guðmundsson', title 'seðlabankastjóri'

    'Jóhanna Dalberg, sölustjóri félagsins, telur ekki ástæðu til að örvænta.'
    --> name 'Jóhanna Dalberg', title 'sölustjóri félagsins'

    'Rætt var við Pál Eiríksson, sem leikur Gunnar á Hlíðarenda.'
    --> name 'Páll Eiríksson', title 'leikur Gunnar á Hlíðarenda'

    'Hetja dagsins var Guðrún Gunnarsdóttir (markvörður norska liðsins Brann) en hún átti stórleik.'
    --> name 'Guðrún Gunnarsdóttir', title 'markvörður norska liðsins Brann'

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

def _add_name(result, mannsnafn, titill):
    """ Add a name to the resulting name list """
    if not titill:
        return False
    if " " not in mannsnafn:
        return False
    if "..." in titill or "[" in titill:
        return False
    # Cut off common endings that don't belong in a title
    for s in ("í tilkynningu", "í fjölmiðlum", "í samtali", "í Kastljósi"):
        if titill.endswith(s):
            titill = titill[:-1 -len(s)]
    if not titill:
        return False
    if "nöfn" not in result:
        result.nöfn = []
    result.nöfn.append((mannsnafn, titill))
    return True

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

def Setning(node, params, result):
    """ Undirsetning: láta standa óbreytta """
    result._nominative = result._text
    result.del_attribs("skýring_nafn")

# Textar sem ekki eru teknir gildir sem skýringar
ekki_skýring = { "myndskeið" }

def NlSkýring(node, params, result):
    """ Skýring nafnliðar (innan sviga eða komma) """

    def cut(s):
        if s.startswith(", ") or s.startswith("( "):
            s = s[2:]
        if s.endswith(" ,") or s.endswith(" )"):
            s = s[:-2]
        return s

    s = cut(result._text)
    if s.startswith("sem "):
        # Jón, sem er heimsmethafi í hástökki,
        s = s[4:]
        if s.startswith("er "):
            s = s[3:]
        elif s.startswith("nú er "):
            s = s[6:]
        elif s.startswith("einnig er "):
            s = s[10:]
        elif s.startswith("ekki er "):
            s = "ekki " + s[8:]
        elif s.startswith("ekki var "):
            s = "var ekki " + s[9:]
        elif s.startswith("verið hefur "):
            s = "hefur verið " + s[12:]
    else:
        # Ég talaði við Jón (heimsmethafa í hástökki)
        s = cut(result._nominative)
        if s.lower() in ekki_skýring:
            s = None

    if s:
        result.skýring = s
        mannsnafn = result.get("mannsnafn")
        if s == mannsnafn:
            # Mannsnafn sem skýring á nafnlið: gæti verið gagnlegt
            result.skýring_nafn = mannsnafn
    # Ekki senda mannsnafn innan úr skýringunni upp tréð
    result.del_attribs("mannsnafn")

def NlEind(node, params, result):
    """ Nafnliðareind """
    mannsnafn = result.get("mannsnafn")
    skýring = result.get("skýring")
    if mannsnafn and skýring:
        # Fullt nafn með skýringu: bæta því við gagnagrunninn
        _add_name(result, mannsnafn, skýring)
        result.del_attribs("skýring")

#def Nl(node, params, result):
#    """ Fiska upp mannsnöfn úr svigaskýringum """
#    mannsnafn = result.get("skýring_nafn")
#    if mannsnafn:
#        print("Nl: mannsnafn úr skýringu er '{0}', allur texti er '{1}'".format(mannsnafn, result._nominative))
#        titill = result._nominative
#        # Skera tákn (sviga/hornklofa/bandstrik/kommur) aftan af
#        # bil + tákn + bil + nafn + bil + tákn
#        titill = titill[:- (3 + 2 + len(mannsnafn))]
#        print("Nl: nafn '{0}', titill '{1}'".format(mannsnafn, titill))
#        result.del_attribs("skýring_nafn")

def NlKjarni(node, params, result):
    """ Skoða mannsnöfn með titlum sem kunna að þurfa viðbót úr eignarfallslið """

    if "_et" in node.nt:
        # Höfum aðeins áhuga á eintölu

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

            if _add_name(result, mannsnafn, titill):
                # Búið að afgreiða þetta nafn
                result.del_attribs("mannsnafn")

        else:
            mannsnafn = result.get("skýring_nafn")
            if mannsnafn:
                #print("NlKjarni: mannsnafn úr skýringu er '{0}', allur texti er '{1}'".format(mannsnafn, result._nominative))
                titill = result._nominative
                # Skera nafnið og tákn (sviga/hornklofa/bandstrik/kommur) aftan af
                rdelim = titill[-2:]
                titill = titill[:-2]
                delims = {
                    " )" : " ( ",
                    " ]" : " [ ",
                    " -" : " - ",
                    " ," : " , "
                }
                ldelim = delims[rdelim]
                titill = titill[0:titill.rfind(ldelim)]
                # print("NlKjarni: nafn '{0}', titill '{1}'".format(mannsnafn, titill))
                _add_name(result, mannsnafn, titill)
                result.del_attribs("skýring_nafn")
                result.del_attribs(("mannsnafn", "skýring"))

    # Leyfa mannsnafni að ferðast áfram upp tréð ef við
    # fundum ekki titil á það hér
    result.del_attribs(("titill", "ávarp", "efliður"))

