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
    a number of Icelandic websites.

"""

from bs4 import BeautifulSoup, NavigableString
from datetime import datetime
from collections import namedtuple

Metadata = namedtuple('Metadata', ['heading', 'author', 'timestamp', 'authority'])

MODULE_NAME = __name__


class ScrapeHelper:

    """ Generic scraping helper base class """

    def __init__(self, root):
        self._root = root

    def analyze(self, soup):
        """ Analyze the article soup and return metadata """
        return Metadata(heading = "", author = self._root.author,
            timestamp = datetime.now(), authority = self._root.authority)

    @property
    def scr_module(self):
        return MODULE_NAME

    @property
    def scr_class(self):
        return self.__class__.__name__

    @property
    def scr_version(self):
        if hasattr(self.__class__, "_VERSION"):
            return self.__class__._VERSION
        return "1.0"


class KjarninnScraper(ScrapeHelper):

    """ Scraping helper for Kjarninn.is """

    def __init(self, root):
        super().__init__(root)

    def analyze(self, soup):
        """ Analyze the article soup and return metadata """
        return Metadata(heading = "", author = "Ritstjórn Kjarnans",
            timestamp = datetime.now(), authority = 1.0)


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

