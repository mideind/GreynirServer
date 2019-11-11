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
import re
from datetime import datetime

from main import app

# pylint: disable=unused-wildcard-import
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

    def validate_json(r):
        assert r.content_type.startswith(API_CONTENT_TYPE)
        assert r.is_json
        j = resp.get_json()
        assert "valid" in j
        assert j["valid"] == True
        assert "qtype" in j
        return j

    # Frivolous module
    # Note: test=1 ensures that the query bypasses the cache
    resp = client.get("/query.api?test=1&voice=1&q=Hver er sætastur?")
    json = validate_json(resp)
    assert json["qtype"] == "Special"
    assert "voice" in json
    assert "answer" in json
    assert json["answer"] == "Tumi Þorsteinsson."
    assert json["voice"] == "Tumi Þorsteinsson er langsætastur."

    # Person and entity title queries are tested using a dummy database
    # populated with data from CSV files stored in tests/test_files/testdb_*.csv
    # Builtin module: title
    resp = client.get("/query.api?voice=1&q=hver er viðar þorsteinsson")
    json = validate_json(resp)
    assert json["qtype"] == "Person"
    assert "voice" in json
    assert json["voice"].startswith("Viðar Þorsteinsson er ")
    assert json["voice"].endswith(".")

    # Builtin module: title
    resp = client.get("/query.api?voice=1&q=hver er björn þorsteinsson")
    json = validate_json(resp)
    assert json["qtype"] == "Person"
    assert "voice" in json
    assert json["voice"].startswith("Björn Þorsteinsson er ")
    assert json["voice"].endswith(".")

    # Builtin module: person
    resp = client.get("/query.api?voice=1&q=hver er forsætisráðherra")
    json = validate_json(resp)
    assert json["qtype"] == "Title"
    assert "voice" in json
    assert json["voice"].startswith("Forsætisráðherra er ")
    assert json["voice"].endswith(".")

    # Bus module
    resp = client.get("/query.api?test=1&voice=1&q=hvaða stoppistöð er næst mér")
    json = validate_json(resp)
    assert json["qtype"] == "NearestStop"
    assert "answer" in json
    assert json["answer"] == "Fiskislóð"
    assert "voice" in json
    assert json["voice"] == "Næsta stoppistöð er Fiskislóð; þangað eru 310 metrar."

    resp = client.get("/query.api?voice=1&q=hvenær er von á vagni númer 17")
    json = validate_json(resp)
    assert json["qtype"] == "ArrivalTime"
    assert "answer" in json
    assert json["answer"] == "Staðsetning óþekkt"  # No location info available
    assert "voice" in json
    # assert json["voice"] == "Vagn númer 17 kemur klukkan 15 33"

    # Time module
    resp = client.get("/query.api?voice=1&q=hvað er klukkan í Kaupmannahöfn?")
    json = validate_json(resp)
    assert json["qtype"] == "Time"
    assert json["key"] == "Europe/Copenhagen"
    assert "answer" in json
    assert re.search(r"^\d\d:\d\d$", json["answer"])
    assert "voice" in json

    resp = client.get("/query.api?voice=1&q=Hvað er klukkan núna")
    json = validate_json(resp)
    assert json["qtype"] == "Time"
    assert json["key"] == "Atlantic/Reykjavik"
    assert "answer" in json
    assert re.search(r"^\d\d:\d\d$", json["answer"])
    assert "voice" in json
    assert json["voice"].startswith("Klukkan er")

    # Date module
    resp = client.get("/query.api?q=Hver er dagsetningin?")
    json = validate_json(resp)
    assert json["qtype"] == "Date"
    assert "answer" in json
    assert json["answer"].endswith(datetime.now().strftime("%Y"))

    resp = client.get("/query.api?q=Hvað eru margir dagar til jóla?")
    json = validate_json(resp)
    assert json["qtype"] == "Date"
    assert "answer" in json
    assert re.search(r"^\d+", json["answer"])

    # resp = client.get("/query.api?q=Hvað er langt fram að verslunarmannahelgi")
    # json = validate_json(resp)
    # assert json["qtype"] == "Date"
    # assert "answer" in json
    # assert re.search(r"^\d+", json["answer"])

    # resp = client.get("/query.api?q=hvað er langt liðið frá uppstigningardegi")
    # json = validate_json(resp)
    # assert json["qtype"] == "Date"
    # assert "answer" in json
    # assert re.search(r"^\d+", json["answer"])

    resp = client.get("/query.api?q=hvenær eru jólin")
    json = validate_json(resp)
    assert json["qtype"] == "Date"
    assert "answer" in json
    assert re.search(r"24", json["answer"])

    # Arithmetic module
    ARITHM_QUERIES = {
        "hvað er fimm sinnum tólf": "60",
        "hvað er 12 sinnum 12?": "144",
        "hvað er nítján plús 3": "22",
        "hvað er hundrað mínus sautján": "83",
        "hvað er 17 deilt með fjórum": "4,25",
        "hver er kvaðratrótin af 256": "16",
        "hvað er 12 í þriðja veldi": "1728",
        "hvað eru tveir í tíunda veldi": "1024",
        "hvað eru 17 prósent af 20": "3,4",
        "hvað er 7000 deilt með 812": "8,62",
        "hvað er þrisvar sinnum sjö": "21",
    }

    for q, a in ARITHM_QUERIES.items():
        resp = client.get("/query.api?voice=1&q={0}".format(q))
        json = validate_json(resp)
        assert json["qtype"] == "Arithmetic"
        assert "answer" in json
        assert json["answer"] == a

    # Location module
    # No API key on test server!
    # resp = client.get(
    #     "/query.api?q=Hvar er ég?&latitude={0}&longitude={1}".format(
    #         64.15673429618045, -21.9511777069624
    #     )
    # )
    # json = validate_json(resp)
    # assert json["qtype"] == "Location"
    # assert "answer" in json
    # assert json["answer"].startswith("Fiskislóð 31")

    # Weather module
    resp = client.get("/query.api?q=Hversu hlýtt er úti?")
    json = validate_json(resp)
    assert json["qtype"] == "Weather"
    assert "answer" in json
    assert re.search(r"^\-?\d+°$", json["answer"])

    # Geography module
    resp = client.get("/query.api?q=Hver er höfuðborg Spánar?")
    json = validate_json(resp)
    assert json["qtype"] == "Geography"
    assert "answer" in json
    assert json["answer"] == "Madríd"

    resp = client.get("/query.api?q=Í hvaða landi er Jóhannesarborg?")
    json = validate_json(resp)
    assert json["qtype"] == "Geography"
    assert "answer" in json
    assert json["answer"].endswith("Suður-Afríku")

    resp = client.get("/query.api?q=Í hvaða heimsálfu er míkrónesía?")
    json = validate_json(resp)
    assert json["qtype"] == "Geography"
    assert "answer" in json
    assert json["answer"].startswith("Eyjaálfu")

    # Random module
    resp = client.get("/query.api?q=Veldu tölu milli sautján og 30")
    json = validate_json(resp)
    assert json["qtype"] == "Random"
    assert "answer" in json
    assert int(json["answer"]) >= 17 and int(json["answer"]) <= 30

    resp = client.get("/query.api?q=kastaðu teningi")
    json = validate_json(resp)
    assert json["qtype"] == "Random"
    assert "answer" in json
    assert int(json["answer"]) >= 1 and int(json["answer"]) <= 6

    # Telephone module
    resp = client.get("/query.api?q=Hringdu í síma 6 9 9 2 4 2 2")
    json = validate_json(resp)
    assert json["qtype"] == "Telephone"
    assert "answer" in json
    assert "open_url" in json
    assert json["open_url"] == "tel:6992422"
    assert json["q"].endswith("6992422")

    resp = client.get("/query.api?q=hringdu fyrir mig í númerið 69 92 42 2")
    json = validate_json(resp)
    assert json["qtype"] == "Telephone"
    assert "answer" in json
    assert "open_url" in json
    assert json["open_url"] == "tel:6992422"
    assert json["q"].endswith("6992422")

    resp = client.get("/query.api?q=vinsamlegast hringdu í 699-2422")
    json = validate_json(resp)
    assert json["qtype"] == "Telephone"
    assert "answer" in json
    assert "open_url" in json
    assert json["open_url"] == "tel:6992422"
    assert json["q"].endswith("6992422")

    # Wikipedia module
    resp = client.get("/query.api?q=Hvað segir wikipedia um Jón Leifs?")
    json = validate_json(resp)
    assert json["qtype"] == "Wikipedia"
    assert "answer" in json
    assert "Wikipedía" in json["q"]  # Make sure it's being beautified
    assert "tónskáld" in json["answer"]

    # Opinion module
    resp = client.get("/query.api?q=Hvað finnst þér um loftslagsmál?")
    json = validate_json(resp)
    assert json["qtype"] == "Opinion"
    assert "answer" in json
    assert json["answer"].startswith("Ég hef enga sérstaka skoðun")

    # Stats module
    resp = client.get("/query.api?q=hversu marga einstaklinga þekkirðu?")
    json = validate_json(resp)
    assert json["qtype"] == "Stats"
    assert "answer" in json

    resp = client.get("/query.api?q=Hversu mörgum spurningum hefur þú svarað?")
    json = validate_json(resp)
    assert json["qtype"] == "Stats"
    assert "answer" in json


def test_processors():
    """ Try to import all tree/token processors by instantiating Processor object """
    from processor import Processor

    _ = Processor(processor_directory="processors")


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
