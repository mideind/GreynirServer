"""

    Greynir: Natural language processing for Icelandic

    High-level wrappers for checking grammar and spelling

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


    This module exports check_grammar(), a function called from main.py
    to apply grammar and spelling annotations to user-supplied text.

"""

from typing import Iterator, List, cast
from reynir.reynir import ProgressFunc, Tok
import nertokenizer
import reynir_correct


class RecognitionPipeline(reynir_correct.CorrectionPipeline):

    """ Derived class that adds a named entity recognition pass
        to the GreynirCorrect tokenization pipeline """

    def __init__(self, text: str) -> None:
        super().__init__(text)

    def recognize_entities(self, stream: Iterator[Tok]) -> Iterator[Tok]:
        """ Recognize named entities using the nertokenizer module,
            but construct tokens using the Correct_TOK class from
            reynir_correct """
        return nertokenizer.recognize_entities(
            stream, token_ctor=reynir_correct.Correct_TOK
        )


class NERCorrect(reynir_correct.GreynirCorrect):

    """ Derived class to override the default tokenization of
        GreynirCorrect to perform named entity recognition """

    def __init__(self) -> None:
        super().__init__()

    def tokenize(self, text):
        """ Use the recognizing & correcting tokenizer instead
            of the normal one """
        pipeline = RecognitionPipeline(text)
        return pipeline.tokenize()


def check_grammar(text: str, *, progress_func: ProgressFunc = None):
    """ Check the grammar and spelling of the given text and return
        a list of annotated paragraphs, containing sentences, containing
        tokens. The progress_func, if given, will be called periodically
        during processing to indicate progress, with a ratio parameter
        which is a float in the range 0.0..1.0. """

    result = reynir_correct.check_with_custom_parser(
        text,
        split_paragraphs=True,
        parser_class=NERCorrect,
        progress_func=progress_func,
    )

    def encode_sentence(sent: reynir_correct.AnnotatedSentence):
        """ Map a reynir._Sentence object to a raw sentence dictionary
            expected by the web UI """
        if sent.tree is None:
            # Not parsed: use the raw token list
            tokens = [dict(k=d.kind, x=d.txt) for d in sent.tokens]
        else:
            # Successfully parsed: use the text from the terminals (where available)
            # since we have more info there, for instance on em/en dashes.
            # Create a map of token indices to corresponding terminal text
            token_map = {t.index: t.text for t in sent.terminals}
            tokens = [
                dict(k=d.kind, x=token_map.get(ix, d.txt))
                for ix, d in enumerate(sent.tokens)
            ]
        return dict(
            tokens=tokens,
            annotations=[
                dict(
                    start=ann.start,
                    end=ann.end,
                    code=ann.code,
                    text=ann.text,
                    detail=ann.detail,
                    suggest=ann.suggest,
                )
                for ann in sent.annotations
            ],
        )

    paragraphs = cast(
        List[List[reynir_correct.AnnotatedSentence]], result["paragraphs"]
    )
    pgs = [[encode_sentence(sent) for sent in pg] for pg in paragraphs]

    stats = dict(
        num_tokens=result["num_tokens"],
        num_sentences=result["num_sentences"],
        num_parsed=result["num_parsed"],
        ambiguity=result["ambiguity"],
    )

    return pgs, stats
