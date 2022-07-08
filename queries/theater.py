"""

    Greynir: Natural language processing for Icelandic

    Randomness query response module

    Copyright (C) 2022 Miðeind ehf.

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

    This query module handles dialogue related to theater tickets.
"""

from typing import Any, Dict, List, Optional, Tuple, cast
from typing_extensions import TypedDict
import json
import logging
import random
import datetime

from settings import changedlocale
from query import Query, QueryStateDict
from tree import Result, Node, TerminalNode
from queries import AnswerTuple, gen_answer, natlang_seq, parse_num, time_period_desc
from queries.num import number_to_text, numbers_to_ordinal, numbers_to_text
from queries.resources import (
    DateResource,
    FinalResource,
    ListResource,
    NumberResource,
    Resource,
    ResourceState,
    TimeResource,
    WrapperResource,
)
from queries.dialogue import (
    AnsweringFunctionMap,
    DialogueStateManager,
)

_THEATER_DIALOGUE_NAME = "theater"
_THEATER_QTYPE = "theater"
_START_DIALOGUE_QTYPE = "theater_start"

TOPIC_LEMMAS = ["leikhús", "sýning"]


def help_text(lemma: str) -> str:
    """Help text to return when query.py is unable to parse a query but
    one of the above lemmas is found in it"""
    return "Ég skil þig ef þú segir til dæmis: {0}.".format(
        random.choice(("Hvaða sýningar eru í boði",))
    )


# This module wants to handle parse trees for queries
HANDLE_TREE = True

# This module involves dialogue functionality
DIALOGUE_NAME = "theater"
HOTWORD_NONTERMINALS = {"QTheaterHotWord"}

# The grammar nonterminals this module wants to handle
QUERY_NONTERMINALS = {"QTheater"}.union(HOTWORD_NONTERMINALS)

# The context-free grammar for the queries recognized by this plug-in module
GRAMMAR = """

Query →
    QTheaterHotWord | QTheater

QTheater → QTheaterQuery '?'?

QTheaterQuery →
    QTheaterDialogue

QTheaterHotWord →
    QTheaterNames '?'?
    | QTheaterEgVil? QTheaterKaupaFaraFaPanta "leikhúsmiða" '?'?
    | QTheaterEgVil? QTheaterKaupaFaraFaPanta "miða" "í" QTheaterNames '?'?
    | QTheaterEgVil? QTheaterKaupaFaraFaPanta "miða" "á" QTheaterNames "sýningu" '?'?
    | QTheaterEgVil? QTheaterKaupaFaraFaPanta QTheaterNames '?'?
    | QTheaterEgVil? QTheaterKaupaFaraFaPanta "leikhússýningu" '?'?

QTheaterNames →
    'leikhús'
    | 'þjóðleikhús'
    | 'Þjóðleikhús'
    | 'Borgarleikhús'
    | 'borgarleikhús'


QTheaterKaupaFaraFaPanta →
    "kaupa" "mér"?
    | "fara" "á"
    | "fara" "í"
    | "fá"
    | "panta"

QTheaterDialogue →
    QTheaterShowQuery
    | QTheaterShowDateQuery
    | QTheaterMoreDates
    | QTheaterPreviousDates
    | QTheaterShowSeatCountQuery
    | QTheaterShowLocationQuery
    | QTheaterShowPrice
    | QTheaterShowLength
    | QTheaterOptions
    | QTheaterYes
    | QTheaterNo
    | QTheaterCancel
    | QTheaterStatus

QTheaterOptions →
    QTheaterGeneralOptions
    | QTheaterShowOptions
    | QTheaterDateOptions
    | QTheaterRowOptions
    | QTheaterSeatOptions

QTheaterGeneralOptions →
    "hverjir"? "eru"? "valmöguleikarnir"
    | "hvert" "er" "úrvalið"
    | "hvað" "er" "í" "boði"

QTheaterShowOptions →  
    "hvaða" "sýningar" "eru" "í" "boði"

QTheaterDateOptions →
    "hvaða" "dagsetningar" "eru" "í" "boði"
    | "hvaða" "dagar" "eru" "í" "boði"
    | "hvaða" "dagsetningar" "er" "hægt" "að" "velja" "á" "milli"

QTheaterRowOptions →
    "hvaða" "raðir" "eru" QTheaterIBodiLausar
    | "hvaða" "röð" "er" QTheaterIBodiLausar
    | "hvaða" "bekkir" "eru" QTheaterIBodiLausar
    | "hvaða" "bekkur" "er" QTheaterIBodiLausar

QTheaterSeatOptions →
    "hvaða" "sæti" "eru" QTheaterIBodiLausar
    "hverjir" "eru" "sæta" "valmöguleikarnir"

QTheaterIBodiLausar →
    "í" "boði"
    | "lausar"
    | "lausir"
    | "laus"

QTheaterShowQuery → QTheaterEgVil? "velja" 'sýning' QTheaterShowName 
    > QTheaterEgVil? "fara" "á" 'sýning' QTheaterShowName
    > QTheaterShowName

QTheaterShowName → Nl

QTheaterShowPrice →
    "hvað" "kostar" "einn"? 'miði'
    | "hvað" "kostar" "1"? 'miði'
    | "hvað" "kostar" "einn"? 'miðinn' "á" "sýninguna"

QTheaterShowLength →
    "hvað" "er" "sýningin" "löng"

QTheaterShowDateQuery →
    QTheaterEgVil? "fara"? "á"? 'sýning'? QTheaterShowDate

QTheaterShowDate →
    QTheaterDateTime | QTheaterDate | QTheaterTime

QTheaterDateTime →
    tímapunkturafs

QTheaterDate →
    dagsafs
    | dagsföst

QTheaterTime →
    "klukkan"? tími

QTheaterMoreDates →
    "hverjar"? "eru"? "næstu" "þrjár"? QSyningarTimar
    | "hverjir" "eru" "næstu" "þrír"? QSyningarTimar
    | "get" "ég" "fengið" "að" "sjá" "næstu" "þrjá"? QSyningarTimar
    | QTheaterEgVil? "sjá"? "fleiri" QSyningarTimar 
    | QTheaterEgVil? "sjá"? "næstu" "þrjá"? QSyningarTimar

QTheaterPreviousDates →
    QTheaterEgVil "sjá" "fyrri" QSyningarTimar
    | "hvaða" QSyningarTimar "eru" "á" "undan" "þessum"?
    | "get" "ég" "fengið" "að" "sjá" QSyningarTimar "á" "undan" "þessum"?
    | QTheaterEgVil? "sjá"? QSyningarTimar "á" "undan" "þessum"?

QSyningarTimar →
    'sýningartíma'
    | "dagsetningar"
    | "sýningartímana"

QTheaterShowSeatCountQuery →
    QTheaterEgVil? "fá"? QTheaterNum "sæti"?

QTheaterShowLocationQuery →
    QTheaterShowRow
    | QTheaterShowSeats

QTheaterShowRow →
    QTheaterRodBekkur
    | QTheaterEgVil QTheaterVeljaRod QTheaterRodBekkur

QTheaterVeljaRod →
    "velja" "sæti"? "í"?
    | "sitja" "í"
    | "fá" "sæti" "í"
    | "fá" "sæti" "á"

QTheaterRodBekkur →
    QTheaterRodBekk? "númer"? QTheaterNum
    | QTheaterNum "bekk"
    | QTheaterNum "röð"

QTheaterShowSeats →
    QTheaterEgVil? "sæti"? "númer"? QTheaterNum "til"? QTheaterNum? 
    | QTheaterEgVil? "sæti"? "númer"? QTheaterNum "og"? QTheaterNum? 

QTheaterDateOptions → 
    "hvaða" "dagsetningar" "eru" "í" "boði"

QTheaterRodBekk → "röð" | "bekk"

QTheaterEgVil →
    "ég"? "vil"
    | "ég" "vill"
    | "mig" "langar" "að"
    | "mig" "langar" "í"

QTheaterNum →
    # to is a declinable number word ('tveir/tvo/tveim/tveggja')
    # töl is an undeclinable number word ('sautján')
    # tala is a number ('17')
    to | töl | tala

QTheaterYes → "já" "já"* | "endilega" | "já" "takk" | "játakk" | "já" "þakka" "þér" "fyrir" | "já" "takk" "kærlega" "fyrir"? | "jább" "takk"?

QTheaterNo → "nei" "takk"? | "nei" "nei"* | "neitakk" | "ómögulega"

QTheaterCancel → "ég" "hætti" "við"
    | QTheaterEgVil "hætta" "við" QTheaterPontun?

QTheaterStatus →
    "staðan"
    | "hver" "er" "staðan" "á" QTheaterPontun?
    | "staðan"
    | "hvert" "var" "ég" 'komin'? "í" QTheaterPontun?
    | "hvar" "var" "ég" 'komin'? "í"? QTheaterPontun?
    | "hver" "var" "staðan" "á"? QTheaterPontun
    | QTheaterEgVil "halda" "áfram" "með" QTheaterPontun

QTheaterPontun →
    "pöntuninni"
    | "leikhús" "pöntuninni"
    | "leikhús" "pöntunina"
    | "leikhúsmiða" "pöntuninni"
    | "leikhúsmiða" "pöntunina"
    | "leikhúsmiðapöntunina"
    | "leikhúsmiðapöntuninni"
    | "leikhús" "miða" "pöntunina"
    | "leikhús" "miða" "pöntuninni"


"""


class ShowType(TypedDict):
    title: str
    price: int
    show_length: int
    date: List[datetime.datetime]
    location: List[Tuple[int, int]]


_SHOWS: List[ShowType] = [
    {
        "title": "Emil í Kattholti",
        "price": 5900,
        "show_length": 150,
        "date": [
            datetime.datetime(2022, 8, 27, 13, 0),
            datetime.datetime(2022, 8, 28, 13, 0),
            datetime.datetime(2022, 8, 28, 17, 0),
            datetime.datetime(2022, 9, 3, 13, 0),
            datetime.datetime(2022, 9, 3, 17, 0),
            datetime.datetime(2022, 9, 4, 13, 0),
            datetime.datetime(2022, 9, 10, 13, 0),
        ],
        "location": [
            (1, 1),  # (row, seat)
            (1, 2),
            (1, 3),
            (1, 4),
            (2, 7),
            (2, 8),
            (2, 9),
            (6, 20),
            (6, 21),
            (6, 22),
            (6, 23),
            (6, 24),
        ],
    },
    {
        "title": "Lína Langsokkur",
        "price": 3900,
        "show_length": 90,
        "date": [
            datetime.datetime(2022, 8, 27, 13, 0),
            datetime.datetime(2022, 8, 28, 13, 0),
            datetime.datetime(2022, 8, 28, 17, 0),
            datetime.datetime(2022, 9, 3, 13, 0),
            datetime.datetime(2022, 9, 3, 17, 0),
            datetime.datetime(2022, 9, 4, 13, 0),
            datetime.datetime(2022, 9, 10, 13, 0),
        ],
        "location": [
            (1, 11),  # (row, seat)
            (1, 12),
            (1, 13),
            (1, 14),
            (2, 7),
            (2, 18),
            (2, 19),
            (6, 20),
            (6, 21),
            (6, 22),
            (6, 23),
            (6, 24),
        ],
    },
]

_BREAK_LENGTH = 0.3  # Seconds
_BREAK_SSML = '<break time="{0}s"/>'.format(_BREAK_LENGTH)


def _generate_show_answer(
    resource: ListResource, dsm: DialogueStateManager, result: Result
) -> Optional[AnswerTuple]:
    if resource.is_unfulfilled:
        return gen_answer(resource.prompts["initial"])
    if resource.is_fulfilled:
        return gen_answer(resource.prompts["confirm"].format(show=resource.data[0]))
    return None


def _generate_date_answer(
    resource: ListResource, dsm: DialogueStateManager, result: Result
) -> Optional[AnswerTuple]:
    title = dsm.get_resource("Show").data[0]
    print("GENERATING DATE ANSWER")
    dates: list[str] = []
    text_dates: list[str] = []
    index: int = 0
    extras: Dict[str, Any] = dsm.extras
    if "page_index" in extras:
        index = extras["page_index"]
    print("itering shows")
    for show in _SHOWS:
        if show["title"] == title:
            print("itering dates")
            for date in show["date"]:
                with changedlocale(category="LC_TIME"):
                    text_dates.append(date.strftime("\n   - %a %d. %b kl. %H:%M"))
                    dates.append(date.strftime("\n%A %d. %B klukkan %H:%M"))
    date_number: int = 3 if len(dates) >= 3 else len(dates)
    start_string: str = (
        "Eftirfarandi dagsetning er í boði:"
        if date_number == 1
        else "Næstu tvær dagsetningarnar eru:"
        if date_number == 2
        else "Næstu þrjár dagsetningarnar eru:"
    )
    if index == 0:
        start_string = start_string.replace("Næstu", "Fyrstu", 1)
    if len(dates) < 3:
        index = 0
        extras["page_index"] = 0
    if index > len(dates) - 3 and len(dates) > 3:
        start_string = "Síðustu þrjár dagsetningarnar eru:\n"
        index = max(0, len(dates) - 3)
        extras["page_index"] = index
    if resource.is_partially_fulfilled:
        show_date: Optional[datetime.date] = cast(
            DateResource, dsm.get_resource("ShowDate")
        ).date
        show_times: list[str] = []
        if show_date is not None:
            for show in _SHOWS:
                if show["title"] == title:
                    for date in show["date"]:
                        assert isinstance(date, datetime.datetime)
                        if date.date() == show_date:
                            show_times.append(date.strftime("\n   - %H:%M"))
            ans = resource.prompts["multiple_times_for_date"]
            voice_times = " klukkan " + natlang_seq(show_times)
            voice_ans = ans.format(
                times=voice_times.replace("\n   -", "").replace("\n", _BREAK_SSML)
            )
            text_ans = ans.format(times="".join((show_times)))
            ans = gen_answer(
                resource.prompts["multiple_times_for_date"]
                .format(times=natlang_seq(show_times))
                .replace("dagur", "dagurinn")
            )
            return (dict(answer=text_ans), text_ans, numbers_to_ordinal(voice_ans))
    print("UNFULFILLLED?", resource.is_unfulfilled)
    if resource.is_unfulfilled:
        if len(dates) > 0:
            ans = resource.prompts["initial"]
            if date_number == 1:
                ans = ans.replace("eru", "er", 1).replace(
                    "dagsetningar", "dagsetning", 1
                )
            voice_date_string = (
                start_string + natlang_seq(dates[index : index + date_number])
            ).replace("dagur", "dagurinn")
            text_date_string = start_string + "".join(
                text_dates[index : index + date_number]
            )
            voice_ans = ans.format(
                show=title,
                dates=voice_date_string,
                date_number=number_to_text(len(dates), gender="kvk"),
            ).replace("\n", _BREAK_SSML)
            text_ans = ans.format(
                show=title,
                dates=text_date_string,
                date_number=len(dates),
            )
            return (dict(answer=text_ans), text_ans, numbers_to_ordinal(voice_ans))
        else:
            return gen_answer(resource.prompts["no_date_available"].format(show=title))
    if resource.is_fulfilled:
        date = dsm.get_resource("ShowDate").data
        time = dsm.get_resource("ShowTime").data
        with changedlocale(category="LC_TIME"):
            date_time: str = datetime.datetime.combine(
                date,
                time,
            ).strftime("%A %d. %B klukkan %H:%M")
        ans = gen_answer(
            resource.prompts["confirm"]
            .format(date=date_time)
            .replace("dagur", "daginn")
        )
        return ans


def _generate_seat_count_answer(
    resource: NumberResource, dsm: DialogueStateManager, result: Result
) -> Optional[AnswerTuple]:
    if resource.is_unfulfilled:
        return gen_answer(resource.prompts["initial"])
    if resource.is_fulfilled:
        ans = resource.prompts["confirm"]
        nr_seats: int = resource.data
        if nr_seats == 1:
            ans = ans.replace("eru", "er")
        text_ans = ans.format(seats=resource.data)
        voice_ans = ans.format(seats=number_to_text(resource.data))
        return (dict(answer=text_ans), text_ans, voice_ans)


def _generate_row_answer(
    resource: ListResource, dsm: DialogueStateManager, result: Result
) -> Optional[AnswerTuple]:
    title: str = dsm.get_resource("Show").data[0]
    seats: int = dsm.get_resource("ShowSeatCount").data
    available_rows: list[str] = []
    text_available_rows: list[str] = []
    for show in _SHOWS:
        if show["title"] == title:
            checking_row: int = 1
            seats_in_row: int = 0
            row_added: int = 0
            for (row, _) in show["location"]:
                if checking_row == row and row != row_added:
                    seats_in_row += 1
                    if seats_in_row >= seats:
                        available_rows.append(number_to_text(row))
                        text_available_rows.append(str(row))
                        seats_in_row = 0
                        row_added = row
                else:
                    checking_row = row
                    seats_in_row = 1
    if resource.is_unfulfilled:
        if len(available_rows) == 0:
            dsm.set_resource_state("ShowDateTime", ResourceState.UNFULFILLED)
            dsm.extras["page_index"] = 0
            ans = resource.prompts["not_enough_seats"]
            if seats == 1:
                ans = ans.replace("laus", "laust")
            text_ans = ans.format(seats=seats)
            voice_ans = ans.format(seats=number_to_text(seats))
            return (dict(answer=text_ans), text_ans, voice_ans)
        ans = resource.prompts["initial"]
        if len(available_rows) == 1:
            ans = ans.replace("röðum", "röð")
        if seats == 1:
            ans = ans.replace("eru", "er")
        text_ans = ans.format(seats=seats, seat_rows=natlang_seq(text_available_rows))
        voice_ans = ans.format(
            seats=number_to_text(seats), seat_rows=natlang_seq(available_rows)
        )
        return (dict(answer=text_ans), text_ans, voice_ans)
    if resource.is_fulfilled:
        row = dsm.get_resource("ShowSeatRow").data[0]
        ans = resource.prompts["confirm"]
        text_ans = ans.format(row=row)
        voice_ans = ans.format(row=number_to_text(row))
        return (dict(answer=text_ans), text_ans, voice_ans)


def _generate_seat_number_answer(
    resource: ListResource, dsm: DialogueStateManager, result: Result
) -> Optional[AnswerTuple]:
    title: str = dsm.get_resource("Show").data[0]
    seats: int = dsm.get_resource("ShowSeatCount").data
    chosen_row: int = dsm.get_resource("ShowSeatRow").data[0]
    available_seats: list[str] = []
    text_available_seats: list[str] = []
    for show in _SHOWS:
        if show["title"] == title:
            for (row, seat) in show["location"]:
                if chosen_row == row:
                    text_available_seats.append(str(seat))
                    available_seats.append(number_to_text(seat))
    if resource.is_unfulfilled:
        ans = resource.prompts["initial"]
        if len(available_seats) == 1:
            ans = ans.replace("eru", "er")
        text_ans = ans.format(seats=natlang_seq(text_available_seats), row=chosen_row)
        voice_ans = ans.format(
            seats=natlang_seq(available_seats), row=number_to_text(chosen_row)
        )
        return (dict(answer=text_ans), text_ans, voice_ans)
    if resource.is_fulfilled:
        chosen_seats_voice_string: str = ""
        chosen_seats_text_string: str = ""

        if seats > 1:
            chosen_seats_voice_string = "{first_seat} til {last_seat}".format(
                first_seat=number_to_text(result.get("numbers")[0]),
                last_seat=number_to_text(result.get("numbers")[1]),
            )
            chosen_seats_text_string = "{first_seat} til {last_seat}".format(
                first_seat=result.get("numbers")[0],
                last_seat=result.get("numbers")[1],
            )
        else:
            chosen_seats_voice_string = number_to_text(result.get("numbers")[0])
            chosen_seats_text_string = result.get("numbers")[0]
        ans = resource.prompts["confirm"]
        text_ans = ans.format(seats=chosen_seats_text_string)
        voice_ans = ans.format(seats=chosen_seats_voice_string)
        return (dict(answer=text_ans), text_ans, voice_ans)


def _generate_final_answer(
    resource: FinalResource, dsm: DialogueStateManager, result: Result
) -> Optional[AnswerTuple]:
    if resource.is_cancelled:
        return gen_answer(resource.prompts["cancelled"])

    dsm.set_resource_state(resource.name, ResourceState.CONFIRMED)
    title = dsm.get_resource("Show").data[0]
    date = cast(DateResource, dsm.get_resource("ShowDate")).data
    time = cast(TimeResource, dsm.get_resource("ShowTime")).data
    number_of_seats = cast(NumberResource, dsm.get_resource("ShowSeatCount")).data
    seats = dsm.get_resource("ShowSeatNumber").data
    seat_voice_string: str = ""
    seats_text_string: str = ""
    if number_of_seats > 1:
        seat_voice_string = "{first_seat} til {last_seat}".format(
            first_seat=number_to_text(seats[0]),
            last_seat=number_to_text(seats[-1]),
        )
        seats_text_string = "{first_seat} til {last_seat}".format(
            first_seat=seats[0],
            last_seat=seats[-1],
        )
    else:
        seat_voice_string = number_to_text(seats[0])
        seats_text_string = seats[0]
    row = dsm.get_resource("ShowSeatRow").data[0]
    with changedlocale(category="LC_TIME"):
        date_time_voice: str = (
            datetime.datetime.combine(
                date,
                time,
            )
            .strftime("%A %d. %B klukkan %H:%M\n")
            .replace("dagur", "daginn")
        )
        date_time_text: str = datetime.datetime.combine(
            date,
            time,
        ).strftime("%a %d. %b kl. %H:%M")
    ans = resource.prompts["final"]
    text_ans = ans.format(
        seats=seats_text_string, row=row, show=title, date_time=date_time_text
    )
    voice_ans = ans.format(
        seats=seat_voice_string,
        row=number_to_text(row),
        show=title,
        date_time=date_time_voice,
    )
    return (dict(answer=text_ans), text_ans, voice_ans)


def QTheaterDialogue(node: Node, params: QueryStateDict, result: Result) -> None:
    if "qtype" not in result:
        result.qtype = _THEATER_QTYPE


def QTheaterHotWord(node: Node, params: QueryStateDict, result: Result) -> None:
    result.qtype = _START_DIALOGUE_QTYPE
    print("ACTIVATING THEATER MODULE")
    Query.get_dsm(result).hotword_activated()


def QTheaterShowQuery(node: Node, params: QueryStateDict, result: Result) -> None:
    dsm: DialogueStateManager = Query.get_dsm(result)
    selected_show: str = result.show_name
    print("SEARCHING FOR A SHOW:", selected_show)
    resource: ListResource = cast(ListResource, dsm.get_resource("Show"))
    show_exists = False
    for show in _SHOWS:
        if show["title"].lower() == selected_show.lower():
            resource.data = [show["title"]]
            dsm.set_resource_state(resource.name, ResourceState.FULFILLED)
            show_exists = True
            break
    if not show_exists:
        if resource.is_unfulfilled:
            dsm.set_answer(gen_answer(resource.prompts["no_show_matched"]))
            # result.no_show_matched = True
        if resource.is_fulfilled:
            dsm.set_answer(
                gen_answer(
                    resource.prompts["no_show_matched_data_exists"].format(
                        show=resource.data[0]
                    )
                )
            )
            # result.no_show_matched_data_exists = True

def QTheaterShowPrice(node: Node, params: QueryStateDict, result: Result) -> None:
    dsm = Query.get_dsm(result)
    show = dsm.get_resource("Show")
    if show.is_confirmed:
        show = [s for s in _SHOWS if s["title"].lower() == show.data[0].lower()][0]
        price = show["price"]
        ans = f"Verðið fyrir einn miða á sýninguna {show['title']} er {price} kr."

        dsm.set_answer(({"answer": ans}, ans, numbers_to_text(ans, gender="kvk").replace("kr", "krónur")))
    else:
        dsm.set_answer(gen_answer("Þú hefur ekki valið sýningu."))

def QTheaterShowLength(node: Node, params: QueryStateDict, result: Result) -> None:
    dsm = Query.get_dsm(result)
    show = dsm.get_resource("Show")
    if show.is_confirmed:
        show = [s for s in _SHOWS if s["title"].lower() == show.data[0].lower()][0]
        length = show["show_length"]
        ans = f"Lengd sýningarinnar {show['title']} er {time_period_desc(length*60)}."

        dsm.set_answer(({"answer": ans}, ans, numbers_to_text(ans, gender="kvk")))
    else:
        dsm.set_answer(gen_answer("Þú hefur ekki valið sýningu."))

def _add_date(
    resource: DateResource, dsm: DialogueStateManager, result: Result
) -> None:
    dsm.set_resource_state(resource.name, ResourceState.UNFULFILLED)
    if dsm.get_resource("Show").is_confirmed:
        show_title: str = dsm.get_resource("Show").data[0]
        for show in _SHOWS:
            if show["title"].lower() == show_title.lower():
                for date in show["date"]:
                    if result["show_date"] == date.date():
                        resource.set_date(date.date())
                        dsm.set_resource_state(resource.name, ResourceState.FULFILLED)
                        break
        time_resource: TimeResource = cast(TimeResource, dsm.get_resource("ShowTime"))
        dsm.set_resource_state(time_resource.name, ResourceState.UNFULFILLED)
        datetime_resource: Resource = dsm.get_resource("ShowDateTime")
        show_times: list[datetime.time] = []
        for show in _SHOWS:
            if show["title"].lower() == show_title.lower():
                for date in show["date"]:
                    if resource.date == date.date():
                        show_times.append(date.time())
        if len(show_times) == 0:
            dsm.set_answer(gen_answer(datetime_resource.prompts["no_date_matched"]))
            # result.no_date_matched = True
            return
        if len(show_times) == 1:
            time_resource.set_time(show_times[0])
            dsm.set_resource_state(time_resource.name, ResourceState.FULFILLED)
            dsm.set_resource_state(datetime_resource.name, ResourceState.FULFILLED)
        else:
            dsm.set_resource_state(
                datetime_resource.name, ResourceState.PARTIALLY_FULFILLED
            )


def _add_time(
    resource: TimeResource, dsm: DialogueStateManager, result: Result
) -> None:
    dsm.set_resource_state(resource.name, ResourceState.UNFULFILLED)
    if result.get("no_date_matched"):
        return
    if dsm.get_resource("Show").is_confirmed:
        show_title: str = dsm.get_resource("Show").data[0]
        date_resource: DateResource = cast(DateResource, dsm.get_resource("ShowDate"))
        datetime_resource: Resource = dsm.get_resource("ShowDateTime")
        first_matching_date: Optional[datetime.datetime] = None
        if date_resource.is_fulfilled:
            for show in _SHOWS:
                if show["title"].lower() == show_title.lower():
                    for date in show["date"]:
                        if (
                            date_resource.date == date.date()
                            and result["show_time"] == date.time()
                        ):
                            first_matching_date = date
                            resource.set_time(date.time())
                            dsm.set_resource_state(
                                resource.name, ResourceState.FULFILLED
                            )
                            break
            if resource.is_fulfilled:
                dsm.set_resource_state(datetime_resource.name, ResourceState.FULFILLED)
            else:
                result.wrong_show_time = True
        else:
            for show in _SHOWS:
                if show["title"].lower() == show_title.lower():
                    for date in show["date"]:
                        if result["show_time"] == date.time():
                            if first_matching_date is None:
                                first_matching_date = date
                            else:
                                dsm.set_answer(
                                    gen_answer(
                                        datetime_resource.prompts["many_matching_times"]
                                    )
                                )
                                # result.many_matching_times = True
                                return
            if first_matching_date is not None:
                date_resource: DateResource = cast(
                    DateResource, dsm.get_resource("ShowDate")
                )
                date_resource.set_date(first_matching_date.date())
                dsm.set_resource_state(date_resource.name, ResourceState.FULFILLED)
                resource.set_time(first_matching_date.time())
                dsm.set_resource_state(resource.name, ResourceState.FULFILLED)
                dsm.set_resource_state(datetime_resource.name, ResourceState.FULFILLED)
        if first_matching_date is None:
            dsm.set_answer(gen_answer(datetime_resource.prompts["no_time_matched"]))
            # result.no_time_matched = True


def QTheaterDateTime(node: Node, params: QueryStateDict, result: Result) -> None:
    datetimenode = node.first_child(lambda n: True)
    assert isinstance(datetimenode, TerminalNode)
    now = datetime.datetime.now()
    y, m, d, h, min, _ = (i if i != 0 else None for i in json.loads(datetimenode.aux))
    if y is None:
        y = now.year
    if m is None:
        m = now.month
    if d is None:
        d = now.day
    if h is None:
        h = 12
    if min is None:
        min = 0
    # Change before noon times to afternoon
    if h < 12:
        h += 12
    result["show_time"] = datetime.time(h, min)
    result["show_date"] = datetime.date(y, m, d)

    dsm: DialogueStateManager = Query.get_dsm(result)
    _add_date(cast(DateResource, dsm.get_resource("ShowDate")), dsm, result)
    _add_time(cast(TimeResource, dsm.get_resource("ShowTime")), dsm, result)


def QTheaterDate(node: Node, params: QueryStateDict, result: Result) -> None:
    datenode = node.first_child(lambda n: True)
    assert isinstance(datenode, TerminalNode)
    cdate = datenode.contained_date
    if cdate:
        y, m, d = cdate
        now = datetime.datetime.utcnow()

        # This is a date that contains at least month & mday
        if d and m:
            if not y:
                y = now.year
                # Bump year if month/day in the past
                if m < now.month or (m == now.month and d < now.day):
                    y += 1
            result["show_date"] = datetime.date(day=d, month=m, year=y)

            dsm: DialogueStateManager = Query.get_dsm(result)
            _add_date(cast(DateResource, dsm.get_resource("ShowDate")), dsm, result)
            return
    raise ValueError("No date in {0}".format(str(datenode)))


def QTheaterTime(node: Node, params: QueryStateDict, result: Result) -> None:
    # Extract time from time terminal nodes
    tnode = cast(TerminalNode, node.first_child(lambda n: n.has_t_base("tími")))
    if tnode:
        aux_str = tnode.aux.strip("[]")
        hour, minute, _ = (int(i) for i in aux_str.split(", "))
        # Change before noon times to afternoon
        if hour < 12:
            hour += 12

        result["show_time"] = datetime.time(hour, minute)

        dsm: DialogueStateManager = Query.get_dsm(result)
        _add_time(cast(TimeResource, dsm.get_resource("ShowTime")), dsm, result)


def QTheaterMoreDates(node: Node, params: QueryStateDict, result: Result) -> None:
    dsm: DialogueStateManager = Query.get_dsm(result)
    if dsm.current_resource.name == "ShowDate":
        extras: Dict[str, Any] = dsm.extras
        if "page_index" in extras:
            extras["page_index"] += 3
        else:
            extras["page_index"] = 3


def QTheaterPreviousDates(node: Node, params: QueryStateDict, result: Result) -> None:
    dsm: DialogueStateManager = Query.get_dsm(result)
    if dsm.current_resource.name == "ShowDate":
        extras: Dict[str, Any] = dsm.extras
        if "page_index" in extras:
            extras["page_index"] = max(extras["page_index"] - 3, 0)
        else:
            extras["page_index"] = 0


def QTheaterShowSeatCountQuery(
    node: Node, params: QueryStateDict, result: Result
) -> None:
    dsm: DialogueStateManager = Query.get_dsm(result)
    if dsm.get_resource("ShowDateTime").is_confirmed:
        resource: NumberResource = cast(
            NumberResource, dsm.get_resource("ShowSeatCount")
        )
        if result.number > 0:
            resource.data = result.number
            dsm.set_resource_state(resource.name, ResourceState.FULFILLED)
        else:
            dsm.set_answer(gen_answer(resource.prompts["invalid_seat_count"]))
            # result.invalid_seat_count = True


def QTheaterShowRow(node: Node, params: QueryStateDict, result: Result) -> None:
    dsm: DialogueStateManager = Query.get_dsm(result)
    if dsm.get_resource("ShowSeatCount").is_confirmed:
        title: str = dsm.get_resource("Show").data[0]
        seats: int = dsm.get_resource("ShowSeatCount").data
        resource: ListResource = cast(ListResource, dsm.get_resource("ShowSeatRow"))
        available_rows: list[int] = []
        for show in _SHOWS:
            if show["title"].lower() == title.lower():
                checking_row: int = 1
                seats_in_row: int = 0
                for (row, _) in show["location"]:
                    if checking_row == row:
                        seats_in_row += 1
                        if seats_in_row >= seats:
                            available_rows.append(row)
                            seats_in_row = 0
                    else:
                        checking_row = row
                        seats_in_row = 1
        if result.number in available_rows:
            resource.data = [result.number]
            dsm.set_resource_state(resource.name, ResourceState.FULFILLED)
        else:
            dsm.set_resource_state(resource.name, ResourceState.UNFULFILLED)
            ans = resource.prompts["no_row_matched"]
            if seats == 1:
                ans = ans.replace("laus", "laust")
            text_ans = ans.format(seats=seats)
            voice_ans = ans.format(seats=number_to_text(seats))
            dsm.set_answer((dict(answer=text_ans), text_ans, voice_ans))
            # result.no_row_matched = True


def QTheaterShowSeats(node: Node, params: QueryStateDict, result: Result) -> None:

    dsm: DialogueStateManager = Query.get_dsm(result)
    if dsm.get_resource("ShowSeatRow").is_confirmed:
        resource: ListResource = cast(ListResource, dsm.get_resource("ShowSeatNumber"))
        title: str = dsm.get_resource("Show").data[0]
        row: int = dsm.get_resource("ShowSeatRow").data[0]
        number_of_seats: int = dsm.get_resource("ShowSeatCount").data
        selected_seats: list[int] = []
        if len(result.numbers) > 1:
            selected_seats = [
                seat for seat in range(result.numbers[0], result.numbers[1] + 1)
            ]
        else:
            selected_seats = [result.numbers[0]]
        if len(selected_seats) != number_of_seats:
            resource.data = []
            dsm.set_resource_state(resource.name, ResourceState.UNFULFILLED)

            result.wrong_number_seats_selected = True
            if len(result.get("numbers")) > 1:
                chosen_seats = len(
                    range(result.get("numbers")[0], result.get("numbers")[1] + 1)
                )
            else:
                chosen_seats = 1
            ans = resource.prompts["wrong_number_seats_selected"]
            text_ans = ans.format(chosen_seats=chosen_seats, seats=number_of_seats)
            voice_ans = ans.format(
                chosen_seats=number_to_text(chosen_seats),
                seats=number_to_text(number_of_seats),
            )
            dsm.set_answer((dict(answer=text_ans), text_ans, voice_ans))
            return
        for show in _SHOWS:
            if show["title"].lower() == title.lower():
                seats: list[int] = []
                for seat in selected_seats:
                    if (row, seat) in show["location"]:
                        seats.append(seat)
                    else:
                        resource.data = []
                        dsm.set_resource_state(resource.name, ResourceState.UNFULFILLED)
                        dsm.set_answer(
                            gen_answer(resource.prompts["seats_unavailable"])
                        )
                        # result.seats_unavailable = True
                        return
                resource.data = []
                for seat in seats:
                    resource.data.append(seat)
        if len(resource.data) > 0:
            dsm.set_resource_state(resource.name, ResourceState.FULFILLED)


def QTheaterGeneralOptions(node: Node, params: QueryStateDict, result: Result) -> None:
    # result.options_info = True
    dsm: DialogueStateManager = Query.get_dsm(result)
    resource = dsm.current_resource
    if resource.name == "Show":
        QTheaterShowOptions(node, params, result)
    elif resource.name == "ShowDateTime":
        QTheaterDateOptions(node, params, result)
    elif resource.name == "ShowSeatRow":
        QTheaterRowOptions(node, params, result)
    elif resource.name == "ShowSeatOptions":
        QTheaterSeatOptions(node, params, result)


def QTheaterShowOptions(node: Node, params: QueryStateDict, result: Result) -> None:
    # result.show_options = True
    dsm: DialogueStateManager = Query.get_dsm(result)
    resource = dsm.current_resource
    if resource.name == "Show":
        shows: list[str] = []
        for show in _SHOWS:
            shows.append("\n   - " + show["title"])
        ans = resource.prompts["options"]
        if len(shows) == 1:
            ans = ans.replace("Sýningarnar", "Sýningin", 1).replace("eru", "er", 2)
        text_ans = ans.format(options="".join(shows))
        voice_ans = ans.format(options=natlang_seq(shows)).replace("-", "")
        dsm.set_answer((dict(answer=text_ans), text_ans, voice_ans))


def QTheaterDateOptions(node: Node, params: QueryStateDict, result: Result) -> None:
    # result.date_options = True
    dsm: DialogueStateManager = Query.get_dsm(result)
    resource = dsm.current_resource
    if resource.name == "ShowDateTime":
        title = dsm.get_resource("Show").data[0]
        dates: list[str] = []
        text_dates: list[str] = []
        index: int = 0
        extras: Dict[str, Any] = dsm.extras
        if "page_index" in extras:
            index = extras["page_index"]
        for show in _SHOWS:
            if show["title"].lower() == title.lower():
                print("itering dates")
                for date in show["date"]:
                    with changedlocale(category="LC_TIME"):
                        text_dates.append(date.strftime("\n   - %a %d. %b kl. %H:%M"))
                        dates.append(date.strftime("\n%A %d. %B klukkan %H:%M"))
        date_number: int = 3 if len(dates) >= 3 else len(dates)
        start_string: str = (
            "Eftirfarandi dagsetning er í boði:"
            if date_number == 1
            else "Næstu tvær dagsetningarnar eru:"
            if date_number == 2
            else "Næstu þrjár dagsetningarnar eru:"
        )
        print("blaaaaa")
        if index == 0:
            start_string = start_string.replace("Næstu", "Fyrstu", 1)
        if len(dates) < 3:
            index = 0
            extras["page_index"] = 0
        if index > len(dates) - 3 and len(dates) > 3:
            start_string = "Síðustu þrjár dagsetningarnar eru:\n"
            index = max(0, len(dates) - 3)
            extras["page_index"] = index
        options_string = (
            start_string + natlang_seq(dates[index : index + date_number])
        ).replace("dagur", "dagurinn")
        text_options_string = start_string + "".join(
            text_dates[index : index + date_number]
        )
        if len(dates) > 0:
            ans = resource.prompts["options"]
            if date_number == 1:
                ans = ans.replace("eru", "er", 1).replace(
                    "dagsetningar", "dagsetning", 1
                )
            voice_ans = ans.format(
                options=options_string,
                date_number=number_to_text(len(dates), gender="kvk"),
            ).replace("\n", _BREAK_SSML)
            text_ans = ans.format(
                options=text_options_string,
                date_number=number_to_text(len(dates), gender="kvk"),
            )

            dsm.set_answer(
                (dict(answer=text_ans), text_ans, numbers_to_ordinal(voice_ans))
            )
        else:
            dsm.set_answer(
                gen_answer(resource.prompts["no_date_available"].format(show=title))
            )


def QTheaterRowOptions(node: Node, params: QueryStateDict, result: Result) -> None:
    # result.row_options = True
    dsm: DialogueStateManager = Query.get_dsm(result)
    resource = dsm.current_resource
    if resource.name == "ShowSeatRow":
        title: str = dsm.get_resource("Show").data[0]
        seats: int = dsm.get_resource("ShowSeatCount").data
        available_rows: list[str] = []
        text_available_rows: list[str] = []
        for show in _SHOWS:
            if show["title"].lower() == title.lower():
                checking_row: int = 1
                seats_in_row: int = 0
                row_added: int = 0
                for (row, _) in show["location"]:
                    if checking_row == row and row != row_added:
                        seats_in_row += 1
                        if seats_in_row >= seats:
                            available_rows.append(number_to_text(row))
                            text_available_rows.append(str(row))
                            seats_in_row = 0
                            row_added = row
                    else:
                        checking_row = row
                        seats_in_row = 1
        ans = resource.prompts["options"]
        if len(available_rows) == 1:
            ans = ans.replace("eru", "er").replace("Raðir", "Röð")
        if seats == 1:
            ans = ans.replace("laus", "laust")
        text_ans = ans.format(rows=natlang_seq(text_available_rows), seats=seats)
        voice_ans = ans.format(
            rows=natlang_seq(available_rows), seats=number_to_text(seats)
        )
        dsm.set_answer((dict(answer=text_ans), text_ans, voice_ans))


def QTheaterSeatOptions(node: Node, params: QueryStateDict, result: Result) -> None:
    result.seat_options = True
    dsm: DialogueStateManager = Query.get_dsm(result)
    resource = dsm.current_resource
    if resource.name == "ShowSeatNumber":
        title: str = dsm.get_resource("Show").data[0]
        chosen_row: int = dsm.get_resource("ShowSeatRow").data[0]
        available_seats: list[str] = []
        text_available_seats: list[str] = []
        for show in _SHOWS:
            if show["title"].lower() == title.lower():
                for (row, seat) in show["location"]:
                    if chosen_row == row:
                        text_available_seats.append(str(seat))
                        available_seats.append(number_to_text(seat))
        if (not resource.is_confirmed and result.get("options_info")) or result.get(
            "seat_options"
        ):
            ans = resource.prompts["options"]
            if len(available_seats) == 1:
                ans = ans.replace("Sætin", "Sætið", 1).replace("eru", "er", 2)
            text_ans = ans.format(
                row=chosen_row, options=natlang_seq(text_available_seats)
            )
            voice_ans = ans.format(
                row=number_to_text(chosen_row), options=natlang_seq(available_seats)
            )
            dsm.set_answer((dict(answer=text_ans), text_ans, voice_ans))


def QTheaterShowName(node: Node, params: QueryStateDict, result: Result) -> None:
    result.show_name = (
        " ".join(result._text.split()[1:])
        if result._text.startswith("sýning")
        else result._text
    )


def QTheaterNum(node: Node, params: QueryStateDict, result: Result):
    number: int = int(parse_num(node, result._nominative))
    if "numbers" not in result:
        result["numbers"] = []
    result.numbers.append(number)
    result.number = number


def QTheaterCancel(node: Node, params: QueryStateDict, result: Result):
    dsm: DialogueStateManager = Query.get_dsm(result)
    dsm.set_resource_state("Final", ResourceState.CANCELLED)
    dsm.finish_dialogue()

    result.qtype = "QTheaterCancel"


def QTheaterYes(node: Node, params: QueryStateDict, result: Result):
    dsm: DialogueStateManager = Query.get_dsm(result)
    current_resource = dsm.current_resource
    if (
        not current_resource.is_confirmed
        and current_resource.name
        in (
            "Show",
            "ShowDateTime",
            "ShowSeatCount",
            "ShowSeatRow",
            "ShowSeatNumber",
        )
    ) and current_resource.is_fulfilled:
        print("CONFIRIMNGG")
        dsm.set_resource_state(current_resource.name, ResourceState.CONFIRMED)
        print("CASCADED STATE")
        if isinstance(current_resource, WrapperResource):
            for rname in current_resource.requires:
                dsm.get_resource(rname).state = ResourceState.CONFIRMED


def QTheaterNo(node: Node, params: QueryStateDict, result: Result):
    dsm: DialogueStateManager = Query.get_dsm(result)
    resource = dsm.current_resource
    if (
        not resource.is_confirmed
        and resource.name
        in (
            "Show",
            "ShowDateTime",
            "ShowSeatCount",
            "ShowSeatRow",
            "ShowSeatNumber",
        )
    ) and resource.is_fulfilled:
        dsm.set_resource_state(resource.name, ResourceState.UNFULFILLED)
        if isinstance(resource, WrapperResource):
            for rname in resource.requires:
                dsm.set_resource_state(rname, ResourceState.UNFULFILLED)


def QTheaterStatus(node: Node, params: QueryStateDict, result: Result):
    # TODO: Handle QTheaterStatus again with dsm in query
    result.qtype = "QTheaterStatus"
    dsm: DialogueStateManager = Query.get_dsm(result)
    dsm.set_answer(
        gen_answer(
            "Leikhúsmiðapöntunin þín gengur bara vel. {0}".format(
                dsm.get_answer(_ANSWERING_FUNCTIONS, result)
            )
        )
    )


# SHOW_URL = "https://leikhusid.is/wp-json/shows/v1/categories/938"


# def _fetch_shows() -> Any:
#     resp = query_json_api(SHOW_URL)
#     if resp:
#         assert isinstance(resp, list)
#         return [s["title"] for s in resp]


_ANSWERING_FUNCTIONS: AnsweringFunctionMap = {
    "Show": _generate_show_answer,
    "ShowDateTime": _generate_date_answer,
    "ShowSeatCount": _generate_seat_count_answer,
    "ShowSeatRow": _generate_row_answer,
    "ShowSeatNumber": _generate_seat_number_answer,
    "Final": _generate_final_answer,
}


def sentence(state: QueryStateDict, result: Result) -> None:
    """Called when sentence processing is complete"""
    q: Query = state["query"]
    dsm: DialogueStateManager = q.dsm
    if dsm.not_in_dialogue():
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
        return

    try:
        print("A")
        # result.shows = _fetch_shows()
        # dsm.setup_dialogue(_ANSWERING_FUNCTIONS)
        # if result.qtype == "QTheaterStatus":
        #     # Example info handling functionality
        #     text = "Leikhúsmiðapöntunin þín gengur bara vel. "
        #     ans = dsm.get_answer() or gen_answer(text)
        #     q.set_answer(*ans)
        #     return
        # print("C")
        # print(dsm._resources)
        ans: Optional[AnswerTuple] = dsm.get_answer(_ANSWERING_FUNCTIONS, result)
        if "show_options" not in result:
            q.query_is_command()
        print("D", ans)
        if not ans:
            print("No answer generated")
            q.set_error("E_QUERY_NOT_UNDERSTOOD")
            return

        q.set_qtype(result.qtype)
        q.set_answer(*ans)
    except Exception as e:
        logging.warning("Exception while processing random query: {0}".format(e))
        q.set_error("E_EXCEPTION: {0}".format(e))
        raise
