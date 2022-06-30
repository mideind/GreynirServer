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
from queries.num import number_to_neutral
from queries.dialogue import (
    DateResource,
    DialogueStateManager,
    ListResource,
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
    | QTheaterShowOptions
    | QYes
    | QNo
    | QCancel
    # TODO: Hvað er í boði, ég vil sýningu X, dagsetningu X, X mörg sæti, staðsetningu X

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
    "röð"? QNum
    | "bekk" QNum
    | QNum "bekk"
    | QNum "röð"

QTheaterShowSeats →
    QTheaterEgVil? "sæti"? QNum "til" QNum 

QTheaterShowOptions → "sýningar" 
    | "hvaða" "sýningar" "eru" "í" "boði"
    | "hvað" "er" "í" "boði"
    | "hverjir"? "eru"? "valmöguleikarnir"
    | "hvert" "er" "úrvalið"

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
    if result.get("show_options"):
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
    result = dsm.get_result()
    if result.get("dateOptions"):
        return resource.prompts["options"]
    if result.get("no_date_matched"):
        return resource.prompts["no_date_matched"]
    if result.get("no_time_matched"):
        return resource.prompts["no_time_matched"]
    if result.get("many_matching_times"):
        return resource.prompts["many_matching_times"]
    if result.get("multiple_times_for_date"):
        title = dsm.get_resource("Show").data[0]
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
        return resource.prompts["initial"].format(
            show=title,
            dates=start_string + "".join(dates),
        )
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
        return resource.prompts["confirm"].format(seats=resource.data[0])


def _generate_row_answer(
    resource: ListResource, dsm: DialogueStateManager
) -> Optional[str]:
    result = dsm.get_result()
    title: str = dsm.get_resource("Show").data[0]
    seats: int = dsm.get_resource("ShowSeatCount").data[0]
    available_rows: list[str] = []
    for show in _SHOWS:
        if show["title"] == title:
            checking_row: int = 1
            seats_in_row: int = 0
            for (row, _) in show["location"]:
                if checking_row == row:
                    seats_in_row += 1
                    if seats_in_row >= seats:
                        available_rows.append(str(row))
                        seats_in_row = 0
                else:
                    checking_row = row
                    seats_in_row = 1
    for index, row in enumerate(available_rows):
        available_rows[index] = number_to_neutral(row)
    if result.get("rowOptions"):
        return resource.prompts["options"].format(rows=available_rows, seats=seats)
    if result.get("no_row_matched"):
        return resource.prompts["no_row_matched"].format(seats=seats)
    if resource.is_unfulfilled:
        return resource.prompts["initial"].format(
            seats=number_to_neutral(seats), seat_rows=natlang_seq(available_rows)
        )
    if resource.is_fulfilled:
        row = dsm.get_resource("ShowSeatRow").data[0]
        return resource.prompts["confirm"].format(row=number_to_neutral(row))


def _generate_seat_number_answer(
    resource: ListResource, dsm: DialogueStateManager
) -> Optional[str]:
    print("_generate_seat_number_answer", resource.state)
    result = dsm.get_result()
    title: str = dsm.get_resource("Show").data[0]
    seats: int = dsm.get_resource("ShowSeatCount").data[0]
    chosen_row: int = dsm.get_resource("ShowSeatRow").data[0]
    available_seats: list[str] = []
    for show in _SHOWS:
        if show["title"] == title:
            for (row, seat) in show["location"]:
                if chosen_row == row:
                    available_seats.append(number_to_neutral(seat))
    if result.get("seatOptions"):
        return resource.prompts["options"].format(
            row=number_to_neutral(row), options=natlang_seq(available_seats)
        )
    if result.get("wrong_number_seats_selected"):
        print("wrong_number_seats_selected prompt")
        chosen_seats = len(
            range(result.get("numbers")[0], result.get("numbers")[1] + 1)
        )
        return resource.prompts["wrong_number_seats_selected"].format(
            chosen_seats=number_to_neutral(chosen_seats), seats=number_to_neutral(seats)
        )
    if result.get("seats_unavailable"):
        print("seats_unavailable prompt")
        return resource.prompts["seats_unavailable"]
    if resource.is_unfulfilled:
        print("initial prompt")
        return resource.prompts["initial"].format(
            seats=natlang_seq(available_seats), row=number_to_neutral(chosen_row)
        )
    if resource.is_fulfilled:
        print("confirm prompt")
        chosen_seats_string: str = "{first_seat} til {last_seat}".format(
            first_seat=number_to_neutral(result.get("numbers")[0]),
            last_seat=number_to_neutral(result.get("numbers")[1]),
        )
        return resource.prompts["confirm"].format(seats=chosen_seats_string)


def _generate_location_answer(
    resource: ListResource, dsm: DialogueStateManager
) -> Optional[str]:
    result = dsm.get_result()
    seat_resource = dsm.get_resource("ShowSeatCount")
    if result.get("locationOptions"):
        return resource.prompts["options"]
    if resource.is_unfulfilled:
        title: str = dsm.get_resource("Show").data[0]
        seats: int = seat_resource.data[0]
        available_rows: list[str] = []
        for show in _SHOWS:
            if show["title"] == title:
                checking_row: int = 1
                seats_in_row: int = 0
                for (row, seat) in show["location"]:
                    if checking_row == row:
                        seats_in_row += 1
                        if seats_in_row >= seats:
                            available_rows.append(str(row))
                            seats_in_row = 0
                    else:
                        checking_row = row
                        seats_in_row = 1
        for index, row in enumerate(available_rows):
            available_rows[index] = number_to_neutral(row)
        return resource.prompts["initial"].format(
            seats=number_to_neutral(seats), seat_rows=natlang_seq(available_rows)
        )
    if resource.is_fulfilled:
        location_resource = dsm.get_resource("ShowSeatRow")
        number_to_neutral()
        seat_string = "{first_seat} til {last_seat}".format(
            first_seat=number_to_neutral(location_resource.data[0][1]),
            last_seat=number_to_neutral(location_resource.data[-1][1]),
        )
        return resource.prompts["confirm"].format(
            seats=seat_string, row=location_resource.data[0][0]
        )


def _generate_final_answer(
    resource: ListResource, dsm: DialogueStateManager
) -> Optional[str]:
    if resource.is_cancelled:
        return resource.prompts["cancelled"]

    resource.state = ResourceState.CONFIRMED
    title = dsm.get_resource("Show").data[0]
    date = cast(DateResource, dsm.get_resource("ShowDate")).data
    time = cast(TimeResource, dsm.get_resource("ShowTime")).data
    seats = dsm.get_resource("ShowSeatNumber").data
    seat_string: str = "{first_seat} til {last_seat}".format(
        first_seat=number_to_neutral(seats[0]),
        last_seat=number_to_neutral(seats[-1]),
    )
    row = dsm.get_resource("ShowSeatRow").data[0]
    ans = resource.prompts["final"].format(
        seats=seat_string,
        row=row,
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
    else:
        dsm.set_error()


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
                                print("Setting first_matching_date")
                                first_matching_date = cast(datetime.datetime, date)
                            else:
                                print("Result matched many times, returning")
                                result.many_matching_times = True
                                return
            if first_matching_date is not None:
                date_resource: DateResource = cast(
                    DateResource, dsm.get_resource("ShowDate")
                )
                date_resource.set_date(first_matching_date.date())
                resource.set_time(first_matching_date.time())
        if first_matching_date is None:
            result.no_time_matched = True
    else:
        dsm.set_error()


def QTheaterDateTime(node: Node, params: QueryStateDict, result: Result) -> None:
    print("In theater datetime")
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
    result["show_time"] = datetime.time(h, min)
    result["show_date"] = datetime.date(y, m, d)
    print("Show date: ", result["show_date"])
    print("Show time: ", result["show_time"])

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

        result["show_time"] = datetime.time(hour, minute)

        if "callbacks" not in result:
            result["callbacks"] = []
        filter_func: Callable[[Resource], bool] = lambda r: r.name == "ShowTime"
        result.callbacks.append((filter_func, _time_callback))


def QTheaterShowSeatCountQuery(
    node: Node, params: QueryStateDict, result: Result
) -> None:
    def _add_seat_number(
        resource: Resource, dsm: DialogueStateManager, result: Result
    ) -> None:
        resource.data = [result.number]
        resource.state = ResourceState.FULFILLED

    if "callbacks" not in result:
        result["callbacks"] = []
    filter_func: Callable[[Resource], bool] = lambda r: r.name == "ShowSeatCount"
    result.callbacks.append((filter_func, _add_seat_number))


def QTheaterShowLocationQuery(
    node: Node, params: QueryStateDict, result: Result
) -> None:
    """
    print("In QTheaterShowLocationQuery")

    def _add_location(
        resource: ListResource, dsm: DialogueStateManager, result: Result
    ) -> None:
        print("ADD LOCATION CALLBACK")
        for seat in range(result.numbers[1], result.numbers[2] + 1):
            print("Adding seat to list: ", seat)
            resource.data.append((result.numbers[0], seat))
        print("Location data: ", resource.data)
        resource.state = ResourceState.FULFILLED

    if "callbacks" not in result:
        result["callbacks"] = []
    filter_func: Callable[[Resource], bool] = lambda r: r.name == "ShowSeatRow"
    result.callbacks.append((filter_func, _add_location))
    """
    pass


def QLocationSeatsFirst(node: Node, params: QueryStateDict, result: Result) -> None:
    # Making sure that the row comes before the seats in the list
    result.numbers.insert(0, result.numbers.pop())
    print("Result numbers: ", result.numbers)


def QTheaterShowRow(node: Node, params: QueryStateDict, result: Result) -> None:
    def _add_row(
        resource: ListResource, dsm: DialogueStateManager, result: Result
    ) -> None:
        title: str = dsm.get_resource("Show").data[0]
        seats: int = dsm.get_resource("ShowSeatCount").data[0]
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
            resource.data.append(result.number)
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
        print("Add seats callback, state: ", resource.state)
        title: str = dsm.get_resource("Show").data[0]
        print("Row data: ", dsm.get_resource("ShowSeatRow").data)
        row: int = dsm.get_resource("ShowSeatRow").data[0]
        number_of_seats: int = dsm.get_resource("ShowSeatCount").data[0]
        print("Result.numbers: ", len(result.numbers))
        selected_seats: list[int] = [
            seat for seat in range(result.numbers[0], result.numbers[1] + 1)
        ]
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
                        print("Seat not unavailable")
                        resource.data = []
                        resource.state = ResourceState.UNFULFILLED
                        result.seats_unavailable = True
                        return
                for seat in seats:
                    print("Appending seat: ", seat)
                    resource.data.append(seat)
        print("Length of data: ", len(resource.data))
        if len(resource.data) > 0:
            print("Setting state to fulfilled")
            resource.state = ResourceState.FULFILLED

    if "callbacks" not in result:
        result["callbacks"] = []
    filter_func: Callable[[Resource], bool] = lambda r: r.name == "ShowSeatNumber"
    result.callbacks.append((filter_func, _add_seats))


def QTheaterShowOptions(node: Node, params: QueryStateDict, result: Result) -> None:
    result.show_options = True


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
