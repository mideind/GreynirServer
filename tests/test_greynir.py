"""

    Greynir: Natural language processing for Icelandic

    Copyright (C) 2020 Miðeind ehf.

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


    Tests for code in the Greynir repo.

"""

import pytest
import os
from urllib.parse import urlencode

from main import app
from db import SessionContext
from db.models import Query

# pylint: disable=unused-wildcard-import
from geo import *


@pytest.fixture
def client():
    """ Instantiate Flask's modified Werkzeug client to use in tests """
    app.config["TESTING"] = True
    app.config["DEBUG"] = True
    return app.test_client()


# Routes that don't return 200 OK without certain query/post parameters or external services
SKIP_ROUTES = frozenset(
    (
        "/staticmap",
        "/page",
        "/nnparse.api",
        "/nntranslate.api",
        "/nn/translate.api",
        "/exit.api",
        "/salescloud/nyskraning",
        "/salescloud/breyting",
    )
)

REQ_METHODS = frozenset(["GET", "POST"])


def test_routes(client):
    """ Test all non-argument routes in Flask app by requesting
        them without passing any query or post parameters """
    for rule in app.url_map.iter_rules():
        route = str(rule)
        if rule.arguments or route in SKIP_ROUTES:
            continue
        for m in [t for t in rule.methods if t in REQ_METHODS]:
            # Make request for each method supported by route
            method = getattr(client, m.lower())
            resp = method(route)
            assert resp.status in ("200 OK", "202 ACCEPTED")


API_CONTENT_TYPE = "application/json"
API_EXCLUDE_PREFIX = "/nn"
API_ROUTES = [
    r
    for r in app.url_map.iter_rules()
    if (str(r).endswith(".api") or str(r).endswith(".task"))
    and (not r.arguments)
    and (str(r) not in SKIP_ROUTES)
    and (not str(r).startswith(API_EXCLUDE_PREFIX))
]


def test_api(client):
    """ Call API routes and validate response. """
    # TODO: Route-specific validation of JSON responses
    for r in API_ROUTES:
        # BUG: As-is, this makes pretty little sense
        # since no data is posted to the APIs
        resp = client.post(str(r))
        assert resp.content_type.startswith(API_CONTENT_TYPE)


def test_postag_api(client):
    resp = client.get(r"/postag.api?t=Hér%20sé%20ást%20og%20friður")
    assert resp.status_code == 200
    assert resp.content_type == "application/json; charset=utf-8"
    assert "result" in resp.json
    assert len(resp.json["result"]) == 1
    assert len(resp.json["result"][0]) == 5


def test_ifdtag_api(client):
    resp = client.get(r"/ifdtag.api?t=Hér%20sé%20ást%20og%20friður")
    assert resp.status_code == 200
    assert resp.content_type == "application/json; charset=utf-8"
    assert "valid" in resp.json
    # The IFD tagger doesn't work out of the box, i.e. directly from
    # a git clone. It needs the config/TnT-model.pickle file, which is
    # generated separately. The test will thus not produce a tagged
    # result, without further preparation.
    # assert resp.json["valid"]
    # assert "result" in resp.json
    # assert len(resp.json["result"]) == 1
    # assert len(resp.json["result"][0]) == 5


def test_del_query_history(client):
    """ Test query history deletion API. """

    with SessionContext(commit=False) as session:
        # If database contains the logged query "GREYNIR_TESTING" we know the
        # tests are running on the dummy data in tests/test_files/test_queries.csv.
        cnt = session.query(Query).filter(Query.question == "GREYNIR_TESTING").count()
        if not cnt == 1:
            return

        # Num queries in dummy test data
        TEST_EXPECTED_NUM_QUERIES = 6

        # We expect one query with this client ID
        TEST_CLIENT_ID = "123456789"

        # Number of queries prior to API call
        pre_numq = session.query(Query).count()
        assert pre_numq == TEST_EXPECTED_NUM_QUERIES, "Malformed dummy test data"

        qstr = urlencode(
            {"action": "clear", "client_type": "some_type", "client_id": TEST_CLIENT_ID}
        )

        _ = client.get("/query_history.api?" + qstr)

        post_numq = session.query(Query).count()

        assert post_numq == pre_numq - 1


def test_processors():
    """ Try to import all tree/token processors by instantiating Processor object """
    from processor import Processor

    _ = Processor(processor_directory="processors")


def test_nertokenizer():
    from nertokenizer import recognize_entities


def test_postagger():
    from postagger import NgramTagger


def test_query():
    # TODO: Import all query modules and test whether
    # they include all necessary functions/variables
    from query import Query
    from queries.builtin import HANDLE_TREE
    from queries.special import handle_plain_text

    assert HANDLE_TREE is True
    assert handle_plain_text


def test_scraper():
    from scraper import Scraper


def test_search():
    from search import Search


def test_tnttagger():
    from tnttagger import TnT


def test_geo():
    """ Test geography and location-related functions in geo.py """
    assert icelandic_city_name("London") == "Lundúnir"
    assert icelandic_city_name("Rome") == "Róm"

    assert continent_for_country("IS") == "EU"
    assert continent_for_country("no") == "EU"
    assert continent_for_country("MX") == "NA"

    assert coords_for_country("DE") != None
    assert coords_for_country("it") != None

    assert coords_for_street_name("Austurstræti") != None
    assert coords_for_street_name("Háaleitisbraut") != None

    assert country_name_for_isocode("DE", lang="is") == "Þýskaland"
    assert country_name_for_isocode("DE") == "Þýskaland"

    assert isocode_for_country_name("Danmörk", lang="is") == "DK"
    assert isocode_for_country_name("Danmörk", lang="IS") == "DK"
    assert isocode_for_country_name("Noregur") == "NO"

    addr_info = icelandic_addr_info("Fiskislóð 31")
    assert addr_info and addr_info["stadur_tgf"] == "Reykjavík"

    # Test city info lookup
    city_info = lookup_city_info("Kænugarður")
    assert city_info and len(city_info) == 1 and city_info[0]["country"] == "UA"

    city_info = lookup_city_info("Kaupmannahöfn")
    assert city_info and len(city_info) == 1 and city_info[0]["country"] == "DK"

    city_info = lookup_city_info("Pjongjang")
    assert city_info and len(city_info) == 1 and city_info[0]["country"] == "KP"

    city_info = lookup_city_info("Pyongyang")
    assert city_info and len(city_info) == 1 and city_info[0]["country"] == "KP"

    # Test address string parsing
    assert parse_address_string("   Fiskislóð  31") == {
        "street": "Fiskislóð",
        "number": 31,
        "letter": None,
    }
    assert parse_address_string("Öldugata 19c ") == {
        "street": "Öldugata",
        "number": 19,
        "letter": "c",
    }
    assert parse_address_string("    Dúfnahólar   10   ") == {
        "street": "Dúfnahólar",
        "number": 10,
        "letter": None,
    }

    # Test prepositions for street names
    assert iceprep_for_street("Öldugata") == "á"
    assert iceprep_for_street("Fiskislóð") == "á"
    assert iceprep_for_street("Austurstræti") == "í"
    assert iceprep_for_street("Hamrahlíð") == "í"

    # Test prepositions for placenames
    assert iceprep_for_placename("Dalvík") == "á"
    assert iceprep_for_placename("Akureyri") == "á"
    assert iceprep_for_placename("Ísafjörður") == "á"
    assert iceprep_for_placename("Reykjavík") == "í"
    assert iceprep_for_placename("Hafnarfjörður") == "í"
    assert iceprep_for_placename("London") == "í"
    assert iceprep_for_placename("Dyflinni") == "í"

    # Test prepositions for countries
    assert iceprep_for_country("Ítalía") == "á"
    assert iceprep_for_country("Ísland") == "á"
    assert iceprep_for_country("Þýskaland") == "í"
    assert iceprep_for_country("Japan") == "í"
    assert iceprep_for_country("spánn") == "á"

    # Test prepositions for countries, queried by CC
    assert iceprep_for_cc("IS") == "á"
    assert iceprep_for_cc("US") == "í"
    assert iceprep_for_cc("ES") == "á"
    assert iceprep_for_cc("es") == "á"

    # Test placename capitalization
    assert capitalize_placename("ríó de janeiro") == "Ríó de Janeiro"
    assert capitalize_placename("vík í mýrdal") == "Vík í Mýrdal"
    assert capitalize_placename("Vík í mýrdal") == "Vík í Mýrdal"
    assert capitalize_placename("frankfúrt am main") == "Frankfúrt am Main"
    assert capitalize_placename("mið-afríkulýðveldið") == "Mið-Afríkulýðveldið"
    assert capitalize_placename("Norður-kórea") == "Norður-Kórea"
    assert capitalize_placename("norður-Kórea") == "Norður-Kórea"
    assert capitalize_placename("bosnía og hersegóvína") == "Bosnía og Hersegóvína"
    assert capitalize_placename("Norður-Makedónía") == "Norður-Makedónía"

    # Distance
    assert int(distance((64.141439, -21.943944), (65.688131, -18.102528))) == 249
    assert in_iceland((66.462205, -15.968417))
    assert not in_iceland((62.010846, -6.776709))
    assert not in_iceland((62.031342, -18.539553))

def test_doc():
    """ Test document-related functions in doc.py """
    from doc import PlainTextDocument, DocxDocument

    txt_bytes = "Halló, gaman að kynnast þér.\n\nHvernig gengur?".encode("utf-8")
    doc = PlainTextDocument(txt_bytes)
    assert doc.extract_text() == txt_bytes.decode("utf-8")

    # Change to same directory as this file in order
    # to resolve relative path to files used by tests
    prev_dir = os.getcwd()
    abspath = os.path.abspath(__file__)
    dname = os.path.dirname(abspath)
    os.chdir(dname)

    txt = "Þetta er prufa.\n\nLína 1.\n\nLína 2."
    doc = DocxDocument("test_files/test.docx")
    assert doc.extract_text() == txt

    # Change back to previous directory
    os.chdir(prev_dir)


def test_numbers():
    """ Test number handling functionality in queries """
    from queries import numbers_to_neutral

    assert numbers_to_neutral("Baugatangi 1, Reykjavík") == "Baugatangi eitt, Reykjavík"
    assert numbers_to_neutral("Baugatangi 2, Reykjavík") == "Baugatangi tvö, Reykjavík"
    assert numbers_to_neutral("Baugatangi 3, Reykjavík") == "Baugatangi þrjú, Reykjavík"
    assert (
        numbers_to_neutral("Baugatangi 4, Reykjavík") == "Baugatangi fjögur, Reykjavík"
    )
    assert numbers_to_neutral("Baugatangi 5, Reykjavík") == "Baugatangi 5, Reykjavík"
    assert numbers_to_neutral("Baugatangi 10, Reykjavík") == "Baugatangi 10, Reykjavík"
    assert numbers_to_neutral("Baugatangi 11, Reykjavík") == "Baugatangi 11, Reykjavík"
    assert numbers_to_neutral("Baugatangi 12, Reykjavík") == "Baugatangi 12, Reykjavík"
    assert numbers_to_neutral("Baugatangi 13, Reykjavík") == "Baugatangi 13, Reykjavík"
    assert numbers_to_neutral("Baugatangi 14, Reykjavík") == "Baugatangi 14, Reykjavík"
    assert numbers_to_neutral("Baugatangi 15, Reykjavík") == "Baugatangi 15, Reykjavík"
    assert numbers_to_neutral("Baugatangi 20, Reykjavík") == "Baugatangi 20, Reykjavík"
    assert (
        numbers_to_neutral("Baugatangi 21, Reykjavík")
        == "Baugatangi tuttugu og eitt, Reykjavík"
    )
    assert (
        numbers_to_neutral("Baugatangi 22, Reykjavík")
        == "Baugatangi tuttugu og tvö, Reykjavík"
    )
    assert (
        numbers_to_neutral("Baugatangi 23, Reykjavík")
        == "Baugatangi tuttugu og þrjú, Reykjavík"
    )
    assert (
        numbers_to_neutral("Baugatangi 24, Reykjavík")
        == "Baugatangi tuttugu og fjögur, Reykjavík"
    )
    assert numbers_to_neutral("Baugatangi 25, Reykjavík") == "Baugatangi 25, Reykjavík"
    assert (
        numbers_to_neutral("Baugatangi 100, Reykjavík") == "Baugatangi 100, Reykjavík"
    )
    assert (
        numbers_to_neutral("Baugatangi 101, Reykjavík")
        == "Baugatangi hundrað og eitt, Reykjavík"
    )
    assert (
        numbers_to_neutral("Baugatangi 102, Reykjavík")
        == "Baugatangi hundrað og tvö, Reykjavík"
    )
    assert (
        numbers_to_neutral("Baugatangi 103, Reykjavík")
        == "Baugatangi hundrað og þrjú, Reykjavík"
    )
    assert (
        numbers_to_neutral("Baugatangi 104, Reykjavík")
        == "Baugatangi hundrað og fjögur, Reykjavík"
    )
    assert (
        numbers_to_neutral("Baugatangi 105, Reykjavík") == "Baugatangi 105, Reykjavík"
    )
    assert (
        numbers_to_neutral("Baugatangi 111, Reykjavík") == "Baugatangi 111, Reykjavík"
    )
    assert (
        numbers_to_neutral("Baugatangi 112, Reykjavík") == "Baugatangi 112, Reykjavík"
    )
    assert (
        numbers_to_neutral("Baugatangi 113, Reykjavík") == "Baugatangi 113, Reykjavík"
    )
    assert (
        numbers_to_neutral("Baugatangi 114, Reykjavík") == "Baugatangi 114, Reykjavík"
    )
    assert (
        numbers_to_neutral("Baugatangi 115, Reykjavík") == "Baugatangi 115, Reykjavík"
    )
    assert (
        numbers_to_neutral("Baugatangi 121, Reykjavík")
        == "Baugatangi hundrað tuttugu og eitt, Reykjavík"
    )
    assert (
        numbers_to_neutral("Baugatangi 174, Reykjavík")
        == "Baugatangi hundrað sjötíu og fjögur, Reykjavík"
    )
    assert (
        numbers_to_neutral("Baugatangi 200, Reykjavík") == "Baugatangi 200, Reykjavík"
    )
    assert (
        numbers_to_neutral("Baugatangi 201, Reykjavík")
        == "Baugatangi tvö hundruð og eitt, Reykjavík"
    )
    assert (
        numbers_to_neutral("Baugatangi 202, Reykjavík")
        == "Baugatangi tvö hundruð og tvö, Reykjavík"
    )
    assert (
        numbers_to_neutral("Baugatangi 203, Reykjavík")
        == "Baugatangi tvö hundruð og þrjú, Reykjavík"
    )
    assert (
        numbers_to_neutral("Baugatangi 204, Reykjavík")
        == "Baugatangi tvö hundruð og fjögur, Reykjavík"
    )
    assert (
        numbers_to_neutral("Baugatangi 205, Reykjavík") == "Baugatangi 205, Reykjavík"
    )
    assert (
        numbers_to_neutral("Baugatangi 211, Reykjavík") == "Baugatangi 211, Reykjavík"
    )
    assert (
        numbers_to_neutral("Baugatangi 212, Reykjavík") == "Baugatangi 212, Reykjavík"
    )
    assert (
        numbers_to_neutral("Baugatangi 213, Reykjavík") == "Baugatangi 213, Reykjavík"
    )
    assert (
        numbers_to_neutral("Baugatangi 214, Reykjavík") == "Baugatangi 214, Reykjavík"
    )
    assert (
        numbers_to_neutral("Baugatangi 215, Reykjavík") == "Baugatangi 215, Reykjavík"
    )
    assert (
        numbers_to_neutral("Baugatangi 700, Reykjavík") == "Baugatangi 700, Reykjavík"
    )
    assert (
        numbers_to_neutral("Baugatangi 701, Reykjavík")
        == "Baugatangi sjö hundruð og eitt, Reykjavík"
    )
    assert (
        numbers_to_neutral("Baugatangi 702, Reykjavík")
        == "Baugatangi sjö hundruð og tvö, Reykjavík"
    )
    assert (
        numbers_to_neutral("Baugatangi 703, Reykjavík")
        == "Baugatangi sjö hundruð og þrjú, Reykjavík"
    )
    assert (
        numbers_to_neutral("Baugatangi 704, Reykjavík")
        == "Baugatangi sjö hundruð og fjögur, Reykjavík"
    )
    assert (
        numbers_to_neutral("Baugatangi 705, Reykjavík") == "Baugatangi 705, Reykjavík"
    )
    assert (
        numbers_to_neutral("Baugatangi 711, Reykjavík") == "Baugatangi 711, Reykjavík"
    )
    assert (
        numbers_to_neutral("Baugatangi 712, Reykjavík") == "Baugatangi 712, Reykjavík"
    )
    assert (
        numbers_to_neutral("Baugatangi 713, Reykjavík") == "Baugatangi 713, Reykjavík"
    )
    assert (
        numbers_to_neutral("Baugatangi 714, Reykjavík") == "Baugatangi 714, Reykjavík"
    )
    assert (
        numbers_to_neutral("Baugatangi 715, Reykjavík") == "Baugatangi 715, Reykjavík"
    )
    assert (
        numbers_to_neutral("Baugatangi 1-4, Reykjavík")
        == "Baugatangi eitt-fjögur, Reykjavík"
    )
    assert (
        numbers_to_neutral("Baugatangi 1-17, Reykjavík")
        == "Baugatangi eitt-17, Reykjavík"
    )
