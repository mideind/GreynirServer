#!/usr/bin/env python3
"""

    Greynir: Natural language processing for Icelandic

    Topic tagger module

    Copyright (C) 2026 Miðeind ehf.

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


    This module assigns LSI topic vectors and topics to articles, and
    recalculates the topics' own vectors from their keywords. It replaces
    the 'tag' and 'topics' commands of vectors/builder.py, which needed
    gensim 3.8 and therefore a frozen CPython 3.9 environment of its own
    (see PLAN.md, "port the topic tagger off gensim/3.9").

    The arithmetic is topicvector.LsiModel.project, the gensim-free
    projection that already serves search-by-terms, so tagging and
    searching cannot drift apart. The LSI model itself is unchanged: the
    same dictionary, idf weights and projection matrix, exported from the
    gensim files by tools/export_lsi_model.py. Vectors written here
    therefore live in the same space as the ~1.5 million that builder.py
    wrote, and old and new articles are compared and searched through the
    same pgvector index without re-embedding anything. Only rebuilding the
    model itself (builder.py 'model') still needs gensim.

    Behaviour deliberately mirrors builder.py, edge cases included:

      * an article's bag of words is its stems from the words table, each
        repeated by its count;
      * vectors are compared in gensim's sparse form, where a component of
        magnitude 1e-9 or less does not exist (matutils.full2sparse), and
        an article whose vector is empty in that form gets a NULL
        topic_vector and no topics;
      * cosine similarity is computed as matutils.cossim computes it, and
        a topic is assigned when the similarity reaches its threshold;
      * every article is committed in its own transaction, so a run that
        dies part-way keeps what it finished;
      * topic vectors are stored in the topics table in gensim's sparse
        [[index, value], ...] format under the "lsi" key, which builder.py
        can still read. That keeps builder.py usable as a rollback.

    Two deliberate differences:

      * topic_vector is written dense, with every one of its 200 components.
        builder.py stored only the *values* of gensim's sparse output, so
        when a component fell under 1e-9 it was dropped and every later
        component slid down one place, leaving a 199-element vector with
        its values in the wrong positions. The pgvector trigger rejects
        those, leaving topic_embedding NULL (17 articles as of 2026-10-13).
        Re-tagging them here repairs them.
      * it refuses to tag when the topics table holds no topic vectors.
        builder.py would carry on and stamp every article it touched as
        indexed with a NULL topic_vector, silently wiping vectors.

"""

from typing import Dict, List, NamedTuple, Optional, Set, Tuple

import getopt
import json
import math
import sys
import time
from datetime import datetime, timezone

import numpy as np
from sqlalchemy import exists
from sqlalchemy.orm import Query

from reynir.basics import ConfigError, LineReader

from settings import Settings
from db import SessionContext, Session
from db.models import Article, ArticleTopic, Topic, Word
from topicvector import LsiModel, w_from_stem
from utility import GREYNIR_ROOT_DIR

# The topic keyword file stays where builder.py reads it from, so that
# both taggers share one copy for as long as builder.py exists
TOPICS_CONF = GREYNIR_ROOT_DIR / "vectors" / "Topics.conf"

# The name under which topic vectors are stored in the topics table
MODEL_NAME = "lsi"

# gensim's matutils.full2sparse drops components whose magnitude is not
# above this, and builder.py's vectors went through it
SPARSE_EPS = 1e-9

# The word categories that topic keywords may have (vectors/settings.py)
TOPIC_KEYWORD_CATEGORIES = frozenset(
    ("kk", "kvk", "hk", "lo", "so", "entity", "person", "person_kk", "person_kvk")
)

SparseVector = Dict[int, float]


def _now() -> datetime:
    """Return the current time in UTC"""
    return datetime.now(timezone.utc)


def _timestamp() -> str:
    """The run timestamp format builder.py printed into runscraper.log"""
    return "{0}".format(_now())[0:19]


# ---------------------------------------------------------------------------
# Vector arithmetic, matching gensim
# ---------------------------------------------------------------------------


def to_sparse(vec: np.ndarray) -> SparseVector:
    """Convert a dense vector to gensim's sparse form, as
    matutils.full2sparse does: components of magnitude <= 1e-9 vanish"""
    return {int(i): float(vec[i]) for i in np.nonzero(np.abs(vec) > SPARSE_EPS)[0]}


def cossim(vec1: SparseVector, vec2: SparseVector) -> float:
    """Cosine similarity between two sparse vectors, computed exactly as
    gensim's matutils.cossim does, including iterating over the shorter
    vector, so that topic thresholds see the same numbers as before"""
    if not vec1 or not vec2:
        return 0.0
    vec1len = math.sqrt(sum(val * val for val in vec1.values()))
    vec2len = math.sqrt(sum(val * val for val in vec2.values()))
    if len(vec2) < len(vec1):
        vec1, vec2 = vec2, vec1
    result = sum(value * vec2.get(index, 0.0) for index, value in vec1.items())
    return result / (vec1len * vec2len)


def project_words(model: LsiModel, wlist: List[str]) -> Optional[np.ndarray]:
    """Project a bag of words into LSI space. Returns None where gensim's
    sparse result would have been empty, i.e. where builder.py stored
    no vector at all."""
    if not wlist:
        return None
    vec, _ = model.project(wlist)
    if not to_sparse(vec):
        return None
    return vec


# ---------------------------------------------------------------------------
# Article tagging
# ---------------------------------------------------------------------------


class TopicInfo(NamedTuple):
    id: str
    name: str
    threshold: float
    vector: SparseVector


def load_topics(session: Session) -> List[TopicInfo]:
    """Load the topics that have a vector, as builder.py load_topics does"""
    topics: List[TopicInfo] = []
    for topic in session.query(Topic).all():
        if not topic.vector:
            continue
        pairs = json.loads(topic.vector).get(MODEL_NAME)
        if pairs:
            topics.append(
                TopicInfo(
                    id=str(topic.id),
                    name=topic.name,
                    threshold=topic.threshold,
                    vector={int(ix): float(f) for ix, f in pairs},
                )
            )
    return topics


def article_words(session: Session, article_id: str) -> List[str]:
    """Return an article's bag of words from the words table, with each
    stem repeated by its count, as builder.py assign_article_topics does"""
    wlist: List[str] = []
    q = (
        session.query(Word.stem, Word.cat, Word.cnt)
        .filter(Word.article_id == article_id)
        .all()
    )
    for stem, cat, cnt in q:
        w = w_from_stem(stem, cat)
        if cnt == 1:
            wlist.append(w)
        else:
            wlist.extend([w] * cnt)
    return wlist


def match_topics(
    vec: Optional[np.ndarray], topics: List[TopicInfo]
) -> List[Tuple[TopicInfo, float]]:
    """Return the topics whose similarity to the article vector reaches
    their threshold, with the similarities, in topics table order"""
    if vec is None:
        return []
    article = to_sparse(vec)
    found: List[Tuple[TopicInfo, float]] = []
    for topic in topics:
        similarity = cossim(article, topic.vector)
        if similarity >= topic.threshold:
            found.append((topic, similarity))
    return found


def compute_article(
    session: Session, model: LsiModel, topics: List[TopicInfo], article_id: str
) -> Tuple[Optional[np.ndarray], List[Tuple[TopicInfo, float]]]:
    """Compute an article's topic vector and topics without writing
    anything. Shared by the tagger and by tools/verify_topictagger.py,
    so the verification checks the code that actually runs."""
    vec = project_words(model, article_words(session, article_id))
    return vec, match_topics(vec, topics)


def tag_article(
    model: LsiModel,
    topics: List[TopicInfo],
    article_id: str,
    heading: Optional[str],
    verbose: bool = False,
    process_all: bool = False,
) -> None:
    """Assign a topic vector and topics to one article, in its own
    committed transaction"""
    with SessionContext(commit=True) as session:
        vec, found = compute_article(session, model, topics, article_id)
        if verbose:
            print("{0} : {1}".format(article_id, heading))
            if vec is not None:
                article = to_sparse(vec)
                for topic in topics:
                    print(
                        "   Similarity to topic {0} is {1:.3f}".format(
                            topic.name, cossim(article, topic.vector)
                        )
                    )
        if found and not process_all:
            print(
                "Article '{0}':\n   topics {1}".format(
                    heading, [(t.name, sim) for t, sim in found]
                )
            )
        # Replace any previous topics
        session.execute(
            ArticleTopic.table().delete().where(ArticleTopic.article_id == article_id)
        )
        for topic, _ in found:
            session.add(ArticleTopic(article_id=article_id, topic_id=topic.id))
        # Stamp the article as indexed and store its vector. The database
        # trigger derives topic_embedding from topic_vector.
        a = session.query(Article).filter(Article.id == article_id).one_or_none()
        if a is not None:
            a.indexed = _now()
            a.topic_vector = (
                json.dumps([float(x) for x in vec]) if vec is not None else None
            )


def selection_query(session: Session, process_all: bool, uuid: Optional[str]) -> Query:
    """The articles to tag: those never indexed, or parsed again since they
    were, and that have at least one row in the words table. This is the
    same set that builder.py assign_topics selects, but builder.py asks
    for it as a join to words grouped by article, and that form is slow.
    Postgres overestimates the candidates more than tenfold, so it plans
    a merge join that walks every article and the whole 11 GB words
    primary key on every run, about 200 s even when ten articles qualify.
    EXISTS gives a semi join that probes words once per candidate (2.6 s
    measured 2026-10-14). The order is unspecified in both forms, so
    under a limit, which articles come first may differ."""
    q = session.query(Article.id, Article.heading)
    if uuid:
        q = q.filter(Article.id == uuid)
    elif not process_all:
        q = q.filter((Article.indexed == None) | (Article.indexed < Article.parsed))
    return q.filter(exists().where(Word.article_id == Article.id))


def articles_to_tag(
    limit: Optional[int], process_all: bool, uuid: Optional[str]
) -> List[Tuple[str, Optional[str]]]:
    """Select the articles to tag; see selection_query"""
    with SessionContext(read_only=True) as session:
        q = selection_query(session, process_all, uuid)
        rows = q.all() if (uuid or limit is None) else q[0:limit]
        return [(str(article_id), heading) for article_id, heading in rows]


def tag_articles(
    limit: Optional[int],
    verbose: bool = False,
    process_all: bool = False,
    uuid: Optional[str] = None,
) -> int:
    """Tag the articles that need it. Returns a process exit code."""

    print("------ Greynir starting tagging -------")
    if uuid:
        print("Tagging article {0}".format(uuid))
    elif process_all:
        print("Processing all articles")
    elif limit:
        print("Limit: {0} articles".format(limit))
    print("Time: {0}".format(_timestamp()))

    t0 = time.time()

    model = LsiModel.get()
    if model is None:
        # LsiModel.get() has printed why. Fail loudly: a tagger that
        # quietly does nothing is how 2026-08-23 went unnoticed for weeks.
        print("Cannot tag without the LSI model in resources/lsi/", file=sys.stderr)
        return 1

    with SessionContext(read_only=True) as session:
        topics = load_topics(session)
    if not topics:
        print(
            "No topic vectors in the topics table; run 'topics' first",
            file=sys.stderr,
        )
        return 1

    articles = articles_to_tag(limit, process_all, uuid)
    for article_id, heading in articles:
        tag_article(model, topics, article_id, heading, verbose, process_all)

    t1 = time.time()

    print("\n------ Tagging completed -------")
    print("Articles tagged: {0}".format(len(articles)))
    print("Total time: {0:.2f} seconds".format(t1 - t0))
    print("Time: {0}\n".format(_timestamp()))
    return 0


# ---------------------------------------------------------------------------
# Topic vectors
# ---------------------------------------------------------------------------


class TopicSpec(NamedTuple):
    identifier: Optional[str]
    threshold: Optional[float]
    keywords: Set[str]


def read_topics_conf(fname: str = str(TOPICS_CONF)) -> Dict[str, TopicSpec]:
    """Read topic names, identifiers, thresholds and keywords from
    Topics.conf, applying the same rules as vectors/settings.py Topics.
    Raises ConfigError, with file and line, on a malformed file."""

    topics: Dict[str, TopicSpec] = {}
    current: Optional[str] = None
    in_topics = False

    rdr = LineReader(fname)
    try:
        for s in rdr.lines():
            ix = s.find("#")
            if ix >= 0:
                s = s[0:ix]
            s = s.strip()
            if not s:
                continue
            if s[0] == "[" and s[-1] == "]":
                section = s[1:-1].strip().lower()
                if section != "topics":
                    raise ConfigError("Unknown section name '{0}'".format(section))
                in_topics = True
                continue
            if not in_topics:
                raise ConfigError("No handler for config line '{0}'".format(s))
            a = s.split("=", maxsplit=1)
            if len(a) == 2:
                if a[0].strip().lower() != "topic":
                    raise ConfigError(
                        "Unknown setting '{0}' in topics".format(a[0].strip())
                    )
                # Format: topic = Topic name | identifier | threshold
                parts = a[1].split("|")
                current = parts[0].strip()
                identifier = parts[1].strip() if len(parts) > 1 else None
                if identifier is not None and not identifier.isidentifier():
                    raise ConfigError(
                        "Topic identifier must be a valid Python identifier"
                    )
                try:
                    threshold = float(parts[2].strip()) if len(parts) > 2 else None
                except ValueError:
                    raise ConfigError("Topic threshold must be a floating point number")
                keywords = topics[current].keywords if current in topics else set()
                topics[current] = TopicSpec(identifier, threshold, keywords)
                continue
            # A keyword, of the form word/cat
            if current is None:
                raise ConfigError(
                    "Must set topic name (topic = X) before specifying topic words"
                )
            if "/" not in s:
                raise ConfigError(
                    "Topic words must include a slash '/' and a word category"
                )
            if s.split("/", maxsplit=1)[1] not in TOPIC_KEYWORD_CATEGORIES:
                raise ConfigError(
                    "Topic words must be nouns, verbs, adjectives, entities or persons"
                )
            topics[current].keywords.add(s.replace(" ", "_"))
    except ConfigError as e:
        e.set_pos(rdr.fname(), rdr.line())
        raise
    return topics


def keywords_vector(model: LsiModel, keywords: List[str]) -> List[Tuple[int, float]]:
    """Project topic keywords into LSI space, in the sparse form that
    builder.py calculate_topics stored. Keywords are used as given, without
    w_from_stem, exactly as builder.py fed them to doc2bow."""
    vec, _ = model.project(keywords)
    return sorted(to_sparse(vec).items())


def calculate_topics(verbose: bool = False) -> int:
    """Recalculate the topic vectors in the topics table from their
    keywords, as builder.py calculate_topics does: a topic named in
    Topics.conf takes its keywords, identifier and threshold from there,
    any other topic keeps the keywords it has. Topics.conf entries with
    no row in the table are ignored, also as before. Returns an exit code."""

    print("------ Greynir recalculating topic vectors -------")
    model = LsiModel.get()
    if model is None:
        print("Cannot calculate topics without the LSI model", file=sys.stderr)
        return 1
    try:
        conf = read_topics_conf()
    except ConfigError as e:
        print("Configuration error: {0}".format(e), file=sys.stderr)
        return 2

    with SessionContext(commit=True) as session:
        for topic in session.query(Topic).all():
            spec = conf.get(topic.name)
            if spec is not None:
                # Sorted, where builder.py used set order: the keyword column
                # then stops reshuffling on every run. Order does not affect
                # the vector, which is a bag of words.
                keywords = sorted(spec.keywords)
                topic.keywords = " ".join(keywords)
                topic.identifier = spec.identifier
                topic.threshold = spec.threshold
            else:
                keywords = topic.keywords.split()
            if not all("/" in kw for kw in keywords):
                raise ValueError(
                    "Topic '{0}' has a keyword without a category".format(topic.name)
                )
            pairs = keywords_vector(model, keywords)
            if verbose:
                print(
                    "Topic {0}: {1} keywords, {2} vector components".format(
                        topic.name, len(keywords), len(pairs)
                    )
                )
            topic.vector = json.dumps({MODEL_NAME: pairs})

    print("------ Greynir recalculation complete -------")
    return 0


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------


class Usage(Exception):
    def __init__(self, msg: str) -> None:
        super().__init__(msg)
        self.msg = msg


__doc__ = """

    Greynir - Natural language processing for Icelandic

    Topic tagger module

    Usage:
        python topictagger.py [options] command [arguments]

    Options:
        -h, --help       : Show this help text
        -l N, --limit=N  : Limit processing to N articles
        -a, --all        : Process all articles
        -v, --verbose    : Show diagnostics while processing

    Commands:
        tag [uuid] : tag any untagged articles (or the article with the given uuid)
        topics     : recalculate topic vectors from keywords in vectors/Topics.conf

    Rebuilding the LSI model itself still needs gensim: see vectors/builder.py.

"""


def _main(argv: Optional[List[str]] = None) -> int:

    if argv is None:
        argv = sys.argv
    try:
        try:
            opts, args = getopt.getopt(
                argv[1:], "hl:van", ["help", "limit=", "verbose", "all", "notify"]
            )
            # -n/--notify is accepted as a no-op, as builder.py accepts it,
            # so the cron line can switch tagger without changing its options
        except getopt.error as msg:
            raise Usage(str(msg))

        limit_specified = False
        limit: Optional[int] = 10
        verbose = False
        process_all = False

        for o, a in opts:
            if o in ("-h", "--help"):
                print(__doc__)
                return 0
            elif o in ("-l", "--limit"):
                try:
                    limit = int(a)
                    limit_specified = True
                except ValueError:
                    pass
            elif o in ("-v", "--verbose"):
                verbose = True
            elif o in ("-a", "--all"):
                process_all = True

        try:
            Settings.read("config/Greynir.conf")
        except ConfigError as e:
            print("Configuration error: {0}".format(e), file=sys.stderr)
            return 2

        if not args:
            raise Usage("No command specified")

        la = len(args)
        arg = args[0]
        if arg == "tag":
            uuid = args[1] if la > 1 else None
            if la > (1 if uuid is None else 2):
                raise Usage("Too many arguments")
            if uuid:
                if process_all:
                    raise Usage("Conflict between uuid argument and --all option")
                if limit_specified:
                    raise Usage("Conflict between uuid argument and --limit option")
            if process_all and not limit_specified:
                limit = None
            return tag_articles(
                limit=limit, verbose=verbose, process_all=process_all, uuid=uuid
            )
        elif arg == "topics":
            if la > 1:
                raise Usage("Too many arguments")
            return calculate_topics(verbose=verbose)
        elif arg == "model":
            raise Usage(
                "Rebuilding the LSI model needs gensim; use vectors/builder.py model"
            )
        else:
            raise Usage("Unknown command: '{0}'".format(arg))

    except Usage as err:
        print(err.msg, file=sys.stderr)
        print("For help use --help", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(_main())
