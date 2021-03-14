"""

    Greynir: Natural language processing for Icelandic

    Telephony query response module

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
    along with this program.  If not, see http://www.gnu.org/licenses/.


    This module is an example of a plug-in query response module
    for the Greynir query subsystem. It handles plain text queries, i.e.
    ones that do not require parsing the query text. For this purpose
    it only needs to implement the handle_plain_text() function, as
    shown below.


    This module handles telephony-related queries.

"""

import re
import random

from query import Query

_TELEPHONE_QTYPE = "Telephone"


TOPIC_LEMMAS = ["hringja", "símanúmer", "sími"]


def help_text(lemma: str) -> str:
    """ Help text to return when query.py is unable to parse a query but
        one of the above lemmas is found in it """
    return "Ég get hringt ef þú segir til dæmis: {0}".format(
        random.choice(("Hringdu í 18 18", "Hringdu í 18 19"))
    )


# # This module wants to handle parse trees for queries,
# HANDLE_TREE = True

# # The context-free grammar for the queries recognized by this plug-in module
# GRAMMAR = """

# Query →
#     QTel

# QTel → QTelQuery '?'?

# QTelQuery →
#     QTelCmd QTelNumPrep QTelPhoneNumberNoun? QTelPhoneNumber

# QTelPhoneNumberNoun →
#     "síma" | "símanúmer" | "símanúmerið" | "númer" | "númerið"

# QTelNumPrep →
#     "í"

# # QTelPhoneNumber →
# # To be implemented

# QTelCmd →
#     "hringdu"
#     | "hringdu" "fyrir" mig"
#     | "værirðu" "til" "í" "að" "hringja"
#     | "værir" "þú" "til" "í" "að" "hringja"
#     | "geturðu" "hringt"
#     | "getur" "þú" "hringt"
#     | "nennirðu" "að" "hringja"
#     | "nennir" "þú" "að" "hringja"
#     | "vinsamlegast" "hringdu"

# """

# TODO: This should be moved over to grammar at some point, too many manually defined,
# almost identical commands. But at the moment, the grammar has poor support for phone
# numbers, especially  when the numbers are coming out of a speech recognition engine
# This module should also be able to handle natural language number words.
_PHONECALL_REGEXES = frozenset(
    (
        r"(hringdu í )([\d|\-|\s]+)$",
        r"(hringdu í síma )([\d|\-|\s]+)$",
        r"(hringdu í símanúmer )([\d|\-|\s]+)$",
        r"(hringdu í símanúmerið )([\d|\-|\s]+)$",
        r"(hringdu í númer )([\d|\-|\s]+)$",
        r"(hringdu í númerið )([\d|\-|\s]+)$",
        r"(hringdu fyrir mig í )([\d|\-|\s]+)$",
        r"(hringdu fyrir mig í síma )([\d|\-|\s]+)$",
        r"(hringdu fyrir mig í símanúmer )([\d|\-|\s]+)$",
        r"(hringdu fyrir mig í símanúmerið )([\d|\-|\s]+)$",
        r"(hringdu fyrir mig í númer )([\d|\-|\s]+)$",
        r"(hringdu fyrir mig í númerið )([\d|\-|\s]+)$",
        r"(værirðu til í að hringja í síma )([\d|\-|\s]+)$",
        r"(værirðu til í að hringja í símanúmer )([\d|\-|\s]+)$",
        r"(værirðu til í að hringja í símanúmerið )([\d|\-|\s]+)$",
        r"(værirðu til í að hringja í númer )([\d|\-|\s]+)$",
        r"(værirðu til í að hringja í númerið )([\d|\-|\s]+)$",
        r"(værir þú til í að hringja í síma )([\d|\-|\s]+)$",
        r"(værir þú til í að hringja í símanúmer )([\d|\-|\s]+)$",
        r"(værir þú til í að hringja í símanúmerið )([\d|\-|\s]+)$",
        r"(værir þú til í að hringja í númer )([\d|\-|\s]+)$",
        r"(værir þú til í að hringja í númerið )([\d|\-|\s]+)$",
        r"(geturðu hringt í )([\d|\-|\s]+)$",
        r"(geturðu hringt í síma )([\d|\-|\s]+)$",
        r"(geturðu hringt í símanúmer )([\d|\-|\s]+)$",
        r"(geturðu hringt í símanúmerið )([\d|\-|\s]+)$",
        r"(geturðu hringt í númerið )([\d|\-|\s]+)$",
        r"(geturðu hringt í númer )([\d|\-|\s]+)$",
        r"(getur þú hringt í )([\d|\-|\s]+)$",
        r"(getur þú hringt í síma )([\d|\-|\s]+)$",
        r"(getur þú hringt í símanúmer )([\d|\-|\s]+)$",
        r"(getur þú hringt í símanúmerið )([\d|\-|\s]+)$",
        r"(getur þú hringt í númerið )([\d|\-|\s]+)$",
        r"(getur þú hringt í númer )([\d|\-|\s]+)$",
        r"(nennirðu að hringja í )([\d|\-|\s]+)$",
        r"(nennirðu að hringja í síma )([\d|\-|\s]+)$",
        r"(nennirðu að hringja í símanúmer )([\d|\-|\s]+)$",
        r"(nennirðu að hringja í símanúmerið )([\d|\-|\s]+)$",
        r"(nennirðu að hringja í númerið )([\d|\-|\s]+)$",
        r"(nennirðu að hringja í númer )([\d|\-|\s]+)$",
        r"(nennir þú að hringja í )([\d|\-|\s]+)$",
        r"(nennir þú að hringja í síma )([\d|\-|\s]+)$",
        r"(nennir þú að hringja í símanúmer )([\d|\-|\s]+)$",
        r"(nennir þú að hringja í símanúmerið )([\d|\-|\s]+)$",
        r"(nennir þú að hringja í númerið )([\d|\-|\s]+)$",
        r"(nennir þú að hringja í númer )([\d|\-|\s]+)$",
        r"(vinsamlegast hringdu í )([\d|\-|\s]+)$",
        r"(vinsamlegast hringdu í síma )([\d|\-|\s]+)$",
    )
)


def handle_plain_text(q: Query) -> bool:
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
