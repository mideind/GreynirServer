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

from typing import Optional, List, Dict, Any, Union, cast

import re
from random import choice
from collections import OrderedDict

from pyyoutube import Api, SearchListResponse, SearchResult

from query import Query
from queries import gen_answer


_PLAY_QTYPE = "Play"


_AFFIRMITIVE = "Skal gert!"


YT_API = Api(api_key="AIzaSyC3_19QvfPme_CwyTDmiuw3617RV0-lqzI")


def search_youtube(
    q: str, types: List[str] = ["video"], limit: int = 5
) -> Optional[Union[SearchListResponse, Dict[Any, Any]]]:
    r = YT_API.search_by_keywords(q=q, search_type=types, count=5, limit=5)
    return r


_YOUTUBE_VIDEO_URL = "https://www.youtube.com/watch?v={0}"


def find_youtube_videos(q: str, limit: int = 1) -> List[str]:
    """Find video URLs for a given a search string using the YouTube API."""
    vids = []
    r = search_youtube(q, limit=limit)
    if r is None or r.items is None:
        return vids
    for i in r.items:
        item = i.to_dict()
        if "id" not in item or "videoId" not in item["id"]:
            continue
        vids.append(_YOUTUBE_VIDEO_URL.format(item["id"]["videoId"]))

    return vids


_YOUTUBE_PLAYLIST_URL = "https://www.youtube.com/watch?v={0}&list={1}"


def find_youtube_playlists(q: str, limit: int = 1) -> List[str]:
    """Find playlists for a given a search string using the YouTube API."""
    vids = []
    r = search_youtube(q, types=["playlist"], limit=limit)
    if r is None or r.items is None:
        return vids
    for i in r.items:
        item = i.to_dict()
        if "id" not in item or "playlistId" not in item["id"]:
            continue
        playlist_id = item["id"]["playlistId"]
        pl_vids = YT_API.get_playlist_items(playlist_id=playlist_id, count=1)
        if not pl_vids.items:
            continue
        first_vid_id = pl_vids.items[0].snippet.resourceId.videoId
        vids.append(_YOUTUBE_PLAYLIST_URL.format(first_vid_id, playlist_id))

    return vids


# Musical genres
def _play_jazz(qs: str, q: Query) -> None:
    urls = find_youtube_playlists("jazz")
    if urls:
        q.set_url(urls[0])
    else:
        # Caravan - Duke Ellington classic
        q.set_url("https://www.youtube.com/watch?v=E5loTx0_KDE")
    q.set_answer(*gen_answer(_AFFIRMITIVE))


def _play_blues(qs: str, q: Query) -> None:
    urls = find_youtube_playlists("blues")
    if urls:
        q.set_url(urls[0])
    else:
        # How Long Blues - Jimmy & Mama Yancey
        q.set_url("https://www.youtube.com/watch?v=jw9tMRhKEak")
    q.set_answer(*gen_answer(_AFFIRMITIVE))


def _play_rock(qs: str, q: Query) -> None:
    urls = find_youtube_playlists("rock music")
    if urls:
        q.set_url(urls[0])
    else:
        # How Long Blues - Jimmy & Mama Yancey
        q.set_url("https://www.youtube.com/watch?v=y8OtzJtp-EM")
    q.set_answer(*gen_answer(_AFFIRMITIVE))


def _play_classical(qs: str, q: Query) -> None:
    urls = find_youtube_playlists("classical music")
    if urls:
        q.set_url(urls[0])
    else:
        # Beethoven - 9th symph. 2nd movement
        q.set_url("https://www.youtube.com/watch?v=iwIvS4yIThU")
    q.set_answer(*gen_answer(_AFFIRMITIVE))


def _play_electronic(qs: str, q: Query) -> None:
    urls = find_youtube_playlists("electronic music")
    if urls:
        q.set_url(urls[0])
    else:
        # Orbital - The Box
        q.set_url("https://www.youtube.com/watch?v=qddG0iUSax4")
    q.set_answer(*gen_answer(_AFFIRMITIVE))


# Randomly selected genre
def _play_music(qs: str, q: Query) -> None:
    m = [_play_jazz, _play_blues, _play_rock, _play_classical, _play_electronic]
    choice(m)(qs, q)


# Films
def _play_film(qs: str, q: Query) -> Any:
    q.set_url("https://www.youtube.com/watch?v=FC6jFoYm3xs")
    q.set_answer(*gen_answer(_AFFIRMITIVE))


_VERB = "|".join(
    frozenset(
        (
            "spilaðu",
            "spilaðu fyrir mig",
            "spila þú",
            "spila þú fyrir mig",
            "settu á fóninn",
            "gætirðu spilað",
        )
    )
)
_ADJ = "|".join(
    frozenset(("góðan", "góða", "gott", "skemmtilegan", "skemmtilegt", "skemmtilega"))
)


HARDCODED_Q2H = {
    # Classical
    "spilaðu klassík": _play_classical,
    "spila þú klassík": _play_classical,
    "spilaðu klassíkt": _play_classical,
    "spila þú klassíkt": _play_classical,
    "spilaðu klassíska tónlist": _play_classical,
    "spila þú klassíska tónlist": _play_classical,
    "spilaðu klassísk tónverk": _play_classical,
    "spila þú klassísk tónverk": _play_classical,
    # Generic
    "spila tónlist": _play_music,
    "spilaðu tónlist": _play_music,
    "spila þú tónlist": _play_music,
    "spila tónverk": _play_music,
    "spilaðu tónverk": _play_music,
    "spila þú tónverk": _play_music,
    "spilaðu skemmtilega tónlist": _play_music,
    "spilaðu einhverja tónlist": _play_music,
    "spila þú einhverja tónlist": _play_music,
    "spilaðu fyrir mig tónlist": _play_music,
    "spilaðu tónlist fyrir mig": _play_music,
    "spilaðu skemmtilegt tónverk": _play_music,
    "spilaðu einhvert tónverk": _play_music,
    "spila þú einhvert tónverk": _play_music,
    "spilaðu fyrir mig tónverk": _play_music,
    "spilaðu tónverk fyrir mig": _play_music,
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
    "spilaðu mynd": _play_film,
    "spilaðu kvikmynd fyrir mig": _play_film,
    "spilaðu bíómynd fyrir mig": _play_film,
    "spilaðu mynd fyrir mig": _play_film,
    "sýndu mér kvikmynd": _play_film,
    "sýndu mér bíómynd": _play_film,
}


def _play_music_named(qs: str, q: Query) -> Any:
    pass


REGEX_Q2H = OrderedDict(
    {
        # Jazz
        r"^(?:{0})\s?(?:{1})?\s(djass|jazz|jass|djasstónlist)$".format(
            _VERB, _ADJ
        ): _play_jazz,
        # Blues
        r"^(?:{0})\s?(?:{1})?\s(blús|blúsinn|blústónlist)$".format(
            _VERB, _ADJ
        ): _play_blues,
        # Rock
        r"^(?:{0})\s?(?:{1})?\s(rokk|rokktónlist|rokk og ról)$".format(
            _VERB, _ADJ
        ): _play_jazz,
        # Electronic
        r"^(?:{0})\s?(?:{1})?\s(raftónlist|elektróníska tónlist|elektrónískt)$".format(
            _VERB, _ADJ
        ): _play_electronic,
        # Play music by X
        r"^(spilaðu|spila þú)\s?(?:góða|gott|góðan|skemmtilega|skemmtilegt|skemmtilegan)?\s(tónlist|tónverk|lag|verk|slagara) (eftir|með|í flutningi) (.+)$": _play_music_named,
    }
)


def handle_plain_text(q: Query) -> bool:
    """Handle a plain text query."""
    ql = q.query_lower.rstrip("?")

    # Check if it's a hardcoded barestring query
    handler_fn = HARDCODED_Q2H.get(ql)
    if handler_fn:
        handler_fn(ql, q)
        return True

    # Check if query matches regexes supported by this module
    res = None
    for rx, fn in REGEX_Q2H.items():
        res = re.search(rx, ql)
        if res:
            fn(ql, q)
            break

    if not res:
        return False

    # OK, this is a query we recognize and handle
    q.set_qtype(_PLAY_QTYPE)

    q.set_answer(*gen_answer("Skal gert!"))

    return True

    # A non-voice answer is usually a dict or a list
    answer = cast(str, res.get("answer")) or ""
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
    # if is_func or response.get("can_cache", False):
    #     q.set_expires(datetime.utcnow() + timedelta(hours=24))

    return True
