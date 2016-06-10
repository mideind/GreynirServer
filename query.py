#!/usr/bin/env python
"""
    Reynir: Natural language processing for Icelandic

    Query module

    Copyright (c) 2016 Vilhjalmur Thorsteinsson
    All rights reserved
    See the accompanying README.md file for further licensing and copyright information.

    This module implements a query processor that operates on queries in the form of parse trees
    and returns the results requested, if the query is valid and understood.

"""

import sys
from datetime import datetime
from contextlib import closing

from settings import Settings
from scraperdb import Person, Entity
from bindb import BIN_Db
from tree import Tree


_THIS_MODULE = sys.modules[__name__] # The module object for this module


def sentence(state, result):
    """ Called when sentence processing is complete """
    q = state["query"]
    if "fyrirtæki" in result:
        q.set_answer(result.fyrirtæki)
    elif "mannsnafn" in result:
        q.set_answer(result.mannsnafn)
    elif "sérnafn" in result:
        # Check the most general result last
        q.set_answer(result.sérnafn)
    else:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")


def NlSérnafn(node, params, result):
    """ Sérnafn, stutt eða langt """
    result.sérnafn = result._nominative

def Fyrirtæki(node, params, result):
    """ Fyrirtækisnafn, þ.e. sérnafn + ehf./hf./Inc. o.s.frv. """
    result.fyrirtæki = result._nominative

def Mannsnafn(node, params, result):
    """ Hreint mannsnafn """
    #print("Mannsnafn: {0}".format(result["_text"]))
    result.mannsnafn = result._nominative

def Málsgrein(node, params, result):
    result.del_attribs(("mannsnafn", "sérnafn", "fyrirtæki"))

def Grein(node, params, result):
    result.del_attribs(("mannsnafn", "sérnafn", "fyrirtæki"))

def SetningÁnF(node, params, result):
    result.del_attribs(("mannsnafn", "sérnafn", "fyrirtæki"))

def Lokatákn(node, params, result):
    result._nominative = ""


class Query:

    def __init__(self, session):
        self._session = session
        self._error = None
        self._answer = None

    def execute(self, tree_string):
        """ Execute the query in the given parsed tree and return True if successful """
        self._error = None
        qp = _THIS_MODULE # The processor is this module itself

        tree = Tree()
        print("Tree is:\n{0}".format(tree_string))

        tree.load(tree_string)

        with closing(BIN_Db.get_db()) as bin_db:

            state = { "session": self._session, "processor": qp, "bin_db": bin_db, "query": self }
            tree.process_sentence(state, tree[1]) # Process the first and only sentence within the tree

        return self._error is None

    def set_answer(self, answer):
        self._answer = answer

    def set_error(self, error):
        self._error = error

    def answer(self):
        """ Return the query answer """
        return self._answer

    def error(self):
        """ Return the query error, if any """
        return self._error


