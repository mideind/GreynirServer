"""
    Reynir: Natural language processing for Icelandic

    Main module, URL scraper and web server

    Author: Vilhjalmur Thorsteinsson

    This software is at a very early development stage.
    While that is the case, it is:
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

from flask import Flask
from flask import render_template, redirect, jsonify
from flask import request, session, url_for

from settings import Settings, ConfigError
from tokenizer import tokenize, dump_tokens_to_file, StaticPhrases, Abbreviations, TOK
from grammar import Nonterminal
from parser import Parser, ParseError
from binparser import BIN_Parser
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

    with closing(urllib.request.urlopen(url)) as response:
        html_doc = response.read()

    soup = BeautifulSoup(html_doc, "html.parser")
    # soup = BeautifulSoup(html_doc, 'html5lib') # Use alternative parser
    body = soup.body

    # Extract the text content of the HTML into a list
    tlist = TextList()
    extract_text(body, tlist)
    text = tlist.result()
    tlist = None # Free memory

    # Eliminate consecutive whitespace
    text = re.sub(r'\s+', ' ', text)

    # Tokenize the resulting text, returning a generator
    return tokenize(text)


def run():
    """ Main test routine """
    process_url('http://www.ruv.is//frett/flottamennirnir-matarlausir-i-einni-kos')


@app.route("/analyze", methods=['POST'])
def analyze():
    """ Analyze text from a given URL """

    url = request.form.get("url", "").strip()
    t0 = time.time()

    if url.startswith("http:") or url.startswith("https:"):
        # Scrape the URL, tokenize the text content and return the token list
        toklist = list(process_url(url))
    else:
        # Tokenize the text entered as-is and return the token list
        toklist = list(tokenize(url))

    tok_time = time.time() - t0

    # Count sentences
    num_sent = 0
    sent_begin = 0
    bp = BIN_Parser()

    t0 = time.time()

    for ix, t in enumerate(toklist):
        if t[0] == TOK.S_BEGIN:
            num_sent += 1
            sent = []
            sent_begin = ix
        elif t[0] == TOK.S_END:
            # Parse the accumulated sentence
            try:
                forest = bp.go(sent)
            except ParseError as e:
                forest = None
            num = 0 if forest is None else Parser.num_combinations(forest)
            print("Parsed sentence of length {0} with {1} combinations{2}".format(len(sent), num,
                "\n" + " ".join(s[1] for s in sent) if num >= 100 else ""))
            # Mark the sentence beginning with the number of parses
            toklist[sent_begin] = TOK.Begin_Sentence(num_parses = num)
        elif t[0] == TOK.P_BEGIN:
            pass
        elif t[0] == TOK.P_END:
            pass
        else:
            sent.append(t)

    parse_time = time.time() - t0

    result = dict(
        tokens = toklist,
        tok_time = tok_time,
        tok_num = len(toklist),
        tok_sent = num_sent,
        parse_time = parse_time
    )

    # Dump the tokens to a text file for inspection
    # dump_tokens_to_file("txt", toklist)

    # Return the tokens as a JSON structure to the client
    return jsonify(result = result)


@app.route("/parsegrid", methods=['POST'])
def parse_grid():
    """ Show the parse grid for a particular parse tree of a sentence """

    MAX_LEVEL = 32 # Maximum level of option depth we can handle
    txt = request.form.get('txt', "")
    parse_path = request.form.get('option', "")

    # Tokenize the text
    tokens = list(tokenize(txt))
    # Parse the text
    bp = BIN_Parser()
    err = dict()

    try:
        forest = bp.go(tokens)
    except ParseError as e:
        err["msg"] = str(e)
        # Relay information about the parser state at the time of the error
        err["info"] = e.info()
        forest = None

    # Find the number of parse combinations
    combinations = Parser.num_combinations(forest) if forest else 0
    # Make the parse grid with all options
    grid, ncols = Parser.make_grid(forest) if forest else ([], 0)
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
                info = info.name()
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
        combinations = combinations, choice_list = uc_list,
        parse_path = parse_path)


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

    return render_template("main.html", default_url = DEFAULT_URL)


@app.route("/test")
def test():
    """ Handler for a page of sentences for testing """

    # Run test and show the result
    bp = BIN_Parser()

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

# Run a default Flask web server for testing if invoked directly as a main program

if __name__ == "__main__":

    try:
        # Read configuration file
        Settings.read("Reynir.conf")
    except ConfigError as e:
        print("Configuration error: {0}".format(e))
        quit()

    print("Running Reynir with debug={0}, host={1}, db_hostname={2}"
        .format(Settings.DEBUG, Settings.HOST, Settings.DB_HOSTNAME))

    # Additional files that should cause a reload of the web server application
    extra_files = ['Reynir.grammar', 'Reynir.conf', 'Verbs.conf']

    # Run the Flask web server application
    app.run(debug=Settings.DEBUG, host=Settings.HOST, use_reloader=True,
        extra_files = extra_files)

