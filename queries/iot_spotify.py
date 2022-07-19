"""

    Greynir: Natural language processing for Icelandic

    Randomness query response module

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

    This query module handles queries related to the generation
    of random numbers, e.g. "Kastaðu tengingi", "Nefndu tölu milli 5 og 10", etc.

"""


# TODO: add "láttu", "hafðu", "litaðu", "kveiktu" functionality.
# TODO: make the objects of sentences more modular, so that the same structure doesn't need to be written for each action
# TODO: ditto the previous comment. make the initial non-terminals general and go into specifics at the terminal level instead.
# TODO: substituion klósett, baðherbergi hugmyndÆ senda lista i javascript og profa i röð
# TODO: Embla stores old javascript code cached which has caused errors
# TODO: Cut down javascript sent to Embla
# TODO: Two specified groups or lights.
# TODO: No specified location
# TODO: Fix scene issues

from os import access
from typing import Dict, Mapping, Optional, cast
from typing_extensions import TypedDict

import logging
import random
import json
import flask
from datetime import datetime, timedelta
import re

from reynir.lemmatize import simple_lemmatize

from query import Query, QueryStateDict, AnswerTuple
from queries import gen_answer, read_jsfile, read_grammar_file
from queries.spotify import SpotifyClient
from tree import Result, Node, TerminalNode
from util import read_api_key


_IoT_QTYPE = "IoTSpotify"

# TOPIC_LEMMAS = [
#     "tónlist",
#     "spila",
# ]


def help_text(lemma: str) -> str:
    """Help text to return when query.py is unable to parse a query but
    one of the above lemmas is found in it"""
    return "Ég skil þig ef þú segir til dæmis: {0}.".format(
        random.choice(
            ("Hækkaðu í tónlistinni", "Kveiktu á tónlist", "Láttu vera tónlist")
        )
    )


# This module wants to handle parse trees for queries
HANDLE_TREE = True

# The grammar nonterminals this module wants to handle
QUERY_NONTERMINALS = {"QIoTSpotify"}

# The context-free grammar for the queries recognized by this plug-in module

_SPOTIFY_REGEXES = [
    r"^(spilaðu )([\w|\s]+)(með )([\w|\s]+)$",
]

GRAMMAR = f"""

/þgf = þgf
/ef = ef

Query →
    QIoTSpotify '?'?

QIoTSpotify →
    QIoTSpotifyPlaySongByArtist

QIoTSpotifyPlaySongByArtist →
    QIoTSpotifyPlayVerb QIoTSpotifySongName QIoTSpotifyWithPreposition QIoTSpotifyArtistName

QIoTSpotifyPlayVerb →
    'spila:so'_bh

QIoTSpotifySongName →
    Nl

QIoTSpotifyWithPreposition →
    'með'
    | 'eftir'

QIoTSpotifyArtistName →
    Nl
    | sérnafn
"""


def QIoTSpotify(node: Node, params: QueryStateDict, result: Result) -> None:
    result.qtype = _IoT_QTYPE


def QIoTSpotifyPlayVerb(node: Node, params: QueryStateDict, result: Result) -> None:
    "spotify play function"
    result.action = "play"


def QIoTSpotifySongName(node: Node, params: QueryStateDict, result: Result) -> None:
    result.song_name = result._text


def QIoTSpotifyArtistName(node: Node, params: QueryStateDict, result: Result) -> None:
    result.artist_name = result._indefinite


def get_song_and_artist(q: Query) -> tuple:
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
            song_name = m.group(2)
            artist_name = m.group(4).strip()
            return (song_name, artist_name)
    else:
        return False


def sentence(state: QueryStateDict, result: Result) -> None:
    """Called when sentence processing is complete"""
    print("sentence")
    q: Query = state["query"]
    if result.action == "play":
        print("SPOTIFY PLAY")
        song_artist_tuple = get_song_and_artist(q)
        print("exited plain text")
        song_name = song_artist_tuple[0]
        artist_name = song_artist_tuple[1]
        print("SONG NAME :", song_name)
        print("ARTIST NAME :", artist_name)

        print("RESTULT SONG NAME:", result.song_name)
        print("RESULT ARTIST NAME:", result.artist_name)
        device_data = q.client_data("spotify")
        if device_data is not None:
            client_id = str(q.client_id)
            spotify_client = SpotifyClient(
                device_data,
                client_id,
                song_name=result.song_name,
                artist_name=result.artist_name,
            )
            song_url = spotify_client.get_song_by_artist()
            response = spotify_client.play_song_on_device()
            print("RESPONSE FROM SPOTIFY:", response)
            if response is None:
                q.set_url(song_url)

            answer = "Ég spilaði lagið"
        else:
            answer = "Það vantar að tengja Spotify aðgang."
            q.set_answer(*gen_answer(answer))
            return
        # q.set_url(
        #     "https://spotify.app.link/?product=open&%24full_url=https%3A%2F%2Fopen.spotify.com%2Ftrack%2F2BSyX4weGuITcvl5r2lLCC%3Fgo%3D1%26sp_cid%3D2a74d03dedb9fa4450d122ddebebcf9b%26fallback%3Dgetapp&feature=organic&_p=c31529c0980b7af1e11b90f9"
        # )
        voice_answer, response = answer, dict(answer=answer)
        q.set_answer(response, answer, voice_answer)

    else:
        print("ELSE")
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
        return

    # # TODO: Need to add check for if there are no registered devices to an account, probably when initilazing the querydata
