"""

    Reynir: Natural language processing for Icelandic

    Wikipedia query response module

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

# TODO: Shorten overly long first paragraphs.

from queries import query_json_api
from datetime import datetime, timedelta
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
    QWikiQuery '?'?

QWikiQuery →
    "hvað" "segir" QWikipedia "um" QWikiSubject
    | "hvað" "getur" QWikipedia "sagt" "mér"? "um" QWikiSubject
    | "hvaða" "upplýsingar" "er" QWikipedia "með" "um" QWikiSubject
    | "hvaða" "upplýsingum" "býr" QWikipedia "yfir" "varðandi" QWikiSubject
    | "hvað" "myndi" QWikipedia "segja" "mér"? "um" QWikiSubject
    | "fræddu" "mig" "um" QWikiSubject
    # | "flettu" "upp" QWikiSubject "í" QWikipedia
    # | "hvað" "er" QWikiSubject "samkvæmt" QWikipedia
    # | "hver" "er QWikiSubject "samkvæmt" QWikipedia

QWikiSubject →
    Nl_þf

QWikipedia →
    {0}

$score(+35) QWikiQuery

""".format(
    " | ".join('"' + v + '"' for v in _WIKI_VARIATIONS)
)


def QWikiQuery(node, params, result):
    # Set the query type
    result.qtype = _WIKI_QTYPE
    result.qkey = result["subject_nom"]


def QWikiSubject(node, params, result):
    result["subject_nom"] = result._nominative.title()
    result["subject_dat"] = result._text


def EfLiður(node, params, result):
    """ Don't change the case of possessive clauses """
    result._nominative = result._text


def FsMeðFallstjórn(node, params, result):
    """ Don't change the case of prepositional clauses """
    result._nominative = result._text


def _clean_answer(answer):
    # Split on newline, use only first paragraph
    a = answer.split("\n")[0].strip()
    # Get rid of "Getur líka átt við" leading sentence
    if a.startswith("Getur líka átt"):
        a = ". ".join(a.split(".")[1:])
    # Remove text within parentheses
    a = re.sub(r"\([^)]+\)", "", a)
    # Fix any whitespace formatting issues created by
    # removing text within parentheses
    a = re.sub(r"\s+", " ", a)
    a = re.sub(r"\s\.$", ".", a)
    a = re.sub(r"\s,\s.", ", ", a)
    return a


_WIKI_API_URL = "https://is.wikipedia.org/w/api.php?format=json&action=query&prop=extracts&exintro&explaintext&redirects=1&titles={0}"


def _query_wiki_api(subject):
    """ Fetch JSON from Wikipedia API """
    url = _WIKI_API_URL.format(subject)
    return query_json_api(url)


def get_wiki_summary(subject_nom, subject_dat):
    """ Fetch summary of subject from Icelandic Wikipedia """
    res = _query_wiki_api(subject_nom)

    not_found = "Ég fann ekkert um {0} í Wikipedíu".format(subject_dat)

    if not res or "query" not in res or "pages" not in res["query"]:
        return not_found

    pages = res["query"]["pages"]
    keys = pages.keys()
    if not len(keys) or "-1" in keys:
        return not_found

    k = sorted(keys)[0]

    text = pages[k].get("extract", "")

    return _clean_answer(text)


def sentence(state, result):
    """ Called when sentence processing is complete """
    q = state["query"]
    if "qtype" in result and "subject_nom" in result:
        # Successfully matched a query type
        q.set_qtype(result.qtype)
        q.set_key(result.qkey)

        # Fetch from Wikipedia API
        answer = get_wiki_summary(result["subject_nom"], result["subject_dat"])
        response = dict(answer=answer)
        voice = answer
        q.set_answer(response, answer, voice)

        # Beautify query by fixing spelling of Wikipedia
        b = q.beautified_query
        for w in _WIKI_VARIATIONS:
            b = b.replace(w, _WIKIPEDIA_CANONICAL)
            b = b.replace(w.capitalize(), _WIKIPEDIA_CANONICAL)
        q.set_beautified_query(b)

        # Cache reply for 24 hours
        q.set_expires(datetime.utcnow() + timedelta(hours=24))

    else:
        state["query"].set_error("E_QUERY_NOT_UNDERSTOOD")
