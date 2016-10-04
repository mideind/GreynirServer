"""

    Reynir: Natural language processing for Icelandic

    Query module

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


    This module implements a query processor that operates on queries in the form of parse trees
    and returns the results requested, if the query is valid and understood.

"""

import sys
from datetime import datetime
from contextlib import closing
from collections import namedtuple, defaultdict

from settings import Settings, changedlocale
from scraperdb import desc, Root, Article, Person, Entity, \
    RelatedWordsQuery, ArticleCountQuery, ArticleListQuery
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

ArticleInfo = namedtuple('ArticleInfo', ['domain', 'uuid', 'heading', 'ts'])


def append_answers(rd, q, prop_func):
    """ Iterate over query results and add them to the result dictionary rd """
    for p in q:
        s = correct_spaces(prop_func(p))
        ai = ArticleInfo(domain = p.domain, uuid = p.id, heading = p.heading, ts = p.timestamp)
        rd[s][ai.uuid] = ai # Add to a dict of UUIDs


def make_response_list(rd):
    """ Create a response list from the result dictionary rd """
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
                    if rj.lower() in ri.lower():
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
            if ri.lower() in rj.lower():
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
    return rl[0:_MAXLEN_ANSWER]


def prepare_response(q, prop_func):
    """ Prepare and return a simple (one-query) response """
    rd = defaultdict(dict)
    append_answers(rd, q, prop_func)
    return make_response_list(rd)


def _query_person_titles(session, name):
    """ Return a list of all titles for a person """
    rd = defaultdict(dict)
    q = session.query(Person.title, Article.id, Article.timestamp, Article.heading, Root.domain) \
        .filter(Person.name == name).filter(Root.visible == True) \
        .join(Article).join(Root) \
        .all()
    # Append titles from the persons table
    append_answers(rd, q, prop_func = lambda x: x.title)
    # Also append definitions from the entities table, if any
    q = session.query(Entity.definition, Article.id, Article.timestamp, Article.heading, Root.domain) \
        .filter(Entity.name == name).filter(Root.visible == True) \
        .join(Article).join(Root) \
        .all()
    append_answers(rd, q, prop_func = lambda x: x.definition)
    return make_response_list(rd)


def _query_article_list(session, name):
    """ Return a list of dicts with information about articles where the given name appears """
    articles = ArticleListQuery.articles(name, limit = _MAXLEN_ANSWER, enclosing_session = session)
    # Each entry is uuid, heading, timestamp (as ISO format string), domain
    # Collapse identical headings and remove empty ones
    adict = { a[1] : dict(uuid = str(a[0]), heading = a[1],
        timestamp = a[2].isoformat()[0:16], domain = a[3]) for a in articles if a[1] }
    return sorted(adict.values(), key = lambda x: x["timestamp"], reverse = True)

def query_person(session, name):
    """ A query for a person by name """
    titles = _query_person_titles(session, name)
    # Now, create a list of articles where this person name appears
    articles = _query_article_list(session, name)
    return dict(titles = titles, articles = articles)


def query_person_title(session, name):
    """ Return the most likely title for a person """
    rl = _query_person_titles(session, name)
    return correct_spaces(rl[0][0]) if rl else ""


def query_title(session, title):
    """ A query for a person by title """
    # !!! Consider doing a LIKE '%title%', not just LIKE 'title%'
    rd = defaultdict(dict)
    title_lc = title.lower() # Query by lowercase title
    q = session.query(Person.name, Article.id, Article.timestamp, Article.heading, Root.domain) \
        .filter(Person.title_lc.like(title_lc + ' %') | (Person.title_lc == title_lc)) \
        .filter(Root.visible == True) \
        .join(Article).join(Root) \
        .all()
    # Append names from the persons table
    append_answers(rd, q, prop_func = lambda x: x.name)
    # Also append definitions from the entities table, if any
    q = session.query(Entity.name, Article.id, Article.timestamp, Article.heading, Root.domain) \
        .filter(Entity.definition == title) \
        .filter(Root.visible == True) \
        .join(Article).join(Root) \
        .all()
    append_answers(rd, q, prop_func = lambda x: x.name)
    return make_response_list(rd)


def _query_entity_titles(session, name):
    """ A query for definitions of an entity by name """
    q = session.query(Entity.verb, Entity.definition, Article.id, Article.timestamp, Article.heading, Root.domain) \
        .filter(Entity.name == name) \
        .filter(Root.visible == True) \
        .join(Article).join(Root) \
        .all()
    return prepare_response(q, prop_func = lambda x: x.definition)


def query_entity(session, name):
    """ A query for an entity by name """
    titles = _query_entity_titles(session, name)
    articles = _query_article_list(session, name)
    return dict(titles = titles, articles = articles)


def query_entity_def(session, name):
    """ Return a single (best) definition of an entity """
    rl = _query_entity_titles(session, name)
    return correct_spaces(rl[0][0]) if rl else ""


def query_company(session, name):
    """ A query for an company in the entities table """
    # Create a query name by cutting off periods at the end
    # (hf. -> hf) and adding a percent pattern match at the end
    qname = name.strip()
    use_like = False
    while qname and qname[-1] == '.':
        qname = qname[:-1]
        use_like = True
    q = session.query(Entity.verb, Entity.definition, Article.id, Article.timestamp, Article.heading, Root.domain) \
        .filter(Root.visible == True) \
        .join(Article).join(Root)
    if use_like:
        q = q.filter(Entity.name.like(qname + '%'))
    else:
        q = q.filter(Entity.name == qname)
    q = q.all()
    return prepare_response(q, prop_func = lambda x: x.definition)


def query_word(session, stem):
    """ A query for words related to the given stem """
    # Count the articles where the stem occurs
    acnt = ArticleCountQuery.count(stem, enclosing_session = session)
    rlist = RelatedWordsQuery.rel(stem, enclosing_session = session) if acnt else []
    # Convert to an easily serializable dict
    # Exclude the original search stem from the result
    return dict(
        rlist = [ dict(stem = rstem, cat = rcat) for rstem, rcat, rcnt in rlist if rstem != stem ],
        acnt = acnt
    )


_QFUNC = {
    "Person" : query_person,
    "Title" : query_title,
    "Entity" : query_entity,
    "Company" : query_company,
    "Word" : query_word
}

def sentence(state, result):
    """ Called when sentence processing is complete """
    q = state["query"]
    if "qtype" in result:
        # Successfully matched a query type
        q.set_qtype(result.qtype)
        q.set_key(result.qkey)
        session = state["session"]
        # Select a query function and exceute it
        qfunc = _QFUNC.get(result.qtype)
        if qfunc is None:
            q.set_answer(result.qtype + ": " + result.qkey)
        else:
            try:
                q.set_answer(qfunc(session, result.qkey))
            except Exception as e:
                q.set_error("E_EXCEPTION: {0}".format(e))
    else:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")


# The following functions correspond to grammar nonterminals (see Reynir.grammar)
# and are called during tree processing (depth-first, i.e. bottom-up navigation)

def QPerson(node, params, result):
    """ Person query """
    result.qtype = "Person"
    if "mannsnafn" in result:
        result.qkey = result.mannsnafn
    elif "sérnafn" in result:
        result.qkey = result.sérnafn
    else:
        assert False

def QCompany(node, params, result):
    result.qtype = "Company"
    result.qkey = result.fyrirtæki

def QEntity(node, params, result):
    result.qtype = "Entity"
    result.qkey = result.sérnafn

def QTitle(node, params, result):
    result.qtype = "Title"
    result.qkey = result.titill

def QWord(node, params, result):
    result.qtype = "Word"
    assert "qkey" in result

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

def QWordNounKey(node, params, result):
    result.qkey = result._canonical

def QWordPersonKey(node, params, result):
    if "mannsnafn" in result:
        result.qkey = result.mannsnafn
    elif "sérnafn" in result:
        result.qkey = result.sérnafn
    else:
        result.qkey = result._nominative

def QWordEntityKey(node, params, result):
    result.qkey = result._nominative

def QWordVerbKey(node, params, result):
    result.qkey = result._root


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
        self._key = None

    
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
        self._key = None

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


    def set_key(self, key):
        """ Set the query key, i.e. the term or string used to execute the query """
        # This is for instance a person name in nominative case
        self._key = key


    def set_error(self, error):
        """ Set an error result """
        self._error = error


    def qtype(self):
        """ Return the query type """
        return self._qtype


    def answer(self):
        """ Return the query answer """
        return self._answer


    def key(self):
        """ Return the query key """
        return self._key


    def error(self):
        """ Return the query error, if any """
        return self._error


