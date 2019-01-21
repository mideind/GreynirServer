"""

    Reynir: Natural language processing for Icelandic

    High-level wrappers for checking grammar and spelling

    Copyright (C) 2019 Miðeind ehf.

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

import reynir_correct
import nertokenizer


class RecognitionPipeline(reynir_correct.CorrectionPipeline):

    """ Derived class that adds a named entity recognition pass
        to the ReynirCorrect tokenization pipeline """

    def __init__(self, text):
        super().__init__(text)

    def recognize_entities(self, stream):
        """ Recognize named entities using the nertokenizer module """
        return nertokenizer.recognize_entities(stream)


class NERCorrect(reynir_correct.ReynirCorrect):

    """ Derived class to override the default tokenization of
        ReynirCorrect to perform named entity recognition """

    def __init__(self):
        super().__init__()

    def tokenize(self, text):
        """ Use the recognizing & correcting tokenizer instead
            of the normal one """
        pipeline = RecognitionPipeline(text)
        return pipeline.tokenize()


def check_grammar(text):
    """ Check the grammar and spelling of the given text and return
        a list of annotated paragraphs, containing sentences, containing
        tokens """

    result = reynir_correct.check_with_custom_parser(
        text,
        split_paragraphs=True,
        parser_class=NERCorrect
    )

    def encode_sentence(sent):
        """ Map a reynir._Sentence object to a raw sentence dictionary
            expected by the web UI """
        if sent.tree is None:
            # Not parsed: use the raw token list
            tokens = [dict(k=d.kind, x=d.txt) for d in sent.tokens]
        else:
            # Successfully parsed: use the terminals, since we have
            # more info there, for instance on em/en dashes
            stok = sent.tokens
            tokens = [dict(k=stok[t.index].kind, x=t.text) for t in sent.terminals]
        return dict(
            tokens=tokens,
            annotations=[
                dict(
                    start=ann.start,
                    end=ann.end,
                    code=ann.code,
                    text=ann.text
                )
                for ann in sent.annotations
            ]
        )

    pgs = [
        [encode_sentence(sent) for sent in pg]
        for pg in result["paragraphs"]
    ]

    stats = dict(
        num_tokens=result["num_tokens"],
        num_sentences=result["num_sentences"],
        num_parsed=result["num_parsed"],
        ambiguity=result["ambiguity"]
    )

    return pgs, stats
