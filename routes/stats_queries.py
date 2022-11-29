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


    Query engine stats routes.

"""

from typing import Union, Dict, Any, List

import json
from datetime import datetime, timedelta

from werkzeug.wrappers import Response
from flask import request, render_template

from . import routes, cache
from db.sql import (
    QueriesQuery,
    QueryTypesQuery,
    QueryClientTypeQuery,
    TopUnansweredQueriesQuery,
    TopAnsweredQueriesQuery,
)
from utility import read_api_key
from settings import changedlocale


_DEFAULT_QUERY_STATS_PERIOD = 30
_MAX_QUERY_STATS_PERIOD = 30


def query_stats_data(session=None, num_days: int = 7) -> Dict[str, Any]:
    """Return all query stats."""
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
            q = list(QueriesQuery.period(start, end, enclosing_session=session))
            query_count_data.append(q[0][0])

    query_avg = sum(query_count_data) / num_days

    start = today - timedelta(days=num_days)
    end = datetime.utcnow()

    # Query types
    query_types_data = QueryTypesQuery.period(
        start=start,
        end=end,
        enclosing_session=session,
    )
    query_types_data = [list(e) for e in query_types_data]

    # Client types
    _CLIENT_COLORS = {
        "ios": "#4c8bf5",
        "android": "#a4c639",
        "www": "#f7b924",
    }
    res = QueryClientTypeQuery.period(start, end)
    client_types_data: List[Dict[str, Any]] = [
        {
            "name": f"{k[0]} {k[1] or ''}".rstrip(),
            "count": k[2],
            "color": _CLIENT_COLORS.get(k[0], "#ccc"),
        }
        for k in res
    ]

    # Top queries (answered and unanswered)
    def prep_top_answ_data(res) -> List[Dict[str, Any]]:
        rl = list(res)
        highest_count = res[0][2]
        toplist = []
        for q in rl:
            toplist.append({"query": q[0], "count": q[2], "freq": q[2] / highest_count})
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
@cache.cached(timeout=30 * 60, key_prefix="stats", query_string=True)
def stats_queries() -> Union[Response, str]:
    """Render a page containing various statistics on query
    engine usage from the Greynir database."""

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
