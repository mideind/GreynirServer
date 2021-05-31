"""

    Greynir: Natural language processing for Icelandic

    TV & radio schedule query response module

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
    along with this program. If not, see http://www.gnu.org/licenses/.


    This module handles queries related to television and radio schedules.
    Only handles RÚV television (for now).

"""

# TODO: Support TV schedule queries for other stations than RÚV
# TODO: Fix formatting issues w. trailing spaces, periods at the end of answer str
# TODO: "Hvað er á dagskrá á rúv annað kvöld?"
# TODO: "Hvaða þættir eru á rúv?"

from typing import List, Dict, Optional, Tuple, Any

import logging
import random
from datetime import datetime, timedelta

from query import AnswerTuple, Query, QueryStateDict
from queries import query_json_api, gen_answer
from tree import Result


_SCHEDULES_QTYPE = "Schedule"

_TELEVISION_QKEY = "TelevisionSchedule"
_TELEVISION_EVENING_QKEY = "TelevisionEvening"
_RADIO_QKEY = "RadioSchedule"

TOPIC_LEMMAS = [
    "sjónvarp",
    "sjónvarpsdagskrá",
    "útvarpsdagskrá",
    "dagskrá",
    "rúv",
    "ríkissjónvarp",
    "útvarp",
    "ríkisútvarp",
    "rás",
    "þáttur",
]


def help_text(lemma: str) -> str:
    """Help text to return when query.py is unable to parse a query but
    one of the above lemmas is found in it"""
    return "Ég get svarað ef þú spyrð til dæmis: {0}?".format(
        random.choice(
            (
                "Hvað er í sjónvarpinu í kvöld",
                "Hvað er á RÚV í augnablikinu",
                "Hvaða efni er verið að sýna í sjónvarpinu",
                # "Hvaða efni er verið að spila í útvarpinu",
                # "Hvað er í útvarpinu",
                # "Hvað er á Rás 1 í augnablikinu",
            )
        )
    )


# This module wants to handle parse trees for queries
HANDLE_TREE = True

# The grammar nonterminals this module wants to handle
QUERY_NONTERMINALS = {"QSchedule"}

# The context-free grammar for the queries recognized by this plug-in module
# Uses "QSch" as prefix for grammar namespace
GRAMMAR = """

Query →
    QSchedule

QSchedule →
    QScheduleQuery '?'?

QScheduleQuery →
    QScheduleTV | QScheduleRadio

QScheduleTV →
    QSchTelevisionQuery
    | QSchTelevisionEveningQuery

QSchTelevisionQuery →
    QSchWhatIsNom QSchEiginlega? QSchGoingOn? QSchOnTV QSchNow?
    | QSchWhatIsDative QSchEiginlega? QSchBeingShown QSchOnTV QSchNow?
    | "dagskrá" QSchBeingShown? QSchOnTV? QSchNow?
    | "dagskrá" QSchGoingOn? QSchOnTV? QSchNow?
    | QSchWhatIsNom "á" "dagskrá" QSchOnTV QSchNow?

QSchTelevisionEveningQuery →
   "hvað" "er" QSchEiginlega? QSchOnSchedule? QSchOnTV QSchThisEvening
   | "hvernig" "er" QSchEiginlega? QSchTheSchedule QSchOnTV? QSchThisEvening
   | "hver" "er" QSchEiginlega? QSchTheSchedule QSchOnTV? QSchThisEvening

QScheduleRadio →
    QSchRadioStationNowQuery

QSchRadioStationNowQuery →
    QSchWhatIsNom QSchEiginlega? QSchGoingOn? QSchOnRadioStation QSchNow?
    | QSchWhatIsNom QSchEiginlega? QSchOnSchedule? QSchOnRadioStation QSchNow?
    | QSchWhatIsDative QSchEiginlega? "verið" "að" "spila" QSchOnRadioStation QSchNow?

QSchWhatIsNom →
    "hvað" "er" | "hvaða" "þáttur" "er" | "hvaða" "dagskrárliður" "er" | "hvaða" "efni" "er"

QSchWhatIsDative →
    "hvað" "er" | "hvaða" "þátt" "er" | "hvaða" "dagskrárlið" "er" | "hvaða" "efni" "er"

QSchOnTV →
    QSchOnRUV # | QSchOnStod2

QSchOnRUV →
    "í" "sjónvarpinu" | "á" "rúv" | "í" "ríkissjónvarpinu"
    | "á" "stöð" "eitt" | "hjá"? "rúv" | "sjónvarpsins" | "sjónvarps"

QSchOnStod2 →
    "á" "stöð" "tvö" | "á" "stöð" "2"

# Supported radio stations
QSchOnRadioStation →
   QSchOnRas1 | QSchOnRas2

QSchOnRas1 →
    "á" "rás" "eitt"
    | "á" "rás" "1"
    | "í" "útvarpinu"
    | "í" "ríkisútvarpinu"
    | "á" "ríkisútvarpinu"

QSchOnRas2 →
    "á" "rás" "tvö" | "á" "rás" "2"

QSchNow →
    "nákvæmlega"? "núna" | "eins" "og" "stendur" | "í" "augnablikinu"

QSchGoingOn →
    "í" "gangi"

QSchBeingShown →
    "verið" "að" "sýna"

QSchEiginlega →
    "eiginlega"

QSchOnSchedule →
    "á" "dagskrá"
    | "í" "dagskrá"
    | "á" "dagskránni"
    | "í" "boði"
    | "boðið" "upp" "á"
    | "verið" "að" "sýna"

QSchTheSchedule →
    "dagskráin" | "sjónvarpsdagskráin"

QSchThisEvening →
    "núna"? "í_kvöld"

$score(+55) QSchedule

"""


def QSchOnRas1(node, params, result):
    result["radio_channel"] = "ras1"
    result["radio_channel_pretty"] = "Rás 1"


def QSchOnRas2(node, params, result):
    result["radio_channel"] = "ras2"
    result["radio_channel_pretty"] = "Rás 2"


def QSchTelevisionQuery(node, params, result):
    result.qtype = _SCHEDULES_QTYPE
    result.qkey = _TELEVISION_QKEY


def QSchTelevisionEveningQuery(node, params, result):
    result.qtype = _SCHEDULES_QTYPE
    result.qkey = _TELEVISION_EVENING_QKEY


def QSchRadioStationNowQuery(node, params, result):
    result.qtype = _SCHEDULES_QTYPE
    result.qkey = _RADIO_QKEY


def _clean_desc(d: str) -> str:
    """Return first sentence in multi-sentence string."""
    return d.replace("Dr.", "Doktor").replace("?", ".").split(".")[0]


_RUV_TV_SCHEDULE_API_ENDPOINT = "https://apis.is/tv/ruv/"
_TV_API_ERRMSG = "Ekki tókst að sækja sjónvarpsdagskrá."
_CACHED_TV_SCHEDULE: Optional[List] = None
_TV_LAST_FETCHED: Optional[datetime] = None


def _query_tv_schedule_api() -> Optional[List]:
    """Fetch current television schedule from API, or return cached copy."""
    global _CACHED_TV_SCHEDULE
    global _TV_LAST_FETCHED
    if (
        not _CACHED_TV_SCHEDULE
        or not _TV_LAST_FETCHED
        or _TV_LAST_FETCHED.date() != datetime.today().date()
    ):
        # Not cached. Fetch data.
        _CACHED_TV_SCHEDULE = None
        sched = query_json_api(_RUV_TV_SCHEDULE_API_ENDPOINT)
        if sched and "results" in sched and len(sched["results"]):
            _TV_LAST_FETCHED = datetime.utcnow()
            _CACHED_TV_SCHEDULE = sched["results"]
    return _CACHED_TV_SCHEDULE


_RUV_RADIO_SCHEDULE_API_ENDPOINT = "https://muninn.ruv.is/files/json/{0}/{1}/"
_RADIO_API_ERRMSG = "Ekki tókst að sækja útvarpsdagskrá."
_RADIO_SCHED_CACHE: Dict[str, List] = {}
_RADIO_LAST_FETCHED: Dict[str, datetime] = {}


def _query_radio_schedule_api(channel: str) -> List:
    """Fetch current radio schedule from RÚV API, or return cached copy."""
    global _RADIO_SCHED_CACHE
    global _RADIO_LAST_FETCHED

    if (
        not _RADIO_SCHED_CACHE.get(channel)
        or not _RADIO_LAST_FETCHED.get(channel)
        or _RADIO_LAST_FETCHED[channel].date() != datetime.today().date()
    ):
        # Not cached. Fetch data.
        today = datetime.today()

        url = _RUV_RADIO_SCHEDULE_API_ENDPOINT.format(
            channel, today.strftime("%Y-%m-%d")
        )
        response = query_json_api(url)

        if (
            not response
            or not response.get("schedule")
            or not response["schedule"].get("services")
            or len(response["schedule"]["services"]) == 0
        ):
            return []

        _RADIO_SCHED_CACHE[channel] = response["schedule"]["services"][0].get(
            "events", []
        )
        _RADIO_LAST_FETCHED[channel] = today

    return _RADIO_SCHED_CACHE.get(channel, [])


def _span(p: Dict, tv: bool = True) -> Tuple[datetime, datetime]:
    """Return the time span of a program."""
    if tv:
        start = datetime.strptime(p["startTime"], "%Y-%m-%d %H:%M:%S")
    else:
        start = datetime.strptime(p["start-time"], "%Y-%m-%d %H:%M:%S")
    h, m, _ = p["duration"].split(":")
    dur = timedelta(hours=int(h), minutes=int(m))
    return start, start + dur


def _curr_prog(sched: List, tv: bool = True) -> Optional[Dict]:
    """
    Return current TV/radio program (based on tv boolean), given a schedule
    i.e. a list of programs in chronological sequence.
    """
    now = datetime.utcnow()
    for p in sched:
        t1, t2 = _span(p, tv)
        if t1 <= now < t2:
            return p
        if t1 > now:
            # We're past the current time in the schedule
            break
    return None


def _evening_prog(sched: List) -> List:
    """
    Return programs on a TV schedule starting from 19:00,
    or at the current time if later.
    """
    start = datetime.utcnow()
    if (start.hour, start.minute) < (19, 0):
        start = datetime(start.year, start.month, start.day, 19, 0, 0)
    result = []
    for p in sched:
        t1, t2 = _span(p)
        if (t1 <= start < t2) or t1 >= start:
            # Item is being shown or will be shown later in the evening
            result.append(p)
    return result


def _gen_curr_tv_program_answer(q: Query, result: Result) -> AnswerTuple:
    """Generate answer to query about current TV program."""
    sched = _query_tv_schedule_api()
    if not sched:
        return gen_answer(_TV_API_ERRMSG)

    prog = _curr_prog(sched)
    if not prog:
        return gen_answer("Það er engin dagskrá á RÚV núna.")

    title = prog["title"]
    ep = "" if "fréttir" in title.lower() else ""
    answ = f"RÚV er að sýna {ep}{title}. {_clean_desc(prog['description'])}."
    return gen_answer(answ)


def _gen_evening_tv_program_answer(q: Query, result: Result) -> AnswerTuple:
    """Generate answer to query about the evening's TV programs"""
    sched = _query_tv_schedule_api()
    if not sched:
        return gen_answer(_TV_API_ERRMSG)

    prog = _evening_prog(sched)
    if not prog:
        return gen_answer("Það er enginn liður eftir á dagskrá RÚV.")

    answ = ["Klukkan"]
    for p in prog:
        answ.append(f"{p['startTime'][11:16]} : {p['title']}.\n")
    voice_answer = "".join(answ)
    answer = "".join(answ[1:]).replace(" : ", " ")
    return dict(answer=answer), answer, voice_answer


def _gen_curr_radio_program_answer(q: Query, result: Result) -> AnswerTuple:
    """Generate answer to query about current radio program."""
    sched = _query_radio_schedule_api(result.get("radio_channel", "ras1"))
    if len(sched) == 0:
        return gen_answer(_RADIO_API_ERRMSG)

    prog = _curr_prog(sched, False)
    if not prog:
        ans = f"Það er engin dagskrá á {result.get('radio_channel_pretty')} núna."
        return dict(answer=ans), ans, ans.replace("1", "eitt").replace("2", "tvö")

    title = prog["title"]
    desc = prog["description"]
    answ = f"Á {result.get('radio_channel_pretty')} er verið að spila {title}. {_clean_desc(desc)}"
    return (
        dict(answer=answ),
        answ,
        answ.replace("Rás 1", "Rás eitt").replace("Rás 2", "Rás tvö"),
    )


_HANDLER_MAP = {
    _TELEVISION_QKEY: _gen_curr_tv_program_answer,
    _TELEVISION_EVENING_QKEY: _gen_evening_tv_program_answer,
    _RADIO_QKEY: _gen_curr_radio_program_answer,
}


def sentence(state: QueryStateDict, result: Result) -> None:
    """Called when sentence processing is complete"""
    q: Query = state["query"]
    handler_keys = _HANDLER_MAP.keys()
    if "qtype" in result and "qkey" in result and result["qkey"] in handler_keys:
        # Successfully matched a query type
        q.set_qtype(result.qtype)
        q.set_key(result.qkey)

        try:
            r: AnswerTuple = _HANDLER_MAP[result.qkey](q, result)
            q.set_answer(*r)
            q.set_beautified_query(q._beautified_query.replace("rúv", "RÚV"))
            # TODO: Set intelligent expiry time
            q.set_expires(datetime.utcnow() + timedelta(minutes=3))
        except Exception as e:
            logging.warning(
                f"Exception while processing TV schedule query: {e}"
            )
            q.set_error(f"E_EXCEPTION: {e}")

    else:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
