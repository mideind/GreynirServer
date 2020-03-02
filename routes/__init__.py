"""

    Greynir: Natural language processing for Icelandic

    Copyright (C) 2020 Miðeind ehf.

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

import threading
import time
import uuid
from functools import wraps
from datetime import datetime, timedelta

from flask import (
    Blueprint, jsonify, make_response, current_app, Response,
    abort, request, url_for, _request_ctx_stack
)
from werkzeug.exceptions import HTTPException, InternalServerError


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


# The following asynchronous support code is adapted from Miguel Grinberg's
# PyCon 2016 "Flask at Scale" tutorial: https://github.com/miguelgrinberg/flack

# A dictionary of currently living tasks
tasks = dict()
tasks_lock = threading.Lock()


@routes.before_app_first_request
def before_first_request():
    """ Start a background thread that cleans up old tasks """

    def clean_old_tasks():
        """ This function cleans up old tasks from an in-memory data structure """
        global tasks
        while True:
            # Only keep tasks that are running or that finished less than 5
            # minutes ago.
            five_min_ago = datetime.utcnow() - timedelta(minutes=5)
            with tasks_lock:
                tasks = {
                    task_id: task
                    for task_id, task in tasks.items()
                    if 't' not in task or task['t'] > five_min_ago
                }
            time.sleep(60)

    if not current_app.config['TESTING']:
        thread = threading.Thread(target=clean_old_tasks)
        thread.start()


def fancy_url_for(*args, **kwargs):
    """ url_for() replacement that works even when there is no request context """
    if "_external" not in kwargs:
        kwargs["_external"] = False
    reqctx = _request_ctx_stack.top
    if reqctx is None:
        if kwargs["_external"]:
            raise RuntimeError(
                "Cannot generate external URLs without a request context."
            )
        with current_app.test_request_context():
            return url_for(*args, **kwargs)
    return url_for(*args, **kwargs)


def async_task(f):
    """ This decorator transforms a sync route into an asynchronous one
        by running it in a background thread """

    @wraps(f)
    def wrapped(*args, **kwargs):

        # Assign a unique id to the asynchronous task
        task_id = uuid.uuid4().hex

        def progress(ratio):
            """ Function to call from the worker task to indicate progress. """
            # ratio is a float from 0.0 (just started) to 1.0 (finished)
            tasks[task_id]["progress"] = ratio

        def task(app, environ):
            # Create a request context similar to that of the original request
            # so that the task can have access to flask.g, flask.request, etc.
            this_task = tasks[task_id]
            with app.request_context(environ):
                try:
                    # Run the route function and record the response
                    this_task["rv"] = f(*args, progress_func=progress, **kwargs)
                except HTTPException as e:
                    this_task["rv"] = current_app.handle_http_exception(e)
                except Exception as e:
                    # The function raised an exception, so we set a 500 error
                    this_task["rv"] = InternalServerError()
                    if current_app.debug:
                        # We want to find out if something happened so reraise
                        raise
                finally:
                    # We record the time of the response, to help in garbage
                    # collecting old tasks
                    this_task["t"] = datetime.utcnow()

        # Record the task, and then launch it
        with tasks_lock:
            tasks[task_id] = {
                "progress": 0.0,
            }
            new_task = threading.Thread(
                target=task,
                args=(
                    current_app._get_current_object(),
                    request.environ,
                )
            )
        new_task.start()

        # Return a 202 response, with a link that the client can use to
        # obtain task status
        return (
            json.dumps(dict(progress=0.0)),
            202,
            {
                "Location": fancy_url_for("routes.get_status", task=task_id),
                "Content-Type": "application/json; charset=utf-8",
            }
        )

    return wrapped


@routes.route('/status/<task>', methods=['GET'])
def get_status(task):
    """ Return status about an asynchronous task. If this request returns a 202
        status code, it means that task hasn't finished yet. Else, the response
        from the task is returned. """
    task_id = task
    with tasks_lock:
        task = tasks.get(task_id)
        if task is None:
            abort(404)
        if "rv" in task:
            # Task completed
            return task["rv"]
        # Not completed: report progress
        return (
            json.dumps(dict(progress=task["progress"])),
            202,
            {
                "Location": fancy_url_for("routes.get_status", task=task_id),
                "Content-Type": "application/json; charset=utf-8",
            }
        )


# Import routes from other files
from .api import *
from .main import *
from .loc import *
from .news import *
from .people import *
from .stats import *
from nn.routes import *
