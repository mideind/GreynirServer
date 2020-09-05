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


_INTRO_QTYPE = "Introduction"


_MY_NAME_IS_REGEXES = (
    r"^ég heiti (.+)$",
    r"^nafn mitt er (.+)$",
    r"^nafnið mitt er (.+)$",
    r"^ég ber heitið (.+)$",
    r"^ég ber nafnið (.+)$",
)

_RESPONSES = {
    "hk": "Gaman að kynnast þér, {0}. Ég heiti Embla.",
    "kk": "Sæll og blessaður, {0}. Ég heiti Embla.",
    "kvk": "Sæl og blessuð, {0}. Ég heiti Embla.",
}


def handle_plain_text(q):
    """ Handle the user introducing herself """
    ql = q.query_lower.rstrip("?")

    for rx in _MY_NAME_IS_REGEXES:
        m = re.search(rx, ql)
        if m:
            break
    else:
        # Not understood
        return False

    name = m.group(1).strip()
    if not name:
        return False

    if name.startswith("ekki "):
        return False

    with BIN_Db.get_db() as bdb:
        fn = name.split()[0].title()
        gender = bdb.lookup_name_gender(fn)
        a = _RESPONSES[gender or "hk"].format(fn)

    voice = a.replace(",", "")
    q.set_answer(dict(answer=a), a, voice)
    q.set_qtype(_INTRO_QTYPE)
    q.query_is_command()

    return True
