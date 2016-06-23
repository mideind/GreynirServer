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
from collections import namedtuple, defaultdict

from settings import Settings, changedlocale
from scraperdb import Root, Article, Person, Entity, desc
from bindb import BIN_Db
from tree import Tree
from tokenizer import TOK, correct_spaces
from fastparser import Fast_Parser, ParseForestDumper, ParseForestPrinter, ParseError
from reducer import Reducer


_THIS_MODULE = sys.modules[__name__] # The module object for this module
_QUERY_ROOT = 'QueryRoot' # The grammar root nonterminal for queries; see Reynir.grammar
_MAXLEN_ANSWER = 25 # Maximum number of top answers to send in response to queries
# If we have 5 or more titles/definitions with more than one associated URL,
# cut off those that have only one source URL
_CUTOFF_AFTER = 4
_MAX_URLS = 5 # Maximum number of URL sources so provide for each top answer

ArticleInfo = namedtuple('ArticleInfo', ['domain', 'url', 'heading', 'ts'])

def response_list(q, prop_func):
    """ Create a response list from the result of a query q """
    rd = defaultdict(dict)
    for p in q:
        s = correct_spaces(prop_func(p))
        ai = ArticleInfo(domain = p.domain, url = p.article_url, heading = p.heading, ts = p.timestamp)
        rd[s][ai.url] = ai # Add to a dict of URLs

    # Now we have a dictionary of distinct results, along with their URLs

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
                        rd[ri].update(rd[rj])
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
                rd[rj].update(rd[ri])
                del rd[ri]
                break

    with changedlocale() as strxfrm:

        def sort_articles(articles):
            """ Sort the individual article URLs so that the newest one appears first """
            return sorted(articles.values(), key = lambda x: x.ts, reverse = True)

        rl = sorted([(s, sort_articles(articles)) for s, articles in rd.items()],
            key = lambda x: (-len(x[1]), strxfrm(x[0]))) # Sort by number of URLs in article dict

    # If we have 5 or more titles/definitions with more than one associated URL,
    # cut off those that have only one source URL
    if len(rl) > _CUTOFF_AFTER and len(rl[_CUTOFF_AFTER][1]) > 1:
        rl = [ val for val in rl if len(val[1]) > 1 ]

    # Crop the article url lists down to _MAX_URLS
    for i, val in enumerate(rl):
        if len(val[1]) > _MAX_URLS:
            rl[i] = (val[0], val[1][0:_MAX_URLS])
    return rl

def response_list_names(q, prop_func):
    """ Create a name list from the result of a query q """
    rd = defaultdict(dict)
    for p in q:
        s = correct_spaces(prop_func(p))
        ai = ArticleInfo(domain = p.domain, url = p.article_url, heading = p.heading, ts = p.timestamp)
        rd[s][ai.url] = ai # Add to a dict of URLs

    with changedlocale() as strxfrm:

        def sort_articles(articles):
            """ Sort the individual article URLs so that the newest one appears first """
            return sorted(articles.values(), key = lambda x: x.ts, reverse = True)

        return sorted([(s, sort_articles(articles)) for s, articles in rd.items()],
            key = lambda x: (-len(x[1]), strxfrm(x[0])))

def query_person(session, name):
    """ A query for a person by name """
    q = session.query(Person.title, Person.article_url, Article.timestamp, Article.heading, Root.domain) \
        .filter(Person.name == name) \
        .join(Article).join(Root) \
        .all()
    return response_list(q, prop_func = lambda x: x.title)

def query_title(session, title):
    """ A query for a person by title """
    # !!! Consider doing a LIKE '%title%', not just LIKE 'title%'
    title_lc = title.lower() # Query by lowercase title
    q = session.query(Person.name, Person.article_url, Article.timestamp, Article.heading, Root.domain) \
        .filter(Person.title_lc.like(title_lc + ' %') | (Person.title_lc == title_lc)) \
        .join(Article).join(Root) \
        .all()
#    return response_list_names(q, prop_func = lambda x: x.name)
    return response_list(q, prop_func = lambda x: x.name)

def query_entity(session, name):
    """ A query for an entity by name """
    q = session.query(Entity.verb, Entity.definition, Entity.article_url, Article.timestamp, Article.heading, Root.domain) \
        .filter(Entity.name == name) \
        .join(Article).join(Root) \
        .all()
    return response_list(q, prop_func = lambda x: x.definition)

def query_company(session, name):
    """ A query for an company in the entities table """
    # Create a query name by cutting off periods at the end
    # (hf. -> hf) and adding a percent pattern match at the end
    qname = name.strip()
    use_like = False
    while qname and qname[-1] == '.':
        qname = qname[:-1]
        use_like = True
    q = session.query(Entity.verb, Entity.definition, Entity.article_url, Article.timestamp, Article.heading, Root.domain) \
        .join(Article).join(Root)
    if use_like:
        q = q.filter(Entity.name.like(qname + '%'))
    else:
        q = q.filter(Entity.name == qname)
    q = q.all()
    return response_list(q, prop_func = lambda x: x.definition)


def sentence(state, result):
    """ Called when sentence processing is complete """
    q = state["query"]
    if "qtype" in result:
        # Successfully matched a query type
        q.set_qtype(result.qtype)
        session = state["session"]
        if result.qtype == "Person":
            # A person was given; his/her titles are returned
            q.set_answer(query_person(session, result.qkey)[0:_MAXLEN_ANSWER])
        elif result.qtype == "Entity":
            # An entity name was given; its definitions are returned
            q.set_answer(query_entity(session, result.qkey)[0:_MAXLEN_ANSWER])
        elif result.qtype == "Company":
            # A company name was given; its definitions (descriptions) are returned
            q.set_answer(query_company(session, result.qkey)[0:_MAXLEN_ANSWER])
        elif result.qtype == "Title":
            # A title was given; persons having that title are returned
            q.set_answer(query_title(session, result.qkey)[0:_MAXLEN_ANSWER])
        else:
            q.set_answer(result.qtype + ": " + result.qkey)
    else:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")


# The following functions correspond to grammar nonterminals (see Reynir.grammar)
# and are called during tree processing (depth-first, i.e. bottom-up navigation)

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
    """ Hreint mannsnafn, þ.e. án ávarps og titils """
    result.mannsnafn = result._nominative

def EfLiður(node, params, result):
    """ Eignarfallsliðir haldast óbreyttir, þ.e. þeim á ekki að breyta í nefnifall """
    result._nominative = result._text

def FsMeðFallstjórn(node, params, result):
    """ Forsetningarliðir haldast óbreyttir, þ.e. þeim á ekki að breyta í nefnifall """
    result._nominative = result._text

def QTitleKey(node, params, result):
    """ Titill """
    result.titill = result._nominative


class Query:

    """ A Query is initialized by parsing a query string using QueryRoot as the
        grammar root nonterminal. The Query can then be executed by processing
        the best parse tree using the nonterminal handlers given above, returning a
        result object if successful. """

    def __init__(self, session):
        self._session = session
        self._error = None
        self._answer = None
        self._tree = None
        self._qtype = None

    
    @staticmethod
    def _parse(toklist):
        """ Parse a token list as a query """

        # Parse with the nonterminal 'QueryRoot' as the grammar root
        with Fast_Parser(verbose = False, root = _QUERY_ROOT) as bp:

            sent_begin = 0
            num_sent = 0
            num_parsed_sent = 0
            rdc = Reducer(bp.grammar)
            trees = dict()
            sent = []

            for ix, t in enumerate(toklist):
                if t[0] == TOK.S_BEGIN:
                    sent = []
                    sent_begin = ix
                elif t[0] == TOK.S_END:
                    slen = len(sent)
                    if not slen:
                        continue
                    num_sent += 1
                    # Parse the accumulated sentence
                    num = 0
                    try:
                        # Parse the sentence
                        forest = bp.go(sent)
                        if forest is not None:
                            num = Fast_Parser.num_combinations(forest)
                            if num > 1:
                                # Reduce the resulting forest
                                forest = rdc.go(forest)
                    except ParseError as e:
                        forest = None
                    if num > 0:
                        num_parsed_sent += 1
                        # Obtain a text representation of the parse tree
                        trees[num_sent] = ParseForestDumper.dump_forest(forest)
                        #ParseForestPrinter.print_forest(forest)

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
        self._qtype = None # Erase previous query type, if any

        parse_result, trees = Query._parse(toklist)

        if not trees:
            # No parse at all
            self.set_error("E_NO_TREES")
            return False

        result.update(parse_result)

        if result["num_sent"] != 1:
            # Queries must be one sentence
            self.set_error("E_MULTIPLE_SENTENCES")
            return False
        if result["num_parsed_sent"] != 1:
            # Unable to parse the single sentence
            self.set_error("E_NO_PARSE")
            return False
        if 1 not in trees:
            # No sentence number 1
            self.set_error("E_NO_FIRST_SENTENCE")
            return False
        # Looks good
        # Store the resulting parsed query as a tree
        tree_string = "S1\n" + trees[1]
        #print("Query tree:\n{0}".format(tree_string))
        self._tree = Tree()
        self._tree.load(tree_string)
        return True


    def execute(self):
        """ Execute the query contained in the previously parsed tree; return True if successful """
        if self._tree is None:
            self.set_error("E_QUERY_NOT_PARSED")
            return False

        self._error = None
        self._qtype = None
        with closing(BIN_Db.get_db()) as bin_db:

            state = { "session": self._session, "processor": _THIS_MODULE, "bin_db": bin_db, "query": self }
            # Process the first and only sentence within the tree
            self._tree.process_sentence(state, self._tree[1])

        return self._error is None

    def set_qtype(self, qtype):
        """ Set the query type ('Person', 'Title', 'Company', 'Entity'...) """
        self._qtype = qtype

    def set_answer(self, answer):
        """ Set the answer to the query """
        self._answer = answer

    def set_error(self, error):
        """ Set an error result """
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


