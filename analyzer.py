#!/usr/bin/env python
"""
    Reynir: Natural language processing for Icelandic

    Word category analyzer front end

    Copyright (c) 2015 Vilhjalmur Thorsteinsson
    All rights reserved
    See the accompanying README.md file for further licensing and copyright information.

    This module is written in Python 3 for Python 3.4

"""

from contextlib import closing

from flask import Flask
from flask import render_template, redirect, jsonify
from flask import request, session, url_for

from settings import Settings, ConfigError
from tokenizer import tokenize, TOK
from parser import ParseError
from fastparser import Fast_Parser, ParseForestNavigator
from binparser import BIN_Token
from reducer import Reducer

# Initialize Flask framework

app = Flask(__name__)

from flask import current_app

def debug():
    # Call this to trigger the Flask debugger on purpose
    assert current_app.debug == False, "Don't panic! You're here by request of debug()"

_GENDERS_SET = BIN_Token._GENDERS_SET
_CASES_SET = set(BIN_Token._CASES)
_NUMBER_SET = { "et", "ft" }
_CATEGORY_SET = { "no", "so", "lo", "fs", "ao", "eo", "st", "fn", "pfn", "abfn", "nhm", "to", "töl", "ártal" }
_CHECK_SET = {
    "no" : _CASES_SET | _NUMBER_SET,
    "so" : set(BIN_Token._VERB_VARIANTS) | _NUMBER_SET | { "op" },
    "fs" : set(),
    "lo" : _GENDERS_SET | _CASES_SET | _NUMBER_SET | { "mst", "sb", "vb" },
    "fn" : _GENDERS_SET | _CASES_SET | _NUMBER_SET | { "p1", "p2", "p3" }
}
_CHECK_SET["pfn"] = _CHECK_SET["fn"]

# Mapping of literal terminal names to corresponding word categories

_CATEGORY_MAP = {
    "margur" : "no",
    "árið" : "no",
    "ég" : "pfn",
    "þú" : "pfn",
    "hans" : "pfn",
    "hennar" : "pfn",
    "hann" : "pfn",
    "hún" : "pfn",
    "það" : "pfn",
    "sá" : "fn",
    "hvor" : "fn",
    "vera" : "so",
    "verða" : "so",
    "vilja" : "so",
    "telja" : "so",
    "geta" : "so",
    "munu" : "so",
    "skulu" : "so",
    "mega" : "so",
    "hafa" : "so",
    "eiga" : "so",
    "sem" : "st",
    "og" : "st",
    "eða" : "st",
    "en" : "st",
    "þótt" : "st",
    "hver" : "st",
    "hvor" : "st",
    "hvaða" : "st",
    "hvers" : "st",
    "vegna" : "st",
    "hvar" : "st",
    "hvernig" : "st",
    "hvort" : "st",
    "hvenær" : "st",
    "þannig" : "st",
    "þegar" : "st",
    "þá" : "st",
    "þar" : "st",
    "nema" : "st",
    "svo" : "st"
}

def compatible(meaning, terminal, category):
    """ Return True if the word meaning is compatible with the terminal """
    is_no = False
    if category == "no":
        if meaning.ordfl not in _GENDERS_SET:
            return False
        is_no = True
    elif category in { "eo", "ao" }:
        if meaning.ordfl != "ao":
            return False
    elif category in _CATEGORY_SET and category != meaning.ordfl:
        return False
    beyging = meaning.beyging
    check_set = _CHECK_SET.get(category, {})
    for v in terminal.variants:
        if is_no and v in _GENDERS_SET:
            # Special check for noun genders
            if meaning.ordfl != v:
                return False
        elif v in check_set and BIN_Token._VARIANT[v] not in beyging:
            return False
    # Additional checks for forms that we don't accept
    # unless they're explicitly permitted by the terminal
    if category == "so":
        for v in [ "sagnb", "lhþt", "bh" ]:
            if BIN_Token._VARIANT[v] in beyging and not terminal.has_variant(v):
                return False
    return True

def mark_categories(forest, toklist, ix):

    """ Annotate the token list with word category information """

    class TokenCategorizer(ParseForestNavigator):

        def __init__(self, toklist, ix):
            super().__init__()
            self._toklist = toklist
            self._ix = ix

        def _visit_token(self, level, node):
            """ At token node """
            category = node.terminal.first
            if category in _CATEGORY_MAP:
                # Convert from literal first part to corresponding word category
                category = _CATEGORY_MAP[category]
            ix = self._ix
            toklist = self._toklist
            while toklist[ix][0] in { TOK.P_BEGIN, TOK.P_END }:
                ix += 1
            if toklist[ix][0] == TOK.WORD:
                # Replace the original word token with an augmented 4-tuple
                # containing the word category and the name of the
                # terminal that was matched
                t = toklist[ix]
                if t.val is None:
                    meanings = None
                else:
                    meanings = [ m for m in t.val if compatible(m, node.terminal, category) ]
                toklist[ix] = (t.kind, t.txt, meanings, node.terminal.name, category)
                print("Assigning category {0} to word '{1}'".format(category, t.txt))
            ix += 1
            self._ix = ix
            return None

    TokenCategorizer(toklist, ix).go(forest)


@app.route("/analyze", methods=['POST'])
def analyze():
    """ Find word categories in the submitted text """

    txt = request.form.get("txt", "").strip()

    # Tokenize the text entered as-is and return the token list
    toklist = list(tokenize(txt))

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
                    try:
                        # Parse the sentence
                        forest = bp.go(sent)
                        if forest:
                            num = Fast_Parser.num_combinations(forest)

                        if num > 1:
                            # Reduce the resulting forest
                            forest = rdc.go(forest)
                            assert Fast_Parser.num_combinations(forest) == 1

                        # Mark the token list with the identified word categories
                        mark_categories(forest, toklist, sent_begin + 1)

                    except ParseError as e:
                        forest = None
                        # Obtain the index of the offending token
                        err_index = e.token_index
                    print("Parsed sentence of length {0} with {1} combinations{2}".format(slen, num,
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

    result = dict(
        tokens = toklist,
        tok_num = len(toklist),
        num_sent = num_sent,
        num_parsed_sent = num_parsed_sent,
        avg_ambig_factor = (total_ambig / total_tokens) if total_tokens > 0 else 1.0
    )

    # Return the tokens as a JSON structure to the client
    return jsonify(result = result)


@app.route("/")
def main():
    """ Handler for the main (index) page """

    txt = request.args.get("txt", "")
    return render_template("analyzer.html", default_text = txt)


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
    # Note: Reynir.grammar is automatically reloaded if its timestamp changes
    extra_files = ['Reynir.conf', 'Verbs.conf']

    # Run the Flask web server application
    app.run(debug = Settings.DEBUG, host = Settings.HOST, port = 8080,
        use_reloader = True,
        extra_files = extra_files)

