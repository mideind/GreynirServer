"""

    Greynir: Natural language processing for Icelandic

    TV & radio schedule query response module

    Copyright (C) 2023 Miðeind ehf.

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

"""

# TODO: "Hvaða þættir eru á rúv?"
# TODO: Channels provided by Síminn
# TODO: "Rás tveir" vandamál, ætti að vera "Rás tvö"

from typing import List, Dict, Optional, Tuple, Any, cast
from typing_extensions import TypedDict
from queries import Query, QueryStateDict
from tree import Node, TerminalNode, ParamList, Result

import logging
import random
import datetime
import cachetools

from tokenizer import split_into_sentences

from speech.trans import gssml
from settings import changedlocale
from queries.util import query_json_api, read_grammar_file


_SCHEDULES_QTYPE = "Schedule"


TOPIC_LEMMAS = [
    "dagskrá",
    "rás",
    "ríkissjónvarp",
    "ríkisútvarp",
    "rúv",
    "sjónvarp",
    "sjónvarpsdagskrá",
    "stöð",
    "útvarp",
    "útvarpsdagskrá",
    "útvarpsrás",
    "þáttur",
]


def help_text(lemma: str) -> str:
    """Help text to return when query processor is unable unable to parse a query but
    one of the above lemmas is found in it"""
    return "Ég get svarað ef þú spyrð til dæmis: {0}?".format(
        random.choice(
            (
                "Hvað er í sjónvarpinu",
                "Hvað er í útvarpinu",
                "Dagskrá RÚV klukkan 19:00",
                "Hvaða þátt er verið að sýna í sjónvarpinu",
                "Hvað er næsti þáttur á Stöð 2",
                "Hvað var í útvarpinu klukkan sjö í morgun",
                "Hvaða efni er verið að spila á Stöð 2",
                "Hvað verður á Rás 1 klukkan sjö í kvöld",
            )
        )
    )


# This module wants to handle parse trees for queries
HANDLE_TREE = True

# The grammar nonterminals this module wants to handle
QUERY_NONTERMINALS = {"QSchedule"}

# The context-free grammar for the queries recognized by this plug-in module
# Uses "QSch" as prefix for grammar namespace
GRAMMAR = read_grammar_file("schedules")

# Some constants used throughout the module
_RUV: str = "RÚV"
_STOD_TVO: str = "Stöð 2"
_SIMINN: str = "Síminn"
_TV: str = "tv"
_RADIO: str = "radio"


def _add_channel(
    result: Result, api: str, channel: str, channel_type: str, station: str
) -> None:
    """
    Helper function to fill result dictionary
    with info on a particular channel.
    """
    result["api_channel"] = api
    result["channel"] = channel
    result["channel_type"] = channel_type
    result["station"] = station


def QScheduleQuery(node: Node, params: ParamList, result: Result) -> None:
    result.qtype = _SCHEDULES_QTYPE


def QSchWill(node: Node, params: ParamList, result: Result) -> None:
    result["will_be"] = True


def QSchPM(node: Node, params: ParamList, result: Result) -> None:
    result["PM"] = True


def QSchAM(node: Node, params: ParamList, result: Result) -> None:
    result["PM"] = False


def QSchSérnafn(node: Node, params: ParamList, result: Result) -> None:
    channel = result._nominative.replace("Stöðvar", "Stöð")

    if channel == "Stöð 2 Sport 2":
        QSchStod2Sport2(node, params, result)
    elif channel == "Stöð 2 Sport":
        QSchStod2Sport(node, params, result)
    elif channel == "Stöð 2 Bíó":
        QSchStod2Bio(node, params, result)
    elif channel == _STOD_TVO:
        QSchStod2(node, params, result)


def QSchRUV(node: Node, params: ParamList, result: Result) -> None:
    _add_channel(result, "ruv", _RUV, _TV, _RUV)


def QSchRUV2(node: Node, params: ParamList, result: Result) -> None:
    _add_channel(result, "ruv2", "RÚV 2", _TV, _RUV)


def QSchStod2(node: Node, params: ParamList, result: Result) -> None:
    _add_channel(result, "stod2", _STOD_TVO, _TV, _STOD_TVO)


def QSchStod2Sport(node: Node, params: ParamList, result: Result) -> None:
    _add_channel(result, "sport", "Stöð 2 Sport", _TV, _STOD_TVO)


def QSchStod2Sport2(node: Node, params: ParamList, result: Result) -> None:
    _add_channel(result, "sport2", "Stöð 2 Sport 2", _TV, _STOD_TVO)


def QSchStod2Bio(node: Node, params: ParamList, result: Result) -> None:
    _add_channel(result, "bio", "Stöð 2 Bíó", _TV, _STOD_TVO)


def QSchStod3(node: Node, params: ParamList, result: Result) -> None:
    _add_channel(result, "stod3", "Stöð 3", _TV, _STOD_TVO)


def QSchRas1(node: Node, params: ParamList, result: Result) -> None:
    _add_channel(result, "ras1", "Rás 1", _RADIO, _RUV)


def QSchRas2(node: Node, params: ParamList, result: Result) -> None:
    _add_channel(result, "ras2", "Rás 2", _RADIO, _RUV)


def QSchNext(node: Node, params: ParamList, result: Result) -> None:
    result["get_next"] = True


def QSchTime(node: Node, params: ParamList, result: Result) -> None:
    # If exact time is given (e.g. 19:30)
    result["exact_time"] = ":" in result._text
    # Extract time from time terminal nodes
    tnode = cast(TerminalNode, node.first_child(lambda n: n.has_t_base("tími")))
    if tnode:
        aux_str = tnode.aux.strip("[]")
        hour, minute, _ = (int(i) for i in aux_str.split(", "))

        result["qtime"] = datetime.time(hour, minute)


def QSchThisMorning(node: Node, params: ParamList, result: Result) -> None:
    result["qdate"] = datetime.date.today()


def QSchThisEvening(node: Node, params: ParamList, result: Result) -> None:
    # It is debatable whether the following calculation should
    # occur in the client's time zone or in UTC (=Icelandic time)
    now = datetime.datetime.utcnow()
    evening = datetime.time(20, 0)
    result["qdate"] = now.date()  # !!! FIXME: Use consistent date calculation functions
    result["qtime"] = evening if now.time() < evening else now.time()
    result["PM"] = True


def QSchTomorrow(node: Node, params: ParamList, result: Result) -> None:
    result["qdate"] = datetime.date.today() + datetime.timedelta(days=1)


def QSchTomorrowEvening(node: Node, params: ParamList, result: Result) -> None:
    result["qdate"] = datetime.date.today() + datetime.timedelta(days=1)
    result["qtime"] = datetime.time(20, 0)
    result["PM"] = True


def QSchYesterday(node: Node, params: ParamList, result: Result) -> None:
    result["qdate"] = datetime.date.today() - datetime.timedelta(days=1)


def QSchYesterdayEvening(node: Node, params: ParamList, result: Result) -> None:
    result["qdate"] = datetime.date.today() - datetime.timedelta(days=1)
    result["qtime"] = datetime.time(20, 0)
    result["PM"] = True


def QSchNow(node: Node, params: ParamList, result: Result) -> None:
    now = datetime.datetime.utcnow()
    result["qdate"] = now.date()
    result["qtime"] = now.time()


_STATION_ENDPOINTS = {
    _STOD_TVO: "https://api.stod2.is/dagskra/api/{0}/{1}",
    _RUV: "https://muninn.ruv.is/files/json/{0}/{1}/",
    # _SIMINN: "https://api.tv.siminn.is/oreo-api/v2/channels/{0}/events?start={1}&end={2}",
}

# Schedule cache (keep for one day)
_SCHED_CACHE: cachetools.TTLCache = cachetools.TTLCache(maxsize=15, ttl=86400)  # type: ignore

# Type for schedules
_SchedType = List[Dict[str, Any]]


class _AnswerDict(TypedDict):
    """Format of answer dictionary. Includes answer from module
    along with station, channel and expiration time."""

    response: Dict[str, Any]
    answer: str
    voice: str
    station: str
    channel: str
    expire_time: datetime.datetime


# Programs which don't have/need a description
_NO_DESCRIPTION_SET = frozenset(
    ("fréttir", "fréttayfirlit", "veðurfréttir", "hádegisfréttir")
)


def _extract_ruv_schedule(response: Dict[str, Any]) -> _SchedType:
    """Safely extract schedule from RÚV API response."""
    if "error" in response.get("schedule", ""):
        return []
    try:
        return cast(_SchedType, response["schedule"]["services"][0]["events"])
    except (KeyError, IndexError):
        return []


def _query_schedule_api(channel: str, station: str, date: datetime.date) -> _SchedType:
    """Fetch and return channel schedule from API or cache for specified date."""

    if (channel, date) in _SCHED_CACHE:
        return cast(_SchedType, _SCHED_CACHE[(channel, date)])

    if station == _SIMINN:
        # TODO: Síminn endpoint needs its own formatting
        # since url includes start and end time along with channel ID
        return []
    else:
        url: str = _STATION_ENDPOINTS[station].format(channel, date.isoformat())
    response = query_json_api(url, timeout=30)

    if response is None:
        return []

    sched: _SchedType
    if station == _RUV:
        sched = _extract_ruv_schedule(cast(Dict[str, Any], response))
    else:
        # Other stations respond with list of dicts
        sched = cast(_SchedType, response)

    # Only cache non-empty schedules
    # (the empty schedules might get updated during the day)
    if len(sched) > 0:
        _SCHED_CACHE[(channel, date)] = sched

    return sched


def _get_program_start_end(
    program: Dict[str, str], station: str
) -> Tuple[datetime.datetime, datetime.datetime]:
    """Return the time span of an episode/program."""

    if station == _SIMINN:
        start = datetime.datetime.strptime(program["start"], "%Y-%m-%dT%H:%M:%S.%fZ")
        end = datetime.datetime.strptime(program["end"], "%Y-%m-%dT%H:%M:%S.%fZ")
        return (start, end)

    if station == _RUV:
        start = datetime.datetime.strptime(program["start-time"], "%Y-%m-%d %H:%M:%S")
        d = list(map(int, program["duration"].split(":")))
        duration = datetime.timedelta(
            hours=d[0], minutes=d[1], seconds=d[2] if len(d) >= 3 else 0
        )
    elif station == _STOD_TVO:
        start = datetime.datetime.strptime(program["upphaf"], "%Y-%m-%dT%H:%M:%SZ")
        d = list(map(int, program["slotlengd"].split(":")))
        duration = datetime.timedelta(hours=d[0], minutes=d[1], seconds=0)
    else:
        # Unknown station
        start = datetime.datetime.utcnow()
        duration = datetime.timedelta()

    return (start, start + duration)


def _programs_after_time(
    sched: _SchedType, station: str, qdatetime: datetime.datetime
) -> Tuple[_SchedType, bool]:
    """
    Return list of programs in sched that haven't finished at time qdatetime
    and a boolean for whether a program has already started.
    """
    start: datetime.datetime
    end: datetime.datetime

    curr_playing: bool = False
    i = 0
    while i < len(sched):
        start, end = _get_program_start_end(sched[i], station)

        if end > qdatetime:  # Program hasn't ended
            if start <= qdatetime:  # Program has started
                curr_playing = True
            break
        i += 1

    # Programs that haven't finished,
    # and whether a program has started
    return sched[i:], curr_playing


def _split_ruv_schedule(sched: _SchedType) -> Tuple[_SchedType, _SchedType]:
    """
    Splits RÚV schedule into events and sub-events, as some
    programs (sub-events) are played during other programs (events)
    (e.g. "Morgunfréttir" is shown during "Morgunvaktin" on Rás 1).
    """
    events: _SchedType = []
    sub_events: _SchedType = []

    for program in sched:
        if program.get("type") == "subevent":
            sub_events.append(program)
        else:
            events.append(program)

    return events, sub_events


def _get_current_and_next_program(
    sched: _SchedType,
    station: str,
    qdatetime: datetime.datetime,
    get_next: bool,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Extract current program and next program, if any,
    from a schedule at time qdatetime.
    """

    progs: _SchedType
    is_playing: bool
    sub_progs: _SchedType = []
    sub_is_playing: bool = False

    curr_playing: Optional[Dict[str, Any]] = None
    next_playing: Optional[Dict[str, Any]] = None

    if station == _RUV:
        # Special handling for RÚV, as they have events and sub-events
        # e.g. "Morgunfréttir" is shown during "Morgunvaktin" on Rás 1
        progs, sub_progs = _split_ruv_schedule(sched)

        # Events
        progs, is_playing = _programs_after_time(progs, station, qdatetime)
        # Sub-events
        sub_progs, sub_is_playing = _programs_after_time(sub_progs, station, qdatetime)

    else:
        # Other stations than RÚV
        progs, is_playing = _programs_after_time(sched, station, qdatetime)

    if len(progs) == 0:
        # Schedule is finished at qdatetime
        return None, None

    if sub_is_playing and sub_progs:
        # RÚV sub-event playing, also fetch parent event
        curr_playing = sub_progs[0]
        next_playing = progs[0]
        return curr_playing, next_playing

    if is_playing:
        # Program playing
        curr_playing = progs[0]

        # Try to also fetch next program if get_next is True
        if get_next:
            # Deal with RÚV sub-events
            if station == _RUV and len(sub_progs):
                if len(progs) > 1:
                    # Get start time of next sub-event and next event
                    next_sub_start = datetime.datetime.strptime(
                        sub_progs[0]["start-time"], "%Y-%m-%d %H:%M:%S"
                    )
                    next_event_start = datetime.datetime.strptime(
                        progs[1]["start-time"], "%Y-%m-%d %H:%M:%S"
                    )
                else:
                    next_sub_start = next_event_start = datetime.datetime.utcnow()

                # If current event is last event of the day or
                # next sub-event begins before next event
                if len(progs) == 1 or next_sub_start < next_event_start:
                    # Next up is a sub-event
                    next_playing = sub_progs[0]

            if next_playing is None and len(progs) > 1:
                # If next playing isn't already set,
                # set it as the next program/event
                next_playing = progs[1]

    elif qdatetime > datetime.datetime.utcnow() - datetime.timedelta(minutes=5):
        # Nothing playing at qdatetime,
        # fetch next program if query isn't for past schedule
        next_playing = progs[0]

    return curr_playing, next_playing


def _extract_title_and_desc(prog: Dict[str, Any], station: str) -> Tuple[str, str]:
    """
    Extract title and description of a program on a given station.
    """
    title: str = ""
    desc: str = ""

    if station == _RUV:
        title = prog.get("title", "") or ""

        if title.lower() not in _NO_DESCRIPTION_SET:
            desc = prog.get("description", "") or ""

            # Backup description
            if desc == "" and prog.get("details"):
                desc = prog["details"].get("series-description", "") or ""

    elif station == _STOD_TVO:
        title = prog.get("isltitill", "") or ""
        # Backup title
        if title == "":
            title = prog.get("titill", "") or ""

        desc = prog.get("lysing", "") or ""

    elif station == _SIMINN:
        title = prog.get("title", "") or ""

        # Note: Some channels have descriptions in English,
        # might cause problems for the voice
        desc = prog.get("description", "") or ""

        # Backup description
        if desc == "" and prog.get("episode"):
            desc = prog["episode"].get("description", "") or ""

    return (title, desc)


def _clean_desc(d: str) -> str:
    """Return first sentence in multi-sentence string."""
    return list(split_into_sentences(d, original=True))[0]


def _answer_next_program(
    next_prog: Optional[Dict[str, Any]],
    station: str,
    channel: str,
    is_radio: bool,
) -> _AnswerDict:
    """
    Create query answer dict, containing:
        response dict
        answer: text for displaying
        voice: text for voice line
        station: tv/radio station
        channel: tv/radio channel
        expire_time: when the answer becomes outdated.
    """
    answer: str = ""
    prog_endtime: datetime.datetime = datetime.datetime.utcnow()

    if next_prog:
        next_title, next_desc = _extract_title_and_desc(next_prog, station)

        answer += (
            f"Næst á dagskrá á {channel} verður "
            f"{'spilaður' if is_radio else 'sýndur'} "
            f"dagskrárliðurinn {next_title}."
        )

        if next_desc != "":
            answer += " " + _clean_desc(next_desc)

        # Answer is valid for station until the next program starts
        prog_endtime, _ = _get_program_start_end(next_prog, station)
    else:
        answer = f"Það er ekkert á dagskrá á {channel} eftir núverandi dagskrárlið."

    return {
        "response": {"answer": answer, "voice": answer},
        "answer": answer,
        "voice": answer,
        "station": station,
        "channel": channel,
        "expire_time": prog_endtime,
    }


def _answer_program(
    curr_prog: Optional[Dict[str, Any]],
    station: str,
    channel: str,
    qdatetime: datetime.datetime,
    is_radio: bool,
) -> _AnswerDict:
    """
    Create query answer dict, containing:
        response dict
        answer: text for displaying
        voice: text for voice line
        station: tv/radio station
        channel: tv/radio channel
        expire_time: when the answer becomes outdated.
    """

    now = datetime.datetime.utcnow()
    answer: str = ""
    voice: str
    is_now: bool
    is_future: bool = qdatetime > now
    showtime: str = ""
    vshowtime: str = ""
    showing: str
    prog_endtime: Optional[datetime.datetime] = None

    # If qdatetime is within one minute of now
    is_now = abs(now - qdatetime) <= datetime.timedelta(minutes=1)

    if is_now:
        showing = f"er verið að {'spila' if is_radio else 'sýna'} dagskrárliðinn"
    else:
        showing = (
            f"{'verður' if is_future else 'var'} "
            f"{'spilaður' if is_radio else 'sýndur'} dagskrárliðurinn"
        )

        showtime = f" klukkan {qdatetime.strftime('%-H:%M')}"
        vshowtime = " klukkan " + gssml(qdatetime.strftime("%-H:%M"), type="time")

        day_diff = qdatetime.date() - datetime.date.today()

        if day_diff == datetime.timedelta(days=1):
            showtime += " á morgun"
            vshowtime += " á morgun"
        elif day_diff == datetime.timedelta(days=-1):
            showtime += " í gær"
            vshowtime += " í gær"
        elif day_diff != datetime.timedelta(days=0):
            showtime += qdatetime.strftime(" %-d. %B")
            vshowtime += gssml(qdatetime.strftime(" %-d. %B"), type="date")

    if curr_prog:
        curr_title, curr_desc = _extract_title_and_desc(curr_prog, station)

        answer = f"Á {channel}{{showtime}} {showing} {curr_title}."

        if curr_desc != "":
            answer += " " + _clean_desc(curr_desc)

        # Answer is valid for station until the program starts
        _, prog_endtime = _get_program_start_end(curr_prog, station)
    else:
        if is_now:
            answer = f"Ekkert er á dagskrá á {channel} í augnablikinu."
        else:
            answer = f"Ekkert {'verður' if is_future else 'var'} á dagskrá á {channel}{{showtime}}."

    # Mark time/date info for transcribing in voice answer
    voice = answer.format(showtime=vshowtime)
    answer = answer.format(showtime=showtime)
    return {
        "response": {"answer": answer},
        "answer": answer,
        "voice": voice,
        "station": station,
        "channel": channel,
        "expire_time": cast(datetime.datetime, prog_endtime),
    }


def _get_schedule_answer(result: Result) -> _AnswerDict:
    """Generate answer to query about current TV/radio program."""

    api_channel: str = result.get("api_channel")
    channel: str = result.get("channel")
    station: str = result.get("station")
    is_radio: bool = result.get("channel_type") == _RADIO

    now = datetime.datetime.utcnow()
    now_date: datetime.date = now.date()
    now_time: datetime.time = now.time()

    qdate: datetime.date = result.get("qdate") or now_date
    qtime: datetime.time = result.get("qtime") or now_time
    # Construct datetime from date/time in query (by default use current date/time)
    qdt: datetime.datetime = datetime.datetime.combine(qdate, qtime)

    # If exact time isn't specified (e.g. "klukkan sjö" instead of "klukkan 7:00")
    if not result.get("exact_time"):
        if qdt.hour < 12 and result.get("PM"):
            # If wording specifies afternoon (e.g. "í kvöld", "eftir hádegi")
            qdt += datetime.timedelta(hours=12)

        elif result.get("will_be") and qdt < now:
            # If wording implies we want schedule in future
            # and query datetime is in past
            # (e.g. "verður sýnt kl sjö" when current time is more than seven)
            qdt += datetime.timedelta(hours=12)

    get_next: bool = result.get("get_next", False)

    # Fetch schedule data from API or cache.
    sched: _SchedType = _query_schedule_api(api_channel, station, qdt.date())

    if len(sched) == 0:
        error = f"Ekki tókst að sækja dagskrána á {channel}."

        return _AnswerDict(
            response={"answer": error},
            answer=error,
            voice=f"Ekki tókst að sækja dagskrána á {gssml(channel, type='numbers', gender='hk')}.",
            station=station,
            channel=channel,
            expire_time=qdt,
        )

    curr_prog: Optional[Dict[str, Any]]
    next_prog: Optional[Dict[str, Any]]
    curr_prog, next_prog = _get_current_and_next_program(sched, station, qdt, get_next)

    with changedlocale(category="LC_TIME"):
        if get_next:
            # Only asking for next program
            return _answer_next_program(next_prog, station, channel, is_radio)
        else:
            # Asking for current program or program at specific date/time
            return _answer_program(curr_prog, station, channel, qdt, is_radio)


def sentence(state: QueryStateDict, result: Result) -> None:
    """Called when sentence processing is complete"""
    q: Query = state["query"]

    if (
        "qtype" in result
        and "api_channel" in result
        and "channel" in result
        and "station" in result
    ):
        # Successfully matched a query type
        q.set_qtype(result.qtype)

        try:
            r: _AnswerDict = _get_schedule_answer(result)

            q.set_key(r["station"] + " - " + r["channel"])
            q.set_source(r["station"])
            q.set_beautified_query(q.beautified_query.replace("rúv", _RUV))

            q.set_expires(r["expire_time"])
            q.set_answer(r["response"], r["answer"], r["voice"])

        except Exception as e:
            logging.warning(f"Exception while processing TV/radio schedule query: {e}")
            q.set_error(f"E_EXCEPTION: {e}")

    else:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
