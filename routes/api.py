"""

    Reynir: Natural language processing for Icelandic

    Copyright (C) 2019 Miðeind ehf.

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

from . import routes, better_jsonify, text_from_request, bool_from_request, restricted
from . import _MAX_URL_LENGTH, _MAX_UUID_LENGTH
from flask import request, current_app
import werkzeug
from tnttagger import ifd_tag
from db import SessionContext
from db.models import ArticleTopic
from treeutil import TreeUtility
from correct import check_grammar
from reynir.binparser import canonicalize_token
from article import Article as ArticleProxy
from query import process_query
from doc import SUPPORTED_DOC_MIMETYPES, MIMETYPE_TO_DOC_CLASS
from speech import get_synthesized_text_url
import logging


# Maximum number of query string variants
_MAX_QUERY_VARIANTS = 10
# Maximum length of each query string
_MAX_QUERY_LENGTH = 512
# Synthetic location for use in testing
_MIDEIND_LOCATION = (64.156896, -21.951200)  # Fiskislóð 31, 101 Reykjavík


@routes.route("/ifdtag.api", methods=["GET", "POST"])
@routes.route("/ifdtag.api/v<int:version>", methods=["GET", "POST"])
def ifdtag_api(version=1):
    """ API to parse text and return IFD tagged tokens in a simple and sparse JSON format """
    if not (1 <= version <= 1):
        # Unsupported version
        return better_jsonify(valid=False, reason="Unsupported version")

    try:
        text = text_from_request(request)
    except:
        return better_jsonify(valid=False, reason="Invalid request")

    pgs = ifd_tag(text)

    return better_jsonify(valid=bool(pgs), result=pgs)


@routes.route("/analyze.api", methods=["GET", "POST"])
@routes.route("/analyze.api/v<int:version>", methods=["GET", "POST"])
def analyze_api(version=1):
    """ Analyze text manually entered by the user, i.e. not coming from an article.
        This is a lower level API used by the Greynir web front-end. """
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


@routes.route("/correct.api", methods=["GET", "POST"])
@routes.route("/correct.api/v<int:version>", methods=["GET", "POST"])
@restricted
def correct_api(version=1):
    """ Correct text provided by the user, i.e. not coming from an article.
        This can be either an uploaded file or a string.
        This is a lower level API used by the Greynir web front-end. """
    if not (1 <= version <= 1):
        return better_jsonify(valid=False, reason="Unsupported version")

    file = request.files.get("file")
    if file is not None:
        # file is a Werkzeug FileStorage object
        mimetype = file.content_type
        if mimetype not in SUPPORTED_DOC_MIMETYPES:
            return better_jsonify(valid=False, reason="File type not supported")

        # Create document object from file and extract text
        try:
            # Instantiate appropriate class for mime type from file data
            # filename = werkzeug.secure_filename(file.filename)
            doc_class = MIMETYPE_TO_DOC_CLASS[mimetype]
            doc = doc_class(file.read())
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


@routes.route("/postag.api", methods=["GET", "POST"])
@routes.route("/postag.api/v<int:version>", methods=["GET", "POST"])
def postag_api(version=1):
    """ API to parse text and return POS tagged tokens in a verbose JSON format """
    if not (1 <= version <= 1):
        # Unsupported version
        return better_jsonify(valid=False, reason="Unsupported version")

    try:
        text = text_from_request(request)
    except:
        return better_jsonify(valid=False, reason="Invalid request")

    with SessionContext(commit=True) as session:
        pgs, stats, register = TreeUtility.tag_text(session, text, all_names=True)
        # Amalgamate the result into a single list of sentences
        if pgs:
            # Only process the first paragraph, if there are many of them
            if len(pgs) == 1:
                pgs = pgs[0]
            else:
                # More than one paragraph: gotta concatenate 'em all
                pa = []
                for pg in pgs:
                    pa.extend(pg)
                pgs = pa
        for sent in pgs:
            # Transform the token representation into a
            # nice canonical form for outside consumption
            # err = any("err" in t for t in sent)
            for t in sent:
                canonicalize_token(t)

    # Return the tokens as a JSON structure to the client
    return better_jsonify(valid=True, result=pgs, stats=stats, register=register)


@routes.route("/parse.api", methods=["GET", "POST"])
@routes.route("/parse.api/v<int:version>", methods=["GET", "POST"])
def parse_api(version=1):
    """ API to parse text and return POS tagged tokens in JSON format """
    if not (1 <= version <= 1):
        # Unsupported version
        return better_jsonify(valid=False, reason="Unsupported version")

    try:
        text = text_from_request(request)
    except:
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
                pa = []
                for pg in pgs:
                    pa.extend(pg)
                pgs = pa

    # Return the tokens as a JSON structure to the client
    return better_jsonify(valid=True, result=pgs, stats=stats, register=register)


@routes.route("/article.api", methods=["GET", "POST"])
@routes.route("/article.api/v<int:version>", methods=["GET", "POST"])
def article_api(version=1):
    """ Obtain information about an article, given its URL or id """

    if not (1 <= version <= 1):
        return better_jsonify(valid=False, reason="Unsupported version")

    url = request.values.get("url")
    uuid = request.values.get("id")

    if url:
        url = url.strip()[0:_MAX_URL_LENGTH]
    if uuid:
        uuid = uuid.strip()[0:_MAX_UUID_LENGTH]
    if url:
        # URL has priority, if both are specified
        uuid = None
    if not url and not uuid:
        return better_jsonify(valid=False, reason="No url or id specified in query")

    with SessionContext(commit=True) as session:

        if uuid:
            a = ArticleProxy.load_from_uuid(uuid, session)
        elif url.startswith("http:") or url.startswith("https:"):
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


@routes.route("/reparse.api", methods=["POST"])
@routes.route("/reparse.api/v<int:version>", methods=["POST"])
def reparse_api(version=1):
    """ Reparse an already parsed and stored article with a given UUID """
    if not (1 <= version <= 1):
        return better_jsonify(valid="False", reason="Unsupported version")

    uuid = request.form.get("id", "").strip()[0:_MAX_UUID_LENGTH]
    tokens = None
    register = {}
    stats = {}

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


@routes.route("/query.api", methods=["GET", "POST"])
@routes.route("/query.api/v<int:version>", methods=["GET", "POST"])
def query_api(version=1):
    """ Respond to a query string """

    if not (1 <= version <= 1):
        return better_jsonify(valid=False, reason="Unsupported version")

    # String with query
    q = request.values.get("q", "")

    # If voice is set, return a voice-friendly string
    voice = bool_from_request(request, "voice")
    # Specify a particular voice
    voice_id = request.values.get("voice_id")
    # If test is set, add a synthetic location, if not given
    test = bool_from_request(request, "test")

    # Obtain the query string(s) and the client's location, if present
    lat = request.values.get("latitude")
    lon = request.values.get("longitude")

    # Additional client info
    client_id = request.values.get("client_id")
    client_type = request.values.get("client_type")
    # When running behind an nginx reverse proxy, the client's remote 
    # address is passed to the web application via the "X-Real-IP" header
    client_ip = request.remote_addr or request.headers.get("X-Real-IP")

    # q param contains one or more |-separated strings
    mq = q.split("|")[0:_MAX_QUERY_VARIANTS]
    q = [m.strip()[0:_MAX_QUERY_LENGTH] for m in mq]

    # Attempt to convert the (lat, lon) location coordinates to floats
    location_present = bool(lat) and bool(lon)
    # For testing, insert a synthetic location if not already present
    if not location_present and test:
        lat, lon = _MIDEIND_LOCATION
        location_present = True
    if location_present:
        try:
            lat = float(lat)
            if not (-90.0 <= lat <= 90.0):
                location_present = False
        except ValueError:
            location_present = False
    if location_present:
        try:
            lon = float(lon)
            if not (-180.0 <= lon <= 180.0):
                location_present = False
        except ValueError:
            location_present = False

    # Auto-uppercasing can be turned off by sending autouppercase: false in the query JSON
    auto_uppercase = bool_from_request(request, "autouppercase", True)

    # Send the query to the query processor
    result = process_query(
        q,
        voice,
        auto_uppercase,
        location=(lat, lon) if location_present else None,
        remote_addr=client_ip,
        client_type=client_type,
        client_id=client_id,
    )

    # Get URL for response synthesized speech audio
    if voice:
        # If the result contains a "voice" key, return it
        audio = result.get("voice")
        url = get_synthesized_text_url(audio, voice_id=voice_id) if audio else None
        if url:
            result["audio"] = url
        response = result.get("response")
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
