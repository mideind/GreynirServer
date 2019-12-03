"""

    Reynir: Natural language processing for Icelandic

    Television schedule query response module

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
    along with this program. If not, see http://www.gnu.org/licenses/.


    This module handles queries related to counting up or down.

"""


_COUNTING_QTYPE = "Counting"


# This module wants to handle parse trees for queries
HANDLE_TREE = True

# The context-free grammar for the queries recognized by this plug-in module
GRAMMAR = """

Query →
    QCounting

QCounting → QCountingQuery '?'? 

QCountingQuery →
    QCountingUp | QCountingDown

QCountingUp →
    "teldu" QCountingSpeed? "upp" "að" QCountingNumber
    | "teldu" QCountingSpeed? "upp" "í" QCountingNumber

QCountingDown →
    "teldu" QCountingSpeed? "niður" "frá" QCountingNumber

QCountingBetween →
    "teldu" QCountingSpeed? "frá" QCountingNumber "upp"? "til" QCountingNumber
    | "teldu" QCountingSpeed? "frá" QCountingNumber "upp" "í" QCountingNumber
    | "teldu" QCountingSpeed? "frá" QCountingNumber "upp" "að" QCountingNumber

QCountingNumber →
    to | töl | tala

QCountingSpeed →
    "mjög" "hægt" | "hægt" | "hratt" | "mjög" "hratt"

$score(+35) QCounting

"""


def QCountingQuery(node, params, result):
    # Set the query type
    result.qtype = _COUNTING_QTYPE


def QCountingUp(node, params, result):
    result.qkey = "CountUp"


def QCountingDown(node, params, result):
    result.qkey = "CountDown"


def QCountingBetween(node, params, result):
    result.qkey = "CountBetween"
  

def _gen_count(q):
    pass


def sentence(state, result):
    """ Called when sentence processing is complete """
    q = state["query"]
    if "qtype" in result and "qkey" in result:
        # Successfully matched a query type
        q.set_qtype(result.qtype)
        q.set_key(result.qkey)

        try:
            r = _gen_count(q)
            q.set_answer(*r)
            q.set_expires(datetime.utcnow() + timedelta(hours=24))
        except Exception as e:
            logging.warning("Exception while processing counting query: {0}".format(e))
            q.set_error("E_EXCEPTION: {0}".format(e))
    else:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
