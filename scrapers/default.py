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

# The metadata returned by the helper.analyze() function
Metadata = namedtuple('Metadata', ['heading', 'author', 'timestamp', 'authority'])

MODULE_NAME = __name__


class ScrapeHelper:

    """ Generic scraping helper base class """

    def __init__(self, root):
        self._root = root

    def analyze(self, soup):
        """ Analyze the article HTML soup and return metadata """
        return Metadata(heading = "", author = self._root.author,
            timestamp = datetime.now(), authority = self._root.authority)

    def find_content(self, soup):
        """ Find the actual article content within an HTML soup and return its parent node """
        # By default, return the entire body
        return soup.body

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

    def analyze(self, soup):
        """ Analyze the article soup and return metadata """
        # Extract the heading from the OpenGraph (Facebook) og:title meta property
        try:
            heading = soup.html.head.select_one('meta[property="og:title"]')
            if heading:
                heading = heading['content']
        except Exception as e:
            print("Unable to obtain heading for article")
            heading = None
        if not heading:
            heading = "[Óþekkt fyrirsögn]" # Unknown heading
        # Extract the publication time from the article:published_time meta property
        try:
            timestamp = soup.html.head.select_one('meta[property="article:published_time"]')
            if timestamp:
                timestamp = timestamp['content']
        except Exception as e:
            print("Unable to obtain timestamp for article")
            timestamp = None
        if not timestamp:
            timestamp = datetime.now()
        # Exctract the author name
        try:
            author = soup.select_one('a[itemprop="author"]').string
        except Exception as e:
            author = None
        if not author:
            author = "Ritstjórn Kjarnans"
        return Metadata(heading = heading, author = author,
            timestamp = timestamp, authority = self.authority)


class RuvScraper(ScrapeHelper):

    """ Scraping helper for RUV.is """

    def __init(self, root):
        super().__init__(root)


class MblScraper(ScrapeHelper):

    """ Scraping helper for Mbl.is """

    def __init(self, root):
        super().__init__(root)


class VisirScraper(ScrapeHelper):

    """ Scraping helper for Visir.is """

    def __init(self, root):
        super().__init__(root)


class EyjanScraper(ScrapeHelper):

    """ Scraping helper for Eyjan.pressan.is """

    def __init(self, root):
        super().__init__(root)

