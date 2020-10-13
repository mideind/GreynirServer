"""

    Greynir: Natural language processing for Icelandic

    Distance query response module

    Copyright (C) 2020 Miðeind ehf.

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


    This module generates a polite introductory response to statements
    of the form "Ég heiti X" ("My name is X").

"""

import re

from reynir.bindb import BIN_Db

from query import Query
from . import gen_answer


_INTRO_QTYPE = "Introduction"


_MY_NAME_IS_REGEXES = frozenset(
    (
        r"^ég heiti (.+)$",
        r"^nafn mitt er (.+)$",
        r"^nafnið mitt er (.+)$",
        r"^ég ber heitið (.+)$",
        r"^ég ber nafnið (.+)$",
    )
)

_INTRODUCTION_RESPONSES = {
    "hk": "Gaman að kynnast þér, {0}. Ég heiti Embla.",
    "kk": "Sæll og blessaður, {0}. Ég heiti Embla.",
    "kvk": "Sæl og blessuð, {0}. Ég heiti Embla.",
}

_WHATS_MY_NAME = frozenset(
    (
        "hvað heiti ég fullu nafni",
        "hvað heiti ég",
        "veistu hvað ég heiti",
        "veistu hvað ég heiti fullu nafni" "veistu ekki hvað ég heiti",
        "hver er ég",
        "veistu hver ég er",
        "veistu ekki hver ég er",
        "hvaða nafn er ég með",
        "hvaða nafni heiti ég",
        "veistu hvaða nafni ég heiti",
        "hvað heiti ég eiginlega",
        "hvaða nafn ber ég",
    )
)

_DUNNO_NAME = "Ég veit ekki hvað þú heitir."


# TODO: Implement this
# _I_LIVE_AT_REGEXES = (
#     r"ég á heima á (.+)$",
#     r"ég á heima í (.+)$",
#     r"heimilisfang mitt er á (.+)$",
#     r"heimilisfang mitt er í (.+)$",
#     r"heimilisfang mitt er (.+)$",
# )

# _DUNNO_ADDRESS = "Ég veit ekki hvar þú átt heima."


_WHO_IS_ME = "hver er {0}"
_YOU_ARE = "Þú ert {0}"


def handle_plain_text(q: Query) -> bool:
    """ Handle the user introducing herself """
    ql = q.query_lower.rstrip("?")

    # "Hver er [nafn notanda]?"
    nd = q.client_data("name")
    if nd:
        for t in ["first", "full"]:
            if t not in nd:
                continue
            if ql == _WHO_IS_ME.format(nd[t].lower()):
                q.set_answer(*gen_answer(_YOU_ARE.format(nd[t])))
                return True

    # Is it a statement where the user provides his name?
    for rx in _MY_NAME_IS_REGEXES:
        m = re.search(rx, ql)
        if m:
            break
    if m:
        name = m.group(1).strip()
        # TODO: Strip any non alphabetic chars?
        if not name:
            return False

        # Get first name, look up gender for a gender-tailored response
        with BIN_Db.get_db() as bdb:
            fn = name.split()[0].title()
            gender = bdb.lookup_name_gender(fn) or "hk"
            answ = _INTRODUCTION_RESPONSES[gender].format(fn)

        # Save this info about user to query data table
        if q.client_id:
            qdata = dict(full=name.title(), first=fn, gender=gender)
            q.set_client_data("name", qdata)

        # Generate answer
        voice = answ.replace(",", "")
        q.set_answer(dict(answer=answ), answ, voice)
        q.set_qtype(_INTRO_QTYPE)
        q.query_is_command()
        return True

    # A query concerning the user's name?
    elif ql in _WHATS_MY_NAME:
        answ = None
        nd = q.client_data("name")
        if nd and "full" in nd:
            answ = f"Þú heitir {nd['full']}"
        else:
            answ = _DUNNO_NAME
        q.set_answer(*gen_answer(answ))
        q.set_qtype(_INTRO_QTYPE)
        return True

    return False
