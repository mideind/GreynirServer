"""

    Greynir: Natural language processing for Icelandic

    Default scraping helpers module

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


    This module implements a set of default scraping helpers for
    a number of Icelandic websites. The particular scraping module and
    class to be used for each root website is selected in the roots
    table of the scraper database.

"""

import re
import logging
from typing import Optional, Sequence
import urllib.parse as urlparse
import requests
from datetime import datetime

from bs4 import BeautifulSoup, NavigableString, Tag


MODULE_NAME = __name__

# The HTML parser to use with BeautifulSoup
# _HTML_PARSER = "html5lib"
_HTML_PARSER = "html.parser"

# Icelandic month names. Used for parsing
# date strings in some of the scrapers
MONTHS: Sequence[str] = [
    "janúar",
    "febrúar",
    "mars",
    "apríl",
    "maí",
    "júní",
    "júlí",
    "ágúst",
    "september",
    "október",
    "nóvember",
    "desember",
]

MONTHS_ABBR: Sequence[str] = [
    "jan",
    "feb",
    "mar",
    "apr",
    "maí",
    "jún",
    "júl",
    "ágú",
    "sep",
    "okt",
    "nóv",
    "des",
]


class Metadata:
    """ The metadata returned by the helper.get_metadata() function """

    def __init__(
        self,
        heading: Optional[str],
        author: str,
        timestamp: datetime,
        authority: float,
        icon: str,
    ) -> None:
        self.heading = heading
        self.author = author
        self.timestamp = timestamp
        self.authority = authority
        self.icon = icon

    def __repr__(self) -> str:
        return "{0}(heading='{1}', author='{2}', ts='{3}')".format(
            type(self).__name__, self.heading, self.author, self.timestamp
        )


class ScrapeHelper:
    """ Generic scraping helper base class """

    def __init__(self, root):
        self._domain = root.domain
        self._authority = root.authority
        self._author = root.author
        self._description = root.description
        self._root_id = root.id
        self._feeds = []

    def make_soup(self, doc):
        """ Make a soup object from a document """
        soup = BeautifulSoup(doc, _HTML_PARSER)
        return None if (soup is None or soup.html is None) else soup

    def skip_url(self, url: str) -> bool:
        """ Return True if this URL should not be scraped """
        return False  # Scrape all URLs by default

    def skip_rss_entry(self, entry):
        """ Return True if URL in RSS feed entry should be skipped """
        return False

    @staticmethod
    def unescape(s: str) -> str:
        """ Unescape headings that may contain Unicode characters """

        def replacer(matchobj):
            m = matchobj.group(1)
            assert m
            return chr(int(m, 16))  # Hex

        # Example: \u0084 -> chr(132)
        return re.sub(r"\\u([0-9a-fA-F]{4})", replacer, s) if s else ""

    def get_metadata(self, soup) -> Metadata:
        """ Analyze the article HTML soup and return metadata """
        return Metadata(
            heading=None,
            author=self.author,
            timestamp=datetime.utcnow(),
            authority=self.authority,
            icon=self.icon,
        )

    @staticmethod
    def _get_body(soup):
        """ Can be overridden in subclasses in special situations """
        return soup.html.body

    def get_content(self, soup):
        """ Find the actual article content within an HTML soup
            and return its parent node """
        if not soup or not soup.html or not soup.html.body:
            # No body in HTML: something is wrong, return None
            logging.warning("get_content returning None")
            return None
        f = getattr(self, "_get_content")
        if callable(f):
            content = f(self._get_body(soup))
            if content:
                # Always delete embedded social media widgets
                content = ScrapeHelper.del_social_embeds(content)
        else:
            content = None
        # By default, return the entire body
        return content or self._get_body(soup)

    @property
    def root_id(self):
        """ Return the root id corresponding to this domain """
        return self._root_id

    @property
    def domain(self) -> str:
        return self._domain

    @property
    def icon(self) -> str:
        """ Return the name of an icon file for this root """
        return self._domain + ".png"

    @property
    def authority(self) -> float:
        return self._authority

    @property
    def author(self) -> str:
        return self._author

    @property
    def feeds(self):
        return self._feeds

    @property
    def scr_module(self) -> str:
        """ Return the name of the module for this scraping helper class """
        return MODULE_NAME

    @property
    def scr_class(self) -> str:
        """ Return the name of this scraping helper class """
        return self.__class__.__name__

    @property
    def scr_version(self) -> str:
        """ Return the version of this scraping helper class """
        # If no VERSION attribute in the class, return a default '1.0'
        return getattr(self.__class__, "VERSION", "1.0")

    @staticmethod
    def general_filter(tag, name, attr, attr_val) -> bool:
        """ General filter function to use with BeautifulSoup.find().
            Looks for tag['attr'] == attr_val or attr_val in tag['attr'].
            attr_val can also be iterable, in which case all the given
            attribute values must be present on the tag for the match to
            be made. """
        if tag.name != name or not tag.has_attr(attr):
            return False
        a = tag[attr]
        assert a is not None

        # Handle both potentially multi-valued attrs
        # (for instance multiple classes on a div),
        # and multi-valued attr_vals (for instance more
        # than one class that should be present)
        if isinstance(a, str):
            a = set(a.split())
        if isinstance(attr_val, str):
            return attr_val in a
        return all(v in a for v in attr_val)

    @staticmethod
    def meta_property_filter(tag, prop_val, prop_attr="property"):
        """ Filter function for meta properties in HTML documents """
        # By default, catch <meta property='prop_val' content='X'>
        return ScrapeHelper.general_filter(tag, "meta", prop_attr, prop_val)

    @staticmethod
    def div_class_filter(tag, cls):
        """ Filter function for divs in HTML documents, selected by class """
        return ScrapeHelper.general_filter(tag, "div", "class", cls)

    @staticmethod
    def div_id_filter(tag, div_id):
        """ Filter function for divs in HTML documents, selected by id """
        return ScrapeHelper.general_filter(tag, "div", "id", div_id)

    @staticmethod
    def meta_property(soup, property_name, prop_attr="property"):
        try:
            f = lambda tag: ScrapeHelper.meta_property_filter(
                tag, property_name, prop_attr
            )
            mp = soup.html.head.find(f)
            if not mp:
                logging.warning(
                    "meta property {0} not found in soup.html.head".format(
                        property_name
                    )
                )
            return str(mp["content"]) if mp else None
        except Exception as e:
            logging.warning(
                "Exception in meta_property('{0}'): {1}".format(property_name, e)
            )
            return None

    @staticmethod
    def tag_prop_val(soup, tag, prop, val):
        """ Find a tag of a given type with an attribute having the specified value """
        if not soup:
            return None
        return soup.find(lambda t: ScrapeHelper.general_filter(t, tag, prop, val))

    @staticmethod
    def tag_class(soup, tag, cls):
        """ Find a tag of a given type with a particular class """
        return ScrapeHelper.tag_prop_val(soup, tag, "class", cls)

    @staticmethod
    def div_class(soup, *argv):
        """ Find a div with a particular class/set of classes within the
            HTML soup, recursively within its parent if more than one
            div spec is given """
        for cls in argv:
            if not soup:
                return None
            f = lambda tag: ScrapeHelper.div_class_filter(tag, cls)
            soup = soup.find(f)
        return soup

    @staticmethod
    def nested_tag(soup, *argv):
        """ Find a tag within a nested hierarchy of tags """
        for next_tag in argv:
            if not soup:
                return None
            soup = soup.find(lambda tag: tag.name == next_tag)
        return soup

    @staticmethod
    def div_id(soup, div_id):
        """ Find a div with a particular id """
        if not soup or not div_id:
            return None
        f = lambda tag: ScrapeHelper.div_id_filter(tag, div_id)
        return soup.find(f)

    @staticmethod
    def del_tag_prop_val(soup, tag, prop, val):
        """ Delete all occurrences of the tag that have
            a property with the given value """
        if soup is None:
            return
        while True:
            s = ScrapeHelper.tag_prop_val(soup, tag, prop, val)
            if s is None:
                break
            s.decompose()

    @staticmethod
    def del_div_class(soup, *argv):
        """ Delete all occurrences of the specified div.class """
        if soup is None:
            return
        while True:
            s = ScrapeHelper.div_class(soup, *argv)
            if s is None:
                break
            s.decompose()

    @staticmethod
    def del_tag(soup, tag_name):
        """ Delete all occurrences of the specified tag """
        if soup is None:
            return
        while True:
            s = soup.find(lambda tag: tag.name == tag_name)
            if s is None:
                break
            s.decompose()

    @staticmethod
    def del_social_embeds(soup):
        # Delete all iframes and embedded FB/Twitter/Instagram posts
        ScrapeHelper.del_tag(soup, "iframe")
        ScrapeHelper.del_tag(soup, "twitterwidget")
        ScrapeHelper.del_div_class(soup, "fb-post")
        ScrapeHelper.del_tag_prop_val(soup, "blockquote", "class", "instagram-media")
        ScrapeHelper.del_tag_prop_val(soup, "blockquote", "class", "twitter-tweet")
        return soup


class KjarninnScraper(ScrapeHelper):
    """ Scraping helper for Kjarninn.is """

    def __init__(self, root):
        super().__init__(root)
        self._feeds = ["https://kjarninn.is/feed/"]

    def skip_url(self, url):
        """ Return True if this URL should not be scraped """
        s = urlparse.urlsplit(url)
        if s.path and s.path.startswith("/tag/"):
            return True
        if s.path and s.path.startswith("/hladvarp/"):
            return True
        return False  # Scrape all other URLs by default

    def get_metadata(self, soup):
        """ Analyze the article soup and return metadata """
        metadata = super().get_metadata(soup)
        # Extract the heading from the OpenGraph (Facebook) og:title meta property
        heading = ScrapeHelper.meta_property(soup, "og:title") or ""
        if "|" in heading:
            heading = heading[0 : heading.index("|")].rstrip()
        heading = self.unescape(heading)
        # Extract the publication time from the article:published_time meta property
        ts = ScrapeHelper.meta_property(soup, "article:published_time")
        if ts:
            timestamp = datetime(
                year=int(ts[0:4]),
                month=int(ts[5:7]),
                day=int(ts[8:10]),
                hour=int(ts[11:13]),
                minute=int(ts[14:16]),
                second=int(ts[17:19]),
            )
        else:
            timestamp = datetime.utcnow()
        # Exctract the author name
        # Start with <span itemprop="author">
        f = lambda xtag: ScrapeHelper.general_filter(xtag, "span", "itemprop", "author")
        tag = soup.html.body.find(f) if soup.html.body else None
        if not tag:
            # Then, try <span class="author">
            f = lambda xtag: ScrapeHelper.general_filter(
                xtag, "span", "class", "author"
            )
            tag = soup.html.body.find(f) if soup.html.body else None
        if not tag:
            logging.warning("span.class.author tag not found in soup.html.body")
        author = str(tag.string) if tag and tag.string else "Ritstjórn Kjarnans"
        metadata.heading = heading
        metadata.author = author
        metadata.timestamp = timestamp
        return metadata

    # noinspection PyMethodMayBeStatic
    def _get_content(self, soup_body):
        """ Find the article content (main text) in the soup """
        article = soup_body.find("article")
        if not article:
            article = ScrapeHelper.div_class(soup_body, "article-body")

        # soup_body has already been sanitized in the ScrapeHelper base class
        if article is None:
            logging.warning("Kjarninn scraper: soup_body article is None")
            return None

        # Delete div.container.title-container tags from the content
        title_cont = ScrapeHelper.div_class(article, ("container", "title-container"))
        if title_cont is not None:
            title_cont.decompose()

        # Delete div.container.quote-container tags from the content
        ScrapeHelper.del_div_class(article, ("container", "quote-container"))
        # Delete div.container-fluid tags from the content
        ScrapeHelper.del_div_class(article, "container-fluid")
        # Get the content itself
        content = ScrapeHelper.div_class(article, "article-body")
        if content is None:
            # No div.article-body present
            content = article
        # Delete div.category-snippet tags from the content
        ScrapeHelper.del_div_class(content, "category_snippet")
        # Delete image containers from content
        ScrapeHelper.del_div_class(content, "image-container")
        # Delete "Lestu meira" lists at bottom of article
        ScrapeHelper.del_div_class(content, "tag_list_block")
        # Delete div.ad-container tags from the content
        ScrapeHelper.del_div_class(content, "ad-container")
        # Delete sub-headlines
        ScrapeHelper.del_tag(article, "h2")
        ScrapeHelper.del_tag(content, "h3")
        ScrapeHelper.del_tag(content, "h4")

        return content


class RuvScraper(ScrapeHelper):
    """ Scraping helper for RUV.is """

    def __init__(self, root):
        super().__init__(root)
        # Not using RÚV's RSS feed for now since it contains English-language articles
        # self._feeds = ["http://www.ruv.is/rss/frettir"]

    def skip_url(self, url):
        """ Return True if this URL should not be scraped """
        s = urlparse.urlsplit(url)
        p = s.path
        # Only scrape urls with the right path prefix
        if p and p.startswith("/frett/"):
            return False  # Don't skip
        return True

    def get_metadata(self, soup):
        """ Analyze the article soup and return metadata """
        metadata = super().get_metadata(soup)
        # Extract the heading from the OpenGraph (Facebook) og:title meta property
        heading = ScrapeHelper.meta_property(soup, "og:title") or ""
        heading = self.unescape(heading)
        # Extract the publication time from the article:published_time meta property
        ts = ScrapeHelper.meta_property(soup, "article:published_time")
        if ts:
            timestamp = datetime(
                year=int(ts[0:4]),
                month=int(ts[5:7]),
                day=int(ts[8:10]),
                hour=int(ts[11:13]),
                minute=int(ts[14:16]),
                second=int(ts[17:19]),
            )
        else:
            timestamp = datetime.utcnow()
        # Exctract the author name
        # Look for div[class == 'view-id-author'] > div[class == 'clip']
        clip = ScrapeHelper.div_class(soup.html.body, "view-id-author", "clip")
        if not clip:
            clip = ScrapeHelper.div_class(soup.html.body, "view-content", "clip")
        author = clip.text.strip() if clip else "Fréttastofa RÚV"
        metadata.heading = heading
        metadata.author = author
        metadata.timestamp = timestamp
        return metadata

    # noinspection PyMethodMayBeStatic
    def _get_content(self, soup_body):
        """ Find the article content (main text) in the soup """
        content = ScrapeHelper.div_class(
            soup_body, ("region", "region-two-66-33-first"), "region-inner"
        )
        if content is None:
            # Try alternative layout
            content = ScrapeHelper.div_class(soup_body, "view-content", "second")
        if content is None:
            # Fallback to outermost block
            content = ScrapeHelper.div_class(soup_body, ("block", "block-system"))
        # Still no content? Return empty soup
        if content is None:
            return BeautifulSoup("", _HTML_PARSER)

        ScrapeHelper.del_div_class(
            content, "pane-custom"
        )  # Sharing stuff at bottom of page
        ScrapeHelper.del_div_class(content, "title-wrapper")  # Additional header stuff
        ScrapeHelper.del_div_class(content, "views-field-field-user-display-name")
        ScrapeHelper.del_div_class(content, "field-name-myndatexti-credit-source")
        ScrapeHelper.del_div_class(content, "field-name-field-media-reference")
        ScrapeHelper.del_div_class(content, "field-name-field-myndatexti")
        ScrapeHelper.del_div_class(content, "pane-menningin-faerslur-panel-pane-16")
        ScrapeHelper.del_div_class(content, "region-conditional-stack")
        ScrapeHelper.del_div_class(content, "pane-author")
        ScrapeHelper.del_div_class(content, "user-profile")
        ScrapeHelper.del_div_class(content, "pane-node-created")
        ScrapeHelper.del_div_class(content, "field-name-video-player-sip-vefur")
        ScrapeHelper.del_div_class(content, "field-name-sip-vefur-image-credit")
        ScrapeHelper.del_div_class(content, "pane-node-field-authors")
        # Remove hidden taxonomy/sharing lists at bottom of article
        for ul in content.find_all("ul", {"class": "links"}):
            ul.decompose()
        for ul in content.find_all("ul", {"class": "rrssb-buttons"}):
            ul.decompose()
        return content


class MblScraper(ScrapeHelper):
    """ Scraping helper for Mbl.is """

    _SKIP_PREFIXES = [
        "/fasteignir/",
        "/english/",
        "/frettir/bladamenn/",
        "/frettir/sjonvarp/",
        "/frettir/knippi/",
        "/frettir/colorbox/",
        "/frettir/lina_snippet/",
        "/myndasafn/",
        "/atvinna/",
        "/vidburdir/",
        "/sport/",
        "/mogginn/",
    ]

    def __init__(self, root):
        super().__init__(root)
        self._feeds = [
            "https://www.mbl.is/feeds/fp/",
            "https://www.mbl.is/feeds/innlent/",
            "https://www.mbl.is/feeds/erlent/",
            "https://www.mbl.is/feeds/togt/",
            "https://www.mbl.is/feeds/helst/",
            "https://www.mbl.is/feeds/nyjast/",
            "https://www.mbl.is/feeds/vidskipti/",
            "https://www.mbl.is/feeds/200milur/",
            "https://www.mbl.is/feeds/sport/",
            "https://www.mbl.is/feeds/folk/",
            "https://www.mbl.is/feeds/matur/",
            "https://www.mbl.is/feeds/smartland/",
            "https://www.mbl.is/feeds/bill/",
            "https://www.mbl.is/feeds/k100/",
        ]

    def skip_url(self, url):
        """ Return True if this URL should not be scraped """
        s = urlparse.urlsplit(url)
        path = s.path
        if path:
            if any(path.startswith(p) for p in self._SKIP_PREFIXES):
                return True
            if "/breytingar_i_islenska_fotboltanum/" in path:
                # Avoid lots of details about soccer players
                return True
            if "/felagaskipti_i_enska_fotboltanum/" in path:
                return True
        return False  # Scrape all URLs by default

    def get_metadata(self, soup):
        """ Analyze the article soup and return metadata """
        metadata = super().get_metadata(soup)

        url = ScrapeHelper.meta_property(soup, "og:url") or ""

        # Extract the heading from the meta title or
        # OpenGraph (Facebook) og:title property
        heading = ScrapeHelper.meta_property(soup, "title", prop_attr="name") or ""
        if not heading:
            heading = ScrapeHelper.meta_property(soup, "og:title") or ""
        if not heading:
            # Check for a h2 inside a div.pistill-entry
            p_e = ScrapeHelper.div_class(soup.html.body, "pistill-entry")
            if p_e and p_e.h2:
                heading = p_e.h2.string
        if not heading:
            h1 = soup.find("h1", {"class": "newsitem-fptitle"})
            if h1:
                heading = h1.get_text()

        if heading:
            if heading.endswith(" - mbl.is"):
                heading = heading[0:-9]
            if heading.endswith(" - K100"):
                heading = heading[0:-7]
            heading = heading.strip()
            heading = self.unescape(heading)

        # Extract the publication time from the article:published_time meta property
        # A dateline from mbl.is looks like this: Viðskipti | mbl | 24.8.2015 | 10:48
        dateline_elem = ScrapeHelper.div_class(soup.html.body, "dateline")
        dateline = (
            "".join(dateline_elem.stripped_strings).split("|") if dateline_elem else ""
        )
        timestamp = None
        if dateline:
            ix = 0
            date = None
            time = None
            while ix < len(dateline):
                if "." in dateline[ix]:
                    # Might be date
                    try:
                        date = [int(x) for x in dateline[ix].split(".")]
                    except:
                        date = None
                elif ":" in dateline[ix]:
                    # Might be time
                    try:
                        time = [int(x) for x in dateline[ix].split(":")]
                    except:
                        time = None
                if time and date:
                    # Seems we're done
                    break
                ix += 1
            if time and date:
                try:
                    timestamp = datetime(
                        year=date[2],
                        month=date[1],
                        day=date[0],
                        hour=time[0],
                        minute=time[1],
                    )
                except Exception as e:
                    logging.warning(
                        "Exception when obtaining date of mbl.is article '{0}': {1}".format(
                            url, e
                        )
                    )
                    timestamp = None

        if timestamp is None:
            logging.warning("Failed to obtain date of mbl.is article '{0}'".format(url))
            timestamp = datetime.utcnow()

        # Extract the author name
        rp = ScrapeHelper.div_class(soup.html.body, "frett-main", "reporter-profile")
        f = lambda tag: ScrapeHelper.general_filter(tag, "a", "class", "name")
        rname = rp.find(f) if rp else None
        if rname:
            rname = rname.string
        else:
            # Probably a blog post
            rp = ScrapeHelper.div_class(soup.html.body, "pistlar-author-profile-box")
            if rp and rp.h4:
                rname = rp.h4.string

        author = rname if rname else "Ritstjórn mbl.is"
        metadata.heading = heading
        metadata.author = author
        metadata.timestamp = timestamp
        return metadata

    def _get_content(self, soup_body):
        """ Find the article content (main text) in the soup """
        # 'New style' as of May 23, 2016
        soup = ScrapeHelper.div_class(soup_body, "main-layout")
        if soup is None:
            # Revert to 'old style'
            soup = ScrapeHelper.div_class(soup_body, "frett-main")
        if soup is None:
            # Could be a blog post
            soup = ScrapeHelper.div_class(soup_body, "pistill-entry-body")
        if soup is None:
            # Subsection front page?
            soup = ScrapeHelper.tag_prop_val(soup_body, "main", "role", "main")
        if soup is None:
            # Could be a picture collection - look for div#non-galleria
            soup = ScrapeHelper.div_id(soup_body, "non-galleria")
        if soup is None:
            # Could be special layout for /ferdalog
            soup = ScrapeHelper.div_class(soup_body, "newsitem")
        if soup is None:
            logging.warning(
                "_get_content: "
                "soup_body.div.main-layout/frett-main/pistill-entry-body is None"
            )

        if soup:
            # Delete h1 tags from the content
            s = soup.h1
            if s is not None:
                s.decompose()
            # Delete p/strong/a paragraphs from the content (intermediate links)
            for p in soup.find_all("p"):
                try:
                    if p.strong and p.strong.a:
                        p.decompose()
                except AttributeError:
                    pass

            for ul in soup.find_all("ul", {"class": "list-group"}):
                ul.decompose()

            deldivs = (
                "info",
                "reporter-profile",
                "reporter-line",
                "mainimg-big",
                "extraimg-big-w-txt",
                "extraimg-big",
                "newsimg-left",
                "newsimg-right",
                "newsitem-image",
                "newsitem-image-center",
                "newsitem-fptitle",
                "newsitem-intro",
                "sidebar-row",
                "reporter-line",
                "newsitem-bottom-toolbar",
                "sidebar-mobile",
                "mbl-news-link",
                "embedded-media",
                "r-sidebar",
                "big-teaser",
                "imagebox",
                "imagebox-description",
                "augl",
                "box-teaser",
                "reporter-line",
            )
            for divclass in deldivs:
                ScrapeHelper.del_div_class(soup, divclass)

        return soup


class VisirScraper(ScrapeHelper):
    """ Scraping helper for Visir.is """

    _SKIP_PREFIXES = [
        "/english/",
        "/section/",  # All /section/X URLs seem to be (extreeeemely long) summaries
        "/property/",  # Fasteignaauglýsingar
        "/lifid/",
        "/paper/fbl/",
        "/soyouthinkyoucansnap",
        "/k/",
    ]

    def __init__(self, root):
        super().__init__(root)
        self._feeds = ["http://www.visir.is/rss/allt"]

    def skip_url(self, url):
        """ Return True if this URL should not be scraped """
        s = urlparse.urlsplit(url)
        if s.netloc.startswith("fasteignir.") or s.netloc.startswith("albumm."):
            # Skip fasteignir.visir.is and albumm.visir.is
            return True
        if not s.path or any(s.path.startswith(p) for p in self._SKIP_PREFIXES):
            return True
        return False  # Scrape all URLs by default

    def skip_rss_entry(self, entry):
        # Skip live sport event pages
        title = entry.title
        if title.startswith("Í beinni: ") or title.startswith("Leik lokið: "):
            return True
        return False

    def get_metadata(self, soup):
        """ Analyze the article soup and return metadata """
        metadata = super().get_metadata(soup)

        url = ScrapeHelper.meta_property(soup, "og:url") or ""

        # Extract the heading from the OpenGraph (Facebook) og:title meta property
        heading = ScrapeHelper.meta_property(soup, "og:title") or ""
        heading = self.unescape(heading)
        if heading.startswith("Vísir - "):
            heading = heading[8:]
        if heading.endswith(" - Glamour"):
            heading = heading[:-10]
        if heading.endswith(" - Vísir"):
            heading = heading[:-8]
        heading = heading.rstrip("|")

        # Timestamp
        timestamp = None
        time_el = soup.find("time", {"class": "article-single__time"})
        if time_el:
            datestr = time_el.get_text().rstrip()

            # Example: "21.1.2019 09:04"
            if re.search(r"^\d{1,2}\.\d{1,2}\.\d\d\d\d\s\d{1,2}:\d{1,2}", datestr):
                try:
                    timestamp = datetime.strptime(datestr, "%d.%m.%Y %H:%M")
                except Exception:
                    pass
            # Example: "17. janúar 2019 14:30"
            else:
                try:
                    (mday, m, y, hm) = datestr.split()
                    (hour, mins) = hm.split(":")
                    mday = mday.replace(".", "")
                    month = MONTHS.index(m) + 1

                    timestamp = datetime(
                        year=int(y),
                        month=int(month),
                        day=int(mday),
                        hour=int(hour),
                        minute=int(mins),
                    )
                except Exception:
                    pass

        if timestamp is None:
            logging.warning("Could not parse date in visir.is article {0}".format(url))
            timestamp = datetime.utcnow()

        # Author
        author = ScrapeHelper.tag_prop_val(soup, "a", "itemprop", "author")
        if author:
            author = author.string
        else:
            # Check for an author name at the start of the article
            article = ScrapeHelper.div_class(soup, "articlewrapper")
            if article:
                author = ScrapeHelper.div_class(article, "meta")
                if author:
                    author = author.string
            else:
                # Updated format of Visir.is
                article = ScrapeHelper.div_class(soup, "article-single__meta")
                if article:
                    try:
                        author = article.span.a.string
                    except:
                        author = ""
                    if not author:
                        try:
                            author = article.span.string
                        except:
                            pass
        if not author:
            author = "Ritstjórn visir.is"
        else:
            author = author.strip()
            if author.endswith(" skrifar"):
                # 'Jón Jónsson skrifar'
                author = author[0:-8]
        metadata.heading = heading.strip()
        metadata.author = author
        metadata.timestamp = timestamp
        return metadata

    @staticmethod
    def _get_body(soup):
        """ Hack to fix bug in visir.is HTML: must search entire
            document, not just the html body """
        return soup

    def _get_content(self, soup_body):
        """ Find the article content (main text) in the soup """

        # We shouldn't even try to extract text from the live sport event pages
        liveheader = ScrapeHelper.div_id(soup_body, "livefeed-sporthead")
        if liveheader:
            return BeautifulSoup("", _HTML_PARSER)  # Return empty soup.

        soup = ScrapeHelper.div_class(soup_body, "article", "articletext")
        if not soup:
            # Check for new Visir layout
            soup = ScrapeHelper.div_class(soup_body, "article-single__content")
        if not soup:
            # Check for normal Visir layout
            soup = ScrapeHelper.div_class(soup_body, "articlewrapper")
        if soup:
            # Delete div.media from the content
            ScrapeHelper.del_div_class(soup, "media")
            # Delete div.meta from the content
            ScrapeHelper.del_div_class(soup, "meta")
            # Delete video players
            ScrapeHelper.del_div_class(soup, "jwplayer")
            ScrapeHelper.del_div_class(soup, "embedd-media-player")
            # Delete figure tags from the content
            if soup.figure:
                soup.figure.decompose()
            for fc in soup.find_all("figcaption"):
                fc.decompose()

        return soup


class EyjanScraper(ScrapeHelper):

    """ Scraping helper for Eyjan.pressan.is """

    def __init__(self, root):
        super().__init__(root)

    def get_metadata(self, soup):
        """ Analyze the article soup and return metadata """
        metadata = super().get_metadata(soup)
        # Extract the heading from the OpenGraph (Facebook) og:title meta property
        heading = ScrapeHelper.meta_property(soup, "og:title") or ""
        heading = self.unescape(heading)
        # Extract the publication time from the <span class='date'></span> contents
        dateline_elem = ScrapeHelper.div_class(soup, "article-full")
        dateline_elem = ScrapeHelper.tag_class(dateline_elem, "span", "date")
        dateline = (
            "".join(dateline_elem.stripped_strings).split() if dateline_elem else ""
        )
        timestamp = None
        if dateline:
            # Example: Þriðjudagur 15.12.2015 - 14:14
            try:
                date = [int(x) for x in dateline[1].split(".")]
                time = [int(x) for x in dateline[3].split(":")]
                timestamp = datetime(
                    year=date[2],
                    month=date[1],
                    day=date[0],
                    hour=time[0],
                    minute=time[1],
                )
            except Exception as e:
                logging.warning(
                    "Exception when obtaining date of eyjan.is article: {0}".format(e)
                )
                timestamp = None
        if timestamp is None:
            timestamp = datetime.utcnow()
        # Extract the author name
        author = "Ritstjórn eyjan.is"
        metadata.heading = heading
        metadata.author = author
        metadata.timestamp = timestamp
        return metadata

    def _get_content(self, soup_body):
        """ Find the article content (main text) in the soup """
        # Delete div.container-fluid tags from the content
        article = ScrapeHelper.div_class(soup_body, "article-full")
        if article is None:
            article = soup_body
            if article is None:
                logging.warning("No content for eyjan.is article")
                return None
        # Remove link to comments
        soup = article.a
        if soup is not None:
            soup.decompose()
        # Remove the dateline from the content
        soup = ScrapeHelper.tag_class(article, "span", "date")
        if soup is not None:
            soup.decompose()
        # Remove the heading
        soup = ScrapeHelper.tag_class(article, "h2", "headline_article")
        if soup is not None:
            soup.decompose()
        # Remove picture caption, if any
        soup = ScrapeHelper.div_class(article, "wp-caption")
        if soup is not None:
            soup.decompose()
        return article


class StjornlagaradScraper(ScrapeHelper):
    """ Scraping helper for stjornlagarad.is """

    def __init__(self, root):
        super().__init__(root)

    def skip_url(self, url):
        """ Return True if this URL should not be scraped """
        s = urlparse.urlsplit(url)
        if not s.path:
            return True
        # Only parse stjornlagarad.is/starfid/frumvarp/
        return not s.path.startswith("/starfid/frumvarp/")

    def get_metadata(self, soup):
        metadata = super().get_metadata(soup)
        metadata.heading = "Frumvarp Stjórnlagaráðs"
        metadata.author = "Stjórnlagaráð"
        return metadata

    def _get_content(self, soup_body):
        """ Find the article content (main text) in the soup """
        # Delete div#header
        soup = ScrapeHelper.div_id(soup_body, "header")
        if soup is not None:
            soup.decompose()
        # Delete div#samskiptasattmali
        soup = ScrapeHelper.div_id(soup_body, "samskiptasattmali")
        if soup is not None:
            soup.decompose()
        # Delete div#mjog-stor-footer
        soup = ScrapeHelper.div_id(soup_body, "mjog-stor-footer")
        if soup is not None:
            soup.decompose()
        return soup_body


class StjornarradScraper(ScrapeHelper):
    """ Scraping helper for the webs of Icelandic ministries """

    def __init__(self, root):
        super().__init__(root)

    def skip_url(self, url):
        """ Return True if this URL should not be scraped """
        s = urlparse.urlsplit(url)
        if not s.path or not s.path.startswith("/efst-a-baugi/frettir/stok-frett"):
            return True
        return False

    def get_metadata(self, soup):
        metadata = super().get_metadata(soup)
        body = ScrapeHelper.div_class(soup, "pgmain", "article", "boxbody")
        heading = ScrapeHelper.nested_tag(soup, "main", "article", "header", "h1")
        if heading:
            metadata.heading = heading.string
        else:
            metadata.heading = body.h1.string if body and body.h1 else ""
        date = ScrapeHelper.nested_tag(soup, "main", "article")
        if date is not None and date.has_attr("data-last-modified"):
            date = date["data-last-modified"]
            metadata.timestamp = datetime.strptime(date, "%Y-%m-%d %H:%M:%S")
        else:
            date = ScrapeHelper.tag_prop_val(body, "span", "class", "date")
            if date is not None:
                metadata.timestamp = datetime.strptime(date.string, "%d.%m.%Y")
        # Name of the ministry in question
        metadata.author = self._description or "Stjórnarráð Íslands"
        return metadata

    def _get_content(self, soup_body):
        """ Find the article content (main text) in the soup """
        soup = ScrapeHelper.nested_tag(soup_body, "main", "article", "section")
        if soup is None:
            soup = ScrapeHelper.div_class(soup_body, "pgmain", "article", "boxbody")
            if soup is None:
                return soup_body
            # Older layout: delete extra inline stuff
            # Delete h1
            if soup.h1:
                soup.h1.decompose()
            # Delete date
            date = ScrapeHelper.tag_prop_val(soup, "span", "class", "date")
            if date is not None:
                date.decompose()
            # Delete div.imgbox
            imgbox = ScrapeHelper.div_class(soup, "imgbox")
            if imgbox is not None:
                imgbox.decompose()
            # Delete div.buttons
            buttons = ScrapeHelper.div_class(soup, "buttons")
            if buttons is not None:
                buttons.decompose()
        # Remove embedded infograms
        if soup:
            ScrapeHelper.del_div_class(soup, "infogram-embed")
        return soup


class KvennabladidScraper(ScrapeHelper):
    """ Scraping helper for Kvennabladid.is """

    def __init__(self, root):
        super().__init__(root)
        self._feeds = ["https://kvennabladid.is/feed/"]

    def get_metadata(self, soup):
        """ Analyze the article soup and return metadata """
        metadata = super().get_metadata(soup)
        # Extract the heading from the OpenGraph (Facebook) og:title meta property
        heading = ScrapeHelper.meta_property(soup, "og:title") or ""
        heading = self.unescape(heading)
        # Extract the publication time from the
        dateline = ScrapeHelper.div_class(soup, "blog-info-wrapper", "blog-date")
        dateline = dateline.a.text if dateline and dateline.a else None
        timestamp = None
        if dateline:
            try:
                dateline = dateline.split()  # 18 jún 2016
                day = int(dateline[0])
                month = MONTHS_ABBR.index(dateline[1]) + 1
                year = int(dateline[2])
                # Use current H:M:S as there is no time of day in the document itself
                now = datetime.utcnow()
                timestamp = datetime(
                    year=year,
                    month=month,
                    day=day,
                    hour=now.hour,
                    minute=now.minute,
                    second=now.second,
                )
            except Exception as e:
                logging.warning(
                    "Exception when obtaining date of kvennabladid.is "
                    "article: {0}".format(e)
                )
                timestamp = None
        if timestamp is None:
            timestamp = datetime.utcnow()
        # Extract the author name
        author = ScrapeHelper.div_class(soup, "blog-info-wrapper", "blog-author")
        try:
            author = author.a.text
        except:
            author = "Ritstjórn Kvennablaðsins"
        metadata.heading = heading
        metadata.author = author
        metadata.timestamp = timestamp
        return metadata

    def _get_content(self, soup_body):
        """ Find the article content (main text) in the soup """
        article = ScrapeHelper.div_class(soup_body, "blog-content")
        # Delete all captions
        ScrapeHelper.del_div_class(article, "wp-caption")
        ScrapeHelper.del_tag_prop_val(article, "p", "class", "wp-caption-text")
        return article


class AlthingiScraper(ScrapeHelper):
    """ Scraping helper for althingi.is """

    def __init__(self, root):
        super().__init__(root)

    def get_metadata(self, soup):
        """ Analyze the article soup and return metadata """
        metadata = super().get_metadata(soup)
        # Extract the heading from the OpenGraph (Facebook) og:title meta property
        heading = ScrapeHelper.meta_property(soup, "og:title") or ""
        heading = self.unescape(heading)
        # Default timestamp
        timestamp = datetime.utcnow()
        # Check whether this heading starts with 'NN/YYYY:',
        # and if so, extract the year
        a = heading.split(":", maxsplit=1)
        if len(a) > 1:
            a = a[0].split("/", maxsplit=1)
            if len(a) > 1:
                try:
                    timestamp = datetime(year=int(a[1].strip()), month=1, day=1)
                except ValueError:
                    # Something wrong with the year: back off
                    timestamp = datetime.utcnow()
        metadata.heading = heading
        metadata.author = "Lagasafn Alþingis"
        metadata.timestamp = timestamp
        return metadata

    def _get_content(self, soup_body):
        """ Find the article content (main text) in the soup """
        article = ScrapeHelper.div_class(soup_body, "pgmain", "news", "boxbody")
        return article


class StundinScraper(ScrapeHelper):
    """ Scraping helper for stundin.is """

    def __init__(self, root):
        super().__init__(root)
        # Feed with links to Stundin's open-access articles
        self._feeds = ["https://stundin.is/rss/free/"]

    def get_metadata(self, soup):
        """ Analyze the article soup and return metadata """
        metadata = super().get_metadata(soup)

        # Extract the heading from the OpenGraph (Facebook) og:title meta property
        heading = ScrapeHelper.meta_property(soup, "og:title") or ""
        heading = self.unescape(heading)

        # Extract author name, if available
        name = soup.find("div", {"class": "journalist__name"})
        if not name:
            name = soup.find("h3", {"class": "article__columnist__name"})
        author = name.get_text() if name else None
        if not author:
            author = "Ritstjórn Stundarinnar"

        # Timestamp
        timestamp = datetime.utcnow()
        try:
            time_el = soup.find("time", {"class": "datetime"})
            ts = time_el["datetime"]

            # Example: "2019-01-18 09:55"
            timestamp = datetime(
                year=int(ts[0:4]),
                month=int(ts[5:7]),
                day=int(ts[8:10]),
                hour=int(ts[11:13]),
                minute=int(ts[14:16]),
            )
        except Exception as e:
            logging.warning(
                "Exception obtaining date of stundin.is article: {0}".format(e)
            )

        metadata.heading = heading
        metadata.author = author
        metadata.timestamp = timestamp

        return metadata

    def _get_content(self, soup_body):
        """ Find the article content (main text) in the soup """
        article = ScrapeHelper.div_class(soup_body, "article__body__text")

        # Delete these elements
        ScrapeHelper.del_tag(article, "figure")
        ScrapeHelper.del_tag(article, "aside")
        ScrapeHelper.del_tag(article, "h2")
        ScrapeHelper.del_tag(article, "h3")
        ScrapeHelper.del_div_class(article, "inline-wrap")

        return article


class HringbrautScraper(ScrapeHelper):
    """ Scraping helper for hringbraut.is """

    def __init__(self, root):
        super().__init__(root)
        self._feeds = ["http://www.hringbraut.is/frettir/feed/"]

    def get_metadata(self, soup):
        """ Analyze the article soup and return metadata """
        metadata = super().get_metadata(soup)

        # Extract the heading from the OpenGraph (Facebook) og:title meta property
        heading = ScrapeHelper.meta_property(soup, "og:title") or ""
        heading = self.unescape(heading)
        heading = heading.replace("\u00AD", "")  # Remove soft hyphens

        # Author
        author = "Ritstjórn Hringbrautar"

        # Timestamp
        timestamp = datetime.utcnow()

        info = soup.find("div", {"class": "entryInfo"})
        date_span = info.find("span", {"class": "date"}) if info else None

        if date_span:
            # Example: "17. janúar 2019 - 11:58"
            datestr = date_span.get_text().rstrip()
            try:
                (mday, m, y, _, hm) = datestr.split()
                (hour, mins) = hm.split(":")
                mday = mday.replace(".", "")
                month = MONTHS.index(m) + 1

                timestamp = datetime(
                    year=int(y),
                    month=int(month),
                    day=int(mday),
                    hour=int(hour),
                    minute=int(mins),
                )
            except Exception as e:
                logging.warning(
                    "Exception obtaining date of hringbraut.is article: {0}".format(e)
                )

        metadata.heading = heading
        metadata.author = author
        metadata.timestamp = timestamp

        return metadata

    def _get_content(self, soup_body):
        """ Find the article content (main text) in the soup """
        content = ScrapeHelper.div_class(soup_body, "entryContent")

        # Many hringbraut.is articles end with a "Sjá nánar" paragraph
        # and then a paragraph containing a URL. Remove these.
        paragraphs = list(content.find_all("p", recursive=False))
        if len(paragraphs) > 2:
            last = paragraphs[-1]
            sec_last = paragraphs[-2]
            if last.get_text().startswith("http"):
                last.decompose()
            if sec_last.get_text().startswith("Nánar á"):
                sec_last.decompose()
        return content


class FrettabladidScraper(ScrapeHelper):
    """ Scraping helper for frettabladid.is """

    _ALLOWED_PREFIXES = [
        "/frettir/",
        "/markadurinn/",
        "/sport/",
        "/lifid/",
        "/skodun/",
        "/timamot/",
    ]

    _BANNED_PREFIXES = [
        "/sport/i-beinni-",
        "/sport/sport-fotbolti",
        "/sport/sport-enski-boltinn",
        "/sport/sport-islenski-boltinn",
        "/skodun/skoun-fastir-pennar/",
        "/timamot/timamot-afmli",
        "/timamot/timamot-minningargreinar",
        "/skodun/skoun-fra-degi-til-dags",
        "/markadurinn/markadurinn-innlent/",
        "/lifid/lifi-helgarblai",
        "/lifid/lifi-tiska",
        "/lifid/lifi-folk",
        "/skodun/skoun-bakankar",
        "/markadurinn/markadurinn-innlent",
    ]

    def __init__(self, root):
        super().__init__(root)
        self._feeds = ["https://www.frettabladid.is/rss/"]

    def skip_url(self, url):
        """ Return True if this URL should not be scraped """
        s = urlparse.urlsplit(url)
        if not s.path:
            return True

        # Skip live sport events
        if any(s.path.startswith(p) for p in self._BANNED_PREFIXES):
            return True

        # Skip photos-only articles
        comp = s.path.split("/")
        if comp[-1].startswith("myndasyrpa-"):
            return True

        # Accept any URLs starting with allowed prefixes
        if s.path and any(
            s.path.startswith(prefix) for prefix in self._ALLOWED_PREFIXES
        ):
            return False

        return True  # Skip all other URLs by default

    def get_metadata(self, soup):
        """ Analyze the article soup and return metadata """
        metadata = super().get_metadata(soup)

        # Extract the heading from the OpenGraph (Facebook) og:title meta property
        heading = ScrapeHelper.meta_property(soup, "og:title") or ""
        heading = self.unescape(heading)
        title_suffix = "– Fréttablaðið"
        if heading.endswith(title_suffix):
            heading = heading[: -len(title_suffix)].strip()

        # Author
        name = soup.find("div", {"class": "article-byline"})
        if not name:
            name = soup.find("div", {"class": "bylineblock-heading"})
        if not name:
            name = soup.find("div", {"class": "author-name"})
        author = name.get_text() if name else "Ritstjórn Fréttablaðsins"

        # Timestamp
        timestamp = datetime.utcnow()
        ts = ScrapeHelper.meta_property(soup, "article:published_time")
        if ts:
            timestamp = datetime(
                year=int(ts[0:4]),
                month=int(ts[5:7]),
                day=int(ts[8:10]),
                hour=int(ts[11:13]),
                minute=int(ts[14:16]),
                second=int(ts[17:19]),
            )
        else:
            try:
                # T.d. "Fimmtudagur 28. mars 2019"
                pubdate = soup.find("div", {"class": "article-pubdate"})
                # T.d. "Kl. 13.35"
                pubtime = soup.find("div", {"class": "article-pubtime"})

                if pubdate and pubtime:
                    (_, mday, m, y) = pubdate.get_text().split()
                    mday = mday.replace(".", "")
                    month = MONTHS.index(m) + 1
                    (_, tt) = pubtime.get_text().split()
                    (hh, mm) = tt.split(".")
                    timestamp = datetime(
                        year=int(y),
                        month=int(month),
                        day=int(mday),
                        hour=int(hh),
                        minute=int(mm),
                    )
            except Exception as e:
                logging.warning(
                    "Error finding Frettabladid article date: {0}".format(str(e))
                )
                timestamp = datetime.utcnow()

        metadata.heading = heading
        metadata.author = author
        metadata.timestamp = timestamp

        return metadata

    def _get_content(self, soup_body):
        """ Find the article content (main text) in the soup """
        content = ScrapeHelper.div_class(soup_body, "article-body")
        # Some sports event pages don't have an article__body
        if not content:
            return BeautifulSoup("", _HTML_PARSER)  # Return empty soup.

        # Get rid of stuff we don't want
        ScrapeHelper.del_tag(content, "h3")
        ScrapeHelper.del_tag(content, "figure")
        ScrapeHelper.del_div_class(content, "embed")

        # First char in first paragraph is wrapped in its own span tag
        # for styling purposes, which separates it from the rest of the word.
        # We extract the character and insert it into the first p tag
        firstchar = ""
        span = content.find("span", {"class": "article-dropcap"})
        if span:
            firstchar = span.get_text()
            span.decompose()

        for div in content.find_all("div", {"class": "read-more-block"}):
            div.decompose()

        for div in content.find_all("div", {"class": "sja-einnig"}):
            div.decompose()

        for div in content.find_all("div", {"class": "img-block"}):
            div.decompose()

        for div in content.find_all("div", {"class": "strap"}):
            div.decompose()

        for div in content.find_all("div", {"class": "author-wrapper"}):
            div.decompose()

        for div in content.find_all("div", {"class": "share-buttons-wrapper"}):
            div.decompose()

        for h2 in content.find_all("h2"):
            h2.decompose()

        # Insert it in the first paragraph
        ptag = content.find("p")
        if ptag and firstchar:
            ptag.insert(0, NavigableString(firstchar))

        return content


class HagstofanScraper(ScrapeHelper):
    """ Scraping helper for hagstofa.is """

    def __init__(self, root):
        super().__init__(root)
        self._feeds = ["https://hagstofa.is/rss/allt/"]

    def fetch_url(self, url):
        # Requests defaults to ISO-8859-1 because content-type
        # does not declare encoding. In fact, charset is UTF-8.
        r = requests.get(url)
        r.encoding = r.apparent_encoding
        return r.text

    def get_metadata(self, soup):
        """ Analyze the article soup and return metadata """
        metadata = super().get_metadata(soup)

        # Author
        author = "Hagstofa Íslands"

        # Extract the heading from the OpenGraph (Facebook) og:title meta property
        heading = ScrapeHelper.meta_property(soup, "og:title") or ""
        prefix = "Hagstofan:"
        if heading.startswith(prefix):
            heading = heading[len(prefix) :].strip()

        # Timestamp
        timestamp = datetime.utcnow()

        info = soup.find("div", {"class": "page-header"})
        date_span = info.find("i", {"class": "date"}) if info else None

        if date_span:
            # Example: "22. mars 2019"
            datestr = date_span.get_text().rstrip()
            try:
                (mday, m, y) = datestr.split()
                mday = mday.replace(".", "")
                month = MONTHS.index(m) + 1

                timestamp = datetime(
                    year=int(y),
                    month=int(month),
                    day=int(mday),
                    hour=timestamp.hour,
                    minute=timestamp.minute,
                )
            except Exception as e:
                logging.warning(
                    "Exception obtaining date of hagstofa.is article: {0}".format(e)
                )

        metadata.heading = heading
        metadata.author = author
        metadata.timestamp = timestamp

        return metadata

    def _get_content(self, soup_body):
        """ Find the article content (main text) in the soup """
        content = soup_body.article
        # For some reason, Hagstofan's RSS feed sometimes includes
        # non-news statistics pages with a non-standard format
        if not content:
            return BeautifulSoup("", _HTML_PARSER)  # Return empty soup.

        # Remove tables
        for div in content.find_all("div", {"class": "scrollable"}):
            div.decompose()
        for table in content.find_all("table"):
            table.decompose()

        # Remove buttons
        for a in content.find_all("a", {"class": "btn"}):
            a.decompose()

        # Remove social media stuff
        for ul in content.find_all("ul", {"class": "article-social"}):
            ul.decompose()

        # Remove source lists, and paragraphs containing only a single link
        for p in content.find_all("p"):
            children = list(p.children)
            if len(children) and children[0].name == "sup":
                p.decompose()
            elif len(children) == 1 and children[0].name == "a":
                p.decompose()

        # Remove footer
        footer = content.find("div", {"class": "article-footer"})
        if footer:
            footer.decompose()

        return content


class DVScraper(ScrapeHelper):
    """ Scraping helper for hagstofa.is """

    def __init__(self, root):
        super().__init__(root)
        self._feeds = ["https://www.dv.is/feed/", "https://pressan.dv.is/feed/"]

    def get_metadata(self, soup):
        """ Analyze the article soup and return metadata """
        metadata = super().get_metadata(soup)

        # Author
        author = "Ritstjórn DV"
        try:
            info_div = soup.find("div", {"class": "grein_upplysingar"})
            if info_div:
                author = info_div.find("strong").get_text()
        except Exception as e:
            logging.warning(
                "Exception obtaining author of dv.is article: {0}".format(e)
            )

        # Extract the heading from the OpenGraph og:title meta property
        heading = ScrapeHelper.meta_property(soup, "og:title") or ""
        suffix = "- DV"
        if heading.endswith(suffix):
            heading = heading[: -len(suffix)].strip()

        # Extract the publication time from the article:published_time meta property
        timestamp = datetime.utcnow()
        try:
            ts = ScrapeHelper.meta_property(soup, "article:published_time")
            if ts:
                timestamp = datetime(
                    year=int(ts[0:4]),
                    month=int(ts[5:7]),
                    day=int(ts[8:10]),
                    hour=int(ts[11:13]),
                    minute=int(ts[14:16]),
                    second=int(ts[17:19]),
                )
        except:
            pass

        metadata.heading = heading
        metadata.author = author
        metadata.timestamp = timestamp

        return metadata

    def _get_content(self, soup_body):
        """ Find the article content (main text) in the soup """
        content = ScrapeHelper.div_class(soup_body, "textinn")
        if not content:
            return BeautifulSoup("", _HTML_PARSER)  # Return empty soup.

        for t in content.find_all("style"):
            t.decompose()
        ScrapeHelper.del_div_class(content, "efnisordin")
        ScrapeHelper.del_div_class(content, "ibodi")
        ScrapeHelper.del_tag(content, "iframe")
        if content.figure:
            content.figure.decompose()
        for fc in content.find_all("figcaption"):
            fc.decompose()

        return content


class BBScraper(ScrapeHelper):
    """ Scraping helper for bb.is """

    def __init__(self, root):
        super().__init__(root)
        self._feeds = ["http://www.bb.is/feed/"]

    def get_metadata(self, soup):
        """ Analyze the article soup and return metadata """
        metadata = super().get_metadata(soup)

        # Author
        author = "Ritstjórn Bæjarins besta"
        try:
            meta_auth = ScrapeHelper.meta_property(soup, "author")
            if meta_auth:
                author = meta_auth
        except Exception as e:
            logging.warning(
                "Exception obtaining author of bb.is article: {0}".format(e)
            )

        # Extract the heading from the OpenGraph og:title meta property
        heading = ScrapeHelper.meta_property(soup, "og:title") or ""

        # Extract the publication time from the article:published_time meta property
        timestamp = datetime.utcnow()
        try:
            ts = ScrapeHelper.meta_property(soup, "article:published_time")
            if ts:
                timestamp = datetime(
                    year=int(ts[0:4]),
                    month=int(ts[5:7]),
                    day=int(ts[8:10]),
                    hour=int(ts[11:13]),
                    minute=int(ts[14:16]),
                    second=int(ts[17:19]),
                )
        except Exception:
            pass

        metadata.heading = heading
        metadata.author = author
        metadata.timestamp = timestamp

        return metadata

    def _get_content(self, soup_body):
        """ Find the article content (main text) in the soup """
        content = ScrapeHelper.div_class(soup_body, "td-post-content")

        ScrapeHelper.del_div_class(content, "td-featured-image-rec")
        ScrapeHelper.del_div_class(content, "td-post-featured-image")
        ScrapeHelper.del_div_class(content, "sharedaddy")
        ScrapeHelper.del_div_class(content, "fb-comments")

        ScrapeHelper.del_tag(content, "h3")
        ScrapeHelper.del_tag(content, "fb:comments-count")

        for t in content.find_all(text=re.compile(r"\sathugasemdir$")):
            p = t.find_parent("p")
            if p:
                p.decompose()

        return content


class LemurinnScraper(ScrapeHelper):
    """ Scraping helper for lemurinn.is """

    def __init__(self, root):
        super().__init__(root)
        self._feeds = ["https://lemurinn.is/feed/"]

    def get_metadata(self, soup):
        """ Analyze the article soup and return metadata """
        metadata = super().get_metadata(soup)

        # Extract the heading from the OpenGraph og:title meta property
        heading = ScrapeHelper.meta_property(soup, "og:title") or ""

        # Author
        author = "Ritstjórn Lemúrsins"
        auth_tag = soup.find("a", {"class": "author"})
        if auth_tag:
            author = auth_tag.get_text().strip()
            # Capitalize if necessary
            if not author[0].isupper():
                author = author[0].upper() + author[1:]

        # Extract the publication time from the article:published_time meta property
        timestamp = datetime.utcnow()
        try:
            ts = ScrapeHelper.meta_property(soup, "article:published_time")
            if ts:
                timestamp = datetime(
                    year=int(ts[0:4]),
                    month=int(ts[5:7]),
                    day=int(ts[8:10]),
                    hour=int(ts[11:13]),
                    minute=int(ts[14:16]),
                    second=int(ts[17:19]),
                )
        except Exception:
            pass

        metadata.heading = heading
        metadata.author = author
        metadata.timestamp = timestamp

        return metadata

    def _get_content(self, soup_body):
        """ Find the article content (main text) in the soup """
        content = ScrapeHelper.div_class(soup_body, "post-content")

        return content


class MannlifScraper(ScrapeHelper):
    """ Scraping helper for man.is """

    def __init__(self, root):
        super().__init__(root)
        self._feeds = ["https://www.man.is/feed/"]

    def skip_url(self, url):
        """ Return True if this URL should not be scraped """
        s = urlparse.urlsplit(url)
        p = s.path
        # Only scrape urls with the right path prefix
        if p and p.startswith("/studio-birtingur/"):
            return True  # Don't skip
        return False

    def get_metadata(self, soup):
        """ Analyze the article soup and return metadata """
        metadata = super().get_metadata(soup)

        # Extract the heading from the OpenGraph og:title meta property
        heading = ScrapeHelper.meta_property(soup, "og:title") or ""
        heading = heading.rstrip("|")

        # Author
        author = "Ritstjórn Mannlífs"
        auth_tag = ScrapeHelper.div_class(soup, "tdb-author-name")
        if auth_tag:
            author = auth_tag.get_text()

        timestamp = None
        try:
            # Extract date (no timestamp available) from pubdate tag
            time_tag = soup.find("time", {"class": "entry-date"})
            ts = None
            if time_tag:
                ts = time_tag["datetime"]
            if ts:
                timestamp = datetime(
                    year=int(ts[0:4]),
                    month=int(ts[5:7]),
                    day=int(ts[8:10]),
                    hour=int(ts[11:13]),
                    minute=int(ts[14:16]),
                    second=int(ts[17:19]),
                )
        except Exception as e:
            logging.warning(
                "Exception when obtaining date of man.is article: {0}".format(e)
            )

        if not timestamp:
            timestamp = datetime.utcnow()

        metadata.heading = heading
        metadata.author = author
        metadata.timestamp = timestamp

        return metadata

    def _get_content(self, soup_body):
        """ Find the article content (main text) in the soup """
        content = ScrapeHelper.div_class(soup_body, "tdb_single_content")
        ScrapeHelper.del_div_class(content, "td-a-ad")
        ScrapeHelper.del_tag(content, "figure")
        return content


class VisindavefurScraper(ScrapeHelper):
    """ Scraping helper for visindavefur.hi.is """

    def __init__(self, root):
        super().__init__(root)
        # Can't use due to weird redirects from URLs provided in feed
        # self._feeds = ["https://visindavefur.is/visindavefur.rss"]

    def skip_url(self, url):
        """ Return True if this URL should not be scraped """
        s = urlparse.urlsplit(url)
        p = s.path
        # Only scrape urls with the right path prefix
        if p and p.startswith("/svar.php"):
            return False  # Don't skip
        return True

    def get_metadata(self, soup):
        """ Analyze the article soup and return metadata """
        metadata = super().get_metadata(soup)

        # Extract the heading from the OpenGraph og:title meta property
        heading = ScrapeHelper.meta_property(soup, "og:title") or ""

        # Author
        author = "Vísindavefurinn"
        auth_tag = ScrapeHelper.div_class(soup, "au-name")
        if auth_tag:
            author = auth_tag.get_text()

        timestamp = None
        now = datetime.utcnow()
        try:
            # Extract date (no timestamp available) from pubdate tag
            pubdate_tag = soup.find("div", {"class": "publish-date"})
            dtxt = None
            if pubdate_tag:
                d = list(pubdate_tag.find_all("p"))
                if d:
                    dtxt = d[0].get_text()
            if dtxt:
                (mday, m, y) = dtxt.split(".")
                timestamp = datetime(
                    year=int(y),
                    month=int(m),
                    day=int(mday),
                    hour=now.hour,
                    minute=now.minute,
                    second=now.second,
                )
        except Exception as e:
            logging.warning(
                "Exception when obtaining date of visindavefur.is article: {0}".format(
                    e
                )
            )

        if not timestamp:
            timestamp = now

        metadata.heading = heading
        metadata.author = author
        metadata.timestamp = timestamp

        return metadata

    def _get_content(self, soup_body):
        """ Find the article content (main text) in the soup """
        for p in soup_body.find_all("p", {"class": "br"}):
            p.replace_with(Tag(soup_body, name="br"))
        content = soup_body.find("section", {"class": "article-text"})
        ScrapeHelper.del_div_class(content, "article-img")
        ScrapeHelper.del_tag(content, "center")
        ScrapeHelper.del_tag(content, "img")
        ScrapeHelper.del_tag(content, "table")
        ScrapeHelper.del_tag(content, "ul")
        return content


class SedlabankinnScraper(ScrapeHelper):
    """ Scraping helper for sedlabanki.is """

    def __init__(self, root):
        super().__init__(root)
        self._feeds = [
            "https://www.sedlabanki.is/extensions/news/rss/Frettatilkynningar.rss"
        ]

    def get_metadata(self, soup):
        """ Analyze the article soup and return metadata """
        metadata = super().get_metadata(soup)

        # Extract the heading from the OpenGraph og:title meta property
        heading = ScrapeHelper.meta_property(soup, "og:title") or ""

        # Author
        author = "Seðlabanki Íslands"

        # Extract the publication time from the media tag
        timestamp = datetime.utcnow()
        try:
            media = ScrapeHelper.div_class(soup, "media")
            if media:
                tstr = media["data-last-modified"]
                timestamp = datetime.strptime(tstr, "%Y-%m-%d %H:%M:%S")
        except Exception as e:
            pass

        metadata.heading = heading
        metadata.author = author
        metadata.timestamp = timestamp

        return metadata

    def _get_content(self, soup_body):
        """ Find the article content (main text) in the soup """
        content = ScrapeHelper.div_class(soup_body, "media-body")
        ScrapeHelper.del_tag(content, "h2")
        ScrapeHelper.del_tag(content, "table")
        ScrapeHelper.del_div_class(content, "muted")
        for a in content.find_all("a", {"class": "til-baka"}):
            a.decompose()
        for span in content.find_all("span", {"class": "news-img"}):
            span.decompose()

        return content
