"""

    Greynir: Natural language processing for Icelandic

    News query response module

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


    This module handles queries related to current news & news headlines.
    Uses RÚV's JSON API to fetch top headlines on the ruv.is front page.

"""

# TODO: Fyrirsagnir, og að styðja "Segðu mér meira um X"
# TODO: Hvað er helst í fréttum í dag? Fréttir dagsins?

from typing import List, Optional, Dict

import logging
import cachetools  # type: ignore
import random

from query import Query
from queries import gen_answer, query_json_api


_NEWS_QTYPE = "News"


TOPIC_LEMMAS = ["fréttir", "fregnir", "frétta"]


def help_text(lemma) -> str:
    """Help text to return when query.py is unable to parse a query but
    one of the above lemmas is found in it"""
    return "Ég skil þig ef þú spyrð til dæmis: {0}?".format(
        random.choice(("Hvað er í fréttum", "Hvað er að frétta"))
    )


# The grammar nonterminals this module wants to handle
QUERY_NONTERMINALS = {"QNewsQuery"}

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
    QNewsTellMe? QNewsQualifiersDef? "fréttir"
    | QNewsTellMe? "hvað" "er" QNewsQualifiers? "í" "fréttum" QNewsRUV? QNewsNow?
    | QNewsTellMe? "hvað" "er" QNewsQualifiers? "að" "frétta" QNewsRUV? QNewsNow?
    | QNewsTellMe? "hvað" "er" "að" "gerast" QNewsNow?
    | QNewsTellMe? "hvaða" "fréttir" "eru" QNewsQualifiers? QNewsRUV QNewsNow?
    | QNewsTellMe? "hverjar" "eru" QNewsQualifiersDef? "fréttir" QNewsRUV? QNewsNow?
    | QNewsTellMe? "hverjar" "eru" QNewsQualifiersDef? "fréttirnar" QNewsRUV? QNewsNow?

QNewsTellMe →
    "segðu" "mér" | "geturðu" "sagt" "mér"

QNewsNow →
    "núna" | "þessa_stundina" | "í" "dag"

QNewsQualifiers →
    "helst" | "eiginlega" | "núna" | "nýjast"

QNewsQualifiersDef →
    "helstu" | "nýjustu" | "síðustu" | "allranýjustu" | "seinustu"

QNewsRUV →
    "á"? "rúv"
    | "í" "rúv"
    | "hjá" "rúv"
    | "í" "ríkisútvarpinu"
    | "á" "ríkisútvarpinu"
    | "hjá" "ríkisútvarpinu"
    | "á" "vef" "rúv"
    | "á" "vef" "ríkisútvarpsins"
    | "ríkisútvarpsins"

$score(+35) QNewsQuery

"""


def QNewsQuery(node, params, result):
    result.qtype = _NEWS_QTYPE


_NEWS_API = "https://ruv.is/json/frettir/hladbord"
_NEWS_CACHE_TTL = 300  # seconds, ttl = 5 mins


@cachetools.cached(cachetools.TTLCache(1, _NEWS_CACHE_TTL))
def _get_news_data(max_items: int = 8) -> Optional[List[Dict]]:
    """ Fetch news headline data from RÚV, preprocess it. """
    res = query_json_api(_NEWS_API)
    if not res or "nodes" not in res or not len(res["nodes"]):
        return None

    items = [
        {"title": i["node"]["title"], "intro": i["node"]["intro"]} for i in res["nodes"]
    ]

    return items[:max_items]


def _clean_text(txt: str) -> str:
    txt = txt.replace("\r", " ").replace("\n", " ").replace("  ", " ")
    return txt.strip()


_BREAK_LENGTH = 1.0  # Seconds
_BREAK_SSML = '<break time="{0}s"/>'.format(_BREAK_LENGTH)


def top_news_answer():
    """ Answer query about top news. """
    headlines = _get_news_data()
    if not headlines:
        return None

    items = [_clean_text(h["intro"]) + " " for h in headlines]
    news = "".join(items).strip()
    # Add a pause between individual news items
    voice_news = _BREAK_SSML.join(items).strip()

    answer = news
    voice = "Í fréttum rúv er þetta helst: {0}".format(voice_news)
    response = dict(answer=answer)

    return response, answer, voice


def sentence(state, result):
    """ Called when sentence processing is complete """
    q: Query = state["query"]
    if "qtype" in result:
        try:
            res = top_news_answer()
            if res:
                # We've successfully answered a query
                q.set_qtype(result.qtype)
                q.set_key("LatestNews")
                q.set_answer(*res)
            else:
                errmsg = "Ekki tókst að sækja fréttir"
                q.set_answer(*gen_answer(errmsg))
            q.set_source("RÚV")
        except Exception as e:
            logging.warning("Exception answering news query '{0}': {1}".format(q, e))
            q.set_error("E_EXCEPTION: {0}".format(e))
            return
    else:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
