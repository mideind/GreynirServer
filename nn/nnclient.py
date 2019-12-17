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

from nn import nntree
from nn.nntree import ParseResult
from nn.utils import index_text
from reynir.binparser import BIN_Token
from reynir import bintokenizer


class NnClient:
    """ A client that connects to the HTTP REST interface of
        a tensorflow model server (using plaintext) """

    port = None
    host = None
    verb = None

    @classmethod
    def request_sentence(cls, text):
        """ Request neural network output for a single sentence """
        raise NotImplemented

    @classmethod
    def request_text(cls, text):
        """ Request neural network output for contiguous text """
        raise NotImplemented

    @classmethod
    def _request(cls, pgs, data=None):
        """ Send serialized request to remote model server """
        url = "http://{host}:{port}/{verb}.api".format(
            host=cls.host, port=cls.port, verb=cls.verb
        )
        headers = {"content-type": "application/json; charset=UTF-8"}
        payload = {"pgs": pgs}

        if data is not None:
            for (k, v) in data.items():
                payload[k] = v

        logging.debug(str(payload))
        payload = json.dumps(payload)
        resp = requests.post(url, data=payload, headers=headers)
        resp.raise_for_status()

        obj = json.loads(resp.text)
        if obj.get("predictions") is None:
            raise ValueError("Invalid request or batch size too large")
        predictions = obj["predictions"]
        return [
            cls._processResponse(inst, sent)
            for (inst, sent) in zip(predictions, list(pgs))
        ]

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
            inputs=sent, outputs=instance["outputs"], scores=float(instance["scores"])
        )
        return result

    @classmethod
    def _normalizeText(cls, text):
        """ Preprocess text and normalize for translation network """
        return text

    @classmethod
    def request_sentence(cls, text, src_lang=None, tgt_lang=None):
        """ Request neural network output for a single sentence """
        if "\n" in text:
            single_sentence = text.split("\n")[0]
        else:
            single_sentence = text
        pgs = [single_sentence]
        data = dict(src_lang=src_lang, tgt_lang=tgt_lang)
        results = cls._request(pgs, data=data)
        if results is None:
            return results
        return results[0]

    @classmethod
    def request_text(cls, text, src_lang=None, tgt_lang=None):
        """ Preprocess, segment and normalize text for translation network """
        pg_map, sent_map = index_text(text)
        sents = list(sent_map.values())
        data = dict(src_lang=src_lang, tgt_lang=tgt_lang)
        result = TranslateClient._request(sents, data=data)
        inst_map = {idx: inst for (idx, inst) in enumerate(result)}
        resp = dict(pgs=pg_map, results=inst_map)
        return resp

    @classmethod
    def request_segmented(cls, sent_map, src_lang=None, tgt_lang=None, verbatim=False):
        """ Translate presegmented sentences
            args:
                sent_map: either a list of sentences or a dict[key] of sentences"""
        data = dict(src_lang=src_lang, tgt_lang=tgt_lang)
        if type(sent_map) is dict:
            sents = (
                [tokenizer.correct_spaces(sent) for sent in sent_map.values()]
                if not verbatim
                else list(sent_map.values())
            )
            result = TranslateClient._request(sents, data=data)
            inst_map = {idx: inst for (idx, inst) in zip(sent_map.keys(), result)}
            resp = dict(results=inst_map)
        else:
            sents = (
                [tokenizer.correct_spaces(sent) for sent in sent_map]
                if not verbatim
                else sent_map
            )
            result = TranslateClient._request(sents, data=data)
            inst_map = {idx: inst for (idx, inst) in enumerate(result)}
            resp = dict(results=inst_map)
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
        try:
            instance["scores"] = max([float(score) for score in instance["scores"]])
        except TypeError:
            # Score is not iterable
            pass
        return instance

    @classmethod
    def _instances_to_ptrees(cls, insts, sents):
        """ Transforms list of result dicts of flat parse trees
            into a list of dicts of parsed tree structures """
        for (inst, sent) in zip(insts, sents):
            parse_toks = inst["outputs"]
            tree, p_result = nntree.parse_tree_with_text(parse_toks, sent)
            inst["outputs"] = tree

            if Settings.DEBUG:
                print("Received parse tokens from nnserver:", parse_toks)
                print("ParseResult: ", p_result)
                print("Parsed by nntree into:")
                tree.pprint()
                if p_result != ParseResult.SUCCESS:
                    print(
                        "NnParse not successful for input: '{text}'".format(text=sent)
                    )
                    print("ParseResult: {result}".format(result=p_result))
                    print("Output: {parse_toks}".format(parse_toks=parse_toks))

    @classmethod
    def request_text(cls, text, flat=False):
        """ Request neural network output for contiguous text """
        sents = cls._normalizeText(text)
        results = cls._request(sents)
        if not flat:
            cls._instances_to_ptrees(results, sents)
        return results

    @classmethod
    def request_sentence(cls, text, flat=False):
        """ Request neural network output for a single sentence """
        if "\n" in text:
            single_sentence = text.split("\n")[0]
        else:
            single_sentence = text
        toks = cls._normalizeSentence(single_sentence)
        single_sentence = " ".join(toks)
        sents = [single_sentence]
        results = cls._request(sents)
        if results is None:
            return results
        if not flat:
            cls._instances_to_ptrees(results, sents)
        return results[0]

    @classmethod
    def _normalizeText(cls, text):
        """ Preprocess text and normalize for parsing network """
        pgs = text.split("\n")
        normalized_pgs = [
            [tok.txt for tok in list(bintokenizer.tokenize(pg))
                if BIN_Token.is_understood(tok)
            ] for pg in pgs]
        normalized_pgs = [
            " ".join([tok for tok in npg if tok]) for npg in normalized_pgs
        ]
        return normalized_pgs

    @classmethod
    def _normalizeSentence(cls, single_sentence):
        """ Preprocess text and normalize for parsing network """
        return [
            tok.txt
            for tok in bintokenizer.tokenize(single_sentence)
            if BIN_Token.is_understood(tok)
        ]
