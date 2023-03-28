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


    Stats-related routes

"""

from typing import Any, Dict, List, Optional, Union, Iterable

from werkzeug.wrappers import Response


import json
import logging
from colorsys import hsv_to_rgb
from datetime import datetime, timedelta
from decimal import Decimal

from flask import request, render_template
from reynir.bindb import GreynirBin

from . import routes, cache, max_age
from settings import changedlocale
from utility import read_api_key
from db import SessionContext, Session
from db.sql import (
    StatsQuery,
    ChartsQuery,
    GenderQuery,
    BestAuthorsQuery,
    QueryCountQuery,
    QueryTypesQuery,
    QueryClientTypeQuery,
    TopUnansweredQueriesQuery,
    TopAnsweredQueriesQuery,
)


# Days
_DEFAULT_STATS_PERIOD = 10
_MAX_STATS_PERIOD = 90
_TOP_AUTHORS_PERIOD = 30

# TODO: This should be put in a column in the roots table
_SOURCE_ROOT_COLORS = {
    "Kjarninn": "#f17030",
    "RÚV": "#dcdcdc",
    "Vísir": "#3d6ab9",
    "Morgunblaðið": "#020b75",
    "Eyjan": "#ca151c",
    "Kvennablaðið": "#900000",
    "Stundin": "#ee4420",
    "Hringbraut": "#44607a",
    "Fréttablaðið": "#002a61",
    "Hagstofa Íslands": "#818285",
    "DV": "#ed1c24",
    "BB": "#ffb6c1",
    "Mannlíf": "#ffcc00",  # Gula pressan ;)
    "Hagstofan": "#828282",
    "Bændablaðið": "#41938A",
    "Viðskiptablaðið": "#00ffff",
    "Heimildin": "#f17030",
}


def chart_stats(session: Optional[Session]=None, num_days: int = 7) -> Dict[str, Any]:
    """Return scraping and parsing stats for charts"""
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    labels: List[str] = []
    sources: Dict[str, List[int]] = {}
    parsed_data: List[float] = []

    # Get article count for each source for each day, and query count for each day
    # We change locale to get localized weekday/month names
    with changedlocale(category="LC_TIME"):
        for n in range(0, num_days):
            days_back = num_days - n - 1
            start = today - timedelta(days=days_back)
            end = today - timedelta(days=days_back - 1)

            # Generate date label
            dfmtstr = "%a %-d. %b"
            labels.append(start.strftime(dfmtstr))

            sent = 0
            parsed = 0

            # Get article count per source for day
            # Also collect parsing stats for parse % chart
            q = ChartsQuery.period(start, end, enclosing_session=session)
            for (name, cnt, s, p) in q:
                sources.setdefault(name, []).append(cnt)
                sent += s
                parsed += p

            percent = round((parsed / sent) * 100, 2) if sent else 0
            parsed_data.append(percent)

    # Create datasets for bar chart
    datasets = []
    article_count = 0
    for k, v in sorted(sources.items()):
        color = _SOURCE_ROOT_COLORS.get(k, "#000")
        datasets.append({"label": k, "backgroundColor": color, "data": v})
        article_count += sum(v)

    # Calculate averages
    scrape_avg = article_count / num_days
    parse_avg = sum(parsed_data) / num_days

    return {
        "scraped": {"labels": labels, "datasets": datasets, "avg": scrape_avg},
        "parsed": {
            "labels": labels,
            "datasets": [{"data": parsed_data}],
            "avg": parse_avg,
        },
    }


def top_authors(
    days: int = _TOP_AUTHORS_PERIOD, session: Optional[Session] = None
) -> List[Dict[str, Any]]:
    """Generate list of top authors w. parse percentage."""
    end = datetime.utcnow()
    start = end - timedelta(days=days)
    authors = list(
        BestAuthorsQuery.period(start, end, enclosing_session=session, min_articles=10)
    )[:20]

    authresult = list()
    with GreynirBin.get_db() as bindb:
        for a in authors:
            name = a[0]
            gender = bindb.lookup_name_gender(name)
            if gender == "hk":  # Skip unnamed authors (e.g. "Ritstjórn Vísis")
                continue
            perc = round(float(a[4]), 2)
            authresult.append({"name": name, "gender": gender, "perc": perc})

    return authresult[:10]


@routes.route("/stats", methods=["GET"])
@cache.cached(timeout=30 * 60, key_prefix="stats", query_string=True)
@max_age(seconds=30 * 60)
def stats() -> Union[Response, str]:
    """Render a page containing various statistics from the Greynir database."""
    days = _DEFAULT_STATS_PERIOD
    try:
        days = min(
            _MAX_STATS_PERIOD, int(request.args.get("days", _DEFAULT_STATS_PERIOD))
        )
    except Exception:
        pass

    chart_data: Dict[str, Any] = dict()

    try:
        with SessionContext(read_only=True) as session:

            # Article stats
            sq = StatsQuery()
            articles_result = sq.execute(session)
            articles_total = dict(art=Decimal(), sent=Decimal(), parsed=Decimal())
            for r in articles_result:
                articles_total["art"] += r.art
                articles_total["sent"] += r.sent
                articles_total["parsed"] += r.parsed

            # Gender stats
            gq = GenderQuery()
            gender_result = gq.execute(session)

            gender_total = dict(
                kvk=Decimal(), kk=Decimal(), hk=Decimal(), total=Decimal()
            )
            for r in gender_result:
                gender_total["kvk"] += r.kvk
                gender_total["kk"] += r.kk
                gender_total["hk"] += r.hk
                gender_total["total"] += r.kvk + r.kk + r.hk

            # Author stats
            author_result = top_authors(session=session, days=days)

            # Scraping and parsing stats
            chart_data = chart_stats(session=session, num_days=days)

            return render_template(
                "stats.html",
                title="Tölfræði",
                articles_result=articles_result,
                articles_total=articles_total,
                gender_result=gender_result,
                gender_total=gender_total,
                author_result=author_result,
                scraped_chart_data=json.dumps(chart_data["scraped"]),
                scraped_avg=int(round(chart_data["scraped"]["avg"])),
                parsed_chart_data=json.dumps(chart_data["parsed"]),
                parsed_avg=round(chart_data["parsed"]["avg"], 1),
            )
    except Exception as e:
        logging.error(f"Error rendering stats page: {e}")
        return Response(f"Error: {e}", status=500)


_DEFAULT_QUERY_STATS_PERIOD = 30
_MAX_QUERY_STATS_PERIOD = 30


def query_stats_data(
    session: Optional[Session]=None, num_days: int = _DEFAULT_QUERY_STATS_PERIOD
) -> Dict[str, Any]:
    """Return all data for query stats dashboard."""
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    labels = []
    query_count_data = []

    # Get query count for each day
    # We change locale to get localized date weekday/month names
    with changedlocale(category="LC_TIME"):
        for n in range(0, num_days):
            days_back = num_days - n - 1
            start = today - timedelta(days=days_back)
            end = today - timedelta(days=days_back - 1)

            # Generate date label
            dfmtstr = "%a %-d. %b"
            labels.append(start.strftime(dfmtstr))

            # Get query count for day
            q = list(QueryCountQuery.period(start, end, enclosing_session=session))
            query_count_data.append(q[0][0])

    query_avg = sum(query_count_data) / num_days

    start = today - timedelta(days=num_days)
    end = datetime.utcnow()

    # Query types
    res = list(
        QueryTypesQuery.period(
            start=start,
            end=end,
            enclosing_session=session,
        )
    )
    total = sum([k[0] for k in res])

    # This function is used to ensure that all the query
    # types have a fixed, unique color on the pie chart.
    def gen_distinct_hex_colors(num: int) -> List[str]:
        """Generate a list of perceptually distinct hex colors."""
        hsv_tuples = [(x * 1.0 / num, 0.9, 0.9) for x in range(num)]
        hex_out = []
        for hsv in hsv_tuples:
            rgb = map(lambda x: int(x * 255), hsv_to_rgb(*hsv))
            hex_out.append("#%02x%02x%02x" % tuple(rgb))
        return hex_out

    query_types_data = {
        "labels": [k[1] for k in res],
        "datasets": [
            {
                "data": [k[0] for k in res],
                "percentage": [round(k[0] / total * 100, 1) for k in res],
                "backgroundColor": gen_distinct_hex_colors(len(res)),
            }
        ],
    }

    # Client types
    _CLIENT_COLORS = {
        "ios": "#4c8bf5",
        "ios_flutter": "#4c8bf5",
        "android": "#a4c639",
        "android_flutter": "#a4c639",
        "python": "#ffff00",
        "www": "#f7b924",
    }
    res = QueryClientTypeQuery.period(start, end)
    total = sum([k[2] for k in res])
    client_types_data = {
        "labels": [f"{k[0]} {k[1] or ''}".rstrip() for k in res],
        "datasets": [
            {
                "data": [k[2] for k in res],
                "percentage": [round(k[2] / total * 100, 1) for k in res],
                "backgroundColor": [_CLIENT_COLORS.get(k[0], "#ccc") for k in res],
            }
        ],
    }
    # TODO: Add iOS, Android percentages

    # Top queries (answered and unanswered)
    def prep_top_answ_data(res: Iterable) -> List[Dict[str, Any]]:
        rl = list(res)  # Consume generator
        highest_count = rl[0][1]
        toplist = []
        for q in rl:
            toplist.append({"query": q[0], "count": q[1], "freq": q[1] / highest_count})
        return toplist

    res = TopUnansweredQueriesQuery.period(start, end, enclosing_session=session)
    top_unanswered = prep_top_answ_data(res)
    res = TopAnsweredQueriesQuery.period(start, end, enclosing_session=session)
    top_answered = prep_top_answ_data(res)

    return {
        "query_count": {
            "labels": labels,
            "datasets": [{"data": query_count_data}],
            "avg": query_avg,
        },
        "query_types": query_types_data,
        "client_types": client_types_data,
        "top_unanswered": top_unanswered,
        "top_answered": top_answered,
    }


@routes.route("/stats/queries", methods=["GET"])
@cache.cached(timeout=30 * 60, key_prefix="stats_queries", query_string=True)
@max_age(seconds=30 * 60)
def stats_queries() -> Union[Response, str]:
    """Render a page containing various statistics on query engine usage."""

    # Accessing this route requires an API key
    key = request.args.get("key")
    if key is None or key != read_api_key("GreynirServerKey"):
        return Response(f"Not authorized", status=401)

    days = _DEFAULT_QUERY_STATS_PERIOD
    try:
        days = min(
            _MAX_QUERY_STATS_PERIOD,
            int(request.args.get("days", _DEFAULT_QUERY_STATS_PERIOD)),
        )
    except Exception:
        pass

    stats_data = query_stats_data(num_days=days)

    return render_template(
        "stats-queries.html",
        title="Tölfræði fyrirspurnakerfis",
        days=days,
        query_count_data=json.dumps(stats_data["query_count"]),
        queries_avg=stats_data["query_count"]["avg"],
        query_types_data=json.dumps(stats_data["query_types"]),
        client_types_data=json.dumps(stats_data["client_types"]),
        top_unanswered=stats_data["top_unanswered"],
        top_answered=stats_data["top_answered"],
    )
