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


_LINE_COLORS = frozenset(("#f00", "#00f", "#0f0", "#ff0", "#0ff", "#f0f"))


@routes.route("/wordfreq", methods=["GET", "POST"])
@cache.cached(timeout=60 * 60 * 4, key_prefix="wordfreq", query_string=True)
def wordfreq():
    """ Return word frequency chart data for a given time period. """
    resp = dict(err=True)

    # Words parameter should be 1-6 diff. word lemmas
    warg = request.args.get("words")
    if not warg:
        return better_jsonify(**resp)
    words = [w.strip() for w in warg.split(",")][:6]  # Max 6 words

    # Create datetime objects from query string args
    try:
        date_from = datetime.strptime(request.args.get("date_from"), "%d/%m/%Y")
        date_to = datetime.strptime(request.args.get("date_to"), "%d/%m/%Y")
    except Exception as e:
        print(e)
        return better_jsonify(**resp)

    days = (date_to - date_from).days
    colors = list(_LINE_COLORS)

    # Generate date labels
    labels = [i for i in range(0, days + 1)]

    # Create datasets to be loaded into front-end chart
    data = dict(labels=labels, datasets=[])
    for w in words:
        ds = dict(label=w, fill=False, lineTension=0)
        ds["borderColor"] = ds["backgroundColor"] = colors.pop(0)
        ds["data"] = [random.randint(0, 50) for i in range(0, days + 1)]
        data["datasets"].append(ds)
    resp["data"] = data
    resp["err"] = False

    return better_jsonify(**resp)
