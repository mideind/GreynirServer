"""

    Greynir: Natural language processing for Icelandic

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

# TODO: Support TV schedule queries for other stations than RÚV
# TODO: Support radio schedules

import logging
import re
import random
from datetime import datetime, timedelta

from queries import query_json_api, gen_answer


_TELEVISION_QTYPE = "Television"


TOPIC_LEMMAS = ["sjónvarp", "sjónvarpsdagskrá", "rúv", "ríkissjónvarp"]


def help_text(lemma):
    """ Help text to return when query.py is unable to parse a query but
        one of the above lemmas is found in it """
    return "Ég get svarað ef þú spyrð til dæmis: {0}?".format(
        random.choice(
            (
                "Hvað er í sjónvarpinu",
                "Hvað er á RÚV í augnablikinu",
                "Hvaða efni er verið að sýna í sjónvarpinu",
            )
        )
    )


# This module wants to handle parse trees for queries
HANDLE_TREE = True

# The context-free grammar for the queries recognized by this plug-in module
GRAMMAR = """

Query →
    QTelevision

QTelevision → QTelevisionQuery '?'?

QTelevisionQuery →
    QTVWhatIsNom QTVEiginlega? QTVGoingOn? QTVOnTV QTVNow?
    | QTVWhatIsDative QTVEiginlega? QTVBeingShown QTVOnTV QTVNow?
    | "dagskrá" QTVBeingShown? QTVOnTV? 
    | "dagskrá" QTVGoingOn? QTVOnTV? 

QTVWhatIsNom →
    "hvað" "er" | "hvaða" "þáttur" "er" | "hvaða" "dagskrárliður" "er" | "hvaða" "efni" "er"

QTVWhatIsDative →
    "hvað" "er" | "hvaða" "þátt" "er" | "hvaða" "dagskrárlið" "er" | "hvaða" "efni" "er"

QTVOnTV →
    "í" "sjónvarpinu" | "á" "rúv" | "í" "ríkissjónvarpinu" | "á" "stöð" "eitt" | "rúv"

QTVNow →
    "nákvæmlega"? "núna" | "eins" "og" "stendur" | "í" "augnablikinu"

QTVGoingOn →
    "í" "gangi"

QTVBeingShown →
    "verið" "að" "sýna" 

QTVEiginlega →
    "eiginlega"

$score(+35) QTelevision

"""


def QTelevisionQuery(node, params, result):
    # Set the query type
    result.qtype = _TELEVISION_QTYPE
    result.qkey = "Dagskrárliður"


def _clean_desc(d):
    """ Return first sentence in multi-sentence string. """
    return d.replace("Dr.", "Doktor").replace("?", ".").split(".")[0]


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
            _LAST_FETCHED = datetime.utcnow()
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
        now = datetime.utcnow()
        if now >= t1 and now < t2:
            return p1


def _gen_curr_program_answer(q):
    """ Generate answer to query about current TV program(s). """
    sched = _query_tv_schedule_api()
    if not sched:
        return gen_answer(_API_ERRMSG)

    prog = _curr_prog(sched)
    if not prog:
        return gen_answer("Það er engin dagskrá á RÚV núna.")

    ep = "" if "fréttir" in prog["title"].lower() else "þáttinn "
    answ = "RÚV er að sýna {0}{1}. {2}.".format(
        ep, prog["title"], _clean_desc(prog["description"])
    )
    return gen_answer(answ)


def sentence(state, result):
    """ Called when sentence processing is complete """
    q = state["query"]
    if "qtype" in result:
        # Successfully matched a query type
        q.set_qtype(result.qtype)
        q.set_key(result.qkey)

        try:
            r = _gen_curr_program_answer(q)
            q.set_answer(*r)
            q.set_beautified_query(q._beautified_query.replace("rúv", "RÚV"))
            # TODO: Set intelligent expiry time
            q.set_expires(datetime.utcnow() + timedelta(minutes=3))
        except Exception as e:
            logging.warning(
                "Exception while processing TV schedule query: {0}".format(e)
            )
            q.set_error("E_EXCEPTION: {0}".format(e))

    else:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
