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
      The dictionary comes with a preset item with key "_text" that contains
      a string with the combined text of the child nodes.

    This particular processor collects information about persons and their titles,
    and abbreviations and their meanings.

    TODO:

    Canonical (nominative) form of names and titles
    Reassign prepositions that probably don't belong with names
        * Retain 'á'+þgf ('fulltrúi á loftslagsráðstefnunni')
        * Retain 'í'+þgf ('félagi í samtökunum')
        * Retain 'við'+þf ('dósent við Kaupmannahafnarháskóla')

"""

from datetime import datetime
from collections import namedtuple


MODULE_NAME = __name__


def sentence(result):
    """ Called at the end of sentence processing """
    #print("Sentence done, text is '{0}'".format(result["_text"]))
    if "nöfn" in result:
        for nafn, titill in result.nöfn:
            print("Nafn: '{0}' Titill: '{1}'".format(nafn, titill))

def Nl(node, params, result):
    """ Nafnliður """
    if "_nf" in node.nt:
        # Nafnliður í nefnifalli: senda frumlag upp
        result.frumlag = result._text
    else:
        # Ekki senda frumlag upp ef þessi nafnliður er ekki í nefnifalli
        result.del_attribs("frumlag")

def S0(node, params, result):
    """ Rót trés """
    pass
    #print("S0: texti er '{0}'".format(result["_text"]))

def Setning(node, params, result):
    """ Venjuleg setning """
    #print("Setning: frumlag er '{0}'".format(result.get("frumlag")))
    # Ekki senda frumlag upp í ytri setningar, ef einhverjar eru
    result.del_attribs("frumlag")

def SagnRuna(node, params, result):
    """ Sagnruna, þ.e. sögn ásamt andlögum hennar """
    # Ekki senda frumlög upp í gegn um sagnrunur
    result.del_attribs("frumlag")

def SagnliðurMeðF(node, params, result):
    """ Sagnliður með inniföldu frumlagi """
    #print("SagnliðurMeðF: frumlag er '{0}'".format(result.get("frumlag")))
    # Ekki senda frumlag áfram upp úr sagnlið með inniföldu frumlagi
    # (sem er setningarígildi)
    result.del_attribs("frumlag")

def Manneskja(node, params, result):
    """ Mannsnafn, e.t.v. með titli """
    #print("Mannsnafn: {0}".format(result["_text"]))
    result.mannsnafn = result._root
    result.del_attribs("efliður")

def Titill(node, params, result):
    #print("Titill: {0}".format(result["_text"]))
    result.titill = result._root

def EfLiður(node, params, result):
    """ Eignarfallsliður eftir nafnlið """
    result.efliður = result._text
    # Leyfa eignarfallslið að standa óbreyttum í titli
    result._root = result._text

def FsLiður(node, params, result):
    """ Forsetningarliður """
    # Leyfa forsetningarlið að standa óbreyttum í titli
    result._root = result._text

def NlKjarni(node, params, result):
    """ Skoða mannsnöfn með titlum sem kunna að þurfa viðbót úr eignarfallslið """
    if "_et" in node.nt:
        # Eintala
        mannsnafn = result.get("mannsnafn")
        if mannsnafn:
            titill = result.get("titill")
            if titill is None:
                # Enginn titill aftan við nafnið
                titill = ""
            else:
                # Skera titilinn (og eitt stafabil) aftan af mannsnafninu
                mannsnafn = mannsnafn[0 : - 1 - len(titill)]
                # Bæta eignarfallslið aftan á titilinn:
                # 'bankastjóri Seðlabanka Íslands'
                efliður = result.get("efliður")
                if efliður:
                    titill += " " + efliður
                if titill.startswith(", "):
                    titill = titill[2:]
                if titill.endswith(" ,"):
                    titill = titill[0:-2]

            if (" " in mannsnafn) and titill:
                # Bæta nafni og titli við nafnalista
                if "nöfn" not in result:
                    result.nöfn = []
                result.nöfn.append((mannsnafn, titill))

    result.del_attribs(("mannsnafn", "titill", "efliður"))

