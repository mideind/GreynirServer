"""

    Greynir: Natural language processing for Icelandic

    Query module

    Copyright (C) 2020 Miðeind ehf.
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

from typing import Optional, Tuple, List, Dict, Callable, Any

from types import ModuleType

import importlib
import logging
from datetime import datetime, timedelta
import json
import re
import random
from collections import defaultdict

from settings import Settings

from db import SessionContext, desc
from db.models import Query as QueryRow

from tree import Tree
from reynir import TOK, Tok, tokenize, correct_spaces
from reynir.fastparser import Fast_Parser, ParseForestDumper, ParseError, ffi
from reynir.binparser import BIN_Grammar, GrammarError
from reynir.reducer import Reducer
from reynir.bindb import BIN_Db
from nertokenizer import recognize_entities
from images import get_image_url
from processor import modules_in_dir


# Latitude, longitude
LocationType = Tuple[float, float]

# The grammar root nonterminal for queries; see Reynir.grammar
_QUERY_ROOT = "QueryRoot"


# A fixed preamble that is inserted before the concatenated query grammar fragments
_GRAMMAR_PREAMBLE = """

QueryRoot →
    Query

# Mark the QueryRoot nonterminal as a root in the grammar
$root(QueryRoot)

"""


def beautify_query(query):
    """ Return a minimally beautified version of the given query string """
    # Make sure the query starts with an uppercase letter
    bq = (query[0].upper() + query[1:]) if query else ""
    # Add a question mark if no other ending punctuation is present
    if not any(bq.endswith(s) for s in ("?", ".", "!")):
        bq += "?"
    return bq


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
            # Note that if Settings.DEBUG is True, we always write a fresh
            # binary grammar file, regardless of file timestamps. This helps
            # in query development, as query grammar fragment strings may change
            # without any .grammar source file change (which is the default
            # trigger for generating new binary grammar files).
            return self.read_from_generator(
                fname,
                grammar_generator(),
                verbose,
                binary_fname,
                force_new_binary=Settings.DEBUG,
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
    _c_grammar = ffi.NULL
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


_IGNORED_QUERY_PREFIXES = ("embla", "hæ embla", "hey embla", "sæl embla")
_IGNORED_PREFIX_RE = r"^({0})\s*".format("|".join(_IGNORED_QUERY_PREFIXES))


class Query:

    """ A Query is initialized by parsing a query string using QueryRoot as the
        grammar root nonterminal. The Query can then be executed by processing
        the best parse tree using the nonterminal handlers given above, returning a
        result object if successful. """

    _parser = None  # type: Optional[QueryParser]
    _processors = []  # type: List[ModuleType]
    _help_texts = dict()  # type: Dict[str, List[Callable]]

    def __init__(
        self, session,
        query: str, voice: str,
        auto_uppercase: bool,
        location: Optional[LocationType],
        client_id: str
    ) -> None:

        q = self._preprocess_query_string(query)
        self._session = session
        self._query = q or ""
        self._location = location
        # Prepare a "beautified query" string that can be
        # shown in a client user interface. By default, this
        # starts with an uppercase letter and ends with a
        # question mark, but this can be modified during the
        # processing of the query.
        self.set_beautified_query(beautify_query(q))
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
        self._tree = None  # type: Optional[Tree]
        self._qtype = None
        self._key = None
        self._toklist = None
        # Expiration timestamp, if any
        self._expires = None
        # URL assocated with query, can be set by query response handler
        # and subsequently provided to the remote client
        self._url = None
        # Command returned by query
        self._command = None
        # Client id, if known
        self._client_id = client_id
        # Source of answer to query
        self._source = None
        # Query context, which is None until fetched via self.fetch_context()
        # This should be a dict that can be represented in JSON
        self._context = None

    def _preprocess_query_string(self, q):
        """ Preprocess the query string prior to further analysis """
        if not q:
            return q
        qf = re.sub(_IGNORED_PREFIX_RE, "", q, flags=re.IGNORECASE)
        # If stripping the prefixes results in an empty query,
        # just return original query string unmodified.
        return qf or q

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
                    "Error importing query processor module {0}: {1}".format(modname, e)
                )
        cls._processors = procs

        # Obtain query grammar fragments from those processors
        # that handle parse trees. Also collect topic lemmas that
        # can be used to provide context-sensitive help texts
        # when queries cannot be parsed.
        grammar_fragments = []
        help_texts = defaultdict(list)
        for processor in procs:
            handle_tree = getattr(processor, "HANDLE_TREE", None)
            if handle_tree:
                # Check whether this processor supplies
                # a query grammar fragment
                fragment = getattr(processor, "GRAMMAR", None)
                if fragment and isinstance(fragment, str):
                    # Looks legit: add it to our list
                    grammar_fragments.append(fragment)
            # Collect topic lemmas and corresponding help text functions
            topic_lemmas = getattr(processor, "TOPIC_LEMMAS", None)
            if topic_lemmas:
                help_text_func = getattr(processor, "help_text", None)
                # If topic lemmas are given, a help_text function
                # should also be present
                assert help_text_func is not None
                if help_text_func is not None:
                    for lemma in topic_lemmas:
                        help_texts[lemma].append(help_text_func)
        cls._help_texts = help_texts

        # Coalesce the grammar additions from the fragments
        grammar_additions = "\n".join(grammar_fragments)
        # Initialize a singleton parser instance for queries,
        # with the nonterminal 'QueryRoot' as the grammar root
        cls._parser = QueryParser(grammar_additions)

    @staticmethod
    def _parse(toklist):
        """ Parse a token list as a query """
        bp = Query._parser
        assert bp is not None
        num_sent = 0
        num_parsed_sent = 0
        rdc = Reducer(bp.grammar)
        trees = dict()
        sent = []  # type: List[Tok]

        for t in toklist:
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
        """ Parse the query from its string, returning True if valid """
        self._tree = None  # Erase previous tree, if any
        self._error = None  # Erase previous error, if any
        self._qtype = None  # Erase previous query type, if any
        self._key = None
        self._toklist = None

        q = self._query.strip()
        if not q:
            self.set_error("E_EMPTY_QUERY")
            return False

        toklist = tokenize(q, auto_uppercase=self._auto_uppercase and q.islower())
        toklist = list(toklist)
        # The following seems not to be needed and may complicate things
        # toklist = list(recognize_entities(toklist, enclosing_session=self._session))

        actual_q = correct_spaces(" ".join(t.txt for t in toklist if t.txt))
        if actual_q:
            actual_q = actual_q[0].upper() + actual_q[1:]
            if not any(actual_q.endswith(s) for s in ("?", ".", "!")):
                actual_q += "?"

        # Update the beautified query string, as the actual_q string
        # probably has more correct capitalization
        self.set_beautified_query(actual_q)

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
        if Settings.DEBUG:
            print(tree_string)
        self._tree = Tree()
        self._tree.load(tree_string)
        # Store the token list
        self._toklist = toklist
        return True

    def execute_from_plain_text(self):
        """ Attempt to execute a plain text query, without having to parse it """
        if not self._query:
            return False
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

    def last_answer(self, *, within_minutes=5):
        """ Return the last answer given to this client, by default
            within the last 5 minutes (0=forever) """
        if not self._client_id:
            # Can't find the last answer if no client_id given
            return None
        # Find the newest non-error, no-repeat query result for this client
        q = (
            self._session.query(QueryRow.answer, QueryRow.voice)
            .filter(QueryRow.client_id == self._client_id)
            .filter(QueryRow.qtype != "Repeat")
            .filter(QueryRow.error == None)
        )
        if within_minutes > 0:
            # Apply a timestamp filter
            since = datetime.utcnow() - timedelta(minutes=within_minutes)
            q = q.filter(QueryRow.timestamp >= since)
        # Sort to get the newest query that fulfills the criteria
        last = q.order_by(desc(QueryRow.timestamp)).limit(1).one_or_none()
        return None if last is None else tuple(last)

    def fetch_context(self, *, within_minutes=10):
        """ Return the context from the last answer given to this client,
            by default within the last 10 minutes (0=forever) """
        if not self._client_id:
            # Can't find the last answer if no client_id given
            return None
        # Find the newest non-error, no-repeat query result for this client
        q = (
            self._session.query(QueryRow.context)
            .filter(QueryRow.client_id == self._client_id)
            .filter(QueryRow.qtype != "Repeat")
            .filter(QueryRow.error == None)
        )
        if within_minutes > 0:
            # Apply a timestamp filter
            since = datetime.utcnow() - timedelta(minutes=within_minutes)
            q = q.filter(QueryRow.timestamp >= since)
        # Sort to get the newest query that fulfills the criteria
        ctx = q.order_by(desc(QueryRow.timestamp)).limit(1).one_or_none()
        if ctx is None:
            return None
        # This function normally returns a dict that has been decoded from JSON
        return None if ctx is None else ctx[0]

    @property
    def query(self):
        return self._query

    @property
    def query_lower(self):
        return self._query.lower()

    @property
    def beautified_query(self):
        """ Return the query string that will be reflected back to the client """
        return self._beautified_query

    def set_beautified_query(self, q):
        """ Set the query string that will be reflected back to the client """
        self._beautified_query = (
            q.replace("embla", "Embla")
            .replace("miðeind", "Miðeind")
            .replace("Guðni Th ", "Guðni Th. ")  # By presidential request :)
        )

    def lowercase_beautified_query(self):
        """ If we know that no uppercase words occur in the query,
            except the initial capital, this function can be called
            to adjust the beautified query string accordingly. """
        self.set_beautified_query(self._beautified_query.capitalize())

    def query_is_command(self):
        """ Called from a query processor if the query is a command, not a question """
        # Put a period at the end of the beautified query text
        # instead of a question mark
        if self._beautified_query.endswith("?"):
            self._beautified_query = self._beautified_query[:-1] + "."

    @property
    def expires(self):
        """ Expiration time stamp for this query answer, if any """
        return self._expires

    def set_expires(self, ts):
        """ Set an expiration time stamp for this query answer """
        self._expires = ts

    @property
    def url(self):
        """ URL answer associated with this query """
        return self._url

    def set_url(self, u):
        """ Set the URL answer associated with this query """
        self._url = u

    @property
    def command(self):
        """ JavaScript command associated with this query """
        return self._command

    def set_command(self, c):
        """ Set the JavaScript command associated with this query """
        self._command = c

    @property
    def source(self):
        """ Return the source of the answer to this query """
        return self._source

    def set_source(self, s):
        """ Set the source for the answer to this query """
        self._source = s

    @property
    def location(self):
        """ The client location, if known, as a (lat, lon) tuple """
        return self._location

    @property
    def token_list(self):
        """ The original token list for the query """
        return self._toklist

    def set_qtype(self, qtype):
        """ Set the query type ('Person', 'Title', 'Company', 'Entity'...) """
        self._qtype = qtype

    def set_answer(self, response, answer, voice_answer=None):
        """ Set the answer to the query """
        # Detailed response (this is usually a dict)
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

    @property
    def is_voice(self):
        """ Return True if this is a voice query """
        return self._voice

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

    def set_context(self, ctx):
        """ Set a query context that will be stored and made available
            to the next query from the same client """
        self._context = ctx

    @property
    def context(self):
        """ Return the context that has been set by self.set_context() """
        return self._context

    @classmethod
    def try_to_help(cls, query, result):
        """ Attempt to help the user in the case of a failed query,
            based on lemmas in the query string """
        # Collect a set of lemmas that occur in the query string
        lemmas = set()
        with BIN_Db.get_db() as db:
            for token in query.lower().split():
                if token.isalpha():
                    m = db.meanings(token)
                    if not m:
                        # Try an uppercase version, just in case (pun intended)
                        m = db.meanings(token.capitalize())
                    if m:
                        lemmas |= set(mm.stofn.lower() for mm in m)
        # Collect a list of potential help text functions from the query modules
        help_text_funcs = []
        for lemma in lemmas:
            help_text_funcs.extend(
                [
                    (lemma, help_text_func)
                    for help_text_func in cls._help_texts.get(lemma, [])
                ]
            )
        if help_text_funcs:
            # Found at least one help text func matching a lemma in the query
            # Select a function at random and invoke it with the matched
            # lemma as a parameter
            lemma, help_text_func = random.choice(help_text_funcs)
            result["answer"] = result["voice"] = help_text_func(lemma)
            result["valid"] = True

    def execute(self) -> Dict[str, Any]:
        """ Check whether the parse tree is describes a query, and if so,
            execute the query, store the query answer in the result dictionary
            and return True """
        if Query._parser is None:
            Query.init_class()
        # By default, the result object contains the 'raw' query
        # string (the one returned from the speech-to-text processor)
        # as well as the beautified version of that string - which
        # usually starts with an uppercase letter and has a trailing
        # question mark (or other ending punctuation).
        result = dict(q_raw=self.query, q=self.beautified_query)
        # First, try to handle this from plain text, without parsing:
        # shortcut to a successful, plain response
        if not self.execute_from_plain_text():
            if not self.parse(result):
                # Unable to parse the query
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
        # Re-assign the beautified query string, in case the query processor modified it
        result["q"] = self.beautified_query
        # ...and the query type, as a string ('Person', 'Entity', 'Title' etc.)
        result["qtype"] = qt = self.qtype()
        # ...and the key used to retrieve the answer, if any
        result["key"] = self.key()
        # ...and a URL, if any has been set by the query processor
        if self.url:
            result["open_url"] = self.url
        # ...and a command, if any has been set
        if self.command:
            result["command"] = self.command
        # .. and the source, if set by query processor
        if self.source:
            result["source"] = self.source
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
            # Dump query results to the console
            def converter(o):
                """ Ensure that datetime is output in ISO format to JSON """
                if isinstance(o, datetime):
                    return o.isoformat()[0:16]
                return None

            print(
                "{0}".format(
                    json.dumps(result, indent=3, ensure_ascii=False, default=converter)
                )
            )
        return result


def _to_case(np, lookup_func, cast_func, meaning_filter_func):
    """ Return the noun phrase after casting it from nominative to accusative case """
    # Split the phrase into words and punctuation, respectively
    a = re.split(r"([\w]+)", np)
    seen_preposition = False
    # Enumerate through the 'tokens'
    for ix, w in enumerate(a):
        if not w:
            continue
        if w == "- ":
            # Something like 'Skeiða- og Hrunamannavegur'
            continue
        if w.strip() in {"-", "/"}:
            # Reset the seen_preposition flag after seeing a hyphen or slash
            seen_preposition = False
            continue
        if seen_preposition:
            continue
        if re.match(r"^[\w]+$", w):
            # This is a word: begin by looking up the word form
            _, mm = lookup_func(w)
            if not mm:
                # Unknown word form: leave it as-is
                continue
            if any(m.ordfl == "fs" for m in mm):
                # Probably a preposition: don't modify it, but
                # stop casting until the end of this phrase
                seen_preposition = True
                continue
            # Cast the word to the case we want
            a[ix] = cast_func(w, meaning_filter_func=meaning_filter_func)
    # Reassemble the list of words and punctuation
    return "".join(a)


def to_accusative(np, *, meaning_filter_func=None):
    """ Return the noun phrase after casting it from nominative to accusative case """
    with BIN_Db.get_db() as db:
        return _to_case(
            np,
            db.lookup_word,
            db.cast_to_accusative,
            meaning_filter_func=meaning_filter_func,
        )


def to_dative(np, *, meaning_filter_func=None):
    """ Return the noun phrase after casting it from nominative to dative case """
    with BIN_Db.get_db() as db:
        return _to_case(
            np,
            db.lookup_word,
            db.cast_to_dative,
            meaning_filter_func=meaning_filter_func,
        )


def process_query(
    q,
    voice,
    *,
    auto_uppercase=False,
    location=None,
    remote_addr=None,
    client_id=None,
    client_type=None,
    client_version=None,
    bypass_cache=False,
    private=False
):
    """ Process an incoming natural language query.
        If voice is True, return a voice-friendly string to
        be spoken to the user. If auto_uppercase is True,
        the string probably came from voice input and we
        need to intelligently guess which words in the query
        should be upper case (to the extent that it matters).
        The q parameter can either be a single query string
        or an iterable of strings that will be processed in
        order until a successful one is found. """

    now = datetime.utcnow()
    result = None
    client_id = client_id[:256] if client_id else None
    first_clean_q = None
    first_qtext = None

    with SessionContext(commit=True) as session:

        if isinstance(q, str):
            # This is a single string
            it = [q]
        else:
            # This should be an array of strings,
            # in decreasing priority order
            it = q

        # Iterate through the submitted query strings,
        # assuming that they are in decreasing order of probability,
        # attempting to execute them in turn until we find
        # one that works (or we're stumped)

        for qtext in it:

            qtext = qtext.strip()
            clean_q = qtext.rstrip("?")
            if first_clean_q is None:
                # Store the first (most likely) query string
                # that comes in from the speech-to-text processor,
                # since we want to return that one to the client
                # if no query string is matched - not the last
                # (least likely) query string
                first_clean_q = clean_q
                first_qtext = qtext
            # First, look in the query cache for the same question
            # (in lower case), having a not-expired answer
            cached_answer = None
            if voice and not bypass_cache:
                # Only use the cache for voice queries
                # (handling detailed responses in other queries
                # is too much for the cache)
                cached_answer = (
                    session.query(QueryRow)
                    .filter(QueryRow.question_lc == clean_q.lower())
                    .filter(QueryRow.expires >= now)
                    .order_by(desc(QueryRow.expires))
                    .limit(1)
                    .one_or_none()
                )
            if cached_answer is not None:
                # The same question is found in the cache and has not expired:
                # return the previous answer
                a = cached_answer
                result = dict(
                    valid=True,
                    q_raw=qtext,
                    q=a.bquestion,
                    answer=a.answer,
                    response=dict(answer=a.answer or ""),
                    voice=a.voice,
                    expires=a.expires,
                    qtype=a.qtype,
                    key=a.key,
                )
                # !!! TBD: Log the cached answer as well?
                return result
            query = Query(session, qtext, voice, auto_uppercase, location, client_id)
            result = query.execute()
            if result["valid"] and "error" not in result:
                # Successful: our job is done
                if not private:
                    # If not in private mode, log the result
                    try:
                        qrow = QueryRow(
                            timestamp=now,
                            interpretations=it,
                            question=clean_q,
                            # bquestion is the beautified query string
                            bquestion=result["q"],
                            answer=result["answer"],
                            voice=result.get("voice"),
                            # Only put an expiration on voice queries
                            expires=query.expires if voice else None,
                            qtype=result.get("qtype"),
                            key=result.get("key"),
                            latitude=location[0] if location else None,
                            longitude=location[1] if location else None,
                            # Client identifier
                            client_id=client_id,
                            client_type=client_type or None,
                            client_version=client_version or None,
                            # IP address
                            remote_addr=remote_addr or None,
                            # Context dict, stored as JSON, if present
                            # (set during query execution)
                            context=query.context,
                            # All other fields are set to NULL
                        )
                        session.add(qrow)
                    except Exception as e:
                        logging.error("Error logging query: {0}".format(e))
                return result

        # Failed to answer the query, i.e. no query processor
        # module was able to parse the query and provide an answer
        result = result or dict(valid=False, error="E_NO_RESULT")
        if first_clean_q:
            # Re-insert the query data from the first (most likely)
            # string returned from the speech-to-text processor,
            # replacing residual data that otherwise would be there
            # from the last (least likely) query string
            result["q_raw"] = first_qtext
            result["q"] = beautify_query(first_qtext)
            # Attempt to include a helpful response in the result
            Query.try_to_help(first_clean_q, result)

            # Log the failure
            qrow = QueryRow(
                timestamp=now,
                interpretations=it,
                question=first_clean_q,
                bquestion=result["q"],
                answer=result.get("answer"),
                voice=result.get("voice"),
                error=result.get("error"),
                latitude=location[0] if location else None,
                longitude=location[1] if location else None,
                # Client identifier
                client_id=client_id,
                client_type=client_type or None,
                client_version=client_version or None,
                # IP address
                remote_addr=remote_addr or None
                # All other fields are set to NULL
            )
            session.add(qrow)

        return result
