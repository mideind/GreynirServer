"""

    Greynir: Natural language processing for Icelandic

    News query response module

    Copyright (C) 2023 Miðeind ehf.

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


    This module handles queries related to current news and news headlines.
    Uses the RÚV JSON API to fetch top headlines from the ruv.is front page.

"""

# TODO: Fyrirsagnir, og að styðja "Segðu mér meira um X"
# TODO: Hvað er helst í fréttum í dag? Fréttir dagsins?
# TODO: Phonetically transcribe news

from typing import Any, List, Optional, Dict, cast

import logging
import cachetools  # type: ignore
import random

from speech.trans import gssml
from queries import Query, QueryStateDict, AnswerTuple
from queries.util import gen_answer, query_json_api, read_grammar_file
from tree import Result, Node


_NEWS_QTYPE = "News"


TOPIC_LEMMAS = ["fréttir", "fregnir", "frétta"]


def help_text(lemma: str) -> str:
    """Help text to return when query processor is unable to parse a query but
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
GRAMMAR = read_grammar_file("news")


# Grammar nonterminal plugins
def QNewsQuery(node: Node, params: QueryStateDict, result: Result) -> None:
    result.qtype = _NEWS_QTYPE


_NEWS_API = "https://ruv.is/json/frettir/hladbord"
_NEWS_CACHE_TTL = 300  # seconds, ttl = 5 mins


@cachetools.cached(cast(Any, cachetools).TTLCache(1, _NEWS_CACHE_TTL))
def _get_news_data(max_items: int = 8) -> Optional[List[Dict[str, str]]]:
    """Fetch news headline data from RÚV, preprocess it."""
    res = query_json_api(_NEWS_API)
    if not isinstance(res, dict) or "nodes" not in res or not len(res["nodes"]):
        return None

    try:
        items = [
            {"title": i["node"]["title"], "intro": i["node"]["intro"]}
            for i in res["nodes"]
        ]
        return items[:max_items]
    except Exception as e:
        logging.warning(f"Exception parsing news data: {e}")

    return None


def _clean_text(txt: str) -> str:
    txt = txt.replace("\r", " ").replace("\n", " ").replace("  ", " ")
    return txt.strip()


def top_news_answer() -> Optional[AnswerTuple]:
    """Answer query about top news."""
    headlines = _get_news_data()
    if not headlines:
        return None

    items = [_clean_text(h["intro"]) + " " for h in headlines]
    news = "".join(items).strip()
    voice_news = ""
    for item in items:
        # TODO: Transcribing the news using 'generic'
        # costs 6 seconds when not cached,
        # this is too costly at the moment
        # voice_news += gssml(item, type="generic")
        voice_news += item
        # Add a pause between individual news items
        voice_news += gssml(type="vbreak", time="1s")

    answer = news
    voice = f"Í fréttum rúv er þetta helst. {voice_news}"
    response = dict(answer=answer)

    return response, answer, voice


def sentence(state: QueryStateDict, result: Result) -> None:
    """Called when sentence processing is complete."""
    q: Query = state["query"]
    if "qtype" in result:
        try:
            res = top_news_answer()
            if res:
                # We've successfully answered a query
                q.set_qtype(result.qtype)
                q.set_key("LatestNews")
                q.set_answer(*res)
                q.set_source("RÚV")
            else:
                errmsg = "Ekki tókst að sækja fréttir."
                q.set_answer(*gen_answer(errmsg))
        except Exception as e:
            logging.warning(f"Exception answering news query '{q}': {e}")
            q.set_error(f"E_EXCEPTION: {e}")

        return

    q.set_error("E_QUERY_NOT_UNDERSTOOD")
