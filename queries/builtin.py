"""

    Greynir: Natural language processing for Icelandic

    Built-in query module

    Copyright (C) 2023 Miðeind ehf.
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


    This module implements a default query processor for builtin queries.
    The processor operates on queries in the form of parse trees and returns
    the results requested, if the query is valid and understood.

"""

from typing import Callable, Dict, Iterable, Optional, List, Any, Tuple, cast
from typing_extensions import TypedDict

import math
from datetime import datetime
from collections import defaultdict
import logging

from sqlalchemy import DateTime

from settings import Settings

from db import desc, OperationalError, Session
from db.models import Article, Person, Entity, Root, Column
from db.sql import RelatedWordsQuery, ArticleCountQuery, ArticleListQuery

from treeutil import TreeUtility
from reynir import TOK, Tok, correct_spaces
from reynir.bintokenizer import stems_of_token
from search import Search
from speech.trans import gssml
from queries import AnswerTuple, Query, ResponseDict, ResponseType, QueryStateDict
from tree import Result, Node
from utility import cap_first, icequote
from queries.util import read_grammar_file


# The type of a name/entity register
RegisterType = Dict[str, Dict[str, Any]]


class TermDict(TypedDict):
    """A dictionary containing a search term and its associated score"""
    x: str
    w: float


# --- Begin "magic" module constants ---

# The following constants - HANDLE_TREE, PRIORITY and GRAMMAR -
# are "magic"; they are read by query.py to determine how to
# integrate this query module into the server's set of active modules.

# Indicate that this module wants to handle parse trees for queries
HANDLE_TREE = True

# Invoke this processor after other tree processors
# (unless they have even lower priority)
PRIORITY = -100

# The grammar nonterminals this module wants to handle
QUERY_NONTERMINALS = {"BuiltinQueries"}

GRAMMAR = read_grammar_file("builtin")

# --- End of "magic" module constants ---

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


def append_answers(
    rd: RegisterType, q: Iterable[Article], prop_func: Callable[[Any], str]
) -> None:
    """Iterate over query results and add them to the result dictionary rd"""
    for p in q:
        s = correct_spaces(prop_func(p))
        ts = p.timestamp or datetime.utcnow()
        ai = dict(
            domain=p.domain,
            uuid=p.id,
            heading=p.heading,
            timestamp=ts,
            ts=ts.isoformat()[0:16],
            url=p.url,
        )
        rd[s][p.id] = ai  # Add to a dict of UUIDs


def name_key_to_update(register: RegisterType, name: str) -> Optional[str]:
    """Return the name register dictionary key to update with data about
    the given person name. This may be an existing key within the
    dictionary, the given key, or None if no update should happen."""

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

        def has_correspondence(n: str, nlist: List[str]) -> bool:
            """Return True if the middle name or abbreviation n can
            correspond to any middle name or abbreviation in nlist"""
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


def append_names(
    rd: RegisterType, q: Iterable[Article], prop_func: Callable[[Any], str]
) -> None:
    """Iterate over query results and add them to the result dictionary rd,
    assuming that the key is a person name"""
    s: Optional[str]
    for p in q:
        s = correct_spaces(prop_func(p))
        ts = p.timestamp or datetime.utcnow()
        ai = dict(
            domain=p.domain,
            uuid=p.id,
            heading=p.heading,
            timestamp=ts,
            ts=ts.isoformat()[0:16],
            url=p.url,
        )
        # Obtain the key within rd that should be updated with new
        # data. This may be an existing key, a new key or None if no
        # update is to be performed.
        s = name_key_to_update(rd, s)
        if s is not None:
            rd[s][p.id] = ai  # Add to a dict of UUIDs


def make_response_list(rd: RegisterType) -> List[Dict[str, Any]]:
    """Create a response list from the result dictionary rd"""
    # rd is { result: { article_id : article_descriptor } }
    # where article_descriptor is a dict

    # We want to rank the results roughly by the following criteria:
    # * Number of mentions
    # * Newer mentions are better than older ones
    # * If a result contains another result, that ranks
    #   as a partial mention of both
    # * Longer results are better than shorter ones

    def contained(needle: str, haystack: str) -> bool:
        """Return True if whole needles are contained in the haystack"""
        return (" " + needle.lower() + " ") in (" " + haystack.lower() + " ")

    def sort_articles(articles: Dict[str, Any]):
        """Sort the individual article URLs so that the newest one appears first"""
        return sorted(articles.values(), key=lambda x: x["timestamp"], reverse=True)

    def length_weight(result: str) -> float:
        """Longer results are better than shorter ones, but only to a point"""
        return min(math.e * math.log(len(result)), 10.0)

    now = datetime.utcnow()

    def mention_weight(articles: Dict[str, Any]) -> float:
        """Newer mentions are better than older ones"""
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

    scores: Dict[str, float] = dict()
    mention_weights: Dict[str, float] = dict()

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

    def is_ex(s: str) -> bool:
        """Does the given result contain an 'ex' prefix?"""
        return any(
            contained(x, s)
            for x in ("fyrrverandi", "fv.", "fráfarandi", "áður", "þáverandi", "fyrrum")
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
    rl_sorted = sorted(
        [(s, sort_articles(articles)) for s, articles in rd.items()],
        key=lambda x: scores[x[0]],
        reverse=True,
    )

    # If we have 5 or more titles/definitions with more than one associated URL,
    # cut off those that have only one source URL
    if len(rl_sorted) > _CUTOFF_AFTER and len(rl_sorted[_CUTOFF_AFTER][1]) > 1:
        rl_sorted = [val for val in rl_sorted if len(val[1]) > 1]

    # Crop the article url lists down to _MAX_URLS
    return [
        dict(answer=a[0], sources=a[1][0:_MAX_URLS])
        for a in rl_sorted[0:_MAXLEN_ANSWER]
    ]


def prepare_response(
    q: Iterable[Article], prop_func: Callable[[Any], str]
) -> List[Dict[str, Any]]:
    """Prepare and return a simple (one-query) response"""
    rd: RegisterType = defaultdict(dict)
    append_answers(rd, q, prop_func)
    return make_response_list(rd)


def add_entity_to_register(
    name: str, register: RegisterType, session: Session, all_names: bool = False
) -> None:
    """Add the entity name and the 'best' definition to the given
    name register dictionary. If all_names is True, we add
    all names that occur even if no title is found."""
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


def add_name_to_register(
    name: str, register: RegisterType, session: Session, all_names: bool = False
) -> None:
    """Add the name and the 'best' title to the given name register dictionary"""
    if name in register:
        # Already have a title for this exact name; don't bother
        return
    # Use the query module to return titles for a person
    title, _ = query_person_title(session, name)
    name_key = name_key_to_update(register, name)
    if name_key is not None:
        if title:
            register[name_key] = dict(kind="name", title=title)
        elif all_names:
            register[name_key] = dict(kind="name", title=None)


def create_name_register(
    tokens: Iterable[Tok], session: Session, all_names: bool = False
) -> RegisterType:
    """Assemble a dictionary of person and entity names
    occurring in the token list"""
    register: RegisterType = {}
    for t in tokens:
        if t.kind == TOK.PERSON:
            for pn in t.person_names:
                add_name_to_register(pn.name, register, session, all_names=all_names)
        elif t.kind == TOK.ENTITY:
            add_entity_to_register(t.txt, register, session, all_names=all_names)
    return register


def _query_person_titles(session: Session, name: str):
    """Return a list of all titles for a person"""
    # This list should never become very long, so we don't
    # apply a limit here
    rd: RegisterType = defaultdict(dict)
    try:
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
    except OperationalError as e:
        logging.warning(f"SQL error in _query_person_titles(): {e}")
        q = []
    # Append titles from the persons table
    append_answers(rd, q, prop_func=lambda x: x.title)
    # Also append definitions from the entities table, if any
    try:
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
    except OperationalError as e:
        logging.warning(f"SQL error in _query_person_titles(): {e}")
        q = []
    append_answers(rd, q, prop_func=lambda x: x.definition)
    return make_response_list(rd)


def _query_article_list(session: Session, name: str):
    """Return a list of dicts with information about articles
    where the given name appears"""
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


def query_person(query: Query, session: Session, name: str) -> AnswerTuple:
    """A query for a person by name"""
    response: Dict[str, Any] = dict(answers=[], sources=[])
    if name in {"hann", "hún", "hán", "það"}:
        # Using a personal pronoun: check whether we can infer
        # the name from the query context, i.e. from a recent query result
        ctx = None if name == "það" else query.fetch_context()
        if ctx and "person_name" in ctx:
            # Yes, success
            name = cast(str, ctx["person_name"])
        else:
            # No - give up
            if name == "hann":
                answer = voice_answer = "Ég veit ekki við hvern þú átt."
            elif name == "hún":
                answer = voice_answer = "Ég veit ekki við hverja þú átt."
            else:
                answer = voice_answer = "Ég veit ekki við hvert þú átt."
            return response, answer, voice_answer
    if query.is_voice:
        # Handle voice query
        if " " not in name:
            # If using voice, do not attempt to answer single-name
            # queries ('Hver er Guðmundur?') since the answers are almost
            # always nonsensical
            query.set_error("E_PERSON_NOT_FOUND")
            return dict(answer=""), "", ""
        # A name with at least two components
        title, source = query_person_title(session, name)
        if not title:
            # Rather than accept this as a voice query
            # for a person that is not found, return an
            # error and thereby give other query handlers
            # a chance to parse this
            query.set_error("E_PERSON_NOT_FOUND")
            return dict(answer=""), "", ""
        answer = title
        voice_answer = (
            f"{gssml(name, type='person')} er {gssml(answer, type='generic')}."
        )
        # Set the context for a subsequent query
        query.set_context({"person_name": name})
        # Set source, if known
        if source is not None:
            query.set_source(source)
        response = dict(answer=answer)
    else:
        # Not voice
        voice_answer = ""
        titles = _query_person_titles(session, name)
        # Now, create a list of articles where this person name appears
        articles = _query_article_list(session, name)
        response = dict(answers=titles, sources=articles)
        if titles and "answer" in titles[0]:
            # 'Már Guðmundsson er seðlabankastjóri.'
            answer = titles[0]["answer"]
            # Set the context for a subsequent query
            query.set_context({"person_name": name})
        else:
            answer = f"Nafnið {icequote(name)} finnst ekki."
    return response, answer, voice_answer


# Try to avoid titles that simply say that A is the husband/wife of B,
# or something similar
_DONT_LIKE_TITLE = (
    "maki",
    "eiginmaður",
    "eiginkona",
    "kærasti",
    "kærasta",
    "sambýlismaður",
    "sambýliskona",
)


def query_person_title(session: Session, name: str) -> Tuple[str, Optional[str]]:
    """Return the most likely title for a person"""

    def we_dont_like(answer: str) -> bool:
        """Return False if we don't like this title and
        would prefer another one"""
        # Skip titles that simply say that somebody is the husband or
        # wife of somebody else
        return answer.startswith(_DONT_LIKE_TITLE)

    rl = _query_person_titles(session, name)
    len_rl = len(rl)
    index = 0
    while index < len_rl and we_dont_like(rl[index]["answer"]):
        index += 1
    if index >= len_rl:
        # If we don't like any answer anyway, go back to the topmost one
        index = 0
    if index >= len_rl:
        return "", None
    return correct_spaces(rl[index]["answer"]), rl[index]["sources"][0]["domain"]


def query_title(query: Query, session: Session, title: str) -> AnswerTuple:
    """A query for a person by title"""
    # !!! Consider doing a LIKE '%title%', not just LIKE 'title%'
    # We impose a LIMIT of 1024 on each query result,
    # since the query may return many names (for instance 'Hver er formaður?'),
    # and getting more name mentions than this is not likely to significantly
    # affect the outcome.
    QUERY_LIMIT = 1024
    rd: RegisterType = defaultdict(dict)
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
        .order_by(desc(cast(Column[DateTime], Article.timestamp)))
        .limit(QUERY_LIMIT)
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
        .order_by(desc(Article.timestamp))
        .limit(QUERY_LIMIT)
        .all()
    )
    append_names(rd, q, prop_func=lambda x: x.name)
    response = make_response_list(rd)
    answer: str
    voice_answer: str
    voice_title = gssml(title, type="generic")
    if response and title and "answer" in response[0]:
        first_response = response[0]
        # Return 'Seðlabankastjóri er Már Guðmundsson.'
        answer = first_response["answer"]
        voice_answer = f"{voice_title} er {gssml(answer, type='person')}."
        # Store the person name in the query context
        # so it can be referred to in subsequent queries
        query.set_context({"person_name": answer})
        if first_response.get("sources"):
            first_source = first_response["sources"][0]["domain"]
            query.set_source(first_source)
    else:
        answer = f"Ekkert nafn finnst með titilinn {icequote(title)}."
        voice_answer = f"Ég veit ekki hver er {voice_title}."
    return response, answer, voice_answer


def _query_entity_definitions(session: Session, name: str) -> List[Dict[str, Any]]:
    """A query for definitions of an entity by name"""
    # Note: the comparison below between name_lc and name
    # is automatically case-insensitive, so name.lower() is not required
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
        .filter_by(name_lc=name)
        .filter(Root.visible == True)
        .join(Article, Article.url == Entity.article_url)
        .join(Root)
        .order_by(Article.timestamp)
        .all()
    )
    return prepare_response(q, prop_func=lambda x: x.definition)


def query_entity(query: Query, session: Session, name: str) -> AnswerTuple:
    """A query for an entity by name"""
    titles = _query_entity_definitions(session, name)
    articles = _query_article_list(session, name)
    response: ResponseDict = dict(answers=titles, sources=articles)
    if titles and "answer" in titles[0]:
        # 'Mál og menning er bókmenntafélag.'
        answer = titles[0]["answer"]
        answer = cap_first(answer)
        uc_name = cap_first(name)
        voice_answer = (
            f"{gssml(uc_name, type='entity')} er {gssml(answer, type='entity')}."
        )
        if "sources" in titles[0]:
            source = titles[0]["sources"][0]["domain"]
            query.set_source(source)
        query.set_context({"entity_name": uc_name})
    else:
        answer = f"Engin skilgreining finnst á nafninu {icequote(name)}."
        voice_answer = f"Ég veit ekki hvað {gssml(name, type='entity')} er."
        if query.is_voice:
            # Rather than accept this as a voice query
            # for an entity that is not found, return an
            # error and thereby give other query handlers
            # a chance to parse this
            query.set_error("E_ENTITY_NOT_FOUND")
    return response, answer, voice_answer


def query_entity_def(session: Session, name: str) -> str:
    """Return a single (best) definition of an entity"""
    rl = _query_entity_definitions(session, name)
    return correct_spaces(rl[0]["answer"]) if rl else ""


def query_company(
    query: Query, session: Session, name: str
) -> Tuple[List[Dict[str, Any]], str, str]:
    """A query for an company in the entities table"""
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
        answer = response[0]["answer"]
        voice_answer = f"{gssml(name, type='entity')} er {answer}."
    else:
        answer = f"Engin skilgreining finnst á nafninu {icequote(name)}."
        voice_answer = f"Ég veit ekki hvað {gssml(name, type='company')} er."
    return response, answer, voice_answer


def query_word(query: Query, session: Session, stem: str) -> AnswerTuple:
    """A query for words related to the given stem"""
    # Count the articles where the stem occurs
    acnt = ArticleCountQuery.count(stem, enclosing_session=session)
    if acnt:
        rlist = RelatedWordsQuery.rel(stem, enclosing_session=session) or []
    else:
        rlist = []
    # Convert to an easily serializable dict
    # Exclude the original search stem from the result
    return (
        dict(
            count=acnt,
            answers=[
                dict(stem=rstem, cat=rcat)
                for rstem, rcat, _ in rlist
                if rstem != stem
            ],
        ),
        "",
        None,
    )


def launch_search(query: Query, session: Session, qkey: str) -> AnswerTuple:
    """Launch a search with the given search terms"""
    toklist = query.token_list
    assert toklist is not None
    pgs, _ = TreeUtility.raw_tag_toklist(toklist)  # root=_QUERY_ROOT

    # Collect the list of search terms
    terms: List[Tuple[str, str]] = []
    tweights: List[TermDict] = []
    fixups: List[Tuple[TermDict, int]] = []
    for pg in pgs:
        for sent in pg:
            for t in sent:
                # Obtain search stems for the tokens.
                d = TermDict(x=t.get("x", ""), w=0.0)
                tweights.append(d)
                # The terms are represented as (stem, category) tuples.
                stems = stems_of_token(t)
                if stems:
                    terms.extend(stems)
                    fixups.append((d, len(stems)))

    assert sum(n for _, n in fixups) == len(terms)

    if Settings.DEBUG:
        print(f"Terms are:\n   {terms}")

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
    return dict(answers=result["articles"], weights=tweights), "", None


def repeat_query(query: Query, session: Session, qkey: str) -> AnswerTuple:
    """Request to repeat the result of the last query"""
    last = query.last_answer()
    if last is None:
        answer = "Ekkert nýlegt svar."
        voice_answer = "Ég hef ekki svarað neinu nýlega."
    else:
        answer, voice_answer = last
    # Put a period at the end of the beautified query,
    # instead of a question mark
    query.query_is_command()
    response = dict(answer=answer)
    return response, answer, voice_answer


# Map query types to handler functions
_QFUNC: Dict[str, Callable[[Query, Session, str], AnswerTuple]] = {
    "Person": query_person,
    "Title": query_title,
    "Entity": query_entity,
    "Company": query_company,
    "Word": query_word,
    "Search": launch_search,
    "Repeat": repeat_query,
}

# Query types that are not supported for voice queries
_Q_NO_VOICE = frozenset(("Search", "Word"))

# Query types that are only supported for voice queries
_Q_ONLY_VOICE = frozenset(("Repeat",))


def sentence(state: QueryStateDict, result: Result) -> None:
    """Called when sentence processing is complete"""
    q: Query = state["query"]
    if "qtype" not in result:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
        return
    if q.is_voice and result.qtype in _Q_NO_VOICE:
        # We don't do topic searches or word relationship
        # queries via voice; that would be pretty meaningless
        q.set_error("E_VOICE_NOT_SUPPORTED")
        return
    if not q.is_voice and result.qtype in _Q_ONLY_VOICE:
        # We don't allow repeat requests in non-voice queries
        q.set_error("E_ONLY_VOICE_SUPPORTED")
        return

    # Successfully matched a query type
    q.set_qtype(result.qtype)
    q.set_key(result.qkey)

    if result.qtype == "Search":
        # For searches, don't add a question mark at the end
        if q.beautified_query.endswith("?") and not q.query.endswith("?"):
            q.set_beautified_query(q.beautified_query[:-1])
    session = state["session"]
    # Select a query function and exceute it
    qfunc = _QFUNC.get(result.qtype)
    answer: str
    response: ResponseType
    if qfunc is None:
        answer = cast(str, result.qtype + ": " + result.qkey)
        response = dict(answer=answer)
        q.set_answer(response, answer)
        return
    try:
        response, answer, voice_answer = qfunc(q, session, result.qkey)
        q.set_answer(response, answer, voice_answer)
    except AssertionError:
        raise
    except Exception as e:
        q.set_error(f"E_EXCEPTION: {e}")


# The following functions correspond to grammar nonterminals (see Greynir.grammar)
# and are called during tree processing (depth-first, i.e. bottom-up navigation)


def QPerson(node: Node, params: QueryStateDict, result: Result) -> None:
    """Person query"""
    result.qtype = "Person"
    if "mannsnafn" in result:
        result.qkey = result.mannsnafn
    elif "sérnafn" in result:
        result.qkey = result.sérnafn
    elif "persónufornafn" in result:
        result.qkey = result.persónufornafn
    else:
        assert False


def QPersonPronoun(node: Node, params: QueryStateDict, result: Result) -> None:
    """Persónufornafn: hann, hún, það"""
    result.persónufornafn = result._nominative


def QCompany(node: Node, params: QueryStateDict, result: Result) -> None:
    result.qtype = "Company"
    result.qkey = result.fyrirtæki


def QEntity(node: Node, params: QueryStateDict, result: Result) -> None:
    result.qtype = "Entity"
    assert "qkey" in result


def QTitle(node: Node, params: QueryStateDict, result: Result) -> None:
    result.qtype = "Title"
    result.qkey = result.titill


def QWord(node: Node, params: QueryStateDict, result: Result) -> None:
    result.qtype = "Word"
    assert "qkey" in result


def QSearch(node: Node, params: QueryStateDict, result: Result) -> None:
    result.qtype = "Search"
    # Return the entire query text as the search key
    result.qkey = result._text


def QRepeat(node: Node, params: QueryStateDict, result: Result) -> None:
    """Request to repeat the last query answer"""
    result.qkey = ""
    result.qtype = "Repeat"


def Sérnafn(node: Node, params: QueryStateDict, result: Result) -> None:
    """Sérnafn, stutt eða langt"""
    result.sérnafn = result._nominative


def Fyrirtæki(node: Node, params: QueryStateDict, result: Result) -> None:
    """Fyrirtækisnafn, þ.e. sérnafn + ehf./hf./Inc. o.s.frv."""
    result.fyrirtæki = result._nominative


def Mannsnafn(node: Node, params: QueryStateDict, result: Result) -> None:
    """Hreint mannsnafn, þ.e. án ávarps og titils"""
    result.mannsnafn = result._nominative


def EfLiður(node: Node, params: QueryStateDict, result: Result) -> None:
    """Eignarfallsliðir haldast óbreyttir,
    þ.e. þeim á ekki að breyta í nefnifall"""
    result._nominative = result._text


def FsMeðFallstjórn(node: Node, params: QueryStateDict, result: Result) -> None:
    """Forsetningarliðir haldast óbreyttir,
    þ.e. þeim á ekki að breyta í nefnifall"""
    result._nominative = result._text


def QEntityKey(node: Node, params: QueryStateDict, result: Result) -> None:
    if "sérnafn" in result:
        result.qkey = result.sérnafn
    else:
        result.qkey = result._nominative


def QTitleKey(node: Node, params: QueryStateDict, result: Result) -> None:
    """Titill"""
    result.titill = result._nominative


def QWordNounKey(node: Node, params: QueryStateDict, result: Result) -> None:
    result.qkey = result._canonical


def QWordPersonKey(node: Node, params: QueryStateDict, result: Result) -> None:
    if "mannsnafn" in result:
        result.qkey = result.mannsnafn
    elif "sérnafn" in result:
        result.qkey = result.sérnafn
    else:
        result.qkey = result._nominative


def QWordEntityKey(node: Node, params: QueryStateDict, result: Result) -> None:
    result.qkey = result._nominative


def QWordVerbKey(node: Node, params: QueryStateDict, result: Result) -> None:
    result.qkey = result._root
