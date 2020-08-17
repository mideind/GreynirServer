"""

    Greynir: Natural language processing for Icelandic

    Places query response module

    Copyright (C) 2020 Miðeind ehf.

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


    This module handles queries related to places (shops, businesses, etc.)
    such as opening hours, location, distance, etc. Uses Google's Places API.

"""

# TODO: "Hvert er heimilisfangið á Forréttabarnum?"
# TODO: "Á hvaða götu er Slippbarinn?"

import logging
import re
from datetime import datetime, timedelta

from geo import in_iceland, iceprep_for_street
from queries import gen_answer, query_places_api, query_place_details, icequote
from reynir import NounPhrase

_PLACES_QTYPE = "Places"


# Indicate that this module wants to handle parse trees for queries,
# as opposed to simple literal text strings
HANDLE_TREE = True

# The context-free grammar for the queries recognized by this plug-in module
GRAMMAR = """

Query →
    QPlacesQuery '?'?

QPlacesQuery →
    QPlacesOpeningHours | QPlacesIsOpen | QPlacesIsClosed | QPlacesAddress

QPlacesOpeningHours →
    "hvað" "er" "opið" "lengi" QPlacesPrepAndSubject
    | "hvað" "er" "lengi" "opið" QPlacesPrepAndSubject
    | "hverjir" "eru" "opnunartímar" QPlacesPrepAndSubject
    | "hverjir" "eru" "opnunartímar" QPlacesSubjectEf
    | "hvaða" "opnunartímar" "eru" QPlacesPrepAndSubject
    | "hversu" "lengi" "er" "opið" QPlacesPrepAndSubject
    | "hve" "lengi" "er" "opið" QPlacesPrepAndSubject
    | "klukkan" "hvað" "opnar" QPlacesPrepAndSubject
    | "klukkan" "hvað" "opnar" QPlacesSubjectNf
    | "hvenær" "lokar" QPlacesPrepAndSubject
    | "hvenær" "lokar" QPlacesSubjectNf
    | "hvenær" "opnar" QPlacesPrepAndSubject
    | "hvenær" "opnar" QPlacesSubjectNf
    | "klukkan" "hvað" "lokar" QPlacesPrepAndSubject
    | "klukkan" "hvað" "lokar" QPlacesSubjectNf
    | "hversu" "langt" "er" "í" "lokun" QPlacesPrepAndSubject
    | "hversu" "langt" "er" "í" "lokun" QPlacesSubjectEf
    | "hvað" "er" "langt" "í" "lokun" QPlacesPrepAndSubject
    | "hvað" "er" "langt" "í" "lokun" QPlacesSubjectEf
    | "hvenær" "er" "opið" QPlacesPrepAndSubject
    | "hvað" "er" QPlacesSubjectNf QPlacesOpen "lengi"

QPlacesIsOpen →
    "er" "opið" QPlacesPrepAndSubject
    | "er" QPlacesSubjectNf QPlacesOpen

QPlacesIsClosed →
    "er" "lokað" QPlacesPrepAndSubject
    | "er" QPlacesSubjectNf QPlacesClosed

QPlacesAddress →
    "hvert" "er" "heimilisfangið" QPlacesPrepAndSubject
    | "hvað" "er" "heimilisfangið" QPlacesPrepAndSubject
    | "hvert" "er" "heimilisfang" QPlacesSubjectEf
    | "hvað" "er" "heimilisfang" QPlacesSubjectEf
    | "hvar" "er" QPlacesSubjectNf "til" "húsa"
    | "hvar" "er" QPlacesSubjectNf "staðsett" 
    | "hvar" "er" QPlacesSubjectNf "staðsettur"
    | QPlacesPreposition "hvaða" "götu" "er" QPlacesSubjectNf
    | QPlacesPreposition "hvaða" "stræti" "er" QPlacesSubjectNf

QPlacesPrepAndSubject →
    QPlacesPreposition QPlacesSubjectÞgf

QPlacesSubjectÞgf →
    Nl_þgf

QPlacesSubjectNf →
    Nl_nf

QPlacesSubjectEf →
    Nl_ef

QPlacesPreposition →
    "á" | "í" | "hjá" | "við"

QPlacesOpen →
    "opið" | "opin" | "opinn"

QPlacesClosed →
    "lokað" | "lokuð" | "lokaður"

$score(+35) QPlacesQuery

"""


_PLACENAME_MAP = {}


def _fix_placename(pn):
    p = pn.capitalize()
    return _PLACENAME_MAP.get(p, p)


def QPlacesQuery(node, params, result):
    result["qtype"] = _PLACES_QTYPE


def QPlacesOpeningHours(node, params, result):
    result["qkey"] = "OpeningHours"


def QPlacesIsOpen(node, params, result):
    result["qkey"] = "IsOpen"


def QPlacesIsClosed(node, params, result):
    result["qkey"] = "IsClosed"


def QPlacesAddress(node, params, result):
    result["qkey"] = "PlaceAddress"


def QPlacesSubjectNf(node, params, result):
    result["subject_nom"] = _fix_placename(result._nominative)


QPlacesSubjectÞgf = QPlacesSubjectEf = QPlacesSubjectNf


_PLACES_API_ERRMSG = "Ekki tókst að fletta upp viðkomandi stað"


def answ_address(placename, loc, qtype):
    # Look up placename in places API
    res = query_places_api(placename, userloc=loc, fields="formatted_address")

    if res["status"] != "OK" or "candidates" not in res or not res["candidates"]:
        return gen_answer(_PLACES_API_ERRMSG)

    # Use top result
    place = res["candidates"][0]
    addr = re.sub(r", Ísland$", "", place["formatted_address"])

    answer = voice = addr
    response = dict(answer=answer)

    return response, answer, voice


def answ_openhours(placename, loc, qtype):
    # Look up placename in places API
    res = query_places_api(placename, userloc=loc)  # , fields="opening_hours,place_id")

    if res["status"] != "OK" or "candidates" not in res or not res["candidates"]:
        return gen_answer(_PLACES_API_ERRMSG)

    # Use top result
    place = res["candidates"][0]
    place_id = place["place_id"]
    is_open = place["opening_hours"]["open_now"]
    needs_disambig = len(res["candidates"]) > 1
    fmt_addr = place["formatted_address"]
    street = fmt_addr.split()[0]
    street_þgf = "{nl:þf}".format(nl=NounPhrase(street))

    # from pprint import pprint
    # pprint(res["candidates"])

    # Get place coords
    lat, lng = (None, None)
    try:
        lat = float(place["geometry"]["location"]["lat"])
        lng = float(place["geometry"]["location"]["lng"])
    except:
        return gen_answer(_PLACES_API_ERRMSG)

    # Make sure it's in Iceland
    if not in_iceland((lat, lng)):
        return gen_answer("Enginn staður með þetta heiti fannst á Íslandi")

    print(place)

    # Look up place ID in Place Details API to get more information
    res = query_place_details(place_id, fields="opening_hours,name")
    if res["status"] != "OK" or not res or "result" not in res:
        return gen_answer(_PLACES_API_ERRMSG)

    now = datetime.utcnow()
    wday = int(now.strftime("%w"))  # Sun is index 0, as req. by Google API

    try:
        name = res["result"]["name"]
        if needs_disambig:
            name = "{0} {1} {2}".format(name, iceprep_for_street(street), street_þgf)

        # Get opening hours for current weekday
        periods = res["result"]["opening_hours"]["periods"]
        p = periods[wday]
        opens = p["open"]["time"]
        closes = p["close"]["time"]

        # Format correctly
        openstr = opens[:2] + ":" + opens[2:]
        closestr = closes[:2] + ":" + opens[2:]
        p_desc = "{0} - {1}".format(openstr, closestr)
        p_voice = p_desc.replace("-", "til")
        today_desc = "Í dag er {0} opin frá {1}".format(name, p_voice)
    except:
        logging.warning("Exception generating answer for opening hours: {0}".format(e))
        return gen_answer(_PLACES_API_ERRMSG)

    # Generate answer
    if qtype == "OpeningHours":
        answer = p_desc
        voice = today_desc
    # Is X open? Is X closed?
    elif qtype == "IsOpen" or qtype == "IsClosed":
        yes_no = (
            "Já"
            if (is_open and qtype == "IsOpen" or not is_open and qtype == "IsClosed")
            else "Nei"
        )
        answer = "{0}. {1}.".format(yes_no, today_desc)
        voice = answer

    response = dict(answer=answer)

    return response, answer, voice


_HANDLER_MAP = {
    "OpeningHours": answ_openhours,
    "IsOpen": answ_openhours,
    "IsClosed": answ_openhours,
    "PlaceAddress": answ_address,
}


def sentence(state, result):
    """ Called when sentence processing is complete """
    q = state["query"]
    if "qtype" in result and "qkey" in result and "subject_nom" in result:
        # Successfully matched a query type
        subj = result["subject_nom"]
        try:
            handlerfunc = _HANDLER_MAP[result.qkey]
            res = handlerfunc(subj, q.location, result.qkey)
            if res:
                q.set_answer(*res)
                q.set_source("Google")
            else:
                errmsg = "Ekki tókst að fletta upp staðnum {0}".format(icequote(subj))
                q.set_answer(*gen_answer(errmsg))
            q.set_qtype(result.qtype)
            q.set_key(subj)
        except Exception as e:
            raise
            logging.warning("Exception answering places query: {0}".format(e))
            q.set_error("E_EXCEPTION: {0}".format(e))
            return
    else:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
