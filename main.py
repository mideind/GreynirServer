#!/usr/bin/env python3
"""

    Reynir: Natural language processing for Icelandic

    Web server main module

    Copyright (C) 2018 Miðeind ehf.

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


    This module is written in Python 3 and is compatible with PyPy3.

    This is the main module of the Greynir web server. It uses Flask
    as its templating and web server engine. In production, this module is
    typically run inside Gunicorn (using servlets) under nginx or a
    compatible WSGi HTTP(S) server. For development, it can be run
    directly from the command line and accessed through port 5000.

"""

import sys
import os
import time
import random
import re
import logging
from datetime import datetime
from functools import wraps
from decimal import Decimal

from flask import Flask
from flask import render_template, make_response, jsonify, redirect, url_for
from flask import request, send_from_directory
from flask.wrappers import Response

import reynir
from settings import Settings, ConfigError, changedlocale
from reynir.bindb import BIN_Db
from nertokenizer import tokenize_and_recognize, correct_spaces
from reynir.binparser import canonicalize_token
from reynir.fastparser import Fast_Parser, ParseForestFlattener
from article import Article as ArticleProxy
from treeutil import TreeUtility
from scraperdb import (
    SessionContext,
    desc,
    Root,
    Person,
    Article,
    ArticleTopic,
    Topic,
    GenderQuery,
    StatsQuery,
)
from query import Query
from search import Search
from getimage import get_image_url
from tnttagger import ifd_tag


# Initialize Flask framework

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False  # We're fine with using Unicode/UTF-8
app.config["TEMPLATES_AUTO_RELOAD"] = True

from flask import current_app


def debug():
    # Call this to trigger the Flask debugger on purpose
    assert current_app.debug == False, "Don't panic! You're here by request of debug()"


# Utilities for Flask/Jinja2 formatting of numbers using the Icelandic locale

def make_pattern(rep_dict):
    return re.compile("|".join([re.escape(k) for k in rep_dict.keys()]), re.M)


def multiple_replace(string, rep_dict, pattern=None):
    """ Perform multiple simultaneous replacements within string """
    if pattern is None:
        pattern = make_pattern(rep_dict)
    return pattern.sub(lambda x: rep_dict[x.group(0)], string)


_REP_DICT_IS = {",": ".", ".": ","}
_PATTERN_IS = make_pattern(_REP_DICT_IS)


@app.template_filter("format_is")
def format_is(r, decimals=0):
    """ Flask/Jinja2 template filter to format a number for the Icelandic locale """
    fmt = "{0:,." + str(decimals) + "f}"
    return multiple_replace(fmt.format(float(r)), _REP_DICT_IS, _PATTERN_IS)


@app.template_filter("format_ts")
def format_ts(ts):
    """ Flask/Jinja2 template filter to format a timestamp """
    return str(ts)[0:19]


# Flask cache busting for static .css and .js files

@app.url_defaults
def hashed_url_for_static_file(endpoint, values):
    """ Add a ?h=XXX parameter to URLs for static .js and .css files,
        where XXX is calculated from the file timestamp """
    if "static" == endpoint or endpoint.endswith(".static"):
        filename = values.get("filename")
        if filename and (filename.endswith(".js") or filename.endswith(".css")):
            if "." in endpoint:  # has higher priority
                blueprint = endpoint.rsplit(".", 1)[0]
            else:
                blueprint = request.blueprint  # can be None too

            if blueprint:
                static_folder = app.blueprints[blueprint].static_folder
            else:
                static_folder = app.static_folder

            param_name = "h"
            while param_name in values:
                param_name = "_" + param_name
            values[param_name] = static_file_hash(os.path.join(static_folder, filename))


def static_file_hash(filename):
    """ Obtain a timestamp for the given file """
    return int(os.stat(filename).st_mtime)


# Miscellaneous utility stuff

def max_age(seconds):
    """ Caching decorator for Flask - augments response with a max-age cache header """

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            resp = f(*args, **kwargs)
            if not isinstance(resp, Response):
                resp = make_response(resp)
            resp.cache_control.max_age = seconds
            return resp

        return decorated_function

    return decorator


def get_json_bool(rq, name, default=False):
    """ Get a boolean from JSON encoded in a request form """
    b = rq.form.get(name)
    if b is None:
        b = rq.args.get(name)
    if b is None:
        # Not present in the form: return the default
        return default
    return isinstance(b, str) and b == "true"


def better_jsonify(**kwargs):
    """ Ensure that the Content-Type header includes 'charset=utf-8' """
    resp = jsonify(**kwargs)
    resp.headers["Content-Type"] = "application/json; charset=utf-8"
    return resp


# Default text shown in the URL/text box
_DEFAULT_TEXTS = [
    "Hver gegnir starfi seðlabankastjóra?",
    "Hvað er HeForShe?",
    "Hver er Valgerður Bjarnadóttir?",
    "Hver er borgarstjóri?",
    "Hver er formaður Öryrkjabandalagsins?",
    "Hvað er Wintris?",
    "Hver er Vigdís Finnbogadóttir?",
    "Hver er Kristján Eldjárn?",
    "Hver er forstjóri Landsvirkjunar?",
    "Hver gegnir starfi forstjóra Orkuveitu Reykjavíkur?",
    "Hver er þjóðleikhússtjóri?",
    "Hver er fyrirliði íslenska landsliðsins?",
    "Hver er forsetaframbjóðandi?",
    "Hver er forseti Finnlands?",
    "Hver hefur verið aðstoðarmaður forsætisráðherra?",
    "Hver er forstjóri Google?",
    "Hvað er UNESCO?",
    "Hver er Íslandsmeistari í golfi?",
]

# Default number of top news items to show in front page list
_TOP_NEWS_LENGTH = 20

# Default number of top persons to show in front page list
_TOP_PERSONS_LENGTH = 20

# Maximum length of incoming GET/POST parameters
_MAX_URL_LENGTH = 512
_MAX_UUID_LENGTH = 36
_MAX_TEXT_LENGTH = 8192
_MAX_TEXT_LENGTH_VIA_URL = 512
_MAX_QUERY_LENGTH = 512


def top_news(topic=None, start=None, limit=_TOP_NEWS_LENGTH):
    """ Return a list of top recent news, of a particular topic,
        up to a particular start time, having a specified length """
    toplist = []
    topdict = dict()
    if start is None:
        start = datetime.utcnow()
    MARGIN = 10  # Get more articles than requested in case there are duplicates

    with SessionContext(commit=True) as session:

        q = (
            session.query(Article)
            .join(Root)
            .filter(Article.tree != None)
            .filter(Article.timestamp != None)
            .filter(Article.timestamp < start)
            .filter(Article.heading > "")
            .filter(Article.num_sentences > 0)
            .filter(Root.visible == True)
        )

        if topic is not None:
            # Filter by topic identifier
            q = q.join(ArticleTopic).join(Topic).filter(Topic.identifier == topic)

        q = q.order_by(desc(Article.timestamp))[0 : limit + MARGIN]

        class ArticleDisplay:

            """ Utility class to carry information about an article to the web template """

            def __init__(
                self, heading, timestamp, url, uuid, num_sentences, num_parsed, icon
            ):
                self.heading = heading
                self.timestamp = timestamp
                self.url = url
                self.uuid = uuid
                self.num_sentences = num_sentences
                self.num_parsed = num_parsed
                self.icon = icon

            @property
            def width(self):
                """ The ratio of parsed sentences to the total number of sentences,
                    expressed as a percentage string """
                if self.num_sentences == 0:
                    return "0%"
                return "{0}%".format((100 * self.num_parsed) // self.num_sentences)

            @property
            def time(self):
                return self.timestamp.isoformat()[11:16]

            @property
            def date(self):
                return self.timestamp.isoformat()[0:10]

        for a in q:
            # Collect and count the titles
            icon = a.root.domain + ".ico"

            d = ArticleDisplay(
                heading=a.heading,
                timestamp=a.timestamp,
                url=a.url,
                uuid=a.id,
                num_sentences=a.num_sentences,
                num_parsed=a.num_parsed,
                icon=icon,
            )

            # Have we seen the same heading on the same domain?
            t = (a.root.domain, a.heading)
            if t in topdict:
                # Same domain+heading already in the list
                i = topdict[t]
                if d.timestamp > toplist[i].timestamp:
                    # The new entry is newer: replace the old one
                    toplist[i] = d
                # Otherwise, ignore the new entry and continue
            else:
                # New heading: note its index in the list
                llist = len(toplist)
                topdict[t] = llist
                toplist.append(d)
                if llist + 1 >= limit:
                    break

    return toplist[0:limit]


def top_persons(limit=_TOP_PERSONS_LENGTH):
    """ Return a list of names and titles appearing recently in the news """
    toplist = dict()
    MAX_TITLE_LENGTH = 64

    with SessionContext(commit=True) as session:

        q = (
            session.query(Person.name, Person.title, Person.article_url, Article.id)
            .join(Article)
            .join(Root)
            .filter(Root.visible)
            .order_by(desc(Article.timestamp))[0 : limit * 2]  # Go through up to 2 * N records
        )

        def is_better_title(new_title, old_title):
            len_new = len(new_title)
            len_old = len(old_title)
            if len_old >= MAX_TITLE_LENGTH:
                # Too long: we want a shorter one
                return len_new < len_old
            if len_new >= MAX_TITLE_LENGTH:
                # This one is too long: we don't want it
                return False
            # Otherwise, longer is better
            return len_new > len_old

        with BIN_Db.get_db() as bindb:
            for p in q:
                # Insert the name into the list if it's not already there,
                # or if the new title is longer than the previous one
                if p.name not in toplist or is_better_title(
                    p.title, toplist[p.name][0]
                ):
                    toplist[p.name] = (
                        correct_spaces(p.title),
                        p.article_url,
                        p.id,
                        bindb.lookup_name_gender(p.name),
                    )
                    if len(toplist) >= limit:
                        # We now have as many names as we initially wanted: terminate the loop
                        break

    with changedlocale() as strxfrm:
        # Convert the dictionary to a sorted list of dicts
        return sorted(
            [
                dict(name=name, title=tu[0], gender=tu[3], url=tu[1], uuid=tu[2])
                for name, tu in toplist.items()
            ],
            key=lambda x: strxfrm(x["name"]),
        )


def process_query(session, toklist, result):
    """ Check whether the parse tree is describes a query, and if so, execute the query,
        store the query answer in the result dictionary and return True """
    q = Query(session)
    if not q.parse(toklist, result):
        if Settings.DEBUG:
            print("Unable to parse query, error {0}".format(q.error()))
        result["error"] = q.error()
        return False
    if not q.execute():
        # This is a query, but its execution failed for some reason: return the error
        if Settings.DEBUG:
            print("Unable to execute query, error {0}".format(q.error()))
        result["error"] = q.error()
        return True
    # Successful query: return the answer in response
    result["response"] = q.answer()
    # ...and the query type, as a string ('Person', 'Entity', 'Title' etc.)
    result["qtype"] = qt = q.qtype()
    result["key"] = q.key()
    if qt == "Person":
        # For a person query, add an image (if available)
        img = get_image_url(q.key(), enclosing_session=session)
        if img is not None:
            result["image"] = dict(
                src=img.src,
                width=img.width,
                height=img.height,
                link=img.link,
                origin=img.origin,
            )
    return True


def text_from_request(request):
    """ Return text passed in a HTTP request, either using GET or POST """
    if request.method == "POST":
        if request.headers["Content-Type"] == "text/plain":
            # This API accepts plain text POSTs, UTF-8 encoded.
            # Example usage:
            # curl -d @example.txt https://greynir.is/postag.api --header "Content-Type: text/plain"
            text = request.data.decode("utf-8")
        else:
            # This API also accepts form/url-encoded requests:
            # curl -d "text=Í dag er ágætt veður en mikil hálka er á götum." https://greynir.is/postag.api
            text = request.form.get("text", "")
    else:
        text = request.args.get("t", "")
    # Replace all consecutive whitespace with a single space
    return " ".join(text.split())[0:_MAX_TEXT_LENGTH]


# Note: Endpoints ending with .api are configured not to be cached by nginx
@app.route("/analyze.api", methods=["GET", "POST"])
@app.route("/analyze.api/v<int:version>", methods=["GET", "POST"])
def analyze_api(version=1):
    """ Analyze text manually entered by the user, i.e. not coming from an article.
        This is a lower level API used by the Greynir web front-end. """
    if not (1 <= version <= 1):
        return better_jsonify(valid=False, reason="Unsupported version")

    try:
        text = text_from_request(request)
    except:
        return better_jsonify(valid=False, reason="Invalid request")

    with SessionContext(commit=True) as session:
        pgs, stats, register = TreeUtility.tag_text(session, text)

    # Return the tokens as a JSON structure to the client
    return better_jsonify(valid=True, result=pgs, stats=stats, register=register)


# Note: Endpoints ending with .api are configured not to be cached by nginx
@app.route("/postag.api", methods=["GET", "POST"])
@app.route("/postag.api/v<int:version>", methods=["GET", "POST"])
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
            err = any("err" in t for t in sent)
            for t in sent:
                canonicalize_token(t)

    # Return the tokens as a JSON structure to the client
    return better_jsonify(valid=True, result=pgs, stats=stats, register=register)


# Note: Endpoints ending with .api are configured not to be cached by nginx
@app.route("/ifdtag.api", methods=["GET", "POST"])
@app.route("/ifdtag.api/v<int:version>", methods=["GET", "POST"])
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


# Note: Endpoints ending with .api are configured not to be cached by nginx
@app.route("/parse.api", methods=["GET", "POST"])
@app.route("/parse.api/v<int:version>", methods=["GET", "POST"])
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


@app.route("/article.api", methods=["GET", "POST"])
@app.route("/article.api/v<int:version>", methods=["GET", "POST"])
def article_api(version=1):
    """ Obtain information about an article, given its URL or id """

    if not (1 <= version <= 1):
        return better_jsonify(valid=False, reason="Unsupported version")

    if request.method == "GET":
        url = request.args.get("url")
        uuid = request.args.get("id")
    else:
        url = request.form.get("url")
        uuid = request.form.get("id")
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


# Note: Endpoints ending with .api are configured not to be cached by nginx
@app.route("/reparse.api", methods=["POST"])
@app.route("/reparse.api/v<int:version>", methods=["POST"])
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


# Frivolous fun stuff

_SPECIAL_QUERIES = {
    "er þetta spurning?": {"answer": "Er þetta svar?"},
    "er þetta svar?": {"answer": "Er þetta spurning?"},
    "hvað er svarið?": {"answer": "42."},
    "hvert er svarið?": {"answer": "42."},
    "veistu allt?": {"answer": "Nei."},
    "hvað veistu?": {"answer": "Spurðu mig!"},
    "veistu svarið?": {"answer": "Spurðu mig!"},
    "hvað heitir þú?": {"answer": "Greynir. Ég er grey sem reynir að greina íslensku."},
    "hver ert þú?": {"answer": "Ég er grey sem reynir að greina íslensku."},
    "hver bjó þig til?": {"answer": "Villi."},
    "hver skapaði þig?": {"answer": "Villi."},
    "hver er skapari þinn?": {"answer": "Villi."},
    "hver er flottastur?": {"answer": "Villi."},
    "er guð til?": {"answer": "Ég held ekki."},
    "hver skapaði guð?": {"answer": "Enginn sem ég þekki."},
    "hver skapaði heiminn?": {"answer": "Enginn sem ég þekki."},
    "hver er tilgangur lífsins?": {"answer": "42."},
    "hvar endar alheimurinn?": {"answer": "Inni í þér."},
}

# Note: Endpoints ending with .api are configured not to be cached by nginx
@app.route("/query.api", methods=["GET", "POST"])
@app.route("/query.api/v<int:version>", methods=["GET", "POST"])
def query_api(version=1):
    """ Respond to a query string """

    if not (1 <= version <= 1):
        return better_jsonify(valid=False, reason="Unsupported version")

    if request.method == "GET":
        q = request.args.get("q", "")
    else:
        q = request.form.get("q", "")
    q = q.strip()[0:_MAX_QUERY_LENGTH]

    # Auto-uppercasing can be turned off by sending autouppercase: false in the query JSON
    auto_uppercase = get_json_bool(request, "autouppercase", True)
    result = dict()
    ql = q.lower()

    if ql in _SPECIAL_QUERIES or (ql + "?") in _SPECIAL_QUERIES:
        result["valid"] = True
        result["qtype"] = "Special"
        result["q"] = q
        if ql in _SPECIAL_QUERIES:
            result["response"] = _SPECIAL_QUERIES[ql]
        else:
            result["response"] = _SPECIAL_QUERIES[ql + "?"]
    else:
        with SessionContext(commit=True) as session:

            toklist = list(
                tokenize_and_recognize(
                    q,
                    enclosing_session=session,
                    auto_uppercase=q.islower() if auto_uppercase else False,
                )
            )
            actual_q = correct_spaces(" ".join(t.txt or "" for t in toklist))

            if Settings.DEBUG:
                # Log the query string as seen by the parser
                print("Query is: '{0}'".format(actual_q))

            # Try to parse and process as a query
            is_query = process_query(session, toklist, result)

        result["valid"] = is_query
        result["q"] = actual_q

    return better_jsonify(**result)


@app.route("/treegrid", methods=["GET"])
def tree_grid():
    """ Show a simplified parse tree for a single sentence """

    txt = request.args.get("txt", "")
    with SessionContext(commit=True) as session:
        # Obtain simplified tree, full tree and stats
        tree, full_tree, stats = TreeUtility.parse_text_with_full_tree(session, txt)
        if full_tree is not None:
            # Create a more manageable, flatter tree from the binarized raw parse tree
            full_tree = ParseForestFlattener.flatten(full_tree)

    # Preprocess the trees for display, projecting them to a 2d table structure

    def _wrap_build_tbl(
        tbl, root, is_nt_func, children_func, nt_info_func, t_info_func
    ):
        def _build_tbl(level, offset, nodelist):
            """ Add the tree node data to be displayed at a particular
                level (row) in the result table """
            while len(tbl) <= level:
                tbl.append([])
            tlevel = tbl[level]
            left = sum(t[0] for t in tlevel)
            while left < offset:
                # Insert a left margin if required
                # (necessary if we'we alread inserted a terminal at a
                # level above this one)
                tlevel.append((1, None))
                left += 1
            index = offset
            if nodelist is not None:
                for n in nodelist:
                    if is_nt_func(n):
                        # Nonterminal: display the child nodes in deeper levels
                        # and add a header on top of them, spanning their total width
                        cnt = _build_tbl(level + 1, index, children_func(n))
                        tlevel.append((cnt, nt_info_func(n)))
                        index += cnt
                    else:
                        # Terminal: display it in a single column
                        tlevel.append((1, t_info_func(n)))
                        index += 1
            return index - offset

        return _build_tbl(0, 0, [root])

    def _normalize_tbl(tbl, width):
        """ Fill out the table with blanks so that it is square """
        for row in tbl:
            rw = sum(t[0] for t in row)
            # Right-pad as required
            while rw < width:
                row.append((1, None))
                rw += 1

    tbl = []
    full_tbl = []
    if tree is None:
        full_tree = None
        width = 0
        full_width = 0
        height = 0  # Height of simplified table
        full_height = 0  # Height of full table
    else:

        # Build a table structure for a simplified tree
        width = _wrap_build_tbl(
            tbl,
            tree,
            is_nt_func=lambda n: n["k"] == "NONTERMINAL",
            children_func=lambda n: n["p"],
            nt_info_func=lambda n: dict(n=n["n"]),
            t_info_func=lambda n: n,
        )
        height = len(tbl)
        if width and height:
            _normalize_tbl(tbl, width)

        # Build a table structure for a full tree
        full_width = _wrap_build_tbl(
            full_tbl,
            full_tree,
            is_nt_func=lambda n: n.is_nonterminal,
            children_func=lambda n: n.children,
            nt_info_func=lambda n: dict(n=n.p.name),
            t_info_func=lambda n: dict(t=n.p[0].name, x=n.p[1].t1),
        )
        assert full_width == width
        full_height = len(full_tbl)
        if full_width and full_height:
            _normalize_tbl(full_tbl, full_width)

    return render_template(
        "treegrid.html",
        txt=txt,
        tree=tree,
        stats=stats,
        tbl=tbl,
        height=height,
        full_tbl=full_tbl,
        full_height=full_height,
    )


@app.route("/genders", methods=["GET"])
@max_age(seconds=5 * 60)
def genders():
    """ Render a page with gender statistics """

    with SessionContext(commit=True) as session:

        gq = GenderQuery()
        result = gq.execute(session)

        total = dict(kvk=Decimal(), kk=Decimal(), hk=Decimal(), total=Decimal())
        for r in result:
            total["kvk"] += r.kvk
            total["kk"] += r.kk
            total["hk"] += r.hk
            total["total"] += r.kvk + r.kk + r.hk

        return render_template("genders.html", result=result, total=total)


@app.route("/stats", methods=["GET"])
@max_age(seconds=5 * 60)
def stats():
    """ Render a page with article statistics """

    with SessionContext(commit=True) as session:

        sq = StatsQuery()
        result = sq.execute(session)

        total = dict(art=Decimal(), sent=Decimal(), parsed=Decimal())
        for r in result:
            total["art"] += r.art
            total["sent"] += r.sent
            total["parsed"] += r.parsed

        return render_template("stats.html", result=result, total=total)


@app.route("/about")
@max_age(seconds=10 * 60)
def about():
    """ Handler for an 'About' page """
    return render_template("about.html")


@app.route("/apidoc")
@max_age(seconds=10 * 60)
def apidoc():
    """ Handler for an API documentation page """
    return render_template("apidoc.html")


@app.route("/news")
@max_age(seconds=60)
def news():
    """ Handler for a page with a top news list """
    topic = request.args.get("topic")
    start = request.args.get("start")
    if start is not None:
        try:
            if "." in start:
                # Assume full timestamp with microseconds
                start = datetime.strptime(start, "%Y-%m-%dT%H:%M:%S.%f")
            else:
                # Compact timestamp
                start = datetime.strptime(start, "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            start = None
    articles = top_news(topic=topic, start=start)
    now = datetime.utcnow()
    # If all articles in the list are timestamped within 24 hours of now,
    # we display their times in HH:MM format. Otherwise, we display their
    # dates in YYYY-MM-DD format.
    display_time = True
    if articles and (now - articles[-1].timestamp).days >= 1:
        display_time = False
    # Fetch the topics
    with SessionContext(commit=True) as session:
        q = session.query(Topic.identifier, Topic.name).order_by(Topic.name).all()
        d = {t[0]: t[1] for t in q}
        topics = dict(id=topic, name=d.get(topic, ""), topic_list=q)
    return render_template(
        "news.html", articles=articles, topics=topics, display_time=display_time
    )


@app.route("/people")
@max_age(seconds=60)
def people():
    """ Handler for a page with a list of people recently appearing in news """
    return render_template("people.html", persons=top_persons())


@app.route("/analysis")
def analysis():
    """ Handler for a page with grammatical analysis of user-entered text """
    txt = request.args.get("txt", "")[0:_MAX_TEXT_LENGTH_VIA_URL]
    return render_template("analysis.html", default_text=txt)


@app.route("/page")
def page():
    """ Handler for a page displaying the parse of an arbitrary web page by URL
        or an already scraped article by UUID """
    url = request.args.get("url", None)
    uuid = request.args.get("id", None)
    if url:
        url = url.strip()[0:_MAX_URL_LENGTH]
    if uuid:
        uuid = uuid.strip()[0:_MAX_UUID_LENGTH]
    if url:
        # URL has priority, if both are specified
        uuid = None
    if not url and not uuid:
        # !!! TODO: Separate error page
        return redirect(url_for("main"))

    with SessionContext(commit=True) as session:

        if uuid:
            a = ArticleProxy.load_from_uuid(uuid, session)
        elif url.startswith("http:") or url.startswith("https:"):
            # a = ArticleProxy.load_from_url(url, session)
            a = ArticleProxy.scrape_from_url(url, session)  # Forces a new scrape
        else:
            a = None

        if a is None:
            # !!! TODO: Separate error page
            return redirect(url_for("main"))

        # Prepare the article for display (may cause it to be parsed and stored)
        a.prepare(session, verbose=True, reload_parser=True)
        register = a.create_register(session)

        # Fetch names of article topics, if any
        topics = (
            session.query(ArticleTopic).filter(ArticleTopic.article_id == a.uuid).all()
        )
        topics = [dict(name=t.topic.name, id=t.topic.identifier) for t in topics]

        # Fetch similar (related) articles, if any
        DISPLAY = 10  # Display at most 10 matches
        similar = Search.list_similar_to_article(session, a.uuid, n=DISPLAY)

        return render_template(
            "page.html", article=a, register=register, topics=topics, similar=similar
        )


@app.route("/")
@max_age(seconds=60)
def main():
    """ Handler for the main (index) page """
    txt = request.args.get("txt", None)
    if txt:
        txt = txt.strip()
    if not txt:
        # Select a random default text
        txt = _DEFAULT_TEXTS[random.randint(0, len(_DEFAULT_TEXTS) - 1)]
    return render_template("main.html", default_text=txt)


# Flask handlers


@app.route("/fonts/<path:path>")
@max_age(seconds=24 * 60 * 60)  # Cache font for 24 hours
def send_font(path):
    return send_from_directory("fonts", path)


# noinspection PyUnusedLocal
@app.errorhandler(404)
def page_not_found(e):
    """ Return a custom 404 error """
    return "Þessi vefslóð er ekki rétt", 404


@app.errorhandler(500)
def server_error(e):
    """ Return a custom 500 error """
    return "Eftirfarandi villa kom upp: {0}".format(e), 500


# Initialize the main module

t0 = time.time()
try:
    # Read configuration file
    Settings.read("config/Reynir.conf")
except ConfigError as e:
    logging.error("Reynir did not start due to configuration error:\n{0}".format(e))
    sys.exit(1)

if Settings.DEBUG:
    print("Settings loaded in {0:.2f} seconds".format(time.time() - t0))
    print(
        "Running Reynir with debug={0}, host={1}:{2}, db_hostname={3} on Python {4}"
        .format(
            Settings.DEBUG,
            Settings.HOST,
            Settings.PORT,
            Settings.DB_HOSTNAME,
            sys.version,
        )
    )

if __name__ == "__main__":

    # Run a default Flask web server for testing if invoked directly as a main program

    # Additional files that should cause a reload of the web server application
    # Note: Reynir.grammar is automatically reloaded if its timestamp changes
    extra_files = [
        "Reynir.conf",
        "Verbs.conf",
        "VerbPrepositions.conf",
        "Main.conf",
        "Prefs.conf",
        "Phrases.conf",
        "Vocab.conf",
        "Names.conf",
    ]

    for i, fname in enumerate(extra_files):
        # First check our own module's config subdirectory
        path = os.path.join(os.path.dirname(__file__), "config", fname)
        path = os.path.realpath(path)
        if os.path.isfile(path):
            extra_files[i] = path
        else:
            # This config file is not in the Reynir/config subdirectory:
            # Attempt to watch it in ReynirPackage
            path = os.path.join(os.path.dirname(reynir.__file__), "config", fname)
            path = os.path.realpath(path)
            if os.path.isfile(path):
                extra_files[i] = path
            else:
                print("Extra file path '{0}' not found".format(path))

    from socket import error as socket_error
    import errno

    try:

        # Suppress information log messages from Werkzeug
        werkzeug_log = logging.getLogger("werkzeug")
        if werkzeug_log:
            werkzeug_log.setLevel(logging.WARNING)
        # Run the Flask web server application
        app.run(
            host=Settings.HOST,
            port=Settings.PORT,
            debug=Settings.DEBUG,
            use_reloader=True,
            extra_files=extra_files,
        )

    except socket_error as e:
        if e.errno == errno.EADDRINUSE:  # Address already in use
            logging.error(
                "Reynir is already running at host {0}:{1}"
                .format(Settings.HOST, Settings.PORT)
            )
            sys.exit(1)
        else:
            raise

    finally:
        ArticleProxy.cleanup()
        BIN_Db.cleanup()

else:

    # Suppress information log messages from Werkzeug
    werkzeug_log = logging.getLogger("werkzeug")
    if werkzeug_log:
        werkzeug_log.setLevel(logging.WARNING)
    # Log our startup
    log_str = (
        "Reynir instance starting with host={0}:{1}, db_hostname={2} on Python {3}"
        .format(
            Settings.HOST,
            Settings.PORT,
            Settings.DB_HOSTNAME,
            sys.version.replace("\n", " "),
        )
    )
    logging.info(log_str)
    print(log_str)
    sys.stdout.flush()

    # Running as a server module: pre-load the grammar into memory
    with Fast_Parser() as fp:
        pass
