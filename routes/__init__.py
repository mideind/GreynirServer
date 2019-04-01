"""

    Routes for the Greynir Flask web application.

"""


from flask import Blueprint, jsonify, make_response, current_app, Response
from functools import wraps


# Maximum length of incoming GET/POST parameters
_MAX_TEXT_LENGTH = 16384
_MAX_TEXT_LENGTH_VIA_URL = 512

_MAX_URL_LENGTH = 512
_MAX_UUID_LENGTH = 36



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


def bool_from_request(rq, name, default=False):
    """ Get a boolean from JSON encoded in a request form """
    b = rq.form.get(name)
    if b is None:
        b = rq.args.get(name)
    if b is None:
        # Not present in the form: return the default
        return default
    return isinstance(b, str) and b.lower() in {"true", "1", "yes"}


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
