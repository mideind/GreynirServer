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


    This modules answers queries by fetching information on diverse topics
    from the Icelandic Wikipedia API.

"""

# TODO: Clean up query string, show canonical Wikipedia name in Icelandic

from . import query_json_api
from pprint import pprint
import re

_WIKI_QTYPE = "Wikipedia"

# For end user presentation
_WIKIPEDIA_CANONICAL = "Wikipedía"
_WIKIPEDIA_VOICE = "Vikipedía"

_WIKI_VARIATIONS = (
    "vikipedija",
    "víkípedija",
    "vikípedija",
    "víkipedija",
    "víkípedía",
    "víkipedía",
    "vikípedía",
    "vikipedía",
    "wikipedia",
    "wikipedía",
)

# Indicate that this module wants to handle parse trees for queries,
# as opposed to simple literal text strings
HANDLE_TREE = True

# The context-free grammar for the queries recognized by this plug-in module
GRAMMAR = """

Query →
    QWiki

QWiki →
    "hvað" "segir" "vikipedija" "um" QWikiSubject '?'? 
    | "hvaða" "upplýsingar" "er" QWikipedia "með" "um" QWikiSubject '?'?

QWikiSubject →
    Nl_þf

QWikipedia →
    {0}

$score(+535) QWiki

""".format(
    " | ".join(_WIKI_VARIATIONS)
)


def QWiki(node, params, result):
    # Set the query type
    result.qtype = _WIKI_QTYPE
    result.qkey = result["subject"]


def Nl(node, params, result):
    result["subject"] = result._nominative.title()


def _clean_answer(answer):
    # Remove text within parentheses
    a = re.sub(r"\([^)]+\)", "", answer)
    # Split on newline, use only first paragraph
    a = a.split("\n")[0]
    return a


_WIKI_API_URL = "https://is.wikipedia.org/w/api.php?format=json&action=query&prop=extracts&exintro&explaintext&redirects=1&titles={0}"


def _query_wiki_api(subject):
    url = _WIKI_API_URL.format(subject)
    return query_json_api(url)


def get_wiki_summary(subject):
    res = _query_wiki_api(subject)
    print(res)
    if not res or "query" not in res or "pages" not in res["query"]:
        return None

    pages = res["query"]["pages"]
    keys = pages.keys()
    if not len(keys):
        # logging.warning("No info found on Wikipedia: {0}", res)
        return None

    k = sorted(keys)[0]

    text = pages[k].get("extract", "")

    return _clean_answer(text)


def sentence(state, result):
    """ Called when sentence processing is complete """
    q = state["query"]
    if "qtype" in result and "subject" in result:
        # Successfully matched a query type
        q.set_qtype(result.qtype)
        q.set_key(result.qkey)

        answer = get_wiki_summary(result["subject"])
        response = dict(answer=answer)
        voice_answer = answer
        q.set_answer(response, answer, voice_answer)
    else:
        state["query"].set_error("E_QUERY_NOT_UNDERSTOOD")
