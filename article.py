"""
    Reynir: Natural language processing for Icelandic

    Article class

    Copyright (c) 2016 Vilhjalmur Thorsteinsson
    All rights reserved
    See the accompanying README.md file for further licensing and copyright information.

    This module contains a class modeling an article originating from a scraped web page.

"""

import json
import uuid
from datetime import datetime
from collections import OrderedDict, defaultdict, namedtuple

from settings import Settings, NoIndexWords
from scraperdb import Article as ArticleRow, SessionContext, Word, DataError
from fetcher import Fetcher
from tokenizer import TOK
from fastparser import Fast_Parser, ParseError, ParseForestNavigator, ParseForestDumper
from incparser import IncrementalParser


WordTuple = namedtuple("WordTuple", ["stem", "cat"])

# The word categories that are indexed in the words table
_CATEGORIES_TO_INDEX = frozenset((
    "kk", "kvk", "hk", "person_kk", "person_kvk", "entity",
    "lo", "so"
))

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
    def reload_parser(cls):
        """ Force reload of a fresh parser instance """
        cls._parser = None
        cls._init_class()

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
        self._indexed = None
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
        self._words = None # The individual word stems, in a dictionary

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
        a._indexed = ar.indexed
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
    def _dump_tokens(tokens, tree, words, error_index = None):

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

            This function has the side effect of filling in the words dictionary
            with (stem, cat) keys and occurrence counts.

        """

        # Map tokens to associated terminals, if any
        tmap = Article._terminal_map(tree) # tmap is an empty dict if there's no parse tree
        dump = []
        for ix, t in enumerate(tokens):
            # We have already cut away paragraph and sentence markers (P_BEGIN/P_END/S_BEGIN/S_END)
            d = dict(x = t.txt)
            terminal = None
            wt = None
            if ix in tmap:
                # There is a token-terminal match
                if t.kind == TOK.PUNCTUATION:
                    if t.txt == "-":
                        # Hyphen: check whether it is matching an em or en-dash terminal
                        terminal, _ = tmap[ix]
                        if terminal.cat == "em":
                            d["x"] = "—" # Substitute em dash (will be displayed with surrounding space)
                        elif terminal.cat == "en":
                            d["x"] = "–" # Substitute en dash
                else:
                    # Annotate with terminal name and BÍN meaning (no need to do this for punctuation)
                    terminal, meaning = tmap[ix]
                    d["t"] = terminal.name
                    if meaning is not None:
                        if terminal.first == "fs":
                            # Special case for prepositions since they're really
                            # resolved from the preposition list in Main.conf, not from BÍN
                            m = (meaning.ordmynd, "fs", "alm", terminal.variant(0).upper())
                        else:
                            m = (meaning.stofn, meaning.ordfl, meaning.fl, meaning.beyging)
                        d["m"] = m
                        # Note the word stem and category
                        wt = WordTuple(stem = m[0].replace("-", ""), cat = m[1])
                    elif t.kind == TOK.ENTITY:
                        wt = WordTuple(stem = t.txt, cat = "entity")
            if t.kind != TOK.WORD:
                # Optimize by only storing the k field for non-word tokens
                d["k"] = t.kind
            if t.val is not None and t.kind not in { TOK.WORD, TOK.ENTITY, TOK.PUNCTUATION }:
                # For tokens except words, entities and punctuation, include the val field
                if t.kind == TOK.PERSON:
                    d["v"] = t.val[0][0] # Include only the name of the person in nominal form
                    # Hack to make sure that the gender information is communicated in
                    # the terminal name (in some cases the terminal only contains the case)
                    gender = t.val[0][1]
                    if terminal:
                        if not terminal.name.endswith("_" + gender):
                            d["t"] = terminal.name + "_" + gender
                    else:
                        # There is no terminal: cop out by adding a separate gender field
                        d["g"] = gender
                    wt = WordTuple(stem = t.val[0][0], cat = "person_" + gender)
                else:
                    d["v"] = t.val
            if ix == error_index:
                # Mark the error token, if present
                d["err"] = 1
            dump.append(d)
            if words is not None and wt is not None:
                # Add the (stem, cat) combination to the words dictionary
                words[wt] += 1
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

    def _store_words(self, session):
        """ Store word stems """
        assert session is not None
        # Delete previously stored words for this article
        session.execute(Word.table().delete().where(Word.article_id == self._uuid))
        # Index the words by storing them in the words table
        for word, cnt in self._words.items():
            if word.cat not in _CATEGORIES_TO_INDEX:
                # We do not index closed word categories and non-distinctive constructs
                continue
            if (word.stem, word.cat) in NoIndexWords.SET:
                # Specifically excluded from indexing in Reynir.conf (Main.conf)
                continue
            # Interesting word: let's index it
            w = Word(
                article_id = self._uuid,
                stem = word.stem,
                cat = word.cat,
                cnt = cnt
            )
            session.add(w)

    def _parse(self, enclosing_session = None, verbose = False):
        """ Parse the article content to yield parse trees and annotated token list """
        with SessionContext(enclosing_session) as session:

            # Convert the content soup to a token iterable (generator)
            toklist = Fetcher.tokenize_html(self._url, self._html, session)

            # Dict of parse trees in string dump format,
            # stored by sentence index (1-based)
            trees = OrderedDict()

            # List of paragraphs containing a list of sentences containing token lists
            # for sentences in string dump format (1-based paragraph and sentence indices)
            pgs = []

            # Word stem dictionary, indexed by (stem, cat)
            words = defaultdict(int)

            bp = self.get_parser()
            ip = IncrementalParser(bp, toklist, verbose = verbose)
            num_sent = 0

            for p in ip.paragraphs():

                pgs.append([])

                for sent in p.sentences():

                    num_sent += 1

                    if sent.parse():
                        # Obtain a text representation of the parse tree
                        trees[num_sent] = ParseForestDumper.dump_forest(sent.tree)
                        pgs[-1].append(Article._dump_tokens(sent.tokens, sent.tree, words))
                    else:
                        # Error or no parse: add an error index entry for this sentence
                        eix = sent.err_index
                        trees[num_sent] = "E{0}".format(eix)
                        pgs[-1].append(Article._dump_tokens(sent.tokens, None, None, eix))

            parse_time = ip.parse_time

            self._parsed = datetime.utcnow()
            self._parser_version = bp.version
            self._num_tokens = ip.num_tokens
            self._num_sentences = ip.num_sentences
            self._num_parsed = ip.num_parsed
            self._ambiguity = ip.ambiguity

            # Make one big JSON string for the paragraphs, sentences and tokens
            self._raw_tokens = pgs
            self._tokens = json.dumps(pgs, separators = (',', ':'), ensure_ascii = False)
            self._words = words
            # self._tokens = "[" + ",\n".join("[" + ",\n".join(sent for sent in p) + "]" for p in pgs) + "]"
            # Create a tree representation string out of all the accumulated parse trees
            self._tree = "".join("S{0}\n{1}\n".format(key, val) for key, val in trees.items())


    def store(self, enclosing_session = None):
        """ Store an article in the database, inserting it or updating """
        with SessionContext(enclosing_session, commit = True) as session:
            if self._uuid is None:
                # Insert a new row
                self._uuid = str(uuid.uuid1())
                ar = ArticleRow(
                    id = self._uuid,
                    url = self._url,
                    root_id = self._root_id,
                    heading = self._heading,
                    author = self._author,
                    timestamp = self._timestamp,
                    authority = self._authority,
                    scraped = self._scraped,
                    parsed = self._parsed,
                    processed = self._processed,
                    indexed = self._indexed,
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
                if self._words:
                    # Store the word stems occurring in the article
                    self._store_words(session)
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
            ar.indexed = self._indexed
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
            if self._words is not None:
                # If the article has been parsed, update the index of word stems
                # (This may cause all stems for the article to be deleted, if
                # there are no successfully parsed sentences in the article)
                self._store_words(session)
            return True

    def prepare(self, enclosing_session = None, verbose = False, reload_parser = False):
        """ Prepare the article for display. If it's not already tokenized and parsed, do it now. """
        with SessionContext(enclosing_session, commit = True) as session:
            if self._tree is None or self._tokens is None:
                if reload_parser:
                    # We need a parse: Make sure we're using the newest grammar
                    self.reload_parser()
                self._parse(session, verbose = verbose)
                if self._tree is not None or self._tokens is not None:
                    # Store the updated article in the database
                    self.store(session)

    def parse(self, enclosing_session = None, verbose = False):
        """ Force a parse of the article """
        with SessionContext(enclosing_session, commit = True) as session:
            self._parse(session, verbose = verbose)
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

