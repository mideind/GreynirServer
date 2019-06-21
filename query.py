"""

    Reynir: Natural language processing for Icelandic

    Query module

    Copyright (C) 2019 Miðeind ehf.
    Original author: Vilhjálmur Þorsteinsson

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


    This module implements a query processor that operates on queries
    in the form of parse trees and returns the results requested,
    if the query is valid and understood.

"""

import sys
import math
import importlib
from datetime import datetime
from collections import defaultdict

from settings import Settings

from db import SessionContext
from db.models import Article, Person, Entity, Root
from db.queries import RelatedWordsQuery, ArticleCountQuery, ArticleListQuery

from tree import Tree
from treeutil import TreeUtility
from reynir import TOK, tokenize, correct_spaces
from reynir.bintokenizer import stems_of_token
from reynir.fastparser import (
    Fast_Parser,
    ParseForestDumper,
    ParseError,
)
from reynir.binparser import BIN_Grammar
from reynir.reducer import Reducer
from nertokenizer import recognize_entities
from search import Search
from images import get_image_url
from processor import modules_in_dir


# The module object for this module
_THIS_MODULE = sys.modules[__name__]
# The grammar root nonterminal for queries; see Reynir.grammar
_QUERY_ROOT = "QueryRoot"
# Maximum number of top answers to send in response to queries
_MAXLEN_ANSWER = 20
# Maximum number of article search responses
_MAXLEN_SEARCH = 20
# If we have 5 or more titles/definitions with more than one associated URL,
# cut off those that have only one source URL
_CUTOFF_AFTER = 4
# Maximum number of URL sources so provide for each top answer
_MAX_URLS = 5
# Maximum number of identical mentions of a title or entity description
# that we consider when scoring the mentions
_MAX_MENTIONS = 5


def append_answers(rd, q, prop_func):
    """ Iterate over query results and add them to the result dictionary rd """
    for p in q:
        s = correct_spaces(prop_func(p))
        ai = dict(
            domain=p.domain,
            uuid=p.id,
            heading=p.heading,
            timestamp=p.timestamp,
            ts=p.timestamp.isoformat()[0:16],
            url=p.url,
        )
        rd[s][p.id] = ai  # Add to a dict of UUIDs


def name_key_to_update(register, name):
    """ Return the name register dictionary key to update with data about
        the given person name. This may be an existing key within the
        dictionary, the given key, or None if no update should happen. """

    if name in register:
        # The exact same name is already there: update it as-is
        return name
    # Look for alternative forms of the same name
    # These are all the same person, respectively:
    # Dagur Bergþóruson Eggertsson  / Lilja Dögg Alfreðsdóttir
    # Dagur B. Eggertsson           / Lilja D. Alfreðsdóttir
    # Dagur B Eggertsson            / Lilja D Alfreðsdóttir
    # Dagur Eggertsson              / Lilja Alfreðsdóttir
    nparts = name.split()
    mn = nparts[1:-1]  # Middle names
    # Check whether the same person is already in the registry under a
    # slightly different name
    for k in register.keys():

        parts = k.split()
        if nparts[0] != parts[0] or nparts[-1] != parts[-1]:
            # First or last names different: we don't think these are the same person
            # !!! TODO: Could add Levenshtein distance calculation here
            continue

        # Same first and last names
        # If the name to be added contains no middle name, it is judged to be
        # already in the register and nothing more needs to be done
        if not mn:
            return k  # We can just update the key that was already there
        mp = parts[1:-1]  # Middle names
        if not mp:
            # The new name has a middle name which the old one didn't:
            # Assume its the same person but modify the registry key
            assert name != k
            register[name] = register[k]
            del register[k]
            return name  # No update necessary

        # Both have middle names

        def has_correspondence(n, nlist):
            """ Return True if the middle name or abbreviation n can
                correspond to any middle name or abbreviation in nlist """
            if n.endswith("."):
                n = n[:-1]
            for m in nlist:
                if m.endswith("."):
                    m = m[:-1]
                if n == m:
                    return True
                if n.startswith(m) or m.startswith(n):
                    return True
            # Found no correspondence between n and nlist
            return False

        c_n_p = [has_correspondence(n, mp) for n in mn]
        c_p_n = [has_correspondence(n, mn) for n in mp]
        if all(c_n_p) or all(c_p_n):
            # For at least one direction a->b or b->a,
            # all middle names that occur have correspondences
            if len(mn) > len(mp):
                # The new name is more specific than the old one:
                # Assign the more specific name to the registry key
                register[name] = register[k]
                del register[k]
                return name
            # Return the existing key
            return k

        # There is a non-correspondence between the middle names,
        # so this does not look like it's the same person.
        # Continue searching...

    # An identical or corresponding name was not found:
    # update the name key
    return name


def append_names(rd, q, prop_func):
    """ Iterate over query results and add them to the result dictionary rd,
        assuming that the key is a person name """
    for p in q:
        s = correct_spaces(prop_func(p))
        ai = dict(
            domain=p.domain,
            uuid=p.id,
            heading=p.heading,
            timestamp=p.timestamp,
            ts=p.timestamp.isoformat()[0:16],
            url=p.url,
        )
        # Obtain the key within rd that should be updated with new
        # data. This may be an existing key, a new key or None if no
        # update is to be performed.
        s = name_key_to_update(rd, s)
        if s is not None:
            rd[s][p.id] = ai  # Add to a dict of UUIDs


def make_response_list(rd):
    """ Create a response list from the result dictionary rd """
    # rd is { result: { article_id : article_descriptor } }
    # where article_descriptor is a dict

    # print("\n" + "\n\n".join(str(key) + ": " + str(val) for key, val in rd.items()))

    # We want to rank the results roughly by the following criteria:
    # * Number of mentions
    # * Newer mentions are better than older ones
    # * If a result contains another result, that ranks
    #   as a partial mention of both
    # * Longer results are better than shorter ones

    def contained(needle, haystack):
        """ Return True if whole needles are contained in the haystack """
        return (" " + needle.lower() + " ") in (" " + haystack.lower() + " ")

    def sort_articles(articles):
        """ Sort the individual article URLs so that the newest one appears first """
        return sorted(articles.values(), key=lambda x: x["timestamp"], reverse=True)

    def length_weight(result):
        """ Longer results are better than shorter ones, but only to a point """
        return min(math.e * math.log(len(result)), 10.0)

    now = datetime.utcnow()

    def mention_weight(articles):
        """ Newer mentions are better than older ones """
        w = 0.0
        newest_mentions = sort_articles(articles)[0:_MAX_MENTIONS]
        for a in newest_mentions:
            # Find the age of the article, in whole days
            age = max(0, (now - a["timestamp"]).days)
            # Create an appropriately shaped and sloped age decay function
            div_factor = 1.0 + (math.log(age + 4, 4))
            w += 14.0 / div_factor
        # A single mention is only worth 1/e of a full (multiple) mention
        if len(newest_mentions) == 1:
            return w / math.e
        return w

    scores = dict()
    mention_weights = dict()

    for result, articles in rd.items():
        mw = mention_weights[result] = mention_weight(articles)
        scores[result] = mw + length_weight(result)

    # Give scores for "cross mentions", where one result is contained
    # within another (this promotes both of them). However, the cross
    # mention bonus decays as more crosses are found.
    CROSS_MENTION_FACTOR = 0.20
    # Pay special attention to cases where somebody is said to be "ex" something,
    # i.e. "fyrrverandi"
    EX_MENTION_FACTOR = 0.35

    # Sort the keys by decreasing mention weight
    rl = sorted(rd.keys(), key=lambda x: mention_weights[x], reverse=True)
    len_rl = len(rl)

    def is_ex(s):
        """ Does the given result contain an 'ex' prefix? """
        return any(
            contained(x, s)
            for x in ("fyrrverandi", "fráfarandi", "áður", "þáverandi", "fyrrum")
        )

    # Do a comparison of all pairs in the result list
    for i in range(len_rl - 1):
        ri = rl[i]
        crosses = 0
        ex_i = is_ex(ri)
        for j in range(i + 1, len_rl):
            rj = rl[j]
            if contained(rj, ri) or contained(ri, rj):
                crosses += 1
                # Result rj contains ri or vice versa:
                # Cross-add a part of the respective mention weights
                ex_j = is_ex(rj)
                if ex_i and not ex_j:
                    # We already had "fyrrverandi forseti Íslands" and now we
                    # get "forseti Íslands": reinforce "fyrrverandi forseti Íslands"
                    scores[ri] += mention_weights[rj] * EX_MENTION_FACTOR
                else:
                    scores[rj] += mention_weights[ri] * CROSS_MENTION_FACTOR / crosses
                if ex_j and not ex_i:
                    # We already had "forseti Íslands" and now we
                    # get "fyrrverandi forseti Íslands":
                    # reinforce "fyrrverandi forseti Íslands"
                    scores[rj] += mention_weights[ri] * EX_MENTION_FACTOR
                else:
                    scores[ri] += mention_weights[rj] * CROSS_MENTION_FACTOR / crosses
                if crosses == _MAX_MENTIONS:
                    # Don't bother with more than 5 cross mentions
                    break

    # Sort by decreasing score
    rl = sorted(
        [(s, sort_articles(articles)) for s, articles in rd.items()],
        key=lambda x: scores[x[0]],
        reverse=True,
    )

    # If we have 5 or more titles/definitions with more than one associated URL,
    # cut off those that have only one source URL
    if len(rl) > _CUTOFF_AFTER and len(rl[_CUTOFF_AFTER][1]) > 1:
        rl = [val for val in rl if len(val[1]) > 1]

    # Crop the article url lists down to _MAX_URLS
    return [dict(answer=a[0], sources=a[1][0:_MAX_URLS]) for a in rl[0:_MAXLEN_ANSWER]]


def prepare_response(q, prop_func):
    """ Prepare and return a simple (one-query) response """
    rd = defaultdict(dict)
    append_answers(rd, q, prop_func)
    return make_response_list(rd)


def add_entity_to_register(name, register, session, all_names=False):
    """ Add the entity name and the 'best' definition to the given
        name register dictionary. If all_names is True, we add
        all names that occur even if no title is found. """
    if name in register:
        # Already have a definition for this name
        return
    if " " not in name:
        # Single name: this might be the last name of a person/entity
        # that has already been mentioned by full name
        for k in register.keys():
            parts = k.split()
            if len(parts) > 1 and parts[-1] == name:
                # Reference to the last part of a previously defined
                # multi-part person or entity name,
                # for instance 'Clinton' -> 'Hillary Rodham Clinton'
                register[name] = dict(kind="ref", fullname=k)
                return
        # Not found as-is, but the name ends with an 's':
        # Check again for a possessive version, i.e.
        # 'Steinmeiers' referring to 'Steinmeier',
        # or 'Clintons' referring to 'Clinton'
        if name[-1] == "s":
            name_nominative = name[0:-1]
            for k in register.keys():
                parts = k.split()
                if len(parts) > 1 and parts[-1] == name_nominative:
                    register[name] = dict(kind="ref", fullname=k)
                    return
    # Use the query module to return definitions for an entity
    definition = query_entity_def(session, name)
    if definition:
        register[name] = dict(kind="entity", title=definition)
    elif all_names:
        register[name] = dict(kind="entity", title=None)


def add_name_to_register(name, register, session, all_names=False):
    """ Add the name and the 'best' title to the given name register dictionary """
    if name in register:
        # Already have a title for this exact name; don't bother
        return
    # Use the query module to return titles for a person
    title = query_person_title(session, name)
    name_key = name_key_to_update(register, name)
    if name_key is not None:
        if title:
            register[name_key] = dict(kind="name", title=title)
        elif all_names:
            register[name_key] = dict(kind="name", title=None)


def create_name_register(tokens, session, all_names=False):
    """ Assemble a dictionary of person and entity names
        occurring in the token list """
    register = {}
    for t in tokens:
        if t.kind == TOK.PERSON:
            gn = t.val
            for pn in gn:
                add_name_to_register(pn.name, register, session, all_names=all_names)
        elif t.kind == TOK.ENTITY:
            add_entity_to_register(t.txt, register, session, all_names=all_names)
    return register


def _query_person_titles(session, name):
    """ Return a list of all titles for a person """
    rd = defaultdict(dict)
    q = (
        session.query(
            Person.title,
            Article.id,
            Article.timestamp,
            Article.heading,
            Root.domain,
            Article.url,
        )
        .filter(Person.name == name)
        .filter(Root.visible == True)
        .join(Article, Article.url == Person.article_url)
        .join(Root)
        .order_by(Article.timestamp)
        .all()
    )
    # Append titles from the persons table
    append_answers(rd, q, prop_func=lambda x: x.title)
    # Also append definitions from the entities table, if any
    q = (
        session.query(
            Entity.definition,
            Article.id,
            Article.timestamp,
            Article.heading,
            Root.domain,
            Article.url,
        )
        .filter(Entity.name == name)
        .filter(Root.visible == True)
        .join(Article, Article.url == Entity.article_url)
        .join(Root)
        .order_by(Article.timestamp)
        .all()
    )
    append_answers(rd, q, prop_func=lambda x: x.definition)
    return make_response_list(rd)


def _query_article_list(session, name):
    """ Return a list of dicts with information about articles
        where the given name appears """
    articles = ArticleListQuery.articles(
        name, limit=_MAXLEN_ANSWER, enclosing_session=session
    )
    # Each entry is uuid, heading, timestamp (as ISO format string), domain
    # Collapse identical headings and remove empty ones
    adict = {
        a[1]: dict(
            uuid=str(a[0]),
            heading=a[1],
            ts=a[2].isoformat()[0:16],
            domain=a[3],
            url=a[4],
        )
        for a in articles
        if a[1]
    }
    return sorted(adict.values(), key=lambda x: x["ts"], reverse=True)


def query_person(query, session, name):
    """ A query for a person by name """
    titles = _query_person_titles(session, name)
    # Now, create a list of articles where this person name appears
    articles = _query_article_list(session, name)
    response = dict(answers=titles, sources=articles)
    if titles and "answer" in titles[0]:
        # 'Már Guðmundsson er seðlabankastjóri.'
        voice_answer = name + " er " + titles[0]["answer"] + "."
    else:
        voice_answer = "Ég veit ekki hver " + name + " er."
    return response, voice_answer


def query_person_title(session, name):
    """ Return the most likely title for a person """
    rl = _query_person_titles(session, name)
    return correct_spaces(rl[0]["answer"]) if rl else ""


def query_title(query, session, title):
    """ A query for a person by title """
    # !!! Consider doing a LIKE '%title%', not just LIKE 'title%'
    rd = defaultdict(dict)
    title_lc = title.lower()  # Query by lowercase title
    q = (
        session.query(
            Person.name,
            Article.id,
            Article.timestamp,
            Article.heading,
            Root.domain,
            Article.url,
        )
        .filter(Person.title_lc.like(title_lc + " %") | (Person.title_lc == title_lc))
        .filter(Root.visible == True)
        .join(Article, Article.url == Person.article_url)
        .join(Root)
        .order_by(Article.timestamp)
        .all()
    )
    # Append names from the persons table
    append_names(rd, q, prop_func=lambda x: x.name)
    # Also append definitions from the entities table, if any
    q = (
        session.query(
            Entity.name,
            Article.id,
            Article.timestamp,
            Article.heading,
            Root.domain,
            Article.url,
        )
        .filter(Entity.definition == title)
        .filter(Root.visible == True)
        .join(Article, Article.url == Entity.article_url)
        .join(Root)
        .order_by(Article.timestamp)
        .all()
    )
    append_names(rd, q, prop_func=lambda x: x.name)
    response = make_response_list(rd)
    if response and title and "answer" in response[0]:
        # Return 'Seðlabankastjóri er Már Guðmundsson.'
        upper_title = title[0].upper() + title[1:]
        voice_answer = upper_title + " er " + response[0]["answer"] + "."
    else:
        voice_answer = "Ég veit ekki hver er " + title + "."
    return response, voice_answer


def _query_entity_definitions(session, name):
    """ A query for definitions of an entity by name """
    q = (
        session.query(
            Entity.verb,
            Entity.definition,
            Article.id,
            Article.timestamp,
            Article.heading,
            Root.domain,
            Article.url,
        )
        .filter(Entity.name == name)
        .filter(Root.visible == True)
        .join(Article, Article.url == Entity.article_url)
        .join(Root)
        .order_by(Article.timestamp)
        .all()
    )
    return prepare_response(q, prop_func=lambda x: x.definition)


def query_entity(query, session, name):
    """ A query for an entity by name """
    titles = _query_entity_definitions(session, name)
    articles = _query_article_list(session, name)
    response = dict(answers=titles, sources=articles)
    if titles and "answer" in titles[0]:
        # 'Mál og menning er bókmenntafélag.'
        voice_answer = name + " er " + titles[0]["answer"] + "."
    else:
        voice_answer = "Ég veit ekki hvað " + name + " er."
    return response, voice_answer


def query_entity_def(session, name):
    """ Return a single (best) definition of an entity """
    rl = _query_entity_definitions(session, name)
    return correct_spaces(rl[0]["answer"]) if rl else ""


def query_company(query, session, name):
    """ A query for an company in the entities table """
    # Create a query name by cutting off periods at the end
    # (hf. -> hf) and adding a percent pattern match at the end
    qname = name.strip()
    while qname and qname[-1] == ".":
        qname = qname[:-1]
    q = (
        session.query(
            Entity.verb,
            Entity.definition,
            Article.id,
            Article.timestamp,
            Article.heading,
            Root.domain,
            Article.url,
        )
        .filter(Root.visible == True)
        .join(Article, Article.url == Entity.article_url)
        .join(Root)
        .order_by(Article.timestamp)
    )
    q = q.filter(Entity.name.like(qname + "%"))
    q = q.all()
    response = prepare_response(q, prop_func=lambda x: x.definition)
    if response and response[0]["answer"]:
        voice_answer = name + " er " + response[0]["answer"] + "."
    else:
        voice_answer = "Ég veit ekki hvað " + name + " er."
    return response, voice_answer


def query_word(query, session, stem):
    """ A query for words related to the given stem """
    # Count the articles where the stem occurs
    acnt = ArticleCountQuery.count(stem, enclosing_session=session)
    rlist = RelatedWordsQuery.rel(stem, enclosing_session=session) if acnt else []
    # Convert to an easily serializable dict
    # Exclude the original search stem from the result
    return dict(
        count=acnt,
        answers=[
            dict(stem=rstem, cat=rcat) for rstem, rcat, rcnt in rlist if rstem != stem
        ],
    )


def launch_search(query, session, qkey):
    """ Launch a search with the given search terms """
    pgs, stats = TreeUtility.raw_tag_toklist(
        session, query.token_list(), root=_QUERY_ROOT
    )

    # Collect the list of search terms
    terms = []
    tweights = []
    fixups = []
    for pg in pgs:
        for sent in pg:
            for t in sent:
                # Obtain search stems for the tokens.
                d = dict(x=t["x"], w=0.0)
                tweights.append(d)
                # The terms are represented as (stem, category) tuples.
                stems = stems_of_token(t)
                if stems:
                    terms.extend(stems)
                    fixups.append((d, len(stems)))

    assert sum(n for _, n in fixups) == len(terms)

    if Settings.DEBUG:
        print("Terms are:\n   {0}".format(terms))

    # Launch the search and return the answers, as well as the
    # search terms augmented with information about
    # whether and how they were used
    result = Search.list_similar_to_terms(session, terms, _MAXLEN_SEARCH)

    if "weights" not in result or not result["weights"]:
        # Probably unable to connect to the similarity server
        raise RuntimeError("Unable to connect to the similarity server")

    weights = result["weights"]
    assert len(weights) == len(terms)
    # Insert the weights at the proper places in the
    # token weight list
    index = 0
    for d, n in fixups:
        d["w"] = sum(weights[index : index + n]) / n
        index += n
    return dict(answers=result["articles"], weights=tweights)


_QFUNC = {
    "Person": query_person,
    "Title": query_title,
    "Entity": query_entity,
    "Company": query_company,
    "Word": query_word,
    "Search": launch_search,
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
                voice_answer = None
                answer = qfunc(q, session, result.qkey)
                if isinstance(answer, tuple):
                    # We have both a normal and a voice answer
                    answer, voice_answer = answer
                q.set_answer(answer, voice_answer)
            except AssertionError:
                raise
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
    assert "qkey" in result


def QTitle(node, params, result):
    result.qtype = "Title"
    result.qkey = result.titill


def QWord(node, params, result):
    result.qtype = "Word"
    assert "qkey" in result


def QSearch(node, params, result):
    result.qtype = "Search"
    # Return the entire query text as the search key
    result.qkey = result._text


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
    """ Eignarfallsliðir haldast óbreyttir,
        þ.e. þeim á ekki að breyta í nefnifall """
    result._nominative = result._text


def FsMeðFallstjórn(node, params, result):
    """ Forsetningarliðir haldast óbreyttir,
        þ.e. þeim á ekki að breyta í nefnifall """
    result._nominative = result._text


def QEntityKey(node, params, result):
    if "sérnafn" in result:
        result.qkey = result.sérnafn
    else:
        result.qkey = result._nominative


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


class QueryGrammar(BIN_Grammar):

    """ A subclass of BIN_Grammar that causes conditional sections in the
        Reynir.grammar file, demarcated using
        $if(include_queries)...$endif(include_queries),
        to be included in the grammar as it is read and parsed """

    def __init__(self):
        super().__init__()
        # Enable the 'include_queries' condition
        self.set_conditions({"include_queries"})


class QueryParser(Fast_Parser):

    """ A subclass of Fast_Parser, specialized to parse queries """

    _GRAMMAR_BINARY_FILE = Fast_Parser._GRAMMAR_FILE + ".query.bin"

    # Keep a separate grammar class instance and time stamp for
    # QueryParser. This Python sleight-of-hand overrides
    # class attributes that are defined in BIN_Parser, see binparser.py.
    _grammar_ts = None
    _grammar = None
    _grammar_class = QueryGrammar

    # Also keep separate class instances of the C grammar and its timestamp
    _c_grammar = None
    _c_grammar_ts = None

    def __init__(self):
        super().__init__(verbose=False, root=_QUERY_ROOT)


class Query:

    """ A Query is initialized by parsing a query string using QueryRoot as the
        grammar root nonterminal. The Query can then be executed by processing
        the best parse tree using the nonterminal handlers given above, returning a
        result object if successful. """

    _parser = None
    _processors = None

    def __init__(self, session, query, auto_uppercase):
        self._session = session
        self._query = query
        self._auto_uppercase = auto_uppercase
        self._error = None
        self._answer = None
        self._voice_answer = None
        self._tree = None
        self._qtype = None
        self._key = None
        self._toklist = None

    @classmethod
    def init_class(cls):
        """ Initialize singleton data, i.e. the list of query
            processor modules and the query parser instance """
        # Load the query processor modules found in the
        # queries directory
        modnames = modules_in_dir("queries")
        procs = []
        for modname in modnames:
            try:
                m = importlib.import_module(modname)
                procs.append(m)
            except ImportError as e:
                print(
                    "Error importing query processor module {0}: {1}"
                    .format(modname, e)
                )
        cls._processors = procs
        # Initialize a singleton parser instance for queries,
        # with the nonterminal 'QueryRoot' as the grammar root
        cls._parser = QueryParser()

    @staticmethod
    def _parse(toklist):
        """ Parse a token list as a query """
        bp = Query._parser
        num_sent = 0
        num_parsed_sent = 0
        rdc = Reducer(bp.grammar)
        trees = dict()
        sent = []

        for ix, t in enumerate(toklist):
            if t[0] == TOK.S_BEGIN:
                sent = []
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
                except ParseError:
                    forest = None
                if num > 0:
                    num_parsed_sent += 1
                    # Obtain a text representation of the parse tree
                    trees[num_sent] = ParseForestDumper.dump_forest(forest)
                    # ParseForestPrinter.print_forest(forest)

            elif t[0] == TOK.P_BEGIN:
                pass
            elif t[0] == TOK.P_END:
                pass
            else:
                sent.append(t)

        result = dict(num_sent=num_sent, num_parsed_sent=num_parsed_sent)
        return result, trees

    def parse(self, result):
        """ Parse the token list as a query, returning True if valid """
        if Query._parser is None:
            Query.init_class()

        self._tree = None  # Erase previous tree, if any
        self._error = None  # Erase previous error, if any
        self._qtype = None  # Erase previous query type, if any
        self._key = None
        self._toklist = None

        q = self._query
        toklist = tokenize(
            q, auto_uppercase=q.islower() if self._auto_uppercase else False
        )
        toklist = list(recognize_entities(toklist, enclosing_session=self._session))

        actual_q = correct_spaces(" ".join(t.txt for t in toklist if t.txt))

        # if Settings.DEBUG:
        #     # Log the query string as seen by the parser
        #     print("Query is: '{0}'".format(actual_q))

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
        # print("Query tree:\n{0}".format(tree_string))
        self._tree = Tree()
        self._tree.load(tree_string)
        # Store the token list
        self._toklist = toklist
        return True

    def execute_from_plain_text(self):
        """ Attempt to execute a plain text query, without having to parse it """
        if Query._parser is None:
            Query.init_class()
        for processor in self._processors:
            handle_plain_text = getattr(processor, "handle_plain_text", None)
            if handle_plain_text is not None:
                # This processor has a handle_plain_text function:
                # call it
                if handle_plain_text(self):
                    return True
        return False

    def execute_from_tree(self):
        """ Execute the query contained in the previously parsed tree;
            return True if successful """
        if self._tree is None:
            self.set_error("E_QUERY_NOT_PARSED")
            return False
        assert Query._processors is not None
        self._error = None
        self._qtype = None
        # Process the tree, which has only one sentence
        self._tree.process(self._session, _THIS_MODULE, query=self)
        return self._error is None

    @property
    def query(self):
        return self._query
    
    @property
    def query_lower(self):
        return self._query.lower()
    
    def set_qtype(self, qtype):
        """ Set the query type ('Person', 'Title', 'Company', 'Entity'...) """
        self._qtype = qtype

    def set_answer(self, answer, voice_answer=None):
        """ Set the answer to the query """
        self._answer = answer
        self._voice_answer = voice_answer

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

    def answer(self, voice=False):
        """ Return the query answer """
        if voice and self._voice_answer:
            # If asking for a voice version of the answer
            # and we have one, return it
            return self._voice_answer
        return self._answer

    def key(self):
        """ Return the query key """
        return self._key

    def error(self):
        """ Return the query error, if any """
        return self._error


def execute_query(session, query, voice, auto_uppercase):
    """ Check whether the parse tree is describes a query, and if so, execute the query,
        store the query answer in the result dictionary and return True """
    result = dict(q=query)
    q = Query(session, query, auto_uppercase)
    if q.execute_from_plain_text():
        # We are able to handle this from plain text, without parsing:
        # shortcut to a successful, plain response
        result["valid"] = True
        result["response"] = q.answer(voice)
        result["qtype"] = q.qtype()
        return result
    if not q.parse(result):
        # if Settings.DEBUG:
        #     print("Unable to parse query, error {0}".format(q.error()))
        result["error"] = q.error()
        result["valid"] = False
        return result
    if not q.execute_from_tree():
        # This is a query, but its execution failed for some reason: return the error
        # if Settings.DEBUG:
        #     print("Unable to execute query, error {0}".format(q.error()))
        result["error"] = q.error()
        result["valid"] = True
        return result
    # Successful query: return the answer in response
    result["response"] = q.answer(voice)
    # ...and the query type, as a string ('Person', 'Entity', 'Title' etc.)
    result["qtype"] = qt = q.qtype()
    # ...and the key used to retrieve the answer, if any
    result["key"] = q.key()
    if qt == "Person":
        # For a person query, add an image (if available)
        img = get_image_url(q.key(), enclosing_session=session)
        if img is not None:
            result["image"] = dict(
                src=img.src,
                width=img.width,
                height=img.height,
                link=img.link,
                origin=img.origin,
                name=img.name,
            )
    result["valid"] = True
    return result


def process_query(q, voice, auto_uppercase):
    """ Process an incoming natural language query.
        If voice is True, return a voice-friendly string to
        be spoken to the user. If auto_uppercase is True,
        the string probably came from voice input and we
        need to intelligently guess which words in the query
        should be upper case (to the extent that it matters). """

    with SessionContext(commit=True) as session:

        # Try to parse and process as a query
        try:
            result = execute_query(session, q, voice, auto_uppercase)
        except AssertionError:
            raise
        except:
            # result = dict(valid=False)
            raise

    return result
