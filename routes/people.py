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


    People-related routes

"""

from typing import Any, Dict, List, Set, Tuple, cast, Counter as CounterType

from . import routes, max_age, cache, restricted, days_from_period_arg

from datetime import datetime, timedelta
from collections import defaultdict, Counter
from itertools import permutations

from flask import request, render_template

from settings import changedlocale

from db import SessionContext, desc
from db.models import Person, Article, Root, Word, Column

from reynir import correct_spaces
from reynir.bindb import GreynirBin


# Default number of persons to show in /people
_RECENT_PERSONS_LENGTH = 50
_MAX_TITLE_LENGTH = 64

# Defaults for /people_top
_TOP_PERSONS_LENGTH = 20
_TOP_PERSONS_PERIOD = 1  # in days


def recent_persons(limit: int=_RECENT_PERSONS_LENGTH):
    """Return a list of names and titles appearing recently in the news"""
    toplist: Dict[str, Tuple[str, str, str, str]] = dict()

    with SessionContext(read_only=True) as session:

        q = (
            session.query(Person.name, Person.title, Person.article_url, Article.id)
            .join(Article)
            .join(Root)
            .filter(Root.visible)
            # Go through up to 2 * N records
            .order_by(desc(cast(Column, Article.timestamp)))[0 : limit * 2]
        )

        def is_better_title(new_title: str, old_title: str) -> bool:
            len_new = len(new_title)
            len_old = len(old_title)
            if len_old >= _MAX_TITLE_LENGTH:
                # Too long: we want a shorter one
                return len_new < len_old
            if len_new >= _MAX_TITLE_LENGTH:
                # This one is too long: we don't want it
                return False
            # Otherwise, longer is better
            return len_new > len_old

        with GreynirBin.get_db() as bindb:
            for p in q:
                # Insert the name into the list if it's not already there,
                # or if the new title is longer than the previous one
                if p.name not in toplist or is_better_title(
                    p.title, toplist[p.name][0]
                ):
                    toplist[p.name] = (
                        correct_spaces(p.title),
                        p.article_url,
                        p.id,
                        bindb.lookup_name_gender(p.name),
                    )
                    if len(toplist) >= limit:
                        # We now have as many names as we initially wanted: terminate the loop
                        break

    with changedlocale() as strxfrm:
        # Convert the dictionary to a sorted list of dicts
        return sorted(
            [
                dict(name=name, title=tu[0], gender=tu[3], url=tu[1], uuid=tu[2])
                for name, tu in toplist.items()
            ],
            key=lambda x: strxfrm(x["name"]),
        )


def top_persons(
    limit: int = _TOP_PERSONS_LENGTH, days: int = _TOP_PERSONS_PERIOD
) -> List[Dict[str, Any]]:
    """Return a list of person names appearing most frequently in recent articles."""
    personlist: List[Dict[str, Any]] = []

    with SessionContext(read_only=True) as session:
        q = (
            session.query(
                Word.stem,
                Word.cat,
                Article.id,
                Article.heading,
                Article.url,
                Root.domain,
            )
            .join(Article, Article.id == Word.article_id)
            .join(Root)
            .filter(Root.visible)
            .filter(Article.timestamp > datetime.utcnow() - timedelta(days=days))
            .filter((Word.cat == "person_kk") | (Word.cat == "person_kvk"))
            .filter(Word.stem.like("% %"))  # Match whitespace for least two names.
            .distinct()
        )

        persons: Dict[Tuple[str, str], List[Dict[str, str]]] = defaultdict(list)
        for r in q.all():
            article = {
                "url": r.url,
                "id": r.id,
                "heading": r.heading,
                "domain": r.domain,
            }
            gender = r.cat.split("_")[1]  # Get gender from _ suffix
            k = (r.stem, gender)
            persons[k].append(article)

        for k, v in persons.items():
            (name, gender) = k  # Unpack tuple key
            personlist.append({"name": name, "gender": gender, "articles": v})

        personlist.sort(key=lambda x: len(x["articles"]), reverse=True)

    return personlist[:limit]


_DEFAULT_NUM_PERSONS_GRAPH = 50


def graph_data(num_persons: int=_DEFAULT_NUM_PERSONS_GRAPH):
    """Get and prepare data for people graph"""
    with SessionContext(read_only=True) as session:
        # Find all persons mentioned in articles that
        # have at least two names (i.e. match whitespace)
        q = (
            session.query(Word.stem, Word.article_id, Word.cat)
            .filter(Word.cat.like("person_%"))
            .filter(Word.stem.like("% %"))
        )
        res: List[Tuple[str, str, str]] = q.all()

        # Count number of occurrences of each name
        cnt: CounterType[str] = Counter()
        for name, _, _ in res:
            cnt[name] += 1

        # Get most common names
        names = [name for name, _ in cnt.most_common(num_persons)]

        # Generate dict mapping article ids to a set of top names mentioned
        articles: Dict[str, Set[str]] = defaultdict(set)
        for name, art_id, _ in res:
            if name in names:
                articles[art_id].add(name)

        # Find all links
        nlinks: Dict[Tuple[int, int], int] = defaultdict(int)
        for _, persons in articles.items():
            if len(persons) < 2:
                # We need at least two names to establish link
                continue

            # Find all permutations of people mentioned in article
            perm = list(permutations(persons, 2))
            for a, b in perm:
                # We use a sorted tuple as hashable dict key when
                # counting number of connections between any two names
                k = tuple(sorted([names.index(a), names.index(b)]))
                nlinks[cast(Tuple[int, int], k)] += 1

        # Create final link and node data structures
        links = [
            {"source": k[0], "target": k[1], "weight": v} for k, v in nlinks.items()
        ]
        nodes = []
        for idx, n in enumerate(names):
            # print(cnt[n])
            # TODO: Normalize influence
            nodes.append({"name": n, "id": idx, "influence": cnt[n] / 7, "zone": 0})

        dataset = {"nodes": nodes, "links": links}

        return dataset


@routes.route("/people_recent")
@cache.cached(timeout=10 * 60, key_prefix="people", query_string=True)
@max_age(seconds=10 * 60)
def people_recent():
    """Page with a list of people recently appearing in articles"""
    return render_template(
        "people/recent.html", title="Fólk - Nýlegt", persons=recent_persons()
    )


@routes.route("/people")
@cache.cached(timeout=30 * 60, key_prefix="people_top", query_string=True)
@max_age(seconds=10 * 60)
def people_top():
    """Page showing people most frequently mentioned in recent articles"""
    period = request.args.get("period", "")
    days = days_from_period_arg(period, _TOP_PERSONS_PERIOD)
    persons = top_persons(days=days)

    return render_template(
        "people/top.html", title="Fólk", persons=persons, period=period
    )


@routes.route("/people_graph")
@restricted
@max_age(seconds=10 * 60)
def people_graph():
    """Page with a weighted, force directed graph of relations
    between people via mentions in articles."""
    return render_template("people/graph.html", graph_data=graph_data())


@routes.route("/people_timeline")
@restricted
@max_age(seconds=10 * 60)
def people_timeline():
    """Person timeline page."""
    return render_template("people/timeline.html")
