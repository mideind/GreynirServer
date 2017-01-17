#!/usr/bin/env/python

"""
    Reynir: Natural language processing for Icelandic

    Similarity query client

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


    This module implements a client for the similarity server
    whose source code can be found in vectors/simserver.py.

"""


from multiprocessing.connection import Client
from settings import Settings


class SimilarityClient:

    """ A client that interacts with the similarity server over a
        TCP socket, typically on port 5001 """

    def __init__(self):
        self._conn = None


    def _connect(self):
        """ Connect to a similarity server, with authentication """
        if self._conn is not None:
            # Already connected
            return
        if not Settings.SIMSERVER_PORT:
            # No similarity server configured
            return
        try:
            with open("resources/SimilarityServerKey.txt", "rb") as file:
                secret_password = file.read()
        except FileNotFoundError:
            # Unable to load authentication key
            return
        address = (Settings.SIMSERVER_HOST, Settings.SIMSERVER_PORT)
        self._conn = Client(address, authkey = secret_password)


    def _retry_list(self, **kwargs):
        """ Connect to the server and send it a request, retrying if the
            server has closed the connection in the meantime. Return a
            result list or an empty list if no connection. """
        retries = 0
        while retries < 2:
            self._connect()
            if self._conn is None:
                break
            try:
                self._conn.send(kwargs)
                return self._conn.recv()
            except EOFError:
                self.close()
                retries += 1
                continue
        return []


    def _retry_cmd(self, **kwargs):
        """ Connect to the server and send it a command, retrying if the
            server has closed the connection in the meantime. """
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


    def list_similar_to_article(self, article_id, n = 10):
        """ Returns a list of (article_id, similarity) tuples """
        return self._retry_list(cmd = 'similar', id = article_id, n = n)


    def list_similar_to_topic(self, topic_vector, n = 10):
        """ Returns a list of (article_id, similarity) tuples """
        return self._retry_list(cmd = 'similar', topic = topic_vector, n = n)


    def list_similar_to_terms(self, terms, n = 10):
        """ The terms are a list of (stem, category) tuples.
            Returns a list of (article_id, similarity) tuples """
        return self._retry_list(cmd = 'similar', terms = terms, n = n)


    def refresh_topics(self):
        """ Cause the server to refresh article topic vectors from the database """
        self._retry_cmd(cmd = 'refresh')


    def reload_topics(self):
        """ Cause the server to reload article topic vectors from the database """
        self._retry_cmd(cmd = 'reload')


    def close(self):
        """ Close a client connection """
        if self._conn is not None:
            self._conn.close()
            self._conn = None


