"""
    Reynir: Natural language processing for Icelandic

    Article class

    Copyright (c) 2016 Vilhjalmur Thorsteinsson
    All rights reserved
    See the accompanying README.md file for further licensing and copyright information.

    This module contains a class modeling an article originating from a scraped web page.

"""

import time
import json
from datetime import datetime
from collections import OrderedDict

from settings import Settings
from scraperdb import Article as ArticleRow, SessionContext, Failure, DataError
from fetcher import Fetcher
from tokenizer import TOK, paragraphs
from fastparser import Fast_Parser, ParseError, ParseForestNavigator, ParseForestDumper
from reducer import Reducer


class Article:

    _parser = None

    @classmethod
    def _init_class(cls):
        """ Initialize class attributes """
        if cls._parser is None:
            cls._parser = Fast_Parser(verbose = False) # Don't emit diagnostic messages

    @classmethod
    def cleanup(cls):
        if cls._parser is not None:
            cls._parser.cleanup()
            cls._parser = None

    @classmethod
    def get_parser(cls):
        if cls._parser is None:
            cls._init_class()
        return cls._parser

    @classmethod
    def parser_version(cls):
        """ Return the current grammar timestamp + parser version """
        cls._init_class()
        return cls._parser.version


    def __init__(self, uuid = None, url = None):
        self._uuid = uuid
        self._url = url
        self._heading = ""
        self._author = ""
        self._timestamp = datetime.utcnow()
        self._authority = 1.0
        self._scraped = None
        self._parsed = None
        self._processed = None
        self._scr_module = None
        self._scr_class = None
        self._scr_version = None
        self._parser_version = None
        self._num_tokens = None
        self._num_sentences = 0
        self._num_parsed = 0
        self._ambiguity = 1.0
        self._html = None
        self._tree = None
        self._root_id = None
        self._root_domain = None
        self._helper = None
        self._tokens = None # JSON string
        self._raw_tokens = None # The tokens themselves
        self._failures = None

    @classmethod
    def _init_from_row(cls, ar):
        """ Initialize a fresh Article instance from a database row object """
        a = cls(uuid = ar.id)
        a._url = ar.url
        a._heading = ar.heading
        a._author = ar.author
        a._timestamp = ar.timestamp
        a._authority = ar.authority
        a._scraped = ar.scraped
        a._parsed = ar.parsed
        a._processed = ar.processed
        a._scr_module = ar.scr_module
        a._scr_class = ar.scr_class
        a._scr_version = ar.scr_version
        a._parser_version = ar.parser_version
        assert a._num_tokens is None
        a._num_sentences = ar.num_sentences
        a._num_parsed = ar.num_parsed
        a._ambiguity = ar.ambiguity
        a._html = ar.html
        a._tree = ar.tree
        a._tokens = ar.tokens
        assert a._raw_tokens is None
        a._root_id = ar.root_id
        a._root_domain = ar.root.domain
        return a

    @classmethod
    def _init_from_scrape(cls, url, enclosing_session = None):
        """ Scrape an article from its URL """
        if url is None:
            return None
        a = cls(url = url)
        with SessionContext(enclosing_session) as session:
            # Obtain a helper corresponding to the URL
            html, metadata, helper = Fetcher.fetch_url_html(url, session)
            if html is None:
                return a
            a._html = html
            if metadata is not None:
                a._heading = metadata.heading
                a._author = metadata.author
                a._timestamp = metadata.timestamp
                a._authority = metadata.authority
            a._scraped = datetime.utcnow()
            if helper is not None:
                a._scr_module = helper.scr_module
                a._scr_class = helper.scr_class
                a._scr_version = helper.scr_version
                a._root_id = helper.root_id
                a._root_domain = helper.domain
            return a

    @classmethod
    def load_from_url(cls, url, enclosing_session = None):
        """ Load or scrape an article, given its URL """
        with SessionContext(enclosing_session) as session:
            ar = session.query(ArticleRow).filter(ArticleRow.url == url).one_or_none()
            if ar is not None:
                return cls._init_from_row(ar)
            # Not found in database: attempt to fetch
            return cls._init_from_scrape(url, session)

    @classmethod
    def scrape_from_url(cls, url, enclosing_session = None):
        """ Force fetch of an article, given its URL """
        with SessionContext(enclosing_session) as session:
            ar = session.query(ArticleRow).filter(ArticleRow.url == url).one_or_none()
            a = cls._init_from_scrape(url, session)
            if a is not None and ar is not None:
                # This article already existed in the database, so note its UUID
                a._uuid = ar.id
            return a

    @classmethod
    def load_from_uuid(cls, uuid, enclosing_session = None):
        """ Load an article, given its UUID """
        with SessionContext(enclosing_session) as session:
            try:
                ar = session.query(ArticleRow).filter(ArticleRow.id == uuid).one_or_none()
            except DataError:
                # Probably wrong UUID format
                ar = None
            return None if ar is None else cls._init_from_row(ar)

    @staticmethod
    def _terminal_map(tree):
        """ Return a dict containing a map from original token indices to matched terminals """
        tmap = { }

        class Annotator(ParseForestNavigator):

            """ Subclass to navigate a parse forest and annotate the
                original token list with the corresponding terminal
                matches """

            def _visit_token(self, level, node):
                """ At token node """
                ix = node.token.index # Index into original sentence
                assert ix not in tmap
                meaning = node.token.match_with_meaning(node.terminal)
                tmap[ix] = (node.terminal, None if isinstance(meaning, bool) else meaning) # Map from original token to matched terminal
                return None

        if tree is not None:
            Annotator().go(tree)
        return tmap

    @staticmethod
    def _dump_tokens(sent, tree, error_index = None):
        """ Generate a string (JSON) representation of the tokens in the sentence.

            The JSON token dict contents are as follows:

                t.x is original token text.
                t.k is the token kind (TOK.xxx). If omitted, the kind is TOK.WORD.
                t.t is the name of the matching terminal, if any.
                t.m is the BÍN meaning of the token, if any, as a tuple as follows:
                    t.m[0] is the lemma (stofn)
                    t.m[1] is the word category (ordfl)
                    t.m[2] is the word subcategory (fl)
                    t.m[3] is the word meaning/declination (beyging)
                t.v contains auxiliary information, depending on the token kind
                t.err is 1 if the token is an error token
        """
        # Map tokens to associated terminals, if any
        tmap = Article._terminal_map(tree) # tmap is an empty dict if there's no parse tree
        dump = []
        for ix, t in enumerate(sent):
            # We have already cut away paragraph and sentence markers (P_BEGIN/P_END/S_BEGIN/S_END)
            d = dict(x = t.txt)
            if t.kind != TOK.PUNCTUATION and ix in tmap:
                # Annotate with terminal name and BÍN meaning (no need to do this for punctuation)
                terminal, meaning = tmap[ix]
                d["t"] = terminal.name
                if meaning is not None:
                    if terminal.first == "fs":
                        # Special case for prepositions since they're really
                        # resolved from the preposition list in Main.conf, not from BÍN
                        d["m"] = (meaning.ordmynd, "fs", "alm", terminal.variant(0).upper())
                    else:
                        d["m"] = (meaning.stofn, meaning.ordfl, meaning.fl, meaning.beyging)
            if t.kind != TOK.WORD:
                # Optimize by only storing the k field for non-word tokens
                d["k"] = t.kind
            if t.val is not None and t.kind not in { TOK.WORD, TOK.ENTITY, TOK.PUNCTUATION }:
                # For tokens except words, entities and punctuation, include the val field
                if t.kind == TOK.PERSON:
                    d["v"] = t.val[0][0] # Include only the name of the person in nominal form
                else:
                    d["v"] = t.val
            if ix == error_index:
                # Mark the error token, if present
                d["err"] = 1
            dump.append(d)
        return dump

    def person_names(self):
        """ A generator yielding all person names in an article token stream """
        if self._raw_tokens is None and self._tokens:
            # Lazy generation of the raw tokens from the JSON rep
            self._raw_tokens = json.loads(self._tokens)
        if self._raw_tokens:
            for p in self._raw_tokens:
                for sent in p:
                    for t in sent:
                        if t.get("k") == TOK.PERSON:
                            # The full name of the person is in the v field
                            yield t["v"]

    def entity_names(self):
        """ A generator for entity names from an article token stream """
        if self._raw_tokens is None and self._tokens:
            # Lazy generation of the raw tokens from the JSON rep
            self._raw_tokens = json.loads(self._tokens)
        if self._raw_tokens:
            for p in self._raw_tokens:
                for sent in p:
                    for t in sent:
                        if t.get("k") == TOK.ENTITY:
                            # The entity name
                            yield t["x"]

    def _store_failures(self, session):
        """ Store sentences that fail to parse """
        assert session is not None
        # Delete previously stored failures for this article
        session.execute(Failure.table().delete().where(Failure.article_url == self._url))
        # Add the failed sentences to the failure table
        for sentence in self._failures:
            f = Failure(
                article_url = self._url,
                sentence = sentence,
                cause = None, # Unknown cause so far
                comment = None, # No comment so far
                timestamp = datetime.utcnow())
            session.add(f)

    def _parse(self, enclosing_session = None):
        """ Parse the article content to yield parse trees and annotated token list """
        with SessionContext(enclosing_session) as session:

            # Convert the content soup to a token iterable (generator)
            toklist = Fetcher.tokenize_html(self._url, self._html, session)

            # Count sentences and paragraphs
            num_sent = 0
            num_parsed_sent = 0
            num_paragraphs = 0
            num_tokens = 0
            total_ambig = 0.0
            total_tokens = 0

            # Dict of parse trees in string dump format,
            # stored by sentence index (1-based)
            trees = OrderedDict()

            # List of paragraphs containing a list of sentences containing token lists
            # for sentences in string dump format (1-based paragraph and sentence indices)
            pgs = []

            # List of sentences that fail to parse
            failures = []

            start_time = time.time()
            bp = self.get_parser()
            rdc = Reducer(bp.grammar)

            for p in paragraphs(toklist):

                pgs.append([])

                for _, sent in p:

                    slen = len(sent)
                    # Parse the accumulated sentence
                    num_sent += 1
                    num_tokens += slen
                    err_index = None
                    num = 0
                    try:
                        # Parse the sentence
                        forest = bp.go(sent)
                        if forest is not None:
                            num = Fast_Parser.num_combinations(forest)
                            if num > 0:
                                # Reduce the resulting forest
                                forest = rdc.go(forest)
                    except ParseError as e:
                        forest = None
                        # Obtain the index of the offending token
                        err_index = e.token_index
                    if Settings.DEBUG:
                        print("Parsed sentence of length {0} with {1} combinations{2}"
                            .format(slen, num,
                                ("\n   " + (" ".join(tok[1] for tok in sent)) if num >= 100 else "")))
                    if num > 0:
                        num_parsed_sent += 1
                        # Calculate the 'ambiguity factor'
                        ambig_factor = num ** (1 / slen)
                        # Do a weighted average on sentence length
                        total_ambig += ambig_factor * slen
                        total_tokens += slen
                        # Obtain a text representation of the parse tree
                        trees[num_sent] = ParseForestDumper.dump_forest(forest)
                        pgs[-1].append(Article._dump_tokens(sent, forest))
                    else:
                        # Error or no parse: add an error index entry for this sentence
                        eix = slen - 1 if err_index is None else err_index
                        trees[num_sent] = "E{0}".format(eix)
                        # Add the failing sentence to the list of failures
                        failures.append(" ".join(t.txt for t in sent))
                        pgs[-1].append(Article._dump_tokens(sent, None, eix))

            parse_time = time.time() - start_time

            self._parsed = datetime.utcnow()
            self._parser_version = bp.version
            self._num_tokens = num_tokens
            self._num_sentences = num_sent
            self._num_parsed = num_parsed_sent
            self._ambiguity = (total_ambig / total_tokens) if total_tokens > 0 else 1.0

            # Make one big JSON string for the paragraphs, sentences and tokens
            self._raw_tokens = pgs
            self._tokens = json.dumps(pgs, separators = (',', ':'), ensure_ascii = False)
            # self._tokens = "[" + ",\n".join("[" + ",\n".join(sent for sent in p) + "]" for p in pgs) + "]"
            # Store the failing sentences
            self._failures = failures
            # Create a tree representation string out of all the accumulated parse trees
            self._tree = "".join("S{0}\n{1}\n".format(key, val) for key, val in trees.items())


    def store(self, enclosing_session = None):
        """ Store an article in the database, inserting it or updating """
        with SessionContext(enclosing_session, commit = True) as session:
            if self._uuid is None:
                # Insert a new row
                ar = ArticleRow(
                    # UUID is auto-generated
                    url = self._url,
                    root_id = self._root_id,
                    heading = self._heading,
                    author = self._author,
                    timestamp = self._timestamp,
                    authority = self._authority,
                    scraped = self._scraped,
                    parsed = self._parsed,
                    processed = self._processed,
                    scr_module = self._scr_module,
                    scr_class = self._scr_class,
                    scr_version = self._scr_version,
                    parser_version = self._parser_version,
                    num_sentences = self._num_sentences,
                    num_parsed = self._num_parsed,
                    ambiguity = self._ambiguity,
                    html = self._html,
                    tree = self._tree,
                    tokens = self._tokens
                )
                session.add(ar)
                if self._failures is not None:
                    # After a parse without errors, self._failures is an empty list, not None
                    self._store_failures(session)
                return True

            # Update an already existing row by UUID
            ar = session.query(ArticleRow).filter(ArticleRow.id == self._uuid).one_or_none()
            if ar is None:
                # UUID not found: something is wrong here...
                return False

            # Update the columns
            # UUID is immutable
            ar.url = self._url
            ar.root_id = self._root_id
            ar.heading = self._heading
            ar.author = self._author
            ar.timestamp = self._timestamp
            ar.authority = self._authority
            ar.scraped = self._scraped
            ar.parsed = self._parsed
            ar.processed = self._processed
            ar.scr_module = self._scr_module
            ar.scr_class = self._scr_class
            ar.scr_version = self._scr_version
            ar.parser_version = self._parser_version
            ar.num_sentences = self._num_sentences
            ar.num_parsed = self._num_parsed
            ar.ambiguity = self._ambiguity
            ar.html = self._html
            ar.tree = self._tree
            ar.tokens = self._tokens
            if self._failures is not None:
                # If the article has been parsed, update the list of failures
                self._store_failures(session)
            return True

    def prepare(self, enclosing_session = None):
        """ Prepare the article for display. If it's not already tokenized and parsed, do it now. """
        with SessionContext(enclosing_session, commit = True) as session:
            if self._tree is None or self._tokens is None:
                self._parse(session)
                if self._tree is not None or self._tokens is not None:
                    # Store the updated article in the database
                    self.store(session)

    def parse(self, enclosing_session = None):
        """ Force a parse of the article """
        with SessionContext(enclosing_session, commit = True) as session:
            self._parse(session)
            if self._tree is not None or self._tokens is not None:
                # Store the updated article in the database
                self.store(session)


    @property
    def url(self):
        return self._url

    @property
    def uuid(self):
        return self._uuid

    @property
    def heading(self):
        return self._heading

    @property
    def author(self):
        return self._author

    @property
    def timestamp(self):
        return self._timestamp

    @property
    def num_sentences(self):
        return self._num_sentences

    @property
    def num_parsed(self):
        return self._num_parsed

    @property
    def ambiguity(self):
        return self._ambiguity

    @property
    def root_domain(self):
        return self._root_domain

    @property
    def html(self):
        return self._html

    @property
    def tree(self):
        return self._tree

    @property
    def tokens(self):
        return self._tokens

    @property
    def num_tokens(self):
        """ Count the tokens in the article and cache the result """
        if self._num_tokens is None:
            if self._raw_tokens is None and self._tokens:
                self._raw_tokens = json.loads(self._tokens)
            cnt = 0
            if self._raw_tokens:
                for p in self._raw_tokens:
                    for sent in p:
                        cnt += len(sent)
            self._num_tokens = cnt
        return self._num_tokens

