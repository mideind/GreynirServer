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

import nntree
from nntree import ParseResult


class NnClient:
    """ A client that connects to the HTTP rest interface of
        a tensorflow model server (using plaintext) """

    port = None
    host = None
    verb = None

    @classmethod
    def request_sentence(cls, text, src_lang=None, tgt_lang=None):
        """ Parse a single sentence into flat parse tree """
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
        """ Parse contiguous text into flat parse trees """
        pgs = text.split("\n")
        resp = cls._request(pgs, src_lang, tgt_lang)
        return resp

    @classmethod
    def _request(cls, pgs, src_lang=None, tgt_lang=None):
        """ Send serialized request to remote model server """
        url = "http://{host}:{port}/{verb}.api".format(
            host=cls.host, port=cls.port, verb=cls.verb
        )
        headers = {"content-type": "application/json"}

        normalized_pgs = [
            [tok.txt for tok in list(tokenizer.tokenize(pg))] for pg in pgs
        ]
        normalized_pgs = [
            " ".join([tok for tok in npg if tok]) for npg in normalized_pgs
        ]
        payload = {"pgs": normalized_pgs}
        if src_lang and tgt_lang:
            payload["src_lang"] = src_lang
            payload["tgt_lang"] = tgt_lang

        payload = json.dumps(payload)
        resp = requests.post(url, data=payload, headers=headers)
        resp.raise_for_status()

        try:
            obj = json.loads(resp.text)
            predictions = obj["predictions"]
            results = [
                cls._processResponse(inst, sent)
                for (inst, sent) in zip(predictions, pgs)
            ]

            return results
        # TODO(haukurb): More graceful error handling
        except Exception as e:
            logging.error("Error: could not process response from nnserver")
            logging.error(e)
            return None

    @classmethod
    def _processResponse(cls, instance, sent):
        """ Process the response from a single sentence

            Abstract method """
        raise NotImplemented


class TranslateClient(NnClient):
    """ A client that connects to the HTTP rest interface of
        a tensorflow model server (using plaintext) that returns
        an English translation of Icelandic text """

    port = Settings.NN_TRANSLATE_PORT
    host = Settings.NN_TRANSLATE_HOST
    verb = "translate"

    @classmethod
    def _processResponse(cls, instance, sent):
        """ Process the response from a single sentence """
        model_output = instance["outputs"]
        scores = instance["scores"]
        instance["scores"] = float(scores)
        bkey = "batch_prediction_key" 
        if bkey in instance:
            del instance[bkey]

        logging.debug(model_output)

        return instance


class ParsingClient(NnClient):
    """ A client that connects to an HTTP RESTful interface of
        a tensorflow model server (using plaintext) that returns
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
