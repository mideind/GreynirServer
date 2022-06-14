"""

    Greynir: Natural language processing for Icelandic

    Copyright (C) 2022 Miðeind ehf.

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

from typing import Dict, List, Mapping, Optional, Any, Callable, cast

import re
import logging
from urllib.parse import urlencode
from datetime import datetime, timedelta

from reynir import NounPhrase
from reynir.bindb import GreynirBin

from queries import query_json_api, gen_answer, icequote, read_grammar_file
from queries.num import numbers_to_text, digits_to_text

from query import AnswerTuple, Query, QueryStateDict
from tree import Result, Node
from geo import iceprep_for_street
from util import read_api_key


# Module priority
PRIORITY = 5

# This module wants to handle parse trees for queries
HANDLE_TREE = True

# The grammar nonterminals this module wants to handle
QUERY_NONTERMINALS = {"QJaQuery"}

# The context-free grammar for the queries recognized by this plug-in module
GRAMMAR = read_grammar_file("ja")


def QJaSubject(node: Node, params: QueryStateDict, result: Result) -> None:
    result.qkey = result._nominative


def QJaPhoneNum(node: Node, params: QueryStateDict, result: Result) -> None:
    result.phone_number = result._nominative
    result.qkey = result.phone_number


def QJaName4PhoneNumQuery(node: Node, params: QueryStateDict, result: Result) -> None:
    result.qtype = "Name4PhoneNum"


def QJaPhoneNum4NameQuery(node: Node, params: QueryStateDict, result: Result) -> None:
    result.qtype = "PhoneNum4Name"


_JA_SOURCE = "ja.is"

_JA_API_URL = "https://api.ja.is/search/v6/?{0}"


def query_ja_api(q: str) -> Optional[Dict[str, Any]]:
    """Send query to ja.is API"""
    key = read_api_key("JaServerKey")
    if not key:
        # No key, can't query the API
        logging.warning("No API key for ja.is")
        return None

    qdict = {"q": q}
    headers = {"Authorization": key}

    # Send API request, get back parsed JSON
    url = _JA_API_URL.format(urlencode(qdict))
    return cast(Optional[Dict[str, Any]], query_json_api(url, headers=headers))


def _best_phone_number(item: Dict[str, Any]) -> Optional[str]:
    """Return best phone number, given a result item from ja.is API"""
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


def phonenums4name(name: str) -> Optional[List[Dict[str, Any]]]:
    """Receives name string in nominative case. Returns list of candidates found."""
    res = query_ja_api(name)
    # Verify that we have a sane response with at least 1 result
    if not res or not res.get("people") or not res["people"].get("items"):
        return None
    return res["people"]["items"]


def _answer_phonenum4name_query(q: Query, result: Result) -> AnswerTuple:
    """Answer query of the form "hvað er síminn hjá [íslenskt mannsnafn]?" """
    nþgf = NounPhrase(result.qkey).dative or result.qkey

    res = phonenums4name(result.qkey)
    if not res:
        return gen_answer("Ekki tókst að fletta upp {0}.".format(nþgf))

    # Check if we have a single canonical match from API
    allp = res
    single = len(allp) == 1
    first = allp[0]
    fname = first["name"]
    if not single:
        # Many found with that name, generate smart message asking for disambiguation
        name_components = result.qkey.split()
        one_name_only = len(name_components) == 1
        with GreynirBin.get_db() as bdb:
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

    # Scan API call result, try to find the best phone number
    phone_number = _best_phone_number(first)
    if not phone_number:
        return gen_answer("Ég finn ekki símanúmerið hjá {0}".format(nþgf))

    # Sanitize number and generate answer
    phone_number = phone_number.replace("-", "").replace(" ", "")
    answ = phone_number
    fn = NounPhrase(fname).dative or fname
    voice = f"Síminn hjá {fn} er {digits_to_text(phone_number)}"

    q.set_context(dict(phone_number=phone_number, name=fname))
    q.set_source(_JA_SOURCE)

    return dict(answer=answ), answ, voice


def _answer_name4phonenum_query(q: Query, result: Result) -> AnswerTuple:
    """Answer query of the form "hver er með símanúmerið [númer]?"""
    num = result.phone_number
    clean_num = re.sub(r"[^0-9]", "", num).strip()

    # This answer can be safely cached
    q.set_expires(datetime.utcnow() + timedelta(hours=24))

    if not clean_num or len(clean_num) < 3:
        answer = gen_answer(f"{num} er ekki gilt símanúmer")
        return (answer[0], answer[1], digits_to_text(answer[2]))

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
    voice = numbers_to_text(answ)

    # Set phone number, name and address as context
    q.set_context(dict(phone_number=clean_num, name=name, address=full_addr))

    # Beautify query by showing clean phone number
    bq = q.beautified_query.replace(num, clean_num)
    q.set_beautified_query(bq)

    return dict(answer=answ), answ, voice


_QTYPE2HANDLER: Mapping[str, Callable[[Query, Result], AnswerTuple]] = {
    "Name4PhoneNum": _answer_name4phonenum_query,
    "PhoneNum4Name": _answer_phonenum4name_query,
}


def sentence(state: QueryStateDict, result: Result) -> None:
    """Called when sentence processing is complete"""
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
