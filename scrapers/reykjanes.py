#!/usr/bin/env python
"""
    Reynir: Natural language processing for Icelandic

    Special scraping module for preloaded local data
    used for entiment analysis experiment

    Copyright (c) 2016 Vilhjalmur Thorsteinsson
    All rights reserved
    See the accompanying README.md file for further licensing and copyright information.

"""

import sys
import os

import urllib.parse as urlparse
from datetime import datetime

# Provide access to modules in the parent directory
#sys.path.insert(1, os.path.join(sys.path[0], '..'))

from .default import Metadata, ScrapeHelper

MODULE_NAME = __name__


class ReykjanesScraper(ScrapeHelper):

    """ Generic scraping helper base class """

    def __init__(self, root):
        super().__init__(root)

    def fetch_url(self, url):
        """ Load the requested document from the database """
        return "Document"

    def make_soup(self, doc):
        """ Make a soup object from a document """
        return doc

    def get_metadata(self, soup):
        """ Analyze the article HTML soup and return metadata """
        return Metadata(heading = "Hér er fyrirsögn greinarinnar",
            author = "Höfundur greinarinnar",
            timestamp = datetime.utcnow(), authority = self.authority,
            icon = self.icon)

    def get_content(self, soup):
        """ Find the actual article content within an HTML soup and return its parent node """
        return "Hér er innihald greinarinnar."

    @property
    def scr_module(self):
        """ Return the name of the module for this scraping helper class """
        return MODULE_NAME

