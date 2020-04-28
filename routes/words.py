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
import logging

from . import routes, better_jsonify, cache

from datetime import datetime, timedelta
from flask import request, render_template

from settings import changedlocale

from reynir.bindb import BIN_Db

from db import SessionContext, desc
from db.models import Article, Root, Location, ArticleTopic, Topic
from db.queries import WordFrequencyQuery


@routes.route("/words")
def words():
    """ Handler for word frequency page. """
    return render_template("words.html", title="Orð")


_LINE_COLORS = frozenset(
    ("#006eff", "#eb3732", "#00b450", "#ffb400", "#4600c8", "#f0f")
)


@routes.route("/wordfreq", methods=["GET", "POST"])
@cache.cached(timeout=60 * 60 * 4, key_prefix="wordfreq", query_string=True)
def wordfreq():
    """ Return word frequency chart data for a given time period. """
    resp = dict(err=True)

    # Create datetime objects from query string args
    try:
        date_fmt = "%Y-%m-%d"
        date_from = datetime.strptime(request.args.get("date_from"), date_fmt)
        date_to = datetime.strptime(request.args.get("date_to"), date_fmt)
    except Exception as e:
        logging.warning("Failed to parse date arg: {0}".format(e))
        return better_jsonify(**resp)

    # Words parameter should be 1-6 diff. word lemmas (w. optional category)
    warg = request.args.get("words")
    if not warg:
        return better_jsonify(**resp)

    # Split on comma or whitespace, limit to max 6 words
    warg = warg.strip().replace("  ", " ").replace(",", " ")
    words = [w.strip() for w in warg.split()][:6]
    # Word categories can be specified thus: "maður:kk"
    words = [tuple(w.split(":")) for w in words]

    def cat4word(w):
        with BIN_Db.get_db() as db:
            meanings = db.meanings(w)
            if meanings:
                return meanings[0].ordfl
        return "hk"

    # Get word category (ordfl) for each word, if needed
    valid_cats = ["kk", "kvk", "hk", "lo", "so"]
    for i, w in enumerate(words):
        if len(w) < 2 or w[1] not in valid_cats:
            words[i] = (w[0], cat4word(w[0]))

    colors = list(_LINE_COLORS)

    # Generate date labels
    now = datetime.utcnow()
    delta = date_to - date_from
    labels = [date_from + timedelta(days=i) for i in range(delta.days + 1)]
    with changedlocale(category="LC_TIME"):
        labels = [
            l.strftime("%-d. %b") if l.year == now.year else l.strftime("%-d. %b %Y")
            for l in labels
        ]

    # Create datasets for front-end chart
    with SessionContext(commit=False) as session:
        data = dict(labels=labels, datasets=[])
        for w in words:
            # Look up frequency of word for the given period
            res = WordFrequencyQuery.fetch(
                w[0], w[1], date_from, date_to, enclosing_session=session
            )
            # Generate data and config for chart
            ds = dict(label=w[0], fill=False, lineTension=0)
            ds["borderColor"] = ds["backgroundColor"] = colors.pop(0)
            ds["data"] = [r[1] or 0 for r in res]
            data["datasets"].append(ds)

    # Create response
    resp["err"] = False
    resp["data"] = data
    # Update word list client-side
    resp["words"] = ", ".join([":".join(w) for w in words])

    return better_jsonify(**resp)
