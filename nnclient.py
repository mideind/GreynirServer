#!/usr/bin/env python

"""
    Reynir: Natural language processing for Icelandic

    Neural Network Query Client

    Copyright (C) 2018 Miðeind

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

import json
import requests
import logging

from settings import Settings
import tokenizer

import nntree
from nntree import ParseResult


class NnClient:
    """ Client that speaks to the HTTP RESTful interface of
        a tensorflow model server. """

    port = Settings.NN_PORT
    host = Settings.NN_HOST

    @classmethod
    def parse_sentence(cls, text):
        """ Parse a single sentence into flat parse tree """
        if "\n" in text:
            single_sentence = text.split("\n")[0]
        else:
            single_sentence = text
        pgs = [single_sentence]
        result = cls._request(pgs)
        return result[0] if result is not None else None

    @classmethod
    def parse_text(cls, text):
        """ Parse contiguous text into flat parse trees """
        pgs = text.split("\n")
        return cls._request(pgs)

    @classmethod
    def _request(cls, pgs):
        """ Send serialized request to remote model server """
        url = "http://{host}:{port}/parse.api".format(host=cls.host, port=cls.port)
        headers = {"content-type": "application/json"}

        normalized_pgs = [
            [tok.txt for tok in list(tokenizer.tokenize(pg))] for pg in pgs
        ]
        normalized_pgs = [
            " ".join([tok for tok in npg if tok]) for npg in normalized_pgs
        ]
        payload = {"pgs": normalized_pgs}

        payload = json.dumps(payload)
        resp = requests.post(url, data=payload, headers=headers)

        try:
            obj = json.loads(resp.text)
            predictions = obj["predictions"]
            results = [
                cls._processResponse(inst, sent)
                for (inst, sent) in zip(predictions, pgs)
            ]
            score_str = " ".join(
                ["{:>4.2f}".format(max(inst["scores"])) for inst in predictions]
            )

            logging.info(
                "Parsed {num} sentences with neural network with scores: {scores}".format(
                    num=len(predictions), scores=score_str
                )
            )
            return results
        # TODO(haukurb): More graceful error handling
        except Exception as e:
            logging.error("Error: could not process response from nnserver.")
            logging.error(e)
            return None

    @classmethod
    def _processResponse(cls, instance, sent):
        """ Process the response from a single sentence """
        parse_toks = instance["outputs"]

        logging.info(parse_toks)
        tree, p_result = nntree.parse_tree_with_text(parse_toks, sent)

        if Settings.DEBUG:
            tree.pprint()
            if p_result != ParseResult.SUCCESS:
                print("NnParse not successful for input: '{text}'".format(text=sent))
                print("ParseResult: {result}".format(result=p_result))
                print("Output: {parse_toks}".format(parse_toks=parse_toks))

        import json
        print(json.dumps(tree.to_dict(), indent=3, sort_keys=True))
        return tree.to_dict()


def test_sentence():
    res = NnClient.parse_sentence("Eftirfarandi skilaboð voru smíðuð í NNCLIENT.")
    print("Received response:")
    print(res)


if __name__ == "__main__":
    manual_test()
