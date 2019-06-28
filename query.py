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

from settings import Settings

from db import SessionContext

from tree import Tree
from reynir import TOK, tokenize, correct_spaces
from reynir.fastparser import (
    Fast_Parser,
    ParseForestDumper,
    ParseError,
)
from reynir.binparser import BIN_Grammar
from reynir.reducer import Reducer
from nertokenizer import recognize_entities
from images import get_image_url
from processor import modules_in_dir


# The grammar root nonterminal for queries; see Reynir.grammar
_QUERY_ROOT = "QueryRoot"


class QueryGrammar(BIN_Grammar):

    """ A subclass of BIN_Grammar that causes conditional sections in the
        Reynir.grammar file, demarcated using
        $if(include_queries)...$endif(include_queries),
        to be included in the grammar as it is read and parsed """

    def __init__(self):
        super().__init__()
        # Enable the 'include_queries' condition
        self.set_conditions({"include_queries"})


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

    def __init__(self):
        super().__init__(verbose=False, root=_QUERY_ROOT)


class Query:

    """ A Query is initialized by parsing a query string using QueryRoot as the
        grammar root nonterminal. The Query can then be executed by processing
        the best parse tree using the nonterminal handlers given above, returning a
        result object if successful. """

    _parser = None
    _processors = None

    def __init__(self, session, query, voice, auto_uppercase):
        self._session = session
        self._query = query
        self._voice = voice
        self._auto_uppercase = auto_uppercase
        self._error = None
        self._answer = None
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
                print(
                    "Error importing query processor module {0}: {1}"
                    .format(modname, e)
                )
        cls._processors = procs
        # Initialize a singleton parser instance for queries,
        # with the nonterminal 'QueryRoot' as the grammar root
        cls._parser = QueryParser()

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
                    # ParseForestPrinter.print_forest(forest)

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

        # if Settings.DEBUG:
        #     # Log the query string as seen by the parser
        #     print("Query is: '{0}'".format(actual_q))

        parse_result, trees = Query._parse(toklist)

        if not trees:
            # No parse at all
            self.set_error("E_NO_TREES")
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
        # print("Query tree:\n{0}".format(tree_string))
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
            print("handle_tree is {0}".format(handle_tree))
            if handle_tree:
                # Process the tree, which has only one sentence
                self._tree.process(self._session, processor, query=self)
                if self._answer and self._error is None:
                    return True
        return False

    @property
    def query(self):
        return self._query
    
    @property
    def query_lower(self):
        return self._query.lower()
    
    def set_qtype(self, qtype):
        """ Set the query type ('Person', 'Title', 'Company', 'Entity'...) """
        self._qtype = qtype

    def set_answer(self, answer, voice_answer=None):
        """ Set the answer to the query """
        self._answer = answer
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

    def answer(self):
        """ Return the query answer """
        return self._answer

    def voice_answer(self):
        """ Return a voice answer, if any """
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
        result = dict(q=self.query)
        # First, try to handle this from plain text, without parsing:
        # shortcut to a successful, plain response
        if not self.execute_from_plain_text():
            if not self.parse(result):
                # if Settings.DEBUG:
                #     print("Unable to parse query, error {0}".format(q.error()))
                result["error"] = self.error()
                result["valid"] = False
                return result
            if not self.execute_from_tree():
                # This is a query, but its execution failed for some reason:
                # return the error
                # if Settings.DEBUG:
                #     print("Unable to execute query, error {0}".format(q.error()))
                result["error"] = self.error()
                result["valid"] = True
                return result
        # Successful query: return the answer in response
        result["response"] = self._answer
        if self._voice and self._voice_answer:
            result["voice"] = self._voice_answer
        # ...and the query type, as a string ('Person', 'Entity', 'Title' etc.)
        result["qtype"] = qt = self.qtype()
        # ...and the key used to retrieve the answer, if any
        result["key"] = self.key()
        if qt == "Person":
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
        return result


def process_query(q, voice, auto_uppercase):
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
            # in priority order
            it = iter(q)
        # Iterate through the submitted query strings,
        # attempting to execute them in turn until we find
        # one that works (or we're stumped)
        for qtext in it:
            query = Query(session, qtext, voice, auto_uppercase)
            result = query.execute()
            if result["valid"] and "error" not in result:
                # Successful: our job is done
                return result

        return result or dict(valid=False, error="E_NO_RESULT")
