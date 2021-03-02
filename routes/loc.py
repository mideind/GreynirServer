"""

    Greynir: Natural language processing for Icelandic

    Copyright (C) 2021 Miðeind ehf.

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


    Location-related routes

"""

from typing import Dict, Any, cast

from . import routes, max_age, better_jsonify, cache, days_from_period_arg

from datetime import datetime, timedelta
from collections import defaultdict
import json

from flask import request, render_template, abort, send_file
from country_list import countries_for_language  # type: ignore

from db import SessionContext, dbfunc, desc
from db.models import Location, Article, Root, Column

from geo import (
    location_info,
    location_description,
    LOCATION_TAXONOMY,
    ICELAND_ISOCODE,
    ICE_REGIONS,
    ISO_TO_CONTINENT,
)

from images import get_staticmap_image


# Default number of top locations to show in /locations
_TOP_LOC_LENGTH = 20
_TOP_LOC_PERIOD = 1  # in days

GMAPS_COORD_URL = "https://www.google.com/maps/place/{0}+{1}/@{0},{1},{2}?hl=is"
GMAPS_PLACE_URL = "https://www.google.com/maps/place/{0}?hl=is"


def top_locations(limit=_TOP_LOC_LENGTH, kind=None, days=_TOP_LOC_PERIOD):
    """ Return a list of recent locations along with the list of
        articles in which they are mentioned. """

    with SessionContext(read_only=True) as session:
        q = (
            session.query(
                Location.name,
                Location.kind,
                Location.country,
                Location.article_url,
                Location.latitude,
                Location.longitude,
                Article.id,
                Article.heading,
                Root.domain,
            )
            .join(Article, Article.url == Location.article_url)
            .filter(Article.timestamp > datetime.utcnow() - timedelta(days=days))
            .join(Root)
            .filter(Root.visible)
        )

        # Filter by kind
        if kind:
            q = q.filter(Location.kind == kind)

        q = q.order_by(desc(cast(Column, Article.timestamp)))

        # Group articles by unique location
        locs = defaultdict(list)
        for r in q.all():
            article = {
                "url": r.article_url,
                "id": r.id,
                "heading": r.heading,
                "domain": r.domain,
            }
            k = (r.name, r.kind, r.country, r.latitude, r.longitude)
            locs[k].append(article)

        # Create top locations list sorted by article count
        loclist = []
        for k, v in locs.items():
            name, kind, country, _, _ = k  # Unpack tuple key
            # Google map links currently use the placename instead of
            # coordinates. This works well for most Icelandic and
            # international placenames, but fails on some.
            map_url = GMAPS_PLACE_URL.format(name)
            # if lat and lon:
            #     map_url = GMAPS_COORD_URL.format(lat, lon, "7z")

            loclist.append(
                {
                    "name": name,
                    "kind": kind,
                    "country": country,
                    "map_url": map_url,
                    "articles": v,
                }
            )
        loclist.sort(key=lambda x: len(x["articles"]), reverse=True)

        return loclist[:limit]


def icemap_markers(days=_TOP_LOC_PERIOD):
    """ Return a list of recent Icelandic locations and their coordinates. """
    with SessionContext(read_only=True) as session:
        q = (
            session.query(Location.name, Location.latitude, Location.longitude)
            .join(Article)
            .filter(Article.tree != None)
            .filter(Article.timestamp != None)
            .filter(Article.timestamp <= datetime.utcnow())
            .filter(Article.heading > "")
            .filter(Article.num_sentences > 0)
            .filter(Article.timestamp > datetime.utcnow() - timedelta(days=days))
            .join(Root)
            .filter(Root.visible)
            .filter(Location.country == ICELAND_ISOCODE)
            .filter(Location.kind != "country")
            .filter(Location.latitude != None)
            .filter(Location.longitude != None)
        )
        markers = list(set((l.name, l.latitude, l.longitude) for l in q.all()))

    return markers


def world_map_data(days=_TOP_LOC_PERIOD):
    """ Return data for world map. List of country iso codes with article count. """
    with SessionContext(read_only=True) as session:
        q = (
            session.query(Location.country, dbfunc.count(Location.id))
            .filter(Location.country != None)
            .join(Article)
            .filter(Article.tree != None)
            .filter(Article.timestamp != None)
            .filter(Article.timestamp <= datetime.utcnow())
            .filter(Article.heading > "")
            .filter(Article.num_sentences > 0)
            .filter(Article.timestamp > datetime.utcnow() - timedelta(days=days))
            .join(Root)
            .filter(Root.visible)
            .group_by(Location.country)
        )
        return {r[0]: r[1] for r in q.all()}


@routes.route("/locations", methods=["GET"])
@cache.cached(timeout=30 * 60, key_prefix="locations", query_string=True)
@max_age(seconds=30 * 60)
def locations():
    """ Render locations page. """
    kind = request.args.get("kind")
    kind = kind if kind in LOCATION_TAXONOMY else None

    period = request.args.get("period", "")
    days = days_from_period_arg(period, _TOP_LOC_PERIOD)
    locs = top_locations(kind=kind, days=days)

    return render_template(
        "locations/top.html", title="Staðir", locations=locs, period=period, kind=kind
    )


@routes.route("/locations_icemap", methods=["GET"])
@cache.cached(timeout=30 * 60, key_prefix="icemap", query_string=True)
def locations_icemap():
    """ Render Icelandic map locations page. """
    period = request.args.get("period", "")
    days = days_from_period_arg(period, _TOP_LOC_PERIOD)
    markers = icemap_markers(days=days)

    return render_template(
        "locations/icemap.html",
        title="Íslandskort",
        markers=json.dumps(markers),
        period=period,
    )


@routes.route("/locations_worldmap", methods=["GET"])
@cache.cached(timeout=30 * 60, key_prefix="worldmap", query_string=True)
def locations_worldmap():
    """ Render world map locations page. """
    period = request.args.get("period", "")
    days = days_from_period_arg(period, _TOP_LOC_PERIOD)

    d = world_map_data(days=days)
    n = dict(countries_for_language("is"))

    return render_template(
        "locations/worldmap.html",
        title="Heimskort",
        country_data=d,
        country_names=n,
        period=period,
    )


@routes.route("/staticmap", methods=["GET"])
@cache.cached(timeout=60 * 60 * 24, key_prefix="staticmap", query_string=True)
def staticmap():
    """ Proxy for Google Static Maps API. """
    try:
        lat = float(request.args.get("lat", "0.0"))
        lon = float(request.args.get("lon", "0.0"))
        zoom = int(request.args.get("z", "7"))
    except:
        return abort(400)

    imgdata = get_staticmap_image(lat, lon, zoom=zoom)
    if imgdata:
        fn = "{0}_{1}_{2}.png".format(lat, lon, zoom)
        return send_file(imgdata, attachment_filename=fn, mimetype="image/png")

    return abort(404)


STATIC_MAP_URL = "/staticmap?lat={0}&lon={1}&z={2}"
ZOOM_FOR_LOC_KIND = {"street": 11, "address": 12, "placename": 5, "country": 2}


@routes.route("/locinfo", methods=["GET"])
@cache.cached(timeout=60 * 60 * 24, key_prefix="locinfo", query_string=True)
def locinfo():
    """ Return info about a location as JSON. """
    resp = dict(found=False)  # type: Dict[str, Any]

    name = request.args.get("name")
    kind = request.args.get("kind")

    # Bail if we don't have the args
    if not (name and kind and kind in LOCATION_TAXONOMY):
        return better_jsonify(**resp)

    # Try to find some info on loc
    loc = location_info(name, kind)
    if not loc:
        return better_jsonify(**resp)

    # We've found it
    resp["found"] = True
    resp["country"] = loc.get("country")
    resp["continent"] = loc.get("continent")
    resp["desc"] = location_description(loc)
    lat, lon = loc.get("latitude"), loc.get("longitude")
    # We have coords
    if lat and lon:
        z = ZOOM_FOR_LOC_KIND[loc.get("kind", "street")]
        # We want a slightly lower zoom level for foreign placenames
        if resp["country"] != ICELAND_ISOCODE and kind == "placename":
            z -= 1
        resp["map"] = STATIC_MAP_URL.format(lat, lon, z)
    # Icelandic region
    elif name in ICE_REGIONS:
        resp["map"] = "/static/img/maps/regions/" + name + ".png"
    # Continent
    elif resp["country"] is None and resp["continent"] in ISO_TO_CONTINENT:
        resp["map"] = "/static/img/maps/continents/" + resp["continent"] + ".png"

    return better_jsonify(**resp)
