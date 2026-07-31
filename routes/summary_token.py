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


    Summary authorization tokens

    Generating an article summary calls a paid LLM API, so /summary.api must
    not let an anonymous caller trigger generation merely by naming an article
    id. Reading an already stored summary stays open to everyone; *generating*
    a missing one requires a token.

    A token is a stateless HMAC over (article uuid, expiry time), minted when
    the article page is rendered and handed back by that page's own JavaScript.
    Nothing is stored server side, which matters here: the several Gunicorn
    workers share no memory, and the Flask cache is a per-process SimpleCache,
    so anything stateful would only be seen by the worker that wrote it.

    Binding the signature to the article uuid means a token scraped from one
    page cannot be replayed against a different article, and the expiry keeps
    any such token useful for minutes rather than indefinitely.

    The signing key comes from the GREYNIR_SUMMARY_SECRET environment
    variable, supplied the same way as OPENAI_API_KEY (systemd drop-in, or
    .env - note the drop-in wins, as load_dotenv does not override). It is
    deliberately not read from resources/, because deploy.sh copies only
    resources/geo and such a file would silently fail to deploy.

    If no key is configured we fail closed: no token validates, so summaries
    are served from cache but never generated. That is the safe direction -
    the alternative is an open endpoint that bills an LLM per request.

"""

from typing import Optional

import os
import time
import hmac
import base64
import hashlib
import logging


# How long a minted token remains valid. The page asks for its summary as
# soon as it loads, so this only has to cover render time plus the client's
# first XHR. Five minutes is already generous.
TOKEN_TTL_SECONDS = 300

# Truncated HMAC-SHA256. 128 bits is far beyond forgeable for a value that
# expires within minutes, and keeps the token short in the page markup.
_SIGNATURE_BYTES = 16

_ENV_VAR = "GREYNIR_SUMMARY_SECRET"

_secret: Optional[bytes] = None
_secret_loaded = False


def _get_secret() -> Optional[bytes]:
    """Return the signing key, or None if none is configured.
    The absence of a key is logged once, not per request."""
    global _secret, _secret_loaded
    if not _secret_loaded:
        _secret_loaded = True
        raw = os.environ.get(_ENV_VAR, "").strip()
        if raw:
            _secret = raw.encode("utf-8")
        else:
            _secret = None
            logging.error(
                "%s is not set: article summaries will be served from cache "
                "but never generated. Set it in the service's systemd drop-in.",
                _ENV_VAR,
            )
    return _secret


def _sign(uuid: str, expiry: int, secret: bytes) -> str:
    """Return the signature binding an article uuid to an expiry time."""
    message = f"{uuid}:{expiry}".encode("utf-8")
    digest = hmac.new(secret, message, hashlib.sha256).digest()
    return (
        base64.urlsafe_b64encode(digest[:_SIGNATURE_BYTES]).decode("ascii").rstrip("=")
    )


def make_summary_token(uuid: str) -> str:
    """Mint a token authorizing summary generation for one article.
    Returns an empty string if no signing key is configured, in which case
    the page simply never asks for generation."""
    secret = _get_secret()
    if secret is None or not uuid:
        return ""
    expiry = int(time.time()) + TOKEN_TTL_SECONDS
    return f"{expiry}.{_sign(uuid, expiry, secret)}"


def check_summary_token(uuid: str, token: Optional[str]) -> bool:
    """Return True if token authorizes generating a summary for this article.
    Every failure path returns False rather than raising: a malformed token is
    an ordinary occurrence on a public endpoint, not an error condition."""
    secret = _get_secret()
    if secret is None or not uuid or not token:
        return False
    expiry_str, _, signature = token.partition(".")
    if not signature:
        return False
    try:
        expiry = int(expiry_str)
    except ValueError:
        return False
    if expiry < time.time():
        return False
    # The expiry is part of the signed message, so a token cannot be given a
    # later expiry than the one it was minted with without breaking the MAC.
    return hmac.compare_digest(signature, _sign(uuid, expiry, secret))
