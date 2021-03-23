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
from queries import gen_answer

from reynir import NounPhrase


_TELEPHONE_QTYPE = "Telephone"


TOPIC_LEMMAS = ["hringja"]


def help_text(lemma: str) -> str:
    """Help text to return when query.py is unable to parse a query but
    one of the above lemmas is found in it"""
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


_CONTEXT_SUBJ = frozenset(
    (
        "hann",
        "hana",
        "hán",
        "það",
        "það númer",
        "þetta",
        "þetta númer",
        "þá",
        "þær",
        "þau",
    )
)

_CONTEXT_RX = "|".join(_CONTEXT_SUBJ)

# TODO: This should be moved over to grammar at some point, too many manually defined,
# almost identical commands. But at the moment, the grammar has poor support for phone
# numbers, especially  when the numbers are coming out of a speech recognition engine
# This module should also be able to handle natural language number words.
_PHONECALL_REGEXES = frozenset(
    (
        # Context-based
        r"^(hringdu í )({0})$".format(_CONTEXT_RX),
        r"^(hringdu fyrir mig í )({0})$".format(_CONTEXT_RX),
        r"^(værirðu til í að hringja í síma )({0})$".format(_CONTEXT_RX),
        r"^(værir þú til í að hringja í síma )({0})$".format(_CONTEXT_RX),
        r"^(geturðu hringt í )({0})$".format(_CONTEXT_RX),
        r"^(getur þú hringt í )({0})$".format(_CONTEXT_RX),
        r"^(nennirðu að hringja í )({0})$".format(_CONTEXT_RX),
        r"^(nennir þú að hringja í )({0})$".format(_CONTEXT_RX),
        r"^(vinsamlegast hringdu í )({0})$".format(_CONTEXT_RX),
        # Named subject
        r"^(hringdu í )([\w|\s]+)",
        r"^(hringdu fyrir mig í )([\w|\s]+)$",
        r"^(værirðu til í að hringja í síma )([\w|\s]+)$",
        r"^(værir þú til í að hringja í síma )([\w|\s]+)$",
        r"^(geturðu hringt í )([\w|\s]+)$",
        r"^(getur þú hringt í )([\w|\s]+)$",
        r"^(nennirðu að hringja í )([\w|\s]+)$",
        r"^(nennir þú að hringja í )([\w|\s]+)$",
        r"^(vinsamlegast hringdu í )([\w|\s]+)$",
        # Tel no specified
        r"^(hringdu í )([\d|\-|\s]+)$",
        r"^(hringdu í síma )([\d|\-|\s]+)$",
        r"^(hringdu í símanúmer )([\d|\-|\s]+)$",
        r"^(hringdu í símanúmerið )([\d|\-|\s]+)$",
        r"^(hringdu í númer )([\d|\-|\s]+)$",
        r"^(hringdu í númerið )([\d|\-|\s]+)$",
        r"^(hringdu fyrir mig í )([\d|\-|\s]+)$",
        r"^(hringdu fyrir mig í síma )([\d|\-|\s]+)$",
        r"^(hringdu fyrir mig í símanúmer )([\d|\-|\s]+)$",
        r"^(hringdu fyrir mig í símanúmerið )([\d|\-|\s]+)$",
        r"^(hringdu fyrir mig í númer )([\d|\-|\s]+)$",
        r"^(hringdu fyrir mig í númerið )([\d|\-|\s]+)$",
        r"^(værirðu til í að hringja í síma )([\d|\-|\s]+)$",
        r"^(værirðu til í að hringja í símanúmer )([\d|\-|\s]+)$",
        r"^(værirðu til í að hringja í símanúmerið )([\d|\-|\s]+)$",
        r"^(værirðu til í að hringja í númer )([\d|\-|\s]+)$",
        r"^(værirðu til í að hringja í númerið )([\d|\-|\s]+)$",
        r"^(værir þú til í að hringja í síma )([\d|\-|\s]+)$",
        r"^(værir þú til í að hringja í símanúmer )([\d|\-|\s]+)$",
        r"^(værir þú til í að hringja í símanúmerið )([\d|\-|\s]+)$",
        r"^(værir þú til í að hringja í númer )([\d|\-|\s]+)$",
        r"^(værir þú til í að hringja í númerið )([\d|\-|\s]+)$",
        r"^(geturðu hringt í )([\d|\-|\s]+)$",
        r"^(geturðu hringt í síma )([\d|\-|\s]+)$",
        r"^(geturðu hringt í símanúmer )([\d|\-|\s]+)$",
        r"^(geturðu hringt í símanúmerið )([\d|\-|\s]+)$",
        r"^(geturðu hringt í númerið )([\d|\-|\s]+)$",
        r"^(geturðu hringt í númer )([\d|\-|\s]+)$",
        r"^(getur þú hringt í )([\d|\-|\s]+)$",
        r"^(getur þú hringt í síma )([\d|\-|\s]+)$",
        r"^(getur þú hringt í símanúmer )([\d|\-|\s]+)$",
        r"^(getur þú hringt í símanúmerið )([\d|\-|\s]+)$",
        r"^(getur þú hringt í númerið )([\d|\-|\s]+)$",
        r"^(getur þú hringt í númer )([\d|\-|\s]+)$",
        r"^(nennirðu að hringja í )([\d|\-|\s]+)$",
        r"^(nennirðu að hringja í síma )([\d|\-|\s]+)$",
        r"^(nennirðu að hringja í símanúmer )([\d|\-|\s]+)$",
        r"^(nennirðu að hringja í símanúmerið )([\d|\-|\s]+)$",
        r"^(nennirðu að hringja í númerið )([\d|\-|\s]+)$",
        r"^(nennirðu að hringja í númer )([\d|\-|\s]+)$",
        r"^(nennir þú að hringja í )([\d|\-|\s]+)$",
        r"^(nennir þú að hringja í síma )([\d|\-|\s]+)$",
        r"^(nennir þú að hringja í símanúmer )([\d|\-|\s]+)$",
        r"^(nennir þú að hringja í símanúmerið )([\d|\-|\s]+)$",
        r"^(nennir þú að hringja í númerið )([\d|\-|\s]+)$",
        r"^(nennir þú að hringja í númer )([\d|\-|\s]+)$",
        r"^(vinsamlegast hringdu í )([\d|\-|\s]+)$",
        r"^(vinsamlegast hringdu í síma )([\d|\-|\s]+)$",
    )
)


def handle_plain_text(q: Query) -> bool:
    """ Handle a plain text query requesting a call to a telephone number. """
    ql = q.query_lower.strip().rstrip("?")

    pfx = None
    number = None

    for rx in _PHONECALL_REGEXES:
        m = re.search(rx, ql)
        if m:
            pfx = m.group(1)
            telsubj = m.group(2).strip()
            break
    else:
        return False

    # Special handling if context
    if telsubj in _CONTEXT_SUBJ:
        ctx = q.fetch_context()
        if ctx is None or "phone_number" not in ctx:
            a = gen_answer("Ég veit ekki við hvern þú átt")
        else:
            q.set_url("tel:{0}".format(ctx["phone_number"]))
            answer = "Skal gert"
            a = (dict(answer=answer), answer, "")
    # Only number digits
    else:
        clean_num = re.sub(r"[^0-9]", "", telsubj).strip()
        if len(clean_num) < 3:
            # The number is clearly not a valid phone number
            a = gen_answer("{0} er ekki gilt símanúmer.".format(number))
        elif re.search(r"^[\d|\s]+$", clean_num):
            # At this point we have what looks like a legitimate phone number.
            # Send tel: url to trigger phone call in client
            q.set_url("tel:{0}".format(clean_num))
            answer = "Skal gert"
            a = (dict(answer=answer), answer, "")
            q.set_beautified_query("{0}{1}".format(pfx, clean_num))
        else:
            # This is a named subject
            subj_þgf = NounPhrase(telsubj.title()).dative or telsubj
            a = gen_answer("Ég veit ekki símanúmerið hjá {0}".format(subj_þgf))

    q.set_answer(*a)
    q.set_qtype(_TELEPHONE_QTYPE)
    q.query_is_command()

    return True
