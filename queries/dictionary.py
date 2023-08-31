"""

    Greynir: Natural language processing for Icelandic

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


    This module handles Icelandic dictionary lookup queries.

"""

# TODO: Properly handle verbs, such as "að veiða"

from typing import List

import logging

from queries import Query, QueryStateDict
from tree import Result, Node, ParamList

from utility import cap_first, icequote
from queries.util import (
    query_json_api,
    gen_answer,
    read_grammar_file,
)


# This module wants to handle parse trees for queries
HANDLE_TREE = True

# The grammar nonterminals this module wants to handle
QUERY_NONTERMINALS = {"QDictQuery"}

# The context-free grammar for the queries recognized by this plug-in module
GRAMMAR = read_grammar_file("dictionary")


def QDictSubjectNom(node: Node, params: ParamList, result: Result) -> None:
    result.qkey = result._text


def QDictWordQuery(node: Node, params: ParamList, result: Result) -> None:
    result.qtype = "Dictionary"


_DICT_SOURCE = "Íslensk nútímamálsorðabók"

_WORD_SEARCH_URL = "https://islenskordabok.arnastofnun.is/django/api/es/flettur/?fletta={0}*&simple=true"
_WORD_LOOKUP_URL = (
    "https://islenskordabok.arnastofnun.is/django/api/es/fletta/{0}/?lang=IS"
)


_ENUM_WORDS = [
    "fyrsta",
    "öðru",
    "þriðja",
    "fjórða",
    "fimmta",
    "sjötta",
    "sjöunda",
    "áttunda",
    "níunda",
    "tíunda",
    "ellefta",
    "tólfta",
]


def _clean4voice(s: str) -> str:
    s = s.replace("osfrv.", "og svo framvegis")
    return s


def _answer_dictionary_query(q: Query, result: Result) -> None:
    """Answer query of the form "hver er orðabókaskilgreiningin á X?" """
    # TODO: Note, here we are taking only the first word of a potential noun phrase
    # containing multiple words. This will have to do for now but can be improved.
    wnat = result.qkey
    word = wnat.split()[0].lower()
    url = _WORD_SEARCH_URL.format(word)

    # Search for word via islenskordabok REST API
    res = query_json_api(url)

    def not_found() -> None:
        """Set answer for cases when word lookup fails."""
        nf = f"Ekki tókst að fletta upp orðinu {icequote(word)}"
        q.set_answer(*gen_answer(nf))
        return None

    # Nothing found
    if not isinstance(res, dict) or "results" not in res or not len(res["results"]):
        return not_found()

    # We're only interested in results where fletta string is equal to word being asked about
    results = [n for n in res["results"] if n.get("fletta") == word and "flid" in n]
    if not results:
        return not_found()

    # OK, we have at least one result.
    # For now, we just naively use the first result
    first = results[0]

    # Look it up by ID via the REST API
    url = _WORD_LOOKUP_URL.format(first["flid"])
    r = query_json_api(url)
    if not isinstance(r, dict):
        return not_found()

    items = r.get("items")
    if not items:
        return not_found()

    # Results from the islenskordabok.arnastofnun.is API are either
    # enumerated definitions or a list of explications. We use the
    # former if available, else the latter

    # Get all enumerated definition IDs ("LIÐUR")
    expl: List[int] = [i["itid"] for i in items if i.get("teg") == "LIÐUR"]
    if expl:
        # Get corresponding "SKÝRING" for each definition ID
        sk = [
            i
            for i in items
            if (i.get("paritem") in expl) and (i.get("teg") == "SKÝRING")
        ]
        df = [i["texti"] for i in sk]
    else:
        # Get all definitions ("SKÝRING")
        df = [i["texti"] for i in items if i.get("teg") == "SKÝRING"]
        # df = sorted(df, key=len)

    # If only one definition found, things are simple
    if len(df) == 1:
        answ = f"{icequote(cap_first(word))} er {icequote(df[0])}"
        voice = answ
    else:
        # Otherwise, do some formatting + spell things out nicely for voice synthesis
        voice = f"Orðið {icequote(word)} getur þýtt: "
        answ = ""
        # Generate list of the form "í fyrsta lagi a, í öðru lagi b, ..."
        for i, x in enumerate(df[: len(_ENUM_WORDS)]):
            answ += f"{i+1}. {x}\n"
            enum = f"í {_ENUM_WORDS[i]} lagi,"
            voice += f"{enum} {x.replace('<', '[').replace('>', ']')}, "
        answ = answ.rstrip(",.\n ") + "."
        voice = voice.rstrip(",.\n").strip() + "."
        voice = _clean4voice(voice)

    q.set_answer(dict(answer=answ), answ, voice)

    # Beautify query by placing word being asked about within quote marks
    bq = q.beautified_query.replace(wnat, icequote(word))
    q.set_beautified_query(bq)
    q.set_source(_DICT_SOURCE)


def sentence(state: QueryStateDict, result: Result):
    """Called when sentence processing is complete"""
    q: Query = state["query"]
    if "qtype" in result and "qkey" in result:
        # Successfully matched a query type
        try:
            _answer_dictionary_query(q, result)
        except Exception as e:
            logging.warning(f"Exception while processing dictionary query: {e}")
            q.set_error(f"E_EXCEPTION: {e}")
            return
        q.set_qtype(result.qtype)
        q.set_key(result.qkey)
    else:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
