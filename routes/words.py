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

from tokenizer import TOK

from reynir.bindb import BIN_Db
from reynir.bintokenizer import tokenize

from db import SessionContext, desc
from db.models import Article, Word, Root
from db.queries import WordFrequencyQuery


@routes.route("/words")
def words():
    """ Handler for word frequency page. """
    return render_template("words/words.html", title="Orð")


_LINE_COLORS = frozenset(
    ("#006eff", "#eb3732", "#00b450", "#ffb400", "#4600c8", "#f0f")
)

# More human readble description of word categories
CAT_DESC = {
    "kk": "kk. no.",
    "kvk": "kvk. no.",
    "hk": "hk. no.",
    "lo": "lo.",
    "so": "so.",
    "person_kk": "kk. nafn",
    "person_kvk": "kvk. nafn",
    "entity": "fyrirbæri",
    "??": "óþekkt",
}

_VALID_TOKENS = frozenset((TOK.WORD, TOK.PERSON))
_VALID_WCATS = frozenset(
    ("kk", "kvk", "hk", "lo", "so", "person_kk", "person_kvk", "entity")
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

    # Words parameter should be one or more word lemmas (w. optional category)
    warg = request.args.get("words")
    if not warg:
        return better_jsonify(**resp)
    # Tokenize words
    tokens = list(filter(lambda x: x.kind in _VALID_TOKENS, tokenize(warg)))

    # Create word/cat pairs from each token
    def cat4token(t):
        w = t.txt
        if t.kind == TOK.WORD:
            val = list(filter(lambda m: m.stofn == m.ordmynd, t.val)) or t.val
            cat = val[0].ordfl if len(val) else "??"
            w = val[0].stofn if len(val) else t.txt
        elif t.kind == TOK.PERSON:
            cat = "person_kk"
        return (w, cat)

    words = [cat4token(t) for t in tokens]

    # Filter all words not in allowed category
    words = list(filter(lambda x: x[1] in _VALID_WCATS, words))

    # Split on comma or whitespace, limit to max 6 words
    # warg = warg.strip().replace("  ", " ").replace(",", " ")
    # words = [w.strip() for w in warg.split()][:6]
    # # Word categories can be specified thus: "hestur:kk"
    # words = [tuple(w.split(":")) for w in words]

    # with BIN_Db.get_db() as db:

    #     def cat4word(w):
    #         _, meanings = db.lookup_word(w, auto_uppercase=True)
    #         if meanings:
    #             # Give precedence to lemmas, e.g. interpret "reima" as
    #             # verb rather than gen. pl. of fem. noun "reim"
    #             lemmas = list(filter(lambda x: x.stofn == w, meanings))
    #             m = lemmas[0] if lemmas else meanings[0]
    #             return m.stofn.replace("-", ""), m.ordfl
    #         return w, "??"

    #     # Get word category (ordfl) for each word, if needed
    #     for i, w in enumerate(words):
    #         if len(w) < 2 or w[1] not in _VALID_WCATS:
    #             words[i] = tuple(cat4word(w[0]))

    colors = list(_LINE_COLORS)

    # Generate date labels
    now = datetime.utcnow()
    delta = date_to - date_from
    with changedlocale(category="LC_TIME"):
        # Group by week if period longer than 3 months
        if delta.days >= 90:
            timeunit = "week"

            label_dates = [
                (
                    (date_from + timedelta(days=i * 7)),
                    (date_from + timedelta(days=(i * 7) + 6)),
                )
                for i in range(int((delta.days + 1) / 7))
            ]
            # Construct elegant week date labels w. no superfluous information
            labels = []
            for (d1, d2) in label_dates:
                if d1.month == d2.month:
                    d1fmt = "%-d."
                    d2fmt = "%-d. %b"
                else:
                    d1fmt = d2fmt = "%-d. %b"
                if d1.year != now.year and d1.year != d2.year:
                    d1fmt += " %Y"
                if d2.year != now.year:
                    d2fmt += " %Y"
                labels.append("{0}-{1}".format(d1.strftime(d1fmt), d2.strftime(d2fmt)))
        # Group by day
        else:
            timeunit = "day"
            label_dates = [date_from + timedelta(days=i) for i in range(delta.days)]
            labels = [
                d.strftime("%-d. %b")
                if d.year == now.year
                else d.strftime("%-d. %b %Y")
                for d in label_dates
            ]
            label_dates = [d.strftime("%Y-%m-%d") for d in label_dates]

    # Create datasets for front-end chart
    with SessionContext(commit=False) as session:
        data = dict(labels=labels, labelDates=label_dates, datasets=[])
        for w in words:
            # Look up frequency of word for the given period
            (wd, cat) = w
            res = WordFrequencyQuery.frequency(
                wd,
                cat,
                date_from,
                date_to,
                timeunit=timeunit,
                enclosing_session=session,
            )
            # Generate data and config for chart
            label = "{0} ({1})".format(wd, CAT_DESC.get(cat))
            ds = dict(label=label, fill=False, lineTension=0)
            ds["borderColor"] = ds["backgroundColor"] = colors.pop(0)
            ds["data"] = [r[1] for r in res]
            ds["word"] = "{0}:{1}".format(wd, cat)
            data["datasets"].append(ds)

    # Create response
    resp["err"] = False
    resp["data"] = data
    # Update word list client-side
    resp["words"] = ", ".join([":".join(w) for w in words])

    return better_jsonify(**resp)


def _parse_words(wstr):
    """ Parse string of the form 'w1:cat1, w2:cat2 ...' into list of tuples. """
    if not wstr:
        return None
    ws = wstr.strip()
    if not ws:
        return None
    words = [w.strip() for w in ws.split(",")]
    return [w.split(":") for w in words]


@routes.route("/wordfreq_details", methods=["GET", "POST"])
def wordfreq_details():
    """ Return list of articles containing certain words over a given period. """
    resp = dict(err=True)

    words = _parse_words(request.args.get("words"))
    if not words:
        return better_jsonify(**resp)

    # Parse date args
    try:
        date_fmt = "%Y-%m-%d"
        date_from = datetime.strptime(request.args.get("date_from"), date_fmt)
        dto = request.args.get("date_to")
        if dto:
            date_to = datetime.strptime(dto, date_fmt)
        else:
            # If only one date provided, assume it's a period spanning a single day
            date_to = date_from + timedelta(days=1)
    except Exception as e:
        logging.warning("Failed to parse date arg: {0}".format(e))
        return better_jsonify(**resp)

    # Fetch articles for each word for given period
    wlist = list()
    colors = list(_LINE_COLORS)
    with SessionContext(read_only=True) as session:
        for wd, cat in words:
            q = (
                session.query(Word.stem, Article.id, Article.heading, Root.domain)
                .join(Article, Article.id == Word.article_id)
                .filter(Article.timestamp >= date_from)
                .filter(Article.timestamp < date_to)
                .filter(Word.stem == wd)
                .filter(Word.cat == cat)
                .join(Root)
                .order_by(desc(Article.timestamp))
            )
            articles = [{"id": a[1], "heading": a[2], "domain": a[3]} for a in q.all()]
            wlist.append(
                {"word": wd, "cat": cat, "articles": articles, "color": colors.pop(0)}
            )

    resp["err"] = False
    resp["payload"] = render_template("words/details.html", words=wlist)
    return better_jsonify(**resp)
