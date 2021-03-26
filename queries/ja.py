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
# TODO: Smarter disambiguation interaction

from typing import Dict, Optional, Any, Callable

import re
import logging
from urllib.parse import urlencode
from datetime import datetime, timedelta

from reynir import NounPhrase
from reynir.bindb import BIN_Db

from . import query_json_api, gen_answer, numbers_to_neutral, icequote
from query import Query, ContextDict
from tree import ResultType
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
    | "flettu" "upp" QJaPhoneNum QJaInPhonebook
    | "hver" "er" "í" "síma" QJaPhoneNum

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

$tag(keep) QJaPhoneNum
$tag(keep) QJaSubject

"""


def QJaSubject(node, params, result):
    result.qkey = result._nominative


def QJaPhoneNum(node, params, result):
    result.phone_number = result._nominative
    result.qkey = result.phone_number


def QJaName4PhoneNumQuery(node, params, result):
    result.qtype = "Name4PhoneNum"


def QJaPhoneNum4NameQuery(node, params, result):
    result.qtype = "PhoneNum4Name"


_JA_SOURCE = "ja.is"

_JA_API_URL = "https://api.ja.is/search/v6/?{0}"


def query_ja_api(q: str) -> Optional[Dict[str, Any]]:
    """ Send query to ja.is API """
    key = read_api_key("JaServerKey")
    if not key:
        # No key, can't query the API
        logging.warning("No API key for ja.is")
        return None

    qdict = {"q": q}
    headers = {"Authorization": key}

    # Send API request, get back parsed JSON
    url = _JA_API_URL.format(urlencode(qdict))
    res = query_json_api(url, headers=headers)

    return res


def _best_number(item: Dict[str, Any]) -> Optional[str]:
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
            if pn and "number" in pn and pn.get("mobile") == True:
                return pn["number"]

    # OK, didn't find any mobile numbers. Just return canonical number
    return phone_num.get("number") if phone_num else None


def _answer_phonenum4name_query(q: Query, result: ResultType):
    """ Answer query of the form "hvað er síminn hjá [íslenskt mannsnafn]?" """
    res = query_ja_api(result.qkey)

    nþgf = NounPhrase(result.qkey).dative or result.qkey

    # Verify that we have a sane response with at least 1 result
    if not res or not res.get("people") or not res["people"].get("items"):
        return gen_answer("Ekki tókst að fletta upp {0}.".format(nþgf))

    # Check if we have a single canonical match from API
    allp = res["people"]["items"]
    single = len(allp) == 1
    first = allp[0]
    fname = first["name"]
    if not single:
        # Many found with that name, generate smart message asking for disambiguation
        name_components = result.qkey.split()
        one_name_only = len(name_components) == 1
        with BIN_Db.get_db() as bdb:
            fn = name_components[0].title()
            gender = bdb.lookup_name_gender(fn)
        msg = (
            "Það fundust {0} með það nafn. Prófaðu að tilgreina {1}heimilisfang".format(
                "margar" if gender == "kvk" else "margir",
                "fullt nafn og " if one_name_only else "",
            )
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
            except (KeyError, ValueError) as e:
                logging.warning("Exception: " + str(e))
                continue
        return gen_answer(msg)

    # Scan API call result, try to find the best phone nuber to provide
    phone_number = _best_number(first)
    if not phone_number:
        return gen_answer("Ég finn ekki símanúmerið hjá {0}".format(nþgf))

    # Sanitize number and generate answer
    phone_number = phone_number.replace("-", "").replace(" ", "")
    answ = phone_number
    fn = NounPhrase(fname).dative or fname
    voice = "Síminn hjá {0} er {1}".format(fn, " ".join(list(phone_number)))

    q.set_context(dict(phone_number=phone_number, name=fname))
    q.set_source(_JA_SOURCE)

    return dict(answer=answ), answ, voice


def _answer_name4phonenum_query(q: Query, result: ResultType):
    """ Answer query of the form "hver er með símanúmerið [númer]?"""
    num = result.phone_number
    clean_num = re.sub(r"[^0-9]", "", num).strip()

    # This answer can be safely cached
    q.set_expires(datetime.utcnow() + timedelta(hours=24))

    if not clean_num or len(clean_num) < 3:
        return gen_answer("{0} er ekki gilt símanúmer")

    res = query_ja_api(clean_num)

    # Make sure API response is sane
    if not res or "people" not in res or "businesses" not in res:
        return gen_answer("Ég fann ekki símanúmerið.")

    persons = res["people"]["items"]
    businesses = res["businesses"]["items"]

    # It's either a person or a business
    items = persons or businesses
    if len(items) == 0:
        return gen_answer("Ég fann engan með það númer í símaskránni.")

    p = items[0]  # Always use first result
    # TODO: Make sure the match is in phone number field!

    name = p["name"]
    occup = p.get("occupation", "")
    addr = p.get("address", "")
    pstation = p.get("postal_station", "")  # e.g. "101, Reykjavík"

    full_addr = "{0}{1}".format(addr, ", " + pstation if pstation else "")

    # E.g. "Sveinbjörn Þórðarson, fræðimaður, Öldugötu 4, 101 Reykjavík"
    answ = "{0}{1}{2}".format(
        name, " " + occup if occup else "", ", " + full_addr if full_addr else ""
    ).strip()
    voice = numbers_to_neutral(answ)

    # Set phone number, name and address as context
    q.set_context(dict(phone_number=clean_num, name=name, address=full_addr))

    # Beautify query by showing clean phone number
    bq = q.beautified_query.replace(num, clean_num)
    q.set_beautified_query(bq)

    return dict(answer=answ), answ, voice


_QTYPE2HANDLER: Dict[str, Callable] = {
    "Name4PhoneNum": _answer_name4phonenum_query,
    "PhoneNum4Name": _answer_phonenum4name_query,
}


def sentence(state: ContextDict, result: ResultType):
    """ Called when sentence processing is complete """
    q: Query = state["query"]
    if "qtype" in result and "qkey" in result:
        # Successfully matched a query type
        try:
            r = _QTYPE2HANDLER[result.qtype](q, result)
            if not r:
                r = gen_answer("Ég fann ekki {0}.".format(icequote(result.qkey)))
            q.set_answer(*r)
            q.set_qtype(result.qtype)
            q.set_key(result.qkey)
        except Exception as e:
            logging.warning("Exception while processing ja.is query: {0}".format(e))
            q.set_error("E_EXCEPTION: {0}".format(e))
    else:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
