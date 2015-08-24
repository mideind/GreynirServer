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
            timestamp = datetime.now(), authority = self._root.authority)

    def get_content(self, soup):
        """ Find the actual article content within an HTML soup and return its parent node """
        if not soup or not soup.html or not soup.html.body:
            # No body in HTML: something is wrong, return None
            return None
        try:
            # Call the helper subclass
            content = self._get_content(soup.html.body)
        except Exception as e:
            content = None
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


class KjarninnScraper(ScrapeHelper):

    """ Scraping helper for Kjarninn.is """

    def __init(self, root):
        super().__init__(root)

    def get_metadata(self, soup):
        """ Analyze the article soup and return metadata """
        # Extract the heading from the OpenGraph (Facebook) og:title meta property
        try:
            heading = soup.html.head.select_one('meta[property="og:title"]')
            if heading:
                heading = str(heading['content'])
        except Exception as e:
            heading = None
        if not heading:
            heading = "" # Unknown heading
        # Extract the publication time from the article:published_time meta property
        try:
            timestamp = soup.html.head.select_one('meta[property="article:published_time"]')
            if timestamp:
                timestamp = str(timestamp['content'])
        except Exception as e:
            timestamp = None
        if not timestamp:
            timestamp = datetime.now()
        # Exctract the author name
        try:
            author = str(soup.html.body.select_one('a[itemprop="author"]').string)
        except Exception as e:
            author = None
        if not author:
            author = "Ritstjórn Kjarnans"
        return Metadata(heading = heading, author = author,
            timestamp = timestamp, authority = self.authority)

    def _get_content(self, soup_body):
        """ Find the article content (main text) in the soup """
        # soup_body has already been sanitized in the ScrapeHelper base class
        return soup_body.select_one("div.entry-content")


class RuvScraper(ScrapeHelper):

    """ Scraping helper for RUV.is """

    def __init(self, root):
        super().__init__(root)

    def skip_url(self, url):
        """ Return True if this URL should not be scraped """
        s = urlparse.urlsplit(url)
        if s.path and s.path.startswith("/frontpage/"):
            # Skip the www.ruv.is/frontpage/... URLs
            return True
        if s.path and s.path.startswith("/sarpurinn/"):
            # Skip the www.ruv.is/sarpurinn/... URLs
            return True
        return False # Scrape all URLs by default
        
    def get_metadata(self, soup):
        """ Analyze the article soup and return metadata """
        # Extract the heading from the OpenGraph (Facebook) og:title meta property
        try:
            heading = soup.html.head.select_one('meta[property="og:title"]')
            if heading:
                heading = str(heading['content'])
        except Exception as e:
            heading = None
        if not heading:
            heading = "" # Unknown heading
        # Extract the publication time from the article:published_time meta property
        try:
            timestamp = soup.html.head.select_one('meta[property="article:published_time"]')
            if timestamp:
                timestamp = str(timestamp['content'])
        except Exception as e:
            timestamp = None
        if not timestamp: 
            timestamp = datetime.now()
        # Exctract the author name
        try:
            author = str(soup.html.body.select_one('div.view-id-author').select_one('div.clip').string)
        except Exception as e:
            author = None
        if not author:
            author = "Fréttastofa RÚV"
        return Metadata(heading = heading, author = author,
            timestamp = timestamp, authority = self.authority)

    def _get_content(self, soup_body):
        """ Find the article content (main text) in the soup """
        rg = soup_body.select_one('div.region.region-two-66-33-first')
        return rg.select_one('div.region-inner') if rg else None


class MblScraper(ScrapeHelper):

    """ Scraping helper for Mbl.is """

    def __init(self, root):
        super().__init__(root)

    def skip_url(self, url):
        """ Return True if this URL should not be scraped """
        s = urlparse.urlsplit(url)
        if s.path and s.path.startswith("/fasteignir/"):
            # Skip the www.mbl.is/fasteignir/... URLs
            return True
        if s.path and s.path.startswith("/english/"):
            # Skip the www.mbl.is/english/... URLs
            return True
        return False # Scrape all URLs by default
        
    def get_metadata(self, soup):
        """ Analyze the article soup and return metadata """
        # Extract the heading from the OpenGraph (Facebook) og:title meta property
        try:
            heading = soup.html.head.select_one('meta[property="og:title"]')
            if heading:
                heading = str(heading['content'])
        except Exception as e:
            heading = None
        if not heading:
            heading = "" # Unknown heading
        # Extract the publication time from the article:published_time meta property
        try:
            # A dateline from mbl.is looks like this: Viðskipti | mbl | 24.8.2015 | 10:48
            dateline = ''.join(soup.html.body.select_one('div.frett-container') \
                .select_one('div.dateline').stripped_strings).split('|')
            # Create a timestamp from dateline[-2] and dateline[-1]
            date = [ int(x) for x in dateline[-2].split('.') ]
            time = [ int(x) for x in dateline[-1].split(':') ]
            timestamp = datetime(year = date[2], month = date[1], day = date[0],
                hour = time[0], minute = time[1])
        except Exception as e:
            timestamp = None
        if not timestamp:
            timestamp = datetime.now()
        # Exctract the author name
        try:
            author = str(soup.html.body.select_one('div.view-id-author').select_one('div.clip').string)
        except Exception as e:
            author = None
        if not author:
            author = "Ritstjórn Mbl.is"
        return Metadata(heading = heading, author = author,
            timestamp = timestamp, authority = self.authority)

    def _get_content(self, soup_body):
        """ Find the article content (main text) in the soup """
        fm = soup.html.body.select_one('div.frett-main')
        return fm.select_one('div.maintext') if fm else None


class VisirScraper(ScrapeHelper):

    """ Scraping helper for Visir.is """

    def __init(self, root):
        super().__init__(root)


class EyjanScraper(ScrapeHelper):

    """ Scraping helper for Eyjan.pressan.is """

    def __init(self, root):
        super().__init__(root)

