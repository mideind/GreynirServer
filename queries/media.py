"""

    Greynir: Natural language processing for Icelandic

    Weather query response module

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


    This module handles queries relating to music playback.

"""

from typing import Optional, List, Dict, Any, Union

import re
from random import choice
from collections import OrderedDict

from pyyoutube import Api, SearchListResponse, SearchResult

from query import Query
from special import AnswerType


_PLAY_QTYPE = "Play"


def _play_jazz(qs: str, q: Query) -> AnswerType:
    q.set_url("https://www.youtube.com/watch?v=E5loTx0_KDE")
    return {"answer": "Skal gert!", "is_question": False}


def _play_blues(qs: str, q: Query) -> AnswerType:
    q.set_url("https://www.youtube.com/watch?v=jw9tMRhKEak")
    return {"answer": "Skal gert!", "is_question": False}


def _play_rock(qs: str, q: Query) -> AnswerType:
    q.set_url("https://www.youtube.com/watch?v=y8OtzJtp-EM")
    return {"answer": "Skal gert!", "is_question": False}


def _play_classical(qs: str, q: Query) -> AnswerType:
    q.set_url("https://www.youtube.com/watch?v=iwIvS4yIThU")
    return {"answer": "Skal gert!", "is_question": False}


def _play_music(qs: str, q: Query) -> AnswerType:
    m = [_play_jazz, _play_blues, _play_rock, _play_classical]
    return choice(m)(qs, q)


def _play_film(qs: str, q: Query) -> AnswerType:
    q.set_url("https://www.youtube.com/watch?v=FC6jFoYm3xs")
    return {"answer": "Skal gert!", "is_question": False}


HARDCODED_Q2H = {
    # Play some music. Just experimental fun for now.
    # Jazz
    "spilaðu djass": _play_jazz,
    "spila þú djass": _play_jazz,
    "spilaðu jass": _play_jazz,
    "spila þú jass": _play_jazz,
    "spilaðu jazz": _play_jazz,
    "spila þú jazz": _play_jazz,
    # Blues
    "spilaðu blús": _play_blues,
    "spila þú blús": _play_blues,
    "spilaðu rokk": _play_rock,
    "spila þú rokk": _play_rock,
    # Classical
    "spilaðu klassík": _play_classical,
    "spila þú klassík": _play_classical,
    "spilaðu klassíska tónlist": _play_classical,
    "spila þú klassíska tónlist": _play_classical,
    # Generic
    "spila tónlist": _play_music,
    "spilaðu tónlist": _play_music,
    "spila þú tónlist": _play_music,
    "spilaðu skemmtilega tónlist": _play_music,
    "spilaðu einhverja tónlist": _play_music,
    "spila þú einhverja tónlist": _play_music,
    "spilaðu fyrir mig tónlist": _play_music,
    "spilaðu tónlist fyrir mig": _play_music,
    "spilaðu fyrir mig lag": _play_music,
    "spilaðu lag fyrir mig": _play_music,
    "spilaðu skemmtilega tónlist fyrir mig": _play_music,
    "viltu spila fyrir mig tónlist": _play_music,
    "viltu spila einhverja tónlist fyrir mig": _play_music,
    "spilaðu gott lag": _play_music,
    "spilaðu góða tónlist": _play_music,
    "geturðu spilað tónlist": _play_music,
    "getur þú spilað tónlist": _play_music,
    "geturðu spilað tónlist fyrir mig": _play_music,
    "getur þú spilað tónlist fyrir mig": _play_music,
    "geturðu spilað lag": _play_music,
    "getur þú spilað lag": _play_music,
    "geturðu spilað lag fyrir mig": _play_music,
    "getur þú spilað lag fyrir mig": _play_music,
    # Play a film
    "spilaðu kvikmynd": _play_film,
    "spilaðu bíómynd": _play_film,
    "spilaðu kvikmynd fyrir mig": _play_film,
    "spilaðu bíómynd fyrir mig": _play_film,
    "sýndu mér kvikmynd": _play_film,
    "sýndu mér bíómynd": _play_film,
}


def _play_music_named(qs: str, q: Query) -> AnswerType:
    pass


REGEX_Q2H = OrderedDict(
    {
        r"^spilaðu tónlist með (.+)": _play_music_named,
        r"^spilaðu tónlist með (.+)": _play_music_named,
    }
)


def search_youtube(
    q: str, types: List[str] = ["video"], limit: int = 5
) -> Optional[Union[SearchListResponse, Dict[Any, Any]]]:
    api = Api(api_key="AIzaSyC3_19QvfPme_CwyTDmiuw3617RV0-lqzI")
    r = api.search_by_keywords(q=q, search_type=["video"], count=5, limit=5)
    return r


def handle_plain_text(q: Query) -> bool:
    """Handle a plain text query."""
    ql = q.query_lower.rstrip("?")

    # Check if it's a hardcoded barestring query
    handler_fn = HARDCODED_Q2H.get(ql)
    if handler_fn:
        q.set_answer(*handler_fn())

    # Check if query matches regexes supported by this module
    res = None
    for rx in REGEX_Q2H.keys():
        res = re.search(rx, ql)
        if res:
            break

    if not res:
        return False

    # OK, this is a query we recognize and handle
    q.set_qtype(_PLAY_QTYPE)

    r = _SPECIAL_QUERIES[ql]
    is_func = isfunction(r)
    if is_func:
        response = cast(AnswerCallable, r)(ql, q)
    else:
        response = cast(AnswerType, r)

    # A non-voice answer is usually a dict or a list
    answer = cast(str, response.get("answer")) or ""
    # A voice answer is always a plain string
    voice = cast(str, response.get("voice")) or answer
    q.set_answer(dict(answer=answer), answer, voice)
    # If this is a command, rather than a question,
    # let the query object know so that it can represent
    # itself accordingly
    if not response.get("is_question", True):
        q.query_is_command()
    # Add source
    source = response.get("source")
    if source is not None:
        q.set_source(cast(str, source))
    # Caching for non-dynamic answers
    if is_func or response.get("can_cache", False):
        q.set_expires(datetime.utcnow() + timedelta(hours=24))

    return True
