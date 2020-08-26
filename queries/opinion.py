"""

    Greynir: Natural language processing for Icelandic

    Opinion query response module

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


    This module handles queries related to Embla's opinions.

"""


import re
from datetime import datetime, timedelta

from queries import gen_answer


_OPINION_QTYPE = "Opinion"


_OPINION_REGEXES = (
    r"hvað finnst þér (?:eiginlega)?\s?um (.+)$",
    r"hvað þykir þér (?:eiginlega)?\s?um (.+)$",
    r"hvaða skoðun hefurðu (?:eiginlega)?\s?á (.+)$",
    r"hvaða skoðun hefur þú (?:eiginlega)?\s?á (.+)$",
    r"hvaða skoðun ertu með (?:eiginlega)?\s?á (.+)$",
    r"hvaða skoðun ert þú (?:eiginlega)?\s?með á (.+)$",
    r"hver er skoðun þín á (.+)$",
    r"hvaða skoðanir hefur þú (?:eiginlega)?\s?á (.+)$",
    r"hvaða skoðanir hefurðu á (?:eiginlega)?\s?(.+)$",
    r"hvert er álit þitt á (.+)$",
    r"hvaða álit hefurðu (?:eiginlega)?\s?á (.+)$",
    r"ertu reið yfir (.+)$",
    r"ert þú reið yfir (.+)$",
    r"ertu bitur yfir (.+)$",
    r"ert þú bitur yfir (.+)$",
    r"ertu bitur út af (.+)$",
    r"ert þú bitur út af (.+)$",
    r"ertu í uppnámi yfir (.+)$",
    r"ert þú í uppnámi yfir (.+)$",
    r"ertu í uppnámi út af (.+)$",
    r"ert þú í uppnámi út af (.+)$",
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
    q.set_answer(*gen_answer(answer))
    q.set_qtype(_OPINION_QTYPE)
    q.set_expires(datetime.utcnow() + timedelta(hours=24))

    return True
