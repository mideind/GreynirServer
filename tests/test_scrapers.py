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


    Tests for scrape helpers: the extraction of headings, timestamps and
    article text from the webs of the ministries and of the Central Bank,
    both of which run the Veva content management system. The HTML below
    is abridged from real pages; the structure and class names are theirs.

"""

import os
import re
import sys
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, List, Tuple

# Shenanigans to enable Pytest to discover modules in the
# main workspace directory (the parent of /tests)
basepath, _ = os.path.split(os.path.realpath(__file__))
mainpath = os.path.join(basepath, "..")
if mainpath not in sys.path:
    sys.path.insert(0, mainpath)

from fetcher import Fetcher  # noqa
from scrapers.default import (  # noqa
    Metadata,
    SedlabankinnScraper,
    StjornarradScraper,
)

ROOT: Any = SimpleNamespace(
    id=1, domain="example.is", authority=1.0, author="", description="Ráðuneytið"
)


def extract(helper: Any, html: str) -> Tuple[Metadata, List[str]]:
    """Return the metadata and the paragraphs of text that
    the given scrape helper extracts from an HTML document"""
    metadata = helper.get_metadata(helper.make_soup(html))
    content = helper.get_content(helper.make_soup(html))
    tlist = Fetcher.TextList()
    Fetcher.extract_text(content, tlist)
    return metadata, re.findall(r"\[\[(.*?)\]\]", tlist.result())


NAVIGATION = """<header><nav id="main-nav"><ul class="nav-items">
<li class="nav-item"><a href="/raduneyti/">Ráðuneyti</a></li>
<li class="nav-item"><a href="/verkefni/">Verkefni</a></li>
</ul></nav></header>"""

FOOTER = """<footer><div class="footer container"><p>Stjórnarráð Íslands,
Sölvhólsgötu 4. <a href="/personuvernd/">Meðferð persónuupplýsinga</a></p>
</div></footer>"""

MINISTRY_PAGE = (
    """<!DOCTYPE html><html lang="is"><head>
<title>Stjórnarráðið | Ný stefna um net&shy;öryggi kynnt</title>
<meta property="og:title" content="Ný stefna um netöryggi kynnt" />
</head><body>"""
    + NAVIGATION
    + """<main><div><section class="page-section"><div class="page-section-main">
<div class="rs-content">
 <div class="component-group component-group--horizontalwrap"><div>
  <div class="veva-paragraph"><strong>4. nóvember 2026</strong> /</div>
  <div class="standard-iterator"><div class="standard-iterator-item">
   <div class="veva-paragraph paragraph--lead">Utanríkisráðuneytið</div>
  </div></div>
 </div></div>
 <h1 class="title title--large">Ný stefna um net&shy;öryggi kynnt</h1>
 <div class="veva-grid"><div class="veva-grid-column">
  <div class="page-share-header"><div class="page-share-header__container">
   <figure class="page-share-header__figure">
    <img class="page-share-header__image" src="/library/?itemid=1">
     <figcaption class="page-share-header__caption">Frá fundinum í gær.</figcaption>
    </img>
   </figure>
   <div class="page-share-header__social"><a href="https://facebook.com/">Deila</a></div>
  </div></div>
 </div></div>
 <div style="padding-bottom:1em"><div class="veva-paragraph">
  <p>Ráðherra kynnti í gær nýja stefnu um netöryggi.</p>
  <p>Stefnan gildir til ársins 2030. Henni fylgir
   <a href="/adgerdaaaetlun/">aðgerðaáætlun</a> í tíu liðum.</p>
  <h2 id="helstu-atridi">Helstu atriði</h2>
  <ul><li>Aukin fræðsla fyrir almenning.</li></ul>
  <img class="asset-item-image" src="/library/?itemid=2" alt="Ráðherra" loading="eager" b-x />
  <div class="veva-paragraph">Ráðherra í ræðustól.</div>
  <div class="table-responsive table"><table><tr><td>Ár</td><td>2030</td></tr></table></div>
  <div class="infogram-embed"><iframe src="https://e.infogram.com/x"></iframe></div>
 </div></div>
 <div class="component-group component-group--vertical">
  <div class="standard-iterator standard-iterator--horizontal">
   <a class="text-link btn btn--small btn--tag" href="/leit/?tag=x">Netöryggi</a>
  </div>
  <div><a class="text-link btn btn--primary" href="javascript:history.go(-1);">Til baka</a></div>
 </div>
 <div hidden itemscope itemtype="https://veva.is/SearchMetadata">
  <meta itemprop="tag" content="netöryggi" />
  <meta itemprop="lastModified" content="2026-11-04T08:39:00.0000000" />
 </div>
</div></div>
<aside><div class="rs-content"><p>Fleiri fréttir úr ráðuneytinu.</p></div></aside>
</section></div></main>"""
    + FOOTER
    + "</body></html>"
)

# What the ministry webs delivered, with HTTP status 200, for several weeks
# in the autumn of 2026: the navigation and footer around a 404 message
MINISTRY_NOT_FOUND_PAGE = (
    "<!DOCTYPE html><html><head><title>Stjórnarráðið | 404</title></head><body>"
    + NAVIGATION
    + """<main><div><section class="page-section"><div class="page-section-main">
<div><h2>Síðan sem þú leitaðir að fannst því miður ekki</h2></div>
<div><div class="color-card"><p>Vefslóðin er ekki til.</p></div></div>
</div></section></div></main>"""
    + FOOTER
    + "</body></html>"
)

# The layout that preceded Veva
MINISTRY_OLD_PAGE = """<!DOCTYPE html><html><head><title>Frétt</title></head><body>
<main><article data-last-modified="2026-08-20 10:15:00">
<header><h1>Eldri frétt</h1></header>
<section><p>Þetta er eldri frétt.</p></section>
</article></main></body></html>"""


def test_ministry_veva_layout():
    helper = StjornarradScraper(ROOT)
    metadata, paragraphs = extract(helper, MINISTRY_PAGE)
    # The soft hyphens are removed from the heading
    assert metadata.heading == "Ný stefna um netöryggi kynnt"
    # The date shown on the page, with the time of day of the
    # last-modified stamp since that is from the same day
    assert metadata.timestamp == datetime(2026, 11, 4, 8, 39, tzinfo=timezone.utc)
    assert metadata.author == "Ráðuneytið"
    # Only the article text: no navigation, date line, ministry names,
    # heading, captions, sharing links, tables, tags, buttons or footer
    assert paragraphs == [
        "Ráðherra kynnti í gær nýja stefnu um netöryggi.",
        "Stefnan gildir til ársins 2030. Henni fylgir aðgerðaáætlun í tíu liðum.",
        "Helstu atriði",
        "Aukin fræðsla fyrir almenning.",
    ]
    assert helper.scr_version == "2.0"


def test_ministry_timestamp_of_page_modified_later():
    # A page edited on a later day keeps its date of publication
    html = MINISTRY_PAGE.replace("2026-11-04T08:39:00", "2026-12-01T12:00:00")
    metadata, _ = extract(StjornarradScraper(ROOT), html)
    assert metadata.timestamp == datetime(2026, 11, 4, tzinfo=timezone.utc)


def test_ministry_page_without_article():
    helper = StjornarradScraper(ROOT)
    # A 'not found' page yields no text at all, rather than
    # the navigation and the footer of the page
    _, paragraphs = extract(helper, MINISTRY_NOT_FOUND_PAGE)
    assert paragraphs == []
    # ...and is recognized as such when fetched, so it is not stored
    is_article = StjornarradScraper._is_article_page
    assert not is_article(helper.make_soup(MINISTRY_NOT_FOUND_PAGE))
    assert not is_article(helper.make_soup("<html><head></head></html>"))
    assert not is_article(None)
    assert is_article(helper.make_soup(MINISTRY_PAGE))
    assert is_article(helper.make_soup(MINISTRY_OLD_PAGE))


def test_ministry_fetch_url(monkeypatch: Any):
    helper = StjornarradScraper(ROOT)
    pages = {"good": MINISTRY_PAGE, "gone": MINISTRY_NOT_FOUND_PAGE, "down": None}
    monkeypatch.setattr(Fetcher, "raw_fetch_url", staticmethod(lambda url: pages[url]))
    assert helper.fetch_url("good") == MINISTRY_PAGE
    assert helper.fetch_url("gone") is None
    assert helper.fetch_url("down") is None


def test_ministry_old_layout():
    metadata, paragraphs = extract(StjornarradScraper(ROOT), MINISTRY_OLD_PAGE)
    assert metadata.heading == "Eldri frétt"
    assert metadata.timestamp == datetime(2026, 8, 20, 10, 15, tzinfo=timezone.utc)
    assert paragraphs == ["Þetta er eldri frétt."]


def central_bank_page(body: str) -> str:
    return (
        """<!DOCTYPE html><html lang="is"><head>
<title>Seðlabanki Íslands | Vextir óbreyttir</title>
<meta property="og:title" content="Vextir óbreyttir 10. nóvember 2026" />
</head><body><div id="page-container"><header>
<div class="navbar-drawer"><a href="/peningastefna/">Peningastefna</a></div>
<div class="page-header-content"><div class="veva-page-title">
 <h1 class="display--large">Vext&shy;ir óbreyttir</h1>
</div></div></header>
<main id="main" class="content-body"><div class="sticky-column">
<aside><div class="sticky-column-aside-content">
 <div class="eyebrow">10. nóvember 2026</div><div class="article-authors"></div>
</div></aside>
<section id="content-section" class="sticky-main-content"><div class="rs-content">
 <h2 class="hidden-heading">Vextir óbreyttir 10. nóvember 2026</h2>
 <div><div class="standard-iterator"><div class="standard-iterator-item">
  <div class="tag"><a class="tag-content" href="/safnsida/?Tag=x">peningastefna</a></div>
 </div></div></div>
 <div><div class="content-header"><div class="content-header-body">
  <div class="rs_skip rsbtn" id="readspeaker_button1">
   <a class="rsbtn_play" href="https://readspeaker.com/"><span>Hlusta</span></a>
  </div>
 </div></div></div>"""
        + body
        + """
 <div style="display:none;" data-veva-tags="x" data-last-modified="2026-11-10 16:50"></div>
</div></section></div></main>
<footer><div class="social-sharing-caption">Deila</div>
<div class="contact-info">Seðlabanki Íslands, Kalkofnsvegi 1</div></footer>
</div></body></html>"""
    )


CENTRAL_BANK_TEXT = """<div class="standard-iterator standard-iterator--vertical">
 <div class="standard-iterator-item"><div class="veva-paragraph attachment-right">
  <div class="paragraph-attachment"><figure class="asset-item">
   <img class="asset-item-image" src="/library/?itemid=3"/>
   <figcaption>Seðlabankastjóri</figcaption>
  </figure></div>
  <p>Peningastefnunefnd hefur ákveðið að halda vöxtum óbreyttum.</p>
  <p>Verðbólga mældist 4% í október.</p>
 </div></div>
 <div class="standard-iterator-item">
  <div class="card"><div class="card-content"><h2>Tafla 1: Vextir</h2>
   <div class="table-responsive table"><table><tr><td><p>Meginvextir</p></td>
   <td><p>7,5</p></td></tr></table></div>
  </div></div>
 </div>
 <div class="standard-iterator-item">
  <div class="card"><div class="card-content">
   <div class="veva-paragraph"><p>Næsta ákvörðun verður kynnt í febrúar.</p></div>
  </div></div>
 </div>
 <div class="standard-iterator-item">
  <a class="hide-link-icon file-type-pdf download-link--download" href="/library/?itemid=4">
   <span class="file-type-icon"></span><span class="link-text">Yfirlýsing nefndarinnar</span>
   <span class="file-size">(95,48 KB)</span></a>
 </div>
 <div class="standard-iterator-item">
  <div class="embedded-page"><iframe src="https://vimeo.com/event/1" title="Útsending"></iframe></div>
 </div>
</div>"""

CENTRAL_BANK_PARAGRAPHS = [
    "Peningastefnunefnd hefur ákveðið að halda vöxtum óbreyttum.",
    "Verðbólga mældist 4% í október.",
    "Næsta ákvörðun verður kynnt í febrúar.",
]


def test_central_bank_veva_layout():
    helper = SedlabankinnScraper(ROOT)
    html = central_bank_page('<div class="article-content">' + CENTRAL_BANK_TEXT + "</div>")
    metadata, paragraphs = extract(helper, html)
    # The heading is without the date that og:title has appended
    assert metadata.heading == "Vextir óbreyttir"
    assert metadata.timestamp == datetime(2026, 11, 10, 16, 50, tzinfo=timezone.utc)
    assert metadata.author == "Seðlabanki Íslands"
    # Only the article text: no menu, heading, tags, 'listen' button, image
    # captions, tables with their headings, download links or footer
    assert paragraphs == CENTRAL_BANK_PARAGRAPHS
    assert helper.scr_version == "2.0"


def test_central_bank_without_article_content_wrapper():
    helper = SedlabankinnScraper(ROOT)
    # Some pages have no article-content wrapper around the text...
    _, paragraphs = extract(helper, central_bank_page(CENTRAL_BANK_TEXT))
    assert paragraphs == CENTRAL_BANK_PARAGRAPHS
    # ...and others have an empty one beside it
    html = central_bank_page(CENTRAL_BANK_TEXT + '<div class="article-content"></div>')
    _, paragraphs = extract(helper, html)
    assert paragraphs == CENTRAL_BANK_PARAGRAPHS


def test_central_bank_heading_fallback():
    html = central_bank_page('<div class="article-content"><p>Texti.</p></div>')
    html = re.sub(r'<div class="veva-page-title">.*?</div>', "", html, flags=re.S)
    metadata, paragraphs = extract(SedlabankinnScraper(ROOT), html)
    assert metadata.heading == "Vextir óbreyttir"
    assert paragraphs == ["Texti."]


def test_central_bank_old_layout():
    html = """<!DOCTYPE html><html><head>
<meta property="og:title" content="Eldri frétt" /></head><body>
<div class="media" data-last-modified="2025-01-15 09:30:00"><div class="media-body">
<h2>Eldri frétt</h2><p>Þetta er eldri frétt.</p>
<a class="til-baka" href="/">Til baka</a></div></div></body></html>"""
    metadata, paragraphs = extract(SedlabankinnScraper(ROOT), html)
    assert metadata.heading == "Eldri frétt"
    assert metadata.timestamp == datetime(2025, 1, 15, 9, 30, tzinfo=timezone.utc)
    assert paragraphs == ["Þetta er eldri frétt."]
