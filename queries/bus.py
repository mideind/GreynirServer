"""

    Greynir: Natural language processing for Icelandic

    Bus schedule query module

    Copyright (C) 2023 Miðeind ehf.
    Original author: Vilhjálmur Þorsteinsson

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


    This module implements a processor for queries about bus schedules.
    It also serves as an example of how to plug query grammars into Greynir's
    query subsystem and how to handle the resulting trees.

    The queries supported by the module are as follows:

    * Hvaða stoppistöð er næst mér? (Which bus stop is closest to me?)

    * Hvenær kemur strætó númer tólf? (When does bus number twelve arrive?)

    * Hvaða strætó stoppar á Lækjartorgi? (Which buses stop at Lækjartorg?)

"""

# TODO: Hvar er nálægasta strætóstoppistöð?
# TODO: Hvað er ég lengi í næsta strætóskýli?
# TODO: Hvar stoppar sjöan næst?
# TODO: Fuzzy matching in straeto package should
#       catch N/A/S/V <-> norður/austur/suður/vestur
# TODO: "á" vs. "í" vs. other prepositions before bus stop names
# TODO: If query includes full name of stop,
#       don't pick other, closer, stop with similar name
#       e.g. if query is "... Naustabraut Davíðshaga austur",
#            don't pick "... Naustabraut Davíðshaga vestur"

from typing import Dict, Iterable, Optional, List, Set, Tuple, cast

import re
import random
from threading import Lock
from functools import lru_cache
from datetime import datetime

from reynir import NounPhrase

from queries import AnswerTuple, Query, QueryStateDict
from tree import Result, Node, ParamList
from utility import cap_first
from queries.util import (
    is_plural,
    natlang_seq,
    gen_answer,
    read_grammar_file,
)
from speech.trans import gssml, strip_markup
from settings import Settings
from geo import in_iceland

import straeto

# Today's bus schedule, cached
schedule_today: Optional[straeto.BusSchedule] = None
SCHEDULE_LOCK = Lock()


# Indicate that this module wants to handle parse trees for queries,
# as opposed to simple literal text strings
HANDLE_TREE = True


# Translate slightly wrong words that we allow in the grammar in order to
# make it more resilient
_WRONG_STOP_WORDS = {
    "stoppustöð": "stoppistöð",
    "strætóstoppustöð": "strætóstoppistöð",
    "stoppustuð": "stoppistöð",
    "Stoppustuð": "stoppistöð",
}


# Lemmas of keywords that could indicate that the user is trying to use this module
TOPIC_LEMMAS = [
    "strætó",
    "stoppistöð",
    "biðstöð",
    "stoppustöð",
    "leið",
    "vagn",
    "strætisvagn",
    "ás",
    "tvistur",
    "þristur",
    "fjarki",
    "fimma",
    "sexa",
    "sjöa",
    "átta",
    "nía",
    "tía",
    "ellefa",
    "tólfa",
    "strætóstöð",
    "strætóstoppustöð",
    "strætóstoppistöð",
    "strædo",
    "stræto",
    "seinn",
    "fljótur",
]


def help_text(lemma: str) -> str:
    """Help text to return when query processor is unable to parse a query but
    one of the above lemmas is found in it"""
    return "Ég get svarað ef þú spyrð til dæmis: {0}?".format(
        random.choice(
            (
                "Hvaða stoppistöð er næst mér",
                "Hvar stoppar strætó",
                "Hvenær kemur strætó",
                "Hvenær fer leið fimmtíu og sjö frá Borgarnesi",
                "Hvenær kemur fjarkinn á Hlemm",
                "Hvenær er von á vagni númer fjórtán",
            )
        )
    )


# The grammar nonterminals this module wants to handle
QUERY_NONTERMINALS = {
    "QBusArrivalTime",
    "QBusAnyArrivalTime",
    "QBusNearestStop",
    "QBusWhich",
}

# The context-free grammar for the queries recognized by this plug-in module
GRAMMAR = read_grammar_file("bus")

# The following functions correspond to grammar nonterminals (see
# the context-free grammar above, in GRAMMAR) and are called during
# tree processing (depth-first, i.e. bottom-up navigation).


def QBusNearestStop(node: Node, params: ParamList, result: Result) -> None:
    """Nearest stop query"""
    result.qtype = "NearestStop"
    # No query key in this case
    result.qkey = ""


def QBusStop(node: Node, params: ParamList, result: Result) -> None:
    """Save the word that was used to describe a bus stop"""
    result.stop_word = _WRONG_STOP_WORDS.get(result._nominative, result._nominative)


def QBusStopName(node: Node, params: ParamList, result: Result) -> None:
    """Save the bus stop name"""
    result.stop_name = result._root


def QBusStopThere(node: Node, params: ParamList, result: Result) -> None:
    """A reference to a bus stop mentioned earlier"""
    result.stop_name = "þar"


def QBusStopToThere(node: Node, params: ParamList, result: Result) -> None:
    """A reference to a bus stop mentioned earlier"""
    result.stop_name = "þangað"


def EfLiður(node: Node, params: ParamList, result: Result) -> None:
    """Don't change the case of possessive clauses"""
    result._nominative = result._text


def FsMeðFallstjórn(node: Node, params: ParamList, result: Result) -> None:
    """Don't change the case of prepositional clauses"""
    result._nominative = result._text


def QBusNoun(node: Node, params: ParamList, result: Result) -> None:
    """Save the noun used to refer to a bus"""
    # Use singular, indefinite form
    # Hack: if the QBusNoun is a literal string, the _canonical logic
    # is not able to cast it to nominative case. Do it here by brute force. """
    if result._nominative in ("Vagni", "Vagns"):
        result._nominative = "vagn"
    if result._canonical in ("Vagni", "Vagns"):
        result._canonical = "vagn"
    result.bus_noun = result._canonical


def QBusArrivalTime(node: Node, params: ParamList, result: Result) -> None:
    """Bus arrival time query"""
    # Set the query type
    result.qtype = "ArrivalTime"
    if "bus_number" in result:
        # The bus number has been automatically
        # percolated upwards from a child node (see below).
        # Set the query key
        result.qkey = result.bus_number


def QBusAnyArrivalTime(node: Node, params: ParamList, result: Result) -> None:
    """Bus arrival time query"""
    # Set the query type
    result.qtype = "ArrivalTime"
    # Set the query key to 'Any'
    result.qkey = result.bus_number = "Any"


def QBusWhich(node: Node, params: ParamList, result: Result) -> None:
    """Buses on which routes stop at a given stop"""
    # Set the query type
    result.qtype = "WhichRoute"
    if "stop_name" in result:
        # Set the query key to the name of the bus stop
        result.qkey = result.stop_name


# Translate bus number words to integers

_BUS_WORDS = {
    "ás": 1,
    "tvistur": 2,
    "þristur": 3,
    "fjarki": 4,
    "fimma": 5,
    "sexa": 6,
    "sjöa": 7,
    "átta": 8,
    "nía": 9,
    "tía": 10,
    "ellefa": 11,
    "tólfa": 12,
}


def QBusWord(node: Node, params: ParamList, result: Result) -> None:
    """Handle buses specified in single words,
    such as 'tvisturinn' or 'fimman'"""
    # Retrieve the contained text (in nominative case)
    # and set the bus_name and bus_number attributes,
    # which are then percolated automatically upwards in the tree.
    # We use the ._nominative form of the bus word, converting
    # 'tvistinum' to 'tvisturinn' (retaining the definite article).
    result.bus_name = result._nominative
    # result._canonical is the nominative, singular, indefinite form
    # of the enclosed noun phrase. For example, if the enclosed
    # noun phrase is 'tvistinum', result._canonical returns 'tvistur'.
    result.bus_number = _BUS_WORDS.get(result._canonical, 0)


def QBusNumber(node: Node, params: ParamList, result: Result) -> None:
    """Reflect back the phrase used to specify the bus,
    but in nominative case. Also fetch specified bus number."""
    # 'vagni númer 17' -> 'vagn númer 17'
    # 'leið fimm' -> 'leið fimm'
    result.bus_name = result._nominative

    if "numbers" in result and result.numbers:
        result.bus_number = result.numbers[0]


# End of grammar nonterminal handlers

_BETTER_NAMES = {
    "BSÍ": "Umferðarmiðstöðin",
    "FMOS": "Framhaldsskólinn í Mosfellsbæ",
    "KEF - Airport": "Keflavíkurflugvöllur",
    "KR": "Knattspyrnufélag Reykjavíkur",
    "RÚV": "Útvarpshúsið",
}
_ABBREV_RE = re.compile(r"\b[A-ZÁÐÉÍÓÚÝÞÆÖ]+\b")


def _replace_abbreviations(stop_nf: str, stop_name: str) -> str:
    """
    Replace '... N/A/S/V' with '... norður/austur/suður/vestur'
    and surround other abbreviations with 'spell' GSSML.
    stop_nf is the stop name in nominative case,
    while stop_name can be in another case (e.g. accusative or dative).
    """
    if stop_name.endswith(" N") and straeto.BusStop.named(stop_nf[:-1] + "S"):
        stop_name = stop_name[:-1] + "norður"
    elif stop_name.endswith(" A") and straeto.BusStop.named(stop_nf[:-1] + "V"):
        stop_name = stop_name[:-1] + "austur"
    elif stop_name.endswith(" S") and straeto.BusStop.named(stop_nf[:-1] + "N"):
        stop_name = stop_name[:-1] + "suður"
    elif stop_name.endswith(" V") and straeto.BusStop.named(stop_nf[:-1] + "A"):
        stop_name = stop_name[:-1] + "vestur"
    # Spell out any remaining abbreviations for the speech synthesis engine
    return _ABBREV_RE.sub(lambda m: gssml(m.group(0), type="spell"), stop_name)


def _get_split_symbol(stop: str) -> Optional[str]:
    if " / " in stop:
        return " / "
    if " - " in stop:
        return " - "
    return None


def voicify_stop_name(np: str) -> str:
    """Fix stop name to better suit speech synthesis."""
    np = _BETTER_NAMES.get(np, np)
    return cap_first(_replace_abbreviations(np, np))


@lru_cache(maxsize=None)
def accusative_form(np: str, voice: bool = False) -> str:
    """
    Return accusative case of the stop name,
    optionally expanding abbreviations for speech synthesis.
    """
    orig_stop_name = np
    if voice:
        # Replace with better name before inflecting
        np = _BETTER_NAMES.get(np, np)

    split_symb = _get_split_symbol(np)

    if split_symb is None:
        # Bus stop is single noun phrase
        np = NounPhrase(np).accusative or np
    else:
        # Bus stop consists of two (at least) noun phrases
        # separated by split_symb, inflect them separately
        new_np: List[str] = []
        for n in np.split(split_symb):
            if not n.isupper():
                # Not an all-uppercase abbreviation, try to inflect it
                n = NounPhrase(n).accusative or n
            new_np.append(n)
        np = split_symb.join(new_np)
    if voice:
        np = _replace_abbreviations(orig_stop_name, np)
    return cap_first(np)


@lru_cache(maxsize=None)
def dative_form(np: str, voice: bool = False) -> str:
    """
    Return dative case of the stop name,
    optionally expanding abbreviations for speech synthesis.
    """
    orig_stop_name = np
    if voice:
        np = _BETTER_NAMES.get(np, np)

    split_symb = _get_split_symbol(np)

    if split_symb is None:
        # Bus stop is single noun phrase
        np = NounPhrase(np).dative or np
    else:
        # Bus stop consists of two (at least) noun phrases
        # separated by split_symb, inflect them separately
        new_np: List[str] = []
        for n in np.split(split_symb):
            if not n.isupper():
                # Not an uppercase abbreviation, inflect it
                n = NounPhrase(n).dative or n
            new_np.append(n)
        np = split_symb.join(new_np)
    if voice:
        np = _replace_abbreviations(orig_stop_name, np)
    return cap_first(np)


def voice_distance(d: float) -> str:
    """Convert a distance, given as a float in units of kilometers, to a string
    that can be read aloud in Icelandic starting with 'þangað er' or 'þangað eru'."""
    are = "eru"
    # Distance more than 1 kilometer
    if d >= 1:
        km = round(d, 1)
        vdist = gssml(km, type="float", gender="kk")
        if is_plural(km):
            unit = "kílómetrar"
        else:
            are = "er"
            unit = "kílómetri"
    else:
        # Distance less than 1 km: Round to 10 meters
        m = int(round(d * 1000, -1))
        vdist = gssml(m, type="number", gender="kk")
        unit = "metrar"
    return " ".join(("þangað", are, vdist, unit))


# Hours, minutes, seconds
_HMSTuple = Tuple[int, int, int]


def hms_fmt(hms: _HMSTuple, voice: bool = False) -> str:
    """
    Format a (h, m, s) tuple to a HH:MM string,
    optionally enclosed by <greynir type='time'>
    """
    h, m, s = hms
    if s >= 30:
        # Round upwards
        if s == 30:
            # On a tie, round towards an even minute number
            if m % 2:
                m += 1
        else:
            m += 1
    if m >= 60:
        h += 1
        m -= 60
    if h >= 24:
        h -= 24
    return gssml(f"{h:02}:{m:02}", type="time") if voice else f"{h:02}:{m:02}"


def hms_diff(hms1: _HMSTuple, hms2: _HMSTuple) -> int:
    """Return (hms1 - hms2) in minutes, where both are (h, m, s) tuples"""
    return (hms1[0] - hms2[0]) * 60 + (hms1[1] - hms2[1])


def query_nearest_stop(query: Query, result: Result) -> AnswerTuple:
    """A query for the stop closest to the user"""
    # Retrieve the client location
    location = query.location
    if location is None:
        # No location provided in the query
        answer = "Staðsetning óþekkt."
        voice_answer = "Ég veit ekki hvar þú ert."
        return dict(answer=answer), answer, voice_answer

    if not in_iceland(location):
        # User's location is not in Iceland
        return gen_answer("Ég þekki ekki strætósamgöngur utan Íslands.")

    # Get the stop closest to the user
    stop = straeto.BusStop.closest_to(location)
    if stop is None:
        return gen_answer("Ég finn enga stoppistöð nálægt þér.")

    answer = stop.name + "."
    # Use the same word for the bus stop as in the query
    stop_word = result.get("stop_word", "stoppistöð")
    voice_answer = (
        f"Næsta {stop_word} er {voicify_stop_name(stop.name)}; "
        f"{voice_distance(straeto.distance(location, stop.location))}."
    )
    # Store a location coordinate and a bus stop name in the context
    query.set_context({"location": stop.location, "bus_stop": stop.name})
    return dict(answer=answer), answer, voice_answer


def query_arrival_time(query: Query, result: Result) -> AnswerTuple:
    """Answers a query for the arrival time of a bus"""

    # Examples:
    # 'Hvenær kemur strætó númer 12?'
    # 'Hvenær kemur leið sautján á Hlemm?'
    # 'Hvenær kemur næsti strætó í Einarsnes?'

    # Retrieve the client location, if available, and the name
    # of the bus stop, if given
    stop_name: Optional[str] = result.get("stop_name")
    stop: Optional[straeto.BusStop] = None
    location: Optional[Tuple[float, float]] = None

    if stop_name in {"þar", "þangað"}:
        # Referring to a bus stop mentioned earlier
        ctx = query.fetch_context()
        if ctx and "bus_stop" in ctx:
            stop_name = cast(str, ctx["bus_stop"])
        else:
            return gen_answer("Ég veit ekki við hvaða stað þú átt.")

    if not stop_name:
        location = query.location
        if location is None:
            answer = "Staðsetning óþekkt."
            voice_answer = "Ég veit ekki hvar þú ert."
            return dict(answer=answer), answer, voice_answer

    # Obtain today's bus schedule
    global schedule_today
    with SCHEDULE_LOCK:
        if schedule_today is None or not schedule_today.is_valid_today:
            # We don't have today's schedule: create it
            schedule_today = straeto.BusSchedule()

    # Obtain the set of stops that the user may be referring to
    stops: List[straeto.BusStop] = []
    if stop_name:
        stops = straeto.BusStop.named(stop_name, fuzzy=True)
        if query.location is not None:
            # If we know the location of the client, sort the
            # list of potential stops by proximity to the client
            straeto.BusStop.sort_by_proximity(stops, query.location)
    else:
        # Obtain the closest stops (at least within 400 meters radius)
        assert location is not None
        stops = straeto.BusStop.closest_to_list(location, n=2, within_radius=0.4)
        if not stops:
            # This will fetch the single closest stop, regardless of distance
            stops = [cast(straeto.BusStop, straeto.BusStop.closest_to(location))]

    # Handle the case where no bus number was specified (i.e. is 'Any')
    if result.bus_number == "Any" and stops:
        # Accumulate all bus routes that stop on the requested stop(s)
        stops_canonical: Set[str] = set()
        numbers: Set[str] = set()
        for stop in stops:
            for rid in stop.visits.keys():
                route = straeto.BusRoute.lookup(rid)
                if route is not None:
                    numbers.add(route.number)
                    stops_canonical.add(stop.name)

        if len(numbers) != 1:
            # More than one route possible: ask user to clarify
            route_seq = natlang_seq(sorted(numbers, key=lambda n: int(n)))
            # "Einarsnesi eða Einarsnesi/Bauganesi"
            stops_list = natlang_seq([dative_form(s) for s in sorted(stops_canonical)])
            va_stops_list = " eða ".join(
                [dative_form(s, voice=True) for s in sorted(stops_canonical)]
            )
            answer = f"Leiðir {route_seq} stoppa á {stops_list}. Spurðu um eina þeirra."
            voice_answer = (
                f"Leiðir {gssml(route_seq, type='numbers')}"
                f" stoppa á {va_stops_list}."
                " Spurðu um eina þeirra."
            )
            return dict(answer=answer), answer, voice_answer

        # Only one route: use it as the query subject
        bus_number = numbers.pop()
        bus_name = f"Strætó númer {bus_number}"
        va = [f"Strætó númer {gssml(bus_number, type='number')}"]
    else:
        bus_number = result.get("bus_number", 0)
        bus_name = cap_first(result.bus_name) if "bus_name" in result else "Óþekkt"
        va = [gssml(bus_name, type="numbers")]
        if bus_number < 0:
            # Negative bus numbers don't exist
            answer = f"{bus_name} er ekki til."
            voice_answer = f"{va[0]} er ekki til."
            return dict(answer=answer), answer, voice_answer

    # Prepare results
    a: List[str] = []
    arrivals: List[Tuple[str, List[_HMSTuple]]] = []
    arrivals_dict: Dict[str, List[_HMSTuple]] = {}
    arrives = False
    route_number = str(bus_number)

    # First, check the closest stop
    # !!! TODO: Prepare a different area_priority parameter depending
    # !!! on the user's location; i.e. if she is in Eastern Iceland,
    # !!! route '1' would mean 'AL.1' instead of 'ST.1'.
    if stops:
        for stop in stops:
            arrivals_dict, arrives = schedule_today.arrivals(route_number, stop)
            if arrives:
                break
        arrivals = list(arrivals_dict.items())
        assert stop is not None
        a = [f"Á {accusative_form(stop.name)} í átt að"]

    if arrivals:
        # Get a predicted arrival time for each direction from the
        # real-time bus location server
        assert stop is not None
        prediction = schedule_today.predicted_arrival(route_number, stop)
        now = datetime.utcnow()
        hms_now = (now.hour, now.minute + (now.second // 30), 0)
        first = True

        # We may get three (or more) arrivals if there are more than two
        # endpoints for the bus route in the schedule. To minimize
        # confusion, we only include the two endpoints that have the
        # earliest arrival times and skip any additional ones.
        arrivals = sorted(arrivals, key=lambda t: t[1][0])[:2]

        for direction, times in arrivals:
            if not first:
                va.append(", og")
                a.append(". Í átt að")
            va.append(f"í átt að {dative_form(direction, voice=True)}")
            a.append(dative_form(direction))
            deviation: str = ""
            if prediction and direction in prediction:
                # We have a predicted arrival time
                hms_sched = times[0]
                hms_pred = prediction[direction][0]
                # Calculate the difference between the prediction and
                # now, and skip it if it is 1 minute or less
                diff = hms_diff(hms_pred, hms_now)
                if abs(diff) <= 1:
                    deviation = ", en er að fara núna"
                else:
                    # Calculate the difference in minutes between the
                    # schedule and the prediction, with a positive number
                    # indicating a delay
                    diff = hms_diff(hms_pred, hms_sched)
                    if diff < -1:
                        # More than one minute ahead of schedule
                        if diff < -5:
                            # More than 5 minutes ahead
                            deviation = (
                                ", en kemur sennilega fyrr, "
                                f"eða {hms_fmt(hms_pred, voice=True)}"
                            )
                        else:
                            # Two to five minutes ahead
                            deviation = f", en er {gssml(-diff, type='number', gender='kvk', case='þgf')} mínútum á undan áætlun"

                    elif diff >= 3:
                        # 3 minutes or more behind schedule
                        deviation = (
                            ", en kemur sennilega ekki fyrr "
                            f"en {hms_fmt(hms_pred, voice=True)}"
                        )
            if first:
                assert stop is not None
                if deviation:
                    va.append("á að koma á")
                else:
                    va.append("kemur á")
                va.append(accusative_form(stop.name, voice=True))
            va.append("klukkan")
            a.append("klukkan")
            if len(times) == 1 or (
                len(times) > 1 and hms_diff(times[0], hms_now) >= 10
            ):
                # Either we have only one arrival time, or the next arrival is
                # at least 10 minutes away: only pronounce one time
                hms = times[0]
                time_text = hms_fmt(hms, voice=True)
            else:
                # Return two or more times
                time_text = " og ".join(hms_fmt(hms, voice=True) for hms in times)
            va.append(time_text)
            a.append(strip_markup(time_text))  # Remove greynir SSML tags
            if deviation:
                va.append(deviation)
                a.append(strip_markup(deviation))
            first = False

    elif arrives:
        # The given bus has already completed its scheduled halts at this stop today
        assert stops
        stop = stops[0]
        va.append(f"kemur ekki aftur á {accusative_form(stop.name, voice=True)} í dag")
        a = [bus_name, "kemur ekki aftur á", accusative_form(stop.name), "í dag"]

    elif stops:
        # The given bus doesn't stop at all at either of the two closest stops
        stop = stops[0]
        va.append(f"stoppar ekki á {dative_form(stop.name, voice=True)}")
        a = [bus_name, "stoppar ekki á", dative_form(stop.name)]

    else:
        # The bus stop name is not recognized
        assert stop_name is not None
        va = a = [f"{stop_name.capitalize()} er ekki biðstöð"]

    if stop is not None:
        # Store a location coordinate and a bus stop name in the context
        query.set_context({"location": stop.location, "bus_stop": stop.name})

    # Hack: Since we know that the query string contains no uppercase words,
    # adjust it accordingly; otherwise it may erroneously contain capitalized
    # words such as Vagn and Leið.
    bq = query.beautified_query
    for t in (
        ("Vagn ", "vagn "),
        ("Vagni ", "vagni "),
        ("Vagns ", "vagns "),
        ("Leið ", "leið "),
        ("Leiðar ", "leiðar "),
    ):
        bq = bq.replace(*t)
    query.set_beautified_query(bq)

    def assemble(x: Iterable[str]) -> str:
        """Intelligently join answer string components."""
        s = " ".join(x) + "."
        s = re.sub(r"\s\s+", r" ", s)  # Shorten repeated whitespace
        s = re.sub(r"\s([.,])", r"\1", s)  # Whitespace before comma/period
        s = re.sub(r"([.,])+", r"\1", s)  # Multiple commas/periods
        return s

    answer = assemble(a)
    voice_answer = assemble(va)
    return dict(answer=answer), answer, voice_answer


def query_which_route(query: Query, result: Result):
    """Which routes stop at a given bus stop"""
    user_stop_name = cast(str, result.stop_name)  # 'Einarsnes', 'Fiskislóð'...

    if user_stop_name in {"þar", "þangað"}:
        # Referring to a bus stop mentioned earlier
        ctx = query.fetch_context()
        if ctx and "bus_stop" in ctx:
            user_stop_name = cast(str, ctx["bus_stop"])
            result.qkey = user_stop_name
        else:
            return gen_answer("Ég veit ekki við hvaða stað þú átt.")

    bus_noun = result.bus_noun  # 'strætó', 'vagn', 'leið'...
    stops = straeto.BusStop.named(user_stop_name, fuzzy=True)
    if not stops:
        answer = f"{user_stop_name} þekkist ekki."
        voice_answer = f"Ég þekki ekki biðstöðina {user_stop_name}."
    else:
        routes: Set[str] = set()
        if query.location:
            straeto.BusStop.sort_by_proximity(stops, query.location)
        stop = stops[0]
        for route_id in stop.visits.keys():
            route = straeto.BusRoute.lookup(route_id)
            if route is not None:
                routes.add(route.number)
        route_seq = natlang_seq(sorted(routes))
        stop_verb = "stoppa" if is_plural(len(routes)) else "stoppar"
        answer = f"{bus_noun} númer {route_seq} {stop_verb} á {dative_form(stop.name)}."
        voice_answer = (
            f"{bus_noun} númer {gssml(route_seq, type='numbers')} "
            f"{stop_verb} á {dative_form(stop.name, voice=True)}."
        )
        query.set_key(stop.name)
        # Store a location coordinate and a bus stop name in the context
        query.set_context({"location": stop.location, "bus_stop": stop.name})

    return dict(answer=answer), cap_first(answer), cap_first(voice_answer)


# Dispatcher for the various query types implemented in this module
_QFUNC = {
    "ArrivalTime": query_arrival_time,
    "NearestStop": query_nearest_stop,
    "WhichRoute": query_which_route,
}

# The following function is called after processing the parse
# tree for a query sentence that is handled in this module


def sentence(state: QueryStateDict, result: Result) -> None:
    """Called when sentence processing is complete"""
    q: Query = state["query"]
    if "qtype" in result:
        # Successfully matched a query type
        q.set_qtype(result.qtype)
        q.set_key(result.qkey)
        # Select a query function and execute it
        qfunc = _QFUNC.get(result.qtype)
        try:
            assert qfunc is not None, "qfunc is None"
            q.set_answer(*qfunc(q, result))
        except Exception as e:
            if Settings.DEBUG:
                raise
            q.set_error(f"E_EXCEPTION: {e}")
    else:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
