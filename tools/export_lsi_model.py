#!/usr/bin/env python
"""
    Greynir: Natural language processing for Icelandic

    LSI model exporter

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


    Exports the components of the gensim LSI model that are needed at query
    time -- the dictionary's token-to-id mapping, the tf-idf idf weights,
    and the LSI projection matrix -- as plain JSON/numpy files that
    topicvector.py can load without gensim. This is what lets the terms
    path of the search feature run on modern CPython: gensim 3.8 cannot
    (see PLAN.md phase 3).

    This script itself MUST run under the CPython 3.9 venv in vectors/,
    which has gensim, and with the vectors directory as cwd, because
    reynir.dict was pickled as a builder.ReynirDictionary and unpickling
    imports the builder module (which in turn wants vectors/settings.py):

        cd /home/greynir/github/Greynir/vectors
        ./venv/bin/python /home/villi/github/GreynirServer/tools/export_lsi_model.py \\
            --out /home/villi/github/GreynirServer/resources/lsi

    Besides the export, it writes reference.json: sample token lists with
    the gensim-computed topic vectors for them. verify_lsi_export.py (or an
    ad-hoc check) replays those through topicvector.py to prove that the
    gensim-free reimplementation reproduces gensim's output exactly.

"""

import argparse
import json
import os
import sys

import numpy as np


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="./models", help="gensim model directory")
    ap.add_argument("--out", required=True, help="output directory")
    ap.add_argument("--dimensions", type=int, default=200)
    args = ap.parse_args()

    # Imported late so --help works anywhere
    sys.path.insert(0, ".")
    from gensim import corpora, models  # noqa: E402

    print("Loading dictionary")
    dic = corpora.Dictionary.load(os.path.join(args.models, "reynir.dict"))
    print("Loading tf-idf model")
    tfidf = models.TfidfModel.load(os.path.join(args.models, "tfidf.model"), mmap="r")
    print("Loading LSI model")
    lsi = models.LsiModel.load(
        os.path.join(args.models, "lsi-{0}.model".format(args.dimensions)), mmap="r"
    )

    num_terms = len(dic.token2id)
    u = np.asarray(lsi.projection.u)
    assert u.shape[1] == args.dimensions, u.shape
    # The projection may cover more terms than the dictionary if the
    # dictionary was ever filtered after training; the reverse would be
    # an error
    assert u.shape[0] >= num_terms, (u.shape, num_terms)

    idfs = np.zeros(num_terms, dtype=np.float32)
    for termid, idf in tfidf.idfs.items():
        if termid < num_terms:
            idfs[termid] = idf

    os.makedirs(args.out, exist_ok=True)

    print("Writing token2id.json ({0} terms)".format(num_terms))
    with open(os.path.join(args.out, "token2id.json"), "w", encoding="utf-8") as f:
        json.dump(dic.token2id, f, ensure_ascii=False)

    print("Writing idfs.npy")
    np.save(os.path.join(args.out, "idfs.npy"), idfs)

    print("Writing u.npy as float32 {0}".format(u.shape))
    np.save(os.path.join(args.out, "u.npy"), u.astype(np.float32))

    with open(os.path.join(args.out, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(
            dict(
                num_terms=num_terms,
                dimensions=args.dimensions,
                u_rows=int(u.shape[0]),
                source=os.path.abspath(args.models),
            ),
            f,
            indent=2,
        )

    # Reference cases: deterministic samples of dictionary tokens, various
    # lengths, with repeats, plus edge cases (unknown token, empty list).
    # For each, record gensim's own tfidf -> LSI output as a dense vector.
    print("Writing reference.json")
    tokens_by_id = {v: k for k, v in dic.token2id.items()}
    rng = np.random.RandomState(42)
    cases = []
    for length in (1, 2, 3, 5, 10, 30, 100):
        for trial in range(3):
            ids = rng.randint(0, num_terms, size=length)
            toklist = [tokens_by_id[int(i)] for i in ids]
            if trial == 2:
                # Add repeats and an out-of-vocabulary token
                toklist = toklist + toklist[: max(1, length // 2)]
                toklist.append("úlfakreppa_í_þokunni/hk")
            bow = dic.doc2bow(toklist)
            dense = np.zeros(args.dimensions)
            if bow:
                for ix, val in lsi[tfidf[bow]]:
                    dense[ix] = val
            cases.append(dict(tokens=toklist, vector=[float(x) for x in dense]))
    cases.append(dict(tokens=["úlfakreppa_í_þokunni/hk"], vector=[0.0] * args.dimensions))
    with open(os.path.join(args.out, "reference.json"), "w", encoding="utf-8") as f:
        json.dump(cases, f, ensure_ascii=False)

    print("Export complete: {0}".format(args.out))


if __name__ == "__main__":
    main()
