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

"""

# TODO: Fix formatting issues w. trailing spaces, periods at the end of answer str
# TODO: "Hvað er á dagskrá á rúv annað kvöld?"
# TODO: "Hvaða þættir eru á rúv?"
# TODO: Channels provided by Síminn (sometimes foreign channels)

from typing import List, Dict, Optional, Tuple, Any, cast
from typing_extensions import TypedDict

import logging
import random
import datetime
import cachetools

from settings import changedlocale
from query import AnswerTuple, Query, QueryStateDict
from queries import query_json_api, gen_answer
from tree import Node, ParamList, Result


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
    """Help text to return when query.py is unable to parse a query but
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
GRAMMAR = """

Query →
    QSchedule

QSchedule →
    QScheduleQuery '?'?

# Examples:
# Hvað er verið að spila á rás eitt?
# Hvað verður á dagskrá á Stöð 2 klukkan 21:00?
QScheduleQuery →
    QSchWhatIsWillWas QSchEiginlega? QSchBeingShown? QSchOnScheduleOnStation QSchWhen?
    | QSchWhatIsWillWas QSchEiginlega? QSchBeingShown? QSchWhen? QSchOnScheduleOnStation
    # Dagskrá Stöð 2 klukkan 18:00
    | 'dagskrá:kvk' QSchWhen? QSchOn? QSchStation QSchWhen?
    | QSchNextShow

# Queries asking about next program in schedule:
# Hvað er eiginlega verið að sýna næst á RÚV?
# Hvað er næst á dagskrá í sjónvarpinu?
QSchNextShow →
    QSchWhatIsWillWas QSchEiginlega? QSchNext? QSchBeingShown? QSchNext? QSchOnScheduleOnStation

QSchBeingShown →
    "verið" "að" "spila"
    | "verið" "að" "sýna"
    | "í" "gangi"
    | "í" "spilun"

QSchWhatIsWillWas →
    "hvað" QSchIsWillWas
    | "hver" QSchIsWillWas
    | "hvað" "mun" QSchIsWillWas
    | "hvaða" 'þáttur:kk'_et/fall QSchIsWillWas
    | "hvaða" 'dagskrárliður:kk'_et/fall QSchIsWillWas
    | "hvaða" 'efni:hk'/fall QSchIsWillWas

QSchIsWillWas →
    'vera:so'
    | 'verða:so'

QSchOnScheduleOnStation →
    QSchOnSchedule QSchOn? 'sjónvarpsstöð:kvk'/fall? QSchStation
    | QSchOn 'sjónvarpsstöð:kvk'/fall? QSchStation

QSchNext →
    'næstur:lo'
    | "næsti" "þáttur"
    | "næsti" "dagskrárliður"
    | "næsta" "efni"

QSchEiginlega →
    "eiginlega"

QSchOnSchedule →
    "á" 'dagskrá:kvk'_þgf
    | "í" 'dagskrá:kvk'_þgf
    | "í" "gangi"
    | "verið" "að" "sýna"

QSchOn →
    "á" | "í" | "hjá"


QSchStation →
    QSchRUV
    | QSchRUV2
    | QSchStod2
    | QSchStod2Sport
    | QSchStod2Sport2
    | QSchStod2Bio
    | QSchStod3
    | QSchRas1
    | QSchRas2
    | QSchSérnafn

# Catch entities such as "Stöð 2 Sport"
QSchSérnafn →
    Sérnafn

###############
# TV stations #
###############

QSchRUV →
    'sjónvarp:hk'/fall
    | "rúv"
    | 'RÚV'
    | 'ríkissjónvarp:hk'/fall
    | 'stöð:kvk' "eitt"
    | 'stöð:kvk' "1"

QSchRUV2 →
    "rúv" "2"
    | "rúv" 'tveir:to'
    | "rúv" 'íþrótt:kvk'/fall
    | 'RÚV' "2"
    | 'RÚV' 'tveir:to'
    | "RÚV" 'íþrótt:kvk'/fall

QSchStod2 →
    'stöð:kvk' "tvö"
    | 'stöð:kvk' "2"
    | 'Stöð_2'

QSchStod2Sport →
    QSchStod2 "sport"

QSchStod2Sport2 →
    QSchStod2Sport "tvö"
    | QSchStod2Sport "2"

QSchStod2Bio →
    QSchStod2 "bíó"

QSchStod3 →
    'stöð:kvk' "þrjú"
    | 'stöð:kvk' "3"
    | QSchStod2 'fjölskylda:kvk'

##################
# Radio stations #
##################

QSchRas1 →
    'rás:kvk' "eitt"
    | 'rás:kvk' "1"
    | 'Rás_1'
    | 'útvarp:hk'/fall
    | 'ríkisútvarp:hk'/fall

QSchRas2 →
    'rás:kvk' "tvö"
    | 'rás:kvk' "2"
    | 'Rás_2'

##################

QSchWhen →
    QSchNow
    | QSchTime? QSchDay?
    | QSchDay? QSchTime?

QSchNow →
    "nákvæmlega"? "núna"
    | "í" "augnablikinu"
    | "eins" "og" "stendur"

QSchTime →
    "klukkan"? tími

QSchDay →
    QSchThisMorning
    | QSchThisEvening
    | QSchTomorrowMorning
    | QSchTomorrowEvening
    | QSchAM? QSchYesterday

QSchThisMorning →
    'í_morgun:ao'
    | QSchAM QSchToday?

QSchThisEvening →
    "seinna"? 'í_kvöld'
    | "seinna"? QSchToday

QSchToday →
    "í" "dag"

QSchTomorrowMorning →
    QSchAM? 'á_morgun'

QSchTomorrowEvening →
    "annað" "kvöld"

QSchYesterday →
    'í_gær'

QSchAM →
    "fyrir" "hádegi"

$score(+55) QSchedule

"""


def QScheduleQuery(node: Node, params: ParamList, result: Result) -> None:
    result.qtype = _SCHEDULES_QTYPE


def QSchSérnafn(node: Node, params: ParamList, result: Result) -> None:
    channel = result._nominative.replace("Stöðvar", "Stöð")

    if channel == "Stöð 2 Sport 2":
        QSchStod2Sport2(node, params, result)
    elif channel == "Stöð 2 Sport":
        QSchStod2Sport(node, params, result)
    elif channel == "Stöð 2 Bíó":
        QSchStod2Bio(node, params, result)
    elif channel == "Stöð 2":
        QSchStod2(node, params, result)


def QSchRUV(node: Node, params: ParamList, result: Result) -> None:
    result["channel"] = "ruv"
    result["channel_pretty"] = "RÚV"
    result["channel_type"] = "tv"
    result["station"] = "ruv"


def QSchRUV2(node: Node, params: ParamList, result: Result) -> None:
    result["channel"] = "ruv2"
    result["channel_pretty"] = "RÚV 2"
    result["channel_type"] = "tv"
    result["station"] = "ruv"


def QSchStod2(node: Node, params: ParamList, result: Result) -> None:
    result["channel"] = "stod2"
    result["channel_pretty"] = "Stöð 2"
    result["channel_type"] = "tv"
    result["station"] = "stod2"


def QSchStod2Sport(node: Node, params: ParamList, result: Result) -> None:
    result["channel"] = "sport"
    result["channel_pretty"] = "Stöð 2 Sport"
    result["channel_type"] = "tv"
    result["station"] = "stod2"


def QSchStod2Sport2(node: Node, params: ParamList, result: Result) -> None:
    result["channel"] = "sport2"
    result["channel_pretty"] = "Stöð 2 Sport 2"
    result["channel_type"] = "tv"
    result["station"] = "stod2"


def QSchStod2Bio(node: Node, params: ParamList, result: Result) -> None:
    result["channel"] = "bio"
    result["channel_pretty"] = "Stöð 2 Bíó"
    result["channel_type"] = "tv"
    result["station"] = "stod2"


def QSchStod3(node: Node, params: ParamList, result: Result) -> None:
    result["channel"] = "stod3"
    result["channel_pretty"] = "Stöð 3"
    result["channel_type"] = "tv"
    result["station"] = "stod2"


def QSchRas1(node: Node, params: ParamList, result: Result) -> None:
    result["channel"] = "ras1"
    result["channel_pretty"] = "Rás 1"
    result["channel_type"] = "radio"
    result["station"] = "ruv"


def QSchRas2(node: Node, params: ParamList, result: Result) -> None:
    result["channel"] = "ras2"
    result["channel_pretty"] = "Rás 2"
    result["channel_type"] = "radio"
    result["station"] = "ruv"


def QSchNext(node: Node, params: ParamList, result: Result) -> None:
    result["get_next"] = True


def QSchTime(node: Node, params: ParamList, result: Result) -> None:
    # Time nodes
    tnode = node.first_child(lambda n: n.has_t_base("tími"))
    if tnode:
        aux_str = tnode.aux.strip("[]")
        hour, minute, _ = (int(i) for i in aux_str.split(", "))

        result["qtime"] = datetime.time(hour, minute)


def QSchThisMorning(node: Node, params: ParamList, result: Result) -> None:
    result["morning"] = True
    result["qdate"] = datetime.date.today()


def QSchThisEvening(node: Node, params: ParamList, result: Result) -> None:
    result["qdate"] = datetime.date.today()


def QSchTomorrowMorning(node: Node, params: ParamList, result: Result) -> None:
    result["morning"] = True
    result["qdate"] = datetime.date.today() + datetime.timedelta(days=1)


def QSchTomorrowEvening(node: Node, params: ParamList, result: Result) -> None:
    result["qdate"] = datetime.date.today() + datetime.timedelta(days=1)


def QSchAM(node: Node, params: ParamList, result: Result) -> None:
    result["morning"] = True


def QSchYesterday(node: Node, params: ParamList, result: Result) -> None:
    result["qdate"] = datetime.date.today() - datetime.timedelta(days=1)


def QSchNow(node: Node, params: ParamList, result: Result) -> None:
    now = datetime.datetime.today()
    result["qdate"] = now.date()
    result["qtime"] = now.time()


_STATION_ENDPOINTS = {
    "stod2": "https://api.stod2.is/dagskra/api/{0}/{1}",
    "ruv": "https://muninn.ruv.is/files/json/{0}/{1}/",
    # "siminn": "https://api.tv.siminn.is/oreo-api/v2/channels/{0}/events?start={1}&end={2}",
}

# Schedule cache (keep for one day)
_SCHED_CACHE: cachetools.TTLCache = cachetools.TTLCache(maxsize=15, ttl=86400)

SchedType = List[Dict[str, Any]]


def _extract_ruv_schedule(response: Dict) -> SchedType:
    """Safely extract schedule from RUV API response."""
    if "error" in response.get("schedule", ""):
        return []
    try:
        return response["schedule"]["services"][0]["events"]
    except (KeyError, IndexError):
        return []


def _query_schedule_api(channel: str, station: str, date: datetime.date) -> SchedType:
    """Fetch and return channel schedule from API or cache for specified date."""

    if (channel, date) in _SCHED_CACHE:
        return _SCHED_CACHE[(channel, date)]

    if station == "siminn":
        # TODO: Siminn endpoint needs its own formatting
        # since url includes start and end time along with channel ID
        return []
    else:
        url: str = _STATION_ENDPOINTS[station].format(channel, date.isoformat())
    response: Optional[Dict] = query_json_api(url)

    if response is None:
        return []

    sched: SchedType
    if station == "ruv":
        sched = _extract_ruv_schedule(response)
    else:
        # Other stations respond with list of dicts
        sched = cast(SchedType, response)

    # Only cache non-empty schedules
    # (the empty schedules might get updated during the day)
    if len(sched) > 0:
        _SCHED_CACHE[(channel, date)] = sched

    return sched


def _get_program_start_end(
    program: Dict, station: str
) -> Tuple[datetime.datetime, datetime.datetime]:
    """Return the time span of a episode/program."""

    start: datetime.datetime
    end: datetime.datetime
    duration_dt: datetime.datetime
    duration: datetime.timedelta

    if station == "ruv":
        start = datetime.datetime.strptime(program["start-time"], "%Y-%m-%d %H:%M:%S")
        duration_dt = datetime.datetime.strptime(program["duration"], "%H:%M:%S")

    elif station == "stod2":
        start = datetime.datetime.strptime(program["upphaf"], "%Y-%m-%dT%H:%M:%SZ")
        duration_dt = datetime.datetime.strptime(program["slotlengd"], "%H:%M")

    elif station == "siminn":
        start = datetime.datetime.strptime(program["start"], "%Y-%m-%dT%H:%M:%S.%fZ")
        end = datetime.datetime.strptime(program["end"], "%Y-%m-%dT%H:%M:%S.%fZ")
        return (start, end)

    # Duration of program
    duration = datetime.timedelta(
        hours=duration_dt.hour,
        minutes=duration_dt.minute,
        seconds=duration_dt.second,
    )
    end = start + duration
    return (start, end)


def _programs_after_time(
    sched: SchedType, station: str, qdatetime: datetime.datetime
) -> Tuple[List[Dict], bool]:
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


def _split_ruv_schedule(sched: SchedType) -> Tuple[SchedType, SchedType]:
    """
    Splits RÚV schedule into events and sub-events, as some
    programs (sub-events) are played during other programs (events)
    (e.g. "Morgunfréttir" is shown during "Morgunvaktin" on Rás 1).
    """
    events: SchedType = []
    sub_events: SchedType = []

    for program in sched:
        if program.get("type") == "subevent":
            sub_events.append(program)
        else:
            events.append(program)

    return events, sub_events


class AnswerDict(TypedDict):
    response: Dict[str, Any]
    answer: str
    voice: str
    station: str
    channel: str
    expire_time: datetime.datetime


def _get_current_and_next_program(
    sched: SchedType,
    station: str,
    qdatetime: datetime.datetime,
    get_next: bool,
) -> Tuple[Optional[Dict], Optional[Dict]]:
    """
    Extract current program and next program, if any,
    from a schedule at time qdatetime.
    """

    progs: SchedType
    is_playing: bool
    sub_progs: SchedType
    sub_is_playing: bool = False

    curr_playing: Optional[Dict] = None
    next_playing: Optional[Dict] = None

    if station == "ruv":
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

    if sub_is_playing and len(sub_progs):
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
            if station == "ruv" and len(sub_progs):
                if len(progs) > 1:
                    # Get start time of next sub-event and next event
                    next_sub_start = datetime.datetime.strptime(
                        sub_progs[0]["start-time"], "%Y-%m-%d %H:%M:%S"
                    )
                    next_event_start = datetime.datetime.strptime(
                        progs[1]["start-time"], "%Y-%m-%d %H:%M:%S"
                    )

                # If current event is last event of the day or
                # next sub-event begins before next event
                if len(progs) == 1 or next_sub_start < next_event_start:
                    # Next up is a sub-event
                    next_playing = sub_progs[0]

            if next_playing is None and len(progs) > 1:
                # If next playing isn't already set,
                # set it as the next program/event
                next_playing = progs[1]

    elif qdatetime > datetime.datetime.now() - datetime.timedelta(minutes=5):
        # Nothing playing at qdatetime,
        # fetch next program if query isn't for past schedule
        next_playing = progs[0]

    return curr_playing, next_playing


_FRETTIR_FROZENSET = frozenset(("fréttir", "fréttayfirlit"))


def _extract_title_and_desc(prog: Dict, station: str) -> Tuple[str, str]:
    """
    Extract title and description of a program on a given station.
    """
    title: str = ""
    desc: str = ""

    if station == "ruv":
        title = prog.get("title", "")

        if title.lower() not in _FRETTIR_FROZENSET:
            desc = prog.get("description", "")

            # Backup description
            if desc is None or desc == "":
                if (
                    "details" in prog
                    and prog["details"].get("series-description", "") != ""
                ):
                    desc = prog["details"]["series-description"]

    elif station == "stod2":

        title = prog.get("isltitill", "")
        # Backup title
        if title is None or title == "":
            title = prog.get("titill", "")

        desc = prog.get("lysing", "")

    elif station == "siminn":
        title = prog.get("title", "")

        # TODO: Some channels have descriptions in English,
        # might cause problems for the voice
        desc = prog.get("description", "")

        # Backup description
        if desc is None or desc == "":
            if "episode" in prog and prog["episode"].get("description", "") != "":
                desc = prog["episode"]["description"]

    if title is None:
        title = ""

    if desc is None:
        desc = ""

    return (title, desc)


def _clean_desc(d: str) -> str:
    """Return first sentence in multi-sentence string."""
    # TODO: Improve this
    return d.replace("Dr.", "Doktor").replace("?", ".").split(".")[0]


def _generate_answer(
    curr_prog: Optional[Dict],
    next_prog: Optional[Dict],
    station: str,
    channel_pretty: str,
    qdatetime: datetime.datetime,
    is_radio: bool,
) -> AnswerDict:
    """
    Create query answer dict, containing:
        response dict
        answer, text for displaying
        voice, text for voice line
        station, tv/radio station
        channel, tv/radio channel
        expire_time (datetime), when the answer becomes outdated.
    """

    answer: str = ""
    voice: str
    is_now: bool
    is_future: bool = False
    showtime: str
    showing: str
    prog_endtime: Optional[datetime.datetime] = None

    # If qdatetime is within one minute of now
    is_now = abs(datetime.datetime.now() - qdatetime) <= datetime.timedelta(minutes=1)

    if is_now:
        showing = "er verið að spila" if is_radio else "er verið að sýna"
    else:
        if qdatetime > datetime.datetime.now():
            is_future = True
            # Wording for schedule in the future
            showing = f"verður {'spilaður' if is_radio else 'sýndur'} dagskrárliðurinn"
        else:
            is_future = False
            # Wording for schedule in the past
            showing = f"var {'spilaður' if is_radio else 'sýndur'} dagskrárliðurinn"

        day_diff = datetime.date.today() - qdatetime.date()
        if day_diff == datetime.timedelta(0):
            showtime = f"klukkan {qdatetime.strftime('%H:%M')}"

        elif day_diff == datetime.timedelta(days=-1):
            showtime = f"klukkan {qdatetime.strftime('%H:%M')} á morgun"

        elif day_diff == datetime.timedelta(days=1):
            showtime = f"klukkan {qdatetime.strftime('%H:%M')} í gær"

        else:
            showtime = f"klukkan {qdatetime.strftime('%H:%M %-d. %B')}"

    if curr_prog:
        curr_title, curr_desc = _extract_title_and_desc(curr_prog, station)

        if is_now:
            answer += f"Á {channel_pretty} {showing} {curr_title}. "
        else:
            answer += f"Á {channel_pretty} {showtime} {showing} {curr_title}. "

        if curr_desc != "":
            answer += f"{_clean_desc(curr_desc)}. "

        _, prog_endtime = _get_program_start_end(curr_prog, station)
    else:
        if is_now:
            answer += f"Ekkert er á dagskrá á {channel_pretty} í augnablikinu. "
        else:
            if is_future:
                answer += f"Ekkert verður á dagskrá á {channel_pretty} {showtime}. "
            else:
                answer += f"Ekkert var á dagskrá á {channel_pretty} {showtime}. "

    if next_prog:
        next_title, next_desc = _extract_title_and_desc(next_prog, station)

        answer += f"Næst á dagskrá {channel_pretty} {showing} {next_title}."

        if next_desc != "":
            answer += f" {_clean_desc(next_desc)}."

        if prog_endtime is None:
            prog_endtime, _ = _get_program_start_end(next_prog, station)

    answer = answer.rstrip()

    # TODO: use num utils, years, ordinals, so on
    voice = answer

    return {
        "response": {"answer": answer, "voice": voice},
        "answer": answer,
        "voice": voice,
        "station": station,
        "channel": channel_pretty,
        "expire_time": prog_endtime,
    }


def _get_schedule_answer(result: Result) -> AnswerDict:
    """Generate answer to query about current radio program."""

    channel: str = result.get("channel")
    channel_pretty: str = result.get("channel_pretty")
    station: str = result.get("station")
    is_radio: bool = result.get("type") == "radio"

    now = datetime.datetime.now()

    qdate: datetime.date = result.get("qdate")
    qtime: datetime.time = result.get("qtime")

    if qtime is None:
        qtime = now.time()
    if qdate is None:
        qdate = now.date()

    qdatetime: datetime.datetime = datetime.datetime.combine(qdate, qtime)

    get_next: bool = result.get("get_next", False)

    # Fetch schedule data from API or cache.
    sched: SchedType = _query_schedule_api(channel, station, qdatetime.date())

    if len(sched) == 0:
        if qdatetime.date() != now.date():
            with changedlocale(category="LC_TIME"):
                # TODO: Declension of channel name
                error = f"Ekki tókst að sækja dagskrána {qdatetime.strftime('%-d. %B')} á {channel_pretty}."
        else:
            error = f"Ekki tókst að sækja dagskrána á {channel_pretty}."

        error_ans: AnswerTuple = gen_answer(error)
        voice = error_ans[2]  # TODO: Fix ordinal
        return dict(
            response=cast(Dict[str, Any], error_ans[0]),
            answer=error_ans[1],
            voice=cast(str, voice),
            station=station,
            channel=channel_pretty,
            expire_time=qdatetime,
        )

    curr_prog, next_prog = _get_current_and_next_program(
        sched, station, qdatetime, get_next
    )

    with changedlocale(category="LC_TIME"):
        answ_dict: AnswerDict = _generate_answer(
            curr_prog, next_prog, station, channel_pretty, qdatetime, is_radio
        )
    return answ_dict


def sentence(state: QueryStateDict, result: Result) -> None:
    """Called when sentence processing is complete"""
    q: Query = state["query"]

    if (
        "qtype" in result
        and "channel" in result
        and "channel_pretty" in result
        and "station" in result
    ):
        # Successfully matched a query type
        q.set_qtype(result.qtype)

        try:
            r: AnswerDict = _get_schedule_answer(result)

            q.set_key(f"{r['station']}-{r['channel']}")
            q.set_source(r["station"])
            q.set_beautified_query(q._beautified_query.replace("rúv", "RÚV"))

            q.set_expires(r["expire_time"])
            q.set_answer(r["response"], r["answer"], r["voice"])

        except Exception as e:
            logging.warning(f"Exception while processing TV/radio schedule query: {e}")
            q.set_error(f"E_EXCEPTION: {e}")

    else:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
