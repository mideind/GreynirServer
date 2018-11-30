#!/usr/bin/env python3
"""
    Reynir: Natural language processing for Icelandic

    Neural Network Query Client

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


    This module implements a client that connects to a middleware
    neural network server (see nnserver/nnserver.py), which in turn
    connects to a TensorFlow model server.

"""

import json
import requests
import logging

from settings import Settings
import tokenizer
from fetcher import Fetcher

import nntree
from nntree import ParseResult


def index_text(text):
    """ Segments text into paragraphs and sentences
        and returns:
            dictionary of sentence indices to sentences
            dictionary of paragraph index to constituent sentence indices"""
    text = Fetcher.mark_paragraphs(text)
    tok_stream = tokenizer.tokenize(text)

    pgs = tokenizer.paragraphs(tok_stream)
    pg_idx_to_sent_idx = dict()
    sent_idx_to_sent = dict()
    curr_sent_idx = 0
    curr_pg_idx = 0

    for pg in pgs:
        sent_idxs = []
        for (idx, sent) in pg:
            curr_sent = tokenizer.correct_spaces(" ".join([t.txt for t in sent if t]))
            sent_idxs.append(curr_sent_idx)
            sent_idx_to_sent[curr_sent_idx] = curr_sent
            curr_sent_idx += 1
        pg_idx_to_sent_idx[curr_pg_idx] = sent_idxs
        curr_pg_idx += 1
    return pg_idx_to_sent_idx, sent_idx_to_sent


class NnClient:
    """ A client that connects to the HTTP rest interface of
        a tensorflow model server (using plaintext) """

    port = None
    host = None
    verb = None

    @classmethod
    def request_sentence(cls, text, src_lang=None, tgt_lang=None):
        """ Request neural network output for a single sentence """
        if "\n" in text:
            single_sentence = text.split("\n")[0]
        else:
            single_sentence = text
        pgs = [single_sentence]
        result = cls._request(pgs, src_lang, tgt_lang)
        result = result[0] if result is not None else None
        return result

    @classmethod
    def request_text(cls, text, src_lang=None, tgt_lang=None):
        """ Request neural network output for contiguous text """
        pgs = cls._normalizeText(text)
        resp = cls._request(pgs, src_lang, tgt_lang)
        return resp

    @classmethod
    def _request(cls, pgs, src_lang=None, tgt_lang=None):
        """ Send serialized request to remote model server """
        url = "http://{host}:{port}/{verb}.api".format(
            host=cls.host, port=cls.port, verb=cls.verb
        )
        headers = {"content-type": "application/json"}
        payload = {"pgs": pgs}

        if src_lang and tgt_lang:
            payload["src_lang"] = src_lang
            payload["tgt_lang"] = tgt_lang

        logging.debug(str(payload))
        payload = json.dumps(payload)
        resp = requests.post(url, data=payload, headers=headers)
        resp.raise_for_status()

        try:
            obj = json.loads(resp.text)
            logging.debug(str(obj))
            predictions = obj["predictions"]
            results = [
                cls._processResponse(inst, sent)
                for (inst, sent) in zip(predictions, list(pgs))
            ]

            logging.debug(str(results))
            return results
        # TODO(haukurb): More graceful error handling
        except Exception as e:
            logging.error("Error: could not process response from nnserver")
            logging.error(e)
            return None

    @classmethod
    def _processResponse(cls, instance, sent):
        """ Process the response from a single sentence.
            Abstract method """
        raise NotImplemented

    @classmethod
    def _normalizeText(cls, instance, sent):
        """ Preprocess text and normalize for neural network input
            Abstract method """
        raise NotImplemented



class TranslateClient(NnClient):
    """ A client that connects to an HTTP RESTful interface of
        middleware server for a tensorflow model server (using plaintext) that returns
        an English translation of Icelandic text """

    port = Settings.NN_TRANSLATE_PORT
    host = Settings.NN_TRANSLATE_HOST
    verb = "translate"

    @classmethod
    def _processResponse(cls, instance, sent):
        """ Process the response from a single sentence """
        result = dict(
            inputs=sent,
            outputs=instance["outputs"],
            scores=float(instance["scores"]),
        )
        return result

    @classmethod
    def _normalizeText(cls, text):
        """ Preprocess text and normalize for translation network """
        return text

    @classmethod
    def request_text(cls, text, src_lang=None, tgt_lang=None):
        """ Preprocess text and normalize for translation network """
        pg_map, sent_map = index_text(text)
        sents = list(sent_map.values())
        result = TranslateClient._request(sents, src_lang, tgt_lang)
        inst_map = {idx:inst for (idx,inst) in enumerate(result)}
        resp = dict(
            pgs=pg_map,
            results=inst_map,
        )
        return resp

class ParsingClient(NnClient):
    """ A client that connects to an HTTP RESTful interface of
        middleware server for a tensorflow model server (using plaintext) that returns
        a parse tree of Icelandic text """

    port = Settings.NN_PARSING_PORT
    host = Settings.NN_PARSING_HOST
    verb = "parse"

    @classmethod
    def _processResponse(cls, instance, sent):
        """ Process the response from a single sentence """
        parse_toks = instance["outputs"]
        scores = instance["scores"]

        logging.info(parse_toks)
        tree, p_result = nntree.parse_tree_with_text(parse_toks, sent)

        if Settings.DEBUG:
            print("Received parse tokens from nnserver:", parse_toks)
            print("Parsed by nntree into:")
            tree.pprint()
            if p_result != ParseResult.SUCCESS:
                print("NnParse not successful for input: '{text}'".format(text=sent))
                print("ParseResult: {result}".format(result=p_result))
                print("Output: {parse_toks}".format(parse_toks=parse_toks))

        return tree

    @classmethod
    def _normalizeText(cls, text):
        """ Preprocess text and normalize for parsing network """

        normalized_pgs = [
            [tok.txt for tok in list(tokenizer.tokenize(pg))] for pg in pgs
        ]
        normalized_pgs = [
            " ".join([tok for tok in npg if tok]) for npg in normalized_pgs
        ]
        return normalized_pgs



def test_translate_sentence():
    sample_phrase = "Hæ."
    print("sample_phrase:", sample_phrase)
    res = TranslateClient.request_sentence(sample_phrase)
    # json = "{'predictions':[{'batch_prediction_key':[0],'outputs':'Hi.','scores':-0.946593}]}"
    print("processed_output:", res)
    print()


def test_translate_text():
    sample_phrase = "Hæ.\nHvernig?"
    print("sample_phrase: \"\"\"", sample_phrase, "\"\"\"", sep="")
    print()
    res = TranslateClient.request_text(sample_phrase)
    # json = "{'predictions':[{'batch_prediction_key':[0],'outputs':'Hi.','scores':-0.946593}]}"
    print("processed_output:", res)
    print()


def send_test_parse():
    sample_phrase = (
        "Eftirfarandi skilaboð voru smíðuð í Nnclient og þau skulu verða þáttuð."
    )
    print("Sending test translate phrase to server:", sample_phrase)
    res = ParsingClient.request_sentence(sample_phrase)
    print("Received response:")
    print(res)


if __name__ == "__main__":
    test_translate_sentence()
    # test_translate_text()
    pass
    # manual_test_sentence()
