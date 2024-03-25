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


    This module contains all routes for the Greynir Flask web application.
    It also contains a number of utility functions and decorators,
    including @async_task which encapsulates a route in an asynchronous
    wrapper.

"""

from typing import Dict, Callable, Union, Optional, Any

import threading
import time
import uuid
import json
from functools import wraps
from datetime import timedelta, datetime, timezone

from flask import (
    Blueprint,
    jsonify,
    make_response,
    current_app,
    abort,
    request,
    url_for,
)
from flask.wrappers import Response, Request
from flask import _request_ctx_stack  # type: ignore
from flask.ctx import RequestContext
from werkzeug.datastructures import FileStorage
from werkzeug.exceptions import HTTPException, InternalServerError
import flask_caching


CacheableFunc = Callable[..., Union[str, Response]]
ProgressFunc = Callable[[float], None]

# Maximum length of incoming GET/POST parameters
MAX_TEXT_LENGTH = 16384
MAX_TEXT_LENGTH_VIA_URL = 512

MAX_URL_LENGTH = 512
MAX_UUID_LENGTH = 36

_TRUTHY = frozenset(("true", "1", "yes"))

cache: flask_caching.Cache = current_app.config["CACHE"]
routes: Blueprint = Blueprint("routes", __name__)


def max_age(
    seconds: int,
) -> Callable[[CacheableFunc], Callable[..., Response]]:
    """Caching decorator for Flask - augments response
    with a max-age cache header"""

    def decorator(f: CacheableFunc) -> Callable[..., Response]:
        @wraps(f)
        def decorated_function(*args: Any, **kwargs: Any) -> Response:
            resp = f(*args, **kwargs)
            if not isinstance(resp, Response):
                resp = make_response(resp)
            resp.cache_control.max_age = seconds  # type: ignore
            return resp

        return decorated_function

    return decorator


def restricted(f: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator to return 403 Forbidden if not running in debug mode"""

    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any):
        if not current_app.config["DEBUG"]:
            return abort(403)
        return f(*args, **kwargs)

    return decorated_function


def bool_from_request(rq: Request, name: str, default: bool = False) -> bool:
    """Get a boolean from JSON encoded in a request form"""
    b = rq.form.get(name)
    if b is None:
        b = rq.args.get(name)
    if b is None:
        # Not present in the form: return the default
        return default
    return isinstance(b, str) and b.lower() in _TRUTHY


_NATLANG_PERIODS = {"day": 1, "week": 7, "month": 30}


def days_from_period_arg(arg: str, default: int = 1) -> int:
    return _NATLANG_PERIODS.get(arg, default)


def better_jsonify(**kwargs: Any) -> Response:
    """Ensure that the Content-Type header includes 'charset=utf-8'"""
    resp: Response = jsonify(**kwargs)
    resp.headers["Content-Type"] = "application/json; charset=utf-8"
    return resp


def text_from_request(
    rq: Request, *, post_field: Optional[str] = None, get_field: Optional[str] = None
) -> str:
    """Return text passed in a HTTP request, either using GET or POST.
    When using GET, the default parameter name is 't'. This can
    be overridden using the get_field parameter.
    When using POST, the default form field name is 'text'. This can
    be overridden using the post_field paramter.
    """
    if rq.method == "POST":
        if rq.headers.get("Content-Type") == "text/plain":
            # Accept plain text POSTs, UTF-8 encoded.
            # Example usage:
            # curl -d @example.txt https://greynir.is/postag.api \
            #     --header "Content-Type: text/plain"
            text = rq.data.decode("utf-8")
        else:
            # Also accept form/url-encoded requests:
            # curl -d "text=Í dag er ágætt veður en mikil hálka er á götum." \
            #     https://greynir.is/postag.api
            text = rq.form.get(post_field or "text", "")
        text = text[0:MAX_TEXT_LENGTH]
    elif rq.method == "GET":
        text = rq.args.get(get_field or "t", "")[0:MAX_TEXT_LENGTH_VIA_URL]
    else:
        # Unknown/unsupported method
        text = ""

    return text


# Import routes from other files
from .api import *
from .main import *
from .news import *
from .people import *
from .loc import *
from .words import *
from .stats import *
from .salescloud import *
from nn.api import *
