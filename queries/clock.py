"""

    Reynir: Natural language processing for Icelandic

    Clock query response module

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

"""

from datetime import datetime


def handle_plain_text(q):
    """ Handle a plain text query, contained in the q parameter
        which is an instance of the query.Query class.
        Returns True if the query was handled, and in that case
        the appropriate properties on the Query instance have
        been set, such as the answer and the query type (qtype).
        If the query is not recognized, returns False. """
    ql = q.query_lower
    if ql.endswith("?"):
        ql = ql[:-1]

    if ql == "hvað er klukkan":
        # This is a query we recognize and handle
        q.set_qtype("Special")
        now = datetime.utcnow()
        # Calculate a 'single best' displayable answer
        answer = "{0:02}:{1:02}".format(now.hour, now.minute)
        # A detailed response object is usually a list or a dict
        response = dict(answer=answer)
        # A voice answer is a plain string that will be
        # passed as-is to a voice synthesizer
        voice = "Klukkan er {0} {1:02}.".format(now.hour, now.minute)
        q.set_answer(response, answer, voice)
        return True

    return False
