#!/usr/bin/env python3
"""

    Greynir: Natural language processing for Icelandic

    Topic tagger verification tool

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


    Compares what topictagger.py computes with what vectors/builder.py
    stored, for random samples of articles, and writes nothing: every query
    runs in a READ ONLY transaction, so an accidental write fails instead of
    landing in the live database. It calls topictagger.compute_article, the
    function the tagger itself uses, so it checks the code that runs.

    Only articles with indexed >= parsed are sampled. For those the words
    table is what the stored vector was computed from; an article parsed
    again since its tagging is waiting to be re-tagged and proves nothing.

    The samples are taken by when the stored vector was written:

      recent    since --since (default: the last 24 hours). Written by
                builder.py against today's words table and today's model
                files, so this is the definitive comparison: it must match
                exactly, and the exit code reflects this stratum only.
      historic  2023-05-03 up to --since. The model files date from
                2023-05-03, so these were written with the same model, but
                the words table may have been rewritten since without a
                re-parse, so a mismatch here is evidence, not a verdict.
      pre-2023  before 2023-05-03, possibly from an earlier model.
                Informational: tells whether those vectors share the space.

    Usage, from the repository root, with the pipeline's environment:
        GREYNIR_DB_HOST=greynir.is venv/bin/python tools/verify_topictagger.py

"""

from typing import Dict, List, Optional, Set, Tuple

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import numpy as np

# Allow running from the tools directory as well as the repository root
basepath, _ = os.path.split(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(basepath, ".."))

from sqlalchemy import text  # noqa: E402

from settings import Settings  # noqa: E402
from db import SessionContext, Session  # noqa: E402
from topicvector import LsiModel  # noqa: E402
import topictagger as tt  # noqa: E402

MODEL_DATE = "2023-05-03"


def sample_ids(session: Session, where: str, n: int) -> List[str]:
    """A random sample of taggable articles satisfying a condition"""
    q = text(
        "select a.id from articles a "
        "where a.indexed is not null and a.indexed >= a.parsed and ({0}) "
        "and exists (select 1 from words w where w.article_id = a.id) "
        "order by random() limit :n".format(where)
    )
    return [str(r[0]) for r in session.execute(q, {"n": n})]


def stored(session: Session, article_id: str) -> Tuple[Optional[List[float]], Set[str]]:
    """The topic vector and topic ids that builder.py stored"""
    row = session.execute(
        text("select topic_vector from articles where id = :id"), {"id": article_id}
    ).first()
    vector = json.loads(row[0]) if row is not None and row[0] else None
    topics = {
        str(r[0])
        for r in session.execute(
            text("select topic_id from atopics where article_id = :id"),
            {"id": article_id},
        )
    }
    return vector, topics


def compare(
    session: Session,
    model: LsiModel,
    topics: List[tt.TopicInfo],
    ids: List[str],
    tol: float,
) -> Dict[str, object]:
    by_id = {t.id: t for t in topics}
    counts = {"vector_ok": 0, "topics_ok": 0, "malformed_stored": 0}
    worst = 0.0
    problems: List[str] = []
    for article_id in ids:
        new_vec, found = tt.compute_article(session, model, topics, article_id)
        old_vec, old_topics = stored(session, article_id)
        new_topics = {t.id for t, _ in found}

        if old_vec is not None and len(old_vec) != model.dimensions:
            # builder.py's misaligned 199-element vectors: nothing to compare
            counts["malformed_stored"] += 1
            continue

        if new_vec is None and old_vec is None:
            counts["vector_ok"] += 1
        elif new_vec is None or old_vec is None:
            problems.append(
                "{0}: vector present old={1} new={2}".format(
                    article_id, old_vec is not None, new_vec is not None
                )
            )
        else:
            diff = float(np.max(np.abs(np.array(old_vec) - new_vec)))
            worst = max(worst, diff)
            if diff <= tol:
                counts["vector_ok"] += 1
            else:
                problems.append("{0}: max |diff| {1:.3e}".format(article_id, diff))

        if new_topics == old_topics:
            counts["topics_ok"] += 1
        else:
            # Show how close each disputed topic is to its threshold, which
            # separates a rounding-level tie from a real disagreement
            article = tt.to_sparse(new_vec) if new_vec is not None else {}
            detail = []
            for tid in sorted(new_topics ^ old_topics):
                t = by_id.get(tid)
                if t is None:
                    detail.append("{0}: unknown topic".format(tid))
                    continue
                sim = tt.cossim(article, t.vector)
                detail.append(
                    "{0} old={1} new={2} sim={3:.6f} thr={4}".format(
                        t.name, tid in old_topics, tid in new_topics, sim, t.threshold
                    )
                )
            problems.append("{0}: topics differ: {1}".format(article_id, "; ".join(detail)))

    return dict(
        sampled=len(ids),
        worst_abs_diff=worst,
        problems=problems,
        **counts,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("-n", "--sample", type=int, default=2000, help="articles per stratum")
    ap.add_argument("--tol", type=float, default=1e-6, help="max abs component difference")
    ap.add_argument(
        "--since",
        default=None,
        help="start of the 'recent' stratum, e.g. '2026-10-13 11:00' (UTC); default 24h ago",
    )
    ap.add_argument("--show", type=int, default=10, help="problems to print per stratum")
    args = ap.parse_args()

    Settings.read("config/Greynir.conf")
    model = LsiModel.get()
    if model is None:
        print("LSI model not found in resources/lsi/", file=sys.stderr)
        return 2

    since = args.since or (datetime.now(timezone.utc) - timedelta(hours=24)).strftime(
        "%Y-%m-%d %H:%M"
    )
    strata = [
        ("recent", "a.indexed >= timestamp '{0}'".format(since)),
        (
            "historic",
            "a.indexed >= timestamp '{0}' and a.indexed < timestamp '{1}'".format(
                MODEL_DATE, since
            ),
        ),
        ("pre-2023", "a.indexed < timestamp '{0}'".format(MODEL_DATE)),
    ]

    rc = 0
    with SessionContext(read_only=True) as session:
        topics = tt.load_topics(session)
        print("{0} topics loaded; tolerance {1:g}\n".format(len(topics), args.tol))
        for name, where in strata:
            ids = sample_ids(session, where, args.sample)
            r = compare(session, model, topics, ids, args.tol)
            compared = r["sampled"] - r["malformed_stored"]  # type: ignore
            print(
                "{0:9s} sampled {1:5d}  vectors {2}/{3}  topics {4}/{3}  "
                "worst |diff| {5:.2e}  malformed stored {6}".format(
                    name,
                    r["sampled"],
                    r["vector_ok"],
                    compared,
                    r["topics_ok"],
                    r["worst_abs_diff"],
                    r["malformed_stored"],
                )
            )
            problems: List[str] = r["problems"]  # type: ignore
            for p in problems[: args.show]:
                print("    " + p)
            if len(problems) > args.show:
                print("    ... and {0} more".format(len(problems) - args.show))
            if name == "recent" and (
                problems or r["sampled"] == 0  # an empty sample proves nothing
            ):
                rc = 1
        session.rollback()
    print("\nRESULT: {0}".format("PASS" if rc == 0 else "FAIL (recent stratum)"))
    return rc


if __name__ == "__main__":
    sys.exit(main())
