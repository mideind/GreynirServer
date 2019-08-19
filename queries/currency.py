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
import re

_CURRENCY_QTYPE = "Currency"

_NUMBER_WORDS = {
    "núll": 0,
    "einn": 1,
    "tveir": 2,
    "þrír": 3,
    "fjórir": 4,
    "fimm": 5,
    "sex": 6,
    "sjö": 7,
    "átta": 8,
    "níu": 9,
    "tíu": 10,
    "ellefu": 11,
    "tólf": 12,
    "þrettán": 13,
    "fjórtán": 14,
    "fimmtán": 15,
    "sextán": 16,
    "sautján": 17,
    "átján": 18,
    "nítján": 19,
    "tuttugu": 20,
    "þrjátíu": 30,
    "fjörutíu": 40,
    "fimmtíu": 50,
    "sextíu": 60,
    "sjötíu": 70,
    "áttatíu": 80,
    "níutíu": 90,
    "hundrað": 100,
    "þúsund": 1000,
    "milljón": 1e6,
    "milljarður": 1e9,
}

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
    'króna:kvk'/fall
    | 'króna:kvk'_gr/fall
    | 'íslenskur:lo'_kvk/fall 'króna:kvk'/fall 
    | 'íslenskur:lo'_kvk/fall 'króna:kvk'_gr/fall 

QCurUSD/fall →
    'Bandaríkjadalur:kk'/fall 
    | 'Bandaríkjadalur:kk'_gr/fall 
    | 'Bandaríkjadollari:kk'/fall
    | 'Bandaríkjadollari:kk'_gr/fall
    | 'dollari:kk'/fall
    | 'dollari:kk'_gr/fall

QCurEUR/fall →
    'evra:kvk'/fall
    | 'evra:kvk'_gr/fall
    | 'evrópumynt:kvk'/fall
    | 'evrópumynt:kvk'_gr/fall

QCurGBP/fall →
    'pund:hk'/fall 
    | 'pund:hk'_gr/fall
    | 'breskur:lo'_hk/fall 'pund:hk'/fall 
    | 'breskur:lo'_hk/fall 'pund:hk'_gr/fall 
    | 'sterlingspund:hk'/fall
    | 'sterlingspund:hk'_gr/fall

QCurJPY/fall →
    'jen:hk'/fall 
    | 'jen:hk'_gr/fall
    # "Japansk jen"

QCurCHF/fall →
    'franki:kk'/fall 
    | 'franki:kk'_gr/fall
    # "Svissneskur franki"

QCurCAD/fall →
    'kanadadalur:kk'/fall 
    | 'kanadadalur:kk'_gr/fall 
    | 'kanadadollari:kk'/fall
    | 'kanadadollari:kk'_gr/fall
    | 'kanadískur:lo'_hk/fall 'dollari:kk'/fall 
    | 'kanadískur:lo'_hk/fall 'dollari:kk'_gr/fall 
    # "Kanada dollari"

QCurZAR/fall →
    'rand:hk'/fall 
    | 'rand:hk'_gr/fall 
    | 'suðurafrískur:lo'_hk/fall 'rand:hk'/fall 
    | 'suðurafrískur:lo'_hk/fall 'rand:hk'_gr/fall 

QCurPLN/fall →
    'slot:hk'/fall 
    | 'slot:hk'_gr/fall
    | 'pólskur:lo'_hk/fall 'slot:hk'/fall 
    | 'pólskur:lo'_hk/fall 'slot:hk'_gr/fall 
    | "zloty"
    
QCurRUB/fall →
    'rúbla:kvk'/fall 
    | 'rúbla:kvk'_gr/fall
    # "Rússnesk rúbla"

QCurCNY/fall →
    'júan:hk'/fall 
    | 'júan:hk'_gr/fall
    | "júan"
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

QCurVisAVis → "gagnvart" | "á" "móti"

QCurExchangeRate →
    "gengi" QCurUnit_ef QCurVisAVis QCurUnit_þgf

QCurGeneralRate →
    "gengi" QCurUnit_ef

QCurAmountConversion →
    QCurNumberWord QCurUnit_nf "margar" QCurUnit_nf

QCurrency →
    # "Hver er gengisvísitalan?"
    "hver" "er" QCurCurrencyIndex_nf '?'?
    
    # "Hvert er gengi X?"
    | QCurAnyPrefix QCurGeneralRate '?'?

    # "Hvert er gengi X gagnvart Y?"
    | QCurAnyPrefix QCurExchangeRate '?'?

    # "Hvað eru NUM X margir/margar/mörg Y?"
    | QCurGenericPrefix QCurAmountConversion '?'?

    # "Hvað fæ ég marga/margar/mörg X fyrir NUM Y?"
    # |

$score(155) QCurrency

"""


def parse_num(num_str):
    """ Parse Icelandic number string to float or int """
    num = None
    try:
        # Handle numbers w. Icelandic decimal places ("17,2")
        if re.search(r"^\d+,\d+", num_str):
            num = float(num_str.replace(",", "."))
        # Handle digits ("17")
        else:
            num = float(num_str)
    except ValueError:
        # Handle number words ("sautján")
        if num_str in _NUMBER_WORDS:
            num = _NUMBER_WORDS[num_str]
        else:
            num = 0
    except Exception as e:
        print("Unexpected exception: {0}".format(e))
        raise
    return num


def add_num(num, result):
    """ Add a number to accumulated number args """
    if "numbers" not in result:
        result.numbers = []
    if isinstance(num, str):
        result.numbers.append(parse_num(num))
    else:
        result.numbers.append(num)


def add_currency(curr, result):
    if "currencies" not in result:
        result.currencies = []
    result.currencies.append(curr)


def QCurrency(node, params, result):
    """ Arithmetic query """
    result.qtype = "Currency"
    result.qkey = result._canonical


def QCurNumberWord(node, params, result):
    add_num(result._nominative, result)


def QCurUnit(node, params, result):
    c = node.first_child(lambda x: True)
    nt_name = c.string_self()
    nt_name = nt_name.split("_")[0][-3:]
    add_currency(nt_name, result)


def QCurExchangeRate(node, params, result):
    result.op = "exchange"
    result.desc = node.contained_text()


def QCurGeneralRate(node, params, result):
    result.op = "general"
    result.desc = node.contained_text()


def QCurCurrencyIndex(node, params, result):
    result.op = "index"
    result.desc = node.contained_text()
    add_currency("GVT", result)


def QCurAmountConversion(node, params, result):
    result.op = "convert"
    result.desc = node.contained_text()


CURR_API_URL = "https://apis.is/currency/lb"
ISK_EXCHRATE = {}


def _query_exchange_rate(curr1, curr2):
    """ Returns exchange rate of two ISO 4217 currencies """
    # TODO: Add caching
    res = query_json_api(CURR_API_URL)
    if not res:
        return None
    if curr1 == curr2:
        return 1

    res = res["results"]

    xr = {c["shortName"]: c["value"] for c in res}

    print("{0} gagnvart {1}".format(curr1, curr2))

    if curr1 == "GVT":
        return xr["GVT"]
    elif curr1 == "ISK" and curr2 in xr:
        return xr[curr2]
    elif curr1 in xr and curr2 == "ISK":
        return xr[curr1]
    elif curr1 in xr and curr2 in xr:
        return xr[curr1] / xr[curr2]

    return None


def sentence(state, result):
    """ Called when sentence processing is complete """
    q = state["query"]
    if "qtype" in result:
        # Successfully matched a query type
        val = None

        if result.op == "index":
            val = _query_exchange_rate("GVT", None)
        elif result.op == "exchange":
            val = _query_exchange_rate(result.currencies[0], result.currencies[1])
        elif result.op == "general":
            pass
        elif result.op == "convert":
            val = _query_exchange_rate(result.currencies[1], result.currencies[0])
            val = val * result.numbers[0]
            print(
                "Converting {0} {1} to {2}".format(
                    result.numbers[0], result.currencies[0], result.currencies[1]
                )
            )
        else:
            raise Exception("Unknown operator: {0}".format(result.op))

        if val:
            answer = format_icelandic_float(val)
            response = dict(answer=answer)
            voice_answer = "{0} er {1}".format(result.desc, answer)
            q.set_answer(response, answer, voice_answer)
            q.set_key("ISK")
            q.set_qtype(_CURRENCY_QTYPE)

        return

    state["query"].set_error("E_QUERY_NOT_UNDERSTOOD")
