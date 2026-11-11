"""

    Greynir: Natural language processing for Icelandic

    Safe HTTP fetching

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


    The web server fetches pages from URLs that are given by its users
    (/page?url=..., /article.api and others), and shows them the result.
    Left unchecked, that lets anybody read what the server itself can
    reach but the public Internet cannot: the metadata service of the
    cloud provider at 169.254.169.254, services listening on localhost,
    and hosts on a private network.

    This module provides an HTTP GET that only talks to public addresses.
    The check is made on the address that each connection actually ends up
    connected to, after name resolution. A host name that resolves to an
    internal address, a redirect to one, or a name that resolves differently
    between a check and the fetch (DNS rebinding) are thus all covered,
    which they would not be by inspecting the URL beforehand.

"""

from typing import Any, Optional

import ipaddress
import socket
import urllib.parse as urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.connection import HTTPConnection, HTTPSConnection
from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool


class NonPublicAddressError(requests.exceptions.ConnectionError):
    """Raised when a fetch would have connected to an address
    that is not on the public Internet"""


def is_public_address(addr: str) -> bool:
    """Return True if the given IP address is on the public Internet,
    i.e. not loopback, link-local, private, shared, multicast or reserved"""
    try:
        # Strip any IPv6 zone identifier ('fe80::1%eth0')
        ip = ipaddress.ip_address(addr.split("%", 1)[0])
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address):
        # Judge an IPv4 address in IPv6 clothing by the IPv4 address:
        # mapped (::ffff:a.b.c.d), 6to4 (2002::/16) and NAT64 (64:ff9b::/96)
        embedded = ip.ipv4_mapped or ip.sixtofour
        if embedded is None and ip in _NAT64:
            embedded = ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
        if embedded is not None:
            ip = embedded
    return ip.is_global and not ip.is_multicast


_NAT64 = ipaddress.ip_network("64:ff9b::/96")


def _check_peer(sock: socket.socket, host: str) -> None:
    """Close the socket and raise an exception
    if it is not connected to a public address"""
    try:
        peer = sock.getpeername()[0]
    except OSError:
        peer = ""
    if not is_public_address(peer):
        sock.close()
        raise NonPublicAddressError(
            f"Refusing to fetch from {host}: {peer or 'unknown address'} "
            "is not a public address"
        )


class _PublicHTTPConnection(HTTPConnection):
    def _new_conn(self) -> socket.socket:
        sock = super()._new_conn()
        _check_peer(sock, self.host)
        return sock


class _PublicHTTPSConnection(HTTPSConnection):
    def _new_conn(self) -> socket.socket:
        # Called before the TLS handshake, so nothing is sent
        # to an address that fails the check
        sock = super()._new_conn()
        _check_peer(sock, self.host)
        return sock


class _PublicHTTPConnectionPool(HTTPConnectionPool):
    ConnectionCls = _PublicHTTPConnection


class _PublicHTTPSConnectionPool(HTTPSConnectionPool):
    ConnectionCls = _PublicHTTPSConnection


class _PublicOnlyAdapter(HTTPAdapter):
    """A transport adapter whose connections refuse non-public addresses"""

    def init_poolmanager(self, *args: Any, **kwargs: Any) -> None:
        super().init_poolmanager(*args, **kwargs)
        self.poolmanager.pool_classes_by_scheme = {
            "http": _PublicHTTPConnectionPool,
            "https": _PublicHTTPSConnectionPool,
        }

    def proxy_manager_for(self, *args: Any, **kwargs: Any) -> Any:
        # Through a proxy we could not see where the request ends up
        raise NonPublicAddressError("Proxies are not supported for safe fetching")


def _find_refusal(e: Optional[BaseException]) -> Optional[NonPublicAddressError]:
    """Look for a NonPublicAddressError within a wrapped exception"""
    seen = set()
    stack = [e]
    while stack:
        x = stack.pop()
        if x is None or id(x) in seen:
            continue
        seen.add(id(x))
        if isinstance(x, NonPublicAddressError):
            return x
        stack.extend(a for a in x.args if isinstance(a, BaseException))
        stack.extend(
            a for a in (getattr(x, "reason", None), x.__cause__, x.__context__)
            if isinstance(a, BaseException)
        )
    return None


def public_session() -> requests.Session:
    """Return a requests session that only connects to public addresses.
    Redirects are followed through the same session, so that each hop
    is checked as well."""
    session = requests.Session()
    # Ignore proxy settings and .netrc credentials from the environment
    session.trust_env = False
    session.max_redirects = 10
    adapter = _PublicOnlyAdapter()
    # Replace the default adapters; no other schemes are supported
    session.adapters.clear()
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def safe_get(url: str, **kwargs: Any) -> requests.Response:
    """HTTP GET of a URL that may come from an untrusted source. Raises
    NonPublicAddressError, which is a requests ConnectionError, if the URL
    or any redirect from it leads to an address that is not public."""
    scheme: Optional[str] = urlparse.urlsplit(url).scheme.lower()
    if scheme not in ("http", "https"):
        raise NonPublicAddressError(f"Refusing to fetch {url!r}: not http or https")
    with public_session() as session:
        try:
            return session.get(url, **kwargs)
        except requests.exceptions.ConnectionError as e:
            # The refusal reaches us wrapped by urllib3 and requests:
            # raise it as itself, so that callers can tell it apart
            refusal = _find_refusal(e)
            if refusal is not None and refusal is not e:
                raise refusal from None
            raise
