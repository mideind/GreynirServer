# type: ignore
"""
    Greynir: Natural language processing for Icelandic

    MIM corpus test module

    Copyright (C) 2021 Miðeind ehf.

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


    This module parses XML files in the TEI format from the
    MIM corpus ('Mörkuð íslensk málheild') and compares the POS
    tags in the corpus with output from Greynir

"""

from os import listdir
from os.path import isfile, isdir, join

import xml.etree.ElementTree as ET

from tokenizer import TOK, tokenize
from fastparser import Fast_Parser, ParseError, ParseForestNavigator
from reducer import Reducer
from settings import Settings, ConfigError

# Constants

NS = 'http://www.tei-c.org/ns/1.0'
LEN_NS_PREFIX = len(NS) + 2

# Namespace dictionary for the XML parser
ns = { 'mim': NS }

LEFT_SPACE = "([$«"
RIGHT_SPACE = ".,:;!?%)]»"
MID_SPACE = "#&=<>|"

def find_pos_tags(forest):

    pos_tags = {}

    class TerminalFinder(ParseForestNavigator):

        """ Subclass to navigate a parse forest and populate the set
            of terminals that match each token """

        def visit_token(self, level, node):
            """ At token node """
            assert node.terminal is not None
            pos_tags[node.start] = (node.token, node.terminal)
            return None

    TerminalFinder().go(forest)

    #for key, val in sorted(pos_tags.items()):
    #    print("{0}: {1} -> {2}".format(key, val[0], val[1]))

    return pos_tags


def parse_tokens(toklist, mim_tags, fast_p):
    """ Parse the given token list and return a result dict """

    # Count sentences
    num_sent = 0
    num_parsed_sent = 0
    total_ambig = 0.0
    total_tokens = 0
    sent = []
    sent_begin = 0
    tag_ix = 0
    ntags = len(mim_tags)

    rdc = Reducer(fast_p.grammar)

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
                    # Progress indicator: sentence count
                    print("{}".format(num_sent), end="\r")
                    # Parse the sentence
                    forest = fast_p.go(sent)
                    if forest:
                        num = Fast_Parser.num_combinations(forest)

                    if num > 1:
                        # Reduce the resulting forest
                        forest = rdc.go(forest)

                except ParseError as e:
                    forest = None
                    num = 0
                    # Obtain the index of the offending token
                    err_index = e.token_index

                if num > 0:
                    num_parsed_sent += 1

                    # Extract the POS tags for the terminals in the forest
                    pos_tags = find_pos_tags(forest)

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
            # Check whether the token streams are in sync
            if tag_ix < ntags and t[1] != mim_tags[tag_ix][1]:
                #print("Warning: mismatch between MIM token '{0}' and Greynir token '{1}'".format(mim_tags[tag_ix][1], t[1]))
                # Attempt to sync again by finding the Greynir token in the MIM tag stream
                gap = 1
                MAX_LOOKAHEAD = 4
                while gap < MAX_LOOKAHEAD and (tag_ix + gap) < ntags and mim_tags[tag_ix + gap][1] != t[1]:
                    gap += 1
                if gap < MAX_LOOKAHEAD:
                    # Found the Greynir token ahead
                    #print("Re-synced by skipping ahead by {0} tokens".format(gap))
                    tag_ix += gap
            if tag_ix < ntags:
                tag_ix += 1

    return dict(
        tokens = toklist,
        tok_num = len(toklist),
        num_sent = num_sent,
        num_parsed_sent = num_parsed_sent,
        avg_ambig_factor = (total_ambig / total_tokens) if total_tokens > 0 else 1.0
    )


def parse_paragraph(parag, mim_tags, fast_p):
    """ Parse a single paragraph in free text form and compare to MIM POS tags """

    tokens = tokenize(parag)
    tlist = list(tokens)
    result = parse_tokens(tlist, mim_tags, fast_p)
    print("{0}\n--> {1} sentences, {2} parsed".format(parag, result["num_sent"], result["num_parsed_sent"]))


def parse_xml_file(fpath, fast_p):
    """ Parses a single XML file """

    tree = ET.parse(fpath)
    root = tree.getroot()
    text = root.find('mim:text', ns)
    s = text.findall('.//mim:s',ns)
    # Person name being accumulated
    acc_ty = ""
    acc_name = ""

    for sent in s:
        print("\nFile {0} paragraph {1}".format(fpath, sent.attrib['n']))
        stext = []
        mim_tags = []
        last_was_word = False
        for child in sent:
            tag = child.tag[LEN_NS_PREFIX:]
            ty = child.attrib["type"]
            #print("{0}: '{2}' {1}".format(tag, child.attrib, child.text))
            if tag == "w":
                if last_was_word:
                    stext.append(" " + child.text)
                else:
                    stext.append(child.text)
                    last_was_word = True
            elif tag == "c":
                punct = child.text
                if punct in LEFT_SPACE:
                    stext.append(" " + punct)
                elif punct in RIGHT_SPACE:
                    stext.append(punct + " ")
                elif punct in MID_SPACE:
                    stext.append(" " + punct + " ")
                else:
                    stext.append(child.text)
                last_was_word = False
            else:
                print("Unknown tag: '{}'".format(tag))
            # Append a token tuple to the token list
            if tag == "w" and ty == acc_ty:
                # Continuing a person name
                acc_name += " " + child.text
            else:
                if acc_name:
                    # Not continuing a person name: add it to the token stream
                    mim_tags.append((acc_ty, acc_name))
                    acc_name = ""
                    acc_ty = ""
                if tag == "w" and (ty == "nken-s" or ty == "nven-s"):
                    # Start a new name accumulation
                    acc_ty = ty
                    acc_name = child.text
                else:
                    # Normal continuation: add the token
                    mim_tags.append((ty, child.text))

        # Reassemble the source text into a string
        parag = "".join(stext)
        # Parse the resulting paragraph and compare the parse to the MIM tags
        parse_paragraph(parag, mim_tags, fast_p)


def parse_directory(dirpath, fast_p):
    """ Parses all XML files in a directory """
    print("*** Parsing directory {0}".format(dirpath))
    if dirpath != 'mim/raduneyti':
        return
    for f in listdir(dirpath):
        fpath = join(dirpath, f)
        if isfile(fpath) and fpath.endswith(".xml"):
            parse_xml_file(fpath, fast_p)


def parse_directories(rootpath, fast_p):
    """ Visit all subdirectories within a directory """
    for d in listdir(rootpath):
        dpath = join(rootpath, d)
        if isdir(dpath):
            parse_directory(dpath, fast_p)


if __name__ == "__main__":

    # Initialize the parsing module

    try:
        # Read configuration file
        Settings.read("config/Greynir.conf")
    except ConfigError as e:
        print("Configuration error: {0}".format(e))
        quit()

    print("Running Greynir with debug={0}, host={1}, db_hostname={2}"
        .format(Settings.DEBUG, Settings.HOST, Settings.DB_HOSTNAME))

    with Fast_Parser(verbose = False) as fast_p:

        g = fast_p.grammar

        print("Greynir.grammar has {0} nonterminals, {1} terminals, {2} productions"
            .format(g.num_nonterminals, g.num_terminals, g.num_productions))

        # Attempt to parse all XML files in subdirectories within mim/

        parse_directories("mim", fast_p)

