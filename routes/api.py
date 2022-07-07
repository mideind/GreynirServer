"""

    Greynir: Natural language processing for Icelandic

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


    API routes
    Note: All routes ending with .api are configured not to be cached by nginx

"""

from typing import Dict, Any, List, Optional, cast

from datetime import datetime
import logging
import time

from flask import request, abort
from flask.wrappers import Response

from settings import Settings

from tnttagger import ifd_tag
from db import SessionContext
from db.models import ArticleTopic, Query, Feedback, QueryData
from treeutil import TreeUtility
from correct import check_grammar
from reynir.bintokenizer import TokenDict
from reynir.binparser import canonicalize_token
from article import Article as ArticleProxy
from query import process_query
from query import Query as QueryObject
from doc import SUPPORTED_DOC_MIMETYPES, Document
from speech import (
    text_to_audio_url,
    DEFAULT_VOICE,
    SUPPORTED_VOICES,
    RECOMMENDED_VOICES,
)
from util import read_api_key, icelandic_asciify
from queries.sonos import SonosClient
from queries.smartthings import SmartThingsClient

from . import routes, better_jsonify, text_from_request, bool_from_request
from . import MAX_URL_LENGTH, MAX_UUID_LENGTH
from . import async_task


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
    # Should not get here - this return is mostly to placate Pylance
    return Response("Error", status=403)


@routes.route("/correct.api", methods=["GET", "POST"])
@routes.route("/correct.api/v<int:version>", methods=["GET", "POST"])
def correct_api(version: int = 1) -> Response:
    """Correct text provided by the user, i.e. not coming from an article.
    This can be either an uploaded file or a string.
    This is a lower level API used by the Greynir web front-end."""
    if not (1 <= version <= 1):
        return better_jsonify(valid=False, reason="Unsupported version")

    file = request.files.get("file")
    if file is not None:
        # file is a Werkzeug FileStorage object
        mimetype = file.content_type
        if mimetype not in SUPPORTED_DOC_MIMETYPES:
            return better_jsonify(
                valid=False, reason=f"File type not supported: {mimetype}"
            )

        # Create document object from file and extract text
        try:
            # filename = werkzeug.secure_filename(file.filename)
            # Instantiate an appropriate class for the MIME type of the file
            doc = Document.for_mimetype(mimetype)(file.read())  # type: ignore
            text = doc.extract_text()
        except Exception as e:
            logging.warning("Exception in correct_api(): {0}".format(e))
            return better_jsonify(valid=False, reason="Error reading file")

    else:

        try:
            text = text_from_request(request)
        except Exception as e:
            logging.warning("Exception in correct_api(): {0}".format(e))
            return better_jsonify(valid=False, reason="Invalid request")

    pgs, stats = check_grammar(text)

    # Return the annotated paragraphs/sentences and stats
    # in a JSON structure to the client
    return better_jsonify(valid=True, result=pgs, stats=stats, text=text)


@routes.route("/correct.task", methods=["POST"])
@routes.route("/correct.task/v<int:version>", methods=["POST"])
@async_task  # This means that the function is automatically run on a separate thread
def correct_task(version: int = 1) -> Response:
    """Correct text provided by the user, i.e. not coming from an article.
    This can be either an uploaded file or a string.
    This is a lower level API used by the Greynir web front-end."""
    if not (1 <= version <= 1):
        return better_jsonify(valid=False, reason="Unsupported version")

    file = request.files.get("file")
    if file is not None:
        # Handle uploaded file
        # file is a proxy object that emulates a Werkzeug FileStorage object
        mimetype = file.mimetype
        if mimetype not in SUPPORTED_DOC_MIMETYPES:
            return better_jsonify(valid=False, reason="File type not supported")

        # Create document object from an uploaded file and extract its text
        try:
            # Instantiate an appropriate class for the MIME type of the file
            doc = Document.for_mimetype(mimetype)(file.read())  # type: ignore
            text = doc.extract_text()
        except Exception as e:
            logging.warning("Exception in correct_task(): {0}".format(e))
            return better_jsonify(valid=False, reason="Error reading file")

    else:

        # Handle POSTed form data or plain text string
        try:
            text = text_from_request(request)
        except Exception as e:
            logging.warning("Exception in correct_task(): {0}".format(e))
            return better_jsonify(valid=False, reason="Invalid request")

    # assert isinstance(request, _RequestProxy)
    pgs, stats = check_grammar(text, progress_func=cast(Any, request).progress_func)

    # Return the annotated paragraphs/sentences and stats
    # in a JSON structure to the client
    return better_jsonify(valid=True, result=pgs, stats=stats, text=text)


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

    return Response("Error", status=403)


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

    return Response("Error", status=403)


@routes.route("/article.api", methods=["GET", "POST"])
@routes.route("/article.api/v<int:version>", methods=["GET", "POST"])
def article_api(version: int = 1) -> Response:
    """Obtain information about an article, given its URL or id"""

    if not (1 <= version <= 1):
        return better_jsonify(valid=False, reason="Unsupported version")

    url: Optional[str] = request.values.get("url")
    uuid: Optional[str] = request.values.get("id")

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

    return Response("Error", status=403)


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
    qs: str = request.values.get("q", "")
    # q param contains one or more |-separated strings
    mq: List[str] = qs.split("|")[0:_MAX_QUERY_VARIANTS]
    # Retain only nonempty strings in qs
    q: List[str] = list(filter(None, (m.strip()[0:_MAX_QUERY_LENGTH] for m in mq)))

    # If voice is set, return a voice-friendly string
    voice = bool_from_request(request, "voice")
    # Request a particular voice
    voice_id: str = icelandic_asciify(request.values.get("voice_id", "Dora"))
    # Request a particular voice speed
    try:
        voice_speed = float(request.values.get("voice_speed", 1.0))
    except ValueError:
        voice_speed = 1.0

    # If test is set to True, we
    # (1) add a synthetic location, if not given; and
    # (2) bypass the cache
    test = bool_from_request(request, "test")

    # Obtain the client's location, if present
    slat: Optional[str] = request.values.get("latitude")
    slon: Optional[str] = request.values.get("longitude")

    # Additional client info
    # !!! FIXME: The client_id for web browser clients is the browser version,
    # !!! which is not particularly useful. Consider using an empty string instead.
    client_id: Optional[str] = request.values.get("client_id")
    client_type: Optional[str] = request.values.get("client_type")
    client_version: Optional[str] = request.values.get("client_version")
    # When running behind an nginx reverse proxy, the client's remote
    # address is passed to the web application via the "X-Real-IP" header
    client_ip = request.remote_addr or request.headers.get("X-Real-IP")

    # Query is marked as private and shouldn't be logged
    private = bool_from_request(request, "private")

    # Attempt to convert the (lat, lon) location coordinates to floats
    location_present = bool(slat) and bool(slon)

    lat, lon = 0.0, 0.0

    # For testing, insert a synthetic location if not already present
    if not location_present and test:
        lat, lon = _MIDEIND_LOCATION
        location_present = True

    if location_present and not test:
        try:
            lat = float(slat or "0")
            if not (-90.0 <= lat <= 90.0):
                location_present = False
        except ValueError:
            location_present = False

    if location_present and not test:
        try:
            lon = float(slon or "0")
            if not (-180.0 <= lon <= 180.0):
                location_present = False
        except ValueError:
            location_present = False

    # Auto-uppercasing can be turned off by sending autouppercase: false in the query JSON
    auto_uppercase = bool_from_request(request, "autouppercase", True)
    if Settings.DEBUG:
        auto_uppercase = True  # !!! DEBUG - to emulate mobile client behavior

    # Send the query to the query processor
    result = process_query(
        q,
        voice,
        auto_uppercase=auto_uppercase,
        location=(lat, lon) if location_present else None,
        remote_addr=client_ip,
        client_type=client_type,
        client_id=client_id,
        client_version=client_version,
        bypass_cache=True,  # Settings.DEBUG,
        private=private,
    )

    # Get URL for response synthesized speech audio
    if voice and "voice" in result:
        # If the result contains a "voice" key, return it
        audio = result["voice"]
        url = (
            text_to_audio_url(audio, voice_id=voice_id, speed=voice_speed)
            if audio
            else None
        )
        if url:
            result["audio"] = url
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


@routes.route("/query_history.api", methods=["GET", "POST"])
@routes.route("/query_history.api/v<int:version>", methods=["GET", "POST"])
def query_history_api(version: int = 1) -> Response:
    """Delete query history and/or query data for a particular unique client ID."""

    if not (1 <= version <= 1):
        return better_jsonify(valid=False, reason="Unsupported version")

    resp: Dict[str, Any] = dict(valid=True)

    # Calling this endpoint requires the Greynir API key
    key = request.values.get("api_key")
    gak = read_api_key("GreynirServerKey")
    if not gak or not key or key != gak:
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
        session.execute(Query.table().delete().where(Query.client_id == client_id))
        # Clear all user query data
        if action == "clear_all":
            # pylint: disable=no-member
            session.execute(
                QueryData.table().delete().where(QueryData.client_id == client_id)
            )

    return better_jsonify(**resp)


@routes.route("/speech.api", methods=["GET", "POST"])
@routes.route("/speech.api/v<int:version>", methods=["GET", "POST"])
def speech_api(version: int = 1) -> Response:
    """Send in text, receive URL to speech synthesised audio file."""

    if not (1 <= version <= 1):
        return better_jsonify(valid=False, reason="Unsupported version")

    reply: Dict[str, Any] = dict(err=True)

    # Calling this endpoint requires the Greynir API key
    key = request.values.get("api_key")
    gak = read_api_key("GreynirServerKey")
    if not gak or not key or key != gak:
        reply["errmsg"] = "Invalid or missing API key."
        return better_jsonify(**reply)

    text = request.values.get("text")
    if not text:
        return better_jsonify(**reply)

    fmt = request.values.get("format", "ssml")
    if fmt not in ["text", "ssml"]:
        fmt = "ssml"
    voice_id = icelandic_asciify(request.values.get("voice_id", "Dora"))
    speed = request.values.get("voice_speed", 1.0)
    if not isinstance(speed, float):
        try:
            speed = float(speed)
            if speed < 0.1 or speed > 3.0:
                speed = 1.0
        except Exception:
            speed = 1.0

    try:
        url = text_to_audio_url(text, text_format=fmt, voice_id=voice_id, speed=speed)
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


@routes.route("/feedback.api", methods=["POST"])
@routes.route("/feedback.api/v<int:version>", methods=["POST"])
def feedback_api(version: int = 1) -> Response:
    """Endpoint to accept submitted feedback forms"""

    if not (1 <= version <= 1):
        return better_jsonify(valid=False, reason="Unsupported version")

    name = request.values.get("name")
    email = request.values.get("email")
    comment = request.values.get("comment")
    topic = request.values.get("topic")

    if comment:
        with SessionContext(commit=True) as session:
            try:
                qrow = Feedback(
                    timestamp=datetime.utcnow(),
                    topic=topic,
                    name=name,
                    email=email,
                    comment=comment,
                )
                session.add(qrow)
                return better_jsonify(valid=True)
            except Exception as e:
                logging.error("Error saving feedback to db: {0}".format(e))

    return better_jsonify(valid=False)


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

    Jóhann's comment:
    Data format example for IoT device from js code:

    'client_id': clientID,
    'key': "iot_lights",
    'data': {
        'philips_hue': {
            'credentials': {
                'username': username,
                'ip_address': IP address,
            },
            'data': {
                'groups': {name, id}, {name, id}, ...
        },
    };

    """

    if not (1 <= version <= 1):
        return better_jsonify(valid=False, reason="Unsupported version")

    qdata = request.get_json()
    if qdata is None:
        return better_jsonify(valid=False, errmsg="Empty request.")

    # Calling this endpoint requires the Greynir API key
    key = qdata.get("api_key")
    gak = read_api_key("GreynirServerKey")
    # if not gak or not key or key != gak:
    #     return better_jsonify(valid=False, errmsg="Invalid or missing API key.")

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


_WAV_MIMETYPES = frozenset(("audio/wav", "audio/x-wav"))


@routes.route("/upload_speech_audio.api", methods=["GET"])
@routes.route("/upload_speech_audio.api/v<int:version>", methods=["GET"])
def upload_speech_audio(version: int = 1) -> Response:
    """Receives uploaded speech audio for a query."""

    # This is disabled for now
    return better_jsonify(valid=False, errmsg="Not implemented")

    # This code is currently here only for debugging/development purposes
    # if not (1 <= version <= 1):
    #     return better_jsonify(valid=False, errmsg="Unsupported version")

    # file = request.files.get("file")
    # if file is not None:
    #     # file is a Werkzeug FileStorage object
    #     mimetype = file.content_type
    #     if mimetype not in _WAV_MIMETYPES:
    #         return better_jsonify(
    #             valid=False, reason=f"File type not supported: {mimetype}"
    #         )
    #     try:
    #         with open("/tmp/myfile.wav", "wb") as f:
    #             # Writing data to a file
    #             f.write(file.read())
    #     except Exception as e:
    #         logging.warning("Exception in upload_speech_audio(): {0}".format(e))
    #         return better_jsonify(valid=False, reason="Error reading file")

    # return better_jsonify(valid=True, msg="Audio data received")


@routes.route("/connect_sonos.api", methods=["GET"])
@routes.route("/connect_sonos.api/v<int:version>", methods=["GET", "POST"])
def sonos_code(version: int = 1) -> Response:
    """
    API endpoint to connect to Sonos speakers
    """
    print("sonos code")
    args = request.args
    client_id = args.get("state")
    code = args.get("code")
    code = {
        "sonos": {"credentials": {"code": code}}
    }  # create a dictonary with the code
    if client_id and code:
        success = QueryObject.store_query_data(
            client_id, "iot_speakers", code, update_in_place=True
        )
        if success:
            device_data = code
            # Create an instance of the SonosClient class. This will automatically create the rest of the credentials needed.
            sonos_client = SonosClient(device_data, client_id)
            sonos_voice_clip = (
                f"Hæ! Embla hérna! Ég er búin að tengja þennan Sónos hátalara."
            )
            sonos_client.play_chime()
            time.sleep(1.3)
            sonos_client.play_audio_clip(
                text_to_audio_url(sonos_voice_clip)
            )  # Send the above message to the Sonos speaker
            return better_jsonify(valid=True, msg="Registered sonos code")
    return better_jsonify(valid=False, errmsg="Error registering sonos code.")


@routes.route("/connect_smartthings.api", methods=["GET"])
@routes.route("/connect_smartthings.api/v<int:version>", methods=["GET", "POST"])
def smartthings_code(version: int = 1) -> Response:
    """
    API endpoint to connect to Sonos speakers
    """
    print("smartthings code")
    args = request.args
    client_id = args.get("state")
    code = args.get("code")
    code = {
        "smartthings": {"credentials": {"code": code}}
    }  # create a dictonary with the code
    if client_id and code:
        success = QueryObject.store_query_data(
            client_id, "iot_hubs", code, update_in_place=True
        )
        if success:
            device_data = code
            smartthings_client = SmartThingsClient(device_data, client_id)
            # device_data = code
            # Create an instance of the SonosClient class. This will automatically create the rest of the credentials needed.
            return better_jsonify(valid=True, msg="Registered smartthings code")
    return better_jsonify(valid=False, errmsg="Error registering smartthings code.")


# def sonos_code2(version: int = 1) -> Response:
#     print("sonos code")
#     args = request.args
#     client_id = args.get("state")
#     code = args.get("code")
#     code = {"sonos": {"credentials": {"code": code}}}
#     if client_id and code:
#         success = QueryObject.store_query_data(
#             client_id, "iot_speakers", code, update_in_place=True
#         )
#         if success:
#             return better_jsonify(valid=True, msg="Registered sonos code")

#     return better_jsonify(valid=False, errmsg="Error registering sonos code.")
