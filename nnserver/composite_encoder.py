#!/usr/bin/env/python
# coding=utf-8

"""
    Reynir: Natural language processing for Icelandic

    Neural Network Parsing Encoder

    Copyright (C) 2018 Miðeind ehf.

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


    This module implements a composite subword encoder for tokens on
    the output side of the text-to-parse-tree model, i.e. grammar
    nonterminals, terminals and their variants.

"""

import os

from tensor2tensor.data_generators import text_encoder
import tensorflow as tf
from greynir.parsing_subtokens import ParsingSubtokens
import greynir.grammar_consts as grammar_consts


_NNSERVER_PATH = os.path.dirname(os.path.realpath(__file__))
_PROJECT_PATH = os.path.join(_NNSERVER_PATH, "greynir")

_DEFAULT_PATH = os.path.join(_PROJECT_PATH, "resources", "parsing_tokens.txt")
_DEFAULT_PATH_V2 = os.path.join(_PROJECT_PATH, "resources", "parsing_tokens_180729.txt")

_CASE_TOKS = set(["nf", "þf", "þgf", "ef"])

UNK = "<UNK>"
EOS_ID = text_encoder.EOS_ID


class CompositeTokenEncoder(text_encoder.TextEncoder):
    """Build vocabulary from composite token vocabulary

    Read composite vocabulary and extract subtokens according to simple
    right recursive rule (regular) with a couple of exceptions

    Behaves otherwise similarly to the Tensor2Tensor subword encoders
    """

    def __init__(self, filename=None, reorder=True, version=2):
        if filename is None:
            self.filename = _DEFAULT_PATH if version == 1 else _DEFAULT_PATH_V2
        else:
            self.filename = filename
        self.version = version

        tokens = ParsingSubtokens(self.filename, version=self.version)

        self._num_reserved_ids = len(text_encoder.RESERVED_TOKENS)
        self._reorder = reorder
        self._preprocess_word = tokens.preprocess_word

        self._tok_id_to_tok_str = tokens._tok_id_to_tok_str
        self._ftok_to_tok_id = tokens._ftok_to_tok_id
        self._htok_to_tok_id = tokens._htok_to_tok_id
        self._ttok_to_tok_id = tokens._ttok_to_tok_id
        self.oov_id = tokens.oov_id

    @property
    def num_reserved_ids(self):
        return self._num_reserved_ids

    def _token_to_subtoken_ids(self, word):
        word = self._preprocess_word(word)
        if word in self._ftok_to_tok_id:
            return [self._ftok_to_tok_id[word]]
        if "_" not in word:
            return [self.oov_id]
        toks = word.split("_")
        head, t1 = toks[:2]
        tail = toks[2:]

        tail_start = 0
        if t1 in {"0", "1", "2", "subj"}:
            head = head + "_" + t1
            tail_start += 0 if t1 == "subj" else int(t1)
        else:
            tmp = [t1]
            tmp.extend(tail)
            tail = tmp

        if head not in self._htok_to_tok_id or not all(
            t in self._ttok_to_tok_id for t in tail
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


def test_roundtrip():
    sample = "P S-MAIN IP NP-SUBJ pfn_et_nf_p3 /NP-SUBJ /IP /S-MAIN /P"
    default_encoder = CompositeTokenEncoder()
    subtoken_ids = default_encoder.encode(sample)
    decoded_sample = default_encoder.decode(subtoken_ids)
    assert sample == decoded_sample, "Encoding roundtrip does not match"


if __name__ == "__main__":
    test_roundtrip()
