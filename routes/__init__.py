"""

    Greynir: Natural language processing for Icelandic

    Copyright (C) 2019 Miðeind ehf.

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

"""

from flask import Blueprint, jsonify, make_response, current_app, Response
from functools import wraps


# Maximum length of incoming GET/POST parameters
_MAX_TEXT_LENGTH = 16384
_MAX_TEXT_LENGTH_VIA_URL = 512

_MAX_URL_LENGTH = 512
_MAX_UUID_LENGTH = 36

_TRUTHY = frozenset(("true", "1", "yes"))

cache = current_app.config["CACHE"]
routes = Blueprint("routes", __name__)


def max_age(seconds):
    """ Caching decorator for Flask - augments response with a max-age cache header """

    def decorator(f):

        @wraps(f)
        def decorated_function(*args, **kwargs):
            resp = f(*args, **kwargs)
            if not isinstance(resp, Response):
                resp = make_response(resp)
            resp.cache_control.max_age = seconds
            return resp

        return decorated_function

    return decorator


def restricted(f):
    """ Decorator to return 403 Forbidden if not running in debug mode """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_app.config["DEBUG"]:
            return abort(403)
        return f(*args, **kwargs)

    return decorated_function


def bool_from_request(rq, name, default=False):
    """ Get a boolean from JSON encoded in a request form """
    b = rq.form.get(name)
    if b is None:
        b = rq.args.get(name)
    if b is None:
        # Not present in the form: return the default
        return default
    return isinstance(b, str) and b.lower() in _TRUTHY


def better_jsonify(**kwargs):
    """ Ensure that the Content-Type header includes 'charset=utf-8' """
    resp = jsonify(**kwargs)
    resp.headers["Content-Type"] = "application/json; charset=utf-8"
    return resp


def text_from_request(request, *, post_field=None, get_field=None):
    """ Return text passed in a HTTP request, either using GET or POST.
        When using GET, the default parameter name is 't'. This can
        be overridden using the get_field parameter.
        When using POST, the default form field name is 'text'. This can
        be overridden using the post_field paramter.
    """
    if request.method == "POST":
        if request.headers.get("Content-Type") == "text/plain":
            # Accept plain text POSTs, UTF-8 encoded.
            # Example usage:
            # curl -d @example.txt https://greynir.is/postag.api \
            #     --header "Content-Type: text/plain"
            text = request.data.decode("utf-8")
        else:
            # Also accept form/url-encoded requests:
            # curl -d "text=Í dag er ágætt veður en mikil hálka er á götum." \
            #     https://greynir.is/postag.api
            text = request.form.get(post_field or "text", "")
        text = text[0:_MAX_TEXT_LENGTH]
    else:
        text = request.args.get(get_field or "t", "")[0:_MAX_TEXT_LENGTH_VIA_URL]

    return text


# Import routes from other files
from .api import *
from .main import *
from .loc import *
from .news import *
from .people import *
from .stats import *
from nn.routes import *
