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
from collections import defaultdict

from settings import Settings
from scraperdb import Person, Entity
from bindb import BIN_Db
from tree import Tree
from tokenizer import TOK, correct_spaces
from fastparser import Fast_Parser, ParseForestDumper, ParseError
from reducer import Reducer

_THIS_MODULE = sys.modules[__name__] # The module object for this module

_MAXLEN_ANSWER = 25 # Maximum number of top answers to send in response to queries

def response_list(q, prop_func):
    """ Create a response list from the result of a query q """
    rd = defaultdict(int)
    for p in q:
        s = correct_spaces(prop_func(p))
        rd[s] += 1

    # Now we have a dictionary of distinct results, along with their count

    # Go through the results and delete later ones
    # that are contained within earlier ones
    rl = list(rd.keys())
    for i in range(len(rl) - 1):
        ri = rl[i]
        if ri is not None:
            for j in range(i + 1, len(rl)):
                rj = rl[j]
                if rj is not None:
                    if rj in ri:
                        rd[ri] += rd[rj]
                        del rd[rj]
                        rl[j] = None

    # Go again through the results and delete earlier ones
    # that are contained within later ones
    rl = list(rd.keys())
    for i in range(len(rl) - 1):
        ri = rl[i]
        for j in range(i + 1, len(rl)):
            rj = rl[j]
            if ri in rj:
                rd[rj] += rd[ri]
                del rd[ri]
                break

    rl = sorted([(s, cnt) for s, cnt in rd.items()], key = lambda x: -x[1])

    # If we have 4 or more titles/definitions with more than one occurrence,
    # cut off those that have only one instance
    CUTOFF_AFTER = 3
    if len(rl) > CUTOFF_AFTER and rl[CUTOFF_AFTER][1] > 1:
        rl = [ x for x in rl if x[1] > 1]
    return rl

def response_list_names(q, prop_func):
    """ Create a name list from the result of a query q """
    rd = defaultdict(int)
    for p in q:
        s = correct_spaces(prop_func(p))
        rd[s] += 1
    return sorted([(s, cnt) for s, cnt in rd.items()], key = lambda x: (-x[1], x[0]))

def query_person(session, name):
    """ A query for a person by name """
    q = session.query(Person.title).filter_by(name = name).all()
    return response_list(q, lambda x: x.title)

def query_title(session, title):
    """ A query for a person by title """
    # !!! Consider doing a LIKE '%title%', not just LIKE 'title%'
    q = session.query(Person.name).filter(Person.title.like(title + '%')).all()
    return response_list_names(q, lambda x: x.name)

def query_entity(session, name):
    """ A query for an entity by name """
    print("query_entity: name is '{0}'".format(name))
    q = session.query(Entity.verb, Entity.definition).filter_by(name = name).all()
    return response_list(q, lambda x: x.definition)

def query_company(session, name):
    """ A query for an company in the entities table """
    # Create a query name by cutting off periods at the end
    # (hf. -> hf) and adding a percent pattern match at the end
    qname = name
    while qname.endswith('.'):
        qname = qname[:-1]
    qname += '%'
    print("query_company: qname is '{0}'".format(qname))
    q = session.query(Entity.verb, Entity.definition).filter(Entity.name.like(qname)).all()
    return response_list(q, lambda x: x.definition)

def sentence(state, result):
    """ Called when sentence processing is complete """
    q = state["query"]
    if "qtype" in result:
        # Successfully matched a query type
        q.set_qtype(result.qtype)
        session = state["session"]
        if result.qtype == "Person":
            q.set_answer(query_person(session, result.qkey)[0:_MAXLEN_ANSWER])
        elif result.qtype == "Entity":
            q.set_answer(query_entity(session, result.qkey)[0:_MAXLEN_ANSWER])
        elif result.qtype == "Company":
            q.set_answer(query_company(session, result.qkey)[0:_MAXLEN_ANSWER])
        elif result.qtype == "Title":
            q.set_answer(query_title(session, result.qkey)[0:_MAXLEN_ANSWER])
        else:
            q.set_answer(result.qtype + ": " + result.qkey)
    else:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")


def QPerson(node, params, result):
    """ Person query """
    result.qtype = "Person"
    result.qkey = result.mannsnafn

def QCompany(node, params, result):
    result.qtype = "Company"
    result.qkey = result.fyrirtæki

def QEntity(node, params, result):
    result.qtype = "Entity"
    result.qkey = result.sérnafn

def QTitle(node, params, result):
    result.qtype = "Title"
    result.qkey = result.titill

def Sérnafn(node, params, result):
    """ Sérnafn, stutt eða langt """
    result.sérnafn = result._nominative

def Fyrirtæki(node, params, result):
    """ Fyrirtækisnafn, þ.e. sérnafn + ehf./hf./Inc. o.s.frv. """
    result.fyrirtæki = result._nominative

def Mannsnafn(node, params, result):
    """ Hreint mannsnafn """
    #print("Mannsnafn: {0}".format(result["_text"]))
    result.mannsnafn = result._nominative

def EfLiður(node, params, result):
    result._nominative = result._text

def FsMeðFallstjórn(node, params, result):
    result._nominative = result._text

def QTitleKey(node, params, result):
    """ Titill """
    result.titill = result._nominative
    print("QTitleKey: set result.titill to {0}".format(result.titill))


class Query:

    def __init__(self, session):
        self._session = session
        self._error = None
        self._answer = None
        self._tree = None
        self._qtype = None

    @staticmethod
    def _parse(toklist):
        """ Parse a token list as a query """

        with Fast_Parser(verbose = False, root = 'QueryRoot') as bp: # Don't emit diagnostic messages

            sent_begin = 0
            num_sent = 0
            num_parsed_sent = 0
            rdc = Reducer(bp.grammar)
            trees = dict()
            sent = []

            for ix, t in enumerate(toklist):
                if t[0] == TOK.S_BEGIN:
                    num_sent += 1
                    sent = []
                    sent_begin = ix
                elif t[0] == TOK.S_END:
                    slen = len(sent)
                    # Parse the accumulated sentence
                    num = 0
                    try:
                        # Parse the sentence
                        forest = bp.go(sent)
                        if forest is not None:
                            num = Fast_Parser.num_combinations(forest)
                            if num > 0:
                                # Reduce the resulting forest
                                forest = rdc.go(forest)
                    except ParseError as e:
                        forest = None
                    if num > 0:
                        num_parsed_sent += 1
                        # Obtain a text representation of the parse tree
                        trees[num_sent] = ParseForestDumper.dump_forest(forest)

                elif t[0] == TOK.P_BEGIN:
                    pass
                elif t[0] == TOK.P_END:
                    pass
                else:
                    sent.append(t)

        result = dict(num_sent = num_sent, num_parsed_sent = num_parsed_sent)
        return result, trees


    def parse(self, toklist, result):
        """ Parse the token list as a query, returning True if valid """

        self._tree = None # Erase previous tree, if any
        self._error = None # Erase previous error, if any
        self._qtype = None

        parse_result, trees = Query._parse(toklist)

        if not trees:
            # No parse at all
            self._error = "E_NO_TREES"
            return False

        result.update(parse_result)

        if result["num_sent"] != 1:
            # Queries must be one sentence
            self._error = "E_MULTIPLE_SENTENCES"
            return False
        if result["num_parsed_sent"] != 1:
            # Unable to parse the single sentence
            self._error = "E_NO_PARSE"
            return False
        if 1 not in trees:
            # No sentence number 1
            self._error = "E_NO_FIRST_SENTENCE"
            return False
        # Looks good
        # Store the resulting parsed query as a tree
        tree_string = "S1\n" + trees[1]
        self._tree = Tree()
        self._tree.load(tree_string)
        return True


    def execute(self):
        """ Execute the query in the given parsed tree and return True if successful """
        if self._tree is None:
            self._error = "E_QUERY_NOT_PARSED"
            return False

        self._error = None
        self._qtype = None
        with closing(BIN_Db.get_db()) as bin_db:

            state = { "session": self._session, "processor": _THIS_MODULE, "bin_db": bin_db, "query": self }
            # Process the first and only sentence within the tree
            self._tree.process_sentence(state, self._tree[1])

        return self._error is None

    def set_qtype(self, qtype):
        self._qtype = qtype

    def set_answer(self, answer):
        self._answer = answer

    def set_error(self, error):
        self._error = error

    def qtype(self):
        """ Return the query type """
        return self._qtype

    def answer(self):
        """ Return the query answer """
        return self._answer

    def error(self):
        """ Return the query error, if any """
        return self._error


