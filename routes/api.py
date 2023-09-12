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


    API routes
    Note: All routes ending with .api are configured not to be cached by nginx

"""

from typing import Dict, Any, Iterable, List, Optional, cast

from datetime import datetime
import logging

from flask import request, abort
from flask.wrappers import Response, Request

from settings import Settings

from tnttagger import ifd_tag
from db import SessionContext
from db.models import ArticleTopic, Query, QueryClientData, Summary
from geo import LatLonTuple
from tree.util import TreeUtility
from reynir.bintokenizer import TokenDict
from reynir.binparser import canonicalize_token
from article import Article as ArticleProxy
from queries import process_query
from queries import Query as QueryObject
from speech import (
    GreynirSSMLParser,
    text_to_audio_url,
    DEFAULT_VOICE,
    SUPPORTED_VOICES,
    RECOMMENDED_VOICES,
    DEFAULT_VOICE_SPEED,
)
from speech.voices import voice_for_locale
from queries.util.openai_gpt import summarize
from utility import read_txt_api_key, icelandic_asciify

from . import routes, better_jsonify, text_from_request, bool_from_request
from . import MAX_URL_LENGTH, MAX_UUID_LENGTH


@routes.route("/ifdtag.api", methods=["GET", "POST"])
@routes.route("/ifdtag.api/v<int:version>", methods=["GET", "POST"])
def ifdtag_api(version: int = 1) -> Response:
    """API to parse text and return IFD tagged tokens in a simple and sparse JSON format"""
    if not (1 <= version <= 1):
        # Unsupported version
        return better_jsonify(valid=False, reason="Unsupported version")

    try:
        text = text_from_request(request)
    except Exception:
        return better_jsonify(valid=False, reason="Invalid request")

    pgs = ifd_tag(text)

    return better_jsonify(valid=bool(pgs), result=pgs)


@routes.route("/analyze.api", methods=["GET", "POST"])
@routes.route("/analyze.api/v<int:version>", methods=["GET", "POST"])
def analyze_api(version: int = 1) -> Response:
    """Analyze text manually entered by the user, i.e. not coming from an article.
    This is a lower level API used by the Greynir web front-end."""
    if not (1 <= version <= 1):
        return better_jsonify(valid=False, reason="Unsupported version")
    # try:
    text = text_from_request(request)
    # except:
    #     return better_jsonify(valid=False, reason="Invalid request")
    with SessionContext(commit=True) as session:
        pgs, stats, register = TreeUtility.tag_text(session, text, all_names=True)
        # Return the tokens as a JSON structure to the client
        return better_jsonify(valid=True, result=pgs, stats=stats, register=register)


@routes.route("/postag.api", methods=["GET", "POST"])
@routes.route("/postag.api/v<int:version>", methods=["GET", "POST"])
def postag_api(version: int = 1) -> Response:
    """API to parse text and return POS tagged tokens in a verbose JSON format"""
    if not (1 <= version <= 1):
        # Unsupported version
        return better_jsonify(valid=False, reason="Unsupported version")

    try:
        text = text_from_request(request)
    except Exception:
        return better_jsonify(valid=False, reason="Invalid request")

    with SessionContext(commit=True) as session:
        pgs, stats, register = TreeUtility.tag_text(session, text, all_names=True)
        # Amalgamate the result into a single list of sentences
        pa: List[List[TokenDict]] = []
        if pgs:
            # Only process the first paragraph, if there are many of them
            if len(pgs) == 1:
                pa = pgs[0]
            else:
                # More than one paragraph: gotta concatenate 'em all
                for pg in pgs:
                    pa.extend(pg)
        for sent in pa:
            # Transform the token representation into a
            # nice canonical form for outside consumption
            # err = any("err" in t for t in sent)
            for t in sent:
                canonicalize_token(t)

        # Return the tokens as a JSON structure to the client
        return better_jsonify(valid=True, result=pa, stats=stats, register=register)


@routes.route("/parse.api", methods=["GET", "POST"])
@routes.route("/parse.api/v<int:version>", methods=["GET", "POST"])
def parse_api(version: int = 1) -> Response:
    """API to parse text and return POS tagged tokens in JSON format"""
    if not (1 <= version <= 1):
        # Unsupported version
        return better_jsonify(valid=False, reason="Unsupported version")

    try:
        text = text_from_request(request)
    except Exception:
        return better_jsonify(valid=False, reason="Invalid request")

    with SessionContext(commit=True) as session:
        pgs, stats, register = TreeUtility.parse_text(session, text, all_names=True)
        # In this case, we should always get a single paragraph back
        if pgs:
            # Only process the first paragraph, if there are many of them
            if len(pgs) == 1:
                pgs = pgs[0]
            else:
                # More than one paragraph: gotta concatenate 'em all
                pa: List[List[TokenDict]] = []
                for pg in pgs:
                    pa.extend(pg)
                pgs = pa

        # Return the tokens as a JSON structure to the client
        return better_jsonify(valid=True, result=pgs, stats=stats, register=register)


@routes.route("/article.api", methods=["GET", "POST"])
@routes.route("/article.api/v<int:version>", methods=["GET", "POST"])
def article_api(version: int = 1) -> Response:
    """Obtain information about an article, given its URL or id"""

    if not (1 <= version <= 1):
        return better_jsonify(valid=False, reason="Unsupported version")

    rv = cast(Dict[str, str], request.values)
    url: Optional[str] = rv.get("url")
    uuid: Optional[str] = rv.get("id")

    if url:
        url = url.strip()[0:MAX_URL_LENGTH]
    if uuid:
        uuid = uuid.strip()[0:MAX_UUID_LENGTH]
    if url:
        # URL has priority, if both are specified
        uuid = None
    if not url and not uuid:
        return better_jsonify(valid=False, reason="No url or id specified in query")

    with SessionContext(commit=True) as session:
        if uuid:
            a = ArticleProxy.load_from_uuid(uuid, session)
        elif url and url.startswith(("http:", "https:")):
            a = ArticleProxy.load_from_url(url, session)
        else:
            a = None

        if a is None:
            return better_jsonify(valid=False, reason="Article not found")

        if a.html is None:
            return better_jsonify(valid=False, reason="Unable to fetch article")

        # Prepare the article for display
        a.prepare(session)
        register = a.create_register(session, all_names=True)
        # Fetch names of article topics, if any
        topics = (
            session.query(ArticleTopic).filter(ArticleTopic.article_id == a.uuid).all()
        )
        topics = [dict(name=t.topic.name, id=t.topic.identifier) for t in topics]

        return better_jsonify(
            valid=True,
            url=a.url,
            id=a.uuid,
            heading=a.heading,
            author=a.author,
            ts=a.timestamp.isoformat()[0:19],
            num_sentences=a.num_sentences,
            num_parsed=a.num_parsed,
            ambiguity=a.ambiguity,
            register=register,
            topics=topics,
        )


@routes.route("/summary.api", methods=["GET", "POST"])
@routes.route("/summary.api/v<int:version>", methods=["GET", "POST"])
def summary_api(version: int = 1) -> Response:
    """Obtain a summary of an article, given its URL or id"""

    if not (1 <= version <= 1):
        return better_jsonify(valid=False, reason="Unsupported version")

    rv = cast(Dict[str, str], request.values)
    url: Optional[str] = rv.get("url")
    uuid: Optional[str] = rv.get("id")

    if url:
        url = url.strip()[0:MAX_URL_LENGTH]
    if uuid:
        uuid = uuid.strip()[0:MAX_UUID_LENGTH]
    if url:
        # URL has priority, if both are specified
        uuid = None
    if not url and not uuid:
        return better_jsonify(valid=False, reason="No url or id specified in query")

    with SessionContext(commit=True) as session:
        if uuid:
            a = ArticleProxy.load_from_uuid(uuid, session)
        elif url and url.startswith(("http:", "https:")):
            a = ArticleProxy.load_from_url(url, session)
        else:
            a = None

        if a is None:
            return better_jsonify(valid=False, reason="Article not found")

        if a.html is None:
            return better_jsonify(valid=False, reason="Unable to fetch article")

        # Fetch names of article topics, if any
        topics = (
            session.query(ArticleTopic).filter(ArticleTopic.article_id == a.uuid).all()
        )
        topics = [dict(name=t.topic.name, id=t.topic.identifier) for t in topics]

        # Generate a summary of the article in the indicated languages,
        # if not already available
        summary_rows: Dict[str, Optional[Summary]] = dict(
            is_IS=None, en_US=None, pl_PL=None
        )
        sr: Iterable[Summary] = (
            session.query(Summary).filter(Summary.article_id == a.uuid).all()
        )
        # Collect the summary data we already have
        for s in sr:
            if s.language in summary_rows:
                summary_rows[s.language] = s
        # Find out which summaries are missing
        missing = [k for k, v in summary_rows.items() if v is None]
        if missing:
            # At least one summary is missing: generate it
            now = datetime.utcnow()
            # Collect the text of the article from the tokens
            text = a.text()
            # Update our summaries
            summaries = summarize(text, missing)
            # Insert summaries for the missing languages
            for lang in missing:
                if lang not in summaries:
                    continue
                sr = Summary(
                    article_id=a.uuid,
                    language=lang,
                    summary=summaries[lang],
                    # Currently no text for other languages,
                    # but this may be added later via GPT translation
                    text=text if lang == "is_IS" else "",
                    timestamp=now,
                )
                session.add(sr)
                summary_rows[lang] = sr

        return better_jsonify(
            valid=True,
            url=a.url,
            id=a.uuid,
            heading=a.heading,
            author=a.author,
            ts=a.timestamp.isoformat()[0:19],
            num_sentences=a.num_sentences,
            topics=topics,
            summary={k: v.summary for k, v in summary_rows.items() if v},
        )


@routes.route("/reparse.api", methods=["POST"])
@routes.route("/reparse.api/v<int:version>", methods=["POST"])
def reparse_api(version: int = 1) -> Response:
    """Reparse an already parsed and stored article with a given UUID"""
    if not (1 <= version <= 1):
        return better_jsonify(valid="False", reason="Unsupported version")

    uuid = request.form.get("id", "").strip()[0:MAX_UUID_LENGTH]
    tokens = None
    register = {}
    stats = {}

    if not uuid:
        return better_jsonify(valid=True, error=True, errmsg="Missing ID param")

    with SessionContext(commit=True) as session:
        # Load the article
        a = ArticleProxy.load_from_uuid(uuid, session)
        if a is not None:
            # Found: Parse it (with a fresh parser) and store the updated version
            a.parse(session, verbose=True, reload_parser=True)
            # Save the tokens
            tokens = a.tokens
            # Build register of person names
            register = a.create_register(session)
            stats = dict(
                num_tokens=a.num_tokens,
                num_sentences=a.num_sentences,
                num_parsed=a.num_parsed,
                ambiguity=a.ambiguity,
            )

    # Return the tokens as a JSON structure to the client,
    # along with a name register and article statistics
    return better_jsonify(valid=True, result=tokens, register=register, stats=stats)


def file_url_to_host_url(url: str, r: Request) -> str:
    """Convert a local file:// URL to a http(s):// URL."""
    if url.startswith("file://"):
        try:
            idx = url.index("static/audio/")  # A bit hacky
            path = url[idx:]
            return f"{request.host_url}{path}"
        except:
            pass
    return url


# Maximum number of query string variants
_MAX_QUERY_VARIANTS = 10
# Maximum length of each query string
_MAX_QUERY_LENGTH = 512
# Synthetic location for use in testing
_MIDEIND_LOCATION = (64.156896, -21.951200)  # Fiskislóð 31, 101 Reykjavík


@routes.route("/query.api", methods=["GET", "POST"])
@routes.route("/query.api/v<int:version>", methods=["GET", "POST"])
def query_api(version: int = 1) -> Response:
    """Respond to a query string"""

    if not (1 <= version <= 1):
        return better_jsonify(valid=False, reason="Unsupported version")

    # String with query
    rv = cast(Dict[str, str], request.values)
    qs: str = rv.get("q", "")
    # q param contains one or more |-separated strings
    mq: List[str] = qs.split("|")[0:_MAX_QUERY_VARIANTS]
    # Retain only nonempty strings in qs
    q: List[str] = list(filter(None, (m.strip()[0:_MAX_QUERY_LENGTH] for m in mq)))

    # If voice is set, return a voice-friendly string
    voice = bool_from_request(request, "voice")
    # Request a particular voice
    voice_id: str = icelandic_asciify(rv.get("voice_id", DEFAULT_VOICE))
    # Request a particular voice speed
    try:
        voice_speed = float(rv.get("voice_speed", DEFAULT_VOICE_SPEED))
    except ValueError:
        voice_speed = DEFAULT_VOICE_SPEED

    # If test is set to True, we
    # (1) add a synthetic location, if not given; and
    # (2) bypass the cache
    test = bool_from_request(request, "test")

    # Obtain the client's location, if present
    slat: str = rv.get("latitude", "")
    slon: str = rv.get("longitude", "")

    # Additional client info
    # !!! FIXME: The client_id for web browser clients is the browser user agent,
    # !!! which is not particularly useful. Consider using an empty string instead.
    client_id: Optional[str] = rv.get("client_id")
    client_type: Optional[str] = rv.get("client_type")
    client_version: Optional[str] = rv.get("client_version")
    # When running behind an nginx reverse proxy, the client's remote
    # address is passed to the web application via the "X-Real-IP" header
    client_ip = request.remote_addr or request.headers.get("X-Real-IP")

    # Query is marked as private and shouldn't be logged
    private = bool_from_request(request, "private")

    # Attempt to convert the (lat, lon) location coordinates to floats
    location_present = bool(slat) and bool(slon)

    loc: Optional[LatLonTuple] = None

    if test and not location_present:
        # For testing, insert a synthetic location if not already present
        loc = _MIDEIND_LOCATION
        location_present = True

    if location_present:
        try:
            lat = float(slat)
            if not (-90.0 <= lat <= 90.0):
                raise ValueError("Latitude out of range")
            lon = float(slon)
            if not (-180.0 <= lon <= 180.0):
                raise ValueError("Longitude out of range")
            loc = (lat, lon)
        except ValueError:
            pass

    # Auto-uppercasing can be turned off by sending autouppercase: false in the query JSON
    auto_uppercase = bool_from_request(request, "autouppercase", True)
    if Settings.DEBUG:
        auto_uppercase = True  # !!! DEBUG - to emulate mobile client behavior

    # Send the query to the query processor
    result = process_query(
        q,
        voice,
        auto_uppercase=auto_uppercase,
        location=loc,
        remote_addr=client_ip,
        client_type=client_type,
        client_id=client_id,
        client_version=client_version,
        bypass_cache=True,  # Settings.DEBUG,
        private=private,
        authenticated=_has_valid_api_key(request),
    )

    # Get URL for response synthesized speech audio
    if voice and "voice" in result:
        # If the result contains a "voice" key, return it
        v = result["voice"]
        if v:
            # Parse <greynir> SSML tags and
            # phonetically transcribe their contents
            result["voice"] = v = GreynirSSMLParser(voice_id).transcribe(v)
            # Check if a specific voice or voice locale was set by query module
            vid = voice_id
            if "voice_id" in result:
                vid = result["voice_id"]
            elif "voice_locale" in result and result["voice_locale"] != "is_IS":
                # If a voice locale other than Icelandic is requested,
                # use the default voice for that locale.
                vid = voice_for_locale(result["voice_locale"])
            result["voice_id"] = vid
            # Create audio data
            url = text_to_audio_url(v, voice_id=vid, speed=voice_speed)
            if url:
                result["audio"] = file_url_to_host_url(url, request)
        response = cast(Optional[Dict[str, str]], result.get("response"))
        if response:
            if "sources" in response:
                # A list of sources is not needed for voice results
                del response["sources"]
            if "answers" in response:
                answers = response["answers"]
                # If there is a multi-item answer list
                # in the response, delete all but the first
                # item in the list to simplify the response
                if isinstance(answers, list):
                    del answers[1:]
    else:
        if "voice" in result:
            # Voice result not needed, so don't send it to the client
            del result["voice"]

    return better_jsonify(**result)


def _has_valid_api_key(req: Request, allow_query_param: bool = False) -> bool:
    """Check that the request has a valid API key.
    The key can be provided either via an Authorization header or
    (optionally) via a query parameter named 'api_key' (for legacy reasons)."""
    key = request.headers.get("Authorization", "")
    if not key and allow_query_param:
        key = cast(Dict[str, str], request.values).get("api_key", "")
    gak = read_txt_api_key("GreynirServerKey")  # Cached
    return all((gak, key, key == gak))


@routes.route("/query_history.api", methods=["GET", "POST"])
@routes.route("/query_history.api/v<int:version>", methods=["GET", "POST"])
def query_history_api(version: int = 1) -> Response:
    """Delete query history and/or query data for a particular unique client ID."""

    if not (1 <= version <= 1):
        return better_jsonify(valid=False, reason="Unsupported version")

    resp: Dict[str, Any] = dict(valid=True)

    if not _has_valid_api_key(request, allow_query_param=True):
        resp["errmsg"] = "Invalid or missing API key."
        resp["valid"] = False
        return better_jsonify(**resp)

    VALID_ACTIONS = frozenset(("clear", "clear_all"))

    action = request.values.get("action")
    client_id = request.values.get("client_id")

    if not client_id:
        return better_jsonify(valid=False, errmsg="Missing parameters")
    if action not in VALID_ACTIONS:
        return better_jsonify(
            valid=False,
            errmsg=f"Invalid action parameter '{action}'. Should be in {VALID_ACTIONS}.",
        )

    with SessionContext(commit=True) as session:
        # Clear all logged user queries
        # pylint: disable=no-member
        q = cast(Any, Query).table()
        session.execute(q.delete().where(Query.client_id == client_id))
        # Clear all user query data
        if action == "clear_all":
            # pylint: disable=no-member
            qd = cast(Any, QueryClientData).table()
            session.execute(qd.delete().where(QueryClientData.client_id == client_id))

    return better_jsonify(**resp)


@routes.route("/speech.api", methods=["GET", "POST"])
@routes.route("/speech.api/v<int:version>", methods=["GET", "POST"])
def speech_api(version: int = 1) -> Response:
    """Send in text, receive URL to speech synthesized audio file."""

    if not (1 <= version <= 1):
        return better_jsonify(valid=False, reason="Unsupported version")

    reply: Dict[str, Any] = dict(err=True)

    if not _has_valid_api_key(request, allow_query_param=True):
        reply["errmsg"] = "Invalid or missing API key."
        return better_jsonify(**reply)

    rv = cast(Dict[str, str], request.values)
    text = rv.get("text")
    if not text:
        return better_jsonify(**reply)

    fmt = rv.get("format", "ssml")
    if fmt not in ["text", "ssml"]:
        fmt = "ssml"
    voice_id = icelandic_asciify(rv.get("voice_id", DEFAULT_VOICE))
    try:
        voice_speed = float(rv.get("voice_speed", DEFAULT_VOICE_SPEED))
    except ValueError:
        voice_speed = DEFAULT_VOICE_SPEED

    try:
        url = text_to_audio_url(
            text,
            text_format=fmt,
            voice_id=voice_id,
            speed=voice_speed,
        )
        if url:
            url = file_url_to_host_url(url, request)
    except Exception:
        return better_jsonify(**reply)

    reply["audio_url"] = url
    reply["err"] = False

    return better_jsonify(**reply)


@routes.route("/voices.api", methods=["GET", "POST"])
@routes.route("/voices.api/v<int:version>", methods=["GET", "POST"])
def voices_api(version: int = 1) -> Response:
    """Returns list of supported speech synthesis voices as JSON."""

    if not (1 <= version <= 1):
        return better_jsonify(valid=False, reason="Unsupported version")

    return better_jsonify(
        valid=True,
        default=DEFAULT_VOICE,
        supported=sorted(list(SUPPORTED_VOICES)),
        recommended=sorted(list(RECOMMENDED_VOICES)),
    )


@routes.route("/exit.api", methods=["GET"])
def exit_api():
    """Allow a server to be remotely terminated if running in debug mode"""
    if not Settings.DEBUG:
        abort(404)
    shutdown_func = request.environ.get("werkzeug.server.shutdown")
    if shutdown_func is None:
        raise RuntimeError("Not running with the Werkzeug Server")
    shutdown_func()
    return "The server has shut down"


@routes.route("/register_query_data.api", methods=["POST"])
@routes.route("/register_query_data.api/v<int:version>", methods=["POST"])
def register_query_data_api(version: int = 1) -> Response:
    """
    Stores or updates query data for the given client ID

    Hinrik's comment:
    Data format example from js code
    {
        'device_id': device_id,
        'key': 'smartlights',
        'data': {
            'smartlights': {
                'selected_light': 'philips_hue',
                'philips_hue': {
                    'username': username,
                    'ipAddress': internalipaddress
                }
            }
        }
    }

    """

    if not (1 <= version <= 1):
        return better_jsonify(valid=False, reason="Unsupported version")

    qdata = cast(Optional[Dict[str, Any]], cast(Any, request).json)
    if qdata is None:
        return better_jsonify(valid=False, errmsg="Empty request.")

    if not _has_valid_api_key(request, allow_query_param=True):
        return better_jsonify(valid=False, errmsg="Invalid or missing API key.")

    if (
        not qdata
        or "data" not in qdata
        or "key" not in qdata
        or "client_id" not in qdata
    ):
        return better_jsonify(valid=False, errmsg="Missing parameters.")

    success = QueryObject.store_query_data(
        qdata["client_id"], qdata["key"], qdata["data"]
    )
    if success:
        return better_jsonify(valid=True, msg="Query data registered")

    return better_jsonify(valid=False, errmsg="Error registering query data.")
