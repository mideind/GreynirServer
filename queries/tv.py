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


    This module handles queries related to television schedules.
    Only handles RÚV (for now).

"""

import logging
import re
from datetime import datetime, timedelta
from queries import query_json_api, gen_answer


_TELEVISION_QTYPE = "Television"


_CURR_PROGRAM_QUERIES = (
    "hvað er í sjónvarpinu",
    "hvað er í sjónvarpinu núna",
    "hvað er í sjónvarpinu eins og stendur",
    "hvað er í gangi á RÚV",
    "hvað er í gangi á RÚV núna",
    "hvað er í gangi á RÚV eins og stendur",
)


def _clean_desc(d):
    """ Return first sentence in multi-sentence string. """
    return d.replace("?", ".").split(".")[0]


_RUV_SCHEDULE_API_ENDPOINT = "https://apis.is/tv/ruv/"
_API_ERRMSG = "Ekki tókst að sækja sjónvarpsdagskrá."
_CACHED_SCHEDULE = None
_LAST_FETCHED = None


def _query_tv_schedule_api():
    """ Fetch current television schedule from API, or return cached copy. """
    global _CACHED_SCHEDULE
    global _LAST_FETCHED
    if (
        not _CACHED_SCHEDULE
        or not _LAST_FETCHED
        or _LAST_FETCHED.date() != datetime.today().date()
    ):
        _CACHED_SCHEDULE = None
        sched = query_json_api(_RUV_SCHEDULE_API_ENDPOINT)
        if sched and "results" in sched and len(sched["results"]):
            _LAST_FETCHED = datetime.now()
            _CACHED_SCHEDULE = sched["results"]
    return _CACHED_SCHEDULE


def _curr_prog(sched):
    """ Return current tv program, given a TV schedule 
        i.e. a list of programs in chronological sequence. """
    for p1, p2 in zip(sched[:-1], sched[1:]):
        (t1, t2) = (
            datetime.strptime(p1["startTime"], "%Y-%m-%d %H:%M:%S"),
            datetime.strptime(p2["startTime"], "%Y-%m-%d %H:%M:%S"),
        )
        now = datetime.now()
        if now >= t1 and now < t2:
            return p1


def _gen_curr_program_answer(q):
    """ Generate answer to query about current TV program(s). """
    sched = _query_tv_schedule_api()
    if not sched:
        return gen_answer(_API_ERRMSG)

    prog = _curr_prog(sched)
    if not prog:
        return gen_answer("Það er ekkert í Ríkissjónvarpinu eins og stendur.")

    answ = "Á RÚV er þátturinn {0}. {1}.".format(
        prog["title"], _clean_desc(prog["description"])
    )
    return gen_answer(answ)


# Map hashable query category set to corresponding handler function
_Q2HANDLER = {_CURR_PROGRAM_QUERIES: _gen_curr_program_answer}


def handle_plain_text(q):
    """ Handle a plain text query about tv schedules. """
    ql = q.query_lower.rstrip("?")
    for qset, handler in _Q2HANDLER.items():
        if ql not in qset:
            continue

        try:
            r = handler(q)
            if r:
                q.set_answer(*r)
                q.set_qtype(_TELEVISION_QTYPE)
                return True
        except Exception as e:
            logging.warning(
                "Exception while processing TV schedule query: {0}".format(e)
            )
            q.set_error("E_EXCEPTION: {0}".format(e))

    return False
