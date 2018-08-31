#!/usr/bin/env python
"""

    Reynir: Natural language processing for Icelandic

    Remote parsing server

    Copyright (C) 2017 Miðeind ehf.

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

    This module implements server that forwards parsing queries to a
    remote server and delivers the response.

"""

import socket
import json

_PORT = 9000
_BUFFER_SIZE = 2 ** 15  # 32768
_TIMEOUT_REQUEST = 10
_HOST = "localhost"


class RemoteParser:

    def __init__(
        self, host=_HOST, port=_PORT, buffer_size=_BUFFER_SIZE, timeout=_TIMEOUT_REQUEST
    ):
        self.host = host
        self.port = port
        self.buffer_size = buffer_size
        self.timeout = timeout
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def __enter__(self):
        print("Trying to connect to {}:{}".format(self.host, self.port))
        self.sock.connect((self.host, self.port))
        return self

    def __exit__(self, ttype, value, traceback):
        self.sock.shutdown(socket.SHUT_RDWR)
        self.sock.close()
        return False

    def parse(self, text, version=1):
        lines = text.split("\n")
        obj = dict(
            version=version,
            sentences=lines,
        )
        payload = json.dumps(obj)
        self.sock.send(payload.encode("utf-8"))
        data = self.sock.recv(self.buffer_size)
        try:
            resp = json.loads(data.decode("utf-8"))
        except Exception:
            print("Error parsing text from nnserver: {data}".format(data=data))
            print("Received: {text}".format(text=text))
            return None
        return resp

    def parse_sentence(self, line):
        single_line = line.split("\n")[:1]
        return self.parse(line)
