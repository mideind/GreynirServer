"""

    Greynir: Natural language processing for Icelandic

    Topic vector module

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


    This module projects search terms into the LSI topic vector space,
    replacing the corresponding functionality of the similarity server
    (ReynirCorpus.get_topic_vector in vectors/builder.py). It is a faithful
    reimplementation of the gensim tf-idf + LSI pipeline in plain numpy --
    a dictionary lookup, an idf weighting with L2 normalization, and one
    matrix product against the LSI projection -- because gensim 3.8 cannot
    run on modern CPython and a gensim 4 port was judged not worth it for
    this much linear algebra (PLAN.md phase 3).

    The model files are exported from the gensim originals by
    tools/export_lsi_model.py into resources/lsi/ (gitignored, deployed
    out-of-band like API keys):

        token2id.json   token -> term id, from the gensim dictionary
        idfs.npy        idf weight per term id, float32
        u.npy           LSI projection matrix (num_terms x 200), float32
        meta.json       dimensions and provenance
        reference.json  gensim-computed outputs for sample inputs, used by
                        the export verification (not loaded at runtime)

    The projection matrix is loaded with mmap_mode="r", so concurrent
    gunicorn workers share its pages through the page cache instead of
    each holding a private 66 MB copy.

"""

from typing import Dict, List, Optional, Tuple

import json
import threading

import numpy as np

from settings import NoIndexWords
from db import Session
from db.sql import TermTopicsQuery
from utility import RESOURCES_DIR

# The exported model files live here; see tools/export_lsi_model.py
LSI_DIR = RESOURCES_DIR / "lsi"


def w_from_stem(stem: str, cat: str) -> str:
    """Convert a (stem, cat) tuple to a bag-of-words key, exactly as
    vectors/builder.py does when building the model"""
    return stem.lower().replace("-", "").replace(" ", "_") + "/" + cat


class LsiModel:

    """Lazily loaded, process-wide singleton holding the exported LSI
    model components"""

    _lock = threading.Lock()
    _instance: Optional["LsiModel"] = None
    _load_failed = False

    def __init__(self) -> None:
        with open(LSI_DIR / "meta.json", encoding="utf-8") as f:
            meta = json.load(f)
        self.dimensions: int = meta["dimensions"]
        with open(LSI_DIR / "token2id.json", encoding="utf-8") as f:
            self.token2id: Dict[str, int] = json.load(f)
        self.idfs: np.ndarray = np.load(LSI_DIR / "idfs.npy")
        self.u: np.ndarray = np.load(LSI_DIR / "u.npy", mmap_mode="r")
        assert self.u.shape[1] == self.dimensions
        assert len(self.idfs) <= self.u.shape[0]

    @classmethod
    def get(cls) -> Optional["LsiModel"]:
        """Return the singleton, or None if the model files are absent --
        in which case search-by-terms is unavailable, mirroring how an
        unreachable similarity server used to behave"""
        if cls._instance is not None:
            return cls._instance
        if cls._load_failed:
            return None
        with cls._lock:
            if cls._instance is None and not cls._load_failed:
                try:
                    cls._instance = LsiModel()
                except Exception as e:
                    print(
                        "Unable to load LSI model from {0}: {1}".format(LSI_DIR, e)
                    )
                    cls._load_failed = True
        return cls._instance

    def project(self, tokens: List[str]) -> Tuple[np.ndarray, int]:
        """Project a token list into LSI space, replicating gensim's
        doc2bow -> TfidfModel -> LsiModel pipeline. Returns the dense
        topic vector and the number of distinct in-dictionary tokens
        (gensim's len(bag), needed for the blend weighting below)."""
        counts: Dict[int, int] = {}
        for tok in tokens:
            tid = self.token2id.get(tok)
            if tid is not None:
                counts[tid] = counts.get(tid, 0) + 1
        if not counts:
            return np.zeros(self.dimensions), 0
        ids = np.fromiter(counts.keys(), dtype=np.int64)
        tfs = np.fromiter(counts.values(), dtype=np.float64)
        # gensim TfidfModel: weight = tf * idf, then L2 normalization
        weights = tfs * self.idfs[ids].astype(np.float64)
        norm = float(np.linalg.norm(weights))
        if norm > 0.0:
            weights /= norm
        # gensim LsiModel: topic vector = u^T x (unscaled)
        vec = (weights[:, np.newaxis] * self.u[ids].astype(np.float64)).sum(axis=0)
        return vec, len(counts)


def terms_to_vector(
    session: Session, terms: List[Tuple[str, str]]
) -> Tuple[Optional[np.ndarray], List[float]]:
    """Calculate a topic vector corresponding to the given list of search
    terms, which are assumed to have the form (stem, category). Returns
    the topic vector and a list of weights, one per search term. Returns
    (None, []) if the LSI model is unavailable.

    This is a faithful port of ReynirCorpus.get_topic_vector in
    vectors/builder.py: terms found in the LSI dictionary are projected
    directly; person and entity names, and rare terms missing from the
    dictionary, are instead looked up in the words table and represented
    by the weighted average of the topic vectors of recent documents
    where they appear."""
    model = LsiModel.get()
    if model is None:
        return None, []

    wlist = [w_from_stem(stem, cat) for stem, cat in terms]
    topic_vector, lb = model.project(wlist)

    dims = model.dimensions
    missing = np.zeros(dims)
    weight_missing = 0.0
    term_weights: List[float] = []

    for index, (stem, cat) in enumerate(terms):

        def word_lookup_weight(stem: str, cat: str) -> float:
            """Does this term call for a lookup in the words database table?"""
            if cat == "entity" or cat.startswith("person"):
                # We look up all entity and person names
                # and give them extra weight
                return 2.0
            if cat in {"kk", "kvk", "hk"} and stem[0].isupper() and index > 0:
                # Noun starting with a capital letter, not the first word
                # in a sentence: assume it's a proper name and do a lookup
                # with a weight of 1.6
                return 1.6
            # Without further reason, we don't look up terms that already
            # exist in the LSI model dictionary. For other terms, they
            # appear to be rare and we give them a slight overweight if
            # they are found in the words table.
            return 0.0 if w_from_stem(stem, cat) in model.token2id else 1.2

        weight = word_lookup_weight(stem, cat)

        if weight == 0.0:
            # The word is in the LSI model dictionary and not special in
            # any way; from the overall search term point of view, it gets
            # a weight of 1.0
            term_weights.append(1.0)
            continue

        if (
            cat in NoIndexWords.CATEGORIES_TO_INDEX
            and (stem, cat) not in NoIndexWords.SET
        ):
            # We have a significant (potentially indexable) person, entity,
            # noun, adjective or verb. Give it a weight in the final
            # topic vector.

            def clean(stem: str) -> str:
                """Eliminate composite word hyphens from the stem"""
                if "- og " in stem or "- eða " in stem:
                    # Leave 'iðnaðar- og viðskiptaráðuneyti' alone
                    return stem
                # We want to keep other types of hyphens (surrounded by
                # spaces) such as 'Vestur - Íslendingar'
                a = stem.split(" - ")
                return " - ".join(p.replace("-", "") for p in a)

            q = TermTopicsQuery().execute(
                session, stem=clean(stem), cat=cat, limit=25
            )
            term_vector = np.zeros(dims)
            total_cnt = 0
            # Sum up the topic vectors of the documents where the term
            # appears, weighted by the number of times it appears
            for tv_json, cnt in q:
                if tv_json and cnt:
                    tv = json.loads(tv_json)
                    if len(tv) != dims:
                        # A handful of stored topic vectors are malformed
                        # (199 elements instead of 200, from a gensim
                        # sparse-output quirk); builder.py would crash on
                        # these -- skip them instead
                        continue
                    total_cnt += cnt
                    term_vector += np.array(tv) * cnt
            # Add the combined (weighted average) topic vector of the
            # term to the 'missing' topic vector
            if total_cnt > 0:
                missing += (term_vector / total_cnt) * weight
                # Keep track of how many 'missing' terms have contributed
                # to the missing term vector
                weight_missing += weight
                term_weights.append(weight)
            else:
                # Not found in the words table: this term contributes nothing
                term_weights.append(0.0)
        else:
            term_weights.append(0.0)

    assert len(terms) == len(term_weights)

    if weight_missing > 0.0:
        # Adjust the weight of the returned topic vector so that the
        # missing terms have a contribution that corresponds to their number
        p_tv = lb / (lb + weight_missing)
        # Calculate the relative contribution of the missing terms
        p_m = 1.0 - p_tv
        # Amalgamate the resulting topic vector
        topic_vector = topic_vector * p_tv + missing * p_m

    return topic_vector, term_weights
