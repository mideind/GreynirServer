"""

    Greynir: Natural language processing for Icelandic

    Copyright (C) 2023 Miðeind ehf.

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
import json
import sys

from flask.testing import FlaskClient

# Shenanigans to enable Pytest to discover modules in the
# main workspace directory (the parent of /tests)
basepath, _ = os.path.split(os.path.realpath(__file__))
mainpath = os.path.join(basepath, "..")
if mainpath not in sys.path:
    sys.path.insert(0, mainpath)

from main import app  # noqa
from utility import read_api_key  # noqa

# pylint: disable=unused-wildcard-import
from geo import *  # noqa


@pytest.fixture
def client() -> FlaskClient:
    """Instantiate Flask's modified Werkzeug client to use in tests"""
    app.config["TESTING"] = True
    app.config["DEBUG"] = True
    return app.test_client()


# This value is dumped to the API key path during CI testing
DUMMY_API_KEY = "123456789"


def in_ci_environment() -> bool:
    """This function determines whether the tests are running in the
    continuous integration environment by checking if the API key
    is a dummy value (set in CI config)."""
    global DUMMY_API_KEY
    try:
        return read_api_key("GreynirServerKey") == DUMMY_API_KEY
    except Exception:
        return False


IN_CI_TESTING_ENV = in_ci_environment()


# Routes that don't return 200 OK without certain
# query/post parameters or external services
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
        "/register_query_data.api",
        "/stats/queries",
    )
)

REQ_METHODS = frozenset(["GET", "POST"])


def test_routes(client: FlaskClient):
    """Test all non-argument routes in Flask app by requesting
    them without passing any query or post parameters"""
    for rule in app.url_map.iter_rules():
        route = str(rule)
        if rule.arguments or route in SKIP_ROUTES:
            continue
        if rule.methods:
            for m in [t for t in rule.methods if t in REQ_METHODS]:
                # Make request for each method supported by route
                method = getattr(client, m.lower())
                resp = method(route)
                assert resp.status in ("200 OK", "202 ACCEPTED")
    resp = client.get("/this_does_not_exist")
    assert resp.status in ("404 NOT FOUND")


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


def test_api(client: FlaskClient):
    """Call API routes and validate response."""
    # TODO: Route-specific validation of JSON responses
    for r in API_ROUTES:
        # BUG: As-is, this makes pretty little sense
        # since no data is posted to the APIs
        resp = client.post(str(r))
        assert resp.content_type.startswith(API_CONTENT_TYPE) == True


def test_postag_api(client: FlaskClient):
    resp = client.get(r"/postag.api?t=Hér%20er%20ást%20og%20friður")
    assert resp.status_code == 200
    assert resp.content_type == "application/json; charset=utf-8"
    assert resp.json
    assert "result" in resp.json
    assert len(resp.json["result"]) == 1
    assert len(resp.json["result"][0]) == 5


def test_ifdtag_api(client: FlaskClient):
    resp = client.get(r"/ifdtag.api?t=Hér%20er%20ást%20og%20friður")
    assert resp.status_code == 200
    assert resp.content_type == "application/json; charset=utf-8"
    assert resp.json
    assert "valid" in resp.json
    # The IFD tagger doesn't work out of the box, i.e. directly from
    # a git clone. It needs the config/TnT-model.pickle file, which is
    # generated separately. The test will thus not produce a tagged
    # result, without further preparation.
    # assert resp.json["valid"]
    # assert "result" in resp.json
    # assert len(resp.json["result"]) == 1
    # assert len(resp.json["result"][0]) == 5


def test_voices_api(client: FlaskClient):
    resp = client.get("/voices.api")
    assert resp.status_code == 200
    assert resp.content_type == "application/json; charset=utf-8"
    assert resp.json
    assert "valid" in resp.json and resp.json["valid"] == True
    assert "default" in resp.json
    assert "supported" in resp.json
    assert "recommended" in resp.json


_KEY_RESTRICTED_ROUTES = frozenset(
    (
        # "/query_history.api",  # Disabled for now until clients are updated w. API key
        "/speech.api",
    )
)


def test_api_key_restriction(client: FlaskClient):
    """Make calls to routes that are API key restricted, make sure they complain if no
    API key is provided as a parameter and accept when correct API key is provided."""

    # Try routes without API key, expect complaint about missing API key
    for path in _KEY_RESTRICTED_ROUTES:
        resp = client.post(path)
        assert resp.status_code == 200
        assert resp.content_type == "application/json; charset=utf-8"
        assert isinstance(resp.json, dict)
        assert "errmsg" in resp.json.keys() and "missing API key" in resp.json["errmsg"]

    # Try routes w. correct API key, expect no complaints about missing API key
    # This only runs in the CI testing environment, which creates the dummy key
    global DUMMY_API_KEY
    # TODO: Fix me
    if False and IN_CI_TESTING_ENV:
        for path in _KEY_RESTRICTED_ROUTES:
            resp = client.post(f"{path}?key={DUMMY_API_KEY}")
            assert resp.status_code == 200
            assert resp.content_type == "application/json; charset=utf-8"
            assert isinstance(resp.json, dict)
            assert "errmsg" not in resp.json.keys()

    # This route requires special handling since it receives JSON via POST
    resp = client.post(
        "/register_query_data.api",
        data=json.dumps(dict()),
        content_type="application/json",
    )
    assert resp.status_code == 200
    assert resp.content_type == "application/json; charset=utf-8"
    assert resp.json
    assert "errmsg" in resp.json and "missing API key" in resp.json["errmsg"]


def test_nertokenizer():
    from nertokenizer import recognize_entities

    assert recognize_entities


def test_postagger():
    from postagger import NgramTagger

    assert NgramTagger


def test_query():
    # TODO: Import all query modules and test whether
    # they include all necessary functions/variables
    from queries import Query
    from queries.builtin import HANDLE_TREE
    from queries.special import handle_plain_text

    assert HANDLE_TREE is True
    assert handle_plain_text
    assert Query  # Silence linter


def test_scraper():
    from scraper import Scraper

    assert Scraper


def test_search():
    from search import Search

    assert Search  # Silence linter


def test_tnttagger():
    from tnttagger import TnT

    assert TnT  # Silence linter


def test_geo():
    """Test geography and location-related functions in geo.py"""
    from geo import (
        icelandic_city_name,
        continent_for_country,
        coords_for_country,
        coords_for_street_name,
        country_name_for_isocode,
        isocode_for_country_name,
        icelandic_addr_info,
        lookup_city_info,
        parse_address_string,
        iceprep_for_street,
        iceprep_for_placename,
        iceprep_for_country,
        iceprep_for_cc,
        capitalize_placename,
        distance,
        in_iceland,
        code_for_us_state,
        coords_for_us_state_code,
        location_info,
    )

    assert icelandic_city_name("London") == "Lundúnir"
    assert icelandic_city_name("Rome") == "Róm"

    assert continent_for_country("IS") == "EU"
    assert continent_for_country("no") == "EU"
    assert continent_for_country("MX") == "NA"

    assert coords_for_country("DE") is not None
    assert coords_for_country("it") is not None

    assert coords_for_street_name("Austurstræti") is not None
    assert coords_for_street_name("Háaleitisbraut") is not None

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
        "letter": "",
    }
    assert parse_address_string("Öldugata 19c ") == {
        "street": "Öldugata",
        "number": 19,
        "letter": "c",
    }
    assert parse_address_string("    Dúfnahólar   10   ") == {
        "street": "Dúfnahólar",
        "number": 10,
        "letter": "",
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

    # US States
    assert code_for_us_state("Flórída") == "FL"
    assert code_for_us_state("Norður-Karólína") == "NC"
    assert code_for_us_state("Kalifornía") == "CA"
    assert coords_for_us_state_code("CA") == (36.778261, -119.417932)

    # Generic location info lookup functions
    assert "country" in location_info("Reykjavík", "placename")
    assert "continent" in location_info("Minsk", "placename")
    assert location_info("Japan", "country")["continent"] == "AS"
    assert location_info("Danmörk", "country")["continent"] == "EU"
    assert location_info("Mexíkó", "country")["continent"] == "NA"
    assert location_info("ísafjörður", "placename")["continent"] == "EU"
    assert location_info("Meðalfellsvatn", "placename")["country"] == "IS"
    assert location_info("Georgía", "country")["country"] != "US"
    assert location_info("Virginía", "placename")["country"] == "US"
    assert location_info("Norður-Dakóta", "country")["country"] == "US"
    assert location_info("Kænugarður", "placename")["continent"] == "EU"
    assert location_info("Fiskislóð 31", "address")["country"] == "IS"


def test_util():
    """Test utility functions."""

    from utility import icelandic_asciify

    assert icelandic_asciify("Sveinbjörn Þórðarson") == "Sveinbjorn THordarson"
    assert icelandic_asciify("sveinbjörn þórðarson") == "sveinbjorn thordarson"
    assert icelandic_asciify("Þetta er prófun") == "THetta er profun"
    assert (
        icelandic_asciify("örn flýgur hægt suður við ána")
        == "orn flygur haegt sudur vid ana"
    )
    assert icelandic_asciify("ÞJÓFUR PRÓFAR ÍSVÉL") == "THJOFUR PROFAR ISVEL"
