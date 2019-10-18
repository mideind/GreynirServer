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

# TODO: Special days should be mentioned by name, not date, in voice answers
# TODO: Fix pronunciation of ordinal day of month (i.e. "29di" vs "29da")
# TODO: "How many weeks between April 3 and June 16?"
# TODO: Find out the date and day of the week of holidays, e.g. "Hvenær eru páskar?"
# TODO: Restore timezone-awareness

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
    QDate

QDate →
    QDateQuery '?'?

QDateQuery →
    QDateCurrent | QDateHowLongUntil | QDateHowLongSince

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
    # | "hvað" "eru" "margar" "vikur" "í" QDateItem
    # | "hvað" "eru" "margir" "mánuðir" "í" QDateItem

QDateHowLongSince →
    "hvað" "er" "langt" "síðan" QDateItem
    | "hvað" "er" "langt" "um"? "liðið" "frá" QDateItem
    | "hvað" "er" "langur" "tími" "liðinn" "frá" QDateItem
    | "hvað" "eru" "margir" "dagar" "liðnir" "frá" QDateItem
    | "hvað" "eru" "margir" "dagar" "liðnir" "síðan" QDateItem
    | "hvað" "eru" "margir" "mánuðir" "liðnir" "frá" QDateItem
    | "hvað" "eru" "margir" "mánuðir" "liðnir" "síðan" QDateItem
    | "hvað" "eru" "margar" "vikur" "liðnar" "frá" QDateItem
    | "hvað" "eru" "margar" "vikur" "liðnar" "síðan" QDateItem

QDateItem →
    QDateAbsOrRel | QDateSpecialDay

QDateAbsOrRel →
    FöstDagsetning | AfstæðDagsetning

QDateSpecialDay →
    QDateChristmas 
    | QDateChristmasDay 
    | QDateNewYearsEve
    | QDateNewYearsDay
    | QDateWorkersDay
    | QDateEaster

# TODO: Do this more intelligently
QDateChristmas →
    "jól" | "jólum" | "jóla" 

QDateChristmasDay →
    "jóladagur" | "jóladag" | "jóladegi" | "jóladags"

QDateNewYearsEve →
    "gamlárskvöld" | "gamlárskvöldi" | "gamlárskvölds"

QDateNewYearsDay →
    "nýársdagur" | "nýársdag" | "nýársdegi" | "nýársdags"

# # Inject a healthy bit of socialism ;-)
QDateWorkersDay →
    "baráttudagur" "verkalýðsins" | "baráttudag" "verkalýðsins" | "baráttudegi" "verkalýðsins"

QDateEaster →
    "páskar" | "páska" | "páskum" | "páska" | "páskana" | "páskunum" | "páskanna"

$score(+35) QDate

"""


def QDateQuery(node, params, result):
    result.qtype = _DATE_QTYPE


def QDateCurrent(node, params, result):
    result["now"] = True


def QDateHowLongUntil(node, params, result):
    result["until"] = True


def QDateHowLongSince(node, params, result):
    result["since"] = True


def QDateAbsOrRel(node, params, result):
    t = result.find_descendant(t_base="dagsafs")
    if not t:
        t = result.find_descendant(t_base="dagsföst")
    if t:
        d = terminal_date(t)
        if d:
            result["target"] = d
    else:
        print("No dagsafs in {0}".format(str(t)))


def QDateChristmas(node, params, result):
    result["target"] = datetime(
        year=datetime.today().year, month=12, day=24, hour=0, minute=0, second=0
    )


def QDateChristmasDay(node, params, result):
    result["target"] = datetime(
        year=datetime.today().year, month=12, day=25, hour=0, minute=0, second=0
    )


def QDateNewYearsEve(node, params, result):
    result["target"] = datetime(
        year=datetime.today().year, month=12, day=31, hour=0, minute=0, second=0
    )


def QDateNewYearsDay(node, params, result):
    result["target"] = datetime(
        year=datetime.today().year + 1, month=1, day=1, hour=0, minute=0, second=0
    )


def QDateWorkersDay(node, params, result):
    result["target"] = datetime(
        year=datetime.today().year + 1, month=5, day=1, hour=0, minute=0, second=0
    )

def QDateEaster(node, params, result):
    now = datetime.now()
    e = calc_easter(now.year)
    if e < now:
        e = calc_easter(now.year + 1)
    result["target"] = e


def calc_easter(year):
    """ An implementation of Butcher's Algorithm for determining the date of Easter 
        for the Western church. Works for any date in the Gregorian calendar (1583 
        and onward). Returns a datetime object. 
        From http://code.activestate.com/recipes/576517-calculate-easter-western-given-a-year/ """
    a = year % 19
    b = year // 100
    c = year % 100
    d = (19 * a + b - b // 4 - ((b - (b + 8) // 25 + 1) // 3) + 15) % 30
    e = (32 + 2 * (b % 4) + 2 * (c // 4) - d - (c % 4)) % 7
    f = d + e - 7 * ((a + 11 * d + 22 * e) // 451) + 114
    month = f // 31
    day = f % 31 + 1    
    return datetime(year=year, month=month, day=day, hour=0, minute=0, second=0)


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
    return cnt


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


def howlong_desc_answ(target):
    now = datetime.now()
    days = date_diff(now, target, unit="days")

    # Diff. strings for singular vs. plural
    sing = str(days).endswith("1")
    verb = "er" if sing else "eru"
    days_desc = "dagur" if sing else "dagar"

    # Format date
    fmt = "%-d. %B" if now.year == target.year else "%-d. %B %Y"
    tfmt = target.strftime(fmt)

    # Date asked about is current date
    if days == 0:
        return gen_answer("Það er {0} í dag.".format(tfmt))
    elif days < 0:
        # It's in the past
        days = abs(days)
        passed = "liðinn" if sing else "liðnir"
        voice = "Það {0} {1} {2} {3} frá {4}.".format(
            verb, days, days_desc, passed, tfmt
        )
        answer = "{0} {1}".format(days, days_desc)
    else:
        # It's in the future
        voice = "Það {0} {1} {2} þar til {3} gengur í garð.".format(
            verb, days, days_desc, tfmt
        )
        answer = "{0} {1}".format(days, days_desc)

    response = dict(answer=answer)

    return (response, answer, voice)


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
            now = datetime.now()  # datetime.now(timezone(tz))
            qkey = None

            # Asking about current date
            if "now" in result:
                date_str = now.strftime("%A %-d. %B %Y")
                voice = "Í dag er {0}".format(date_str)
                answer = date_str.capitalize()
                response = dict(answer=answer)
                qkey = "CurrentDate"
            # Asking about period until/since a given date
            elif ("until" in result or "since" in result) and "target" in result:
                target = result.target
                # target.replace(tzinfo=timezone(tz))

                # Find the number of days until target date
                (response, answer, voice) = howlong_desc_answ(target)
                qkey = "FutureDate" if "until" in result else "SinceDate"
            else:
                # Shouldn't be here
                raise Exception("Unable to handle date query")

            q.set_key(qkey)
            q.set_answer(response, answer, voice)
            q.set_qtype(_DATE_QTYPE)

    except Exception as e:
        logging.warning("Exception while processing date query: {0}".format(e))
        q.set_error("E_EXCEPTION: {0}".format(e))
