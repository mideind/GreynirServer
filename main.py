#!/usr/bin/env python3
"""

    Greynir: Natural language processing for Icelandic

    Web server main module

    Copyright (C) 2023 Miðeind ehf.
    Original author: Vilhjálmur Þorsteinsson

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


    This is the main module of the Greynir web application. It uses Flask
    as its web server and templating engine. In production, this module is
    typically run inside Gunicorn (using servlets) under nginx or a
    compatible WSGI HTTP(S) server. For development, it can be run
    directly from the command line and accessed through port 5000.

    Flask routes are imported from routes/*

"""

from typing import Dict, List, Pattern, Optional, Tuple, Union, Any, cast

import sys
import re
import logging
from os import environ as ENV
from platform import system as os_name
from pathlib import Path
from datetime import datetime

from flask import Flask, send_from_directory, render_template
from flask.wrappers import Response
from flask_caching import Cache  # type: ignore
from flask_cors import CORS  # type: ignore

from werkzeug.middleware.proxy_fix import ProxyFix

from dotenv import load_dotenv

import reynir
from reynir.bindb import GreynirBin
from reynir.fastparser import Fast_Parser

from settings import Settings, ConfigError
from article import Article as ArticleProxy
from utility import (
    CONFIG_DIR,
    QUERIES_DIALOGUE_DIR,
    QUERIES_GRAMMAR_DIR,
    QUERIES_UTIL_GRAMMAR_DIR,
)

from reynir.version import __version__ as greynir_version
from tokenizer.version import __version__ as tokenizer_version


# RUNNING_AS_SERVER is True if we're executing under nginx/Gunicorn,
# but False if the program was invoked directly as a Python main module.
RUNNING_AS_SERVER = __name__ != "__main__"

# Load variables from '.env' file into environment
load_dotenv()

# Initialize and configure Flask app
app = Flask(__name__)

# Enable Cross Origin Resource Sharing for app
cors = CORS(app)
app.config["CORS_HEADERS"] = "Content-Type"

# Fix access to client remote_addr when running behind proxy
setattr(app, "wsgi_app", ProxyFix(app.wsgi_app))  # type: ignore

cast(Any, app).json.ensure_ascii = False  # We're fine with using Unicode/UTF-8
app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024  # 1 MB, max upload file size
app.config["CACHE_NO_NULL_WARNING"] = True  # Don't warn if caching is disabled

# Only auto-reload templates if we're not running as a production server
app.config["TEMPLATES_AUTO_RELOAD"] = not RUNNING_AS_SERVER

# Push application context to give view functions, error handlers,
# and other functions access to app instance via current_app
app.app_context().push()

# Set up caching
# Caching is disabled if app is invoked via the command line
cache_type = "SimpleCache" if RUNNING_AS_SERVER else "null"
app.config["CACHE"] = Cache(app, config={"CACHE_TYPE": cache_type})

# Register blueprint routes
from routes import routes, max_age  # type: ignore

app.register_blueprint(routes)


# Utilities for Flask/Jinja2 formatting of numbers using the Icelandic locale
def make_pattern(rep_dict: Dict[str, str]) -> Pattern[str]:
    return re.compile("|".join([re.escape(k) for k in rep_dict.keys()]), re.M)


def multiple_replace(
    s: str, rep_dict: Dict[str, str], pattern: Optional[Pattern[str]] = None
) -> str:
    """Perform multiple simultaneous replacements within string"""
    if pattern is None:
        pattern = make_pattern(rep_dict)
    return pattern.sub(lambda x: rep_dict[x.group(0)], s)


_REP_DICT_IS = {",": ".", ".": ","}
_PATTERN_IS = make_pattern(_REP_DICT_IS)


@app.template_filter("format_is")
def format_is(r: float, decimals: int = 0) -> str:
    """Flask/Jinja2 template filter to format a number for the Icelandic locale"""
    fmt = "{0:,." + str(decimals) + "f}"
    return multiple_replace(fmt.format(float(r)), _REP_DICT_IS, _PATTERN_IS)


@app.template_filter("format_ts")
def format_ts(ts: datetime) -> str:
    """Flask/Jinja2 template filter to format a timestamp as YYYY-MM-DD HH:MM"""
    return str(ts)[0:16]


# Flask cache busting for static .css and .js files
@app.url_defaults
def hashed_url_for_static_file(
    endpoint: str, values: Dict[str, Union[int, str]]
) -> None:
    """Add a ?h=XXX parameter to URLs for static .js and .css files,
    where XXX is calculated from the file timestamp"""

    def static_file_hash(filepath: Path):
        """Obtain a timestamp for the given file"""
        return int(filepath.stat().st_mtime)

    if "static" == endpoint or endpoint.endswith(".static"):
        filename = values.get("filename")
        assert isinstance(filename, str)
        if filename and filename.endswith((".js", ".css")):
            # if "." in endpoint:  # has higher priority
            #     blueprint = endpoint.rsplit(".", 1)[0]
            # else:
            #     blueprint = request.blueprint  # can be None too

            # if blueprint:
            #     static_folder = app.blueprints[blueprint].static_folder
            # else:
            static_folder = app.static_folder or "."
            param_name = "h"
            # Add underscores in front of the param name until it is unique
            while param_name in values:
                param_name = "_" + param_name
            values[param_name] = static_file_hash(Path(static_folder, filename))


@app.route("/static/fonts/<path:path>")
@max_age(seconds=24 * 60 * 60)  # Client should cache font for 24 hours
def send_font(path: str) -> Response:
    return send_from_directory(str(Path("static", "fonts")), path)


# Custom 404 error handler
@app.errorhandler(404)
def page_not_found(_) -> Tuple[str, int]:
    """Return a custom 404 error"""
    return render_template("404.html"), 404


# Custom 500 error handler
@app.errorhandler(500)
def server_error(_) -> Tuple[str, int]:
    """Return a custom 500 error"""
    return render_template("500.html"), 500


@app.context_processor
def inject_nn_bools() -> Dict[str, Union[str, bool]]:
    """Inject bool switches for neural network features"""
    return dict(
        nn_parsing_enabled=Settings.NN_PARSING_ENABLED,
        nn_translate_enabled=Settings.NN_TRANSLATION_ENABLED,
    )


# Initialize the main module
try:
    # Read configuration file
    Settings.read(str(Path("config", "Greynir.conf")))
except ConfigError as e:
    logging.error("Greynir did not start due to a configuration error:\n{0}".format(e))
    sys.exit(1)

if Settings.DEBUG:
    print(
        "\nStarting Greynir web app at {0} with debug={1}, "
        "host={2}:{3}, db_host={4}:{5}\n"
        "Python {6} on {7}\n{8}".format(
            datetime.utcnow(),
            Settings.DEBUG,
            Settings.HOST,
            Settings.PORT,
            Settings.DB_HOSTNAME,
            Settings.DB_PORT,
            sys.version,
            os_name(),
            "GreynirPackage {0} - Tokenizer {1}".format(
                greynir_version, tokenizer_version
            ),
        )
    )
    # Clobber Settings.DEBUG in GreynirPackage
    reynir.Settings.DEBUG = True


if not RUNNING_AS_SERVER:
    if ENV.get("GREYNIR_ATTACH_PTVSD"):
        # Attach to the VSCode PTVSD debugger, enabling remote debugging via SSH
        # import ptvsd

        # ptvsd.enable_attach()
        # ptvsd.wait_for_attach()  # Blocks execution until debugger is attached
        ptvsd_attached = True
        print("Attached to PTVSD")
    else:
        ptvsd_attached = False

    # Run a default Flask web server for testing if invoked directly as a main program

    # Additional files that should cause a reload of the web server application
    # Note: Greynir.grammar is automatically reloaded if its timestamp changes
    extra_files: List[str] = []

    # Reload web server when config files change
    extra_files.extend(str(p) for p in CONFIG_DIR.resolve().glob("*.conf"))
    # Config files for GreynirPackage
    extra_files.extend(
        str(p)
        for p in (Path(reynir.__file__).parent.resolve() / "config").glob("*.conf")
    )

    # Add grammar files
    extra_files.extend(str(p) for p in QUERIES_GRAMMAR_DIR.resolve().glob("*.grammar"))
    extra_files.extend(
        str(p) for p in QUERIES_UTIL_GRAMMAR_DIR.resolve().glob("*.grammar")
    )
    # Add dialogue TOML files
    extra_files.extend(str(p) for p in QUERIES_DIALOGUE_DIR.resolve().glob("*.toml"))

    # Add ord.compressed from GreynirPackage
    # extra_files.append(
    #     str(
    #         (
    #             greynirpackage_dir / "src" / "reynir" / "resources" / "ord.compressed"
    #         ).resolve()
    #     )
    # )

    from socket import error as socket_error
    import errno

    try:
        # Suppress information log messages from Werkzeug
        werkzeug_log = logging.getLogger("werkzeug")
        if werkzeug_log:
            werkzeug_log.setLevel(logging.WARNING)
        # Run the Flask web server application
        app.run(
            host=Settings.HOST,
            port=Settings.PORT,
            debug=Settings.DEBUG,
            use_reloader=not ptvsd_attached,
            extra_files=extra_files,
        )
    except socket_error as e:
        if e.errno == errno.EADDRINUSE:  # Address already in use
            logging.error(
                "Another application is already running at host {0}:{1}".format(
                    Settings.HOST, Settings.PORT
                )
            )
            sys.exit(1)
        else:
            raise
    finally:
        ArticleProxy.cleanup()
        GreynirBin.cleanup()

else:
    app.config["PRODUCTION"] = True

    # Suppress information log messages from Werkzeug
    werkzeug_log = logging.getLogger("werkzeug")
    if werkzeug_log:
        werkzeug_log.setLevel(logging.WARNING)

    # Log our startup
    version = sys.version.replace("\n", " ")
    log_str = (
        f"Greynir instance starting with "
        f"host={Settings.HOST}:{Settings.PORT}, "
        f"db_host={Settings.DB_HOSTNAME}:{Settings.DB_PORT} "
        f"on Python {version}"
    )
    logging.info(log_str)
    print(log_str)
    sys.stdout.flush()

    # Running as a server module: pre-load the grammar into memory
    with Fast_Parser() as _:
        pass
