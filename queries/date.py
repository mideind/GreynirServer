"""

    Reynir: Natural language processing for Icelandic

    Date query response module

    Copyright (C) 2019 Miðeind ehf.

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

# TODO: Fix pronunciation of ordinal day of month (i.e. "29di" vs "29da")

from datetime import datetime
from pytz import timezone

from queries import timezone4loc
from settings import changedlocale


_DATE_QTYPE = "Date"

_DATE_QUERIES = frozenset(
    (
        "hvað er dagsetningin",
        "hver er dagsetningin",
        "hvaða dagsetning er í dag",
        "hver er dagsetningin í dag",
        "hver er dagurinn í dag",
        "hvaða dagur er í dag",
        "hvaða mánaðardagur er í dag",
        "hver er mánaðardagurinn í dag",
        "hvaða vikudagur er í dag",
    )
)


def handle_plain_text(q):
    """ Handle a plain text query asking about the current date/weekday. """
    ql = q.query_lower.rstrip("?")

    if ql in _DATE_QUERIES:
        tz = timezone4loc(q.location, fallback="IS")
        now = datetime.now(timezone(tz))

        with changedlocale(category="LC_TIME"):
            date_str = now.strftime("%A %-d. %B %Y")

            voice = "Í dag er {0}".format(date_str)
            answer = date_str.capitalize()
            response = dict(answer=answer)

            q.set_answer(response, answer, voice)
            q.set_qtype(_DATE_QTYPE)

        return True

    return False
