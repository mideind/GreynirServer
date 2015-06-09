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
from tokenizer import parse_text, dump_tokens_to_file, StaticPhrases, Abbreviations, TOK
from parser import Parser, ParseError
from binparser import BIN_Parser

# Initialize Flask framework

app = Flask(__name__)

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

    # Parse the resulting text, returning a generator
    return parse_text(text)


def run():
    """ Main test routine """
    process_url('http://www.ruv.is//frett/flottamennirnir-matarlausir-i-einni-kos')


@app.route("/analyze", methods=['POST'])
def analyze():
    """ Analyze text from a given URL """

    url = request.form.get('url', None)

    # Scrape the URL, tokenize the text content and return the token list

    t0 = time.time()
    toklist = list(process_url(url))
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
            print("Parsed sentence of length {0} with {1} combinations".format(len(sent), num))
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
    dump_tokens_to_file("txt", toklist)

    # Return the tokens as a JSON structure to the client
    return jsonify(result = result)


@app.route("/parsegrid", methods=['POST'])
def parse_grid():
    """ Show the parse grid for a sentence """

    txt = request.form.get('txt', "")

    bp = BIN_Parser()
    tokens = list(parse_text(txt))
    forest = bp.go(tokens)
    combinations = Parser.num_combinations(forest)
    grid, ncols = Parser.make_grid(forest)
    # The grid is columnar; convert it to row-major
    # form for convenient translation into HTML
    # There will be as many columns as there are tokens
    nrows = len(grid)
    tbl = [ [] for _ in range(nrows) ]
    for gix, gcol in enumerate(grid):
        col = 0
        for startcol, endcol, info in gcol:
            if col < startcol:
                tbl[gix].append((startcol-col, 1, "", ""))
            rowspan = 1
            if isinstance(info, tuple):
                cls = { "terminal" }
                # rowspan = nrows - gix
                # !!! When adding rowspan to the mix,
                # the following rows also need to be updated
                # to subtract one colspan from the calculation
                # in the right places
            else:
                cls = { "nonterminal" }
            if endcol - startcol == 1:
                cls |= { "vertical" }
            tbl[gix].append((endcol-startcol, rowspan, info, cls))
            col = endcol
        if col < ncols:
            tbl[gix].append((ncols - col, 1, "", ""))
    return render_template("parsegrid.html", txt = txt, tbl = tbl, combinations = combinations)


@app.route("/")
def main():
    """ Handler for the main (index) page """

    return render_template("main.html", default_url = DEFAULT_URL)


@app.route("/test")
def test():
    """ Handler for a page of sentences for testing """

    return render_template("test.html")


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

    # Run the Flask web server application
    app.run(debug=Settings.DEBUG, host=Settings.HOST, use_reloader=True)

