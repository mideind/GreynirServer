"""

    People-related routes.

"""

from . import routes, max_age

from datetime import datetime, timedelta
from collections import defaultdict

from flask import request, render_template

from settings import changedlocale

from db import SessionContext, desc
from db.models import Person, Article, Root, Word

from reynir import correct_spaces
from reynir.bindb import BIN_Db


# Default number of top persons to show in /people
_TOP_PERSONS_LENGTH = 20
_TOP_PERSONS_PERIOD = 1  # in days


def recent_persons(limit=_TOP_PERSONS_LENGTH):
    """ Return a list of names and titles appearing recently in the news """
    toplist = dict()
    MAX_TITLE_LENGTH = 64

    with SessionContext(read_only=True) as session:

        q = (
            session.query(Person.name, Person.title, Person.article_url, Article.id)
            .join(Article)
            .join(Root)
            .filter(Root.visible)
            .order_by(desc(Article.timestamp))[
                0 : limit * 2
            ]  # Go through up to 2 * N records
        )

        def is_better_title(new_title, old_title):
            len_new = len(new_title)
            len_old = len(old_title)
            if len_old >= MAX_TITLE_LENGTH:
                # Too long: we want a shorter one
                return len_new < len_old
            if len_new >= MAX_TITLE_LENGTH:
                # This one is too long: we don't want it
                return False
            # Otherwise, longer is better
            return len_new > len_old

        with BIN_Db.get_db() as bindb:
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


def top_persons(limit=_TOP_PERSONS_LENGTH, days=_TOP_PERSONS_PERIOD):
    """ Return a list of person names appearing most frequently in recent articles. """
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

        persons = defaultdict(list)
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

        personlist = []
        for k, v in persons.items():
            (name, gender) = k  # Unpack tuple key
            personlist.append({"name": name, "gender": gender, "articles": v})

        personlist.sort(key=lambda x: len(x["articles"]), reverse=True)

    return personlist[:limit]


@routes.route("/people")
@max_age(seconds=5 * 60)
def people_recent():
    """ Handler for a page with a list of people recently appearing in articles """
    return render_template("people/people-recent.html", persons=recent_persons())


@routes.route("/people_top")
@max_age(seconds=5 * 60)
def people_top():
    """ Handler for page showing people most frequently mentioned in recent articles """
    period = request.args.get("period")
    days = 7 if period == "week" else _TOP_PERSONS_PERIOD
    return render_template(
        "people/people-top.html", persons=top_persons(days=days), period=period
    )
