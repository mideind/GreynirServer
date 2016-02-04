#!/usr/bin/env python
"""
    Reynir: Natural language processing for Icelandic

    Main module, URL scraper and web server

    Copyright (c) 2015 Vilhjalmur Thorsteinsson
    All rights reserved
    See the accompanying README.md file for further licensing and copyright information.

    This module is written in Python 3 for Python 3.4

"""

from bs4 import BeautifulSoup, NavigableString

import urllib.request
import codecs
import re
import time
from contextlib import closing
from datetime import datetime

from flask import Flask
from flask import render_template, redirect, jsonify
from flask import request, session, url_for

from settings import Settings, ConfigError
from tokenizer import tokenize, StaticPhrases, Abbreviations, TOK
from grammar import Nonterminal
from parser import ParseError
from fastparser import Fast_Parser, ParseForestNavigator, ParseForestPrinter, ParseForestDumper
from reducer import Reducer
from scraper import Scraper
from ptest import run_test, Test_DB

# Initialize Flask framework

app = Flask(__name__)

from flask import current_app

def debug():
    # Call this to trigger the Flask debugger on purpose
    assert current_app.debug == False, "Don't panic! You're here by request of debug()"

# Current default URL for testing

DEFAULT_URL = 'http://kjarninn.is/2015/04/mar-gudmundsson-segir-margskonar-misskilnings-gaeta-hja-hannesi-holmsteini/'
# 'http://www.ruv.is//frett/flottamennirnir-matarlausir-i-einni-kos'

# HTML tags that we explicitly don't want to look at

exclude_tags = frozenset(["script", "audio", "video", "style"])

# HTML tags that typically denote blocks (DIV-like), not inline constructs (SPAN-like)

block_tags = frozenset(["p", "h1", "h2", "h3", "h4", "div",
    "main", "article", "header", "section",
    "table", "thead", "tbody", "tr", "td", "ul", "li",
    "form", "option", "input", "label",
    "figure", "figcaption", "footer"])

whitespace_tags = frozenset(["br", "img"])


class TextList:

    """ Accumulates raw text blocks and eliminates unnecessary nesting indicators """

    def __init__(self):
        self._result = []
        self._nesting = 0

    def append(self, w):
        if self._nesting > 0:
            self._result.append(" [[ " * self._nesting)
            self._nesting = 0
        self._result.append(w)

    def append_whitespace(self):
        if self._nesting == 0:
            # No need to append whitespace if we're just inside a begin-block
            self._result.append(" ")

    def begin(self):
        self._nesting += 1

    def end(self):
        if self._nesting > 0:
            self._nesting -= 1
        else:
            self._result.append(" ]] ")

    def result(self):
        return "".join(self._result)


def extract_text(soup, result):
    """ Append the human-readable text found in an HTML soup to the result TextList """
    if soup:
        for t in soup.children:
            if type(t) == NavigableString:
                # Text content node
                result.append(t)
            elif isinstance(t, NavigableString):
                # Comment, CDATA or other text data: ignore
                pass
            elif t.name in whitespace_tags:
                # Tags that we interpret as whitespace, such as <br> and <img>
                result.append_whitespace()
            elif t.name in block_tags:
                # Nested block tag
                result.begin() # Begin block
                extract_text(t, result)
                result.end() # End block
            elif t.name not in exclude_tags:
                # Non-block tag
                extract_text(t, result)


def process_url(url):
    """ Open a URL and process the returned response """

    metadata = None
    body = None

    # Fetch the URL, returning a (metadata, content) tuple or None if error
    info = Scraper.fetch_url(url)

    if info:
        metadata, body = info
        if metadata is None:
            print("No metadata")
            metadata = dict(heading = "",
                author = "",
                timestamp = datetime.utcnow(),
                authority = 0.0)
        else:
            print("Metadata: heading '{0}'".format(metadata.heading))
            print("Metadata: author '{0}'".format(metadata.author))
            print("Metadata: timestamp {0}".format(metadata.timestamp))
            print("Metadata: authority {0:.2f}".format(metadata.authority))
            metadata = vars(metadata) # Convert namedtuple to dict

    # Extract the text content of the HTML into a list
    tlist = TextList()
    extract_text(body, tlist)
    text = tlist.result()
    tlist = None # Free memory

    # Eliminate consecutive whitespace
    text = re.sub(r'\s+', ' ', text)

    # Tokenize the resulting text, returning a generator
    return (metadata, tokenize(text))


def profile(func, *args, **kwargs):
    """ Profile the processing of text or URL """

    import cProfile as profile
    import pstats

    filename = 'Reynir.profile'

    pr = profile.Profile()
    result = pr.runcall(func, *args, **kwargs)
    pr.dump_stats(filename)

    return result


def parse(toklist, single, use_reducer, dump_forest = False):
    """ Parse the given token list and return a result dict """

    # Count sentences
    num_sent = 0
    num_parsed_sent = 0
    total_ambig = 0.0
    total_tokens = 0
    sent = []
    sent_begin = 0

    with Fast_Parser(verbose = False) as bp: # Don't emit diagnostic messages

        rdc = Reducer(bp.grammar)

        for ix, t in enumerate(toklist):
            if t[0] == TOK.S_BEGIN:
                num_sent += 1
                sent = []
                sent_begin = ix
            elif t[0] == TOK.S_END:
                slen = len(sent)
                if slen:
                    # Parse the accumulated sentence
                    err_index = None
                    num = 0 # Number of tree combinations in forest
                    score = 0 # Reducer score of the best parse tree

                    try:
                        # Parse the sentence
                        forest = bp.go(sent)
                        if forest:
                            num = Fast_Parser.num_combinations(forest)

                            if single and dump_forest:
                                # Dump the parse tree to parse.txt
                                with open("parse.txt", mode = "w", encoding= "utf-8") as f:
                                    print("Reynir parse tree for sentence '{0}'".format(url), file = f)
                                    print("{0} combinations\n".format(num), file = f)
                                    if num < 10000:
                                        ParseForestPrinter.print_forest(forest, file = f)
                                    else:
                                        print("Too many combinations to dump", file = f)

                        if use_reducer and num > 1:
                            # Reduce the resulting forest
                            forest, score = rdc.go_with_score(forest)
                            assert Fast_Parser.num_combinations(forest) == 1

                            print(ParseForestDumper.dump_forest(forest)) # !!! DEBUG

                            num = 1

                    except ParseError as e:
                        forest = None
                        # Obtain the index of the offending token
                        err_index = e.token_index

                    print("Parsed sentence of length {0} with {1} combinations, score {2}{3}"
                        .format(slen, num, score,
                            "\n" + (" ".join(s[1] for s in sent) if num >= 100 else "")))
                    if num > 0:
                        num_parsed_sent += 1
                        # Calculate the 'ambiguity factor'
                        ambig_factor = num ** (1 / slen)
                        # Do a weighted average on sentence length
                        total_ambig += ambig_factor * slen
                        total_tokens += slen
                    # Mark the sentence beginning with the number of parses
                    # and the index of the offending token, if an error occurred
                    toklist[sent_begin] = TOK.Begin_Sentence(num_parses = num, err_index = err_index)
            elif t[0] == TOK.P_BEGIN:
                pass
            elif t[0] == TOK.P_END:
                pass
            else:
                sent.append(t)

    return dict(
        tokens = toklist,
        tok_num = len(toklist),
        num_sent = num_sent,
        num_parsed_sent = num_parsed_sent,
        avg_ambig_factor = (total_ambig / total_tokens) if total_tokens > 0 else 1.0
    )


@app.route("/analyze", methods=['POST'])
def analyze():
    """ Analyze text from a given URL """

    url = request.form.get("url", "").strip()
    use_reducer = not ("noreduce" in request.form)
    dump_forest = "dump" in request.form
    metadata = None
    # Single sentence (True) or contiguous text from URL (False)?
    single = False

    t0 = time.time()

    if url.startswith("http:") or url.startswith("https:"):
        # Scrape the URL, tokenize the text content and return the token list
        metadata, generator = process_url(url)
        toklist = list(generator)
    else:
        # Tokenize the text entered as-is and return the token list
        # In this case, there's no metadata
        toklist = list(tokenize(url))
        single = True

    tok_time = time.time() - t0

    t0 = time.time()

    # result = profile(parse, toklist, single, use_reducer, dump_forest)
    result = parse(toklist, single, use_reducer, dump_forest)

    parse_time = time.time() - t0

    result["metadata"] = metadata
    result["tok_time"] = tok_time
    result["parse_time"] = parse_time

    # Return the tokens as a JSON structure to the client
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
        assert isinstance(p[4], Nonterminal) or isinstance(p[4], tuple)
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
    use_reducer = not ("noreduce" in request.form)

    # Tokenize the text
    tokens = list(tokenize(txt))

    grammar = None

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

    # Dump the parse tree to parse.txt
    with open("parse.txt", mode = "w", encoding= "utf-8") as f:
        if forest is not None:
            print("Reynir parse tree for sentence '{0}'".format(txt), file = f)
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
        print(ParseForestDumper.dump_forest(forest)) # !!! DEBUG

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
            assert isinstance(info, Nonterminal) or isinstance(info, tuple)
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
                assert isinstance(info, Nonterminal)
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

    #debug()

    return render_template("parsegrid.html", txt = txt, err = err, tbl = tbl,
        combinations = combinations, score = score,
        choice_list = uc_list, parse_path = parse_path)


@app.route("/addsentence", methods=['POST'])
def add_sentence():
    """ Add a sentence to the test database """
    sentence = request.form.get('sentence', "")
    # The sentence may be one that should parse and give us ideally one result tree,
    # or one that is wrong and should not parse, giving 0 result trees.
    should_parse = request.form.get('shouldparse', 'true') == 'true'
    result = False
    if sentence:
        try:
            with closing(Test_DB.open_db()) as db:
                result = db.add_sentence(sentence, target = 1 if should_parse else 0)
        except Exception as e:
            return jsonify(result = False, err = str(e))
    return jsonify(result = result)


@app.route("/")
def main():
    """ Handler for the main (index) page """

    # Instantiate a dummy parser to access grammar info
    # (this does not cause repeated parsing of the grammar as it is cached in memory)
    bp = Fast_Parser(verbose = False)
    txt = request.args.get("txt", None)
    if not txt:
        txt = DEFAULT_URL
    return render_template("main.html", default_text = txt, grammar = bp.grammar)


@app.route("/test")
def test():
    """ Handler for a page of sentences for testing """

    # Run test and show the result
    bp = Fast_Parser(verbose = False) # Don't emit diagnostic messages

    return render_template("test.html", result = run_test(bp))


# Flask handlers

@app.errorhandler(404)
def page_not_found(e):
    """ Return a custom 404 error """
    return 'Þessi vefslóð er ekki rétt', 404

@app.errorhandler(500)
def server_error(e):
    """ Return a custom 500 error """
    return 'Eftirfarandi villa kom upp: {}'.format(e), 500

# Initialize the main module

try:
    # Read configuration file
    Settings.read("Reynir.conf")
except ConfigError as e:
    print("Configuration error: {0}".format(e))
    quit()

print("Running Reynir with debug={0}, host={1}, db_hostname={2}"
    .format(Settings.DEBUG, Settings.HOST, Settings.DB_HOSTNAME))

# Run a default Flask web server for testing if invoked directly as a main program

if __name__ == "__main__":

    # Additional files that should cause a reload of the web server application
    # Note: Reynir.grammar is automatically reloaded if its timestamp changes
    extra_files = ['Reynir.conf', 'Verbs.conf']

    # Run the Flask web server application
    app.run(debug=Settings.DEBUG, host=Settings.HOST, use_reloader=True,
        extra_files = extra_files)

