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

from . import routes, max_age, better_jsonify

from datetime import datetime, timedelta
from flask import request, render_template

from settings import changedlocale

from db import SessionContext, desc
from db.models import Article, Root, Location, ArticleTopic, Topic


@routes.route("/words")
def words():
    """ Handler for word frequency page. """

    return render_template("words.html")
