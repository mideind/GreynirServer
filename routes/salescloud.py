"""

    Greynir: Natural language processing for Icelandic

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


    This module implements Flask routes for the webhooks associated with
    the SalesCloud subscription system.

"""

from typing import Any, Dict, Optional, cast

import logging
import json
import hmac
import hashlib

from datetime import datetime

# from db.models import Customer, Subscription

from . import routes, better_jsonify, request


# Maximum age of received requests to be valid, in seconds
_MAX_TIME_WINDOW = 100.0


class _Secret:

    """A wrapper for private and public key data used
    in communications with SalesCloud"""

    _SC_SECRET_KEY: Optional[bytes] = None
    _SC_PUBLIC_KEY: Optional[str] = None

    def __init__(self) -> None:
        pass

    @classmethod
    def load(cls) -> None:
        """Fetch secret key and client UUID from a file"""
        try:
            with open("resources/salescloud_key.bin", "r", encoding="utf-8") as f:
                cls._SC_SECRET_KEY = f.readline().strip().encode("ascii")
                cls._SC_PUBLIC_KEY = f.readline().strip()
        except Exception:
            logging.error("Unable to read file resources/salescloud_key.bin")
            cls._SC_SECRET_KEY = b""
            cls._SC_PUBLIC_KEY = ""

    @property
    def key(self) -> bytes:
        """Return the secret key value, which is a bytes object"""
        if not self._SC_SECRET_KEY:
            _Secret.load()
        assert self._SC_SECRET_KEY is not None
        return self._SC_SECRET_KEY

    @property
    def public_key(self) -> str:
        """Return Greynir's public key"""
        if not self._SC_PUBLIC_KEY:
            _Secret.load()
        assert self._SC_PUBLIC_KEY is not None
        return self._SC_PUBLIC_KEY


_SECRET = _Secret()


def validate_request(
    method, url, payload, xsc_date, xsc_key, xsc_digest, max_time=_MAX_TIME_WINDOW
):
    """Validate an incoming request against our secret key. All parameters
    are assumed to be strings (str) except payload and xsc_digest,
    which are bytes."""

    # Sanity check
    if not all((method, url, payload, xsc_date, xsc_key, xsc_digest)):
        return False

    # The public key must of course be correct
    if xsc_key != _SECRET.public_key:
        return False

    # Check the time stamp
    try:
        dt = datetime.strptime(xsc_date, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        # Invalid date/time
        return False
    delta = (datetime.utcnow() - dt).total_seconds()
    if not -2.0 < delta < max_time:
        # The request must be made in a time window ranging from 2 seconds in
        # the future (allowing for a slightly wrong clock) to 100 seconds in
        # the past (allowing time for the HTTP request to arrive and be
        # processed). Anything outside this will be rejected. This makes a
        # brute force attack on the SHA256 hash harder.
        logging.warning(
            "Subscription request outside timestamp window, delta is {0:.1f}".format(
                delta
            )
        )
        return False

    # Reconstruct the signature, which is a bytes object
    xsc_signature = (xsc_date + xsc_key + method + url).encode("ascii") + payload
    # Hash it using the secret key
    my_digest = hmac.new(_SECRET.key, xsc_signature, hashlib.sha256).hexdigest()
    # Compare with the signature from the client and return True if they match
    if hasattr(hmac, "compare_digest"):
        # Better to use the compare_digest function, if available
        return hmac.compare_digest(xsc_digest, my_digest)
    return xsc_digest == my_digest


def handle_request(request):
    """Handle a SalesCloud request, extracting its contents"""
    # Validate the request
    if request.headers.get("User-Agent") != "SalesCloud":
        return dict(success=False, reason="Unknown user agent"), 403  # Forbidden
    xsc_key = request.headers.get("X-SalesCloud-Access-Key", "")[0:256]
    xsc_date = request.headers.get("X-SalesCloud-Date", "")[0:256]
    xsc_digest = request.headers.get("X-SalesCloud-Signature", "")[0:256]
    # Get the payload (bytes)
    payload = b""
    try:
        # Do not accept request bodies larger than 2K
        if int(request.headers.get("Content-length", 0)) < 2048:
            payload = request.get_data(cache=False, as_text=False)
    except Exception:
        # Something is wrong with the Content-length header or the request body
        return dict(success=False), 400  # Bad request
    # Do the signature/digest validation
    # Be careful with the URL: since we go through an nginx proxy,
    # the request URL we see has the HTTP protocol, even though the
    # original URL used to generate the signature was HTTPS
    url = request.url
    if url.startswith("http:"):
        url = "https:" + url[5:]
    if not validate_request(
        request.method, url, payload, xsc_date, xsc_key, xsc_digest
    ):
        logging.error("Invalid signature received")
        return dict(success=False, reason="Invalid signature"), 403  # Forbidden

    # The request is formally valid: return the contents
    j = json.loads(payload.decode("utf-8")) if payload else None
    return j, 200  # OK


@routes.route("/salescloud/nyskraning", methods=["POST"])
def sales_create():
    """Webhook handler for SalesCloud"""
    j, status = handle_request(request)
    if status != 200:
        return better_jsonify(**cast(Dict[str, Any], j)), status
    if j is None or j.get("type") != "subscription_created":
        return (
            better_jsonify(success=False, reason="Unknown request type"),
            400,
        )  # Bad request

    # Example JSON:
    # {
    #     'after_renewal': '2020-04-13T13:23:04+00:00',
    #     'before_renewal': '',
    #     'customer_id': '294824',
    #     'customer_label': '',
    #     'product_id': '21154',
    #     'subscription_status': 'true',
    #     'type': 'subscription_created'
    # }
    return better_jsonify(success=True)


@routes.route("/salescloud/breyting", methods=["POST"])
def sales_modify():
    """Webhook handler for SalesCloud"""
    j, status = handle_request(request)
    if status != 200:
        return better_jsonify(**cast(Dict[str, Any], j)), status
    if j is None or j.get("type") != "subscription_updated":
        return (
            better_jsonify(success=False, reason="Unknown request type"),
            400,
        )  # Bad request

    # Handle a subscription update
    # !!! TBD
    # Example JSON:
    # {
    #     'after_renewal': '2020-06-11T14:35:18+00:00',
    #     'before_renewal': '2020-06-11T14:35:18+00:00',
    #     'customer_id': '3036',
    #     'customer_label': '101373914453493967749',
    #     'product_id': '21154',
    #     'subscription_status': 'true',
    #     'type': 'subscription_updated'
    # }
    # subscription.after_renewal = j["after_renewal"]
    # subscription.product_id = j["product_id"]
    # subscription.customer_id = j["customer_id"]
    # subscription.customer_label = j["customer_label"]
    # subscription.subscription_status = j["subscription_status"]
    return better_jsonify(success=True)
