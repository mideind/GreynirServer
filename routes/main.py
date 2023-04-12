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


    This module contains the main Flask routes for the Greynir web server.

"""

from typing import Dict, Any, Iterable, List, Optional, Sequence, Tuple, Union, cast

import platform
import sys
import random
import json
from datetime import datetime

from flask import render_template, request, redirect, url_for

import tokenizer
import reynir
from reynir.fastparser import ParseForestFlattener

from db import SessionContext, desc, dbfunc
from db.models import Person, Article, ArticleTopic, Entity, Column

from settings import Settings
from article import Article as ArticleProxy
from search import Search
from treeutil import TreeUtility, StatsDict
from images import Img, get_image_url, update_broken_image_url, blacklist_image_url

from . import routes, max_age, cache, better_jsonify, restricted, Response
from . import MAX_URL_LENGTH, MAX_UUID_LENGTH, MAX_TEXT_LENGTH_VIA_URL


# Default text shown in the URL/text box
_DEFAULT_TEXTS: Sequence[str] = [
    "Hver gegnir starfi seðlabankastjóra?",
    "Hvað er HeForShe?",
    "Hver er Valgerður Bjarnadóttir?",
    "Hver er borgarstjóri?",
    "Hver er formaður Öryrkjabandalagsins?",
    "Hvað er Wintris?",
    "Hver er Vigdís Finnbogadóttir?",
    "Hver er Kristján Eldjárn?",
    "Hver er forstjóri Landsvirkjunar?",
    "Hver gegnir starfi forstjóra Orkuveitu Reykjavíkur?",
    "Hver er þjóðleikhússtjóri?",
    "Hver er fyrirliði íslenska landsliðsins?",
    "Hver er forsetaframbjóðandi?",
    "Hver er forseti Finnlands?",
    "Hver hefur verið aðstoðarmaður forsætisráðherra?",
    "Hver er forstjóri Google?",
    "Hvað er UNESCO?",
    "Hver er Íslandsmeistari í golfi?",
]

PARSEFAIL_DEFAULT = 50
PARSEFAIL_MAX = 250


@routes.route("/")
@max_age(seconds=60)
def main() -> str:
    """Handler for the main (index) page"""
    txt = request.args.get("txt")
    if txt:
        txt = txt.strip()
    if not txt:
        # Select a random default text
        txt = _DEFAULT_TEXTS[random.randint(0, len(_DEFAULT_TEXTS) - 1)]
    return render_template("main.html", default_text=txt)


@routes.route("/analysis")
def analysis() -> str:
    """Handler for a page with grammatical analysis of user-entered text"""
    txt = request.args.get("txt", "")[0:MAX_TEXT_LENGTH_VIA_URL]
    return render_template("analysis.html", title="Málgreining", default_text=txt)


MAX_SIM_ARTICLES = 10  # Display at most 10 similarity matches


@routes.route("/similar", methods=["GET", "POST"])
def similar() -> Response:
    """Return rendered HTML list of articles similar to a given article, given a UUID"""
    resp: Dict[str, Any] = dict(err=True)

    # Parse query args
    rv = cast(Dict[str, str], request.values)
    try:
        uuid = rv.get("id")
        if uuid:
            uuid = uuid.strip()[0:MAX_UUID_LENGTH]
    except Exception:
        uuid = None

    if not uuid:
        resp["errmsg"] = "Missing or invalid article UUID."
        return better_jsonify(**resp)

    with SessionContext(commit=True) as session:
        similar = Search.list_similar_to_article(session, uuid, n=MAX_SIM_ARTICLES)

        resp["payload"] = render_template("similar.html", similar=similar)
        resp["err"] = False

        return better_jsonify(**resp)


@routes.route("/page")
def page() -> Union[Response, str]:
    """Handler for a page displaying the parse of an arbitrary web
    page by URL or an already scraped article by UUID"""
    url = request.args.get("url")
    uuid = request.args.get("id")
    if url:
        url = url.strip()[0:MAX_URL_LENGTH]
    if uuid:
        uuid = uuid.strip()[0:MAX_UUID_LENGTH]
    if url:
        # URL has priority, if both are specified
        uuid = None
    if not url and not uuid:
        # !!! TODO: Separate error page
        return redirect(url_for("routes.main"))

    a: Optional[ArticleProxy] = None

    with SessionContext(commit=True) as session:

        if uuid:
            a = ArticleProxy.load_from_uuid(uuid, session)
        else:
            assert url is not None
            if url.startswith("http:") or url.startswith("https:"):
                # Forces a new scrape
                a = ArticleProxy.scrape_from_url(url, session)

        if a is None:
            # !!! TODO: Separate error page
            return redirect(url_for("routes.main"))

        # Prepare the article for display (may cause it to be parsed and stored)
        a.prepare(session, verbose=True, reload_parser=Settings.DEBUG)
        register = a.create_register(session, all_names=True)

        # Fetch names of article topics, if any
        topics = (
            session.query(ArticleTopic).filter(ArticleTopic.article_id == a.uuid).all()
        )
        topics = [dict(name=t.topic.name, id=t.topic.identifier) for t in topics]

        return render_template(
            "page.html", title=a.heading, article=a, register=register, topics=topics
        )


TableType = List[List[Tuple[int, Any]]]


@routes.route("/treegrid", methods=["GET"])
def tree_grid() -> Union[Response,str]:
    """Show a simplified parse tree for a single sentence"""

    txt = request.args.get("txt", "")
    tree = None
    full_tree = None
    stats: StatsDict = dict()
    with SessionContext(commit=True) as session:
        # Obtain simplified tree, full tree and stats
        tree, full_tree, stats = TreeUtility.parse_text_with_full_tree(session, txt)
        if full_tree is not None:
            # Create a more manageable, flatter tree from the binarized raw parse tree
            full_tree = ParseForestFlattener.flatten(full_tree)

    # Preprocess the trees for display, projecting them to a 2d table structure
    def _wrap_build_tbl(
        tbl: TableType, root: Any, is_nt_func, children_func, nt_info_func, t_info_func
    ):
        def _build_tbl(level: int, offset: int, nodelist: Iterable[Any]) -> int:
            """Add the tree node data to be displayed at a particular
            level (row) in the result table"""
            while len(tbl) <= level:
                tbl.append([])
            tlevel = tbl[level]
            left = sum(t[0] for t in tlevel)
            while left < offset:
                # Insert a left margin if required
                # (necessary if we'we alread inserted a terminal at a
                # level above this one)
                tlevel.append((1, None))
                left += 1
            index = offset
            if nodelist:
                for n in nodelist:
                    if is_nt_func(n):
                        # Nonterminal: display the child nodes in deeper levels
                        # and add a header on top of them, spanning their total width
                        cnt = _build_tbl(level + 1, index, children_func(n))
                        tlevel.append((cnt, nt_info_func(n)))
                        index += cnt
                    else:
                        # Terminal: display it in a single column
                        tlevel.append((1, t_info_func(n)))
                        index += 1
            return index - offset

        return _build_tbl(0, 0, [root])

    def _normalize_tbl(tbl: TableType, width: int) -> None:
        """Fill out the table with blanks so that it is square"""
        for row in tbl:
            rw = sum(t[0] for t in row)
            # Right-pad as required
            while rw < width:
                row.append((1, None))
                rw += 1

    tbl: TableType = []
    full_tbl: List[List[Tuple[int, Any]]] = []
    if tree is None:
        full_tree = None
        width = 0
        full_width = 0
        height = 0  # Height of simplified table
        full_height = 0  # Height of full table
    else:

        # Build a table structure for a simplified tree
        width = _wrap_build_tbl(
            tbl,
            tree,
            is_nt_func=lambda n: n["k"] == "NONTERMINAL",
            children_func=lambda n: n["p"],
            nt_info_func=lambda n: dict(n=n["n"], error=False),
            t_info_func=lambda n: n,
        )
        height = len(tbl)
        if width and height:
            _normalize_tbl(tbl, width)

        # Build a table structure for a full tree
        full_width = _wrap_build_tbl(
            full_tbl,
            full_tree,
            is_nt_func=lambda n: n.is_nonterminal,
            children_func=lambda n: n.children,
            nt_info_func=lambda n: dict(
                n=n.p.name, sc=n.score, error=n.p.has_tag("error")
            ),
            t_info_func=lambda n: dict(t=n.p[0].name, sc=n.score, x=n.p[1].t1),
        )
        assert full_width == width
        full_height = len(full_tbl)
        if full_width and full_height:
            _normalize_tbl(full_tbl, full_width)

    return render_template(
        "treegrid.html",
        title="Tré",
        txt=txt,
        tree=tree,
        stats=stats,
        tbl=tbl,
        height=height,
        full_tbl=full_tbl,
        full_height=full_height,
    )


@routes.route("/parsefail")
def parsefail() -> str:
    """Handler for a page showing recent sentences where parsing failed"""

    num = request.args.get("num", PARSEFAIL_DEFAULT)
    try:
        num = min(int(num), PARSEFAIL_MAX)
    except Exception:
        num = PARSEFAIL_DEFAULT

    sfails = []
    with SessionContext(read_only=True) as session:
        q = (
            session.query(Article.id, Article.timestamp, Article.tokens)
            .filter(Article.tree != None)
            .filter(Article.timestamp != None)
            .filter(Article.timestamp <= datetime.utcnow())
            .filter(Article.heading > "")
            .filter(Article.num_sentences > 0)
            .filter(Article.num_sentences != Article.num_parsed)
            .order_by(desc(cast(Column, Article.timestamp)))
            .limit(num)
        )

        for a in q.all():
            try:
                tokens = json.loads(a.tokens)
            except Exception:
                continue
            # Paragraphs
            for p in tokens:
                # Sentences
                for s in p:
                    # Tokens
                    for t in s:
                        if "err" in t:
                            # Only add well-formed sentences that start
                            # with a capital letter and end with a period
                            if s[0]["x"][0].isupper() and s[-1]["x"] == ".":
                                sfails.append([s])
                                break

    return render_template(
        "parsefail.html", title="Ógreindar setningar", sentences=sfails, num=num
    )


@routes.route("/apidoc")
@max_age(seconds=10 * 60)
def apidoc() -> str:
    """Handler for an API documentation page"""
    return render_template("apidoc.html", title="Forritaskil (API)")


@routes.route("/buy")
@max_age(seconds=10 * 60)
def buy() -> str:
    """Handler for a subscription purchase page"""
    return render_template("buy.html", title="Afnot")


@routes.route("/terms")
@max_age(seconds=10 * 60)
def terms() -> str:
    """Handler for terms & conditions page"""
    return render_template("terms.html", title="Skilmálar")


@routes.route("/about")
@max_age(seconds=10 * 60)
def about() -> str:
    """Handler for the 'About' page"""
    try:
        parser_version = reynir.version.__version__
        tokenizer_version = tokenizer.version.__version__
        python_version = "{0} ({1})".format(
            ".".join(str(n) for n in sys.version_info[:3]),
            platform.python_implementation(),
        )
        platform_name = platform.system()
    except AttributeError:
        parser_version = ""
        tokenizer_version = ""
        python_version = ""
        platform_name = ""
    return render_template(
        "about.html",
        title="Um Greyni",
        parser_version=parser_version,
        tokenizer_version=tokenizer_version,
        python_version=python_version,
        platform_name=platform_name,
    )


@routes.route("/reportimage", methods=["POST"])
def reportimage() -> Response:
    """Notification that a (person) image is wrong or broken"""
    resp: Dict[str, Any] = dict(found_new=False)

    name = request.form.get("name")
    url = request.form.get("url")
    status = request.form.get("status")

    if name and url and status:
        new_img = False
        if status == "broken":
            new_img = update_broken_image_url(name, url)
        elif status == "wrong":
            new_img = blacklist_image_url(name, url)
        if new_img:
            resp["image"] = new_img
            resp["found_new"] = True

    return better_jsonify(**resp)


@routes.route("/image", methods=["GET"])
def image() -> Response:
    """Get image for (person) name"""
    resp: Dict[str, Union[bool, Img]] = dict(found=False)

    name = request.args.get("name")
    try:
        thumb = int(request.args.get("thumb", 0))
    except Exception:
        thumb = 0

    if name:
        img = get_image_url(name, thumb=bool(thumb), cache_only=True)
        if img:
            resp["found"] = True
            resp["image"] = img

    return better_jsonify(**resp)


@routes.route("/suggest", methods=["GET"])
@cache.cached(timeout=30 * 60, key_prefix="suggest", query_string=True)
def suggest(limit: int=10) -> Response:
    """Return suggestions for query field autocompletion"""
    limit = int(request.args.get("limit", limit))
    txt = request.args.get("q", "").strip()

    suggestions: List[Dict[str, str]] = []
    whois_prefix = "hver er "
    whatis_prefix = "hvað er "

    prefix = None
    if txt.lower().startswith(whois_prefix):
        prefix = whois_prefix
    elif txt.lower().startswith(whatis_prefix):
        prefix = whatis_prefix

    if not prefix:
        return better_jsonify(suggestions=suggestions)

    with SessionContext(read_only=True) as session:
        name = txt[len(prefix) :].strip()
        model_col = None

        # Hver er Jón Jónsson ?
        if prefix is whois_prefix and name[0].isupper():
            model_col = Person.name
        # Hver er seðlabankastjóri?
        elif prefix is whois_prefix:
            model_col = Person.title
        # Hvað er UNESCO?
        elif prefix is whatis_prefix:
            model_col = Entity.name

        assert model_col is not None

        q = (
            session.query(model_col, dbfunc.count(Article.id).label("total"))
            .filter(model_col.ilike(name + "%"))
            .join(Article)
            .group_by(model_col)
            .order_by(desc("total"))
            .limit(limit)
            .all()
        )

        prefix = prefix[:1].upper() + prefix[1:].lower()
        suggestions = [{"value": (prefix + p[0] + "?"), "data": ""} for p in q]

    return better_jsonify(suggestions=suggestions)


@routes.route("/translate")
@restricted
def translate() -> str:
    """Handler for a page with machine translation of user-entered text"""
    txt = request.args.get("txt", "")[0:MAX_TEXT_LENGTH_VIA_URL]
    return render_template("translate.html", title="Vélþýðing", default_text=txt)
