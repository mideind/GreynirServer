"""

    Reynir: Natural language processing for Icelandic

    Bus schedule query module

    Copyright (C) 2019 Miðeind ehf.
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
    It also serves as an example of how to plug query grammars into Reynir's
    query subsystem and how to handle the resulting trees.

"""

import re
from threading import Lock
from functools import lru_cache

import query
from settings import Settings
from reynir.bindb import BIN_Db

import straeto


# Today's bus schedule, cached
SCHEDULE_TODAY = None
SCHEDULE_LOCK = Lock()

# Indicate that this module wants to handle parse trees for queries,
# as opposed to simple literal text strings
HANDLE_TREE = True

# Translate slightly wrong words that we allow in the grammar in order to
# make it more resilient
_WRONG_STOP_WORDS = {
    "stoppustuð": "stoppistöð",
    "Stoppustuð": "stoppistöð",
}

# The context-free grammar for the queries recognized by this plug-in module
GRAMMAR = """

# ----------------------------------------------
#
# Query grammar for bus-related queries
#
# ----------------------------------------------

# A plug-in query grammar always starts with the following,
# adding one or more query productions to the Query nonterminal

Query →
    QBusArrivalTime | QBusNearestStop

# By convention, names of nonterminals in query grammars should
# start with an uppercase Q

QBusNearestStop →

    "hvaða" QBusStop_kvk "er" QBusStopTail_kvk '?'?
    | "hvaða" QBusStop_hk "er" QBusStopTail_hk '?'?
    | "hver" "er" "næsta" QBusStop_kvk '?'?
    # Leyfa 'hvað er næsta stoppistöð' (algeng misheyrn)
    | "hvað" "er" "næsta" QBusStop_kvk '?'?
    | "hvert" "er" "næsta" QBusStop_hk '?'?
    | "hvar" "stoppar" "strætó" '?'?

$score(+32) QBusNearestStop

QBusStop_kvk →
    "stoppistöð" | "stoppustöð" | "stoppustuð" | "Stoppustuð" | "biðstöð" | "strætóstöð"
    | "strætóstoppistöð" | "strætóstoppustöð"

QBusStop_hk →
    "strætóstopp" | "stopp"

QBusStopTail_kvk →
    "næst" "mér"? | "nálægust" | "styst" "í" "burtu"

QBusStopTail_hk →
    "næst" "mér"? | "nálægast" | "styst" "í" "burtu"

QBusArrivalTime →

    # 'Hvenær kemur ásinn/sexan/tían/strætó númer tvö?'
    "hvenær" "kemur" QBus_nf '?'?

    # 'Hvenær er von á fimmunni / vagni númer sex?'
    # Note that "Von" is also a person name, but
    # the double quote literal form is not case-sensitive
    # and will match person and entity names as well,
    # even if (auto-)capitalized
    | "hvenær" "er" "von" "á" QBus_þgf '?'?

    # 'Hvenær má búast við leið þrettán?
    | "hvenær" "má" "búast" "við" QBus_þgf '?'?

$score(+32) QBusArrivalTime

# We can specify a bus in different ways, which may require
# the bus identifier to be in different cases

QBus/fall →
    QBusWord/fall | QBusNumber/fall

QBusWord/fall →
    'ás:kk'_et_gr/fall
    | 'tvistur:kk'_et_gr/fall
    | 'þristur:kk'_et_gr/fall
    | 'fjarki:kk'_et_gr/fall
    | 'fimma:kvk'_et_gr/fall
    | 'sexa:kvk'_et_gr/fall
    | 'sjöa:kvk'_et_gr/fall
    | 'átta:kvk'_et_gr/fall
    | 'nía:kvk'_et_gr/fall
    | 'tía:kvk'_et_gr/fall
    | 'tólfa:kvk'_et_gr/fall

QBusNumber_nf →
    "leið" 'númer:hk'_et_nf? QBusNumberWord
QBusNumber_þf →
    "leið" 'númer:hk'_et_nf? QBusNumberWord
QBusNumber_þgf →
    "leið" 'númer:hk'_et_nf? QBusNumberWord
QBusNumber_ef →
    "leiðar" 'númer:hk'_et_nf? QBusNumberWord

QBusNumber/fall →
    'strætó:kk'_et/fall 'númer:hk'_et_nf QBusNumberWord

    | 'vagn:kk'_et/fall 'númer:hk'_et_nf QBusNumberWord

    # We also need to handle the person name 'Vagn',
    # in case the query comes in with an uppercase 'V'.
    # A lemma literal, within single quotes, will match
    # person and entity names in the indicated case, if given,
    # or in any case if no case variant is given. 
    | 'Vagn'/fall 'númer:hk'_et_nf QBusNumberWord

QBusNumberWord →

    # to is a declinable number word ('tveir/tvo/tveim/tveggja')
    # töl is an undeclinable number word ('sautján')
    # tala is a number ('17')
    "eitt" | to_nf_ft_hk | töl | tala

"""


# The following functions correspond to grammar nonterminals (see
# the context-free grammar above, in GRAMMAR) and are called during
# tree processing (depth-first, i.e. bottom-up navigation).


def QBusNearestStop(node, params, result):
    """ Nearest stop query """
    result.qtype = "NearestStop"
    # No query key in this case
    result.qkey = ""


def QBusStop(node, params, result):
    """ Save the word that was used to describe a bus stop """
    result.stop_word = _WRONG_STOP_WORDS.get(result._nominative, result._nominative)


def QBusArrivalTime(node, params, result):
    """ Bus arrival time query """
    # Set the query type
    result.qtype = "ArrivalTime"
    if "bus_number" in result:
        # The bus number has been automatically
        # percolated upwards from a child node (see below).
        # Set the query key
        result.qkey = result.bus_number


def QBus(node, params, result):
    pass


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
    "tólfa": 12,
    "einn": 1,
    "tveir": 2,
    "þrír": 3,
    "fjórir": 4,
    "fimm": 5,
    "sex": 6,
    "sjö": 7,
    "níu": 9,
    "tíu": 10,
    "ellefu": 11,
    "tólf": 12,
    "þrettán": 13,
    "fjórtán": 14,
    "fimmtán": 15,
    "sextán": 16,
    "sautján": 17,
    "átján": 18,
    "nítján": 19,
    "tuttugu": 20,
    "þrjátíu": 30,
    "fjörutíu": 40,
    "fimmtíu": 50,
    "sextíu": 60,
    "sjötíu": 70,
    "áttatíu": 80,
    "níutíu": 90,
}


def QBusWord(node, params, result):
    """ Handle buses specified in single words,
        such as 'tvisturinn' or 'fimman' """
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


def QBusNumber(node, params, result):
    """ Reflect back the phrase used to specify the bus,
        but in nominative case. """
    # 'vagni númer 17' -> 'vagn númer 17'
    # 'leið fimm' -> 'leið fimm'
    result.bus_name = result._nominative


def QBusNumberWord(node, params, result):
    """ Obtain the bus number as an integer from word or number terminals. """
    # Use the nominative, singular, indefinite form
    number = result._canonical
    try:
        # Handle digits ("17")
        result.bus_number = int(number)
    except ValueError:
        # Handle number words ("sautján")
        result.bus_number = _BUS_WORDS.get(number, 0)
    except Exception as e:
        print("Unexpected exception: {0}".format(e))
        raise


# End of grammar nonterminal handlers


def _meaning_filter_func(mm):
    """ Filter word meanings when casting bus stop names
        to cases other than nominative """
    # Handle secondary and ternary forms (ÞFFT2, ÞGFET3...)
    # This is a bit hacky, but necessary for optimal results.
    # For place names, ÞGFET2 seems often to be a better choice
    # than ÞGFET, since it has a trailing -i
    # (for instance 'Skjólvangi' instead of 'Skjólvang')
    mm2 = [m for m in mm if "ÞGF" in m.beyging and "2" in m.beyging]
    if not mm2:
        # Did not find the preferred ÞGF2, so we go for the
        # normal form and cut away the secondary and ternary ones
        mm2 = [m for m in mm if "2" not in m.beyging and "3" not in m.beyging]
    return mm2 or mm


@lru_cache(maxsize=None)
def to_accusative(np):
    """ Return the noun phrase after casting it from nominative to accusative case """
    return query.to_accusative(np, meaning_filter_func=_meaning_filter_func)


@lru_cache(maxsize=None)
def to_dative(np):
    """ Return the noun phrase after casting it from nominative to dative case """
    return query.to_dative(np, meaning_filter_func=_meaning_filter_func)


def voice_distance(d):
    """ Convert a distance, given as a float in units of kilometers, to a string
        that can be read aloud in Icelandic """
    # Convert to 100 meter integer units
    km1dec = int(d * 100 + 5) // 10
    if km1dec >= 10:
        # One kilometer or longer
        if km1dec == 10:
            return "einn kílómetri"
        if km1dec % 10 == 1:
            # 3,1 kílómetri
            return "{0},{1} kílómetri".format(km1dec // 10, km1dec % 10)
        # 5,6 kílómetrar
        return "{0},{1} kílómetrar".format(km1dec // 10, km1dec % 10)
    # Distance less than 1 km: Round to 10 meters
    m = int(d * 1000 + 5) // 10
    return "{0}0 metrar".format(m)


def query_nearest_stop(query, session, result):
    """ A query for the stop closest to the user """
    # Retrieve the client location
    location = query.location
    if location is None:
        # No location provided in the query
        answer = "Staðsetning óþekkt"
        response = dict(answer=answer)
        voice_answer = "Ég veit ekki hvar þú ert."
        return response, answer, voice_answer
    # Get the stop closest to the user
    stop = straeto.BusStop.closest_to(location)
    va = [
        "Næsta",
        # Use the same word for the bus stop as in the query
        result.stop_word,
        "er", stop.name + ";",
        "þangað", "eru",
        voice_distance(straeto.distance(location, stop.location)),
    ]
    voice_answer = answer = " ".join(va) + "."
    response = dict(answer=voice_answer)
    return response, answer, voice_answer


def query_arrival_time(query, session, result):
    """ A query for a bus arrival time """
    # Retrieve the client location
    location = query.location
    if location is None:
        answer = "Staðsetning óþekkt"
        response = dict(answer=answer)
        voice_answer = "Ég veit ekki hvar þú ert."
        return response, answer, voice_answer
    bus_number = result.bus_number
    bus_name = result.bus_name
    # Obtain today's bus schedule
    global SCHEDULE_TODAY
    with SCHEDULE_LOCK:
        if SCHEDULE_TODAY is None or not SCHEDULE_TODAY.is_valid_today:
            # We don't have today's schedule: create it
            SCHEDULE_TODAY = straeto.BusSchedule()
    stop = straeto.BusStop.closest_to(location)
    va = [bus_name[0].upper() + bus_name[1:]]
    arrivals = SCHEDULE_TODAY.arrivals(str(bus_number), stop.name).items()
    if arrivals:
        first = True
        for direction, times in arrivals:
            if not first:
                va.append("og")
            va.extend(["í átt að", to_dative(direction)])
            if first:
                va.extend(["kemur", "næst", "á", to_accusative(stop.name), "klukkan"])
            else:
                va.append("klukkan")
            va.append(" og ".join("{0:02}:{1:02}".format(hms[0], hms[1]) for hms in times))
            first = False
    else:
        # The given bus doesn't stop there
        va.extend(["stoppar", "ekki", "á", to_dative(stop.name)])
    voice_answer = answer = " ".join(va) + "."
    response = dict(answer=voice_answer)
    return response, answer, voice_answer


# Dispatcher for the various query types implemented in this module
_QFUNC = {
    "ArrivalTime": query_arrival_time,
    "NearestStop": query_nearest_stop,
}

# The following function is called after processing the parse
# tree for a query sentence that is handled in this module

def sentence(state, result):
    """ Called when sentence processing is complete """
    q = state["query"]
    if "qtype" in result:
        # Successfully matched a query type
        q.set_qtype(result.qtype)
        q.set_key(result.qkey)
        # SQLAlchemy session, if required
        session = state["session"]
        # Select a query function and exceute it
        qfunc = _QFUNC.get(result.qtype)
        if qfunc is None:
            # Something weird going on - should not happen
            answer = result.qtype + ": " + result.qkey
            q.set_answer(dict(answer=answer), answer)
        else:
            try:
                answer = None
                voice_answer = None
                response = qfunc(q, session, result)
                if isinstance(response, tuple):
                    # We have both a normal and a voice answer
                    response, answer, voice_answer = response
                q.set_answer(response, answer, voice_answer)
            except AssertionError:
                raise
            except Exception as e:
                if Settings.DEBUG:
                    raise
                q.set_error("E_EXCEPTION: {0}".format(e))
    else:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
