"""

    Greynir: Natural language processing for Icelandic

    Copyright (C) 2023 Miðeind ehf.

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
    ones that do not require parsing the query text gramatically. For
    this purpose it only needs to implement the handle_plain_text()
    function, as shown below.


    Example query module that responds in English.

"""

from queries import Query
from queries.util import gen_answer


def handle_plain_text(q: Query) -> bool:
    ql = q.query_lower.rstrip("?")

    if ql == "segðu eitthvað á ensku":
        q.set_qtype("English")

        # Set answer
        answer = "This is an example of me speaking English"
        q.set_answer(*gen_answer(answer))
        q.set_voice_id("Abbi")

        return True

    return False
