"""

    Reynir: Natural language processing for Icelandic

    Stats query response module

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


    This module handles queries related to statistics about the query mechanism.

"""


_STATS_QTYPE = "Stats"


_NUM_PEOPLE_Q = ("hvað þekkirðu margar manneskjur",)

_NUM_QUERIES_Q = (
    "hvað hefurðu fengið margar fyrirspurnir"
    "hvað hefurðu fengið margar spurningar"
    "hversu mörgum fyrirspurnum hefurðu svarað"
    "hversu mörgum spurningum hefurðu svarað"
)

_MOST_FREQ_QUERIES_Q = (
    "Hvað spyr fólk mest um"
    "Hvað ertu mest spurð um"
    "Hvað ert þú mest spurð um"
    "Hvað spyr fólk þig aðallega um"
)


def handle_plain_text(q):
    """ Handle a plain text query about Embla statistics. """
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
