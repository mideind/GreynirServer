#!/usr/bin/env/python

"""
    Reynir: Natural language processing for Icelandic

    Similarity query server and client

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


    This module implements classes for a similarity query server and
    a corresponding client. The server can answer queries about articles
    that are similar to a given article or topic vector. This assumes
    that articles already have topic vectors that are stored in the
    topic_vector column in the articles database table.

    The similarity server by default accepts TCP connections on port 5001.
    For security, this port should be closed from outside access via iptables or
    a firewall. However, the server also requires the client to authenticate
    using a secret key that is loaded from resources/SimilarityServerKey.txt.
    This file should not be made visible outside the Reynir server (or local
    network).

    To register this program as a service within systemd, create a unit file
    called similarity.service in the /etc/systemd/system directory, containing
    somthing like the following:

        [Unit]
        Description=Greynir document similarity service
        After=postgresql.service
        Before=greynir.service

        [Service]
        Type=simple
        User=[YOUR USERNAME]
        Group=[YOUR GROUPNAME]
        WorkingDirectory=/home/[YOUR USERNAME]/github/Reynir
        ExecStart=/home/[YOUR USERNAME]/github/Reynir/[YOUR VENV]/bin/python similar.py
        Environment="PATH=/home/[YOUR USERNAME]/github/Reynir/[YOUR VENV]/bin"
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

import json
import time
import array
import math
import heapq
import sys

from threading import Thread, Lock
from datetime import datetime
from multiprocessing import AuthenticationError
from multiprocessing.connection import Listener, Client

from settings import Settings, ConfigError
from scraperdb import SessionContext, desc, Article


class SimilarityServer:

    """ A class that manages an in-memory dictionary of articles
        and their topic vectors, and allows similarity queries of that
        dictionary. The dictionary is refreshed upon request from the
        articles database table.
    """


    def __init__(self):
        # Do an initial load of all article topic vectors
        self._lock = Lock()
        self._timestamp = None
        self._load_topics()


    def _load_topics(self):
        """ Load all article topics into the self._atopics dictionary """
        self._atopics = {}
        with SessionContext(commit = True, read_only = True) as session:
            print("Starting load of all article topic vectors")
            t0 = time.time()
            # Do the next refresh from this time point
            self._timestamp = datetime.utcnow()
            q = session.query(Article.id, Article.topic_vector)

            for a in q.yield_per(2000):
                if a.topic_vector:
                    # Load topic vector in to a compact array of 32-bit (short) floats
                    self._atopics[a.id] = array.array('d', json.loads(a.topic_vector))

            t1 = time.time()
            print("Loading of {0} topic vectors completed in {1:.2f} seconds".format(len(self._atopics), t1 - t0))


    def article_topic(self, article_id):
        """ Return the topic vector of the article having the given uuid,
            or None if no such article exists """
        return self._atopics.get(article_id)


    def refresh_topics(self):
        """ Load any new article topics into the _atopics dict """
        with self._lock:
            with SessionContext(commit = True, read_only = True) as session:
                # Do the next refresh from this time point
                ts = datetime.utcnow()
                q = session.query(Article.id, Article.topic_vector).filter(Article.indexed >= self._timestamp)
                self._timestamp = ts
                count = 0
                for a in q.yield_per(100):
                    if a.topic_vector:
                        # Load topic vector in to a compact array of 32-bit (short) floats
                        self._atopics[a.id] = array.array('d', json.loads(a.topic_vector))
                        count += 1
                print("Completed refresh_topics, {0} article vectors added".format(count))


    def _iter_similarities(self, vector):
        """ Generator of (id, similarity) tuples for all articles to the given vector """
        sum_vector_sq = sum((y * y for y in vector))

        def cosine_similarity(v1):
            """ Compute cosine similarity of v1 to v2: (v1 dot v2)/{||v1||*||v2||) """
            sumxx, sumxy = 0.0, 0.0
            for x, y in zip(v1, vector):
                sumxx += x * x
                sumxy += x * y
            return sumxy / math.sqrt(sumxx * sum_vector_sq)

        for article_id, topic_vector in self._atopics.items():
            yield article_id, cosine_similarity(topic_vector)


    def find_similar(self, n, vector):
        """ Return the N articles with the highest similarity score to the given vector,
            as a list of tuples (article_uuid, similarity) """
        with self._lock:
            return heapq.nlargest(n, self._iter_similarities(vector), key = lambda x: x[1])


    def run(self, port = 5001):
        """ Run a similarity server serving requests that come in at the given port """
        address = ('localhost', port)     # family is deduced to be 'AF_INET'

        with open("resources/SimilarityServerKey.txt", "rb") as file:
            secret_password = file.read()

        with Listener(address, authkey = secret_password) as listener:
            while True:
                try:
                    print("Listening for connections on port {0}".format(port))
                    conn = listener.accept()

                    print('Connection accepted from', listener.last_accepted)
                    Thread(target = self._command_loop, args = (conn,)).start()
                except AuthenticationError:
                    print("Authentication failed for client")


    def _command_loop(self, conn):
        """ Run a command loop for this server inside a client thread """
        with conn:
            # conn is automatically closed when leaving the 'with' scope
            while True:
                try:
                    request = conn.recv()
                except EOFError:
                    print("Client closed connection")
                    break

                if not isinstance(request, dict):
                    print("Invalid request received: {0!r}".format(request))
                    continue

                try:
                    cmd = request["cmd"].strip().lower()
                except:
                    print("Invalid request received: {0!r}".format(request))
                    continue

                if cmd == "logout":
                    print("Client logged out")
                    break

                if cmd == "similar":
                    try:
                        uuid = request["id"].strip().lower()
                    except:
                        print("Invalid request received: {0!r}".format(request))
                        continue
                    try:
                        n = int(request.get("n", 10))
                    except:
                        n = 10
                    conn.send(self.find_similar(n, self.article_topic(uuid)))
                elif cmd == "refresh":
                    # Load any new article topic vectors
                    self.refresh_topics()
                else:
                    print("Unknown command: {0}".format(cmd))


class SimilarityClient:

    """ A client that interacts with the similarity server """

    def __init__(self):
        self._conn = None


    def connect(self, port = 5001):
        """ Connect to a similarity server, with authentication """
        if self._conn is not None:
            self._conn.close()
        address = ('localhost', port)
        with open("resources/SimilarityServerKey.txt", "rb") as file:
            secret_password = file.read()
        self._conn = Client(address, authkey = secret_password)


    def similar_articles(self, article_id, n = 10):
        """ Returns a list of (article_id, similarity) tuples """
        if self._conn is None:
            raise RuntimeError("Must connect client before calling similar_articles()")
        self._conn.send(dict(cmd = 'similar', id = article_id, n = n))
        return self._conn.recv()


    def refresh_topics(self):
        """ Cause the server to refresh article topic vectors from the database """
        if self._conn is None:
            raise RuntimeError("Must connect client before calling refresh_topics()")
        self._conn.send(dict(cmd = 'refresh'))


    def close(self):
        """ Close a client connection """
        if self._conn is not None:
            self._conn.close()
            self._conn = None


if __name__ == "__main__":

    try:
        # Read configuration file
        Settings.read("config/ReynirSimple.conf")
    except ConfigError as e:
        print("Configuration error: {0}".format(e))
        quit()

    # Run a similarity server on the default port
    SimilarityServer().run()

