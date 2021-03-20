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


    This module handles Ja.is API queries.

"""

# TODO: Handle context queries
# TODO: Handle "hver er *heima*síminn hjá X"
# TODO: Reverse phone num lookup
# TODO: Smarter disambiguation interaction

from typing import Dict, Optional

import logging
from urllib.parse import urlencode

# from datetime import datetime, timedelta

from reynir import NounPhrase

from . import query_json_api, gen_answer
from query import Query
from geo import iceprep_for_street
from util import read_api_key


# Module priority
PRIORITY = 5

# This module wants to handle parse trees for queries
HANDLE_TREE = True

# The grammar nonterminals this module wants to handle
QUERY_NONTERMINALS = {"QJaQuery"}

# The context-free grammar for the queries recognized by this plug-in module
GRAMMAR = """

Query →
    QJaQuery '?'?

QJaQuery →
    QJaPhoneNumQuery

QJaPhoneNumQuery →
    QJaName4PhoneNumQuery | QJaPhoneNum4NameQuery

QJaPhoneNum4NameQuery →
    QJaWhatWhich "er" QJaTheNumber_nf "hjá" QJaSubject
    | "hvaða" QJaTheNumber_þf "er" QJaSubject "með"
    | "flettu" "upp" QJaTheNumber_þgf "hjá" QJaSubject

QJaName4PhoneNumQuery →
    "hver" "er" "með" QJaTheNumber_þf QJaPhoneNum QJaInPhonebook?
    | "hverjir" "eru" "með" QJaTheNumber_þf QJaPhoneNum QJaInPhonebook?
    | "flettu" "upp" QJaTheNumber_þgf QJaPhoneNum QJaInPhonebook?

QJaThemÞgf →
    "hann" | "hana" | "þau" | "þá" | "þær" | "það" "númer"? | "þetta" "númer"?

QJaInPhonebook →
    "í" "símaskránni" | "á" "já" "punktur" "is"

QJaPhoneNum →
    Nl

QJaSubject →
    Nl

QJaTheNumber/fall →
    'númer:hk'/fall
    | 'símanúmer:hk'/fall
    | 'sími:kk'/fall

QJaWhatWhich →
    "hvert" | "hvað" | "hver"

$score(+35) QJaQuery

"""


def QJaSubject(node, params, result):
    n = result._text
    nom = NounPhrase(n).nominative or n
    result.qkey = nom


def QJaPhoneNum(node, params, result):
    result.phone_number = result._text


def QJaName4PhoneNumQuery(node, params, result):
    result.qtype = "Name4PhoneNum"


def QJaPhoneNum4NameQuery(node, params, result):
    result.qtype = "PhoneNum4Name"


_JA_SOURCE = "ja.is"

_JA_API_URL = "https://api.ja.is/search/v6/?{0}"


def query_ja_api(q: str) -> Optional[Dict]:
    """ Send query to ja.is API """
    key = read_api_key("JaServerKey")
    if not key:
        # No key, can't query the API
        logging.warning("No API key for ja.is")
        return None

    qd = {"q": q}
    headers = {"Authorization": key}

    # Send API request, get back parsed JSON
    url = _JA_API_URL.format(urlencode(qd))
    print(url)
    res = query_json_api(url, headers=headers)

    return res


_MOBILE_FIRST_NUM = "678"


def _best_number(item: Dict) -> str:
    """ Return best phone number, given a result item from ja.is API """
    phone_num = item.get("phone")
    add_nums = item.get("additional_phones")
    if not phone_num and not add_nums:
        return None

    # First, see if the canonical phone number is a mobile phone number
    # Those should be preferred
    if phone_num and "number" in phone_num:
        if phone_num.get("mobile") == True:
            return phone_num["number"]

    # Otherwise, try the first mobile number we find in add. phone numbers
    if add_nums:
        for pn in add_nums:
            print(pn)
            if pn and "number" in pn and pn.get("mobile") == True:
                return pn["number"]

    # OK, didn't find any mobile numbers. Just return canoncial number
    return phone_num.get("number")


def _answer_phonenum4name_query(q: Query, result):
    """ Answer query of the form "hvað er síminn hjá [íslenskt mannsnafn]?" """
    res = query_ja_api(result.qkey)
    from pprint import pprint

    pprint(res)

    nþgf = NounPhrase(result.qkey).dative or result.qkey

    # Verify that we have a sane response with at least 1 result
    if not res.get("people") or not res["people"].get("items"):
        return gen_answer("Ekki tókst að fletta upp {0}.".format(nþgf))

    # Check if we have a single canonical match from API
    single = len(res["people"]["items"]) == 1
    allp = res["people"]["items"]
    first = allp[0]
    fname = first["name"]
    if not single:
        # Many found with that name, generate smart message asking for disambiguation
        one_name_only = len(result.qkey.split()) == 1
        msg = "Það fundust margir með það nafn. Prufaðu að tilgreina {0}heimilisfang".format(
            "fullt nafn og " if one_name_only else ""
        )
        # Try to generate example, e.g. "Jón Jónssón á Smáragötu"
        for i in allp:
            try:
                street_nf = i["address_nominative"].split()[0]
                street_þgf = i["address"].split()[0]
                msg = msg + " t.d. {0} {1} {2}".format(
                    fname, iceprep_for_street(street_nf), street_þgf
                )
                break
            except Exception as e:
                print("Exception " + str(e))
                continue
        return gen_answer(msg)

    # Scan API call result, try to find the best phone nuber to provide
    phone_number = _best_number(first)
    if not phone_number:
        a = "Ekki tókst að fletta upp símanúmeri hjá {0}".format(nþgf)
        return gen_answer(a)

    # Sanitize number and generate answer
    phone_number = phone_number.replace("-", "").replace(" ", "")
    answ = phone_number
    fn = NounPhrase(fname).dative or fname
    voice = "Síminn hjá {0} er {1}".format(fn, " ".join(list(phone_number)))

    q.set_context(dict(phone_number=phone_number, name=fname))
    q.set_source(_JA_SOURCE)

    return dict(answer=answ), answ, voice


def _answer_name4phonenum_query(q: Query, result):
    """ Answer query of the form "hver er með símanúmerið [númer]?"""
    pass


_QTYPE2HANDLER = {
    "Name4PhoneNum": _answer_name4phonenum_query,
    "PhoneNum4Name": _answer_phonenum4name_query,
}


def sentence(state, result):
    """ Called when sentence processing is complete """
    q: Query = state["query"]
    if "qtype" in result and "qkey" in result:
        # Successfully matched a query type
        try:
            r = _QTYPE2HANDLER[result.qtype](q, result)
            if not r:
                r = gen_answer("Ekki tókst að fletta upp viðkomandi.")
            q.set_answer(*r)
            q.set_qtype(result.qtype)
            q.set_key(result.qkey)
            # q.set_expires(datetime.utcnow() + timedelta(hours=24))
        except Exception as e:
            logging.warning("Exception while processing ja.is query: {0}".format(e))
            q.set_error("E_EXCEPTION: {0}".format(e))
    else:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
