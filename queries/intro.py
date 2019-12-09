"""

    Greynir: Natural language processing for Icelandic

    Distance query response module

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


    This module generates a polite introductory response to statements 
    of the form "Ég heiti X" ("My name is X").

"""

# TODO: Gender awareness ("Sæll, Jón", "Sæl, Gunna")

import re
from random import choice


_LOC_QTYPE = "Introduction"


_MY_NAME_IS_REGEX = r"^ég heiti (.+)$"

_RESPONSES = ("Gaman að kynnast þér, [X]. Ég heiti Embla.",)

def handle_plain_text(q):
    ql = q.query_lower.rstrip("?")

    m = re.search(_MY_NAME_IS_REGEX, ql)
    if not m:
        return False

    name = m.group(1)
    a = choice(_RESPONSES).replace("[X]", name.title())

    response = dict(answer=a)
    voice = a
    answer = a

    q.set_answer(response, answer, voice)
    #query.set_beautified_query(bq)

    return True
