#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
    Reynir: Natural language processing for Icelandic

    Neural Network Query Client

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


    This module implements a client for that connects to a tensorflow model server.

"""

import requests
import base64
import json

from settings import Settings

from composite_encoder import CompositeTokenEncoder as ParsingEncoder
import nntree
from nntree import ParseResult
import grammar_consts as gu

from tensor2tensor.data_generators import text_encoder
from tensorflow.core.example import feature_pb2
from tensorflow.core.example import example_pb2
from google.protobuf import text_format

EOS_ID = text_encoder.EOS_ID
PAD_ID = text_encoder.PAD_ID
_PARSING_VOCAB_PATH = "parsing_tokens_180729.txt"
_ENIS_VOCAB_PATH = "vocab.enis.16384.subwords"


class NnClient:
    """ Client that speaks to the HTTP RESTful interface of
        a tensorflow model server. """

    port=Settings.NN_PORT
    host=Settings.NN_HOST
    _tfms_version="v1"
    _model_name="transformer"
    _verb="predict"
    _parsingEncoder = ParsingEncoder(_PARSING_VOCAB_PATH, version=2)
    _enisEncoder = text_encoder.SubwordTextEncoder(_ENIS_VOCAB_PATH)

    @classmethod
    def parse_sentence(cls, text):
        """ Parse a single sentence into flat parse tree """
        if "\n" in text:
            single_sentence = text.split("\n")[0]
        else:
            single_sentence = text
            pgs = [single_sentence]
        return cls._request(pgs)[0]

    @classmethod
    def parse_text(cls, text):
        """ Parse contiguous text into flat parse trees """
        pgs = text.split("\n")
        return cls.request(pgs)

    @classmethod
    def _request(cls, pgs):
        """ Send serialized request to remote model server """
        url = "http://{host}:{port}/{version}/models/{model}:{verb}".format(
            port=cls.port,
            host=cls.host,
            version=cls._tfms_version,
            model=cls._model_name,
            verb=cls._verb
        )
        headers = {"content-type": "application/json"}
        instances = [cls._serializeToInstance(sent) for sent in pgs]

        payload = {
            "signature_name" : "serving_default",
            "instances" : [inst for inst in instances],
        }
        payload = json.dumps(payload)
        resp = requests.post(url, data=payload, headers=headers)

        try:
            obj = json.loads(resp.text)
            predictions = obj["predictions"]
            results = [
                cls._processResponseInstance(inst, sent) for
                    (inst, sent) in zip(predictions, pgs)
            ]
            return results

        except Exception as e:
            print(e)
            return None

    @classmethod
    def _processResponseInstance(cls, instance, sent):
        """  Process the numerical output from the model server for one sentence """
        scores = instance["scores"]
        output_ids = instance["outputs"]

        pad_start = output_ids.index(PAD_ID) if PAD_ID in output_ids else len(outpt_ids)
        eos_start = output_ids.index(EOS_ID) if EOS_ID in output_ids else len(outpt_ids)
        sent_end = min(pad_start, eos_start)

        parse_toks = cls._parsingEncoder.decode(output_ids[:sent_end])

        tree, p_result = nntree.parse_tree_with_text(parse_toks, sent)
        tree = tree.to_dict()

        if p_result != ParseResult.SUCCESS:
            print("ParseResult: {result}".format(result=p_result))
            print("Output: {parse_toks}".format(parse_toks=parse_toks))
        return tree

    @classmethod
    def _serializeToInstance(cls, sent):
        """ Encodes a single sentence into the format expected by the RESTful interface
        of tensorflow_model_server running an exported tensor2tensor transformer translation model """
        # Add end of sentence token
        input_ids = cls._enisEncoder.encode(sent)
        input_ids.extend([EOS_ID])

        int64_list = feature_pb2.Int64List(value=input_ids)
        feature = feature_pb2.Feature(int64_list=int64_list)
        feature_map = {
            "inputs" : feature
        }
        features = feature_pb2.Features(feature=feature_map)
        example = example_pb2.Example(features=features)

        b64_example = base64.b64encode(example.SerializeToString()).decode("utf-8")
        return {
            "input" : {
                "b64" : b64_example
            }
        }


def manual_test():
    res = NnClient.parse_sentence("Konurnar komu heim.")
    print(res)


if __name__ == "__main__":
    manual_test()
