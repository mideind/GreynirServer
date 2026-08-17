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

    Similarity by article and by topic vector is answered directly from
    PostgreSQL, via a pgvector HNSW index over articles.topic_embedding.
    Similarity by search terms still goes through the similarity server,
    which holds the gensim LSI model needed to project terms into topic
    space; see PLAN.md phase 3 for its planned retirement.

"""

from typing import Iterable, List, Optional, Tuple, TypedDict

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import text as sql_text

from settings import Settings
from db import Session
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


# A similarity candidate: article metadata plus a similarity fraction,
# in decreasing order of similarity
CandidateTuple = Tuple[str, Optional[str], str, str, Optional[datetime], float]

# k nearest neighbours by cosine similarity, served by the
# articles_topic_embedding_hnsw index. The LIMIT values used here
# (n + 5, i.e. at most 25) are comfortably below the hnsw.ef_search
# default of 40; materially larger limits need a SET LOCAL
# hnsw.ef_search to keep recall up.
_SIMILAR_TO_VECTOR_SQL = """
    SELECT a.id::text, a.heading, a.url, r.domain, a.timestamp,
           1.0 - (a.topic_embedding <=> CAST(:vec AS vector)) AS similarity
      FROM articles a
      JOIN roots r ON r.id = a.root_id
     WHERE r.visible
       AND a.topic_embedding IS NOT NULL
     ORDER BY a.topic_embedding <=> CAST(:vec AS vector)
     LIMIT :n
"""

# The stored embedding of a single article, in pgvector text format,
# ready to be passed back into _SIMILAR_TO_VECTOR_SQL
_ARTICLE_VECTOR_SQL = """
    SELECT topic_embedding::text FROM articles WHERE id = :uuid
"""

# Bulk metadata fetch for externally supplied (article id, similarity)
# pairs -- the shape the similarity server returns for the terms path
_HYDRATE_SQL = """
    SELECT a.id::text, a.heading, a.url, r.domain, a.timestamp
      FROM articles a
      JOIN roots r ON r.id = a.root_id
     WHERE a.id = ANY(CAST(:ids AS uuid[]))
"""


class Search:

    """This class wraps similarity queries: nearest-neighbour lookups
    against the pgvector index for article and topic vector queries,
    and the similarity server (via the similarity client) for term
    queries."""

    def __init__(self) -> None:
        """This class is normally not instantiated"""
        pass

    @classmethod
    def _new_client(cls) -> SimilarityClient:
        """Create a new similarity client for each request to avoid
        connection sharing issues between concurrent greenlets/threads"""
        return SimilarityClient()

    @classmethod
    def list_similar_to_article(
        cls, session: Session, uuid: str, n: int
    ) -> Tuple[List[SimilarDict], bool]:
        """List n articles that are similar to the article with the given id.
        Returns a tuple of (similar_articles, not_indexed) where not_indexed
        is True if the article has not yet been indexed for similarity."""
        try:
            UUID(uuid)
        except ValueError:
            # Not a valid UUID: treat like an unknown article
            return [], True
        row = session.execute(  # type: ignore[attr-defined]
            sql_text(_ARTICLE_VECTOR_SQL), {"uuid": uuid}
        ).fetchone()
        if row is None or row[0] is None:
            # Unknown article, or one that the tagger has not
            # (successfully) indexed yet
            return [], True
        return cls._list_similar_to_vector(session, row[0], n), False

    @classmethod
    def list_similar_to_topic(
        cls, session: Session, topic_vector: List[float], n: int
    ) -> List[SimilarDict]:
        """List n articles that are similar to the given topic vector"""
        if not topic_vector or all(e == 0.0 for e in topic_vector):
            # A zero vector has no direction: cosine similarity is undefined
            return []
        vec = "[" + ",".join(str(float(e)) for e in topic_vector) + "]"
        return cls._list_similar_to_vector(session, vec, n)

    @classmethod
    def _list_similar_to_vector(
        cls, session: Session, vec: str, n: int
    ) -> List[SimilarDict]:
        """Run a kNN query for the given vector (in pgvector text format),
        over-fetching by 5 to leave room for the filtering below"""
        # Raise the HNSW search queue over its default of 40: measured
        # 2026-08-17 against exact search, recall@10 improves for a few
        # milliseconds of per-query cost (see PLAN.md phase 2). SET LOCAL
        # scopes the setting to the enclosing transaction.
        session.execute(  # type: ignore[attr-defined]
            sql_text("SET LOCAL hnsw.ef_search = 100")
        )
        rows = session.execute(  # type: ignore[attr-defined]
            sql_text(_SIMILAR_TO_VECTOR_SQL), {"vec": vec, "n": n + 5}
        )
        return cls._filter_candidates(rows, n)

    @classmethod
    def list_similar_to_terms(
        cls, session: Session, terms: List[Tuple[str, str]], n: int
    ) -> WeightsDict:
        """List n articles that are similar to the given terms. The
        terms are expected to be a list of (stem, category) tuples."""
        client = cls._new_client()
        try:
            result = client.list_similar_to_terms(terms, n=n + 5)
        finally:
            client.close()
        articles: List[Tuple[str, float]] = result.get("articles", [])
        weights: List[float] = result.get("weights", [])
        return WeightsDict(
            weights=weights, articles=cls.list_articles(session, articles, n)
        )

    @classmethod
    def list_articles(
        cls, session: Session, result: Iterable[Tuple[str, float]], n: int
    ) -> List[SimilarDict]:
        """Convert (article id, similarity) tuples into article descriptors.
        Metadata for all candidates is fetched in a single query; this used
        to be one query per candidate."""
        pairs = list(result)
        if not pairs:
            return []
        rows = session.execute(  # type: ignore[attr-defined]
            sql_text(_HYDRATE_SQL), {"ids": [sid for sid, _ in pairs]}
        )
        meta = {row[0]: row for row in rows}

        def gen_candidates():
            for sid, similarity in pairs:
                row = meta.get(sid)
                if row is not None:
                    yield (row[0], row[1], row[2], row[3], row[4], similarity)

        return cls._filter_candidates(gen_candidates(), n)

    @classmethod
    def _filter_candidates(
        cls, candidates: Iterable[CandidateTuple], n: int
    ) -> List[SimilarDict]:
        """Filter and deduplicate similarity candidates, arriving in
        decreasing order of similarity, into at most n article descriptors.
        The logic is unchanged from the simserver era: a near-perfect match
        is the source article itself (or a verbatim copy of it), and
        candidates from the same domain with near-identical timestamps and
        similarities are duplicate feeds of the same story, where the newer
        article wins."""
        similar: List[SimilarDict] = []
        for sid, heading, url, domain, ts, similarity in candidates:
            if similarity > 0.9999:
                # The original article (or at least a verbatim copy of it)
                continue
            if not heading:
                # Skip articles without headings
                continue
            if ts is None:
                continue
            if ts.tzinfo is None:
                # Raw SQL rows bypass the DateTimeUtc type decorator;
                # the database stores UTC
                ts = ts.replace(tzinfo=timezone.utc)
            # Similarity in percent
            spercent = 100.0 * similarity

            def is_probably_same_as(last: SimilarDict) -> bool:
                """Return True if the current article is probably the same
                as the one already described in the last object"""
                if last["domain"] != domain:
                    # Another root domain: can't be the same content
                    return False
                if abs(last["ts"] - ts) > timedelta(minutes=10):
                    # More than 10 minutes timestamp difference
                    return False
                # Quite similar: probably the same article
                ratio = spercent / last["similarity"]
                if ratio > 0.993:
                    if Settings.DEBUG:
                        print(
                            "Rejecting {0}, domain {1}, ts {2} because of similarity with {3},"
                            " {4}, {5}; ratio is {6:.3f}".format(
                                heading,
                                domain,
                                ts,
                                last["heading"],
                                last["domain"],
                                last["ts"],
                                ratio,
                            )
                        )
                    return True
                return False

            d = SimilarDict(
                heading=heading,
                url=url,
                uuid=sid,
                domain=domain,
                ts=ts,
                ts_text=ts.isoformat()[0:10],
                similarity=spercent,
            )
            # Don't add another article with practically the same similarity
            # as the previous one, as it is very probably a duplicate
            same = next(
                ((ix, p) for ix, p in enumerate(similar) if is_probably_same_as(p)),
                None,
            )
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
                    print("Replacing: {0} ({1:.2f})".format(heading, spercent))
                similar[same[0]] = d
            else:
                # Similar article, and the previous one is newer:
                # drop the one we're considering
                if Settings.DEBUG:
                    print("Ignoring: {0} ({1:.2f})".format(heading, spercent))
                pass

        if Settings.DEBUG and similar:
            print(
                "Similar list is:\n   {0}".format("\n   ".join(str(s) for s in similar))
            )
        return similar
