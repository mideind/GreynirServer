"""

    Greynir: Natural language processing for Icelandic

    Bus schedule query module

    Copyright (C) 2021 Miðeind ehf.
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

from typing import Optional, List, Tuple, Union, cast

from threading import Lock
from functools import lru_cache
from datetime import datetime
import random

import query
from query import AnswerTuple, Query, ResponseType, Session
from tree import Result
from queries import natlang_seq, numbers_to_neutral, cap_first, gen_answer
from settings import Settings
from reynir import correct_spaces
from geo import in_iceland

import straeto  # type: ignore  # TODO


# Today's bus schedule, cached
SCHEDULE_TODAY: Optional[straeto.BusSchedule] = None
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
    """Help text to return when query.py is unable to parse a query but
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
GRAMMAR = """

# ----------------------------------------------
#
# Query grammar for bus-related queries
#
# ----------------------------------------------

/þfþgf = þf þgf

# A plug-in query grammar always starts with the following,
# adding one or more query productions to the Query nonterminal

Query →
    QBusArrivalTime | QBusAnyArrivalTime | QBusNearestStop | QBusWhich

# By convention, names of nonterminals in query grammars should
# start with an uppercase Q

QBusNearestStop →

    "hvaða" QBusStop_kvk QBusVarEr QBusStopTail_kvk '?'?
    | "hvaða" QBusStop_hk QBusVarEr QBusStopTail_hk '?'?

    | "hvar" "er" "næsta"? QBusStop_kvk '?'?
    | "hver" "er" "næsta" QBusStop_kvk '?'?
    # Leyfa 'hvað er næsta stoppistöð' (algeng misheyrn)
    | "hvað" "er" "næsta" QBusStop_kvk '?'?

    | "hvar" "er" "næsta"? QBusStop_hk '?'?
    | "hvert" "er" "næsta" QBusStop_hk '?'?
    | "hvað" "er" "næsta" QBusStop_hk '?'?
    # Leyfa 'hver er næsta strætóstopp' (algeng misheyrn)
    | "hver" "er" "næsta" QBusStop_hk '?'?

    | "hvar" "stoppar" "strætó" '?'?

$score(+32) QBusNearestStop

QBusVarEr → "er" | "var"

QBusStop_kvk →
    "stoppistöð" "strætó"? | "stoppustöð" "strætó"? | "stoppustuð" "strætó"?
    | "biðstöð" "strætó"? | "strætóstöð"
    | "strætóstoppistöð" | "strætóstoppustöð"

QBusStop_hk →
    "strætóstopp" | "stopp" | "strætóskýli"

QBusStopTail →
    "næst" "mér"? | "styst" "í" "burtu" | "nálægt" "mér"?

QBusStopTail_kvk →
    QBusStopTail | "nálægust"

QBusStopTail_hk →
    QBusStopTail | "nálægast"

QBusNoun/fall/tala →
    'strætó:kk'/tala/fall
    | 'leið:kvk'/tala/fall
    | 'vagn:kk'/tala/fall
    | 'strætisvagn:kk'/tala/fall
    | "strædo" | "stræto"

# Hack to also match Vagn as a person name
# (the lemma terminal 'vagn:kk', used above, does not match person names)

QBusNoun_nf_et → 'Vagn'_nf_kk
QBusNoun_þf_et → 'Vagn'_þf_kk
QBusNoun_þgf_et → 'Vagn'_þgf_kk
QBusNoun_ef_et → 'Vagn'_ef_kk

$tag(keep) QBusNoun/fall/tala

QBusNounSingular_nf →
    QBusNoun_nf_et

QBusNounSingular_þf →
    QBusNoun_þf_et

QBusNounSingular_þgf →
    QBusNoun_þgf_et

QBusNounSingular_ef →
    QBusNoun_ef_et

QBusWhich →
    # 'Hvaða strætó stoppar þar/í Einarsnesi'?
    # 'Hvaða strætisvagnar stoppa þar/á Lækjartorgi'?
    "hvaða" QBusNoun_nf/tala QBusWhichTail/tala '?'?

$score(+32) QBusWhich

QBusWhichTail/tala →
    QBusWhichTailCorrect/tala
    | QBusWhichTailIncorrect/tala

QBusWhichTailCorrect/tala →
    'stoppa:so'_p3_gm_fh_nt/tala "í" QBusStopName_þgf
    | 'stoppa:so'_p3_gm_fh_nt/tala "á" QBusStopName_þgf
    | 'stoppa:so'_p3_gm_fh_nt/tala QBusStopThere

    | 'stöðva:so'_p3_gm_fh_nt/tala "í" QBusStopName_þgf
    | 'stöðva:so'_p3_gm_fh_nt/tala "á" QBusStopName_þgf
    | 'stöðva:so'_p3_gm_fh_nt/tala QBusStopThere

    | 'aka:so'_p3_gm_fh_nt/tala QBusAtStopCorrect_þf
    | 'aka:so'_p3_gm_fh_nt/tala QBusStopToThere

    | 'koma:so'_p3_gm_fh_nt/tala "á" QBusStopName_þf
    | 'koma:so'_p3_gm_fh_nt/tala "í" QBusStopName_þf
    | 'koma:so'_p3_gm_fh_nt/tala "til" QBusStopName_ef
    | 'koma:so'_p3_gm_fh_nt/tala QBusStopToThere

    | 'fara:so'_p3_gm_fh_nt/tala QBusAtStopCorrect_þf
    | 'fara:so'_p3_gm_fh_nt/tala QBusStopToThere

# It seems to be necessary to allow the nominal case
# also, because the Google ASR language model doesn't always
# include all cases for road names (such as 'Fríkirkjuveg')

QBusWhichTailIncorrect/tala →
    'stoppa:so'_p3_gm_fh_nt/tala "í" QBusStopName_nf
    | 'stoppa:so'_p3_gm_fh_nt/tala "á" QBusStopName_nf
    | 'stöðva:so'_p3_gm_fh_nt/tala "í" QBusStopName_nf
    | 'stöðva:so'_p3_gm_fh_nt/tala "á" QBusStopName_nf
    | 'aka:so'_p3_gm_fh_nt/tala "í" QBusStopName_nf
    | 'aka:so'_p3_gm_fh_nt/tala "á" QBusStopName_nf
    | 'aka:so'_p3_gm_fh_nt/tala "til" QBusStopName_nf
    | 'aka:so'_p3_gm_fh_nt/tala "frá" QBusStopName_nf
    | 'koma:so'_p3_gm_fh_nt/tala "á" QBusStopName_nf
    | 'koma:so'_p3_gm_fh_nt/tala "í" QBusStopName_nf
    | 'koma:so'_p3_gm_fh_nt/tala "til" QBusStopName_nf
    | 'fara:so'_p3_gm_fh_nt/tala "í" QBusStopName_nf
    | 'fara:so'_p3_gm_fh_nt/tala "á" QBusStopName_nf
    | 'fara:so'_p3_gm_fh_nt/tala "frá" QBusStopName_nf
    | 'fara:so'_p3_gm_fh_nt/tala "til" QBusStopName_nf

# Prefer the correct forms
$score(-20) QBusWhichTailIncorrect/tala

QBusStopThere →
    "þar"

QBusStopToThere →
    "þangað"

QBusStopName/fall →
    # A bus stop name can consist of two noun phrases,
    # such as 'Þórunnarstræti sjúkrahús'
    Nl/fall Nl/fall?

$score(+1) QBusStopName/fall

# Bus stops with prepositions denoting movement, taking an accusative argument:
# '[kemur] á Hlemm / þangað'
QBusAtStop_þf →
    QBusAtStopCorrect_þf | QBusAtStopIncorrect_þf | QBusStopToThere

# Bus stops with prepositions denoting placement, taking a dative argument:
# '[stoppar] á Hlemmi / þar'
QBusAtStop_þgf →
    QBusAtStopCorrect_þgf | QBusAtStopIncorrect_þgf | QBusStopThere

# Movement prepositions
QBusAtStopCorrect_þf →
    "í" QBusStopName_þf
    | "á" QBusStopName_þf
    | "frá" QBusStopName_þgf
    | "að" QBusStopName_þgf
    | "til" QBusStopName_ef

# Placement prepositions
QBusAtStopCorrect_þgf →
    "í" QBusStopName_þgf
    | "á" QBusStopName_þgf
    | "við" QBusStopName_þf
    | "hjá" QBusStopName_þgf
    | "frá" QBusStopName_þgf
    | "að" QBusStopName_þgf
    | "til" QBusStopName_ef

QBusAtStopIncorrect_þf →
    "í" QBusStopName_nf
    | "í" QBusStopName_þgf
    | "á" QBusStopName_nf
    | "á" QBusStopName_þgf
    | "frá" QBusStopName_nf
    | "til" QBusStopName_nf

QBusAtStopIncorrect_þgf →
    "í" QBusStopName_nf
    | "í" QBusStopName_þf
    | "á" QBusStopName_nf
    | "á" QBusStopName_þf
    | "frá" QBusStopName_nf
    | "til" QBusStopName_nf

# Prefer the correct forms
$score(-20) QBusAtStopIncorrect/þfþgf

QBusWhen → "hvenær" | "klukkan" "hvað"

QBusArrivalTime →

    # 'Hvenær kemur/fer/stoppar ásinn/sexan/tían/strætó númer tvö [næst] [á Hlemmi]?'
    QBusWhen QBusArrivalVerb/þfþgf QBus_nf "næst"? QBusAtStop/þfþgf? '?'?

    # 'Hvenær er [næst] von á fimmunni / vagni númer sex?'
    | QBusWhen "er" "næst"? "von" "á" QBus_þgf QBusAtStop_þf? '?'?

    # 'Hvenær má [næst] búast við leið þrettán?'
    | QBusWhen "má" "næst"? "búast" "við" QBus_þgf QBusAtStop_þf? '?'?

QBusAnyArrivalTime →
    # 'Hvenær kemur/fer/stoppar [næsti] strætó [á Hlemmi]?'
    QBusWhen QBusArrivalVerb/þfþgf "næsti"? QBusNounSingular_nf QBusAtStop/þfþgf? '?'?
    # 'Hvað er langt í [næsta] strætó [á Hlemm / á Hlemmi]?'
    | "hvað" "er" "langt" "í" "næsta"? QBusNounSingular_þf QBusAtStop/þfþgf? '?'?
    # 'Hvenær er von á [næsta] strætó [á Hlemm]?'
    | QBusWhen "er" "von" "á" "næsta"? QBusNounSingular_þgf QBusAtStop_þf? '?'?

QBusArrivalVerb → QBusArrivalVerb/þfþgf

# Movement: verbs control prepositions in accusative case
QBusArrivalVerb_þf → "kemur" | "fer"
# Placement: verbs control prepositions in dative case
QBusArrivalVerb_þgf → "stoppar" | "stöðvar"

$score(+32) QBusArrivalTime
$score(+16) QBusAnyArrivalTime

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
    | 'ellefa:kvk'_et_gr/fall
    | 'tólfa:kvk'_et_gr/fall

QBusNumber/fall →
    QBusNounSingular/fall QBusNr? QBusNumberWord

QBusNr → 'númer:hk'_et_nf | "nr"

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


def QBusStopName(node, params, result):
    """ Save the bus stop name """
    result.stop_name = result._nominative


def QBusStopThere(node, params, result):
    """ A reference to a bus stop mentioned earlier """
    result.stop_name = "þar"


def QBusStopToThere(node, params, result):
    """ A reference to a bus stop mentioned earlier """
    result.stop_name = "þangað"


def EfLiður(node, params, result):
    """ Don't change the case of possessive clauses """
    result._nominative = result._text


def FsMeðFallstjórn(node, params, result):
    """ Don't change the case of prepositional clauses """
    result._nominative = result._text


def QBusNoun(node, params, result):
    """ Save the noun used to refer to a bus """
    # Use singular, indefinite form
    # Hack: if the QBusNoun is a literal string, the _canonical logic
    # is not able to cast it to nominative case. Do it here by brute force. """
    if result._nominative in ("Vagni", "Vagns"):
        result._nominative = "vagn"
    if result._canonical in ("Vagni", "Vagns"):
        result._canonical = "vagn"
    result.bus_noun = result._canonical


def QBusArrivalTime(node, params, result):
    """ Bus arrival time query """
    # Set the query type
    result.qtype = "ArrivalTime"
    if "bus_number" in result:
        # The bus number has been automatically
        # percolated upwards from a child node (see below).
        # Set the query key
        result.qkey = result.bus_number


def QBusAnyArrivalTime(node, params, result):
    """ Bus arrival time query """
    # Set the query type
    result.qtype = "ArrivalTime"
    # Set the query key to 'Any'
    result.qkey = result.bus_number = "Any"


def QBusWhich(node, params, result):
    """ Buses on which routes stop at a given stop """
    # Set the query type
    result.qtype = "WhichRoute"
    if "stop_name" in result:
        # Set the query key to the name of the bus stop
        result.qkey = result.stop_name


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
    "ellefa": 11,
    "tólfa": 12,
    "einn": 1,
    "eitt": 1,
    "tveir": 2,
    "tvö": 2,
    "þrír": 3,
    "þrjú": 3,
    "fjórir": 4,
    "fjögur": 4,
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
    # Hack to catch common ASR error
    "hundrað eitt": 101,
    "hundrað tvö": 102,
    "hundrað þrjú": 103,
    "hundrað fjögur": 104,
    "hundrað fimm": 105,
    "hundrað sex": 106,
    "hundrað og eitt": 101,
    "hundrað og tvö": 102,
    "hundrað og þrjú": 103,
    "hundrað og fjögur": 104,
    "hundrað og fimm": 105,
    "hundrað og sex": 106,
}


def QBusWord(node, params, result):
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


def QBusNumber(node, params, result):
    """Reflect back the phrase used to specify the bus,
    but in nominative case."""
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
        if Settings.DEBUG and result.bus_number == 0:
            print("Unexpected bus number word: {0}".format(number))
    except Exception as e:
        if Settings.DEBUG:
            print("Unexpected exception: {0}".format(e))
        raise


# End of grammar nonterminal handlers


def _meaning_filter_func(mm):
    """Filter word meanings when casting bus stop names
    to cases other than nominative"""
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
def to_accusative(np: str) -> str:
    """ Return the noun phrase after casting it from nominative to accusative case """
    np = straeto.BusStop.voice(np)
    return query.to_accusative(np, meaning_filter_func=_meaning_filter_func)


@lru_cache(maxsize=None)
def to_dative(np: str) -> str:
    """ Return the noun phrase after casting it from nominative to dative case """
    np = straeto.BusStop.voice(np)
    return query.to_dative(np, meaning_filter_func=_meaning_filter_func)


def voice_distance(d):
    """Convert a distance, given as a float in units of kilometers, to a string
    that can be read aloud in Icelandic"""
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


def hms_fmt(hms: Tuple[int, int, int]) -> str:
    """ Format a (h, m, s) tuple to a HH:MM string """
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
    return "{0:02}:{1:02}".format(h, m)


def hms_diff(hms1: Tuple, hms2: Tuple) -> int:
    """ Return (hms1 - hms2) in minutes, where both are (h, m, s) tuples """
    return (hms1[0] - hms2[0]) * 60 + (hms1[1] - hms2[1])


def query_nearest_stop(query: Query, session: Session, result: Result) -> AnswerTuple:
    """ A query for the stop closest to the user """
    # Retrieve the client location
    location = query.location
    if location is None:
        # No location provided in the query
        answer = "Staðsetning óþekkt"
        response = dict(answer=answer)
        voice_answer = "Ég veit ekki hvar þú ert."
        return response, answer, voice_answer
    if not in_iceland(location):
        # User's location is not in Iceland
        return gen_answer("Ég þekki ekki strætósamgöngur utan Íslands.")

    # Get the stop closest to the user
    stop = straeto.BusStop.closest_to(location)
    if stop is None:
        return gen_answer("Ég finn enga stoppistöð nálægt þér.")
    answer = stop.name
    # Use the same word for the bus stop as in the query
    stop_word = result.stop_word if "stop_word" in result else "stoppistöð"
    va = [
        "Næsta",
        stop_word,
        "er",
        stop.name + ";",
        "þangað",
        "eru",
        voice_distance(straeto.distance(location, stop.location)),
    ]
    # Store a location coordinate and a bus stop name in the context
    query.set_context({"location": stop.location, "bus_stop": stop.name})
    voice_answer = " ".join(va) + "."
    response = dict(answer=answer)
    return response, answer, voice_answer


def query_arrival_time(query: Query, session: Session, result: Result):
    """ Answers a query for the arrival time of a bus """

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
            answer = voice_answer = "Ég veit ekki við hvaða stað þú átt."
            response = dict(answer=answer)
            return response, answer, voice_answer

    if not stop_name:
        location = query.location
        if location is None:
            answer = "Staðsetning óþekkt"
            response = dict(answer=answer)
            voice_answer = "Ég veit ekki hvar þú ert."
            return response, answer, voice_answer

    # Obtain today's bus schedule
    global SCHEDULE_TODAY
    with SCHEDULE_LOCK:
        if SCHEDULE_TODAY is None or not SCHEDULE_TODAY.is_valid_today:
            # We don't have today's schedule: create it
            SCHEDULE_TODAY = straeto.BusSchedule()

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
        stops = cast(
            List[straeto.BusStop],
            straeto.BusStop.closest_to_list(location, n=2, within_radius=0.4),
        )
        if not stops:
            # This will fetch the single closest stop, regardless of distance
            stops = [cast(straeto.BusStop, straeto.BusStop.closest_to(location))]

    # Handle the case where no bus number was specified (i.e. is 'Any')
    if result.bus_number == "Any" and stops:
        stop = stops[0]
        routes = sorted(
            (straeto.BusRoute.lookup(rid).number for rid in stop.visits.keys()),
            key=lambda r: int(r),
        )
        if len(routes) != 1:
            # More than one route possible: ask user to clarify
            route_seq = natlang_seq(list(map(str, routes)))
            answer = (
                " ".join(["Leiðir", route_seq, "stoppa á", to_dative(stop.name)])
                + ". Spurðu um eina þeirra."
            )
            voice_answer = (
                " ".join(
                    [
                        "Leiðir",
                        numbers_to_neutral(route_seq),
                        "stoppa á",
                        to_dative(stop.name),
                    ]
                )
                + ". Spurðu um eina þeirra."
            )
            response = dict(answer=answer)
            return response, answer, voice_answer
        # Only one route: use it as the query subject
        bus_number = routes[0]
        bus_name = "strætó númer {0}".format(bus_number)
    else:
        bus_number = result.bus_number if "bus_number" in result else 0
        bus_name = result.bus_name if "bus_name" in result else "Óþekkt"

    # Prepare results
    bus_name = cap_first(bus_name)
    va = [bus_name]
    a = []
    arrivals = []
    arrivals_dict = {}
    arrives = False
    route_number = str(bus_number)

    # First, check the closest stop
    # !!! TODO: Prepare a different area_priority parameter depending
    # !!! on the user's location; i.e. if she is in Eastern Iceland,
    # !!! route '1' would mean 'AL.1' instead of 'ST.1'.
    if stops:
        for stop in stops:
            arrivals_dict, arrives = SCHEDULE_TODAY.arrivals(route_number, stop)
            if arrives:
                break
        arrivals = list(arrivals_dict.items())
        a = ["Á", to_accusative(stop.name), "í átt að"]

    if arrivals:
        # Get a predicted arrival time for each direction from the
        # real-time bus location server
        prediction = SCHEDULE_TODAY.predicted_arrival(route_number, stop)
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
            va.extend(["í átt að", to_dative(direction)])
            a.append(to_dative(direction))
            deviation = []
            if prediction and direction in prediction:
                # We have a predicted arrival time
                hms_sched = times[0]
                hms_pred = prediction[direction][0]
                # Calculate the difference between the prediction and
                # now, and skip it if it is 1 minute or less
                diff = hms_diff(hms_pred, hms_now)
                if abs(diff) <= 1:
                    deviation = [", en er að fara núna"]
                else:
                    # Calculate the difference in minutes between the
                    # schedule and the prediction, with a positive number
                    # indicating a delay
                    diff = hms_diff(hms_pred, hms_sched)
                    if diff < -1:
                        # More than one minute ahead of schedule
                        if diff < -5:
                            # More than 5 minutes ahead
                            deviation = [
                                ", en kemur sennilega fyrr, eða",
                                hms_fmt(hms_pred),
                            ]
                        else:
                            # Two to five minutes ahead
                            deviation = [
                                ", en er",
                                str(-diff),
                                "mínútum á undan áætlun",
                            ]
                    elif diff >= 3:
                        # 3 minutes or more behind schedule
                        deviation = [
                            ", en kemur sennilega ekki fyrr en",
                            hms_fmt(hms_pred),
                        ]
            if first:
                assert stop is not None
                if deviation:
                    va.extend(["á að koma á", to_accusative(stop.name)])
                else:
                    va.extend(["kemur á", to_accusative(stop.name)])
            va.append("klukkan")
            a.append("klukkan")
            if len(times) == 1 or (
                len(times) > 1 and hms_diff(times[0], hms_now) >= 10
            ):
                # Either we have only one arrival time, or the next arrival is
                # at least 10 minutes away: only pronounce one time
                hms = times[0]
                time_text = hms_fmt(hms)
            else:
                # Return two or more times
                time_text = " og ".join(hms_fmt(hms) for hms in times)
            va.append(time_text)
            a.append(time_text)
            va.extend(deviation)
            a.extend(deviation)
            first = False

    elif arrives:
        # The given bus has already completed its scheduled halts at this stop today
        assert stops
        stop = stops[0]
        reply = ["kemur ekki aftur á", to_accusative(stop.name), "í dag"]
        va.extend(reply)
        a = [bus_name] + reply

    elif stops:
        # The given bus doesn't stop at all at either of the two closest stops
        stop = stops[0]
        va.extend(["stoppar ekki á", to_dative(stop.name)])
        a = [bus_name, "stoppar ekki á", to_dative(stop.name)]

    else:
        # The bus stop name is not recognized
        va = a = [stop_name.capitalize(), "er ekki biðstöð"]

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

    def assemble(x):
        """ Intelligently join answer string components. """
        return (" ".join(x) + ".").replace(" .", ".").replace(" ,", ",")

    voice_answer = assemble(va)
    answer = assemble(a)
    response = dict(answer=answer)
    return response, answer, voice_answer


def query_which_route(query: Query, session: Session, result: Result):
    """ Which routes stop at a given bus stop """
    stop_name = cast(str, result.stop_name)  # 'Einarsnes', 'Fiskislóð'...

    if stop_name in {"þar", "þangað"}:
        # Referring to a bus stop mentioned earlier
        ctx = query.fetch_context()
        if ctx and "bus_stop" in ctx:
            stop_name = cast(str, ctx["bus_stop"])
            result.qkey = stop_name
        else:
            answer = voice_answer = "Ég veit ekki við hvaða stað þú átt."
            response = dict(answer=answer)
            return response, answer, voice_answer

    bus_noun = result.bus_noun  # 'strætó', 'vagn', 'leið'...
    stops = straeto.BusStop.named(stop_name, fuzzy=True)
    if not stops:
        a = [stop_name, "þekkist ekki."]
        va = ["Ég", "þekki", "ekki", "biðstöðina", stop_name.capitalize()]
    else:
        routes = set()
        if query.location:
            straeto.BusStop.sort_by_proximity(stops, query.location)
        stop = stops[0]
        for route_id in stop.visits.keys():
            number = straeto.BusRoute.lookup(route_id).number
            routes.add(number)
        va = [bus_noun, "númer"]
        a = va[:]
        nroutes = len(routes)
        cnt = 0
        for rn in sorted(routes, key=lambda t: int(t)):
            if cnt:
                sep = "og" if cnt + 1 == nroutes else ","
                va.append(sep)
                a.append(sep)
            # We convert inflectable numbers to their text equivalents
            # since the speech engine can't be relied upon to get the
            # inflection of numbers right
            va.append(numbers_to_neutral(rn))
            a.append(rn)
            cnt += 1
        tail = ["stoppar á", to_dative(stop.name)]
        va.extend(tail)
        a.extend(tail)
        # Store a location coordinate and a bus stop name in the context
        query.set_context({"location": stop.location, "bus_stop": stop.name})

    voice_answer = correct_spaces(" ".join(va) + ".")
    answer = correct_spaces(" ".join(a))
    answer = cap_first(answer)
    response = dict(answer=answer)
    return response, answer, voice_answer


# Dispatcher for the various query types implemented in this module
_QFUNC = {
    "ArrivalTime": query_arrival_time,
    "NearestStop": query_nearest_stop,
    "WhichRoute": query_which_route,
}

# The following function is called after processing the parse
# tree for a query sentence that is handled in this module


def sentence(state, result):
    """ Called when sentence processing is complete """
    q: Query = state["query"]
    if "qtype" in result:
        # Successfully matched a query type
        q.set_qtype(result.qtype)
        q.set_key(result.qkey)
        # SQLAlchemy session, if required
        session = state["session"]
        # Select a query function and execute it
        qfunc = _QFUNC.get(result.qtype)
        answer: Optional[str] = None
        if qfunc is None:
            # Something weird going on - should not happen
            answer = cast(str, result.qtype) + ": " + cast(str, result.qkey)
            q.set_answer(dict(answer=answer), answer)
        else:
            try:
                voice_answer = None
                response: Union[AnswerTuple, ResponseType] = qfunc(q, session, result)
                if isinstance(response, tuple):
                    # We have both a normal and a voice answer
                    response, answer, voice_answer = response
                assert answer is not None
                q.set_answer(response, answer, voice_answer)
            except AssertionError:
                raise
            except Exception as e:
                if Settings.DEBUG:
                    raise
                q.set_error("E_EXCEPTION: {0}".format(e))
    else:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
