"""

    Greynir: Natural language processing for Icelandic

    Example of a grammar query processor module.

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


    This module is an example of a plug-in query response module
    for the Greynir query subsystem. It handles grammar queries, i.e.
    queries that require grammatical parsing of the query text.


"""

import random

# Indicate that this module wants to handle parse trees for queries,
# as opposed to simple literal text strings
HANDLE_TREE = True


TOPIC_LEMMAS = ["prufa"]


def help_text(lemma: str) -> str:
    """ Help text to return when query.py is unable to parse a query but
        one of the above lemmas is found in it """
    return "Ég get svarað ef þú spyrð til dæmis: {0}?".format(
        random.choice(("Er þetta prufa", "Gæti þetta verið prufa"))
    )


# The context-free grammar for the queries recognized by this plug-in module
GRAMMAR = """

Query →
    QGrammarExample '?'?

QGrammarExampleQuery →
    "er" "þetta" QGrammarExampleTestOrNot
    | "gæti" "þetta" "verið" QGrammarExampleTestOrNot

QGrammarExampleTestOrNot →
    QGrammarExampleTest | QGrammarExampleNotTest

QGrammarExampleTest →
    "prufa"

QGrammarExampleNotTest →
    "ekki" "prufa"

"""


def QGrammarExampleQuery(node, params, result):
    # Set the query type
    result.qtype = "GrammarTest"


def QGrammarExampleTest(node, params, result):
    result.qkey = "Test"


def QGrammarExampleNotTest(node, params, result):
    result.qkey = "NotTest"


def sentence(state, result):
    """ Called when sentence processing is complete """
    q = state["query"]
    if "qtype" in result and "qkey" in result and result.qtype == "GrammarTest":
        # Successfully matched this query type, we're handling it...
        q.set_qtype(result.qtype)

        answ = "Já" if result.qkey == "Test" else "Nei"
        voice = answ
        response = dict(answer=answ)

        # Set query answer
        q.set_answer(response, answ, voice)
        q.set_key(result.qkey)
        return

    # This module did not understand the query
    q.set_error("E_QUERY_NOT_UNDERSTOOD")
