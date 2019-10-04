"""

    Reynir: Natural language processing for Icelandic

    Telephony query response module

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


    This module handles telephony-related queries.

"""

import re

_TELEPHONE_QTYPE = "Telephone"

_PHONECALL_REGEXES = frozenset(
    (
        r"(hringdu í )([\d|\-|\s]+)",
        r"(hringdu í síma )([\d|\-|\s]+)",
        r"(hringdu í símanúmerið )([\d|\-|\s]+)",
        r"(hringdu í númerið )([\d|\-|\s]+)",
        r"(hringdu í númer )([\d|\-|\s]+)",
    )
)


def handle_plain_text(q):
    """ Handle a plain text query requesting a call to a telephone number. """
    ql = q.query_lower.rstrip("?")

    pfx = None
    number = None

    for rx in _PHONECALL_REGEXES:
        m = re.search(rx, ql)
        if m:
            pfx = m.group(1)
            number = m.group(2)
            break
    else:
        return False

    # At this point we have a phone number.
    # Sanitize by removing all non-numeric characters.
    number = re.sub(r"[^0-9]", "", number)
    tel_url = "tel:{0}".format(number)

    voice = ""
    answer = "Skal gert"
    response = dict(answer=answer)

    q.set_beautified_query("{0}{1}".format(pfx, number))
    q.set_answer(response, answer, voice)
    q.set_qtype(_TELEPHONE_QTYPE)
    q.set_url(tel_url)

    return True

