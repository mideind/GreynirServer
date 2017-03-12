#!/usr/bin/env python
"""

    Reynir: Natural language processing for Icelandic

    POS tagger module

    Copyright (C) 2017 Vilhjálmur Þorsteinsson

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


    This module implements a wrapper for Reynir's POS tagging
    functionality. It allows clients to simply and cleanly generate POS tags
    from plain text into a Python dict, which can then easily be converted to
    JSON if desired.

    Use as follows:

    from postagger import Tagger

    with Tagger().session() as tagger:
        for text in mytexts:
            d = tagger.tag(text)
            do_something_with(d["result"], d["stats"], d["register"])

    The session() context manager will automatically clean up after the
    tagging session, i.e. release a scraper database session and the
    parser with its memory caches. Tagging multiple sentences within one
    session is much more efficient than creating separate sessions for
    each one.

"""

from scraperdb import SessionContext
from treeutil import TreeUtility
from tokenizer import canonicalize_token
from settings import Settings, ConfigError
from contextlib import contextmanager
from fastparser import Fast_Parser


class Tagger:

    def __init__(self):
        # Make sure that the settings are loaded
        if not Settings.loaded:
            Settings.read("config/Reynir.conf")
        self._parser = None
        self._session = None

    def tag(self, text):
        """ Parse and POS-tag the given text, returning a dict """
        assert self._parser is not None, "Call Tagger.tag() inside 'with Tagger().context()'!"
        assert self._session is not None, "Call Tagger.tag() inside 'with Tagger().context()'!"
        pgs, stats, register = TreeUtility.raw_tag_text(self._parser, self._session, text)
        # Amalgamate the result into a single list of sentences
        if pgs:
            # Only process the first paragraph, if there are many of them
            if len(pgs) == 1:
                pgs = pgs[0]
            else:
                # More than one paragraph: gotta concatenate 'em all
                pa = []
                for pg in pgs:
                    pa.extend(pg)
                pgs = pa
        for sent in pgs:
            # Transform the token representation into a
            # nice canonical form for outside consumption
            for t in sent:
                canonicalize_token(t)
        return dict(result = pgs, stats = stats, register = register)

    @contextmanager
    def session(self):
        """ Wrapper to make sure we have a fresh database session and a parser object
            to work with in a tagging session - and that they are properly cleaned up
            after use """
        if self._session is not None:
            # Already within a session: weird case, but allow it anyway
            assert self._parser is not None
            yield self
        else:
            with SessionContext(commit = True, read_only = True) as session, Fast_Parser() as parser:
                self._session = session
                self._parser = parser
                try:
                    # Nice trick enabled by the @contextmanager wrapper
                    yield self
                finally:
                    self._parser = None
                    self._session = None

