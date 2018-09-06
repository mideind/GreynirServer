#!/usr/bin/env/python
# coding=utf-8

"""
    Reynir: Natural language processing for Icelandic

    Neural Network Parsing Encoder

    Copyright (C) 2018 Vilhjálmur Þorsteinsson

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


    This module implements composite subword encoder for parsing tokens.

"""

from tensor2tensor.data_generators import text_encoder
import tensorflow as tf


def _preprocess_word_v2(word):
    return (
        word.strip()
        .replace("_lhþt", "_lh_þt")
        .replace("_hvk", "_hk")
        .replace("_hk_hk", "_hk")
    )

def _preprocess_word(word):
    return (
        word.strip()
        .replace("_lh_nt", "_lhnt")
        .replace("_hvk", "_hk")
        .replace("_hk_hk", "_hk")
    )


CASE_TOKS = set(["nf", "þf", "þgf", "ef"])
DEFAULT_PATH = "parsing_tokens.txt"
DEFAULT_PATH_V2 = "parsing_tokens_180729.txt"
UNK = "<UNK>"

EOS_ID = text_encoder.EOS_ID
MISSING = ["NP-AGE", "ADVP-DUR"]
MISSING.extend(["/" + t for t in MISSING])
MISSING = set(t for t in MISSING)


class CompositeTokenEncoder(text_encoder.TextEncoder):
    """Build vocabulary from composite token vocabulary

    Read composite vocabulary and extract subtokens according to simple
    right recursive rule (regular) with a handful a couple of exceptions

    Behaves otherwise similarly to subword encoders
    """

    def __init__(self, filename=None, reorder=True, version=1):
        if filename is None:
            self.filename = DEFAULT_PATH if version==1 else DEFAULT_PATH_V2
        else:
            self.filename = filename
        self._init_token_set()
        self._num_reserved_ids = len(text_encoder.RESERVED_TOKENS)
        self._reorder = reorder
        self._version = version
        self._preprocess_word = _preprocess_word if version == 1 else _preprocess_word_v2

    def _init_token_set(self):
        all_tokens = []
        with tf.gfile.Open(self.filename) as f:
            all_tokens = [_preprocess_word_v2(l) for l in f.readlines()]

        full_toks = {t for t in all_tokens if "_" not in t}
        raw_tokens = {t for t in all_tokens if "_" in t}

        head_toks = set()
        tail_toks = set()
        for rt in raw_tokens:
            toks = rt.split("_")
            head, t1 = toks[:2]
            tail = toks[2:]

            if t1 in ["0", "1", "2", "subj"]:
                head = head + "_" + t1
            else:
                tail.append(t1)

            tail_toks.update(tail)
            head_toks.add(head)

        self._nonterminals = {t for t in all_tokens if t == t.upper()}
        self._nonterm_l = {t for t in self._nonterminals if "/" not in t}
        self._nonterm_r = self._nonterminals - self._nonterm_l
        self._terminals = (head_toks | full_toks | tail_toks) - self._nonterminals
        self._r_to_l = {"/" + t: t for t in self._nonterm_l}

        full_toks, head_toks, tail_toks = [
            sorted(list(l)) for l in [full_toks, head_toks, tail_toks]
        ]

        self._tok_id_to_tok_str = {
            tid: tok
            for (tid, tok) in enumerate(
                full_toks + head_toks + [("_" + t) for t in tail_toks] + [UNK]
            )
        }

        N_FULL, N_HEAD, N_TAIL = [len(s) for s in [full_toks, head_toks, tail_toks]]

        self._ftok_to_tok_id = {tok: i for (i, tok) in enumerate(full_toks)}
        self._htok_to_tok_id = {tok: (i + N_FULL) for (i, tok) in enumerate(head_toks)}
        self._ttok_to_tok_id = {
            tok: (i + N_FULL + N_HEAD) for (i, tok) in enumerate(tail_toks)
        }
        self.oov_id = N_FULL + N_HEAD + N_TAIL

    @property
    def num_reserved_ids(self):
        return self._num_reserved_ids

    def _token_to_subtoken_ids(self, word):
        word = _preprocess_word_v2(word)
        if word in self._ftok_to_tok_id:
            return [self._ftok_to_tok_id[word]]
        if "_" not in word:
            return [self.oov_id]
        toks = word.split("_")
        head, t1 = toks[:2]
        tail = toks[2:]

        tail_start = 0
        if t1 in ["0", "1", "2", "subj"]:
            head = head + "_" + t1
            tail_start += 0 if t1 == "subj" else int(t1)
        else:
            tmp = [t1]
            tmp.extend(tail)
            tail = tmp

        if head not in self._htok_to_tok_id or not all(
            [t in self._ttok_to_tok_id for t in tail]
        ):
            return [self.oov_id]

        ids = [self._htok_to_tok_id[head]]
        tail = [self._ttok_to_tok_id[t] for t in tail]
        if self._reorder:
            tail[tail_start:] = sorted(tail[tail_start:])
        ids.extend(tail)
        return ids

    def token_to_subtokens(self, word):
        remove_slash = lambda t: t if t[0] != "_" else t[1:]
        subtokens = [
            remove_slash(self._tok_id_to_tok_str[t])
            for t in self._token_to_subtoken_ids(word)
        ]
        return subtokens

    def _tokens_to_subtoken_ids(self, words):
        numres = self._num_reserved_ids
        result = []
        for word in words:
            ids = [(i + numres) for i in self._token_to_subtoken_ids(word)]
            result.extend(ids)
            # if self.oov_id+numres in result:
            #     print("unexpected subtoken: '{0}' in {1}".format(word, " ".join(words)))
        return result

    def encode(self, string):
        result = self._tokens_to_subtoken_ids(list(string.split(" ")))
        return result

    def decode(self, ids):
        numres = self._num_reserved_ids
        RES_TOKENS = text_encoder.RESERVED_TOKENS
        result = []
        for idx in range(len(ids)):
            tid = ids[idx]
            if 0 <= tid < numres:
                result.append(RES_TOKENS[tid])
                continue

            tid -= numres
            result.append(self._tok_id_to_tok_str[tid])
            is_full_tok = tid in self._ftok_to_tok_id.values()
            end_of_tail = tid in self._ttok_to_tok_id.values()
            is_oov = tid == self.oov_id
            end_of_tail &= (
                idx + 1 < len(ids)
                and (ids[idx + 1] - numres) not in self._ttok_to_tok_id.values()
            )
            if is_full_tok or end_of_tail or is_oov:
                result.append(" ")
        return "".join(result).strip()

    def decode_list(self, ids):
        numres = self._num_reserved_ids
        RES_TOKENS = text_encoder.RESERVED_TOKENS
        result = []
        for idx in range(len(ids)):
            tid = ids[idx]
            if 0 <= tid < numres:
                result.append(RES_TOKENS[tid])
                continue
            tid = tid - numres
            tok = self._tok_id_to_tok_str[tid]
            tok = tok + "_" if tid in self._htok_to_tok_id else tok
            result.append(tok)
        return result

    @property
    def vocab_size(self):
        return (
            self._num_reserved_ids
            + len(self._ftok_to_tok_id)
            + len(self._htok_to_tok_id)
            + len(self._ttok_to_tok_id)
        )
