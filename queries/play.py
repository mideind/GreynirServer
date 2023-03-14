"""

    Greynir: Natural language processing for Icelandic

    Media playback query response module

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


    This module handles queries relating to music and video playback.

"""

from __future__ import annotations

from typing import Optional, List, Any, Match
from typing_extensions import TypedDict

import re
import logging
from random import choice

from pyyoutube import Api, SearchListResponse  # type: ignore

from queries import Query
from queries.util import gen_answer
from utility import read_api_key


class VideoIdDict(TypedDict):
    """A video ID as a dictionary."""

    videoId: str
    playlistId: str


class SearchDict(TypedDict):
    """A search result item as a dictionary."""

    id: VideoIdDict


class SearchItem:
    """A single search result item."""

    def to_dict(self) -> SearchDict:
        ...


class SearchResults:
    """The result of a YouTube search query."""

    @property
    def items(self) -> Optional[List[SearchItem]]:
        ...


_PLAY_QTYPE = "Play"


_AFFIRMATIVE = "Skal gert!"


_youtube_api: Any = None


def yt_api() -> Any:
    """Lazily instantiate YouTube API client."""
    global _youtube_api
    if not _youtube_api:
        _youtube_api = Api(api_key=read_api_key("GoogleServerKey"))
    if not _youtube_api:
        logging.error("Unable to instantiate YouTube API client")
    return _youtube_api


def search_youtube(
    q: str, types: List[str] = ["video"], limit: int = 5
) -> Optional[SearchResults]:
    r = yt_api().search_by_keywords(q=q, search_type=types, limit=limit)
    return r


_YOUTUBE_VIDEO_URL = "https://www.youtube.com/watch?v={0}"


def find_youtube_videos(q: str, limit: int = 1) -> List[str]:
    """Find video URLs for a given a search string via the YouTube API."""
    vids: List[str] = []
    if not q:
        return vids
    try:
        r = search_youtube(q, limit=limit)
        if r is None or r.items is None:
            return vids
        for i in r.items:
            item = i.to_dict()
            if "id" not in item or "videoId" not in item["id"]:
                continue
            vids.append(_YOUTUBE_VIDEO_URL.format(item["id"]["videoId"]))
    except Exception as e:
        logging.error(f"Error communicating with YouTube API: {e}")

    return vids


_YOUTUBE_PLAYLIST_URL = "https://www.youtube.com/watch?v={0}&list={1}"


def find_youtube_playlists(q: str, limit: int = 3) -> List[str]:
    """Find URLs for playlists given a search string via the YouTube API."""
    vids: List[str] = []
    try:
        r = search_youtube(q, types=["playlist"], limit=limit)
        if r is None or r.items is None:
            return vids

        for i in r.items:
            item = i.to_dict()
            if "id" not in item or "playlistId" not in item["id"]:
                continue
            playlist_id = item["id"]["playlistId"]
            pl_vids = yt_api().get_playlist_items(playlist_id=playlist_id, count=1)
            if not pl_vids.items:
                continue
            first_vid_id = pl_vids.items[0].snippet.resourceId.videoId
            vids.append(_YOUTUBE_PLAYLIST_URL.format(first_vid_id, playlist_id))
    except Exception as e:
        logging.error(f"Error communicating with YouTube API: {e}")

    return vids


def rand_yt_playlist_for_genre(
    genre_name: str, limit: int = 5, fallback: Optional[str]=None
) -> Optional[str]:
    """Given a musical genre name, search for YouTube playlists and return a
    URL to a randomly selected one, with an (optional) fallback video URL."""
    urls = find_youtube_playlists(genre_name, limit=limit)
    if urls:
        return choice(urls)
    return fallback


# Musical genres
def _play_jazz(qs: str, q: Query, matches: Optional[Match[str]]) -> None:
    # Caravan - Duke Ellington classic
    fb = "https://www.youtube.com/watch?v=E5loTx0_KDE"
    q.set_url(rand_yt_playlist_for_genre("jazz", fallback=fb))
    q.set_key(matches.group(1) if matches else "")


def _play_blues(qs: str, q: Query, matches: Optional[Match[str]]) -> None:
    # How Long Blues - Jimmy & Mama Yancey
    fb = "https://www.youtube.com/watch?v=jw9tMRhKEak"
    q.set_url(rand_yt_playlist_for_genre("blues", fallback=fb))
    q.set_key(matches.group(1) if matches else "")


def _play_rock(qs: str, q: Query, matches: Optional[Match[str]]) -> None:
    # Led Zeppelin - Immigrant Song
    fb = "https://www.youtube.com/watch?v=y8OtzJtp-EM"
    q.set_url(rand_yt_playlist_for_genre("classic rock", fallback=fb))
    q.set_key(matches.group(1) if matches else "")


def _play_classical(qs: str, q: Query, matches: Optional[Match[str]]) -> None:
    # Beethoven - 9th symphony, 2nd movement
    fb = "https://www.youtube.com/watch?v=iwIvS4yIThU"
    q.set_url(rand_yt_playlist_for_genre("classical music", fallback=fb))
    q.set_key(matches.group(1) if matches else "")


def _play_electronic(qs: str, q: Query, matches: Optional[Match[str]]) -> None:
    # Orbital - The Box
    fb = "https://www.youtube.com/watch?v=qddG0iUSax4"
    q.set_url(rand_yt_playlist_for_genre("retro electronic music", fallback=fb))
    q.set_key(matches.group(1) if matches else "")


# Play music from a randomly selected genre
def _play_music(qs: str, q: Query, matches: Optional[Match[str]]) -> None:
    m = [_play_jazz, _play_blues, _play_rock, _play_classical, _play_electronic]
    choice(m)(qs, q, None)


_NO_MUSIC_FOUND = "Engin tónlist fannst."


def _play_music_by_artist(qs: str, q: Query, matches: Optional[Match[str]]) -> None:
    """Play a song (any song) by a given artist"""
    artist = matches.group(1) if matches else ""
    q.set_key(artist)

    r = find_youtube_videos(artist)
    if not r:
        q.set_answer(*gen_answer(_NO_MUSIC_FOUND))
    else:
        q.set_url(choice(r))


def _play_song_by_artist(qs: str, q: Query, matches: Optional[Match[str]]) -> None:
    """Play a particular, named song by a given artist"""
    song = matches.group(1) if matches else ""
    artist = matches.group(2) if matches else ""
    searchstr = f"{song} {artist}".strip()
    q.set_key(searchstr)

    r = find_youtube_videos(searchstr)
    if not r:
        q.set_answer(*gen_answer(_NO_MUSIC_FOUND))
    else:
        q.set_url(choice(r))


# Classic out-of-copyright films definitely available on YouTube
_FILMS = [
    "Metropolis 1927",
    "Nosferatu 1922",
    "Battleship Potemkin 1925",
    "Plan 9 from Outer Space 1959",
    "Cyrano de Bergerac 1950",
]


def _play_film(qs: str, q: Query, matches: Optional[Match[str]]) -> None:
    """Play a randomly selected out-of-copyright film on YouTube."""
    url = "https://www.youtube.com/watch?v=FC6jFoYm3xs"  # Nosferatu, 1922
    urls = find_youtube_videos(choice(_FILMS), limit=1)
    if urls:
        url = urls[0]
    else:
        q.set_answer(*gen_answer("Ekki tókst að finna kvikmynd"))
    q.set_url(url)


# Hardcoded non-regex queries handled by this module
HARDCODED_Q2H = {
    # Play some music, play a song
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
    "spilaðu eitthvert tónverk": _play_music,
    "spila þú eitthvert tónverk": _play_music,
    "spilaðu eitthvað tónverk": _play_music,
    "spila þú eitthvað tónverk": _play_music,
    "spilaðu fyrir mig tónverk": _play_music,
    "spilaðu tónverk fyrir mig": _play_music,
    "spilaðu lag": _play_music,
    "spilaðu eitthvað lag": _play_music,
    "spilaðu skemmtilegt lag": _play_music,
    "spilaðu lag fyrir mig": _play_music,
    "spilaðu fyrir mig lag": _play_music,
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
    "sýndu kvikmynd": _play_film,
    "sýndu bíómynd": _play_film,
    "sýndu mér kvikmynd": _play_film,
    "sýndu mér bíómynd": _play_film,
    "sýndu mér einhverja kvikmynd": _play_film,
    "sýndu mér einhverja bíómynd": _play_film,
}

_VERB = "|".join(
    (
        "spilaðu",
        "spilaðu fyrir mig",
        "spila þú",
        "spila þú fyrir mig",
        "settu á fóninn",
        "settu á fóninn fyrir mig",
        "geturðu spilað",
        "getur þú spilað fyrir mig",
        "gætirðu spilað",
        "gætir þú spilað fyrir mig",
        "viltu spila",
        "viltu spila fyrir mig",
        "vilt þú spila",
        "vilt þú spila fyrir mig",
        "nennirðu að spila",
        "nennirðu að spila fyrir mig",
        "nennir þú að spila",
        "nennir þú að spila fyrir mig",
    )
)

_ADJ = "|".join(
    frozenset(
        (
            "góðan",
            "góða",
            "gott",
            "góð",
            "skemmtilegan",
            "skemmtilegt",
            "skemmtilega",
            "skemmtileg",
            "huggulegan",
            "huggulega",
            "huggulegt",
            "hugguleg",
            "einhvern",
            "eitthvað",
            "einhverja",
        )
    )
)

_POST = "|".join(("fyrir mig", "fyrir okkur"))


REGEX_Q2H = {
    # Any music
    r"^(?:{0})\s?(?:{1})?\s(tónlist|tónverk|lag|slagara)\s?(?:{2})?$".format(
        _VERB, _ADJ, _POST
    ): _play_music,
    # Jazz
    r"^(?:{0})\s?(?:{1})?\s(djass|jazz|jass|djasstónlist|djasslag|djass lag)\s?(?:{2})?$".format(
        _VERB, _ADJ, _POST
    ): _play_jazz,
    # Blues
    r"^(?:{0})\s?(?:{1})?\s(blús|blúsinn|blústónlist|blúslag|blús lag)\s?(?:{2})?$".format(
        _VERB, _ADJ, _POST
    ): _play_blues,
    # Rock
    r"^(?:{0})\s?(?:{1})?\s(rokk|rokktónlist|rokklag|rokk og ról)\s?(?:{2})?$".format(
        _VERB, _ADJ, _POST
    ): _play_rock,
    # Classical
    r"^(?:{0})\s?(?:{1})?\s(klassíska tónlist|klassík|klassískt)\s?(?:{2})?$".format(
        _VERB, _ADJ, _POST
    ): _play_classical,
    # Electronic
    r"^(?:{0})\s?(?:{1})?\s(raftónlist|elektróníska tónlist|elektrónískt)\s?(?:{2})?$".format(
        _VERB, _ADJ, _POST
    ): _play_electronic,
    # Play music by X
    r"^(?:{0})\s?(?:{1})?\s(?:tónlist|tónverk|lag|verk|slagara) (?:eftir|með|í flutningi) (.+)$".format(
        _VERB, _ADJ
    ): _play_music_by_artist,
    # Play song Y by X
    r"(?:{0}) (.+) (?:eftir|með|í flutningi) (.+)$".format(_VERB): _play_song_by_artist,
}


def handle_plain_text(q: Query) -> bool:
    """Handle a plain text query."""
    ql = q.query_lower.rstrip("?")

    # Check if it's a hardcoded barestring query
    handler_fn = HARDCODED_Q2H.get(ql)
    if handler_fn:
        handler_fn(ql, q, None)
    else:
        # Check if query matches regexes supported by this module
        matches = None
        for rx, fn in REGEX_Q2H.items():
            matches = re.search(rx, ql)
            if matches:
                fn(ql, q, matches)
                break

        if not matches:
            return False

    # OK, this is a query we've recognized and handled
    q.set_qtype(_PLAY_QTYPE)
    if not q.answer():
        q.set_answer(*gen_answer(_AFFIRMATIVE))

    return True
