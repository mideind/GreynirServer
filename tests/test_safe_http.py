"""

    Greynir: Natural language processing for Icelandic

    Copyright (C) 2026 Miðeind ehf.

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


    Tests for safe_http: URLs given by users of the web server must not be
    fetched from addresses that only the server itself can reach, such as
    the cloud metadata service, localhost or a private network.

"""

import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Iterator, List

import pytest

# Shenanigans to enable Pytest to discover modules in the
# main workspace directory (the parent of /tests)
basepath, _ = os.path.split(os.path.realpath(__file__))
mainpath = os.path.join(basepath, "..")
if mainpath not in sys.path:
    sys.path.insert(0, mainpath)

import safe_http  # noqa
from safe_http import NonPublicAddressError, is_public_address, safe_get  # noqa
from fetcher import Fetcher  # noqa


def test_is_public_address():
    for addr in (
        "8.8.8.8",
        "185.15.59.224",
        "2606:4700::1111",
        "::ffff:8.8.8.8",  # IPv4-mapped public address
    ):
        assert is_public_address(addr), addr
    for addr in (
        "127.0.0.1",  # Loopback
        "127.8.9.10",
        "0.0.0.0",
        "169.254.169.254",  # Link-local: the cloud metadata service
        "10.0.0.1",  # Private networks
        "172.16.0.1",
        "192.168.1.1",
        "100.64.0.1",  # Shared address space (carrier-grade NAT)
        "224.0.0.1",  # Multicast
        "255.255.255.255",
        "::1",
        "::",
        "fe80::1",
        "fe80::1%eth0",
        "fc00::1",  # Unique local
        "::ffff:127.0.0.1",  # Internal IPv4 addresses in IPv6 clothing
        "::ffff:169.254.169.254",
        "2002:7f00:1::",  # 6to4 of 127.0.0.1
        "64:ff9b::a9fe:a9fe",  # NAT64 of 169.254.169.254
        "",
        "not an address",
    ):
        assert not is_public_address(addr), addr


class _Handler(BaseHTTPRequestHandler):
    """Serves a secret at /secret, and redirects /redirect?<url> to <url>"""

    requests_seen: List[str] = []

    def do_GET(self) -> None:
        _Handler.requests_seen.append(f"{self.server.server_address[0]}{self.path}")
        if self.path.startswith("/redirect?"):
            self.send_response(302)
            self.send_header("Location", self.path.split("?", 1)[1])
            self.end_headers()
            return
        body = b"<html><body><p>secret</p></body></html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: Any) -> None:
        pass


def _serve(addr: str) -> HTTPServer:
    server = HTTPServer((addr, 0), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


@pytest.fixture
def servers() -> Iterator[List[str]]:
    """Two local web servers, on different loopback addresses"""
    _Handler.requests_seen = []
    a, b = _serve("127.0.0.1"), _serve("127.0.0.2")
    try:
        yield [f"http://127.0.0.1:{a.server_port}", f"http://127.0.0.2:{b.server_port}"]
    finally:
        a.shutdown()
        b.shutdown()


def test_internal_addresses_are_refused(servers: List[str]):
    port = servers[0].rsplit(":", 1)[1]
    for url in (
        servers[0] + "/secret",
        f"http://localhost:{port}/secret",  # A name that resolves to loopback
        f"http://2130706433:{port}/secret",  # 127.0.0.1 as a decimal number
        f"http://0x7f.1:{port}/secret",  # ...and in hexadecimal shorthand
        f"http://0.0.0.0:{port}/secret",
    ):
        with pytest.raises(NonPublicAddressError):
            safe_get(url, timeout=5)
        # The same through the fetcher, which reports failure as None
        assert Fetcher.raw_fetch_url(url) is None
    # No HTTP request reached the server
    assert _Handler.requests_seen == []


def test_other_schemes_are_refused():
    for url in ("file:///etc/passwd", "ftp://example.com/x", "gopher://x/", "//x/y", ""):
        with pytest.raises(NonPublicAddressError):
            safe_get(url, timeout=5)
        assert Fetcher.raw_fetch_url(url) is None


def test_redirect_to_internal_address_is_refused(
    servers: List[str], monkeypatch: pytest.MonkeyPatch
):
    # Pretend that the first server is on the public Internet
    real = safe_http.is_public_address
    monkeypatch.setattr(
        safe_http, "is_public_address", lambda addr: addr == "127.0.0.1" or real(addr)
    )
    public, internal = servers
    # It can be fetched from, also via a redirect to itself...
    r = safe_get(public + "/redirect?" + public + "/secret", timeout=5)
    assert r.status_code == 200 and "secret" in r.text and len(r.history) == 1
    assert Fetcher.raw_fetch_url(public + "/secret")
    # ...but a redirect from it to an internal address is not followed
    _Handler.requests_seen = []
    url = public + "/redirect?" + internal + "/secret"
    with pytest.raises(NonPublicAddressError):
        safe_get(url, timeout=5)
    assert Fetcher.raw_fetch_url(url) is None
    assert all(seen.startswith("127.0.0.1/redirect") for seen in _Handler.requests_seen)
    assert len(_Handler.requests_seen) == 2


def test_proxy_settings_are_ignored(servers: List[str], monkeypatch: pytest.MonkeyPatch):
    # A proxy from the environment would hide where a request ends up
    monkeypatch.setenv("HTTP_PROXY", servers[1])
    monkeypatch.setenv("http_proxy", servers[1])
    with pytest.raises(NonPublicAddressError):
        safe_get(servers[0] + "/secret", timeout=5)
    assert _Handler.requests_seen == []
    with pytest.raises(NonPublicAddressError):
        safe_get(servers[0] + "/secret", timeout=5, proxies={"http": servers[1]})
    assert _Handler.requests_seen == []
