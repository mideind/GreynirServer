"""

    Reynir: Natural language processing for Icelandic

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


    This module handles queries related to currencies and exchange rates.

"""

from . import format_icelandic_float
from queries import query_json_api

# Indicate that this module wants to handle parse trees for queries,
# as opposed to simple literal text strings
HANDLE_TREE = True

# The context-free grammar for the queries recognized by this plug-in module
GRAMMAR = """

# A plug-in query grammar always starts with the following,
# adding one or more query productions to the Query nonterminal

Query →
    QCurrency

# By convention, names of nonterminals in query grammars should
# start with an uppercase Q

QCurGenericPrefix → "hvað" "er" | "hvað" "eru" | 0
QCurSpecificPrefix → "hvert" "er" | 0
QCurAnyPrefix → QCurGenericPrefix | QCurSpecificPrefix

# Supported currencies
QCurUnit/fall →
    QCurISK/fall | QCurUSD/fall | QCurEUR/fall | QCurGBP/fall 
    | QCurJPY/fall | QCurRUB/fall | QCurCHF/fall | QCurCAD/fall 
    | QCurZAR/fall | QCurPLN/fall | QCurRUB/fall | QCurCNY/fall

QCurISK/fall →
    'króna:kvk'_et/fall
    | 'króna:kvk'_et_gr/fall

QCurUSD/fall →
    'Bandaríkjadalur:kk'_et/fall 
    | 'Bandaríkjadalur:kk'_et_gr/fall 
    | 'Bandaríkjadollari:kk'_et/fall
    | 'Bandaríkjadollari:kk'_et_gr/fall
    | 'dollari:kk'_et/fall
    | 'dollari:kk'_et_gr/fall

QCurEUR/fall →
    'evra:kvk'_et/fall
    | 'evra:kvk'_et_gr/fall
    | 'evrópumynt:kvk'_et/fall
    | 'evrópumynt:kvk'_et_gr/fall

QCurGBP/fall →
    'pund:hk'_et/fall 
    | 'pund:hk'_et_gr/fall
    | 'breskur:lo'_esb_et_hk/fall 'pund:hk'_et/fall 
    | 'breskur:lo'_esb_et_hk/fall 'pund:hk'_et_gr/fall 
    | 'sterlingspund:hk'_et/fall
    | 'sterlingspund:hk'_et_gr/fall

QCurJPY/fall →
    'jen:hk'_et/fall 
    | 'jen:hk'_et_gr/fall
    # "Japansk jen"

QCurCHF/fall →
    'franki:kk'_et/fall 
    | 'franki:kk'_et_gr/fall
    # "Svissneskur franki"

QCurCAD/fall →
    'kanadadalur:kk'_et/fall 
    | 'kanadadalur:kk'_et_gr/fall 
    | 'kanadadollari:kk'_et/fall
    | 'kanadadollari:kk'_et_gr/fall
    # "Kanada dollari"

QCurZAR/fall →
    'rand:hk'_et/fall 
    | 'rand:hk'_et_gr/fall 
    # "suður-afrískt rand"

QCurPLN/fall →
    'slot:hk'_et/fall 
    | 'slot:hk'_et_gr/fall 
    # "pólskt slot"

QCurRUB/fall →
    'rúbla:kvk'_et/fall 
    | 'rúbla:kvk'_et_gr/fall
    # "Rússnesk rúbla"

QCurCNY/fall →
    'júan:hk'_et/fall 
    | 'júan:hk'_et_gr/fall
    | "yuan"
    # "Kínverskt júan"

QCurNumberWord →
    # to is a declinable number word ('tveir/tvo/tveim/tveggja')
    # töl is an undeclinable number word ('sautján')
    # tala is a number ('17')
    to | töl | tala

QCurCurrencyIndex/fall →
    'gengisvísitala:kvk'_et/fall 
    | 'gengisvísitala:kvk'_et_gr/fall

QCurExchangeRate →
    "gengi" QCurUnit_ef "gagnvart" QCurUnit_þgf

QCurrency →
    # "Hver er gengisvísitalan?"
    "hver" "er" QCurCurrencyIndex_nf '?'?
    
    # "Hvert er gengi X gagnvart Y?"
    | QCurAnyPrefix QCurExchangeRate '?'?

    # "Hvað eru NUM X margir/margar/mörg Y?"
    # |

    # "Hvað fæ ég marga/margar/mörg X fyrir NUM Y?"
    # |


$score(155) QCurrency

"""


def add_currency(curr, result):
    if "currencies" not in result:
        result.currencies = []
    result.currencies.append(curr)


def QCurrency(node, params, result):
    """ Arithmetic query """
    result.qtype = "Currency"
    result.qkey = result._canonical


def QCurUnit(node, params, result):
    c = node.first_child(lambda x: True)
    nt_name = c.string_self()
    nt_name = nt_name.split("_")[0][-3:]
    add_currency(nt_name, result)


def QCurExchangeRate(node, params, result):
    result.op = "exchange"
    result.desc = node.contained_text()


def QCurCurrencyIndex(node, params, result):
    result.op = "index"
    result.desc = node.contained_text()
    add_currency("GVT", result)


CURR_API_URL = "https://apis.is/currency/lb"
ISK_EXCHRATE = {}


def _query_exchange_rate(curr1, curr2):
    res = query_json_api(CURR_API_URL)
    if not res:
        return None

    res = res["results"]

    xr = {c["shortName"]: c["value"] for c in res}

    if curr1 == "GVT":
        return xr["GVT"]
    elif curr2 in xr:
        return xr[curr2]

    return None


# def article_begin(state):
#     print(state)
#     result.currencies = []


def sentence(state, result):
    """ Called when sentence processing is complete """
    q = state["query"]
    if "qtype" in result:
        # Successfully matched a query type

        print(result.currencies)
        # Temp hack while I fix this
        if len(result.currencies) == 1:
            result.currencies.append(None)

        val = _query_exchange_rate(result.currencies[0], result.currencies[1])
        if val:
            answer = format_icelandic_float(val)
            response = dict(answer=answer)
            voice_answer = "{0} er {1}".format(result.desc, answer)
            q.set_answer(response, answer, voice_answer)
            q.set_qtype("Currency")
            q.set_key("ISK")
            return

    state["query"].set_error("E_QUERY_NOT_UNDERSTOOD")
