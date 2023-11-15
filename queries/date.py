"""

    Greynir: Natural language processing for Icelandic

    Date query response module

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
    along with this program.  If not, see http://www.gnu.org/licenses/.


    This module is an example of a plug-in query response module
    for the Greynir query subsystem. It handles plain text queries, i.e.
    ones that do not require parsing the query text. For this purpose
    it only needs to implement the handle_plain_text() function, as
    shown below.


    This particular module handles queries related to dates.

"""

# TODO: Special days should be mentioned by name, not date, in voice answers
# TODO: "How many weeks between April 3 and June 16?"
# TODO: Restore timezone-awareness
# TODO: "Hvað er mikið eftir af vinnuvikunni", "hvað er langt í helgina"
# TODO: "Hvaða vikudagur er DAGSETNING næstkomandi?"
# TODO: "Hvað gerðist á þessum degi?"
# TODO: "Hvaða vikudagur var 11. september 2001?" "Hvaða (viku)dagur er á morgun?"
#       "Hvaða dagur var í gær?"
# TODO: "Hvenær eru vetrarsólstöður" + more astronomical dates
# TODO: "Hvað er langt í helgina?" "Hvenær er næsti (opinberi) frídagur?"
# TODO: "Hvað eru margir dagar fram að jólum?"
# TODO: "Hvað eru margir dagar eftir af árinu? mánuðinum? vikunni?"
# TODO: "Hvað eru margir dagar eftir af árinu?" "Hvað er mikið eftir af árinu 2020?"
# TODO: "Hvenær er næst hlaupár?"
# TODO: "Hvaða árstíð er"
# TODO: "Á hvaða vikudegi er jóladagur?"
# TODO: "Hvenær er fyrsti í aðventu"
# TODO: "Hvaða öld er núna"
# TODO: "Hvað eru margir mánuðir í sumardaginn fyrsta" "hvað eru margar vikur í skírdag"
# TODO: "Þorláksmessa" not working
# TODO: "Hvenær er næst fullt tungl"
# TODO: Specify weekday in "hvenær er" queries (e.g. "Sjómannadagurinn er *sunnudaginn* 7. júní")
# TODO: "Hvað eru margar [unit of time measurement] í [dagsetningu]"
# TODO: "Hvenær byrjar þorrinn"
# TODO: "Hvaða frídagar/helgidagar/etc eru í febrúar"
# TODO: "hvenær eru páskar 2035"
# TODO: "Hvað eru margir dagar eftir af árinu?"

import logging
import random
from datetime import datetime, timedelta
from calendar import monthrange, isleap

from icespeak import gssml

from queries import Query, QueryStateDict
from utility import cap_first
from queries.util import (
    gen_answer,
    is_plural,
    sing_or_plur,
    read_grammar_file,
)
from tree import Result, Node, TerminalNode
from settings import changedlocale


_DATE_QTYPE = "Date"


# Lemmas of keywords that could indicate that the user is trying to use this module
TOPIC_LEMMAS = [
    "dagsetning",
    "morgundagur",
    "mánaðardagur",
    "vikudagur",
    "vika",
    "mánuður",
    "hvítasunnudagur",
    "uppstigningardagur",
    "öskudagur",
    "bolludagur",
    "hrekkjavaka",
    "fullveldisdagur",
    "sumardagur",
    "þorláksmessa",
    "aðfangadagur",
    "jól",
    "jóladagur",
    "gamlárskvöld",
    "nýársdagur",
    "baráttudagur",
    "páskar",
    "páskadagur",
    "skírdagur",
    "föstudagur",
    "þjóðhátíðardagur",
    "þjóðhátíð",
    "verslunarmannahelgi",
    "frídagur",
    "menningarnótt",
    "áramót",
    "ár",
]


def help_text(lemma: str) -> str:
    """Help text to return when query processor is unable to parse a query but
    one of the above lemmas is found in it"""
    return "Ég get svarað ef þú spyrð til dæmis: {0}?".format(
        random.choice(
            (
                "Hvaða dagur er í dag",
                "Hvaða dagur er á morgun",
                "Hvað er langt til jóla",
                "Hvenær eru páskarnir",
                "Á hvaða degi er frídagur verslunarmanna",
                "Hvenær er skírdagur",
            )
        )
    )


# Indicate that this module wants to handle parse trees for queries,
# as opposed to simple literal text strings
HANDLE_TREE = True

# The grammar nonterminals this module wants to handle
QUERY_NONTERMINALS = {"QDate"}

# The context-free grammar for the queries recognized by this plug-in module
GRAMMAR = read_grammar_file("date")


def QDateQuery(node: Node, params: QueryStateDict, result: Result) -> None:
    result.qtype = _DATE_QTYPE


def QDateCurrent(node: Node, params: QueryStateDict, result: Result) -> None:
    result["now"] = True


def QDateNextDay(node: Node, params: QueryStateDict, result: Result) -> None:
    result["tomorrow"] = True


def QDatePrevDay(node: Node, params: QueryStateDict, result: Result) -> None:
    result["yesterday"] = True


def QDateHowLongUntil(node: Node, params: QueryStateDict, result: Result) -> None:
    result["until"] = True


def QDateHowLongSince(node: Node, params: QueryStateDict, result: Result) -> None:
    result["since"] = True


def QDateWhenIs(node: Node, params: QueryStateDict, result: Result) -> None:
    result["when"] = True


def QDateWhichYear(node: Node, params: QueryStateDict, result: Result) -> None:
    result["year"] = True


def QDateLeapYear(node: Node, params: QueryStateDict, result: Result) -> None:
    result["leap"] = True


def Árið(node: Node, params: QueryStateDict, result: Result) -> None:
    y_node = node.first_child(lambda n: True)
    assert isinstance(y_node, TerminalNode)
    y = y_node.contained_year
    if not y:
        raise ValueError("No year number associated with YEAR token.")
    result["target"] = datetime(day=1, month=1, year=y)


def QDateAbsOrRel(node: Node, params: QueryStateDict, result: Result) -> None:
    datenode = node.first_child(lambda n: True)
    assert isinstance(datenode, TerminalNode)
    cdate = datenode.contained_date
    if cdate:
        y, m, d = cdate
        now = datetime.utcnow()

        # This is a date that contains at least month & mday
        if d and m:
            if not y:
                y = now.year
                # Bump year if month/day in the past
                if m < now.month or (m == now.month and d < now.day):
                    y += 1
            result["target"] = datetime(day=d, month=m, year=y)
        # Only contains month
        elif m:
            if not y:
                y = now.year
                if m < now.month:
                    y += 1
            ndays = monthrange(y, m)[1]
            result["days_in_month"] = ndays
            result["target"] = datetime(day=1, month=m, year=y)
    else:
        raise ValueError(f"No date in {str(datenode)}")


def QDateWhitsun(node: Node, params: QueryStateDict, result: Result) -> None:
    result["desc"] = "hvítasunnudagur"
    result["target"] = next_easter() + timedelta(days=49)


def QDateAscensionDay(node: Node, params: QueryStateDict, result: Result) -> None:
    result["desc"] = "uppstigningardagur"
    result["target"] = next_easter() + timedelta(days=39)


def QDateAshDay(node: Node, params: QueryStateDict, result: Result) -> None:
    result["desc"] = "öskudagur"
    result["target"] = next_easter() - timedelta(days=46)


def QDateBunDay(node: Node, params: QueryStateDict, result: Result) -> None:
    result["desc"] = "bolludagur"
    result["target"] = next_easter() - timedelta(days=48)  # 7 weeks before easter


def QDateHalloween(node: Node, params: QueryStateDict, result: Result) -> None:
    result["desc"] = "hrekkjavaka"
    result["target"] = dnext(datetime(year=datetime.today().year, month=10, day=31))


def QDateSovereigntyDay(node: Node, params: QueryStateDict, result: Result) -> None:
    result["desc"] = "fullveldisdagurinn"
    result["target"] = dnext(datetime(year=datetime.today().year, month=12, day=1))


def QDateFirstDayOfSummer(node: Node, params: QueryStateDict, result: Result) -> None:
    result["desc"] = "sumardagurinn fyrsti"
    # !!! BUG: This is not correct in all cases
    d = dnext(datetime(year=datetime.today().year, month=4, day=18))
    result["target"] = next_weekday(d, 3)


def QDateThorlaksMass(node: Node, params: QueryStateDict, result: Result) -> None:
    result["desc"] = "þorláksmessa"
    result["target"] = dnext(datetime(year=datetime.today().year, month=12, day=23))


def QDateChristmasEve(node: Node, params: QueryStateDict, result: Result) -> None:
    result["desc"] = "aðfangadagur jóla"
    result["target"] = dnext(datetime(year=datetime.today().year, month=12, day=24))


def QDateChristmasDay(node: Node, params: QueryStateDict, result: Result) -> None:
    result["desc"] = "jóladagur"
    result["target"] = dnext(datetime(year=datetime.today().year, month=12, day=25))


def QDateNewYearsEve(node: Node, params: QueryStateDict, result: Result) -> None:
    result["desc"] = "gamlársdagur"
    result["target"] = dnext(datetime(year=datetime.today().year, month=12, day=31))


def QDateNewYearsDay(node: Node, params: QueryStateDict, result: Result) -> None:
    result["desc"] = "nýársdagur"
    result["target"] = dnext(datetime(year=datetime.today().year, month=1, day=1))


def QDateNewYear(node: Node, params: QueryStateDict, result: Result) -> None:
    result["desc"] = "áramótin"
    result["is_verb"] = "eru"
    result["target"] = dnext(datetime(year=datetime.today().year, month=1, day=1))


def QDateWorkersDay(node: Node, params: QueryStateDict, result: Result) -> None:
    result["desc"] = "baráttudagur verkalýðsins"
    result["target"] = dnext(datetime(year=datetime.today().year, month=5, day=1))


def QDateEaster(node: Node, params: QueryStateDict, result: Result) -> None:
    result["desc"] = "páskar"
    result["is_verb"] = "eru"
    result["target"] = next_easter()


def QDateEasterSunday(node: Node, params: QueryStateDict, result: Result) -> None:
    result["desc"] = "páskadagur"
    result["target"] = next_easter()


def QDateGoodFriday(node: Node, params: QueryStateDict, result: Result) -> None:
    result["desc"] = "föstudagurinn langi"
    result["target"] = next_easter() + timedelta(days=-2)


def QDateMaundyThursday(node: Node, params: QueryStateDict, result: Result) -> None:
    result["desc"] = "skírdagur"
    result["target"] = next_easter() + timedelta(days=-3)


def QDateNationalDay(node: Node, params: QueryStateDict, result: Result) -> None:
    result["desc"] = "þjóðhátíðardagurinn"
    result["target"] = dnext(datetime(year=datetime.today().year, month=6, day=17))


def QDateBankHoliday(node: Node, params: QueryStateDict, result: Result) -> None:
    result["desc"] = "frídagur verslunarmanna"
    # First Monday of August
    result["target"] = this_or_next_weekday(
        dnext(datetime(year=datetime.today().year, month=8, day=1)), 0  # Monday
    )


def QDateCultureNight(node: Node, params: QueryStateDict, result: Result) -> None:
    result["desc"] = "menningarnótt"
    # Culture night is on the first Saturday after Reykjavík's birthday on Aug 18th
    aug18 = dnext(datetime(year=datetime.today().year, month=8, day=18))
    # !!! Is culture night never on Aug 18th?
    result["target"] = next_weekday(aug18, 5)  # Find the next Saturday


def QDateValentinesDay(node: Node, params: QueryStateDict, result: Result) -> None:
    result["desc"] = "valentínusardagur"
    result["target"] = dnext(datetime(year=datetime.today().year, month=2, day=14))


def QDateMansDay(node: Node, params: QueryStateDict, result: Result) -> None:
    result["desc"] = "bóndadagur"
    jan19 = dnext(datetime(year=datetime.today().year, month=1, day=19))
    result["target"] = next_weekday(jan19, 4)  # First Friday after Jan 19


def QDateWomansDay(node: Node, params: QueryStateDict, result: Result) -> None:
    result["desc"] = "konudagur"
    feb18 = dnext(datetime(year=datetime.today().year, month=2, day=18))
    result["target"] = next_weekday(feb18, 6)  # First Sunday after Feb 18


def QDateMardiGrasDay(node: Node, params: QueryStateDict, result: Result) -> None:
    result["desc"] = "sprengidagur"
    result["target"] = next_easter() - timedelta(days=47)


def QDatePalmSunday(node: Node, params: QueryStateDict, result: Result) -> None:
    result["desc"] = "pálmasunnudagur"
    result["target"] = next_easter() - timedelta(days=7)  # Week before Easter Sunday


def QDateSeamensDay(node: Node, params: QueryStateDict, result: Result) -> None:
    result["desc"] = "sjómannadagur"
    june1 = dnext(datetime(year=datetime.today().year, month=6, day=1))
    result["target"] = this_or_next_weekday(june1, 6)  # First Sunday in June


def QDateMothersDay(node: Node, params: QueryStateDict, result: Result) -> None:
    result["desc"] = "mæðradagur"
    may8 = dnext(datetime(year=datetime.today().year, month=5, day=8))
    result["target"] = this_or_next_weekday(may8, 6)  # Second Sunday in May


def QDateFathersDay(node: Node, params: QueryStateDict, result: Result) -> None:
    result["desc"] = "feðradagur"
    nov8 = dnext(datetime(year=datetime.today().year, month=11, day=8))
    result["target"] = this_or_next_weekday(nov8, 6)  # Second Sunday in November


def QDateIcelandicTongueDay(node: Node, params: QueryStateDict, result: Result) -> None:
    result["desc"] = "dagur íslenskrar tungu"
    result["target"] = dnext(datetime(year=datetime.today().year, month=11, day=16))


def QDateSecondChristmasDay(node: Node, params: QueryStateDict, result: Result) -> None:
    result["desc"] = "annar í jólum"
    result["target"] = dnext(datetime(year=datetime.today().year, month=12, day=26))


def QDateFirstDayOfWinter(node: Node, params: QueryStateDict, result: Result) -> None:
    result["desc"] = "fyrsti vetrardagur"
    result["target"] = None  # To be completed


def QDateSummerSolstice(node: Node, params: QueryStateDict, result: Result) -> None:
    result["desc"] = "sumarsólstöður"
    result["is_verb"] = "eru"
    result["target"] = None  # To be completed


def QDateWinterSolstice(node: Node, params: QueryStateDict, result: Result) -> None:
    result["desc"] = "vetrarsólstöður"
    result["is_verb"] = "eru"
    result["target"] = None  # To be completed


def next_weekday(d: datetime, weekday: int) -> datetime:
    """Get the date of the next weekday after a given date.
    0 = Monday, 1 = Tuesday, 2 = Wednesday, etc."""
    days_ahead = weekday - d.weekday()
    if days_ahead <= 0:  # Target day is today, or already happened this week
        days_ahead += 7
    return d + timedelta(days=days_ahead)


def this_or_next_weekday(d: datetime, weekday: int) -> datetime:
    """Get the date of the next weekday after or including a given date.
    0 = Monday, 1 = Tuesday, 2 = Wednesday, etc."""
    days_ahead = weekday - d.weekday()
    if days_ahead < 0:  # Target day already happened this week
        days_ahead += 7
    return d + timedelta(days=days_ahead)


def dnext(d: datetime) -> datetime:
    """Return datetime with year+1 if date was earlier in current year."""
    if d < datetime.utcnow():
        d = d.replace(year=d.year + 1)
    return d


def next_easter() -> datetime:
    """Find the date of next easter in the Gregorian calendar."""
    now = datetime.utcnow()
    e = calc_easter(now.year)
    if e < now:
        e = calc_easter(now.year + 1)
    return e


def calc_easter(year: int) -> datetime:
    """An implementation of Butcher's Algorithm for determining the date of
    Easter for the Western church. Works for any date in the Gregorian
    calendar (1583 and onward). Returns a datetime object.
    http://code.activestate.com/recipes/576517-calculate-easter-western-given-a-year/"""
    a = year % 19
    b = year // 100
    c = year % 100
    d = (19 * a + b - b // 4 - ((b - (b + 8) // 25 + 1) // 3) + 15) % 30
    e = (32 + 2 * (b % 4) + 2 * (c // 4) - d - (c % 4)) % 7
    f = d + e - 7 * ((a + 11 * d + 22 * e) // 451) + 114
    month = f // 31
    day = f % 31 + 1
    return datetime(year=year, month=month, day=day)


def _date_diff(d1: datetime, d2: datetime, unit: str = "days") -> int:
    """Get the time difference between two dates."""
    delta = d2 - d1
    cnt = getattr(delta, unit)
    return cnt


def howlong_answ(q: Query, result: Result) -> None:
    """Generate answer to a query about number of days since/until a given date."""
    now = datetime.utcnow()
    target = result["target"]

    q.set_key("HowLongUntilDate" if "until" in result else "HowLongSinceDate")

    # Check if it's today
    if target.date() == now.date():
        answ = gen_answer(f"Það er {target.strftime('%-d. %B')} í dag.")
        q.set_answer(
            answ[0], answ[1], gssml(answ[2], type="ordinals", case="nf", gender="kk")
        )
        return
    # Check if it's tomorrow
    # TODO: Maybe return num hours until tomorrow?
    if target.date() == now.date() + timedelta(days=1):
        answ = gen_answer(f"Það er {target.strftime('%-d. %B')} á morgun.")
        q.set_answer(
            answ[0], answ[1], gssml(answ[2], type="ordinals", case="nf", gender="kk")
        )
        return

    # Returns num days rounded down, so we increment by one.
    days = _date_diff(now, target, unit="days") + 1

    # Diff. strings for singular vs. plural
    plural = is_plural(days)
    verb = "eru" if plural else "er"
    days_desc = "dagar" if plural else "dagur"

    # Format date
    fmt = "%-d. %B" if now.year == target.year else "%-d. %B %Y"
    tfmt = target.strftime(fmt)

    # Date asked about is in the past
    if days < 0:
        days = abs(days)
        passed = "liðnir" if plural else "liðinn"
        voice = (
            f"Það {verb} "
            f"{gssml(days, type='number', gender='kk')} {days_desc} "
            f"{passed} frá {gssml(tfmt, type='date', case='þgf')}."
        )
        answer = f"{days} {days_desc}."
    # It's in the future
    else:
        voice = (
            f"Það {verb} "
            f"{gssml(days, type='number', gender='kk')} {days_desc} "
            f"þar til {gssml(tfmt, type='date')} gengur í garð."
        )
        answer = f"{days} {days_desc}."

    response = dict(answer=answer)
    q.set_answer(response, answer, voice)


def when_answ(q: Query, result: Result) -> None:
    """Generate answer to a question of the form "Hvenær er(u) [hátíðardagur]?" etc."""
    # Use plural 'eru' for 'páskar', 'jól' etc.
    is_verb = "er" if "is_verb" not in result else result.is_verb
    target_is = f"{cap_first(result.desc)} {is_verb}"
    target = result.target.strftime("%A %-d. %B").replace("dagur", "daginn")
    answer = f"{target_is} {target}"
    voice = f"{target_is} {gssml(target, type='date', case='þf')}"
    response = dict(answer=answer)

    q.set_key("WhenSpecialDay")
    q.set_answer(response, answer, voice)


def curr_date_answ(q: Query, result: Result) -> None:
    """Generate answer to a question of the form "Hver er dagsetningin [í dag]?" etc."""
    now = datetime.utcnow()
    date_str = now.strftime("%A %-d. %B %Y")
    answer = date_str.capitalize()
    response = dict(answer=answer)
    voice = f"Í dag er {gssml(date_str, type='date')}"

    q.set_key("CurrentDate")
    q.set_answer(response, answer, voice)


def tomorrow_date_answ(q: Query, result: Result) -> None:
    """Generate answer to a question of the form "Hvaða dagur er á morgun?" etc."""
    now = datetime.utcnow() + timedelta(days=1)
    date_str = now.strftime("%A %-d. %B %Y")
    answer = date_str.capitalize()
    response = dict(answer=answer)
    voice = f"Á morgun er {gssml(date_str, type='date')}"

    q.set_key("TomorrowDate")
    q.set_answer(response, answer, voice)


def yesterday_date_answ(q: Query, result: Result) -> None:
    """Generate answer to a question of the form "Hvaða dagur var í gær?" etc."""
    now = datetime.utcnow() - timedelta(days=1)
    date_str = now.strftime("%A %-d. %B %Y")
    answer = date_str.capitalize()
    response = dict(answer=answer)
    voice = f"Dagurinn í gær var {gssml(date_str, type='date')}"

    q.set_key("YesterdayDate")
    q.set_answer(response, answer, voice)


def days_in_month_answ(q: Query, result: Result) -> None:
    """Generate answer to a question of the form "Hvað eru margir dagar í [MÁNUÐI]?" etc."""
    ndays = result["days_in_month"]
    t = result["target"]
    mname = t.strftime("%B")
    answer = sing_or_plur(ndays, "dagar.", "dagur.")
    response = dict(answer=answer)
    voice = (
        f"Það eru {gssml(ndays, type='number', gender='kk')} dagar í {mname} {gssml(t.year, type='year')}"
        if is_plural(ndays)
        else f"Það er {gssml(ndays, type='number', gender='kk')} dagur í {mname} {gssml(t.year, type='year')}"
    )

    q.set_key("DaysInMonth")
    q.set_answer(response, answer, voice)


def year_answ(q: Query, result: Result) -> None:
    """Generate answer to a question of the form "Hvaða ár er núna?" etc."""
    now = datetime.utcnow()
    y = now.year
    answer = f"{y}."
    response = dict(answer=answer)
    voice = f"Það er árið {gssml(y, type='year')}."

    q.set_key("WhichYear")
    q.set_answer(response, answer, voice)


def leap_answ(q: Query, result: Result) -> None:
    """Generate answer to a question of the form "Er hlaupár?" etc."""
    now = datetime.utcnow()
    t = result.get("target")
    y = t.year if t else now.year
    verb = "er" if y >= now.year else "var"
    s = f"Árið {{}} {verb} {'' if isleap(y) else 'ekki '}hlaupár."
    answer = s.format(y)
    voice = s.format(gssml(y, type="year"))

    response = dict(answer=answer)
    q.set_key("IsLeapYear")
    q.set_answer(response, answer, voice)


_Q2FN_MAP = [
    ("now", curr_date_answ),
    ("tomorrow", tomorrow_date_answ),
    ("yesterday", yesterday_date_answ),
    ("days_in_month", days_in_month_answ),
    ("until", howlong_answ),
    ("since", howlong_answ),
    ("when", when_answ),
    ("year", year_answ),
    ("leap", leap_answ),
]


def sentence(state: QueryStateDict, result: Result) -> None:
    """Called when sentence processing is complete"""
    q: Query = state["query"]
    if "qtype" not in result:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
        return

    # Successfully matched a query type
    try:
        with changedlocale(category="LC_TIME"):
            for k, handler_func in _Q2FN_MAP:
                if k in result:
                    # Hand query object over to handler function
                    handler_func(q, result)
                    # Lowercase the query string to avoid 'Dagur' being
                    # displayed with a capital D
                    q.lowercase_beautified_query()
                    q.set_qtype(_DATE_QTYPE)
                    break

    except Exception as e:
        logging.warning(f"Exception {e} while processing date query '{q.query}'")
        q.set_error(f"E_EXCEPTION: {e}")
