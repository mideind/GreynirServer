"""

    Greynir: Natural language processing for Icelandic

    Copyright (C) 2022 Miðeind ehf.

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

from typing import Any, Dict, List, Optional, Union

from werkzeug.wrappers import Response

from . import routes, cache

import json
import logging
from datetime import datetime, timedelta
from decimal import Decimal

from flask import request, render_template

from settings import changedlocale
from db import SessionContext, Session
from db.sql import (
    StatsQuery,
    ChartsQuery,
    GenderQuery,
    BestAuthorsQuery,
    QueriesQuery,
)
from reynir.bindb import GreynirBin


# Days
_DEFAULT_STATS_PERIOD = 10
_MAX_STATS_PERIOD = 30
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
}


def chart_stats(session=None, num_days: int = 7) -> Dict[str, Any]:
    """Return scraping and parsing stats for charts"""
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    labels = []
    sources: Dict[str, List[int]] = {}
    parsed_data = []
    query_data = []

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
    query_avg = sum(query_data) / num_days

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
            author_result = top_authors(session=session)

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
