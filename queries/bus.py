"""

    Reynir: Natural language processing for Icelandic

    Bus schedule query module

    Copyright (C) 2019 Miðeind ehf.
    Original author: Vilhjálmur Þorsteinsson

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


    This module implements a query processor for information about
    bus schedules.

"""


# Indicate that this module wants to handle parse trees for queries
HANDLE_TREE = True


def query_arrival_time(query, session, bus_number):
    """ A query for a person by name """
    response = dict(answer="15:33")
    voice_answer = bus_number + " kemur klukkan 15 33"
    return response, voice_answer


_QFUNC = {
    "ArrivalTime": query_arrival_time,
}


def sentence(state, result):
    """ Called when sentence processing is complete """
    q = state["query"]
    if "qtype" in result:
        # Successfully matched a query type
        q.set_qtype(result.qtype)
        q.set_key(result.qkey)
        session = state["session"]
        # Select a query function and exceute it
        qfunc = _QFUNC.get(result.qtype)
        if qfunc is None:
            q.set_answer(result.qtype + ": " + result.qkey)
        else:
            try:
                voice_answer = None
                answer = qfunc(q, session, result.qkey)
                if isinstance(answer, tuple):
                    # We have both a normal and a voice answer
                    answer, voice_answer = answer
                q.set_answer(answer, voice_answer)
            except AssertionError:
                raise
            except Exception as e:
                q.set_error("E_EXCEPTION: {0}".format(e))
    else:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")


GRAMMAR = """ """

_GRAMMAR = """

# ----------------------------------------------
#
# Query grammar
#
# The following grammar is used for queries only
#
# ----------------------------------------------

$if(include_queries)

QueryRoot →
    QArrivalTime

QArrivalTime →
    'hvenær:st' 'koma:so'_gm_fh_nt_p3 QBus_nf '?'?
    | 'hvenær:st' 'vera:so'_gm_fh_nt_p3 'von:kvk'_nf_et 'á:fs'_þgf QBus_þgf '?'?

QBus/fall →
    QBusWord/fall | QBusNumber/fall

QBusWord/fall →
    'ás:kk'_et_gr/fall
    | 'tvistur:kk'_et_gr/fall
    | 'þristur:kk'_et_gr/fall
    | 'fjarki:kk'_et_gr/fall
    | 'fimma:kvk'_et_gr/fall
    | 'sexa:kvk'_et_gr/fall
    | 'sjöa:kvk'_et_gr/fall
    | 'átta:kvk'_et_gr/fall
    | 'nía:kvk'_et_gr/fall
    | 'tía:kvk'_et_gr/fall
    | 'tólfa:kvk'_et_gr/fall

QBusNumber/fall →
    'leið:kvk'_et/fall QBusNumberWord

QBusNumberWord →
    to_nf_ft_hk

$endif(include_queries)

"""


# The following functions correspond to grammar nonterminals (see Reynir.grammar)
# and are called during tree processing (depth-first, i.e. bottom-up navigation)


def QArrivalTime(node, params, result):
    """ Arrival time query """
    result.qtype = "ArrivalTime"
    if "bus_number" in result:
        result.qkey = result.bus_number


def QBus(node, params, result):
    pass


def QBusWord(node, params, result):
    result.bus_number = result._nominative


def QBusNumber(node, params, result):
    pass


def QBusNumberWord(node, params, result):
    result.bus_number = result._text

