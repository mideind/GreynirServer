"""
    Greynir: Natural language processing for Icelandic

    Copyright (C) 2021 Miðeind ehf.

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

"""

from typing import List, Tuple, Dict

import tokenizer

from reynir.binparser import BIN_Token, Tok
from reynir import bintokenizer


def prep_text_for_tokenizer(text: str) -> str:
    return "[[ " + " ]] [[ ".join(text.split("\n")) + " ]]"


def index_text(text: str) -> Tuple[Dict[int, List[int]], Dict[int, str]]:
    """ Segments contiguous (Icelandic) text into paragraphs and sentences
        and returns:
            dictionary of sentence indices to sentences
            dictionary of paragraph index to constituent sentence indices"""
    text = prep_text_for_tokenizer(text)
    tok_stream = bintokenizer.tokenize(text)

    pgs = tokenizer.paragraphs(tok_stream)
    pg_idx_to_sent_idx = dict()  # type: Dict[int, List[int]]
    sent_idx_to_sent = dict()  # type: Dict[int, str]
    curr_sent_idx = 0
    curr_pg_idx = 0

    for pg in pgs:
        sent_idxs = []
        for _, sent in pg:
            curr_sent = list(filter(BIN_Token.is_understood, sent))  # type: List[Tok]
            curr_sent_text = tokenizer.normalized_text_from_tokens(curr_sent)
            sent_idxs.append(curr_sent_idx)
            sent_idx_to_sent[curr_sent_idx] = curr_sent_text
            curr_sent_idx += 1
        pg_idx_to_sent_idx[curr_pg_idx] = sent_idxs
        curr_pg_idx += 1
    return pg_idx_to_sent_idx, sent_idx_to_sent


def split_text(text: str) -> List[List[str]]:
    """ Segments contiguous (Icelandic) text into paragraphs and sentences
        and returns a list of lists
    """
    text = prep_text_for_tokenizer(text)
    tok_stream = bintokenizer.tokenize(text)
    pgs = tokenizer.paragraphs(tok_stream)
    data = []  # type: List[List[str]]
    for pg in pgs:
        pg_data = []  # type: List[str]
        for _, sentence in pg:
            sentence = list(filter(BIN_Token.is_understood, sentence))
            sentence_text = tokenizer.normalized_text_from_tokens(sentence)
            pg_data.append(sentence_text)
        data.append(pg_data)
    return data
