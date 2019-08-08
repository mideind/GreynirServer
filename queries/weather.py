"""

    Reynir: Natural language processing for Icelandic

    Arithmetic query response module

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

"""

import logging
import requests
import json
import re

# Indicate that this module wants to handle parse trees for queries,
# as opposed to simple literal text strings
HANDLE_TREE = True

# The context-free grammar for the queries recognized by this plug-in module
GRAMMAR = """

# ----------------------------------------------
#
# Query grammar for arithmetic-related queries
#
# ----------------------------------------------

# A plug-in query grammar always starts with the following,
# adding one or more query productions to the Query nonterminal

Query →
    QWeather

# By convention, names of nonterminals in query grammars should
# start with an uppercase Q

QWeather →
    "hvernig" "er" "veðrið" "úti"? "núna"? '?'?
    | "hvernig" "veður" "er" "úti"? "núna"? '?'?

"""


def QWeather(node, params, result):
    """ Arithmetic query """
    # Set query type & key
    result.qtype = "Weather"
    result.qkey = "Veður"


_WEATHER_API_URL = "https://apis.is/weather/texts?types=3"


def _query_weather_api():
    """ Send request to weather API """

    # Send request
    url = _WEATHER_API_URL
    try:
        r = requests.get(url)
    except Exception as e:
        logging.warning(str(e))
        return None

    # Verify that status is OK
    if r.status_code != 200:
        logging.warning("Received status {0} from weather API server", r.status_code)
        return None

    # Parse json API response
    try:
        res = json.loads(r.text)
        return res
    except Exception as e:
        logging.warning("Error parsing JSON API response: {0}", str(e))

    return None


def _handle_weather_query(q, result):
    resp = _query_weather_api()

    if not resp or "results" not in resp or len(resp["results"]) < 1:
        return None

    r = resp["results"][0]
    answer = r["content"]
    response = dict(answer=answer)

    # Prepare voice answer
    voice_answer = answer.replace("m/s", "metrar á sekúndu")
    voice_answer = re.sub(r"(\d+)\-(\d+)", r"\1 til \2", voice_answer)

    return response, answer, voice_answer


def sentence(state, result):
    """ Called when sentence processing is complete """
    q = state["query"]
    if "qtype" in result:
        # Successfully matched a query type
        q.set_qtype(result.qtype)
        q.set_key(result.qkey)

        try:
            (response, answer, voice_answer) = _handle_weather_query(q, result)
            q.set_answer(response, answer, voice_answer)
        except AssertionError:
            raise
        except Exception as e:
            raise
            q.set_error("E_EXCEPTION: {0}".format(e))
    else:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
