"""

    Greynir: Natural language processing for Icelandic

    News query response module

    Copyright (C) 2020 Miðeind ehf.

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


    This module handles queries related to current news & news headlines. 
    Uses RÚV's JSON API to fetch top headlines on the ruv.is front page.

"""

import logging
import cachetools

from queries import gen_answer, query_json_api


_NEWS_QTYPE = "News"


# Indicate that this module wants to handle parse trees for queries,
# as opposed to simple literal text strings
HANDLE_TREE = True

# The context-free grammar for the queries recognized by this plug-in module
GRAMMAR = """

Query →
    QNewsQuery '?'?

QNewsQuery →
    QNewsLatest

QNewsLatest →
    QNewsTellMe? "hvað" "er" QNewsQualifiers? "í" "fréttum" QNewsRUV?
    | QNewsTellMe? "hvað" "er" QNewsQualifiers? "að" "frétta" QNewsRUV?
    | QNewsTellMe? "hverjar" "eru" QNewsQualifiersDef? "fréttir" QNewsRUV?
    | QNewsTellMe? "hverjar" "eru" QNewsQualifiersDef? "fréttirnar" QNewsRUV?

QNewsTellMe →
    "segðu" "mér"

QNewsQualifiers →
    "helst" | "eiginlega" | "núna" | "nýjast"

QNewsQualifiersDef →
    "helstu" | "nýjustu" | "síðustu" | "allranýjustu"

QNewsRUV →
    "á" "rúv"
    | "hjá" "rúv"
    | "í" "ríkisútvarpinu"
    | "á" "ríkisútvarpinu"
    | "hjá" "ríkisútvarpinu"
    | "á" "vef" "rúv"
    | "á" "vef" "ríkisútvarpsins"

$score(+35) QNewsQuery

"""


def QNewsQuery(node, params, result):
    result.qtype = _NEWS_QTYPE


_NEWS_API = "https://ruv.is/json/frettir/hladbord"
_NEWS_CACHE_TTL = 300  # seconds, ttl = 5 mins


@cachetools.cached(cachetools.TTLCache(1, _NEWS_CACHE_TTL))
def _get_news_data(max_items=8):
    """ Fetch news headline data from RÚV, preprocess it. """
    res = query_json_api(_NEWS_API)
    if not res or "nodes" not in res or not len(res["nodes"]):
        return None

    items = [
        {"title": i["node"]["title"], "intro": i["node"]["intro"]} for i in res["nodes"]
    ]

    return items[:max_items]


def top_news_answer():
    headlines = _get_news_data()
    if not headlines:
        return None

    answer = "".join([h["intro"] + " " for h in headlines])
    voice = "Í fréttum rúv er þetta helst: " + answer
    response = dict(answer=answer)

    return response, answer, voice


def sentence(state, result):
    """ Called when sentence processing is complete """
    q = state["query"]
    if "qtype" in result:
        # Successfully matched a query type
        q.set_qtype(result.qtype)
        q.set_key("LatestHeadlines")

        try:
            res = top_news_answer()
            if res:
                q.set_answer(*res)
            else:
                errmsg = "Ekki tókst að sækja upplýsingar um fréttir".format()
                q.set_answer(gen_answer(errmsg))
                q.set_source("RÚV")
        except Exception as e:
            logging.warning("Exception answering news query: {0}".format(e))
            q.set_error("E_EXCEPTION: {0}".format(e))
            return
    else:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
