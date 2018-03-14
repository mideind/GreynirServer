#!/usr/bin/env python
"""
    Reynir: Natural language processing for Icelandic

    Image retrieval module

    Copyright (c) 2016 Vilhjalmur Thorsteinsson
    All rights reserved
    See the accompanying README.md file for further licensing and copyright information.

    This module contains a function that retrieves the URL of an image corresponding to
    a (person) name. It uses a Google API on top of the Google Custom Search feature.

    Retrieved image information is cached in the database.

"""


import json
import urllib.request
import urllib.parse
from urllib.error import HTTPError
from datetime import datetime
from collections import namedtuple
from contextlib import closing
from scraperdb import SessionContext, Link


def _server_query(url, q):
    """ Query a server via HTTP GET with a URL-encoded query string obtained from the dict q """
    doc = None
    if len(q):
        url += "?" + urllib.parse.urlencode(q)
    try:
        with closing(urllib.request.urlopen(url)) as response:
            if response:
                # Decode the HTML Content-type header to obtain the
                # document type and the charset (content encoding), if specified
                encoding = 'ISO-8859-1'
                ctype = response.getheader("Content-type", "")
                if ';' in ctype:
                    s = ctype.split(';')
                    ctype = s[0]
                    enc = s[1].strip()
                    s = enc.split('=')
                    if s[0] == "charset" and len(s) == 2:
                        encoding = s[1]
                if ctype == "application/json":
                    doc = response.read() # doc is a bytes object
                    if doc:
                        doc = doc.decode(encoding)
    except HTTPError as ex:
        print("server_query exception: {0}".format(ex))
    return doc


# The Custom Search identifier
_CX = "001858240983628375092:9aogptqla5e"
# The Google API identifier (you must obtain your own key if you want to use this code)
_API_KEY = None
# The content type we're using in the links table
_CTYPE = "image-search-"
# The returned image descriptor tuple
Img = namedtuple('Img', ['src', 'width', 'height', 'link', 'origin'])


def get_image_url(name, size = "large", enclosing_session = None):
    """ Use a Google custom search API to obtain an image corresponding to a (person) name """

    jdoc = None
    ctype = _CTYPE + size

    with SessionContext(commit = True, session = enclosing_session) as session:

        q = session.query(Link.content) \
            .filter(Link.ctype == ctype) \
            .filter(Link.key == name) \
            .one_or_none()
        if q is not None:
            # Found in cache
            jdoc = q.content
            # !!! TODO: make the cache content expire if too old

        if not jdoc:
            # Not found in cache: prepare to ask Google
            global _API_KEY
            if _API_KEY is None:
                try:
                    # Read the Google API key from a server file
                    # You need to obtain your own key if you want to use this code
                    with open("resources/GoogleServerKey.txt") as f:
                        _API_KEY = f.read()
                except FileNotFoundError as ex:
                    _API_KEY = ""

            if not _API_KEY:
                # No API key: can't ask for an image
                return None

            # Assemble the query parameters
            q = dict(
                q = '"' + name + '"', # Try for an exact match
                num = 1,
                start = 1,
                imgSize = size,
                searchType = "image",
                cx = _CX,
                key = _API_KEY
            )
            jdoc = _server_query("https://www.googleapis.com/customsearch/v1", q)
            if jdoc:
                # Store in the cache
                l = Link(
                    ctype = ctype,
                    key = name,
                    content = jdoc,
                    timestamp = datetime.utcnow()
                )
                session.add(l)

    if not jdoc:
        return None
    answer = json.loads(jdoc)

    if answer and "items" in answer and answer["items"] and "link" in answer["items"][0]:
        # Answer looks legit
        img = answer["items"][0]
        image = img["image"]
        return Img(img["link"],
            image["width"], image["height"], image["contextLink"],
            img["displayLink"])

    # No answer that makes sense
    return None


if __name__ == "__main__":

    # Test

    img = get_image_url("Bjarni Benediktsson")
    print("{0}".format(img))

    img = get_image_url("Vilhjálmur Þorsteinsson")
    print("{0}".format(img))

    img = get_image_url("Blængur Klængsson Eyfjörð")
    print("{0}".format(img)) # Should return None

