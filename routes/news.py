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


    News-related routes

"""

from __future__ import annotations

from typing import List, Optional, Union, cast

from werkzeug.wrappers import Response
from . import routes, max_age, better_jsonify

from datetime import datetime, timedelta
from flask import request, render_template

from settings import changedlocale

from db import Session, SessionContext, desc
from db.models import Article, Root, Location, ArticleTopic, Topic, Column


# Default number of top news items to show in /news
_DEFAULT_NUM_ARTICLES = 20
_MAX_NUM_ARTICLES = 100


def fetch_articles(
    topic: Optional[str]=None,
    offset: int=0,
    limit: int=_DEFAULT_NUM_ARTICLES,
    start: Optional[datetime]=None,
    location: Optional[str]=None,
    country: Optional[str]=None,
    root: Optional[str]=None,
    author: Optional[str]=None,
    enclosing_session: Optional[Session]=None,
):
    """Return a list of articles in chronologically reversed order.
    Articles can be filtered by start date, location, country, root etc."""
    toplist: List[ArticleDisplay] = []

    with SessionContext(read_only=True, session=enclosing_session) as session:
        q = (
            session.query(Article)
            .filter(Article.tree != None)
            .filter(Article.timestamp != None)
            .filter(Article.timestamp <= datetime.utcnow())
            .filter(Article.heading > "")
            .filter(Article.num_sentences > 0)
            .join(Root)
            .filter(Root.visible == True)
        )

        # Filter by date
        if start is not None:
            q = q.filter(Article.timestamp > start)

        if location or country:
            q = q.join(Location)
            if location:
                # Filter by location
                q = q.filter(Location.name == location)
            if country:
                # Filter by country code
                q = q.filter(Location.country == country)

        # Filter by source (root) using domain (e.g. "kjarninn.is")
        if root:
            q = q.filter(Root.domain == root)

        # Filter by author name
        if author:
            q = q.filter(Article.author == author)

        # Filter by topic identifier
        if topic:
            q = q.join(ArticleTopic).join(Topic).filter(Topic.identifier == topic)

        q = (
            q.order_by(desc(cast(Column, Article.timestamp)))
            .offset(offset)
            .limit(limit)
        )

        class ArticleDisplay:
            """Utility class to carry information about an article to the web template"""

            def __init__(
                self,
                heading: str,
                timestamp: datetime,
                url: str,
                uuid: str,
                num_sentences: int,
                num_parsed: int,
                icon: str,
                localized_date: str,
                source: str,
            ):
                self.heading = heading
                self.timestamp = timestamp
                self.url = url
                self.uuid = uuid
                self.num_sentences = num_sentences
                self.num_parsed = num_parsed
                self.icon = icon
                self.localized_date = localized_date
                self.source = source

            @property
            def width(self) -> str:
                """The ratio of parsed sentences to the total number of sentences,
                expressed as a percentage string"""
                if self.num_sentences == 0:
                    return "0%"
                return "{0}%".format((100 * self.num_parsed) // self.num_sentences)

            @property
            def time(self) -> str:
                return self.timestamp.isoformat()[11:16]

            @property
            def date(self) -> str:
                if datetime.today().year == self.timestamp.year:
                    return self.localized_date
                return self.fulldate

            @property
            def fulldate(self) -> str:
                return self.localized_date + self.timestamp.strftime(" %Y")

        with changedlocale(category="LC_TIME"):
            for a in q:
                # Instantiate article objects from results
                source = a.root.domain
                icon = source + ".png"
                locdate = a.timestamp.strftime("%-d. %b")

                d = ArticleDisplay(
                    heading=a.heading,
                    timestamp=a.timestamp,
                    url=a.url,
                    uuid=a.id,
                    num_sentences=a.num_sentences,
                    num_parsed=a.num_parsed,
                    icon=icon,
                    localized_date=locdate,
                    source=source,
                )
                toplist.append(d)

    return toplist


@routes.route("/news")
@max_age(seconds=60)
def news() -> Union[Response, str]:
    """Handler for a page with a list of articles + pagination"""
    topic = request.args.get("topic")
    root = request.args.get("root")
    author = request.args.get("author")

    try:
        offset = max(0, int(request.args.get("offset", 0)))
        limit = max(0, int(request.args.get("limit", _DEFAULT_NUM_ARTICLES)))
    except:
        offset = 0
        limit = _DEFAULT_NUM_ARTICLES

    limit = min(limit, _MAX_NUM_ARTICLES)  # Cap at max 100 results per page

    with SessionContext(read_only=True) as session:
        # Fetch articles
        articles = fetch_articles(
            topic=topic,
            offset=offset,
            limit=limit,
            root=root,
            author=author,
            enclosing_session=session,
        )

        # If all articles in the list are timestamped within 24 hours of now,
        # we display their times in HH:MM format. Otherwise, we display full date.
        display_time = True
        if articles and (datetime.utcnow() - articles[-1].timestamp).days >= 1:
            display_time = False

        # Fetch lists of article topics
        q = session.query(Topic.identifier, Topic.name).order_by(Topic.name).all()
        d = {t[0]: t[1] for t in q}
        topics = dict(id=topic, name=d.get(topic, ""), topic_list=q)

        # Fetch list of article sources (roots)
        q = (
            session.query(Root.domain, Root.description)
            .filter(Root.visible == True)
            .order_by(Root.description)
        )
        roots = dict(q.all())

        return render_template(
            "news.html",
            title="Fréttir",
            articles=articles,
            topics=topics,
            display_time=display_time,
            offset=offset,
            limit=limit,
            selected_root=root,
            roots=roots,
            author=author,
        )

    return Response("Error", status=403)


ARTICLES_LIST_MAXITEMS = 50


@routes.route("/articles", methods=["GET"])
def articles_list():
    """Returns rendered HTML article list as a JSON payload"""
    locname = request.args.get("locname")
    country = request.args.get("country")
    period = request.args.get("period")

    days = 7 if period == "week" else 1
    start_date = datetime.utcnow() - timedelta(days=days)

    # Fetch articles
    articles = fetch_articles(
        start=start_date,
        location=locname,
        country=country,
        limit=ARTICLES_LIST_MAXITEMS,
    )

    # Render template
    count = len(articles)
    html = render_template("articles.html", articles=articles)

    # Return payload
    return better_jsonify(payload=html, count=count)
