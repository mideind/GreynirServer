"""

    Greynir: Natural language processing for Icelandic

    Search module

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


    This module implements a search mechanism. The Search class parses
    a search string into list of word stems and creates a topic vector from it,
    which is then used in a similarity query to find related articles.

"""

from typing import Iterable, Iterator, Optional, List, Tuple
from typing_extensions import TypedDict

from datetime import datetime, timedelta

from settings import Settings
from db import Session
from db.models import Root, Article
from similar import SimilarityClient


class SimilarDict(TypedDict):
    """Typed dictionary for the result of a similarity query"""

    heading: str
    url: str
    uuid: str
    domain: str
    ts: datetime
    ts_text: str
    similarity: float


class WeightsDict(TypedDict):
    """Typed dictionary for the result of a similarity query"""

    weights: List[float]
    articles: List[SimilarDict]


class Search:

    """This class wraps search queries to the similarity server
    via the similarity client."""

    # Similarity query client
    similarity_client: Optional[SimilarityClient] = None

    def __init__(self) -> None:
        """This class is normally not instantiated"""
        pass

    @classmethod
    def _connect(cls):
        """Ensure that the client is connected, if possible"""
        if cls.similarity_client is None:
            cls.similarity_client = SimilarityClient()

    @classmethod
    def list_similar_to_article(cls, session: Session, uuid: str, n: int) -> List[SimilarDict]:
        """List n articles that are similar to the article with the given id"""
        cls._connect()
        # Returns a list of tuples: (article_id, similarity)
        assert cls.similarity_client is not None
        result = cls.similarity_client.list_similar_to_article(uuid, n=n + 5)
        articles: List[Tuple[str, float]] = result.get("articles", [])
        # Convert the result tuples into article descriptors
        return cls.list_articles(session, articles, n)

    @classmethod
    def list_similar_to_topic(cls, session: Session, topic_vector: List[float], n: int) -> List[SimilarDict]:
        """List n articles that are similar to the given topic vector"""
        cls._connect()
        # Returns a list of tuples: (article_id, similarity)
        assert cls.similarity_client is not None
        result = cls.similarity_client.list_similar_to_topic(topic_vector, n=n + 5)
        articles: List[Tuple[str, float]] = result.get("articles", [])
        # Convert the result tuples into article descriptors
        return cls.list_articles(session, articles, n)

    @classmethod
    def list_similar_to_terms(cls, session: Session, terms: List[Tuple[str, str]], n: int) -> WeightsDict:
        """List n articles that are similar to the given terms. The
        terms are expected to be a list of (stem, category) tuples."""
        cls._connect()
        # Returns a list of tuples: (article_id, similarity)
        assert cls.similarity_client is not None
        result = cls.similarity_client.list_similar_to_terms(terms, n=n + 5)
        # Convert the result tuples into article descriptors
        articles: List[Tuple[str, float]] = result.get("articles", [])
        # Obtain the search term weights
        weights: List[float] = result.get("weights", [])
        return WeightsDict(weights=weights, articles=cls.list_articles(session, articles, n))

    @classmethod
    def list_articles(
        cls, session: Session, result: Iterable[Tuple[str, float]], n: int
    ) -> List[SimilarDict]:
        """Convert similarity result tuples into article descriptors"""
        similar: List[SimilarDict] = []
        for sid, similarity in result:
            if similarity > 0.9999:
                # The original article (or at least a verbatim copy of it)
                continue
            q = session.query(Article).join(Root).filter(Article.id == sid)
            sa: Optional[Article] = q.one_or_none()
            if sa is None:
                # Article not found
                continue
            if not sa.heading:
                # Skip articles without headings
                continue
            # Similarity in percent
            spercent = 100.0 * similarity

            def is_probably_same_as(last: SimilarDict) -> bool:
                """Return True if the current article is probably different from
                the one already described in the last object"""
                assert sa is not None
                if last["domain"] != sa.root.domain:
                    # Another root domain: can't be the same content
                    return False
                assert sa.timestamp is not None
                if abs(last["ts"] - sa.timestamp) > timedelta(minutes=10):
                    # More than 10 minutes timestamp difference
                    return False
                # Quite similar: probably the same article
                ratio = spercent / last["similarity"]
                if ratio > 0.993:
                    if Settings.DEBUG:
                        print(
                            "Rejecting {0}, domain {1}, ts {2} because of similarity with {3},"
                            " {4}, {5}; ratio is {6:.3f}".format(
                                sa.heading,
                                sa.root.domain,
                                sa.timestamp,
                                last["heading"],
                                last["domain"],
                                last["ts"],
                                ratio,
                            )
                        )
                    return True
                return False

            def gen_similar() -> Iterator[Tuple[int, SimilarDict]]:
                """Generate the entries in the result list that are probably
                the same as the one we are considering"""
                for ix, p in enumerate(similar):
                    if is_probably_same_as(p):
                        yield (ix, p)

            d = SimilarDict(
                heading=sa.heading,
                url=sa.url,
                uuid=sid,
                domain=sa.root.domain,
                ts=sa.timestamp,
                ts_text=sa.timestamp.isoformat()[0:10],
                similarity=spercent,
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
                # Similar article, and the one we're considering is
                # newer: replace the one in the list
                if Settings.DEBUG:
                    print("Replacing: {0} ({1:.2f})".format(sa.heading, spercent))
                similar[same[0]] = d
            else:
                # Similar article, and the previous one is newer:
                # drop the one we're considering
                if Settings.DEBUG:
                    print("Ignoring: {0} ({1:.2f})".format(sa.heading, spercent))
                pass

        if Settings.DEBUG and similar:
            print(
                "Similar list is:\n   {0}".format("\n   ".join(str(s) for s in similar))
            )
        return similar
