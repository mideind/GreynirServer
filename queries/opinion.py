"""

    Reynir: Natural language processing for Icelandic

    Opinion query response module

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


    This module handles queries related to Embla's opinions.

"""


import re
from datetime import datetime, timedelta

_OPINION_QTYPE = "Opinion"

_OPINION_REGEXES = (
    r"hvað finnst þér um (.+)$",
    r"hvaða skoðun hefurðu á (.+)$",
    r"hvaða skoðun hefur þú á (.+)$",
    r"hvaða skoðun ertu með á (.+)$",
    r"hvaða skoðun ert þú með á (.+)$",
    r"hver er skoðun þín á (.+)$",
    r"hvaða skoðanir hefur þú á (.+)$",
    r"hvaða skoðanir hefurðu á (.+)$",
)


def handle_plain_text(q):
    """ Handle a plain text query concerning opinion on any subject. """
    ql = q.query_lower.rstrip("?")

    subj = None

    for rx in _OPINION_REGEXES:
        m = re.search(rx, ql)
        if m:
            subj = m.group(1)
            break
    else:
        return False

    answer = "Ég hef enga sérstaka skoðun í þeim efnum."
    voice = answer
    response = dict(answer=answer)

    q.set_answer(response, answer, voice)
    q.set_qtype(_OPINION_QTYPE)
    q.set_expires(datetime.utcnow() + timedelta(hours=24))

    return True
