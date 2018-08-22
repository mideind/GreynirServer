#!/usr/bin/env python3
import socket
import json

_PORT = 9000
_BUFFER_SIZE = 2 ** 13  # 8192
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
        self.sock.connect((self.host, self.port))
        return self

    def __exit__(self, ttype, value, traceback):
        self.sock.shutdown(socket.SHUT_RDWR)
        self.sock.close()
        return False

    def parse(self, line, flat=True, incomplete=True):
        msg = line.split("\n")[0] # only process first sentence
        encoded_msg = bytearray([1 if flat else 0, 1 if incomplete else 0])
        encoded_msg.extend(msg.encode("utf-8"))
        self.sock.send(encoded_msg)
        data = self.sock.recv(self.buffer_size)
        try:
            tree_dict = json.loads(data.decode("utf-8"))
        except Exception:
            print("Error parsing text: {text}".format(text=msg))
            print("Received: {data}".format(data=data))
            return None
        return tree_dict


def remote_parse_test():
    with RemoteParser() as parser:
        tree = parser.parse("Ísland keppti í HM fyrir stuttu.")
        print(tree)
        return tree


def t1():
    with RemoteParser() as parser:
        text = "Snúðurinn sem fólkið keypti var ekki góður."
        sent = text.split("\n")
        tree_dict = parser.parse(sent)
        print(json.dumps(tree_dict, indent=4, ensure_ascii=False))
