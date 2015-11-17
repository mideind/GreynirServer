#!/usr/bin/env python
"""
    Reynir: Natural language processing for Icelandic

    Default scraping helpers module

    Author: Vilhjalmur Thorsteinsson

    This software is at a very early development stage.
    While that is the case, it is:
    Copyright (c) 2015 Vilhjalmur Thorsteinsson
    All rights reserved
    See the accompanying README.md file for further licensing and copyright information.

    This module implements a set of default scraping helpers for
    a number of Icelandic websites. The particular scraping module and
    class to be used for each root website is selected in the roots
    table of the scraper database.

"""

from bs4 import BeautifulSoup, NavigableString
from datetime import datetime
from collections import namedtuple
import urllib.parse as urlparse

# The metadata returned by the helper.get_metadata() function
Metadata = namedtuple('Metadata', ['heading', 'author', 'timestamp', 'authority'])

MODULE_NAME = __name__


class ScrapeHelper:

    """ Generic scraping helper base class """

    def __init__(self, root):
        self._root = root

    def skip_url(self, url):
        """ Return True if this URL should not be scraped """
        return False # Scrape all URLs by default

    def get_metadata(self, soup):
        """ Analyze the article HTML soup and return metadata """
        return Metadata(heading = None, author = self._root.author,
            timestamp = datetime.utcnow(), authority = self._root.authority)

    def get_content(self, soup):
        """ Find the actual article content within an HTML soup and return its parent node """
        if not soup or not soup.html or not soup.html.body:
            # No body in HTML: something is wrong, return None
            print("get_content returning None")
            return None
        #try:
            # Call the helper subclass
        if hasattr(self, "_get_content"):
            content = self._get_content(soup.html.body)
        else:
            content = None
        #except Exception as e:
        #    content = None
        #    print("get_content exception in self._get_content: {0}".format(e))
        # By default, return the entire body
        return content or soup.html.body

    @property
    def authority(self):
        return self._root.authority

    @property
    def scr_module(self):
        """ Return the name of the module for this scraping helper class """
        return MODULE_NAME

    @property
    def scr_class(self):
        """ Return the name of this scraping helper class """
        return self.__class__.__name__

    @property
    def scr_version(self):
        """ Return the version of this scraping helper class """
        if hasattr(self.__class__, "_VERSION"):
            return self.__class__._VERSION
        # If no _VERSION attribute in the class, return a default '1.0'
        return "1.0"

    @staticmethod
    def general_filter(tag, name, attr, attr_val):
        """ General filter function to use with BeautifulSoup.find().
            Looks for tag['attr'] == attr_val or attr_val in tag['attr'].
            attr_val can also be iterable, in which case all the given
            attribute values must be present on the tag for the match to
            be made. """
        if tag.name != name or not tag.has_attr(attr):
            return False
        a = tag[attr]
        if tag.name == "div" and attr == "class":
            print("general_filter for div.class: a is {0}\nattr_val is {1}".format(a, attr_val))
        assert a
        # Handle both potentially multi-valued attrs (for instance multiple classes on a div),
        # and multi-valued attr_vals (for instance more than one class that should be present)
        if isinstance(a, str):
            check = lambda x: x == a
        else:
            check = lambda x: x in a
        if isinstance(attr_val, str):
            return check(attr_val)
        return all(check(v) for v in attr_val)

    @staticmethod
    def meta_property_filter(tag, prop_val):
        """ Filter function for meta properties in HTML documents """
        return ScrapeHelper.general_filter(tag, "meta", "property", prop_val)

    @staticmethod
    def div_class_filter(tag, cls):
        """ Filter function for divs in HTML documents, selected by class """
        return ScrapeHelper.general_filter(tag, "div", "class", cls)

    @staticmethod
    def meta_property(soup, property_name):
        try:
            f = lambda tag: ScrapeHelper.meta_property_filter(tag, property_name)
            mp = soup.html.head.find(f)
            if not mp:
                print("meta property {0} not found in soup.html.head".format(property_name))
            return str(mp["content"]) if mp else None
        except Exception as e:
            print("Exception in meta_property('{0}'): {1}".format(property_name, e))
            return None

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


class KjarninnScraper(ScrapeHelper):

    """ Scraping helper for Kjarninn.is """

    def __init(self, root):
        super().__init__(root)

    def skip_url(self, url):
        """ Return True if this URL should not be scraped """
        s = urlparse.urlsplit(url)
        if s.path and s.path.startswith("/tag/"):
            return True
        return False # Scrape all other URLs by default
        
    def get_metadata(self, soup):
        """ Analyze the article soup and return metadata """
        # Extract the heading from the OpenGraph (Facebook) og:title meta property
        heading = ScrapeHelper.meta_property(soup, "og:title") or ""
        if "|" in heading:
            heading = heading[0:heading.index("|")].rstrip()
        # Extract the publication time from the article:published_time meta property
        timestamp = ScrapeHelper.meta_property(soup, "article:published_time") or \
            str(datetime.utcnow())[0:19]
        # Exctract the author name
        f = lambda tag: ScrapeHelper.general_filter(tag, "span", "class", "author")
        tag = soup.html.body.find(f)
        if not tag:
            print("span.class.author tag not found in soup.html.body")
        author = str(tag.string) if tag else "Ritstjórn Kjarnans"
        return Metadata(heading = heading, author = author,
            timestamp = timestamp, authority = self.authority)

    def _get_content(self, soup_body):
        """ Find the article content (main text) in the soup """
        # soup_body has already been sanitized in the ScrapeHelper base class
        if soup_body.article is None:
            print("_get_content: soup_body.article is None")
            return None
        # Delete div.container.title-container tags from the content
        soup = ScrapeHelper.div_class(soup_body.article, ["container", "title-container"])
        if soup is not None:
            soup.decompose()
        # Delete div.container.quote-container tags from the content
        soup = ScrapeHelper.div_class(soup_body.article, ["container", "quote-container"])
        if soup is not None:
            soup.decompose()
        # Delete div.container-fluid tags from the content
        soup = ScrapeHelper.div_class(soup_body.article, "container-fluid")
        if soup is not None:
            soup.decompose()
        # Get the content itself
        content = ScrapeHelper.div_class(soup_body.article, "article-body")
        if content is None:
            # No div.article-body present
            content = soup_body.article
        return content


class RuvScraper(ScrapeHelper):

    """ Scraping helper for RUV.is """

    _SKIP_PREFIXES = [
        "/frontpage/",
        "/frontpage?",
        "/sarpurinn/",
        "/tag/",
        "/frettalisti/"
    ]

    def __init(self, root):
        super().__init__(root)

    def skip_url(self, url):
        """ Return True if this URL should not be scraped """
        s = urlparse.urlsplit(url)
        if s.path:
            for prefix in RuvScraper._SKIP_PREFIXES:
                if s.path.startswith(prefix):
                    return True
        return False # Scrape all other URLs by default

    def get_metadata(self, soup):
        """ Analyze the article soup and return metadata """
        # Extract the heading from the OpenGraph (Facebook) og:title meta property
        heading = ScrapeHelper.meta_property(soup, "og:title") or ""
        # Extract the publication time from the article:published_time meta property
        timestamp = ScrapeHelper.meta_property(soup, "article:published_time") or \
            str(datetime.utcnow())[0:19]
        # Exctract the author name
        # Look for div[class == 'view-id-author'] > div[class == 'clip']
        clip = ScrapeHelper.div_class(soup.html.body, "view-id-author", "clip")
        author = clip.string if clip else "Fréttastofa RÚV"
        return Metadata(heading = heading, author = author,
            timestamp = timestamp, authority = self.authority)

    def _get_content(self, soup_body):
        """ Find the article content (main text) in the soup """
        return ScrapeHelper.div_class(soup_body,
            ("region", "region-two-66-33-first"), "region-inner")


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
        "/atvinna/"
    ]

    def __init(self, root):
        super().__init__(root)

    def skip_url(self, url):
        """ Return True if this URL should not be scraped """
        s = urlparse.urlsplit(url)
        if s.path:
            for prefix in MblScraper._SKIP_PREFIXES:
                if s.path.startswith(prefix):
                    return True
        return False # Scrape all URLs by default

    def get_metadata(self, soup):
        """ Analyze the article soup and return metadata """
        # Extract the heading from the OpenGraph (Facebook) og:title meta property
        heading = ScrapeHelper.meta_property(soup, "og:title") or ""
        # Extract the publication time from the article:published_time meta property
        # A dateline from mbl.is looks like this: Viðskipti | mbl | 24.8.2015 | 10:48
        dateline = ScrapeHelper.div_class(soup.html.body, "frett-container", "dateline")
        dateline = ''.join(dateline.stripped_strings).split('|') if dateline else None
        timestamp = None
        if dateline:
            ix = 0
            while ix < len(dateline) - 2:
                if dateline[ix] == "mbl":
                    # The two slots following "mbl" contain the date and the time
                    # Create a timestamp from dateline[ix+1] and dateline[ix+2]
                    try:
                        date = [ int(x) for x in dateline[ix + 1].split('.') ]
                        time = [ int(x) for x in dateline[ix + 2].split(':') ]
                        timestamp = datetime(year = date[2], month = date[1], day = date[0],
                            hour = time[0], minute = time[1])
                    except Exception as e:
                        print("Exception when obtaining date of mbl.is article: {0}".format(e))
                        timestamp = None
                    break
                ix += 1
        if timestamp is None:
            timestamp = datetime.utcnow()
        # Extract the author name
        rp = ScrapeHelper.div_class(soup.html.body, "frett-main", "reporter-profile")
        f = lambda tag: ScrapeHelper.general_filter(tag, "a", "class", "name")
        rname = rp.find(f) if rp else None
        author = rname.string if rname else "Ritstjórn mbl.is"
        return Metadata(heading = heading, author = author,
            timestamp = timestamp, authority = self.authority)

    def _get_content(self, soup_body):
        """ Find the article content (main text) in the soup """
        return ScrapeHelper.div_class(soup_body, "frett-main", "maintext")


class VisirScraper(ScrapeHelper):

    """ Scraping helper for Visir.is """

    def __init(self, root):
        super().__init__(root)


class EyjanScraper(ScrapeHelper):

    """ Scraping helper for Eyjan.pressan.is """

    def __init(self, root):
        super().__init__(root)

