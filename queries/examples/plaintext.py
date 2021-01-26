"""

    Greynir: Natural language processing for Icelandic

    Example of a plain text query processor module.

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


"""

from datetime import datetime, timedelta


def handle_plain_text(q) -> bool:
    """ Handle a plain text query, contained in the q parameter
        which is an instance of the query.Query class.
        Returns True if the query was handled, and in that case
        the appropriate properties on the Query instance have
        been set, such as the answer and the query type (qtype).
        If the query is not recognized, returns False. """
    ql = q.query_lower.rstrip("?")

    if ql == "er þetta prufa":
        q.set_qtype("PlaintextExample")
        q.set_key("IsTest")

        # Set answer
        answer = "Já"
        voice = "Já, þetta er prufa"
        response = dict(answer=answer)
        q.set_answer(response, answer, voice)

        # Caching (optional)
        q.set_expires(datetime.utcnow() + timedelta(hours=24))

        # Context (optional)
        # q.set_context(dict(subject="Prufuviðfangsefni"))

        # Source (optional)
        # q.set_source("Prufumódúll")

        # Beautify query for end user display (optional)
        # q.set_beautified_query(ql.upper())

        # Javascript command to execute client-side (optional)
        # q.set_command("2 + 2")

        # URL to be opened by client (optional)
        # q.set_url("https://miðeind.is")

        return True

    return False
