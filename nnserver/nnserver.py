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


    This module implements a server that provides an Icelandic text interface to
    a Tensorflow model server running a text-to-parse-tree neural network.

"""

import tokenizer
import requests
import base64
import json
import requests

from composite_encoder import CompositeTokenEncoder

from tensor2tensor.data_generators import text_encoder
from tensorflow.core.example import feature_pb2
from tensorflow.core.example import example_pb2

from flask import Flask, jsonify, request


EOS_ID = text_encoder.EOS_ID
PAD_ID = text_encoder.PAD_ID

basepath = os.path.dirname(__file__)

_PARSING_VOCAB_PATH = os.path.join(basepath, "resources", "parsing_tokens_180729.txt")
_ENIS_VOCAB_PATH = os.path.join(basepath, "resources", "vocab.enis.16384.subwords")


app = Flask(__name__)


class NnServer:
    """ Client that minics the HTTP RESTful interface of
        a tensorflow model server, but accepts plain text. """

    _tfms_version = "v1"
    _model_name = "transformer"
    _verb = "predict"
    _parsingEncoder = CompositeTokenEncoder(_PARSING_VOCAB_PATH, version=2)
    _enisEncoder = text_encoder.SubwordTextEncoder(_ENIS_VOCAB_PATH)

    @classmethod
    def request(cls, pgs):
        """ Send serialized request to remote model server """
        url = "http://{host}:{port}/{version}/models/{model}:{verb}".format(
            port=app.config.get("out_port"),
            host=app.config.get("out_host"),
            version=cls._tfms_version,
            model=cls._model_name,
            verb=cls._verb,
        )
        instances = [cls.serialize_to_instance(sent) for sent in pgs]
        payload = {
            "signature_name": "serving_default",
            "instances": instances,
        }
        payload = json.dumps(payload)
        headers = {"content-type": "application/json"}
        resp = requests.post(url, data=payload, headers=headers)

        try:
            obj = json.loads(resp.text)
            predictions = obj["predictions"]
            results = [
                cls.process_response_instance(inst, sent)
                for (inst, sent) in zip(predictions, pgs)
            ]
            obj["predictions"] = results
            return obj
        except Exception as e:
            print("Error: could not process response from nnserver.")
            print(e)
            return None

    @classmethod
    def process_response_instance(cls, instance, sent):
        """  Process the numerical output from the model server for one sentence """
        scores = instance["scores"]
        output_ids = instance["outputs"]
        # Strip padding and eos token
        length = len(output_ids)
        pad_start = output_ids.index(PAD_ID) if PAD_ID in output_ids else length
        eos_start = output_ids.index(EOS_ID) if EOS_ID in output_ids else length
        sent_end = min(pad_start, eos_start)
        output_toks = cls._parsingEncoder.decode(output_ids[:sent_end])
        instance["outputs"] = output_toks
        return instance

    @classmethod
    def serialize_to_instance(cls, sent):
        """ Encodes a single sentence into the format expected by the RESTful interface
        of tensorflow_model_server running an exported tensor2tensor transformer translation model """
        # Add end of sentence token
        input_ids = cls._enisEncoder.encode(sent)
        print(cls._enisEncoder.decode_list(input_ids))
        input_ids.append(EOS_ID)

        int64_list = feature_pb2.Int64List(value=input_ids)
        feature = feature_pb2.Feature(int64_list=int64_list)
        feature_map = {"inputs": feature}
        features = feature_pb2.Features(feature=feature_map)
        example = example_pb2.Example(features=features)

        b64_example = base64.b64encode(example.SerializeToString()).decode()
        return {"input": {"b64": b64_example}}


@app.route("/parse.api", methods=["POST"])
def parse_api():
    try:
        req_body = request.data.decode("utf-8")
        obj = json.loads(req_body)
        # TODO: validate form?
        pgs = obj["pgs"]
        model_response = NnServer.request(pgs)
        resp = jsonify(model_response)
    except:
        resp = jsonify(valid=False, reason="Invalid request")
    resp.headers["Content-Type"] = "application/json; charset=utf-8"
    return resp


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "Middleware server that provides a textual interface to tensorflow model server"
        )
    )
    parser.add_argument(
        "--listen_host",
        dest="IN_HOST",
        default="0.0.0.0",
        required=False,
        type=str,
        help="Hostname to listen on",
    )
    parser.add_argument(
        "--listen_port",
        dest="IN_PORT",
        default="8080",
        required=False,
        type=str,
        help="Port to listen on",
    )
    parser.add_argument(
        "--model_host",
        dest="OUT_HOST",
        default="localhost",
        required=False,
        type=str,
        help="Hostname of model server",
    )
    parser.add_argument(
        "--model_port",
        dest="OUT_PORT",
        default="9000",
        required=False,
        type=str,
        help="Port of model server",
    )
    parser.add_argument(
        "--debug",
        dest="DEBUG",
        default=False,
        action="store_true",
        required=False,
        help="Emit debug information messages",
    )
    args = parser.parse_args()
    app.config["out_host"] = args.OUT_HOST
    app.config["out_port"] = args.OUT_PORT
    app.run(threaded=True, debug=args.DEBUG, host=args.IN_HOST, port=args.IN_PORT)
