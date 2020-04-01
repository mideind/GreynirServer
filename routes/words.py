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


    Word-frequency-related routes

"""

import random

from . import routes, better_jsonify, cache

from datetime import datetime, timedelta
from flask import request, render_template

from settings import changedlocale

from db import SessionContext, desc
from db.models import Article, Root, Location, ArticleTopic, Topic


@routes.route("/words")
def words():
    """ Handler for word frequency page. """

    return render_template("words.html")


@routes.route("/wordfreq", methods=["GET", "POST"])
@cache.cached(timeout=60 * 60 * 4, key_prefix="wordfreq", query_string=True)
def wordfreq():
    """ Return word frequency data for a given time period. """
    resp = dict(err=True)

    warg = request.args.get("words")
    if not warg:
        return better_jsonify(**resp)
    words = [w.strip() for w in warg.split(",")]

    # Parse date arguments
    try:
        date_from = datetime.strptime(request.args.get("date_from"), "%Y-%m-%d")
        date_to = datetime.strptime(request.args.get("date_to"), "%Y-%m-%d")
    except Exception as e:
        print(e)
        return better_jsonify(**resp)

    # Fetch data
    delta = date_to - date_from
    days = delta.days

    wdata = list()
    for w in words:
        d = [random.randint(0, 30) for i in range(0, days + 1)]
        wdata.append(d)

    resp["data"] = wdata
    resp["err"] = False

    return better_jsonify(**resp)
