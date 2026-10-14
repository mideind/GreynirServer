"""

    Greynir: Natural language processing for Icelandic

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


    Tests for topictagger.py, the gensim-free topic tagger.

    These need neither the database nor the exported LSI model, which is
    deployed out-of-band and absent in CI: they use a small synthetic
    model. Equivalence with gensim on the real model is established by
    tools/verify_topictagger.py against the vectors builder.py stored.

"""

import math
import os
import random
import sys
from typing import Dict, List, Tuple

import numpy as np
import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session as OrmSession

# Shenanigans to enable Pytest to discover modules in the
# main workspace directory (the parent of /tests)
basepath, _ = os.path.split(os.path.realpath(__file__))
mainpath = os.path.join(basepath, "..")
if mainpath not in sys.path:
    sys.path.insert(0, mainpath)

import topictagger as tt  # noqa: E402
from reynir.basics import ConfigError  # noqa: E402
from topicvector import LsiModel  # noqa: E402


def _gensim_cossim(vec1: List[Tuple[int, float]], vec2: List[Tuple[int, float]]) -> float:
    """gensim 3.8 matutils.cossim, transcribed, as the reference"""
    d1, d2 = dict(vec1), dict(vec2)
    if not d1 or not d2:
        return 0.0
    len1 = 1.0 * math.sqrt(sum(v * v for v in d1.values()))
    len2 = 1.0 * math.sqrt(sum(v * v for v in d2.values()))
    if len(d2) < len(d1):
        d1, d2 = d2, d1
    return sum(v * d2.get(i, 0.0) for i, v in d1.items()) / (len1 * len2)


def _synthetic_model() -> LsiModel:
    """A four-term, three-dimension LsiModel without reading any files"""
    model = LsiModel.__new__(LsiModel)
    model.dimensions = 3
    model.token2id = {"hestur/kk": 0, "kýr/kvk": 1, "hlaupa/so": 2, "rauður/lo": 3}
    model.idfs = np.array([1.0, 2.0, 0.5, 0.0], dtype=np.float32)
    model.u = np.array(
        [[0.5, 0.1, 0.0], [0.2, -0.3, 0.4], [0.0, 0.6, 0.1], [0.9, 0.9, 0.9]],
        dtype=np.float32,
    )
    return model


def test_to_sparse_drops_at_gensims_cutoff() -> None:
    vec = np.array([0.0, 1e-9, -1e-9, 1.1e-9, -0.5, 2.0])
    # full2sparse keeps a component only if its magnitude is above 1e-9
    assert tt.to_sparse(vec) == {3: 1.1e-9, 4: -0.5, 5: 2.0}
    assert tt.to_sparse(np.zeros(4)) == {}


def test_cossim_matches_gensim() -> None:
    rng = random.Random(20261013)
    for _ in range(200):
        a = [(i, rng.uniform(-1, 1)) for i in sorted(rng.sample(range(50), rng.randint(1, 50)))]
        b = [(i, rng.uniform(-1, 1)) for i in sorted(rng.sample(range(50), rng.randint(1, 50)))]
        # Bit-for-bit, not approximately: thresholds are compared with >=
        assert tt.cossim(dict(a), dict(b)) == _gensim_cossim(a, b)
        assert tt.cossim(dict(b), dict(a)) == _gensim_cossim(b, a)
    assert tt.cossim({}, {0: 1.0}) == 0.0
    assert tt.cossim({0: 1.0}, {}) == 0.0


def test_project_words_tfidf_and_projection() -> None:
    model = _synthetic_model()
    wlist = ["hestur/kk", "hestur/kk", "kýr/kvk", "óþekkt/hk"]
    vec = tt.project_words(model, wlist)
    assert vec is not None
    # tf * idf, L2-normalised, then u^T x; the unknown word is ignored
    w = np.array([2 * 1.0, 1 * 2.0])
    w = w / np.linalg.norm(w)
    expected = w[0] * model.u[0].astype(np.float64) + w[1] * model.u[1].astype(np.float64)
    assert np.allclose(vec, expected, atol=1e-12)


def test_project_words_none_where_builder_stored_none() -> None:
    model = _synthetic_model()
    assert tt.project_words(model, []) is None
    # No word in the dictionary: gensim's bag is empty
    assert tt.project_words(model, ["óþekkt/hk", "annað/hk"]) is None
    # Only a word whose idf is zero: tf-idf drops it, the vector is empty
    assert tt.project_words(model, ["rauður/lo"]) is None


def test_match_topics_threshold_is_inclusive() -> None:
    vec = np.array([1.0, 0.0, 0.0])
    exact = tt.TopicInfo("t1", "Exact", 1.0, {0: 3.0})
    below = tt.TopicInfo("t2", "Below", 0.5, {1: 1.0})
    above = tt.TopicInfo("t3", "Above", 0.7, {0: 1.0, 1: 1.0})
    found = tt.match_topics(vec, [exact, below, above])
    assert [(t.id, round(s, 12)) for t, s in found] == [
        ("t1", 1.0),
        ("t3", round(1 / math.sqrt(2), 12)),
    ]
    assert tt.match_topics(None, [exact]) == []


def test_keywords_vector_is_builders_sparse_format() -> None:
    model = _synthetic_model()
    pairs = tt.keywords_vector(model, ["kýr/kvk", "hlaupa/so"])
    assert [i for i, _ in pairs] == sorted(i for i, _ in pairs)
    assert all(isinstance(i, int) and isinstance(f, float) for i, f in pairs)
    assert tt.keywords_vector(model, ["óþekkt/hk"]) == []


def test_read_topics_conf_real_file() -> None:
    topics = tt.read_topics_conf()
    assert len(topics) == 11
    for name, spec in topics.items():
        assert spec.identifier is not None and spec.identifier.isidentifier(), name
        assert spec.threshold is not None and 0.0 < spec.threshold < 1.0, name
        assert spec.keywords, name
        assert all("/" in kw and " " not in kw for kw in spec.keywords), name
    assert topics["Íþróttir"].identifier == "sport"
    assert "íþrótt/kvk" in topics["Íþróttir"].keywords


@pytest.mark.parametrize(
    "body",
    [
        "íþrótt/kvk\n",  # keyword before any topic
        "topic = Íþróttir | sport | 0.22\níþrótt\n",  # no category
        "topic = Íþróttir | sport | 0.22\níþrótt/xx\n",  # bad category
        "topic = Íþróttir | not an identifier | 0.22\n",
        "topic = Íþróttir | sport | high\n",
        "name = Íþróttir\n",  # unknown setting
    ],
)
def test_read_topics_conf_rejects_malformed(tmp_path, body: str) -> None:
    conf = tmp_path / "Topics.conf"
    conf.write_text("[topics]\n" + body, encoding="utf-8")
    with pytest.raises(ConfigError):
        tt.read_topics_conf(str(conf))


def test_read_topics_conf_rejects_unknown_section(tmp_path) -> None:
    conf = tmp_path / "Topics.conf"
    conf.write_text("[settings]\ndebug = true\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        tt.read_topics_conf(str(conf))


def test_read_topics_conf_spaces_and_repeats(tmp_path) -> None:
    conf = tmp_path / "Topics.conf"
    conf.write_text(
        "[topics]\n"
        "topic = Veður | weather | 0.22   # comment\n"
        "rigning/kvk\n"
        "Veðurstofa Íslands/entity\n"
        "topic = Veður | weather | 0.3\n"
        "vindur/kk\n",
        encoding="utf-8",
    )
    topics: Dict[str, tt.TopicSpec] = tt.read_topics_conf(str(conf))
    # A repeated heading keeps the keywords and takes the later settings,
    # as vectors/settings.py does; spaces become underscores
    assert topics["Veður"].threshold == 0.3
    assert topics["Veður"].keywords == {
        "rigning/kvk",
        "Veðurstofa_Íslands/entity",
        "vindur/kk",
    }


def _selection_sql(process_all: bool, uuid=None) -> str:
    # An unbound session builds and compiles the query without a database
    q = tt.selection_query(OrmSession(), process_all, uuid)
    return " ".join(str(q.statement.compile(dialect=postgresql.dialect())).split())


def test_selection_is_a_semi_join_not_a_grouped_join() -> None:
    # The join-and-group form that builder.py uses makes Postgres walk the
    # whole words table on every run; the set is the same either way
    for args in ((False,), (True,), (False, "00000000-0000-0000-0000-000000000000")):
        sql = _selection_sql(*args)
        assert "EXISTS (SELECT * FROM words WHERE words.article_id = articles.id)" in sql
        assert "JOIN" not in sql and "GROUP BY" not in sql


def test_selection_filters() -> None:
    backlog = "articles.indexed IS NULL OR articles.indexed < articles.parsed"
    assert backlog in _selection_sql(False)
    assert backlog not in _selection_sql(True)
    by_id = _selection_sql(False, "00000000-0000-0000-0000-000000000000")
    assert "articles.id = %(id_1)s" in by_id and backlog not in by_id
