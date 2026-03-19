#!/usr/bin/env/python
"""
    Greynir: Natural language processing for Icelandic

    Similarity query server

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


    This module implements a similarity query server. The server can
    answer queries about articles that are similar to a given article
    or topic vector. This assumes that articles already have topic vectors
    that are stored in the topic_vector column in the articles database table.

    The similarity server by default accepts TCP connections on port 5001.
    For security, this port should be closed from outside access via iptables or
    a firewall. However, the server also requires the client to authenticate
    using a secret key that is loaded from resources/SimilarityServerKey.txt.
    This file should not be made visible outside the Greynir server (or local
    network).

    To register this program as a service within systemd, create a unit file
    called similarity.service in the /etc/systemd/system directory, containing
    somthing like the following (assuming you have a virtualenv called venv):

        [Unit]
        Description=Greynir document similarity service
        After=postgresql.service
        Before=greynir.service

        [Service]
        Type=simple
        User=[YOUR USERNAME]
        Group=[YOUR GROUPNAME]
        WorkingDirectory=/home/[YOUR USERNAME]/Greynir/vectors
        ExecStart=/home/[YOUR USERNAME]/Greynir/vectors/venv/bin/python simserver.py
        Environment="PATH=/home/[YOUR USERNAME]/Greynir/vectors/venv/bin"
        Environment="PYTHONIOENCODING=utf-8"
        Environment="PYTHONUNBUFFERED=True"
        StandardOutput=syslog
        StandardError=syslog

        [Install]
        WantedBy=multi-user.target

    Then run:
        $ sudo systemctl enable similarity
        $ sudo systemctl start similarity

"""

from __future__ import annotations

import gc
import json
import time
import sys

import numpy as np
from numpy.typing import NDArray

from threading import Thread, Lock
from datetime import datetime, timezone
from multiprocessing import AuthenticationError
from multiprocessing.connection import Connection, Listener, Client

from settings import Settings, ConfigError  # type: ignore[attr-defined]
from db import SessionContext, desc  # type: ignore[import-not-found]
from db.models import Article, Root  # type: ignore[import-not-found]
from builder import ReynirCorpus  # type: ignore[attr-defined]


class InternalError(RuntimeError):
    """Exception thrown from within the server, causing it to terminate"""

    def __init__(self, s: str) -> None:
        super().__init__(s)


class SimilarityServer:

    """A class that manages an in-memory matrix of article topic vectors
    and allows similarity queries via vectorized matrix operations.
    The matrix is refreshed upon request from the articles database table.
    """

    def __init__(self) -> None:
        self._lock: Lock = Lock()
        self._timestamp: datetime | None = None
        # Article topic vectors stored as a single (N, dims) float32 matrix
        # The matrix may have spare rows beyond _num_rows for in-place appends
        self._matrix: NDArray[np.float32] | None = None
        # Precomputed squared norms for each row, shape (capacity,)
        self._norms_sq: NDArray[np.float32] | None = None
        # Number of live rows in the matrix
        self._num_rows: int = 0
        # Allocated row capacity of the matrix
        self._capacity: int = 0
        # Article IDs, index-aligned with matrix rows
        self._ids: list[str] = []
        # Reverse mapping: article ID -> row index
        self._id_to_index: dict[str, int] = {}
        self._corpus: ReynirCorpus | None = None

    # Spare capacity added when allocating/growing the topic vector matrix
    _SPARE_ROWS = 10_000

    def _load_topics(self) -> None:
        """Load all article topics into a single NumPy matrix.
        Pre-allocates based on a COUNT query to avoid repeated
        reallocations during loading."""
        assert self._corpus is not None
        dims = self._corpus.dimensions
        ids: list[str] = []
        with SessionContext(commit=True, read_only=True) as session:
            # Get an estimated row count to pre-allocate the matrix
            est_count: int = (
                session.query(Article)
                .join(Root)
                .filter(Root.visible)
                .filter(Article.topic_vector != None)  # noqa: E711
                .count()
            )
            # Allocate once, with spare capacity for new articles
            capacity = est_count + self._SPARE_ROWS
            matrix = np.empty((capacity, dims), dtype=np.float32)
            row = 0
            print(
                "Starting load of all article topic vectors"
                " (estimated {0})".format(est_count)
            )
            t0 = time.time()
            # Do the next refresh from this time point
            self._timestamp = datetime.now(timezone.utc)
            q = (
                session.query(Article)
                .join(Root)
                .filter(Root.visible)
                .with_entities(Article.id, Article.topic_vector)
            )

            for a in q.yield_per(2000):
                if a.topic_vector:
                    vec = json.loads(a.topic_vector)
                    if isinstance(vec, list) and len(vec) == dims:
                        if row >= capacity:
                            # Shouldn't normally happen, but handle it
                            capacity += self._SPARE_ROWS
                            new_matrix = np.empty(
                                (capacity, dims), dtype=np.float32
                            )
                            new_matrix[:row] = matrix[:row]
                            matrix = new_matrix
                        matrix[row] = vec
                        ids.append(a.id)
                        row += 1
                    else:
                        print(
                            "Warning: faulty topic vector for article {0}".format(a.id)
                        )

            t1 = time.time()

        # Keep the loading array directly — it already has spare capacity
        # (est_count + _SPARE_ROWS) for future appends via refresh_topics.
        self._matrix = matrix
        self._num_rows = row
        self._capacity = matrix.shape[0]
        # Precompute squared norms for cosine similarity
        self._norms_sq = np.empty(self._capacity, dtype=np.float32)
        self._norms_sq[:row] = np.einsum(
            "ij,ij->i", self._matrix[:row], self._matrix[:row]
        )
        self._ids = ids
        self._id_to_index = {aid: idx for idx, aid in enumerate(ids)}

        print(
            "Loading of {0} topic vectors completed in {1:.2f} seconds".format(
                len(ids), t1 - t0
            )
        )

    def article_topic(self, article_id: str) -> NDArray[np.float32] | None:
        """Return the topic vector of the article having the given uuid,
        or None if no such article exists"""
        idx = self._id_to_index.get(article_id)
        if idx is None or self._matrix is None or idx >= self._num_rows:
            return None
        return self._matrix[idx]

    def reload_topics(self) -> None:
        """Reload all article topic vectors from the database"""
        with self._lock:
            # Can't serve queries while we're doing this
            self._load_topics()

    def _grow_matrix(self, needed: int) -> None:
        """Grow the matrix and norms arrays to accommodate `needed` new rows."""
        assert self._matrix is not None
        assert self._norms_sq is not None
        dims = self._matrix.shape[1]
        new_capacity = self._capacity + max(needed, self._SPARE_ROWS)
        new_matrix = np.empty((new_capacity, dims), dtype=np.float32)
        new_matrix[: self._num_rows] = self._matrix[: self._num_rows]
        new_norms = np.empty(new_capacity, dtype=np.float32)
        new_norms[: self._num_rows] = self._norms_sq[: self._num_rows]
        self._matrix = new_matrix
        self._norms_sq = new_norms
        self._capacity = new_capacity
        gc.collect()

    def refresh_topics(self) -> None:
        """Load any new or updated article topics into the matrix.
        Existing articles are updated in-place; new articles are
        appended into spare capacity without reallocating."""
        assert self._corpus is not None
        assert self._matrix is not None
        assert self._norms_sq is not None
        with self._lock:
            with SessionContext(commit=True, read_only=True) as session:
                # Do the next refresh from this time point
                ts = datetime.now(timezone.utc)
                q = (
                    session.query(Article)
                    .join(Root)
                    .filter(Root.visible)
                    .filter(Article.indexed >= self._timestamp)
                    .with_entities(Article.id, Article.topic_vector)
                )
                self._timestamp = ts
                updated: int = 0
                new_count: int = 0
                for a in q.yield_per(100):
                    if a.topic_vector:
                        vec = json.loads(a.topic_vector)
                        if (
                            isinstance(vec, list)
                            and len(vec) == self._corpus.dimensions
                        ):
                            idx = self._id_to_index.get(a.id)
                            if idx is not None:
                                # Update existing row in place
                                row = np.array(vec, dtype=np.float32)
                                self._matrix[idx] = row
                                self._norms_sq[idx] = np.dot(row, row)
                                updated += 1
                            else:
                                # Append new row, growing if needed
                                if self._num_rows >= self._capacity:
                                    self._grow_matrix(1)
                                row = np.array(vec, dtype=np.float32)
                                self._matrix[self._num_rows] = row
                                self._norms_sq[self._num_rows] = np.dot(
                                    row, row
                                )
                                self._id_to_index[a.id] = self._num_rows
                                self._ids.append(a.id)
                                self._num_rows += 1
                                new_count += 1
                        else:
                            print(
                                "Warning: faulty topic vector for article {0}".format(
                                    a.id
                                )
                            )
                print(
                    "Completed refresh_topics, {0} updated, {1} new".format(
                        updated, new_count
                    )
                )

    def find_similar(
        self, n: int, vector: NDArray[np.float32] | None
    ) -> list[tuple[str, float]]:
        """Return the N articles with the highest similarity score to the given vector,
        as a list of tuples (article_uuid, similarity).
        Uses vectorized matrix multiplication for efficient computation."""
        if vector is None or len(vector) == 0 or all(e == 0.0 for e in vector):
            return []
        with self._lock:
            if self._matrix is None or self._num_rows == 0:
                return []
            base = np.array(vector, dtype=np.float32)
            norm_base_sq = np.dot(base, base)
            if norm_base_sq < 1.0e-6:
                return []
            # Use only the live rows of the matrix
            live_matrix = self._matrix[: self._num_rows]
            live_norms = self._norms_sq[: self._num_rows]
            # Compute all dot products in one matrix-vector multiply
            dot_products = live_matrix @ base
            # Cosine similarity: dot(v, base) / sqrt(|v|^2 * |base|^2)
            denominators = np.sqrt(live_norms * norm_base_sq)
            # Avoid division by zero for any zero-norm vectors
            with np.errstate(divide="ignore", invalid="ignore"):
                similarities = dot_products / denominators
            # Replace NaN/inf with -1 so they won't appear in top N
            np.nan_to_num(
                similarities, copy=False, nan=-1.0, posinf=-1.0, neginf=-1.0
            )
            # Efficiently select top N using argpartition
            if n >= self._num_rows:
                top_indices = np.argsort(similarities)[::-1]
            else:
                top_indices = np.argpartition(similarities, -n)[-n:]
                top_indices = top_indices[
                    np.argsort(similarities[top_indices])[::-1]
                ]
            return [
                (self._ids[i], float(similarities[i])) for i in top_indices
            ]

    def run(self, host: str, port: int) -> None:
        """Run a similarity server serving requests that come in at the given port"""
        address = (host, port)  # Family is deduced to be 'AF_INET'
        # Load the secret password that clients must use to authenticate themselves
        try:
            with open("resources/SimilarityServerKey.txt", "rb") as file:
                secret_password = file.read()
        except FileNotFoundError:
            raise InternalError(
                "Server key file missing: resources/SimilarityServerKey.txt"
            )
        except:
            raise InternalError(
                "Unable to load server key when starting similarity server"
            )

        print(
            "Greynir similarity server started\nListening for connections on port {0}".format(
                port
            )
        )

        with Listener(address, authkey=secret_password) as listener:
            self._corpus = ReynirCorpus()
            self._load_topics()
            while True:
                try:
                    conn = listener.accept()
                    print("Connection accepted from {0}".format(listener.last_accepted))
                    # Launch a thread to handle commands from this client
                    Thread(target=self._command_loop, args=(conn,)).start()
                except AuthenticationError:
                    print("Authentication failed for client")
                    pass
                except Exception as ex:
                    print("Exception when listening for connections: {0}".format(ex))
                    pass
                finally:
                    sys.stdout.flush()

    def _command_loop(self, conn: Connection) -> None:
        """Run a command loop for this server inside a client thread"""

        class ClientError(RuntimeError):
            """Local exception class for handling erroneous requests from clients"""

            def __init__(self, request: object) -> None:
                super().__init__("Invalid request received: {0!r}".format(request))

        with conn:
            # conn is automatically closed when leaving the 'with' scope
            while True:
                try:
                    request = conn.recv()

                    # Requests are sent as Python dict objects
                    if not isinstance(request, dict):
                        raise ClientError(request)

                    # The main command should be a string under the 'cmd' key
                    try:
                        cmd = request["cmd"].strip().lower()
                    except:
                        raise ClientError(request)

                    if cmd == "logout":
                        print("Client logged out")
                        break

                    if cmd == "similar":
                        # Run a similarity query
                        # Obtain number of desired results
                        try:
                            n = int(request.get("n", 10))
                        except:
                            n = 10
                        topic = None
                        result = dict()
                        if "id" in request:
                            try:
                                # Compare similarity to an article identified by UUID
                                uuid = request["id"].strip().lower()
                                topic = self.article_topic(uuid)
                                if topic is None:
                                    result["not_indexed"] = True
                            except:
                                raise ClientError(request)
                        elif "terms" in request:
                            # Compare similarity to the given terms, which are assumed to
                            # be normalized, i.e. of the form (stem, category).
                            # Examples: ('sjómaður', 'kk'), ('Jóna Hrönn Bolladóttir', 'person_kvk')
                            terms = request["terms"]
                            if not isinstance(terms, list):
                                raise ClientError(request)
                            # Convert the list of search terms to a topic vector
                            assert self._corpus is not None
                            topic, term_weights = self._corpus.get_topic_vector(terms)
                            result["weights"] = term_weights
                        elif "topic" in request:
                            # Compare similarity to the given topic vector
                            if not isinstance(request["topic"], list):
                                raise ClientError(request)
                            topic = np.array(request["topic"], dtype=np.float32)
                        else:
                            raise ClientError(request)
                        # Launch the command and send the reply back to the client
                        t0 = time.time()
                        result["articles"] = self.find_similar(n, topic)
                        t1 = time.time()
                        conn.send(result)
                    elif cmd == "refresh":
                        # Load any new article topic vectors from the articles table
                        self.refresh_topics()
                    elif cmd == "reload":
                        # Reload all article topic vectors from the articles table
                        self.reload_topics()
                    else:
                        print("Unknown command: {0}".format(cmd))

                except EOFError:
                    print("Client closed connection")
                    break

                except ClientError as e:
                    # Print a message and continue listening to commands
                    print(str(e))

                except Exception as ex:
                    print("Exception in client thread loop: {0}".format(ex))
                    break

                finally:
                    sys.stdout.flush()


if __name__ == "__main__":

    try:
        # Read configuration file
        Settings.read("Vectors.conf")
    except ConfigError as e:
        print("Configuration error: {0}".format(e))
        sys.exit(1)

    # Run a similarity server on the default port
    # Modify host to 0.0.0.0 to enable outside access
    try:
        SimilarityServer().run(host="localhost", port=Settings.SIMSERVER_PORT)
    except InternalError as e:
        print(str(e))
        sys.exit(1)
    except OSError as e:
        import errno

        if e.errno == errno.EADDRINUSE:  # Address already in use
            print(
                "Simserver is already running on port {0}".format(
                    Settings.SIMSERVER_PORT
                )
            )
            sys.exit(1)
        else:
            raise
