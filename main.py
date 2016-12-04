#!/usr/bin/env python
"""

    Reynir: Natural language processing for Icelandic

    Web server main module

    Copyright (C) 2016 Vilhjálmur Þorsteinsson

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


    This module is written in Python 3.2 for compatibility with PyPy3

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
from datetime import datetime
from functools import wraps
from decimal import Decimal

from flask import Flask
from flask import render_template, make_response, jsonify, redirect, url_for
from flask import request, send_from_directory
from flask.wrappers import Response

from settings import Settings, ConfigError, changedlocale
from bindb import BIN_Db
from fetcher import Fetcher
from tokenizer import tokenize, TOK, correct_spaces
from fastparser import Fast_Parser, ParseError, ParseForestPrinter
from incparser import IncrementalParser
from reducer import Reducer
from article import Article as ArticleProxy
from scraperdb import SessionContext, desc, Root, Person, Article, ArticleTopic, Topic,\
    GenderQuery, StatsQuery
from query import Query
from getimage import get_image_url
import scraperinit

# Initialize Flask framework

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False # We're fine with using Unicode/UTF-8

from flask import current_app

def debug():
    # Call this to trigger the Flask debugger on purpose
    assert current_app.debug == False, "Don't panic! You're here by request of debug()"


# Utilities for Flask/Jinja2 formatting of numbers using the Icelandic locale

def make_pattern(rep_dict):
    return re.compile("|".join([re.escape(k) for k in rep_dict.keys()]), re.M)

def multiple_replace(string, rep_dict, pattern = None):
    """ Perform multiple simultaneous replacements within string """
    if pattern is None:
        pattern = make_pattern(rep_dict)
    return pattern.sub(lambda x: rep_dict[x.group(0)], string)

_REP_DICT_IS = { ',' : '.', '.' : ',' }
_PATTERN_IS = make_pattern(_REP_DICT_IS)

@app.template_filter('format_is')
def format_is(r, decimals = 0):
    """ Flask/Jinja2 template filter to format a number for the Icelandic locale """
    fmt = "{0:,." + str(decimals) + "f}"
    return multiple_replace(fmt.format(float(r)), _REP_DICT_IS, _PATTERN_IS)

@app.template_filter('format_ts')
def format_ts(ts):
    """ Flask/Jinja2 template filter to format a timestamp """
    return str(ts)[0:19]


# Flask cache busting for static .css and .js files

@app.url_defaults
def hashed_url_for_static_file(endpoint, values):
    """ Add a ?h=XXX parameter to URLs for static .js and .css files,
        where XXX is calculated from the file timestamp """
    if 'static' == endpoint or endpoint.endswith('.static'):
        filename = values.get('filename')
        if filename and (filename.endswith(".js") or filename.endswith(".css")):
            if '.' in endpoint:  # has higher priority
                blueprint = endpoint.rsplit('.', 1)[0]
            else:
                blueprint = request.blueprint  # can be None too

            if blueprint:
                static_folder = app.blueprints[blueprint].static_folder
            else:
                static_folder = app.static_folder

            param_name = 'h'
            while param_name in values:
                param_name = '_' + param_name
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

def get_json_bool(rq, name, default = False):
    """ Get a boolean from JSON encoded in a request form """
    b = rq.form.get(name)
    if b is None:
        # Not present in the form: return the default
        return default
    return isinstance(b, str) and b == "true"


# Default text shown in the URL/text box
_DEFAULT_TEXTS = [
    'Hver gegnir starfi seðlabankastjóra?',
    'Hvað er HeForShe?',
    'Hver er Valgerður Bjarnadóttir?',
    'Hver er borgarstjóri?',
    'Hver er formaður Öryrkjabandalagsins?',
    'Hvað er Wintris?',
    'Hver er Vigdís Finnbogadóttir?',
    'Hver er Kristján Eldjárn?',
    'Hvað tengist Bjarna Benediktssyni?',
    'Hvaða orð tengjast orðinu nauðgun?',
    'Hver er forstjóri Landsvirkjunar?',
    'Hver gegnir starfi forstjóra Orkuveitu Reykjavíkur?',
    'Hver er þjóðleikhússtjóri?',
    'Hver er fyrirliði íslenska landsliðsins?',
    'Hver er forsetaframbjóðandi?',
    'Hvað tengist sögninni að verðtryggja?',
    'Hver er forstjóri Google?'
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


def top_news(topic = None, start = None, limit = _TOP_NEWS_LENGTH):
    """ Return a list of top recent news, of a particular topic,
        up to a particular start time, having a specified length """
    toplist = []
    topdict = dict()
    if start is None:
        start = datetime.utcnow()
    MARGIN = 10 # Get more articles than requested in case there are duplicates

    with SessionContext(commit = True) as session:

        q = session.query(Article).join(Root) \
            .filter(Article.tree != None) \
            .filter(Article.timestamp != None) \
            .filter(Article.timestamp < start) \
            .filter(Article.heading > "") \
            .filter(Root.visible == True)

        if topic is not None:
            # Filter by topic identifier
            q = q.join(ArticleTopic).join(Topic).filter(Topic.identifier == topic)

        q = q.order_by(desc(Article.timestamp))[0:limit + MARGIN]

        class ArticleDisplay:

            """ Utility class to carry information about an article to the web template """

            def __init__(self, heading, timestamp, url, uuid, num_sentences, num_parsed, icon):
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

            d = ArticleDisplay(heading = a.heading, timestamp = a.timestamp, url = a.url, uuid = a.id,
                num_sentences = a.num_sentences, num_parsed = a.num_parsed, icon = icon)

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


def top_persons(limit = _TOP_PERSONS_LENGTH):
    """ Return a list of names and titles appearing recently in the news """
    toplist = dict()
    bindb = BIN_Db.get_db()

    with SessionContext(commit = True) as session:

        q = session.query(Person.name, Person.title, Person.article_url, Article.id) \
            .join(Article).join(Root) \
            .filter(Root.visible) \
            .order_by(desc(Article.timestamp))[0:limit * 2] # Go through up to 2 * N records

        for p in q:
            # Insert the name into the list if it's not already there,
            # or if the new title is longer than the previous one
            if p.name not in toplist or len(p.title) > len(toplist[p.name][0]):
                toplist[p.name] = (correct_spaces(p.title), p.article_url, p.id, bindb.lookup_name_gender(p.name))
                if len(toplist) >= limit:
                    # We now have as many names as we initially wanted: terminate the loop
                    break

    with changedlocale() as strxfrm:
        # Convert the dictionary to a sorted list of dicts
        return sorted(
            [ dict(name = name, title = tu[0], gender = tu[3], url = tu[1], uuid = tu[2]) for name, tu in toplist.items() ],
            key = lambda x: strxfrm(x["name"])
        )


def process_query(session, toklist, result):
    """ Check whether the parse tree is describes a query, and if so, execute the query,
        store the query answer in the result dictionary and return True """
    q = Query(session)
    if not q.parse(toklist, result):
        # Not able to parse this as a query
        return False
    if not q.execute():
        # This is a query, but its execution failed for some reason: return the error
        result["error"] = q.error()
        return True
    # Successful query: return the answer in response
    result["response"] = q.answer()
    # ...and the query type, as a string ('Person', 'Entity', 'Title' etc.)
    result["qtype"] = qt = q.qtype()
    result["key"] = q.key()
    if qt == "Person":
        # For a person query, add an image (if available)
        img = get_image_url(q.key(), enclosing_session = session)
        if img is not None:
            result["image"] = dict(src = img.src,
                width = img.width, height = img.height,
                link = img.link, origin = img.origin)
    return True


# Note: Endpoints ending with .api are configured not to be cached by nginx
@app.route("/analyze.api", methods=['GET', 'POST'])
def analyze():
    """ Analyze text manually entered by the user, i.e. not coming from an article.
        This is a lower level API used by the Greynir web front-end. """

    if request.method == 'POST':
        text = request.form.get("text")
    else:
        text = request.args.get("t")
    text = text.strip()[0:_MAX_TEXT_LENGTH]

    with SessionContext(commit = True) as session:
        pgs, stats, register = ArticleProxy.tag_text(session, text)

    # Return the tokens as a JSON structure to the client
    return jsonify(result = pgs, stats = stats, register = register)


# Note: Endpoints ending with .api are configured not to be cached by nginx
@app.route("/postag.api", methods=['GET', 'POST'])
def postag():
    """ API to parse text and return POS tagged tokens in JSON format """

    try:
        if request.method == 'POST':
            if request.headers["Content-Type"] == "text/plain":
                # This API accepts plain text POSTs, UTF-8 encoded.
                # Example usage:
                # curl -d @example.txt https://greynir.is/parse.api --header "Content-Type: text/plain"
                text = request.data.decode("utf-8")
            else:
                # This API also accepts form/url-encoded requests:
                # curl -d "text=Í dag er ágætt veður en mikil hálka er á götum." https://greynir.is/parse.api
                text = request.form.get("text", "")
        else:
            text = request.args.get("t", "")
        text = text.strip()[0:_MAX_TEXT_LENGTH]
    except:
        return "", 403 # Invalid request

    with SessionContext(commit = True) as session:
        pgs, stats, register = ArticleProxy.tag_text(session, text)
        # In this case, we should always get a single paragraph back
        if pgs:
            # Only process the first paragraph, if there are many of them
            if len(pgs) == 1:
                pgs = pgs[0]
            else:
                # More than one paragraph: concatenate 'em all
                pa = []
                for pg in pgs:
                    pa.extend(pg)
                pgs = pa
        for sent in pgs:
            # Transform the token representation into a
            # nice canonical form for outside consumption
            for t in sent:
                # Set the token kind to a readable string
                kind = t.get("k", TOK.WORD)
                t["k"] = TOK.descr[kind]
                if "t" in t:
                    terminal = t["t"]
                    # Change "literal:category" to category,
                    # or 'stem'_var1_var2 to category_var1_var2
                    if terminal[0] in "\"'" and "m" in t:
                        # Convert 'literal'_var1_var2 to cat_var1_var2
                        a = terminal.split("_")
                        a[0] = t["m"][1] # Token category
                        if a[0] in { "kk", "kvk", "hk" }:
                            a[0] = "no"
                        t["t"] = "_".join(a)
                if "m" in t:
                    # Flatten the meaning from a tuple/list
                    m = t["m"]
                    del t["m"]
                    # s = stofn (stem)
                    # c = ordfl (category)
                    # f = fl (class)
                    # b = beyging (declination)
                    t.update(dict(s = m[0], c = m[1], f = m[2], b = m[3]))
                if "v" in t:
                    # Flatten and simplify the val field, if present
                    # (see tokenizer.py for the corresponding TOK structures)
                    val = t["v"]
                    if kind == TOK.AMOUNT:
                        # Flatten and simplify amounts
                        t["v"] = dict(amount = val[0], currency = val[1])
                    elif kind in { TOK.NUMBER, TOK.CURRENCY, TOK.PERCENT }:
                        # Number, ISO currency code, percentage
                        t["v"] = val[0]
                    elif kind == TOK.DATE:
                        t["v"] = dict(y = val[0], mo = val[1], d = val[2])
                    elif kind == TOK.TIME:
                        t["v"] = dict(h = val[0], m = val[1], s = val[2])
                    elif kind == TOK.TIMESTAMP:
                        t["v"] = dict(y = val[0], mo = val[1], d = val[2],
                            h = val[3], m = val[4], s = val[5])

    # Return the tokens as a JSON structure to the client
    resp = jsonify(result = pgs, stats = stats, register = register)
    resp.headers["Content-Type"] = "application/json; charset=utf-8"
    return resp


# Note: Endpoints ending with .api are configured not to be cached by nginx
@app.route("/reparse.api", methods=['POST'])
def reparse():
    """ Reparse an already parsed and stored article with a given UUID """

    uuid = request.form.get("id", "").strip()[0:_MAX_UUID_LENGTH]
    tokens = None
    register = { }
    stats = { }

    with SessionContext(commit = True) as session:
        # Load the article
        a = ArticleProxy.load_from_uuid(uuid, session)
        if a is not None:
            # Found: Parse it (with a fresh parser) and store the updated version
            a.parse(session, verbose = True, reload_parser = True)
            # Save the tokens
            tokens = a.tokens
            # Build register of person names
            register = a.create_register(session)
            stats = dict(
                num_tokens = a.num_tokens,
                num_sentences = a.num_sentences,
                num_parsed = a.num_parsed,
                ambiguity = a.ambiguity)

    # Return the tokens as a JSON structure to the client,
    # along with a name register and article statistics
    return jsonify(result = tokens, register = register, stats = stats)


# Note: Endpoints ending with .api are configured not to be cached by nginx
@app.route("/query.api", methods=['POST'])
def query():
    """ Respond to a query string """

    q = request.form.get("q", "").strip()[0:_MAX_QUERY_LENGTH]
    # Auto-uppercasing can be turned off by sending autouppercase: false in the query JSON
    auto_uppercase = get_json_bool(request, "autouppercase", True)
    result = dict()

    with SessionContext(commit = True) as session:

        toklist = list(tokenize(q, enclosing_session = session,
            auto_uppercase = q.islower() if auto_uppercase else False))
        actual_q = correct_spaces(" ".join(t.txt or "" for t in toklist))

        if Settings.DEBUG:
            # Log the query string as seen by the parser
            print("Query is: '{0}'".format(actual_q))

        # Try to parse and process as a query
        is_query = process_query(session, toklist, result)


    result["is_query"] = is_query
    result["q"] = actual_q

    return jsonify(result = result)


def make_grid(w):
    """ Make a 2d grid from a flattened parse schema """

    def make_schema(w):
        """ Create a flattened parse schema from the forest w """

        def _part(w, level, suffix):
            """ Return a tuple (colheading + options, start_token, end_token, partlist, info)
                where the partlist is again a list of the component schemas - or a terminal
                matching a single token - or None if empty """
            if w is None:
                # Epsilon node: return empty list
                return None
            if w.is_token:
                return ([ level ] + suffix, w.start, w.end, None, (w.terminal, w.token.text))
            # Interior nodes are not returned
            # and do not increment the indentation level
            if not w.is_interior:
                level += 1
            # Accumulate the resulting parts
            plist = [ ]
            ambig = w.is_ambiguous
            add_suffix = [ ]

            for ix, pc in enumerate(w.enum_children()):
                prod, f = pc
                if ambig:
                    # Uniquely identify the available parse options with a coordinate
                    add_suffix = [ ix ]

                def add_part(p):
                    """ Add a subtuple p to the part list plist """
                    if p:
                        if p[0] is None:
                            # p describes an interior node
                            plist.extend(p[3])
                        elif p[2] > p[1]:
                            # Only include subtrees that actually contain terminals
                            plist.append(p)

                if isinstance(f, tuple):
                    add_part(_part(f[0], level, suffix + add_suffix))
                    add_part(_part(f[1], level, suffix + add_suffix))
                else:
                    add_part(_part(f, level, suffix + add_suffix))

            if w.is_interior:
                # Interior node: relay plist up the tree
                return (None, 0, 0, plist, None)
            # Completed nonterminal
            assert w.is_completed
            assert w.nonterminal is not None
            return ([level - 1] + suffix, w.start, w.end, plist, w.nonterminal)

        # Start of make_schema

        if w is None:
            return None
        return _part(w, 0, [ ])

    # Start of make_grid

    if w is None:
        return None
    schema = make_schema(w)
    assert schema[1] == 0
    cols = [] # The columns to be populated
    NULL_TUPLE = tuple()

    def _traverse(p):
        """ Traverse a schema subtree and insert the nodes into their
            respective grid columns """
        # p[0] is the coordinate of this subtree (level + suffix)
        # p[1] is the start column of this subtree
        # p[2] is the end column of this subtree
        # p[3] is the subpart list
        # p[4] is the nonterminal or terminal/token at the head of this subtree
        col, option = p[0][0], p[0][1:] # Level of this subtree and option

        if not option:
            # No option: use a 'clean key' of NULL_TUPLE
            option = NULL_TUPLE
        else:
            # Convert list to a frozen (hashable) tuple
            option = tuple(option)

        while len(cols) <= col:
            # Add empty columns as required to reach this level
            cols.append(dict())

        # Add a tuple describing the rows spanned and the node info
        if option not in cols[col]:
            # Put in a dictionary entry for this option
            cols[col][option] = []
        cols[col][option].append((p[1], p[2], p[4]))

        # Navigate into subparts, if any
        if p[3]:
            for subpart in p[3]:
                _traverse(subpart)

    _traverse(schema)
    # Return a tuple with the grid and the number of tokens
    return (cols, schema[2])


@app.route("/parsegrid", methods=['POST'])
def parse_grid():
    """ Show the parse grid for a particular parse tree of a sentence """

    MAX_LEVEL = 32 # Maximum level of option depth we can handle
    txt = request.form.get('txt', "")
    parse_path = request.form.get('option', "")
    debug_mode = get_json_bool(request, 'debug')
    use_reducer = not ("noreduce" in request.form)

    # Tokenize the text
    tokens = list(tokenize(txt))

    # Parse the text
    with Fast_Parser(verbose = False) as bp: # Don't emit diagnostic messages
        err = dict()
        grammar = bp.grammar
        try:
            forest = bp.go(tokens)
        except ParseError as e:
            err["msg"] = str(e)
            # Relay information about the parser state at the time of the error
            err["info"] = None # e.info
            forest = None

    # Find the number of parse combinations
    combinations = 0 if forest is None else Fast_Parser.num_combinations(forest)
    score = 0

    if Settings.DEBUG:
        # Dump the parse tree to parse.txt
        with open("parse.txt", mode = "w", encoding= "utf-8") as f:
            if forest is not None:
                print("Reynir parse forest for sentence '{0}'".format(txt), file = f)
                print("{0} combinations\n".format(combinations), file = f)
                if combinations < 10000:
                    ParseForestPrinter.print_forest(forest, file = f)
                else:
                    print("Too many combinations to dump", file = f)
            else:
                print("No parse available for sentence '{0}'".format(txt), file = f)

    if forest is not None and use_reducer:
        # Reduce the parse forest
        forest, score = Reducer(grammar).go_with_score(forest)
        if Settings.DEBUG:
            # Dump the reduced tree along with node scores
            with open("reduce.txt", mode = "w", encoding= "utf-8") as f:
                print("Reynir parse tree for sentence '{0}' after reduction".format(txt), file = f)
                ParseForestPrinter.print_forest(forest, file = f)

    # Make the parse grid with all options
    grid, ncols = make_grid(forest) if forest else ([], 0)
    # The grid is columnar; convert it to row-major
    # form for convenient translation into HTML
    # There will be as many columns as there are tokens
    nrows = len(grid)
    tbl = [ [] for _ in range(nrows) ]
    # Info about previous row spans
    rs = [ [] for _ in range(nrows) ]

    # The particular option path we are displaying
    if not parse_path:
        # Not specified: display the all-zero path
        path = [(0,) * i for i in range(1, MAX_LEVEL)]
    else:
        # Disassemble the passed-in path

        def toint(s):
            """ Safe conversion of string to int """
            try:
                n = int(s)
            except ValueError:
                n = 0
            return n if n >= 0 else 0

        p = [ toint(s) for s in parse_path.split("_") ]
        path = [tuple(p[0 : i + 1]) for i in range(len(p))]

    # This set will contain all option path choices
    choices = set()
    NULL_TUPLE = tuple()

    for gix, gcol in enumerate(grid):
        # gcol is a dictionary of options
        # Accumulate the options that we want do display
        # according to chosen path
        cols = gcol[NULL_TUPLE] if NULL_TUPLE in gcol else [] # Default content
        # Add the options we're displaying
        for p in path:
            if p in gcol:
                cols.extend(gcol[p])
        # Accumulate all possible path choices
        choices |= gcol.keys()
        # Sort the columns that will be displayed
        cols.sort(key = lambda x: x[0])
        col = 0
        for startcol, endcol, info in cols:
            #assert isinstance(info, Nonterminal) or isinstance(info, tuple)
            if col < startcol:
                gap = startcol - col
                gap -= sum(1 for c in rs[gix] if c < startcol)
                if gap > 0:
                    tbl[gix].append((gap, 1, "", ""))
            rowspan = 1
            if isinstance(info, tuple):
                cls = { "terminal" }
                rowspan = nrows - gix
                for i in range(gix + 1, nrows):
                    # Note the rowspan's effect on subsequent rows
                    rs[i].append(startcol)
            else:
                cls = { "nonterminal" }
                # Get the 'pure' name of the nonterminal in question
                #assert isinstance(info, Nonterminal)
                info = info.name
            if endcol - startcol == 1:
                cls |= { "vertical" }
            tbl[gix].append((endcol-startcol, rowspan, info, cls))
            col = endcol
        ncols_adj = ncols - len(rs[gix])
        if col < ncols_adj:
            tbl[gix].append((ncols_adj - col, 1, "", ""))
    # Calculate the unique path choices available for this parse grid
    choices -= { NULL_TUPLE } # Default choice: don't need it in the set
    unique_choices = choices.copy()
    for c in choices:
        # Remove all shorter prefixes of c from the unique_choices set
        unique_choices -= { c[0:i] for i in range(1, len(c)) }
    # Create a nice string representation of the unique path choices
    uc_list = [ "_".join(str(c) for c in choice) for choice in unique_choices ]
    if not parse_path:
        # We are displaying the longest possible all-zero choice: find it
        i = 0
        while (0,) * (i + 1) in unique_choices:
            i += 1
        parse_path = "_".join(["0"] * i)

    return render_template("parsegrid.html", txt = txt, err = err, tbl = tbl,
        combinations = combinations, score = score, debug_mode = debug_mode,
        choice_list = uc_list, parse_path = parse_path)


@app.route("/genders", methods=['GET'])
@max_age(seconds = 5 * 60)
def genders():
    """ Render a page with gender statistics """

    with SessionContext(commit = True) as session:

        gq = GenderQuery()
        result = gq.execute(session)

        total = dict(kvk = Decimal(), kk = Decimal(), hk = Decimal(), total = Decimal())
        for r in result:
            total["kvk"] += r.kvk
            total["kk"] += r.kk
            total["hk"] += r.hk
            total["total"] += r.kvk + r.kk + r.hk

        return render_template("genders.html", result = result, total = total)


@app.route("/stats", methods=['GET'])
@max_age(seconds = 5 * 60)
def stats():
    """ Render a page with article statistics """

    with SessionContext(commit = True) as session:

        sq = StatsQuery()
        result = sq.execute(session)

        total = dict(art = Decimal(), sent = Decimal(), parsed = Decimal())
        for r in result:
            total["art"] += r.art
            total["sent"] += r.sent
            total["parsed"] += r.parsed

        return render_template("stats.html", result = result, total = total)


@app.route("/about")
@max_age(seconds = 10 * 60)
def about():
    """ Handler for an 'About' page """
    return render_template("about.html")


@app.route("/apidoc")
@max_age(seconds = 10 * 60)
def apidoc():
    """ Handler for an API documentation page """
    return render_template("apidoc.html")


@app.route("/news")
@max_age(seconds = 60)
def news():
    """ Handler for a page with a top news list """
    topic = request.args.get("topic")
    start = request.args.get("start")
    if start is not None:
        try:
            if '.' in start:
                # Assume full timestamp with microseconds
                start = datetime.strptime(start, "%Y-%m-%dT%H:%M:%S.%f")
            else:
                # Compact timestamp
                start = datetime.strptime(start, "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            start = None
    articles = top_news(topic = topic, start = start)
    now = datetime.utcnow()
    # If all articles in the list are timestamped within 24 hours of now,
    # we display their times in HH:MM format. Otherwise, we display their
    # dates in YYYY-MM-DD format.
    display_time = True
    if articles and (now - articles[-1].timestamp).days >= 1:
        display_time = False
    # Fetch the topics
    with SessionContext(commit = True) as session:
        q = session.query(Topic.identifier, Topic.name).order_by(Topic.name).all()
        d = { t[0] : t[1] for t in q }
        topics = dict(identifier = topic, name = d.get(topic, ""), topic_list = q)
    return render_template("news.html", articles = articles, topics = topics, display_time = display_time)


@app.route("/people")
@max_age(seconds = 60)
def people():
    """ Handler for a page with a list of people recently appearing in news """
    return render_template("people.html", persons = top_persons())


@app.route("/analysis")
def analysis():
    """ Handler for a page with grammatical analysis of user-entered text """
    txt = request.args.get("txt", "")[0:_MAX_TEXT_LENGTH_VIA_URL]
    return render_template("analysis.html", default_text = txt)


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
        return redirect(url_for('main'))

    with SessionContext(commit = True) as session:

        if uuid:
            a = ArticleProxy.load_from_uuid(uuid, session)
        elif url.startswith("http:") or url.startswith("https:"):
            # a = ArticleProxy.load_from_url(url, session)
            a = ArticleProxy.scrape_from_url(url, session) # Forces a new scrape
        else:
            a = None

        if a is None:
            # !!! TODO: Separate error page
            return redirect(url_for('main'))

        # Prepare the article for display (may cause it to be parsed and stored)
        a.prepare(session, verbose = True, reload_parser = True)
        register = a.create_register(session)
        # Fetch names of article topics, if any
        topics = session.query(ArticleTopic) \
            .filter(ArticleTopic.article_id == a.uuid).all()
        topics = [ dict(name = t.topic.name, identifier = t.topic.identifier) for t in topics ]

        return render_template("page.html", article = a, register = register, topics = topics)


@app.route("/")
@max_age(seconds = 60)
def main():
    """ Handler for the main (index) page """
    txt = request.args.get("txt", None)
    if txt:
        txt = txt.strip()
    if not txt:
        # Select a random default text
        txt = _DEFAULT_TEXTS[random.randint(0, len(_DEFAULT_TEXTS) - 1)]
    return render_template("main.html", default_text = txt)


# Flask handlers

@app.route('/fonts/<path:path>')
@max_age(seconds = 24 * 60 * 60) # Cache font for 24 hours
def send_font(path):
    return send_from_directory('fonts', path)

# noinspection PyUnusedLocal
@app.errorhandler(404)
def page_not_found(e):
    """ Return a custom 404 error """
    return 'Þessi vefslóð er ekki rétt', 404

@app.errorhandler(500)
def server_error(e):
    """ Return a custom 500 error """
    return 'Eftirfarandi villa kom upp: {}'.format(e), 500


# Initialize the main module

t0 = time.time()
try:
    # Read configuration file
    Settings.read("config/Reynir.conf")
except ConfigError as e:
    print("Configuration error: {0}".format(e))
    quit()

if Settings.DEBUG:
    print("Settings loaded in {0:.2f} seconds".format(time.time() - t0))
    print("Running Reynir with debug={0}, host={1}, db_hostname={2}"
        .format(Settings.DEBUG, Settings.HOST, Settings.DB_HOSTNAME))


if __name__ == "__main__":

    # Run a default Flask web server for testing if invoked directly as a main program

    # Additional files that should cause a reload of the web server application
    # Note: Reynir.grammar is automatically reloaded if its timestamp changes
    extra_files = [ 'Reynir.conf',
        'Verbs.conf', 'VerbPrepositions.conf',
        'Main.conf', 'Prefs.conf', 'Abbrev.conf'
    ]
    scraperinit.init_roots()
    from socket import error as socket_error
    import errno
    try:
        # Run the Flask web server application
        app.run(debug=Settings.DEBUG, host=Settings.HOST, use_reloader=True,
            extra_files = [ "config/" + fname for fname in extra_files ])
    except socket_error as e:
        if e.errno == errno.EADDRINUSE: # Address already in use
            print("Reynir is already running at host {0}".format(Settings.HOST))
        else:
            raise
    finally:
        ArticleProxy.cleanup()
        pass

else:

    # Running as a server module: pre-load the grammar into memory
    with Fast_Parser() as fp:
        pass

