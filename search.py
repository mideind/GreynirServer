"""

    Reynir: Natural language processing for Icelandic

    Search module

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


    This module implements a search mechanism. The Search class parses
    a search string into list of word stems and creates a topic vector from it,
    which is then used in a similarity query to find related articles.

"""

import sys
from datetime import datetime, timedelta
from contextlib import closing

from settings import Settings, changedlocale
from article import Article as ArticleProxy
from scraperdb import Root, Article
from bindb import BIN_Db
from tokenizer import stems_of_token
from similar import SimilarityClient


_MAXLEN_ANSWER = 25 # Maximum number of top answers to send in response to queries


class Search:

    """ A Query is initialized by parsing a query string using QueryRoot as the
        grammar root nonterminal. The Query can then be executed by processing
        the best parse tree using the nonterminal handlers given above, returning a
        result object if successful. """

    # Similarity query client
    similarity_client = None


    def __init__(self, session):
        self._session = session
        self._error = None
        self._answer = None
        self._terms = None


    @classmethod
    def _connect(cls):
        """ Ensure that the client is connected, if possible """
        if cls.similarity_client is None:
            cls.similarity_client = SimilarityClient()


    def parse(self, toklist, result):
        """ Parse the token list as a search query """

        self._error = None # Erase previous error, if any
        self._answer = None
        self._terms = None

        pgs, stats, register = ArticleProxy.tag_toklist(self._session, toklist)

        # Collect the list of search terms
        terms = []
        for pg in pgs:
            for sent in pg:
                for t in sent:
                    # Obtain search stems for the tokens. name_emphasis = 2
                    # means that person and entity names are doubled up.
                    # The terms are represented as (stem, category) tuples.
                    terms.extend(stems_of_token(t, name_emphasis = 2))
        print("Terms are:\n   {0}".format(terms))
        self._terms = terms
        return True


    def execute(self, n):
        """ Execute the query contained in the previously parsed tree; return True if successful """
        self._answer = Search.list_similar_to_terms(self._session, self._terms, n)
        return bool(self._answer)


    def set_answer(self, answer):
        """ Set the answer to the query """
        self._answer = answer


    def set_error(self, error):
        """ Set an error result """
        self._error = error


    def answer(self):
        """ Return the query answer """
        return self._answer


    def error(self):
        """ Return the query error, if any """
        return self._error


    @classmethod
    def list_similar_to_article(cls, session, uuid, n):
        """ List n articles that are similar to the article with the given id """
        cls._connect()
        # Returns a list of tuples: (article_id, similarity)
        result = cls.similarity_client.list_similar_to_article(uuid, n = n + 5)
        # Convert the result tuples into article descriptors
        return cls.list_articles(session, result, n)


    @classmethod
    def list_similar_to_topic(cls, session, topic_vector, n):
        """ List n articles that are similar to the given topic vector """
        cls._connect()
        # Returns a list of tuples: (article_id, similarity)
        result = cls.similarity_client.list_similar_to_topic(topic_vector, n = n + 5)
        # Convert the result tuples into article descriptors
        return cls.list_articles(session, result, n)


    @classmethod
    def list_similar_to_terms(cls, session, terms, n):
        """ List n articles that are similar to the given terms. The
            terms are expected to be a list of (stem, category) tuples. """
        cls._connect()
        # Returns a list of tuples: (article_id, similarity)
        result = cls.similarity_client.list_similar_to_terms(terms, n = n + 5)
        # Convert the result tuples into article descriptors
        return cls.list_articles(session, result, n)


    @classmethod
    def list_articles(cls, session, result, n):
        """ Convert similarity result tuples into article descriptors """
        similar = []
        for sid, similarity in result:
            if similarity > 0.9999:
                # The original article (or at least a verbatim copy of it)
                continue
            q = session.query(Article).join(Root).filter(Article.id == sid)
            sa = q.one_or_none()
            if sa and sa.heading.strip(): # Skip articles without headings
                # Similarity in percent
                spercent = 100.0 * similarity

                def is_probably_same_as(last):
                    """ Return True if the current article is probably different from
                        the one already described in the last object """
                    if last["domain"] != sa.root.domain:
                        # Another root domain: can't be the same content
                        return False
                    if abs(last["ts"] - sa.timestamp) > timedelta(minutes = 10):
                        # More than 10 minutes timestamp difference
                        return False
                    # Quite similar: probably the same article
                    ratio = (spercent / last["similarity"])
                    if ratio > 0.993:
                        print("Rejecting {0}, domain {1}, ts {2} because of similarity with {3}, {4}, {5}; ratio is {6:.3f}"
                            .format(sa.heading, sa.root.domain, sa.timestamp,
                                last["heading"], last["domain"], last["ts"], ratio))
                        return True
                    return False

                def gen_similar():
                    """ Generate the entries in the result list that are probably the same as the one we are considering """
                    for ix, p in enumerate(similar):
                        if is_probably_same_as(p):
                            yield (ix, p)

                d = dict(heading = sa.heading, url = sa.url,
                    uuid = sid, domain = sa.root.domain,
                    ts = sa.timestamp, ts_text = sa.timestamp.isoformat()[0:10],
                    similarity = spercent
                )
                # Don't add another article with practically the same similarity
                # as the previous one, as it is very probably a duplicate
                same = next(gen_similar(), None)
                if same is None:
                    # No similar article
                    similar.append(d)
                    if len(similar) == n:
                        # Enough articles: we're done
                        break
                elif d["ts"] > same[1]["ts"]:
                    # Similar article, and the one we're considering is newer: replace the one in the list
                    print("Replacing: {0} ({1:.2f})".format(sa.heading, spercent))
                    similar[same[0]] = d
                else:
                    # Similar article, and the previous one is newer: drop the one we're considering
                    print("Ignoring: {0} ({1:.2f})".format(sa.heading, spercent))

        print("Similar list is:\n   {0}".format("\n   ".join(str(s) for s in similar)))
        return similar


