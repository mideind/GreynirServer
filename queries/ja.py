"""

    Greynir: Natural language processing for Icelandic

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


    This module handles Ja.is API queries.

"""

from typing import Dict, Optional

import logging
from urllib.parse import urlencode
from datetime import datetime, timedelta

from reynir import NounPhrase

from . import query_json_api, gen_answer
from query import Query
from util import read_api_key


# This module wants to handle parse trees for queries
HANDLE_TREE = True

# The context-free grammar for the queries recognized by this plug-in module
GRAMMAR = """

Query →
    QJaQuery '?'?

QJaQuery →
    QJaPhoneNumQuery

QJaPhoneNumQuery →
    "hvað" "er" "símanúmerið" "hjá" QJaSubject

QJaSubject →
    Nl_þgf

$score(+35) QJaQuery

"""


def QJaSubject(node, params, result):
    n = result._text
    nom = NounPhrase(n).nominative or n
    result.qkey = nom


def QJaPhoneNumQuery(node, params, result):
    result.qtype = "JaPhoneNum"


_JA_API_URL = "https://api.ja.is/search/v6/?{0}"


def query_ja_api(q: str) -> Optional[Dict]:
    """ Send query to ja.is API. """
    key = read_api_key("JaServerKey")
    if not key:
        # No key, can't query the API
        logging.warning("No API key for ja.is")
        return None

    qd = {"q": q}
    headers = {"Authorization": key}

    # Send API request, get back parsed JSON
    url = _JA_API_URL.format(urlencode(qd))
    print(url)
    res = query_json_api(url, headers=headers)

    return res


def _answer_phone_num_query(q: Query, result):
    """ Answer query of the form "hvað er síminn hjá [Sveinbirni Þórðarsyni]?" """
    res = query_ja_api(q.key())
    from pprint import pprint
    pprint(res)

    # Verify that we have a sane response with at least 1 result
    if not res.get("people") or not res["people"].get("items"):
        return None

    first_person = res["people"]["items"][0]
    phone_info = first_person.get("phone")
    if not phone_info or "number" not in phone_info:
        return None

    pnum = " ".join(list(phone_info["number"]))

    return gen_answer(pnum)


def sentence(state, result):
    """ Called when sentence processing is complete """
    q: Query = state["query"]
    if "qtype" in result and result["qtype"] == "JaPhoneNum" and "qkey" in result:
        # Successfully matched a query type
        q.set_qtype(result.qtype)
        q.set_key(result.qkey)

        try:
            r = _answer_phone_num_query(q, result)
            if not r:
                r = gen_answer("Ekki tókst að fletta upp viðkomandi.")
            q.set_answer(*r)
            # q.set_expires(datetime.utcnow() + timedelta(hours=24))
        except Exception as e:
            logging.warning("Exception while processing ja.is query: {0}".format(e))
            q.set_error("E_EXCEPTION: {0}".format(e))
    else:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
