"""

    Reynir: Natural language processing for Icelandic

    Query module

    Copyright (C) 2019 Miðeind ehf.
    Original author: Vilhjálmur Þorsteinsson

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


    This module implements a query processor that operates on queries
    in the form of parse trees and returns the results requested,
    if the query is valid and understood.

"""

import importlib
import logging
import datetime
import json

from settings import Settings

from db import SessionContext

from tree import Tree
from reynir import TOK, tokenize, correct_spaces
from reynir.fastparser import (
    Fast_Parser,
    ParseForestDumper,
    ParseError,
)
from reynir.binparser import BIN_Grammar, GrammarError
from reynir.reducer import Reducer
from nertokenizer import recognize_entities
from images import get_image_url
from processor import modules_in_dir


# The grammar root nonterminal for queries; see Reynir.grammar
_QUERY_ROOT = "QueryRoot"

# A fixed preamble that is inserted before all query grammar fragments
_GRAMMAR_PREAMBLE = """

QueryRoot →
    Query

# Mark the QueryRoot nonterminal as a root in the grammar
$root(QueryRoot)

"""


class QueryGrammar(BIN_Grammar):

    """ A subclass of BIN_Grammar that reads its input from
        strings obtained from query handler plug-ins in the
        queries subdirectory, prefixed by a preamble """

    def __init__(self):
        super().__init__()
        # Enable the 'include_queries' condition
        self.set_conditions({"include_queries"})

    @classmethod
    def is_grammar_modified(cls):
        """ Override inherited function to specify that query grammars
            should always be reparsed, since the set of plug-in query
            handlers may have changed, as well as their grammar fragments. """
        return True

    def read(self, fname, verbose=False, binary_fname=None):
        """ Overrides the inherited read() function to supply grammar
            text from a file as well as additional grammar fragments
            from query processor modules. """

        def grammar_generator():
            """ A generator that yields a grammar file, line-by-line,
                followed by grammar additions coming from a string
                that has been coalesced from grammar fragments in query
                processor modules. """
            with open(fname, "r", encoding="utf-8") as inp:
                # Read grammar file line-by-line
                for line in inp:
                    yield line
            # Yield the query grammar preamble
            grammar_preamble = _GRAMMAR_PREAMBLE.split("\n")
            for line in grammar_preamble:
                yield line
            # Yield grammar additions from plug-ins, if any
            grammar_additions = QueryParser.grammar_additions().split("\n")
            for line in grammar_additions:
                yield line

        try:
            return self.read_from_generator(
                fname, grammar_generator(), verbose, binary_fname
            )
        except (IOError, OSError):
            raise GrammarError("Unable to open or read grammar file", fname, 0)


class QueryParser(Fast_Parser):

    """ A subclass of Fast_Parser, specialized to parse queries """

    _GRAMMAR_BINARY_FILE = Fast_Parser._GRAMMAR_FILE + ".query.bin"

    # Keep a separate grammar class instance and time stamp for
    # QueryParser. This Python sleight-of-hand overrides
    # class attributes that are defined in BIN_Parser, see binparser.py.
    _grammar_ts = None
    _grammar = None
    _grammar_class = QueryGrammar

    # Also keep separate class instances of the C grammar and its timestamp
    _c_grammar = None
    _c_grammar_ts = None

    # Store the grammar additions for queries
    # (these remain constant for all query parsers, so there is no
    # need to store them per-instance)
    _grammar_additions = ""

    def __init__(self, grammar_additions):
        QueryParser._grammar_additions = grammar_additions
        super().__init__(verbose=False, root=_QUERY_ROOT)

    @classmethod
    def grammar_additions(cls):
        return cls._grammar_additions


class Query:

    """ A Query is initialized by parsing a query string using QueryRoot as the
        grammar root nonterminal. The Query can then be executed by processing
        the best parse tree using the nonterminal handlers given above, returning a
        result object if successful. """

    _parser = None
    _processors = None

    def __init__(self, session, query, voice, auto_uppercase, location):
        self._session = session
        self._query = query
        self._location = location
        # Prepare a "beautified query" object, that can be
        # shown in a client user interface
        bq = (query[0].upper() + query[1:]) if query else ""
        if not bq.endswith("?"):
            bq += "?"
        self._beautified_query = bq
        self._voice = voice
        self._auto_uppercase = auto_uppercase
        self._error = None
        # A detailed answer, which can be a list or a dict
        self._response = None
        # A single "best" displayable text answer
        self._answer = None
        # A version of self._answer that can be
        # fed to a voice synthesizer
        self._voice_answer = None
        self._tree = None
        self._qtype = None
        self._key = None
        self._toklist = None

    @classmethod
    def init_class(cls):
        """ Initialize singleton data, i.e. the list of query
            processor modules and the query parser instance """
        procs = []
        # Load the query processor modules found in the
        # queries directory
        modnames = modules_in_dir("queries")
        for modname in sorted(modnames):
            try:
                m = importlib.import_module(modname)
                procs.append(m)
            except ImportError as e:
                logging.error(
                    "Error importing query processor module {0}: {1}"
                    .format(modname, e)
                )
        cls._processors = procs

        # Obtain query grammar fragments from those processors
        # that handle parse trees
        grammar_fragments = []
        for processor in procs:
            handle_tree = getattr(processor, "HANDLE_TREE", None)
            if handle_tree:
                # Check whether this processor supplies
                # a query grammar fragment
                fragment = getattr(processor, "GRAMMAR", None)
                if fragment and isinstance(fragment, str):
                    # Looks legit: add it to our list
                    grammar_fragments.append(fragment)

        # Coalesce the grammar additions from the fragments
        grammar_additions = "\n".join(grammar_fragments)
        # Initialize a singleton parser instance for queries,
        # with the nonterminal 'QueryRoot' as the grammar root
        cls._parser = QueryParser(grammar_additions)

    @staticmethod
    def _parse(toklist):
        """ Parse a token list as a query """
        bp = Query._parser
        num_sent = 0
        num_parsed_sent = 0
        rdc = Reducer(bp.grammar)
        trees = dict()
        sent = []

        for ix, t in enumerate(toklist):
            if t[0] == TOK.S_BEGIN:
                sent = []
            elif t[0] == TOK.S_END:
                slen = len(sent)
                if not slen:
                    continue
                num_sent += 1
                # Parse the accumulated sentence
                num = 0
                try:
                    # Parse the sentence
                    forest = bp.go(sent)
                    if forest is not None:
                        num = Fast_Parser.num_combinations(forest)
                        if num > 1:
                            # Reduce the resulting forest
                            forest = rdc.go(forest)
                except ParseError:
                    forest = None
                if num > 0:
                    num_parsed_sent += 1
                    # Obtain a text representation of the parse tree
                    trees[num_sent] = ParseForestDumper.dump_forest(forest)

            elif t[0] == TOK.P_BEGIN:
                pass
            elif t[0] == TOK.P_END:
                pass
            else:
                sent.append(t)

        result = dict(num_sent=num_sent, num_parsed_sent=num_parsed_sent)
        return result, trees

    def parse(self, result):
        """ Parse the token list as a query, returning True if valid """
        self._tree = None  # Erase previous tree, if any
        self._error = None  # Erase previous error, if any
        self._qtype = None  # Erase previous query type, if any
        self._key = None
        self._toklist = None

        q = self._query
        toklist = tokenize(
            q, auto_uppercase=q.islower() if self._auto_uppercase else False
        )
        toklist = list(recognize_entities(toklist, enclosing_session=self._session))

        actual_q = correct_spaces(" ".join(t.txt for t in toklist if t.txt))

        if Settings.DEBUG:
            # Log the query string as seen by the parser
            print("Query is: '{0}'".format(actual_q))

        parse_result, trees = Query._parse(toklist)

        if not trees:
            # No parse at all
            self.set_error("E_NO_PARSE_TREES")
            return False

        result.update(parse_result)

        if result["num_sent"] != 1:
            # Queries must be one sentence
            self.set_error("E_MULTIPLE_SENTENCES")
            return False
        if result["num_parsed_sent"] != 1:
            # Unable to parse the single sentence
            self.set_error("E_NO_PARSE")
            return False
        if 1 not in trees:
            # No sentence number 1
            self.set_error("E_NO_FIRST_SENTENCE")
            return False
        # Looks good
        # Store the resulting parsed query as a tree
        tree_string = "S1\n" + trees[1]
        self._tree = Tree()
        self._tree.load(tree_string)
        # Store the token list
        self._toklist = toklist
        return True

    def execute_from_plain_text(self):
        """ Attempt to execute a plain text query, without having to parse it """
        for processor in self._processors:
            handle_plain_text = getattr(processor, "handle_plain_text", None)
            if handle_plain_text is not None:
                # This processor has a handle_plain_text function:
                # call it
                if handle_plain_text(self):
                    # Successfully handled: we're done
                    return True
        return False

    def execute_from_tree(self):
        """ Execute the query contained in the previously parsed tree;
            return True if successful """
        if self._tree is None:
            self.set_error("E_QUERY_NOT_PARSED")
            return False
        for processor in self._processors:
            self._error = None
            self._qtype = None
            # If a processor defines HANDLE_TREE and sets it to
            # a truthy value, it wants to handle parse trees
            handle_tree = getattr(processor, "HANDLE_TREE", None)
            if handle_tree:
                # Process the tree, which has only one sentence
                self._tree.process(self._session, processor, query=self)
                if self._answer and self._error is None:
                    # The processor successfully answered the query
                    return True
        # No processor was able to answer the query
        return False

    @property
    def query(self):
        return self._query

    @property
    def query_lower(self):
        return self._query.lower()

    @property
    def beautified_query(self):
        return self._beautified_query

    def set_beautified_query(self, q):
        self._beautified_query = q

    @property
    def location(self):
        return self._location

    @property
    def token_list(self):
        return self._toklist

    def set_qtype(self, qtype):
        """ Set the query type ('Person', 'Title', 'Company', 'Entity'...) """
        self._qtype = qtype

    def set_answer(self, response, answer, voice_answer=None):
        """ Set the answer to the query """
        # Detailed response
        self._response = response
        # Single best answer, as a displayable string
        self._answer = answer
        # A voice version of the single best answer
        self._voice_answer = voice_answer

    def set_key(self, key):
        """ Set the query key, i.e. the term or string used to execute the query """
        # This is for instance a person name in nominative case
        self._key = key

    def set_error(self, error):
        """ Set an error result """
        self._error = error

    def qtype(self):
        """ Return the query type """
        return self._qtype

    def response(self):
        """ Return the detailed query answer """
        return self._response

    def answer(self):
        """ Return the 'single best' displayable query answer """
        return self._answer

    def voice_answer(self):
        """ Return a voice version of the 'single best' answer, if any """
        return self._voice_answer

    def key(self):
        """ Return the query key """
        return self._key

    def error(self):
        """ Return the query error, if any """
        return self._error

    def execute(self):
        """ Check whether the parse tree is describes a query, and if so,
            execute the query, store the query answer in the result dictionary
            and return True """
        if Query._parser is None:
            Query.init_class()
        result = dict(q_raw=self.query, q=self.beautified_query)
        # First, try to handle this from plain text, without parsing:
        # shortcut to a successful, plain response
        if not self.execute_from_plain_text():
            if not self.parse(result):
                if Settings.DEBUG:
                    print("Unable to parse query, error {0}".format(self.error()))
                result["error"] = self.error()
                result["valid"] = False
                return result
            if not self.execute_from_tree():
                # This is a query, but its execution failed for some reason:
                # return the error
                # if Settings.DEBUG:
                #     print("Unable to execute query, error {0}".format(q.error()))
                result["error"] = self.error() or "E_UNABLE_TO_EXECUTE_QUERY"
                result["valid"] = True
                return result
        # Successful query: return the answer in response
        if self._answer:
            result["answer"] = self._answer
        if self._voice and self._voice_answer:
            # This is a voice query and we have a voice answer to it
            result["voice"] = self._voice_answer
        if self._voice:
            # Optimize the response to voice queries:
            # we don't need detailed information about alternative
            # answers or their sources
            result["response"] = dict(answer=self._answer or "")
        else:
            # Return a detailed response if not a voice query
            result["response"] = self._response
        # Re-assign the beautified query string, in case the processor modified it
        result["q"] = self.beautified_query
        # ...and the query type, as a string ('Person', 'Entity', 'Title' etc.)
        result["qtype"] = qt = self.qtype()
        # ...and the key used to retrieve the answer, if any
        result["key"] = self.key()
        if not self._voice and qt == "Person":
            # For a person query, add an image (if available)
            img = get_image_url(self.key(), enclosing_session=self._session)
            if img is not None:
                result["image"] = dict(
                    src=img.src,
                    width=img.width,
                    height=img.height,
                    link=img.link,
                    origin=img.origin,
                    name=img.name,
                )
        result["valid"] = True
        if Settings.DEBUG:
            def converter(o):
                """ Ensure that datetime.datetime is output in ISO format to JSON """
                if isinstance(o, datetime.datetime):
                    return o.isoformat()[0:16]
                return None
            print(
                "{0}".format(
                    json.dumps(result, indent=3, ensure_ascii=False, default=converter)
                )
            )
        return result


def process_query(q, voice, auto_uppercase, location=None):
    """ Process an incoming natural language query.
        If voice is True, return a voice-friendly string to
        be spoken to the user. If auto_uppercase is True,
        the string probably came from voice input and we
        need to intelligently guess which words in the query
        should be upper case (to the extent that it matters).
        The q parameter can either be a single query string
        or an iterable of strings that will be processed in
        order until a successful one is found. """

    with SessionContext(commit=True) as session:

        result = None

        # Try to parse and process as a query
        if isinstance(q, str):
            # This is a single string
            it = iter([q])
        else:
            # This should be an iterable of strings,
            # in decreasing priority order
            it = iter(q)
        # Iterate through the submitted query strings,
        # attempting to execute them in turn until we find
        # one that works (or we're stumped)
        for qtext in it:
            query = Query(session, qtext, voice, auto_uppercase, location)
            result = query.execute()
            if result["valid"] and "error" not in result:
                # Successful: our job is done
                return result

        return result or dict(valid=False, error="E_NO_RESULT")
