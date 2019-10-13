"""

    Reynir: Natural language processing for Icelandic

    Date query response module

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


    This module is an example of a plug-in query response module
    for the Greynir query subsystem. It handles plain text queries, i.e.
    ones that do not require parsing the query text. For this purpose
    it only needs to implement the handle_plain_text() function, as
    shown below.


    This particular module handles queries related to dates.

"""

# TODO: Fix pronunciation of ordinal day of month (i.e. "29di" vs "29da")
# TODO: "How many weeks between April 3 and June 16?"
# TODO: Find out the date and day of the week of holidays, e.g. "When is Easter?"
#       or "When is Labour Day?"
# TODO: "Hvað er langt í jólin?" "Hvað er langt til jóla" "Hvað er langt í áramótin"

import json
import logging
from datetime import datetime, date
from pytz import timezone

from queries import timezone4loc, gen_answer
from settings import changedlocale


_DATE_QTYPE = "Date"


# Indicate that this module wants to handle parse trees for queries,
# as opposed to simple literal text strings
HANDLE_TREE = True

# The context-free grammar for the queries recognized by this plug-in module
GRAMMAR = """

Query →
    QDateQuery '?'?

QDateQuery →
    QDateCurrent | QDateHowLongUntil

QDateCurrent →
    "hvað" "er" "dagsetningin" QDateNow?
    | "hver" "er" "dagsetningin" QDateNow?
    | "hvaða" "dagsetning" "er" QDateNow?
    | "hvaða" "dagur" "er" QDateNow?
    | "hvaða" "mánaðardagur" "er" QDateNow?
    | "hvaða" "vikudagur" "er" QDateNow?
    | "hver" "er" "dagurinn" QDateNow?
    | "hver" "er" "mánaðardagurinn" QDateNow?
    | "hver" "er" "vikudagurinn" QDateNow?

QDateNow →
    "í" "dag" | "núna"

QDateHowLongUntil →
    "hvað" "er" "langt" "í" QDateItem
    | "hvað" "er" "langt" "fram" "að" QDateItem
    | "hvað" "er" "langt" "til" QDateItem
    | "hversu" "langt" "er" "í" QDateItem
    | "hversu" "langt" "er" "til" QDateItem
    | "hvað" "eru" "margir" "dagar" "í" QDateItem
    | "hvað" "eru" "margir" "dagar" "til" QDateItem
    | "hvað" "eru" "margar" "vikur" "í" QDateItem
    | "hvað" "eru" "margir" "mánuðir" "í" QDateItem

QDateItem →
    FöstDagsetning | AfstæðDagsetning

# QDateChristmas →
#     "jól"

# QDateChristmas →
#     "jóladagur"

# QDateNewYearsEve →
#     "gamlárskvöld"

# QDateNewYearsDay →
#     "nýársdagur"

# # Inject a healthy bit of socialism ;-)
# QDateWorkersDay →
#     "baráttudagur" "verkalýðsins"

$score(+35) QDateQuery

"""


def QDateQuery(node, params, result):
    result.qtype = _DATE_QTYPE


def QDateCurrent(node, params, result):
    result["now"] = True


def QDateHowLongUntil(node, params, result):
    result["howlong"] = True


def QDateItem(node, params, result):
    t = result.find_descendant(t_base="dagsafs")
    if t:
        d = terminal_date(t)
        if d:
            result["target"] = d


def terminal_date(t):
    """ Extract array of date values from terminal token's auxiliary info,
        which is attached as a json-encoded array. Return datetime object. """
    if t and t._node.aux:
        aux = json.loads(t._node.aux)
        if not isinstance(aux, list) or len(aux) < 3:
            raise Exception("Malformed token aux info")

        # Unpack date array
        (y, m, d) = aux
        if not y:
            now = datetime.now()
            y = datetime.now().year
            # Bump year if month/day in the past
            if m < now.month or (m == now.month and d < now.day):
                y += 1

        return datetime(year=y, month=m, day=d, hour=0, minute=0, second=0)


def date_diff(d1, d2, unit="days"):
    delta = d2 - d1
    cnt = getattr(delta, unit)
    return abs(cnt)


# def _christmas():
#     return datetime(
#         year=datetime.today().year, month=12, day=24, hour=0, minute=0, second=0
#     )


# _CHRISTMAS_QUERIES = {
#     "hvað er langt í jólin": _christmas,
#     "hvað er langt í jól": _christmas,
#     "hvað er langt til jóla": _christmas,
#     "hvað er langt til jólanna": _christmas,
#     "hvað eru margir dagar til jóla": _christmas,
#     "hvað eru margir dagar til jólanna": _christmas,
#     "hversu langt er í jólin": _christmas,
#     "hve langt er í jólin": _christmas,
# }

# _WORKING_WEEK_QUERIES = {
#     "hvað er mikið eftir af vinnuvikunni",
#     "hvað er langt í helgina",
#     "hvað er langt í helgi",
#     "hvað á ég mikið eftir af vinnuvikunni",
# }


def sentence(state, result):
    """ Called when sentence processing is complete """
    q = state["query"]
    if "qtype" not in result:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
        return

    # Successfully matched a query type
    try:
        with changedlocale(category="LC_TIME"):
            # Get timezone and date
            tz = timezone4loc(q.location, fallback="IS")
            now = datetime.now(timezone(tz))
            qkey = None

            # Asking about current date
            if "now" in result:
                date_str = now.strftime("%A %-d. %B %Y")
                voice = "Í dag er {0}".format(date_str)
                answer = date_str.capitalize()
                response = dict(answer=answer)
                qkey = "CurrentDate"
            # Asking about length of period until a given date
            elif "howlong" and "target" in result:
                target = result.target
                target.replace(tzinfo=timezone(tz))
                days = date_diff(now, target, unit="hours")
                # Date asked about is current date
                if days == 0:
                    (response, answer, voice) = gen_answer(
                        "Það er {0} í dag.".format(target.strftime("%-d. %B"))
                    )
                else:
                    fmt = "%-d. %B" if now.year == target.year else "%-d. %B %Y"
                    tfmt = target.strftime(fmt)
                    voice = "Það eru {0} dagar þar til {1} gengur í garð.".format(
                        days, tfmt
                    )
                    answer = "{0} dagar".format(days)
                    response = dict(answer=answer)
                qkey = "FutureDate"
            else:
                # Shouldn't be here
                raise Exception("Unable to handle date query")

            q.set_key(qkey)
            q.set_answer(response, answer, voice)
            q.set_qtype(_DATE_QTYPE)

    except Exception as e:
        logging.warning("Exception while processing date query: {0}".format(e))
        q.set_error("E_EXCEPTION: {0}".format(e))
