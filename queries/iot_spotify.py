"""

    Greynir: Natural language processing for Icelandic

    Example of a plain text query processor module.

    Copyright (C) 2022 Miðeind ehf.

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

from query import Query
from datetime import datetime, timedelta
import random
import re
from queries.spotify import SpotifyClient
from queries import gen_answer


def help_text(lemma: str) -> str:
    """Help text to return when query.py is unable to parse a query but
    one of the above lemmas is found in it"""
    return "Ég skil þig ef þú segir til dæmis: {0}.".format(
        random.choice(("Spilaðu Þorparinn með Pálma Gunnarssyni"))
    )


# The context-free grammar for the queries recognized by this plug-in module

_SPOTIFY_REGEXES = [
    r"^spilaðu ([\w|\s]+) með ([\w|\s]+)$",
    # r"^spilaðu ([\w|\s]+) með ([\w|\s]+) á spotify?$",
    r"^spilaðu ([\w|\s]+) á spotify$",
    r"^spilaðu ([\w|\s]+) á spotify",
]


def handle_plain_text(q) -> bool:
    """Handle a plain text query requesting Spotify to play a specific song by a specific artist."""
    # ql = q.query_lower.strip().rstrip("?")
    print("handle_plain_text")
    ql = q.query_lower.strip().rstrip("?")
    print("QL:", ql)

    pfx = None

    for rx in _SPOTIFY_REGEXES:
        print(rx)
        print("")
        m = re.search(rx, ql)
        print(m)
        if m:
            (print("MATCH!"))
            song_name = m.group(1)
            artist_name = m.group(2).strip()
            print("SONG NAME :", song_name)
            print("ARTIST NAME :", artist_name)
            device_data = q.client_data("iot").get("iot_streaming").get("spotify")
            if device_data is not None:
                client_id = str(q.client_id)
                spotify_client = SpotifyClient(
                    device_data,
                    client_id,
                    song_name=song_name,
                    artist_name=artist_name,
                )
                song_url = spotify_client.get_song_by_artist()
                response = spotify_client.play_song_on_device()
                # response = None
                print("RESPONSE FROM SPOTIFY:", response)
                answer = "Ég spilaði lagið"
                if response is None:
                    q.set_url(song_url)
                q.set_answer({"answer": answer}, answer, "")
                return True

            else:
                answer = "Það vantar að tengja Spotify aðgang."
                q.set_answer(*gen_answer(answer))
                return True
    else:
        return False

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


# def get_song_and_artist(q: Query) -> tuple:
