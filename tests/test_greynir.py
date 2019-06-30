"""

    Reynir: Natural language processing for Icelandic

    Copyright (C) 2019 Miðeind ehf.

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


    Tests for code in the Reynir repo.

"""

import pytest
import os

from main import app

from geo import *

# Routes that don't return 200 OK without certain query/post parameters
SKIP_ROUTES = frozenset(("/staticmap", "/page"))

REQ_METHODS = frozenset(["GET", "POST"])


@pytest.fixture
def client():
    """ Instantiate Flask's modified Werkzeug client to use in tests """
    app.config["TESTING"] = True
    app.config["DEBUG"] = True
    return app.test_client()


def test_routes(client):
    """ Test all non-argument routes in Flask app by requesting
        them without passing any query or post parameters. """
    for rule in app.url_map.iter_rules():
        route = str(rule)
        if rule.arguments or route in SKIP_ROUTES:
            continue

        for m in [t for t in rule.methods if t in REQ_METHODS]:
            # Make request for each method supported by route
            method = getattr(client, m.lower())
            resp = method(route)
            assert resp.status == "200 OK"


API_CONTENT_TYPE = "application/json"
API_ROUTES = [
    r for r in app.url_map.iter_rules() if str(r).endswith(".api") and not r.arguments
]


def test_api(client):
    """ Call API routes and validate response. """
    # TODO: Route-specific validation of JSON responses
    for r in API_ROUTES:
        resp = client.post(str(r))
        assert resp.content_type.startswith(API_CONTENT_TYPE)


def test_query_api(client):
    """ Call API routes and validate response. """
    resp = client.get("/query.api?voice=1&q=Hver er sætastur?")
    assert resp.content_type.startswith(API_CONTENT_TYPE)
    assert resp.is_json
    json = resp.get_json()
    assert "valid" in json
    assert json["valid"] == True
    assert "qtype" in json
    assert json["qtype"] == "Special"
    assert "response" in json
    assert "voice" in json
    assert "answer" in json["response"]
    assert json["response"]["answer"] == "Tumi Þorsteinsson."
    assert json["voice"] == "Tumi Þorsteinsson er langsætastur."

    resp = client.get("/query.api?voice=0&q=Hver er sætastur?")
    assert resp.content_type.startswith(API_CONTENT_TYPE)
    assert resp.is_json
    json = resp.get_json()
    assert "valid" in json
    assert json["valid"] == True
    assert "qtype" in json
    assert json["qtype"] == "Special"
    assert "response" in json
    assert "answer" in json["response"]
    assert json["response"]["answer"] == "Tumi Þorsteinsson."


def test_processors():
    """ Try to import all tree/token processors by instantiating Processor object """
    from processor import Processor

    p = Processor(processor_directory="processors")


def test_nertokenizer():
    from nertokenizer import recognize_entities


def test_postagger():
    from postagger import NgramTagger


def test_query():
    from query import Query
    from queries.builtin import HANDLE_TREE
    assert HANDLE_TREE is True


def test_scraper():
    from scraper import Scraper


def test_search():
    from search import Search


def test_tnttagger():
    from tnttagger import TnT


def test_geo():
    """ Test geography and location-related functions in geo.py """

    assert continent_for_country("IS") == "EU"
    assert coords_for_country("DE") != None
    assert coords_for_street_name("Austurstræti") != None
    assert country_name_for_isocode("DE", lang="is") == "Þýskaland"
    assert isocode_for_country_name("Danmörk", lang="is") == "DK"

    addr_info = icelandic_addr_info("Fiskislóð 31")
    assert addr_info and addr_info["stadur_tgf"] == "Reykjavík"

    city_info = lookup_city_info("Kaupmannahöfn")
    assert city_info and len(city_info) == 1 and city_info[0]["country"] == "DK"

    assert parse_address_string("   Fiskislóð 31") == {
        "street": "Fiskislóð",
        "number": 31,
        "letter": None,
    }
    assert parse_address_string("Öldugata 19c ") == {
        "street": "Öldugata",
        "number": 19,
        "letter": "c",
    }


def test_doc():
    """ Test document-related functions in doc.py """
    from doc import PlainTextDocument, DocxDocument

    txt_bytes = "Halló, gaman að kynnast þér.\n\nHvernig gengur?".encode("utf-8")
    doc = PlainTextDocument(txt_bytes)
    assert doc.extract_text() == txt_bytes.decode("utf-8")

    # Change to same directory as this file in order
    # to resolve relative path to files used by tests
    abspath = os.path.abspath(__file__)
    dname = os.path.dirname(abspath)
    os.chdir(dname)

    txt = "Þetta er prufa.\n\nLína 1.\n\nLína 2."
    doc = DocxDocument("test_files/test.docx")
    assert doc.extract_text() == txt
