#!/usr/bin/env/python

"""
    Greynir: Natural language processing for Icelandic

    Similarity query client

    Copyright (C) 2023 Miðeind ehf.

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


    This module implements a client for the similarity server
    whose source code can be found in vectors/simserver.py.

"""

from typing import Any, List, Optional, Tuple

import os
import sys
from contextlib import closing
from multiprocessing.connection import Connection, answer_challenge, deliver_challenge

from settings import Settings

# Hack to allow the similarity client run both under Gunicorn/eventlet
# on a live server, and stand-alone using the regular Python 3.x library.
# Under Gunicorn/eventlet, the socket class is 'monkey-patched' in ways
# that are not compatible with multiprocessing.connection.Connection().
# We make sure that we obtain access to the original, non-patched
# socket module. This, alas, means that our calls to the similarity
# server are truly blocking, even under Gunicorn/eventlet.

try:
    import eventlet  # type: ignore

    USING_EVENTLET = True
    socket = eventlet.patcher.original("socket")  # type: ignore
    assert socket is not None
except ImportError:
    import socket

    USING_EVENTLET = False  # type: ignore

# The following two functions replicate and hack/tweak corresponding functions
# from multiprocessing.connection. This is necessary because the original
# multiprocessing.connection.SocketClient() function uses the context protocol
# on a socket, but this is not allowed by the monkey-patched GreenSocket
# that eventlet inserts instead of the original socket class.

Address = Tuple[str, int]


def _SocketClient(address: Address) -> Connection:
    """Return a connection object connected to the socket given by `address`"""
    with closing(socket.socket(socket.AF_INET)) as s:
        s.setblocking(True)
        s.connect(address)
        # The following cast() hack is required since Connection()
        # appears to have a wrong signature in typeshed
        return Connection(s.detach())


def _Client(address: Address, authkey: Optional[bytes]=None) -> Connection:
    """Returns a connection to the address of a `Listener`"""
    c = _SocketClient(address)
    if authkey is not None:
        answer_challenge(c, authkey)
        deliver_challenge(c, authkey)
    return c


class SimilarityClient:

    """A client that interacts with the similarity server over a
    TCP socket, typically on port 5001"""

    BASE_PATH = os.path.dirname(os.path.realpath(__file__))
    KEY_FILE = os.path.join(BASE_PATH, "resources", "SimilarityServerKey.txt")

    def __init__(self):
        self._conn = None

    def _connect(self):
        """Connect to a similarity server, with authentication"""
        if self._conn is not None:
            # Already connected
            return
        if not Settings.SIMSERVER_PORT:
            # No similarity server configured
            return
        try:
            with open(self.KEY_FILE, "rb") as file:
                secret_password = file.read()
        except OSError as oserr:
            # Unable to load authentication key
            print(
                "Unable to read similarity server key file {0}; error {1}".format(
                    self.KEY_FILE, oserr
                )
            )
            sys.stdout.flush()
            return
        address = (Settings.SIMSERVER_HOST, Settings.SIMSERVER_PORT)
        try:
            self._conn = _Client(address, authkey=secret_password)
        except Exception as ex:
            print(
                "Unable to connect to similarity server at {0}:{1}; error {2}".format(
                    address[0], address[1], ex
                )
            )
            sys.stdout.flush()
            # Leave self._conn set to None

    def _retry_list(self, **kwargs: Any):
        """Connect to the server and send it a request, retrying if the
        server has closed the connection in the meantime. Return a
        dict with a result list or an empty list if no connection."""
        retries = 0
        while retries < 2:
            self._connect()
            if self._conn is None:
                break
            try:
                self._conn.send(kwargs)
                return self._conn.recv()
            except (EOFError, BlockingIOError):
                self.close()
                retries += 1
                continue
        return dict(articles=[])

    def _retry_cmd(self, **kwargs: Any):
        """Connect to the server and send it a command, retrying if the
        server has closed the connection in the meantime."""
        retries = 0
        while retries < 2:
            self._connect()
            if self._conn is None:
                break
            try:
                self._conn.send(kwargs)
                # Successful: we're done
                return
            except EOFError:
                # Close the connection from the client side and re-connect
                self.close()
                retries += 1
                continue

    def list_similar_to_article(self, article_id: str, n: int=10):
        """Returns a dict containing a list of (article_id, similarity) tuples"""
        return self._retry_list(cmd="similar", id=article_id, n=n)

    def list_similar_to_topic(self, topic_vector: List[float], n: int=10):
        """Returns a dict containing a list of (article_id, similarity) tuples"""
        return self._retry_list(cmd="similar", topic=topic_vector, n=n)

    def list_similar_to_terms(self, terms: List[Tuple[str, str]], n: int=10):
        """The terms are a list of (stem, category) tuples.
        Returns a dict where the articles key contains a
        list of (article_id, similarity) tuples"""
        return self._retry_list(cmd="similar", terms=terms, n=n)

    def refresh_topics(self) -> None:
        """Cause the server to refresh article topic vectors from the database"""
        self._retry_cmd(cmd="refresh")

    def reload_topics(self) -> None:
        """Cause the server to reload article topic vectors from the database"""
        self._retry_cmd(cmd="reload")

    def close(self) -> None:
        """Close a client connection"""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
