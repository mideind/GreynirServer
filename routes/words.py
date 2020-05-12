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
    """ Handler for word frequency main page. """
    return render_template("words/words.html", title="Orð")


# Word categories permitted in word frequency search
_VALID_WCATS = frozenset(
    ("kk", "kvk", "hk", "lo", "so", "person_kk", "person_kvk", "entity")
)

# More human readble description of word categories
CAT_UNKNOWN = "??"
CAT_DESC = {
    "kk": "kk. no.",
    "kvk": "kvk. no.",
    "hk": "hk. no.",
    "lo": "lo.",
    "so": "so.",
    "person_kk": "kk. nafn",
    "person_kvk": "kvk. nafn",
    "entity": "fyrirbæri",
    CAT_UNKNOWN: "óþekkt",
}

# Tokens that should not be ignored
_VALID_TOKENS = frozenset((TOK.WORD, TOK.PERSON, TOK.ENTITY))

# Max number of words to request frequency data for simultaneously
_MAX_NUM_WORDS = 6

# Max period length before grouping chart stats by week
_SHOW_WEEKS_CUTOFF = 90  # days

# Word frequency chart line colors (Miðeind colors)
_LINE_COLORS = frozenset(
    ("#006eff", "#eb3732", "#00b450", "#ffb400", "#4600c8", "#f0f")
)


def _str2words(wstr, separate_on_whitespace=False):
    """ Parse string of the form 'w1:cat1, w2:cat2, ...' into a list
        of word/category tuples. """
    if not wstr:
        return None
    ws = wstr.strip()
    if not ws:
        return None
    words = [w.strip() for w in ws.split(",")]
    if separate_on_whitespace:
        words = " ".join(words).split()
    return [
        w.split(":") if len(w.split(":")) == 2 else (w, CAT_UNKNOWN) for w in words
    ][:_MAX_NUM_WORDS]


def _words2str(words):
    """ Create comma-separated string from (word,cat) tuple list,
        e.g. "[(a,b),(c,d)] -> "a:b, c:d". """
    return ", ".join([":".join(w[:2]) if len(w) >= 2 else (w, None) for w in words])


def _desc4word(wc):
    """ Create a human-friendly description string for a word/category tuple. """
    return "{0} ({1})".format(wc[0], CAT_DESC.get(wc[1]))


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

    # Words param should contain one or more word lemmas (w. optional category)
    warg = request.args.get("words")
    if not warg:
        return better_jsonify(**resp)

    # Get the list of specified cats for each word lemma

    wds, spec_cats = zip(*_str2words(warg, separate_on_whitespace=True))

    # Tokenize all words
    wds_only = " ".join(wds)
    tokens = list(filter(lambda x: x.kind in _VALID_TOKENS, tokenize(wds_only)))

    # Create word/cat pairs from each token
    def cat4token(t):
        w = t.txt
        if t.kind == TOK.WORD:
            val = list(filter(lambda m: m.stofn == m.ordmynd, t.val)) or t.val
            cat = val[0].ordfl if len(val) else CAT_UNKNOWN
            w = val[0].stofn if len(val) else t.txt
        elif t.kind == TOK.PERSON:
            cat = "person_" + t.val[0].gender
        elif t.kind == TOK.ENTITY:
            cat = "entity"
        return (w, cat)

    # Create word/cat tuples, overwriting word category with
    # a user-specified category, if provided
    words = []
    for i, t in enumerate(tokens):
        (w, c) = cat4token(t)
        c = spec_cats[i] if spec_cats[i] and spec_cats[i] != CAT_UNKNOWN else c
        words.append((w, c))

    # Filter all words not in allowed category
    words = list(filter(lambda x: x[1] in _VALID_WCATS, words))
    words = words[:_MAX_NUM_WORDS]

    # Generate date labels
    now = datetime.utcnow()
    delta = date_to - date_from
    with changedlocale(category="LC_TIME"):
        # Group by week if period longer than 3 months
        if delta.days >= _SHOW_WEEKS_CUTOFF:
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
        colors = list(_LINE_COLORS)
        data = dict(labels=labels, labelDates=label_dates, datasets=[])
        for w in words:
            # Look up frequency of the word for the given period
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
    resp["words"] = _words2str(words)

    return better_jsonify(**resp)


@routes.route("/wordfreq_details", methods=["GET", "POST"])
def wordfreq_details():
    """ Return list of articles containing certain words over a given period. """
    resp = dict(err=True)

    words = _str2words(request.args.get("words"))
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

    # Fetch list of articles for each word for the given period
    wlist = list()
    colors = list(_LINE_COLORS)
    with SessionContext(read_only=True) as session:
        for wd, cat in words:
            q = (
                session.query(
                    Article.id, Article.heading, Root.domain, Word.cnt, Word.stem
                )
                .join(Article, Article.id == Word.article_id)
                .filter(Article.timestamp >= date_from)
                .filter(Article.timestamp < date_to)
                .filter(Word.stem == wd)
                .filter(Word.cat == cat)
                .join(Root)
                .order_by(desc(Article.timestamp))
            )
            articles = [
                {"id": a[0], "heading": a[1], "domain": a[2], "cnt": a[3]}
                for a in q.all()
            ]
            wlist.append(
                {
                    "word": wd,
                    "cat": cat,
                    "cnt": sum([a["cnt"] for a in articles]),
                    "articles": articles,
                    "color": colors.pop(0),
                    "desc": _desc4word((wd, cat)),
                }
            )

    resp["err"] = False
    resp["payload"] = render_template("words/details.html", words=wlist)
    return better_jsonify(**resp)
