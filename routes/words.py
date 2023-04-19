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


    Word-frequency-related routes

"""

from typing import Iterable, List, Optional, Union, Tuple, Dict, Any, cast

import logging

from . import routes, better_jsonify, cache

from datetime import datetime, timedelta
from flask import request, render_template

from settings import changedlocale

from tokenizer import TOK, Tok

from reynir.bintokenizer import tokenize

from db import SessionContext, desc
from db.models import Article, Word, Root, Column, DateTime
from db.sql import WordFrequencyQuery


@routes.route("/words")
def words():
    """Handler for word frequency page."""
    return render_template("words/freq.html", title="Orð")


@routes.route("/words_trends")
def words_trends():
    """Handler for word trends page."""
    return render_template("words/trends.html", title="Orð")


CAT_UNKNOWN = "??"

# Word categories permitted in word frequency search
_VALID_WCATS = frozenset(
    (
        "kk",
        "kvk",
        "hk",
        "lo",
        "so",
        "person_kk",
        "person_kvk",
        "person_hk",
        "entity",
        CAT_UNKNOWN,
    )
)

# Human-readable descriptions of word categories
CAT_DESC = {
    "kk": "kk. no.",
    "kvk": "kvk. no.",
    "hk": "hk. no.",
    "lo": "lo.",
    "so": "so.",
    "person_kk": "kk. manneskja",
    "person_kvk": "kvk. manneskja",
    "person_hk": "hk. manneskja",
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


def _str2words(
    wstr: str, separate_on_whitespace: bool = False
) -> Optional[List[Tuple[str, str]]]:
    """Parse string of the form 'w1:cat1, w2:cat2, ...' into a list
    of word/category tuples."""
    if not wstr:
        return None
    ws = wstr.strip()
    if not ws:
        return None
    words: List[str] = [w.strip() for w in ws.split(",") if w.strip()]
    if separate_on_whitespace:
        words = " ".join(words).split()
    return [
        cast(Tuple[str, str], tuple(w.split(":")))
        if len(w.split(":")) == 2
        else (w, CAT_UNKNOWN)
        for w in words
    ][:_MAX_NUM_WORDS]


def _words2str(words: Iterable[Tuple[str, str]]) -> str:
    """Create comma-separated string from (word,cat) tuple list,
    e.g. "[(a,b),(c,d)] -> "a:b, c:d"."""
    return ", ".join([":".join(w[:2]) if len(w) >= 2 else w[0] for w in words])


def _desc4word(wc: Tuple[str, str]) -> str:
    """Create a human-friendly description string for a word/category tuple."""
    return f"{wc[0]} ({CAT_DESC.get(wc[1], CAT_UNKNOWN)})"


@routes.route("/wordfreq", methods=["GET", "POST"])
@cache.cached(timeout=60 * 60 * 4, key_prefix="wordfreq", query_string=True)
def wordfreq():
    """Return word frequency chart data for a given time period."""
    resp: Dict[str, Any] = dict(err=True)
    # Create datetime objects from query string args
    try:
        date_fmt = "%Y-%m-%d"
        date_from = datetime.strptime(request.args.get("date_from", ""), date_fmt)
        date_to = datetime.strptime(request.args.get("date_to", ""), date_fmt)
    except Exception as e:
        logging.warning(f"Failed to parse date arg: {e}")
        return better_jsonify(**resp)

    # Words param should contain one or more comma-separated word
    # lemmas with optional category specified with :cat suffix
    warg: str = request.args.get("words", "")
    if not warg:
        return better_jsonify(**resp)

    # Create word/cat pair from token
    def cat4token(t: Tok) -> Tuple[str, str]:
        assert t.kind in (TOK.WORD, TOK.PERSON, TOK.ENTITY)
        # TODO: Use GreynirPackage lemma lookup function for this
        w, cat = t.txt, ""
        if t.kind == TOK.WORD:
            val = list(filter(lambda m: m.stofn == m.ordmynd, t.meanings)) or t.meanings
            cat = val[0].ordfl if len(val) else CAT_UNKNOWN
            w = val[0].stofn if len(val) else t.txt
            # Hack to fix combined word, remove hyphens added by combinator
            if w.count("-") > t.txt.count("-"):
                san = ""
                txtlen = len(t.txt)
                for i, char in enumerate(w):
                    if char == "-" and i < txtlen and t.txt[i] != "-":
                        continue
                    san += char
                w = san
        elif t.kind == TOK.PERSON:
            cat = "person_" + (t.person_names[0].gender or "hk")
        elif t.kind == TOK.ENTITY:
            cat = "entity"
        return (w, cat)

    # Parse arg string into word/cat tuples
    wds = _str2words(warg)

    # Try to tokenize each item that doesn't have a category
    nwds: List[Tuple[str, str]] = []
    for w, c in wds or []:
        if not c or c == CAT_UNKNOWN:
            # Try to tokenize
            tokens = list(filter(lambda x: x.kind in _VALID_TOKENS, tokenize(w)))
            for t in tokens:
                nwds.append(cat4token(t))
        else:
            nwds.append((w, c))

    # Filter all words not in allowed category and restrict no. words
    words = list(filter(lambda x: x[1] in _VALID_WCATS, nwds))
    words = words[:_MAX_NUM_WORDS]

    # Generate date labels
    now = datetime.utcnow()
    delta = date_to - date_from
    with changedlocale(category="LC_TIME"):
        # Group by week if period longer than 3 months
        label_date_strings: List[Union[str, Tuple[str, str]]] = []
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
            labels: List[str] = []
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
            # Convert dates to strings for client-side
            label_date_strings = [
                (df.strftime("%Y-%m-%d"), dt.strftime("%Y-%m-%d"))
                for df, dt in label_dates
            ]
        # Group by day
        else:
            timeunit = "day"
            label_days = [date_from + timedelta(days=i) for i in range(delta.days)]
            labels = [
                d.strftime("%-d. %b")
                if d.year == now.year
                else d.strftime("%-d. %b %Y")
                for d in label_days
            ]
            label_date_strings = [d.strftime("%Y-%m-%d") for d in label_days]

    # Create datasets for front-end chart
    colors = list(_LINE_COLORS)
    data: Dict[str, Any] = dict(
        labels=labels, labelDates=label_date_strings, datasets=[]
    )
    with SessionContext(commit=False) as session:
        for w in words:
            # Look up frequency of word for the given period
            (wd, cat) = w
            res = (
                WordFrequencyQuery.frequency(
                    wd,
                    cat,
                    date_from,
                    date_to,
                    timeunit=timeunit,
                    enclosing_session=session,
                )
                or []
            )
            # Generate data and config for chart
            label = f"{wd} ({CAT_DESC.get(cat)})"
            ds: Dict[str, Any] = dict(label=label, fill=False, lineTension=0)
            ds["borderColor"] = ds["backgroundColor"] = colors.pop(0)
            ds["data"] = [r[1] for r in res]
            ds["word"] = f"{wd}:{cat}"
            data["datasets"].append(ds)

    # Create response
    resp["err"] = False
    resp["data"] = data
    resp["words"] = _words2str(words)

    return better_jsonify(**resp)


@routes.route("/wordfreq_details", methods=["GET", "POST"])
def wordfreq_details():
    """Return list of articles containing certain words over a given period."""
    resp: Dict[str, Any] = dict(err=True)

    words = _str2words(request.args.get("words") or "")
    if not words:
        return better_jsonify(**resp)

    # Parse date args
    try:
        date_fmt = "%Y-%m-%d"
        date_from = datetime.strptime(request.args.get("date_from", ""), date_fmt)
        dto = request.args.get("date_to")
        if dto:
            date_to = datetime.strptime(dto, date_fmt)
        else:
            # If only one date provided, assume it's a period spanning a single day
            date_to = date_from + timedelta(days=1)
    except Exception as e:
        logging.warning(f"Failed to parse date arg: {e}")
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
                .order_by(desc(cast(Column[DateTime], Article.timestamp)))
            )
            articles = [
                {"id": a[0], "heading": a[1], "domain": a[2], "cnt": a[3]}
                for a in q.all()
            ]
            wlist.append(
                {
                    "word": wd,
                    "cat": cat,
                    "cnt": sum(a["cnt"] for a in articles),
                    "articles": articles,
                    "color": colors.pop(0),
                    "desc": _desc4word((wd, cat)),
                }
            )

    resp["err"] = False
    resp["payload"] = render_template("words/details.html", words=wlist)
    return better_jsonify(**resp)
