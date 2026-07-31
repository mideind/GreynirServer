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


    Summary generation policy

    Generating an article summary calls a paid LLM API, so /summary.api must
    not let an anonymous caller trigger generation merely by naming an article
    id. Reading an already stored summary stays open to everyone; *generating*
    a missing one requires both a valid token and a recent enough article.

    The two checks answer different questions and neither subsumes the other:

      - the token asks "did this caller come from the article's own page?",
        which stops direct enumeration of the corpus;
      - the age limit asks "is this article one we would ever summarise?",
        which bounds the total work available to any caller at all.

    The age limit is the sturdier of the two. A scraper can rotate IPs, cloud
    providers and user agents, and can parse a token out of the page HTML -
    all three were observed on 2026-07-31 - but it cannot make an old article
    young. Since only a few hundred articles are published per day, capping
    generation to a recent window bounds the daily spend regardless of who is
    asking or how many addresses they have.

    Articles outside the window still serve any summary already stored, so
    the 253,474 older articles that have one keep showing it.

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
from datetime import datetime, timedelta, timezone


# How long a minted token remains valid. The page asks for its summary as
# soon as it loads, so this only has to cover render time plus the client's
# first XHR. Five minutes is already generous.
TOKEN_TTL_SECONDS = 300

# Truncated HMAC-SHA256. 128 bits is far beyond forgeable for a value that
# expires within minutes, and keeps the token short in the page markup.
_SIGNATURE_BYTES = 16

_ENV_VAR = "GREYNIR_SUMMARY_SECRET"

# Only articles published within this many days are summarised on demand.
# Override with GREYNIR_SUMMARY_MAX_AGE_DAYS; 0 or less disables generation
# entirely, which is a usable emergency brake.
#
# Seven days is far more than the pipeline produces - a few hundred articles
# a day - while refusing 99.6% of what the 2026-07-31 scraper asked for. It
# was crawling each page's "similar articles" list, which is dominated by old
# material: of the summaries it triggered in three hours, 94% were for
# articles over a year old and only 126 rows were inside a seven day window.
DEFAULT_MAX_ARTICLE_AGE_DAYS = 7

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


def max_article_age_days() -> int:
    """Return the configured generation window, in days. Read per call rather
    than cached, so the value can be changed with a restart alone."""
    raw = os.environ.get("GREYNIR_SUMMARY_MAX_AGE_DAYS", "").strip()
    if not raw:
        return DEFAULT_MAX_ARTICLE_AGE_DAYS
    try:
        return int(raw)
    except ValueError:
        logging.error(
            "GREYNIR_SUMMARY_MAX_AGE_DAYS is not an integer: %r. Using %d.",
            raw,
            DEFAULT_MAX_ARTICLE_AGE_DAYS,
        )
        return DEFAULT_MAX_ARTICLE_AGE_DAYS


def article_is_recent(timestamp: Optional[datetime]) -> bool:
    """Return True if an article of this age may have a summary generated.
    An unknown timestamp is treated as too old: the whole point is to bound
    what can be generated, so anything we cannot date is refused."""
    if timestamp is None:
        return False
    days = max_article_age_days()
    if days <= 0:
        return False
    # Articles read back through DateTimeUtc carry UTC, but normalise anyway
    # so a naive value cannot raise on comparison
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp > datetime.now(timezone.utc) - timedelta(days=days)


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
