"""

    Greynir: Natural language processing for Icelandic

    Opinion query response module

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


    This module handles queries related to Embla's opinions.

"""


from datetime import datetime, timedelta

from query import Query
from queries import gen_answer


_OPINION_QTYPE = "Opinion"


# Indicate that this module wants to handle parse trees for queries,
# as opposed to simple literal text strings
HANDLE_TREE = True

# The grammar nonterminals this module wants to handle
QUERY_NONTERMINALS = {"QOpinion"}

# The context-free grammar for the queries recognized by this plug-in module
GRAMMAR = """

Query →
    QOpinion

QOpinion →
    QOpinionQuery '?'?

QOpinionQuery →
    "hvað" "finnst" "þér" "eiginlega"? "um" QOpinionSubject_þf
    | "hvað" "þykir" "þér" "eiginlega"? "um" QOpinionSubject_þf
    | "hvaða" "skoðun" QOpinionWhichDoYouHave "eiginlega"? "á" QOpinionSubject_þgf
    | "hver" "er" "skoðun" "þín" "á" QOpinionSubject_þgf
    | "hvaða" "skoðanir" QOpinionWhichDoYouHave? "eiginlega"? "á" QOpinionSubject_þgf
    | "hvert" "er" "álit" "þitt" "á" QOpinionSubject_þgf
    | "hvaða" "álit" QOpinionWhichDoYouHave? "eiginlega"? "á" QOpinionSubject_þgf
    | QOpinionAreYou QOpinionEmotions QOpinionDueTo QOpinionSubject_þgf

QOpinionSubject/fall →
    Nl/fall

QOpinionAreYou →
    "ertu" | "ert" "þú"

QOpinionWhichDoYouHave →
    "hefurðu" | "hefur" "þú" | "ertu" "með" | "ertu" "þú" "með"

QOpinionEmotions →
    "reið" | "bitur" | "í" "uppnámi" | "brjáluð" | "vonsvikin"

QOpinionDueTo →
    "út" "af" | "yfir"

$tag(keep) QOpinionSubject/fall

"""


def QOpinionQuery(node, params, result):
    result["qtype"] = _OPINION_QTYPE


def QOpinionSubject(node, params, result):
    result["subject_nom"] = result._nominative


def sentence(state, result):
    """ Called when sentence processing is complete """
    q: Query = state["query"]

    if "qtype" not in result or "subject_nom" not in result:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
        return

    # OK, we've successfully matched a query type
    subj = result["subject_nom"]
    answer = "Ég hef enga sérstaka skoðun í þeim efnum."
    q.set_answer(*gen_answer(answer))
    q.set_qtype(_OPINION_QTYPE)
    q.set_context(dict(subject=subj))
    q.set_key(subj)
    q.set_expires(datetime.utcnow() + timedelta(hours=24))
