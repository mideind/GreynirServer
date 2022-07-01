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

from typing import Any, Callable, Optional, cast
import json
import logging
import random
import datetime


from query import Query, QueryStateDict
from tree import Result, Node, TerminalNode
from queries import gen_answer, natlang_seq, parse_num, query_json_api
from queries.num import number_to_text
from queries.dialogue import (
    DateResource,
    DialogueStateManager,
    ListResource,
    NumberResource,
    Resource,
    ResourceState,
    TimeResource,
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

# The grammar nonterminals this module wants to handle
QUERY_NONTERMINALS = {"QTheater"}

# The context-free grammar for the queries recognized by this plug-in module
GRAMMAR = """

Query →
    QTheater

QTheater → QTheaterQuery '?'?

QTheaterQuery →
    QTheaterHotWord | QTheaterDialogue

QTheaterHotWord →
    "leikhús"
    | "þjóðleikhúsið"
    | "þjóðleikhús"
    | 'Þjóðleikhúsið'
    | 'Þjóðleikhús'
    | QTheaterEgVil? "kaupa" "leikhúsmiða"
    | QTheaterEgVil? "fara" "í" "leikhús"
    | QTheaterEgVil? "fara" "á" "leikhússýningu"

QTheaterDialogue → 
    QTheaterShowQuery
    | QTheaterShowDateQuery
    | QTheaterShowSeatCountQuery
    | QTheaterShowLocationQuery
    | QTheaterOptions
    | QYes
    | QNo
    | QCancel
    # TODO: Hvað er í boði, ég vil sýningu X, dagsetningu X, X mörg sæti, staðsetningu X

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
    "hvaða" "raðir" "eru" "í" "boði"
    | "hvaða" "röð" "er" "í" "boði"
    | "hvaða" "bekkir" "eru" "í" "boði"
    | "hvaða" "bekkur" "er" "í" "boði"

QTheaterSeatOptions →
    "hvaða" "sæti" "eru" "í" "boði"
    "hverjir" "eru" "sæta" "valmöguleikarnir"

QTheaterShowQuery → QTheaterEgVil? "velja" 'sýning' QTheaterShowName 
    > QTheaterEgVil? "fara" "á" 'sýning' QTheaterShowName
    > QTheaterShowName

QTheaterShowName → Nl

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

QTheaterShowSeatCountQuery →
    QTheaterEgVil? "fá"? QNum "sæti"?

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
    QTheaterRodBekk? "númer"? QNum
    | QNum "bekk"
    | QNum "röð"

QTheaterShowSeats →
    QTheaterEgVil? "sæti"? "númer"? QNum "til"? QNum? 

QTheaterDateOptions → 
    "hvaða" "dagsetningar" "eru" "í" "boði"

QTheaterRodBekk → "röð" | "bekk"

QTheaterEgVil →
    "ég"? "vil"
    | "ég" "vill"
    | "mig" "langar" "að"
    | "mig" "langar" "í"

QNum →
    # to is a declinable number word ('tveir/tvo/tveim/tveggja')
    # töl is an undeclinable number word ('sautján')
    # tala is a number ('17')
    to | töl | tala

QYes → "já" "já"* | "endilega" | "já" "takk" | "játakk" | "já" "þakka" "þér" "fyrir" | "já" "takk" "kærlega" "fyrir"? | "jább" "takk"?

QNo → "nei" "takk"? | "nei" "nei"* | "neitakk" | "ómögulega"

QCancel → "ég" "hætti" "við"
    | QTheaterEgVil "hætta" "við" "pöntunina"
    | QTheaterEgVil "hætta" "við" "pöntunina"

"""

# QLocationRowFirst →
#     "bekkur" QNum "sæti" QNum "til"? QNum
#     | "röð" QNum "sæti" QNum "til"? QNum

# QLocationSeatsFirst →
#     "ég"? "vil"? "sæti"? QNum "til"? QNum "í" "röð" QNum
#     | "ég"? "vil"? "sæti"? QNum "til"? QNum "í" QNum "röð"
#     | "ég"? "vil"? "sæti"? QNum "til"? QNum "á" "bekk" QNum
#     | "ég"? "vil"? "sæti"? QNum "til"? QNum "á" QNum "bekk"

_SHOWS = [
    {
        "title": "Emil í Kattholti",
        "date": [
            datetime.datetime(2022, 8, 27, 13, 0),
            datetime.datetime(2022, 8, 28, 13, 0),
            datetime.datetime(2022, 8, 28, 17, 0),
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
]


def _generate_show_answer(
    resource: ListResource, dsm: DialogueStateManager
) -> Optional[str]:
    result = dsm.get_result()
    print("Generate show answer")
    if (not resource.is_confirmed and result.get("options_info")) or result.get(
        "show_options"
    ):
        shows: list[str] = []
        for show in _SHOWS:
            shows.append(show["title"])
        return resource.prompts["options"].format(options=", ".join(shows))
    if result.get("no_show_matched"):
        return resource.prompts["no_show_matched"]
    if result.get("no_show_matched_data_exists"):
        return resource.prompts["no_show_matched_data_exists"].format(
            show=resource.data[0]
        )
    if resource.is_unfulfilled:
        return resource.prompts["initial"]
    if resource.is_fulfilled:
        return resource.prompts["confirm"].format(show=resource.data[0])
    return None


def _generate_date_answer(
    resource: ListResource, dsm: DialogueStateManager
) -> Optional[str]:
    print("Generating date answer")
    result = dsm.get_result()
    title = dsm.get_resource("Show").data[0]

    if (not resource.is_confirmed and result.get("options_info")) or result.get(
        "date_options"
    ):
        dates: list[str] = []
        for show in _SHOWS:
            if show["title"] == title:
                for date in show["date"]:
                    dates.append(date.strftime("    %d/%m/%Y klukkan %H:%M\n"))
        date_number: int = 3 if len(dates) >= 3 else len(dates)
        options_string: str = (
            "Eftirfarandi dagsetning er í boði:\n"
            if date_number == 1
            else "Næstu tvær dagsetningar eru:\n"
            if date_number == 2
            else "Næstu þrjár dagsetningar eru:\n"
        )
        options_string += "".join(dates)
        if len(dates) > 0:
            return resource.prompts["options"].format(options=options_string)
        else:
            return resource.prompts["no_date_available"].format(show=title)
    if result.get("no_date_matched"):
        return resource.prompts["no_date_matched"]
    if result.get("no_time_matched"):
        return resource.prompts["no_time_matched"]
    if result.get("many_matching_times"):
        return resource.prompts["many_matching_times"]
    if result.get("multiple_times_for_date"):
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
                            show_times.append(date.strftime("    %H:%M\n"))
            return resource.prompts["multiple_times_for_date"].format(
                date=show_date, times="".join(show_times)
            )
    if resource.is_unfulfilled:
        title: str = dsm.get_resource("Show").data[0]
        dates: list[str] = []
        for show in _SHOWS:
            if show["title"] == title:
                for date in show["date"]:
                    dates.append(date.strftime("    %d/%m/%Y klukkan %H:%M\n"))
        date_number: int = 3 if len(dates) >= 3 else len(dates)
        start_string: str = (
            "Eftirfarandi dagsetning er í boði:\n"
            if date_number == 1
            else "Næstu tvær dagsetningar eru:\n"
            if date_number == 2
            else "Næstu þrjár dagsetningar eru:\n"
        )
        if len(dates) > 0:
            return resource.prompts["initial"].format(
                show=title,
                dates=start_string + "".join(dates),
            )
        else:
            return resource.prompts["no_date_available"].format(show=title)
    if resource.is_fulfilled:
        date_resource = dsm.get_resource("ShowDate")
        time_resource = dsm.get_resource("ShowTime")
        return resource.prompts["confirm"].format(
            date=datetime.datetime.combine(
                date_resource.data,
                time_resource.data,
            ).strftime("%Y/%m/%d %H:%M")
        )


def _generate_seat_count_answer(
    resource: ListResource, dsm: DialogueStateManager
) -> Optional[str]:
    if resource.is_unfulfilled:
        return resource.prompts["initial"]
    if resource.is_fulfilled:
        return resource.prompts["confirm"].format(
            seats=number_to_text(cast(int, resource.data))
        )


def _generate_row_answer(
    resource: ListResource, dsm: DialogueStateManager
) -> Optional[str]:
    print("Generating row answer")
    result = dsm.get_result()
    title: str = dsm.get_resource("Show").data[0]
    seats: int = dsm.get_resource("ShowSeatCount").data
    available_rows: list[str] = []
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
                        seats_in_row = 0
                        row_added = row
                else:
                    checking_row = row
                    seats_in_row = 1
    available_row_strings: list[str] = []
    if (not resource.is_confirmed and result.get("options_info")) or result.get(
        "row_options"
    ):
        return resource.prompts["options"].format(
            rows=natlang_seq(available_rows), seats=number_to_text(seats)
        )
    if result.get("no_row_matched"):
        return resource.prompts["no_row_matched"].format(seats=number_to_text(seats))
    if resource.is_unfulfilled:
        if len(available_rows) == 0:
            return resource.prompts["not_enough_seats"].format(seats=seats)
        return resource.prompts["initial"].format(
            seats=number_to_text(seats), seat_rows=natlang_seq(available_rows)
        )
    if resource.is_fulfilled:
        row = dsm.get_resource("ShowSeatRow").data[0]
        return resource.prompts["confirm"].format(row=number_to_text(row))


def _generate_seat_number_answer(
    resource: ListResource, dsm: DialogueStateManager
) -> Optional[str]:
    print("_generate_seat_number_answer", resource.state)
    result = dsm.get_result()
    title: str = dsm.get_resource("Show").data[0]
    seats: int = dsm.get_resource("ShowSeatCount").data
    chosen_row: int = dsm.get_resource("ShowSeatRow").data[0]
    available_seats: list[str] = []
    for show in _SHOWS:
        if show["title"] == title:
            for (row, seat) in show["location"]:
                if chosen_row == row:
                    available_seats.append(number_to_text(seat))
    if (not resource.is_confirmed and result.get("options_info")) or result.get(
        "seat_options"
    ):
        return resource.prompts["options"].format(
            row=number_to_text(chosen_row), options=natlang_seq(available_seats)
        )
    if result.get("wrong_number_seats_selected"):
        print("wrong_number_seats_selected prompt")
        chosen_seats = len(
            range(result.get("numbers")[0], result.get("numbers")[1] + 1)
        )
        return resource.prompts["wrong_number_seats_selected"].format(
            chosen_seats=number_to_text(chosen_seats), seats=number_to_text(seats)
        )
    if result.get("seats_unavailable"):
        print("seats_unavailable prompt")
        return resource.prompts["seats_unavailable"]
    if resource.is_unfulfilled:
        print("initial prompt")
        return resource.prompts["initial"].format(
            seats=natlang_seq(available_seats), row=number_to_text(chosen_row)
        )
    if resource.is_fulfilled:
        print("confirm prompt")
        chosen_seats_string: str = ""
        if seats > 1:
            chosen_seats_string = "{first_seat} til {last_seat}".format(
                first_seat=number_to_text(result.get("numbers")[0]),
                last_seat=number_to_text(result.get("numbers")[1]),
            )
        else:
            chosen_seats_string = number_to_text(result.get("numbers")[0])
        return resource.prompts["confirm"].format(seats=chosen_seats_string)


def _generate_final_answer(
    resource: ListResource, dsm: DialogueStateManager
) -> Optional[str]:
    if resource.is_cancelled:
        return resource.prompts["cancelled"]

    resource.state = ResourceState.CONFIRMED
    title = dsm.get_resource("Show").data[0]
    date = cast(DateResource, dsm.get_resource("ShowDate")).data
    time = cast(TimeResource, dsm.get_resource("ShowTime")).data
    number_of_seats = cast(NumberResource, dsm.get_resource("ShowSeatCount")).data
    seats = dsm.get_resource("ShowSeatNumber").data
    seat_string: str = ""
    if number_of_seats > 1:
        seat_string = "{first_seat} til {last_seat}".format(
            first_seat=number_to_text(seats[0]),
            last_seat=number_to_text(seats[-1]),
        )
    else:
        seat_string = number_to_text(seats[0])
    row = dsm.get_resource("ShowSeatRow").data[0]
    ans = resource.prompts["final"].format(
        seats=seat_string,
        row=number_to_text(row),
        show=title,
        date_time=datetime.datetime.combine(
            date,
            time,
        ).strftime("%Y/%m/%d %H:%M"),
    )
    return ans


def QTheaterDialogue(node: Node, params: QueryStateDict, result: Result) -> None:
    result.qtype = _THEATER_QTYPE


def QTheaterHotWord(node: Node, params: QueryStateDict, result: Result) -> None:
    result.qtype = _START_DIALOGUE_QTYPE


def QTheaterShowQuery(node: Node, params: QueryStateDict, result: Result) -> None:
    def _add_show(
        resource: Resource, dsm: DialogueStateManager, result: Result
    ) -> None:
        selected_show: str = dsm.get_result().show_name
        show_exists = False
        for show in _SHOWS:
            if show["title"] == selected_show:
                resource.data = [show["title"]]
                resource.state = ResourceState.FULFILLED
                show_exists = True
                break
        if not show_exists:
            if resource.is_unfulfilled:
                result.no_show_matched = True
            if resource.is_fulfilled:
                result.no_show_matched_data_exists = True

    if "callbacks" not in result:
        result["callbacks"] = []
    filter_func: Callable[[Resource], bool] = lambda r: r.name == "Show"
    result.callbacks.append((filter_func, _add_show))


def _date_callback(
    resource: DateResource, dsm: DialogueStateManager, result: Result
) -> None:
    resource.state = ResourceState.UNFULFILLED
    print("In date callback")
    if dsm.get_resource("Show").is_confirmed:
        print("Show was confirmed")
        show_title: str = dsm.get_resource("Show").data[0]
        for show in _SHOWS:
            if show["title"] == show_title:
                for date in show["date"]:
                    if result["show_date"] == date.date():
                        resource.set_date(date.date())
                        resource.state = ResourceState.FULFILLED
                        break
        time_resource: TimeResource = cast(TimeResource, dsm.get_resource("ShowTime"))
        datetime_resource: Resource = dsm.get_resource("ShowDateTime")
        if time_resource.is_fulfilled:
            print("Time resource was fulfilled")
            datetime_resource.state = ResourceState.FULFILLED
        else:
            print("Time resource not fulfilled, trying to add time")
            show_times: list[datetime.time] = []
            for show in _SHOWS:
                if show["title"] == show_title:
                    for date in show["date"]:
                        print("Date: ", date)
                        print("Time: ", date.time())
                        print("Resource date: ", resource.date)
                        print("Date date: ", date.date())
                        print("if: ", date.date() == resource.date)
                        if resource.date == date.date():
                            print(
                                "Adding showtime: ", date.time(), " fyrir date: ", date
                            )
                            show_times.append(date.time())
            print("Show times: ", show_times)
            if len(show_times) == 0:
                print("No show times found")
                result.no_date_matched = True
                return
            if len(show_times) == 1:
                time_resource.set_time(show_times[0])
                time_resource.state = ResourceState.FULFILLED
                datetime_resource.state = ResourceState.FULFILLED
                print("One show time")
            else:
                result.multiple_times_for_date = True
                print("Many showtimes", show_times)
                datetime_resource.state = ResourceState.PARTIALLY_FULFILLED


def _time_callback(
    resource: TimeResource, dsm: DialogueStateManager, result: Result
) -> None:
    resource.state = ResourceState.UNFULFILLED
    if result.get("no_date_matched"):
        return
    if dsm.get_resource("Show").is_confirmed:
        show_title: str = dsm.get_resource("Show").data[0]
        date_resource: DateResource = cast(DateResource, dsm.get_resource("ShowDate"))
        datetime_resource: Resource = dsm.get_resource("ShowDateTime")
        first_matching_date: Optional[datetime.datetime] = None
        if date_resource.is_fulfilled:
            for show in _SHOWS:
                if show["title"] == show_title:
                    for date in show["date"]:
                        if (
                            date_resource.date == date.date()
                            and result["show_time"] == date.time()
                        ):
                            first_matching_date = cast(datetime.datetime, date)
                            print("Time callback, date there, setting time")
                            resource.set_time(date.time())
                            resource.state = ResourceState.FULFILLED
                            break
            if resource.is_fulfilled:
                datetime_resource.state = ResourceState.FULFILLED
            else:
                result.wrong_show_time = True
        else:
            for show in _SHOWS:
                if show["title"] == show_title:
                    for date in show["date"]:
                        if result["show_time"] == date.time():
                            if first_matching_date is None:
                                first_matching_date = cast(datetime.datetime, date)
                            else:
                                result.many_matching_times = True
                                return
            if first_matching_date is not None:
                date_resource: DateResource = cast(
                    DateResource, dsm.get_resource("ShowDate")
                )
                date_resource.set_date(first_matching_date.date())
                date_resource.state = ResourceState.FULFILLED
                resource.set_time(first_matching_date.time())
                resource.state = ResourceState.FULFILLED
                datetime_resource.state = ResourceState.FULFILLED
        if first_matching_date is None:
            result.no_time_matched = True


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

    if "callbacks" not in result:
        result["callbacks"] = []
    result.callbacks.append((lambda r: r.name == "ShowDate", _date_callback))
    result.callbacks.append((lambda r: r.name == "ShowTime", _time_callback))


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

            if "callbacks" not in result:
                result["callbacks"] = []
            filter_func: Callable[[Resource], bool] = lambda r: r.name == "ShowDate"
            result.callbacks.append((filter_func, _date_callback))
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

        if "callbacks" not in result:
            result["callbacks"] = []
        filter_func: Callable[[Resource], bool] = lambda r: r.name == "ShowTime"
        result.callbacks.append((filter_func, _time_callback))


def QTheaterDateOptions(node: Node, params: QueryStateDict, result: Result) -> None:
    result.date_options = True


def QTheaterShowSeatCountQuery(
    node: Node, params: QueryStateDict, result: Result
) -> None:
    def _add_seat_number(
        resource: NumberResource, dsm: DialogueStateManager, result: Result
    ) -> None:
        if dsm.get_resource("ShowDateTime").is_confirmed:
            print("Number count resource data: ", resource.data)
            resource.data = result.number
            print("Result.number: ", result.number)
            resource.state = ResourceState.FULFILLED

    if "callbacks" not in result:
        result["callbacks"] = []
    filter_func: Callable[[Resource], bool] = lambda r: r.name == "ShowSeatCount"
    result.callbacks.append((filter_func, _add_seat_number))


def QLocationSeatsFirst(node: Node, params: QueryStateDict, result: Result) -> None:
    # Making sure that the row comes before the seats in the list
    result.numbers.insert(0, result.numbers.pop())
    print("Result numbers: ", result.numbers)


def QTheaterShowRow(node: Node, params: QueryStateDict, result: Result) -> None:
    def _add_row(
        resource: ListResource, dsm: DialogueStateManager, result: Result
    ) -> None:
        if dsm.get_resource("ShowSeatCount").is_confirmed:
            title: str = dsm.get_resource("Show").data[0]
            seats: int = dsm.get_resource("ShowSeatCount").data
            available_rows: list[str] = []
            for show in _SHOWS:
                if show["title"] == title:
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
            print("Add row: ", result.number)
            print("Available rows: ", available_rows)
            if result.number in available_rows:
                print("Appending row")
                resource.data = [result.number]
                resource.state = ResourceState.FULFILLED
            else:
                print("Emptying row data")
                resource.data = []
                resource.state = ResourceState.UNFULFILLED
                result.no_row_matched = True

    if "callbacks" not in result:
        result["callbacks"] = []
    filter_func: Callable[[Resource], bool] = lambda r: r.name == "ShowSeatRow"
    result.callbacks.append((filter_func, _add_row))


def QTheaterShowSeats(node: Node, params: QueryStateDict, result: Result) -> None:
    def _add_seats(
        resource: ListResource, dsm: DialogueStateManager, result: Result
    ) -> None:
        if dsm.get_resource("ShowSeatRow").is_confirmed:
            print("Add seats callback, state: ", resource.state)
            title: str = dsm.get_resource("Show").data[0]
            print("Row data: ", dsm.get_resource("ShowSeatRow").data)
            row: int = dsm.get_resource("ShowSeatRow").data[0]
            number_of_seats: int = dsm.get_resource("ShowSeatCount").data
            print("Result.numbers: ", len(result.numbers))
            selected_seats: list[int] = []
            if number_of_seats > 1:
                selected_seats = [
                    seat for seat in range(result.numbers[0], result.numbers[1] + 1)
                ]
            else:
                print("Result.numbers: ", result.numbers)
                print("Result.number: ", result.number)
                selected_seats = [result.numbers[0]]
            print("Selected seats: ", selected_seats)
            if len(selected_seats) != number_of_seats:
                print("Selected seats does not match number of seats")
                print("Resource name that is being emptied: ", resource.name)
                resource.data = []
                resource.state = ResourceState.UNFULFILLED
                result.wrong_number_seats_selected = True
                return
            for show in _SHOWS:
                if show["title"] == title:
                    seats: list[int] = []
                    for seat in selected_seats:
                        if (row, seat) in show["location"]:
                            seats.append(seat)
                        else:
                            print("Seat unavailable")
                            resource.data = []
                            resource.state = ResourceState.UNFULFILLED
                            result.seats_unavailable = True
                            return
                    resource.data = []
                    for seat in seats:
                        resource.data.append(seat)
            print("Length of data: ", len(resource.data))
            if len(resource.data) > 0:
                print("Setting state to fulfilled")
                resource.state = ResourceState.FULFILLED

    if "callbacks" not in result:
        result["callbacks"] = []
    filter_func: Callable[[Resource], bool] = lambda r: r.name == "ShowSeatNumber"
    result.callbacks.append((filter_func, _add_seats))


def QTheaterGeneralOptions(node: Node, params: QueryStateDict, result: Result) -> None:
    print("QTheaterGeneralOptions")
    result.options_info = True


def QTheaterShowOptions(node: Node, params: QueryStateDict, result: Result) -> None:
    print("QTheaterShowOptions")
    result.show_options = True


def QTheaterDateOptions(node: Node, params: QueryStateDict, result: Result) -> None:
    print("QTheaterDateOptions")
    result.date_options = True


def QTheaterRowOptions(node: Node, params: QueryStateDict, result: Result) -> None:
    result.row_options = True


def QTheaterSeatOptions(node: Node, params: QueryStateDict, result: Result) -> None:
    result.seat_options = True


def QTheaterShowName(node: Node, params: QueryStateDict, result: Result) -> None:
    result.show_name = (
        " ".join(result._text.split()[1:])
        if result._text.startswith("sýning")
        else result._text
    )


def QNum(node: Node, params: QueryStateDict, result: Result):
    number: int = int(parse_num(node, result._nominative))
    if "numbers" not in result:
        result["numbers"] = []
    result.numbers.append(number)
    result.number = number


def QCancel(node: Node, params: QueryStateDict, result: Result):
    def _cancel_order(
        resource: Resource, dsm: DialogueStateManager, result: Result
    ) -> None:
        resource.state = ResourceState.CANCELLED

    result.qtype = "QCancel"
    if "callbacks" not in result:
        result["callbacks"] = []
    filter_func: Callable[[Resource], bool] = lambda r: r.name == "Final"
    result.callbacks.append((filter_func, _cancel_order))


def QYes(node: Node, params: QueryStateDict, result: Result):
    def _parse_yes(
        resource: Resource, dsm: DialogueStateManager, result: Result
    ) -> None:
        if "yes_used" not in result and resource.is_fulfilled:
            print("YES USED", resource.name, " confirming")
            resource.state = ResourceState.CONFIRMED
            result.yes_used = True
            if resource.name == "ShowDateTime":
                for rname in resource.requires:
                    dsm.get_resource(rname).state = ResourceState.CONFIRMED

    if "callbacks" not in result:
        result["callbacks"] = []
    filter_func: Callable[[Resource], bool] = (
        lambda r: r.name
        in ("Show", "ShowDateTime", "ShowSeatCount", "ShowSeatRow", "ShowSeatNumber")
        and not r.is_confirmed
    )
    result.callbacks.append((filter_func, _parse_yes))


def QNo(node: Node, params: QueryStateDict, result: Result):
    def _parse_no(
        resource: Resource, dsm: DialogueStateManager, result: Result
    ) -> None:
        if "no_used" not in result and resource.is_fulfilled:
            resource.state = ResourceState.UNFULFILLED
            result.no_used = True
            if resource.name == "ShowDateTime":
                dsm.get_resource("ShowDate").state = ResourceState.UNFULFILLED
                dsm.get_resource("ShowTime").state = ResourceState.UNFULFILLED

    if "callbacks" not in result:
        result["callbacks"] = []
    filter_func: Callable[[Resource], bool] = (
        lambda r: r.name
        in ("Show", "ShowDateTime", "ShowSeatCount", "ShowSeatRow", "ShowSeatNumber")
        and not r.is_confirmed
    )
    result.callbacks.append((filter_func, _parse_no))


SHOW_URL = "https://leikhusid.is/wp-json/shows/v1/categories/938"


def _fetch_shows() -> Any:
    resp = query_json_api(SHOW_URL)
    if resp:
        assert isinstance(resp, list)
        return [s["title"] for s in resp]


_ANSWERING_FUNCTIONS = {
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
    dsm: DialogueStateManager = DialogueStateManager(
        _THEATER_DIALOGUE_NAME, _START_DIALOGUE_QTYPE, q, result
    )
    if dsm.not_in_dialogue():
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
        return

    try:
        print("A")
        result.shows = _fetch_shows()
        dsm.setup_dialogue(_ANSWERING_FUNCTIONS)
        if result.qtype == _START_DIALOGUE_QTYPE:
            print("B")
            dsm.start_dialogue()
        print("C")
        print(dsm._resources)
        ans = dsm.get_answer()
        if "show_options" not in result:
            q.query_is_command()
        print("D")
        if not ans:
            print("No answer generated")
            q.set_error("E_QUERY_NOT_UNDERSTOOD")
            return

        q.set_qtype(result.qtype)
        q.set_answer(*gen_answer(ans))
    except Exception as e:
        logging.warning("Exception while processing random query: {0}".format(e))
        q.set_error("E_EXCEPTION: {0}".format(e))
        raise
