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


    This module handles Icelandic dictionary lookup queries.

"""

# TODO: Properly handle verbs, such as "að veiða"

import logging
from pprint import pprint

from reynir import NounPhrase

from query import Query

from . import query_json_api, gen_answer, cap_first, icequote


# This module wants to handle parse trees for queries
HANDLE_TREE = True

# The context-free grammar for the queries recognized by this plug-in module
GRAMMAR = """

Query →
    QDictQuery '?'?

QDictQuery →
    QDictWordQuery

QDictWordQuery →
    "hvað" "segir" QDictDict "um" "orðið"? QDictSubjectNom
    | "hver" "er" "skilgreiningin" "á" "orðinu"? QDictSubjectNom QDictInDictionary?
    | "flettu" "upp" "orðinu"? QDictSubjectNom QDictInDictionary?
    | "hvernig" "skilgreinir" QDictDict "orðið"? QDictSubjectNom
    | "hvernig" "er" "orðið"? QDictSubjectNom "skilgreint" QDictInDictionary?
    | "skilgreining" "á" "orðinu"? QDictSubjectNom
    | "skilgreiningin" "á" "orðinu"? QDictSubjectNom
    | "orðabókarskilgreining" "á" "orðinu"? QDictSubjectNom
    | "orðabókarskilgreiningin" "á" "orðinu"? QDictSubjectNom
    | "orðabókaskilgreining" "á" "orðinu"? QDictSubjectNom
    | "orðabókaskilgreiningin" "á" "orðinu"? QDictSubjectNom
    | "skilgreindu" "orðið"? QDictSubjectNom
    | "komdu" "með" "skilgreininguna" "á" "orðinu"? QDictSubjectNom

QDictInDictionary →
    "í" "orðabók" | "í" "orðabókinni"
    | "í" "íslenskri" "orðabók" | "í" "íslensku" "orðabókinni"

QDictDict →
    "orðabók" | "orðabókin" | "íslensk" "orðabók" | "íslenska" "orðabókin"

QDictSubjectNom →
    Nl

$score(+135) QDictQuery

"""


def QDictSubjectNom(node, params, result):
    n = result._text
    nom = NounPhrase(n).nominative or n
    result.qkey = nom


def QDictWordQuery(node, params, result):
    result.qtype = "DictionaryWord"


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
]


def _answer_dictionary_query(q: Query, result):
    """ Answer query of the form "hver er orðabókaskilgreiningin á X?" """
    word = result.qkey.split()[0].lower()
    wnat = result.qkey
    url = _WORD_SEARCH_URL.format(word)

    # Search for word via islenskordabok REST API
    res = query_json_api(url)

    # Nothing found
    if not res or "results" not in res or not len(res["results"]):
        return None

    # We have at least one result. Does it match?
    first = res["results"][0]
    if first.get("fletta") != word or "flid" not in first:
        return None

    # For now, we just naively use the first result
    # Look it up by ID via the REST API
    url = _WORD_LOOKUP_URL.format(first["flid"])
    r = query_json_api(url)
    if not r:
        return None

    items = r.get("items")
    if not items:
        return None

    # Get all definitions ("skýringar")
    expl = [i["texti"] for i in items if i.get("teg") == "SKÝRING"]

    # If only one definition found, things are simple
    if len(expl) == 1:
        answ = "{0} er {1}".format(icequote(cap_first(word)), icequote(expl[0]))
        voice = answ
    else:
        # Otherwise, do some nice formatting + spell things out nicely to impr. voice synthesis
        voice = "Orðið {0} getur þýtt: ".format(icequote(word))
        answ = ""
        for i, x in enumerate(expl):
            answ += "{0}. {1}\n".format(i + 1, x)
            enum = "í {0} lagi,".format(_ENUM_WORDS[i])
            voice += "{0} {1}, ".format(enum, x)
        answ = answ.rstrip(", ") + "."
        voice = voice.rstrip(", ") + "."

    # Beautify query by placing word being asked about within parentheses
    bq = q.beautified_query.replace(wnat, icequote(cap_first(word)))
    q.set_beautified_query(bq)

    # Note source
    q.set_source(_DICT_SOURCE)

    return dict(answer=answ), answ, voice


def sentence(state, result):
    """ Called when sentence processing is complete """
    q: Query = state["query"]
    if "qtype" in result and "qkey" in result:
        # Successfully matched a query type
        q.set_qtype(result.qtype)
        q.set_key(result.qkey)

        try:
            r = _answer_dictionary_query(q, result)
            if not r:
                r = gen_answer("Ekki tókst að fletta upp viðkomandi orði.")
            q.set_answer(*r)
            # q.set_expires(datetime.utcnow() + timedelta(hours=24))
        except Exception as e:
            logging.warning(
                "Exception while processing dictionary query: {0}".format(e)
            )
            q.set_error("E_EXCEPTION: {0}".format(e))
    else:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
