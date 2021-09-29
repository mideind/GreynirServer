"""

    Greynir: Natural language processing for Icelandic

    Test query response module

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


    This module handles queries related to testing various response
    payload functionality both server and client-side, for example
    JS code to be executed, URL to be opened, image to display, etc.

"""

from query import Query
from queries import gen_answer


_TEST_QTYPE = "Test"


def handle_plain_text(q: Query) -> bool:
    """Handle a plain text query."""
    ql = q.query_lower.rstrip("?")

    if ql == "keyrðu kóða":
        q.set_command("2 + 2")
    elif ql == "opnaðu vefsíðu":
        q.set_url("https://mideind.is")
    elif ql == "sýndu mynd":
        q.set_image("https://greynir.is/static/img/GreynirLogoHoriz180x80.png")
    else:
        return False

    q.set_qtype(_TEST_QTYPE)
    q.set_answer(*gen_answer("Skal gert"))

    return True