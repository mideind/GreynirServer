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

    Example usage:
    python nnserver.py -lh 0.0.0.0 -lp 8080 -mh localhost -mp 9001

    To curl a running nnserver try:
    curl --header "Content-Type: application/json" \
        --request POST \
        http://localhost:8080/translate.api \
        --data '{"pgs":["Hvernig komstu þangað?"],"signature_name":"serving_default"}'

    To test a running model server directly, try:
    curl --header "Content-Type: application/json" \
        --request POST \
        http://localhost:8080/v1/models/transformer:predict \
        --data '{"instances":[{"input":{"b64":"CiAKHgoGaW5wdXRzEhQaEgoQpweFF0oOBsI+EclIBP4cAQ=="}}],"signature_name":"serving_default"}'

    To test a running model server directly and receive gRPC error feedback (more informative than RESTful):
    cd tf/lib/python3.5/site-packages
    python tensor2tensor/serving/query.py \
        --server 'localhost:8081' \
        --servable_name transformer \
        --data_dir ~/t2t_data \
        --t2t_usr_dir ~/t2t_usr \
        --problem translate_enis16k_rev \
        --inputs_once "Kominn."
"""

import tokenizer
import requests
import base64
import json
import os
import requests

from composite_encoder import CompositeTokenEncoder

from tensor2tensor.data_generators import text_encoder
from tensorflow.core.example import feature_pb2
from tensorflow.core.example import example_pb2

from flask import Flask, jsonify, request


EOS_ID = text_encoder.EOS_ID
PAD_ID = text_encoder.PAD_ID

_NNSERVER_PATH = os.path.dirname(os.path.realpath(__file__))
_PROJECT_PATH = os.path.join(_NNSERVER_PATH, "greynir")

_PARSING_VOCAB_PATH = os.path.join(
    _PROJECT_PATH, "resources", "parsing_tokens_180729.txt"
)
_ENIS_VOCAB_PATH = os.path.join(_PROJECT_PATH, "resources", "vocab.enis.16384.subwords")


app = Flask(__name__)


class NnServer:
    """ Client that mimics the HTTP RESTful interface of
        a tensorflow model server, but accepts plain text. """

    _tfms_version = "v1"
    _model_name = "transformer"
    _verb = "predict"
    src_enc = None
    tgt_enc = None

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
        payload = {"signature_name": "serving_default", "instances": instances}
        payload = json.dumps(payload)
        headers = {"content-type": "application/json"}

        resp = requests.post(url, data=payload, headers=headers)
        resp.raise_for_status()

        obj = json.loads(resp.text)
        predictions = obj["predictions"]
        results = [
            cls.process_response_instance(inst, sent)
            for (inst, sent) in zip(predictions, pgs)
        ]
        obj["predictions"] = results
        return obj

    @classmethod
    def process_response_instance(cls, instance, sent, src_enc=None, tgt_enc=None):
        """  Process the numerical output from the model server for one sentence """
        src_enc = src_enc or cls.src_enc
        tgt_enc = tgt_enc or cls.tgt_enc

        scores = instance["scores"]
        output_ids = instance["outputs"]

        app.logger.debug("scores: " + str(scores))
        app.logger.debug("output_ids: " + str(output_ids))

        # Strip padding and eos token
        length = len(output_ids)
        pad_start = output_ids.index(PAD_ID) if PAD_ID in output_ids else length
        eos_start = output_ids.index(EOS_ID) if EOS_ID in output_ids else length
        sent_end = min(pad_start, eos_start)
        output_toks = cls.tgt_enc.decode(output_ids[:sent_end])

        app.logger.debug(
            "tokenized and depadded: "
            + str(cls.tgt_enc.decode_list(output_ids[:sent_end]))
        )
        app.logger.info(output_toks)

        instance["outputs"] = output_toks
        return instance

    @classmethod
    def serialize_to_instance(cls, sent, src_enc=None, tgt_enc=None):
        """ Encodes a single sentence into the format expected by the RESTful interface
        of tensorflow_model_server running an exported tensor2tensor transformer translation model """
        # Add end of sentence token
        src_enc = src_enc or cls.src_enc
        tgt_enc = tgt_enc or cls.tgt_enc

        input_ids = cls.src_enc.encode(sent)
        app.logger.info("received: " + sent)
        app.logger.debug("tokenized: " + str(cls.src_enc.decode_list(input_ids)))
        app.logger.debug("input_ids: " + str(input_ids))
        input_ids.append(EOS_ID)

        int64_list = feature_pb2.Int64List(value=input_ids)
        feature = feature_pb2.Feature(int64_list=int64_list)
        feature_map = {"inputs": feature}
        features = feature_pb2.Features(feature=feature_map)
        example = example_pb2.Example(features=features)

        b64_example = base64.b64encode(example.SerializeToString()).decode()
        return {"input": {"b64": b64_example}}


class ParsingServer(NnServer):
    """ Client that accepts plain text Icelandic
        and returns a flattened parse tree according
        to the Reynir schema """

    src_enc = text_encoder.SubwordTextEncoder(_ENIS_VOCAB_PATH)
    tgt_enc = CompositeTokenEncoder(_PARSING_VOCAB_PATH, version=1)
    _model_name = "parse"


class TranslateServer(NnServer):
    """ Client that accepts plain text Icelandic
        and returns an English translation of the text """

    src_enc = text_encoder.SubwordTextEncoder(_ENIS_VOCAB_PATH)
    tgt_enc = src_enc
    _model_name = "translate"


@app.route("/parse.api", methods=["POST"])
def parse_api():
    try:
        req_body = request.data.decode("utf-8")
        obj = json.loads(req_body)
        # TODO: validate form?
        pgs = obj["pgs"]
        model_response = ParsingServer.request(pgs)
        resp = jsonify(model_response)
    except Exception as error:
        resp = jsonify(valid=False, reason="Invalid request")
        app.logger.exception(error)
    resp.headers["Content-Type"] = "application/json; charset=utf-8"
    return resp


@app.route("/translate.api", methods=["POST"])
def translate_api():
    try:
        req_body = request.data.decode("utf-8")
        obj = json.loads(req_body)
        pgs = obj["pgs"]
        model_response = TranslateServer.request(pgs)
        resp = jsonify(model_response)
    except Exception as error:
        resp = jsonify(valid=False, reason="Invalid request")
        app.logger.exception(error)
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
        "-lh",
        "--listen_host",
        dest="IN_HOST",
        default="0.0.0.0",
        required=False,
        type=str,
        help="Hostname to listen on",
    )
    parser.add_argument(
        "-lp",
        "--listen_port",
        dest="IN_PORT",
        default="8080",
        required=False,
        type=str,
        help="Port to listen on",
    )
    parser.add_argument(
        "-mh",
        "--model_host",
        dest="OUT_HOST",
        default="localhost",
        required=False,
        type=str,
        help="Hostname of model server",
    )
    parser.add_argument(
        "-mp",
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
    parser.add_argument(
        "--only",
        dest="ONLY",
        default=False,
        required=False,
        type=str,
        choices=["parse", "translate"],
        help="Only use one model (otherwise both).",
    )
    args = parser.parse_args()
    app.config["out_host"] = args.OUT_HOST
    app.config["out_port"] = args.OUT_PORT
    app.run(threaded=True, debug=args.DEBUG, host=args.IN_HOST, port=args.IN_PORT)
