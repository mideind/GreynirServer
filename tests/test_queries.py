"""

    Greynir: Natural language processing for Icelandic

    Copyright (C) 2022 Miðeind ehf.

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


    Tests for the query modules in the queries/ directory

"""

from typing import Dict, Optional, Any

import re
import os
import sys
import pytest
from copy import deepcopy
from datetime import datetime, timedelta
from urllib.parse import urlencode

from flask.testing import FlaskClient

# Shenanigans to enable Pytest to discover modules in the
# main workspace directory (the parent of /tests)
basepath, _ = os.path.split(os.path.realpath(__file__))
mainpath = os.path.join(basepath, "..")
if mainpath not in sys.path:
    sys.path.insert(0, mainpath)

from main import app  # noqa

from settings import changedlocale  # noqa
from db import SessionContext  # noqa
from db.models import Query, QueryData, QueryLog  # noqa
from util import read_api_key  # noqa


@pytest.fixture
def client() -> FlaskClient:
    """Instantiate Flask's modified Werkzeug client to use in tests"""
    app.config["TESTING"] = True
    app.config["DEBUG"] = True
    return app.test_client()


# Expected content type of all query responses
API_CONTENT_TYPE = "application/json"


# Client ID used for all query module tests (unless overridden)
DUMMY_CLIENT_ID = "QueryTesting123"


# API endpoints tested in this module
QUERY_API_ENDPOINT = "/query.api"
QUERY_HISTORY_API_ENDPOINT = "/query_history.api"


def qmcall(c: FlaskClient, qdict: Dict[str, Any], qtype: Optional[str] = None) -> Dict:
    """Use passed client object to call query API with
    query string key value pairs provided in dict arg."""

    assert isinstance(c, FlaskClient)

    # test=1 ensures that we bypass the cache and have a (fixed) location
    if "test" not in qdict:
        qdict["test"] = True

    # private=1 makes sure the query isn't logged. This prevents the tests from
    # populating the local database query logging table. Some tests may rely
    # on query history, in which case private=False should be explicitly specified.
    if "private" not in qdict:
        qdict["private"] = True

    if "client_id" not in qdict:
        qdict["client_id"] = DUMMY_CLIENT_ID

    # Create query string
    qstr = urlencode(qdict)

    # Use client to call API endpoint
    r = c.get(f"{QUERY_API_ENDPOINT}?{qstr}")

    # Basic validation of response
    assert r.content_type.startswith(API_CONTENT_TYPE)
    assert r.is_json
    json = r.get_json()
    assert json
    assert "valid" in json
    assert json["valid"]
    assert "error" not in json
    assert "qtype" in json  # All query modules should set a query type
    assert "answer" in json
    if "voice" in qdict and qdict["voice"]:
        assert "voice" in json

    if qtype is not None:
        assert json["qtype"] == qtype

    return json


def _query_data_cleanup() -> None:
    """Delete any queries or query data logged as
    result of query module tests"""

    with SessionContext(commit=True) as session:
        session.execute(
            Query.table().delete().where(Query.client_id == DUMMY_CLIENT_ID)
        )
        session.execute(
            QueryData.table().delete().where(QueryData.client_id == DUMMY_CLIENT_ID)
        )
        # Note: there is no client_id associated w. entries in the QueryLog table
        # so we cannot delete the logged queries there by this criterion.
        # session.execute(
        #     QueryLog.table().delete().where(QueryLog.client_id == DUMMY_CLIENT_ID)
        # )


def has_google_api_key() -> bool:
    return read_api_key("GoogleServerKey") != ""


def has_ja_api_key() -> bool:
    return read_api_key("JaServerKey") != ""


def has_greynir_api_key() -> bool:
    return read_api_key("GreynirServerKey") != ""


def test_nonsense(client: FlaskClient) -> None:
    """Make sure nonsensical queries are not answered"""

    qstr = {"q": "blergh smergh vlurgh"}
    r = client.get("/query.api?" + urlencode(qstr))
    assert r.content_type.startswith(API_CONTENT_TYPE)
    assert r.is_json
    json = r.get_json()
    assert json
    assert "valid" in json
    assert json["valid"] == True
    assert "error" in json
    assert "answer" not in json


def test_arithmetic(client: FlaskClient) -> None:
    """Arithmetic module"""

    ARITHM_QUERIES = {
        "hvað er 17 deilt með fjórum": "4,25",
        "hvað er fimm sinnum tólf": "60",
        "hvað er 12 sinnum 12?": "144",
        "hvað er nítján plús 3": "22",
        "hvað er nítján plús þrír": "22",
        "hvað er nítján + 3": "22",
        "hvað er 19 + 3": "22",
        "hvað er 19 + þrír": "22",
        "hvað er hundrað mínus sautján": "83",
        "hvað er hundrað - sautján": "83",
        "hvað er 100 - sautján": "83",
        "hvað er 100 - 17": "83",
        "hvað er 17 / 4": "4,25",
        "hvað er 18 deilt með þrem": "6",
        "hvað er 18 / þrem": "6",
        "hvað er 18 / 3": "6",
        "hver er kvaðratrótin af 256": "16",
        "hvað er 12 í þriðja veldi": "1728",
        "hvað eru tveir í tíunda veldi": "1024",
        "hvað eru 17 prósent af 20": "3,4",
        "hvað er 7000 deilt með 812": "8,62",
        "hvað er þrisvar sinnum sjö": "21",
        "hvað er fjórðungur af 28": "7",
        "hvað er einn tuttugasti af 192": "9,6",
        "reiknaðu 7 sinnum 7": "49",
        "reiknaðu 7 x 7": "49",
        "reiknaðu sjö x 7": "49",
        "reiknaðu nítján x sjö": "133",
        "geturðu reiknað kvaðratrótina af 9": "3",
        "hvað er 8900 með vaski": "11.036",
        "hvað eru 7500 krónur með virðisaukaskatti": "9.300",
        "hvað er 9300 án vask": "7.500",
        "hvað er pí deilt með pí": "1",
        "hvað er pí / pí": "1",
        "hvað er pí í öðru veldi": "9,87",
        "hvað er tíu deilt með pí": "3,18",
    }

    for q, a in ARITHM_QUERIES.items():
        json = qmcall(client, {"q": q}, "Arithmetic")
        assert json["answer"] == a

    json = qmcall(client, {"q": "hvað er pí", "private": False}, "PI")
    assert "π" in json["answer"]
    assert "3,14159" in json["answer"]

    json = qmcall(client, {"q": "hvað er það sinnum tveir"}, "Arithmetic")
    assert json["answer"].startswith("6,")

    _query_data_cleanup()  # Remove any data logged to DB on account of tests


def test_builtin(client: FlaskClient) -> None:
    """Person and entity title queries are tested using a dummy database
    populated with data from SQL file in tests/files/"""

    # Builtin module: title
    json = qmcall(client, {"q": "hver er viðar þorsteinsson", "voice": True}, "Person")
    assert json["voice"].startswith("Viðar Þorsteinsson er ")
    assert json["voice"].endswith(".")

    # Builtin module: title
    json = qmcall(client, {"q": "hver er björn þorsteinsson", "voice": True}, "Person")
    assert json["voice"].startswith("Björn Þorsteinsson er ")
    assert json["voice"].endswith(".")

    # Builtin module: person
    json = qmcall(client, {"q": "hver er forsætisráðherra", "voice": True}, "Title")
    assert json["voice"].startswith("Forsætisráðherra er ")
    assert json["voice"].endswith(".")

    # Builtin module: person w. title w. uppercase name
    # json = qmcall(client, {"q": "hver er forstjóri sjóvá", "voice": True}, "Title")
    # assert json["voice"].startswith("Forstjóri") and "Jón Jónsson" in json["voice"]

    # Builtin module: entities
    # json = qmcall(client, {"q": "hvað er Nox Medical"}, "Entity")
    # assert "nýsköpunarfyrirtæki" in json["answer"].lower()
    # assert json["key"] == "Nox Medical"


def test_bus(client: FlaskClient) -> None:
    """Bus module"""

    json = qmcall(
        client, {"q": "hvaða stoppistöð er næst mér", "voice": True}, "NearestStop"
    )
    assert json["answer"] == "Fiskislóð"
    assert (
        json["voice"]
        == "Næsta stoppistöð er Fiskislóð; þangað eru þrjú hundruð og tíu metrar."
    )

    json = qmcall(
        client,
        {"q": "hvenær er von á vagni númer 17", "voice": True, "test": False},
        "ArrivalTime",
    )
    assert json["answer"] == "Staðsetning óþekkt"  # No location info available


def test_counting(client: FlaskClient) -> None:
    """Counting module"""

    json = qmcall(client, {"q": "teldu frá einum upp í tíu"}, "Counting")
    assert json["answer"] == "1…10"

    json = qmcall(client, {"q": "teldu hratt niður frá 4", "voice": True}, "Counting")
    assert json["answer"] == "3…0"
    assert "<break time=" in json["voice"]

    json = qmcall(
        client, {"q": "nennirðu að telja niður frá 24", "voice": True}, "Counting"
    )
    assert json["answer"] == "23…0"

    json = qmcall(client, {"q": "teldu upp að 5000", "voice": True}, "Counting")
    assert len(json["voice"]) < 100


def test_currency(client: FlaskClient) -> None:
    """Currency module"""

    json = qmcall(client, {"q": "hvert er gengi dönsku krónunnar?"}, "Currency")
    assert re.search(r"^\d+(,\d+)?$", json["answer"]) is not None

    json = qmcall(client, {"q": "hvað kostar evran"}, "Currency")
    assert re.search(r"^\d+(,\d+)?$", json["answer"]) is not None

    json = qmcall(
        client, {"q": "hvað kostar bandaríkjadalur mikið í krónum"}, "Currency"
    )
    assert re.search(r"^\d+(,\d+)?$", json["answer"]) is not None

    json = qmcall(
        client, {"q": "Hvert er gengi krónunnar gagnvart dollara í dag?"}, "Currency"
    )
    assert re.search(r"^\d+(,\d+)?$", json["answer"]) is not None

    json = qmcall(
        client, {"q": "hvert er gengi krónunnar á móti dollara í dag"}, "Currency"
    )
    assert re.search(r"^\d+(,\d+)?$", json["answer"]) is not None

    json = qmcall(client, {"q": "hvað eru tíu þúsund krónur margir dalir"}, "Currency")
    assert re.search(r"^\d+(,\d+)?$", json["answer"]) is not None

    json = qmcall(client, {"q": "hvað eru 79 dollarar margar evrur?"}, "Currency")
    assert re.search(r"^\d+(,\d+)?$", json["answer"]) is not None


def test_date(client: FlaskClient) -> None:
    """Date module"""

    SPECIAL_DAYS = (
        "jólin",
        "gamlársdagur",
        "nýársdagur",
        "hvítasunna",
        "páskar",
        "þjóðhátíðardagurinn",
        "baráttudagur verkalýðsins",
        "öskudagur",
        "skírdagur",
        "sumardagurinn fyrsti",
        "verslunarmannahelgi",
        "þorláksmessa",
        "föstudagurinn langi",
        "menningarnótt",
        "sjómannadagurinn",
        "dagur íslenskrar tungu",
        "annar í jólum",
        "feðradagur",
        "mæðradagurinn",
    )
    for d in SPECIAL_DAYS:
        qstr = "hvenær er " + d
        json = qmcall(client, {"q": qstr}, "Date")

    json = qmcall(client, {"q": "hver er dagsetningin?", "voice": True}, "Date")
    assert json["answer"].endswith(datetime.now().strftime("%Y"))
    assert "tvö þúsund" in json["voice"]

    json = qmcall(client, {"q": "hvaða dagur er í dag?", "voice": True}, "Date")
    assert json["answer"].endswith(datetime.now().strftime("%Y"))
    assert "tvö þúsund" in json["voice"]

    json = qmcall(client, {"q": "hvaða dagur er á morgun", "voice": True}, "Date")
    assert json["answer"].endswith(datetime.now().strftime("%Y"))
    assert "tvö þúsund" in json["voice"]

    json = qmcall(client, {"q": "hvaða mánaðardagur var í gær", "voice": True}, "Date")
    assert " 20" in json["answer"]
    assert "tvö þúsund" in json["voice"]

    json = qmcall(
        client, {"q": "Hvað eru margir dagar til jóla?", "voice": True}, "Date"
    )
    assert re.search(r"^\d+", json["answer"])
    assert "dag" in json["voice"]

    json = qmcall(client, {"q": "Hvað eru margir dagar í 12. maí?"}, "Date")
    assert "dag" in json["answer"] or "á morgun" in json["answer"]

    # Tests to make sure this kind of query isn't caught by the distance module
    json = qmcall(client, {"q": "Hvað er langt í jólin?"}, "Date")
    json = qmcall(client, {"q": "Hvað er langt í páska?"}, "Date")

    now = datetime.utcnow()

    with changedlocale(category="LC_TIME"):
        # Today
        dstr = now.date().strftime("%-d. %B")
        json = qmcall(client, {"q": "Hvað eru margir dagar í " + dstr})
        assert "í dag" in json["answer"]
        # Tomorrow
        dstr = (now.date() + timedelta(days=1)).strftime("%-d. %B")
        json = qmcall(client, {"q": "Hvað eru margir dagar í " + dstr})
        assert "á morgun" in json["answer"]

    json = qmcall(client, {"q": "hvaða ár er núna?"}, "Date")
    assert str(now.year) in json["answer"]

    json = qmcall(client, {"q": "er hlaupár?"}, "Date")
    assert str(now.year) in json["answer"]

    json = qmcall(client, {"q": "er 2020 hlaupár?"}, "Date")
    assert "var hlaupár" in json["answer"]

    json = qmcall(client, {"q": "var árið 1999 hlaupár?", "voice": True}, "Date")
    assert "ekki hlaupár" in json["answer"]
    assert "nítján hundruð níutíu og níu" in json["voice"]

    json = qmcall(
        client, {"q": "hvað eru margir dagar í desember", "voice": True}, "Date"
    )
    assert json["answer"].startswith("31")
    assert "dag" in json["answer"]
    assert "þrjátíu og einn" in json["voice"]

    json = qmcall(
        client, {"q": "hvað eru margir dagar í febrúar 2024", "voice": True}, "Date"
    )
    assert json["answer"].startswith("29")
    assert "dag" in json["answer"]
    assert "tuttugu og níu" in json["voice"]

    json = qmcall(client, {"q": "Hvað er langt fram að verslunarmannahelgi"}, "Date")
    assert re.search(r"^\d+", json["answer"])

    # json = qmcall(client, {"q": "hvað er langt liðið frá uppstigningardegi"}, "Date")
    # assert re.search(r"^\d+", json["answer"])

    json = qmcall(client, {"q": "hvenær eru jólin", "voice": True}, "Date")
    assert re.search(r"25", json["answer"]) is not None
    assert "tuttugasta og fimmta" in json["voice"]


def test_dictionary(client: FlaskClient) -> None:
    """Dictionary module"""

    json = qmcall(
        client, {"q": "hvernig skilgreinir orðabókin orðið kettlingur"}, "Dictionary"
    )
    assert "kettlingur" in json["answer"].lower()

    json = qmcall(client, {"q": "flettu upp orðinu skíthæll í orðabók"}, "Dictionary")
    assert "skíthæll" in json["answer"].lower()


def test_distance(client: FlaskClient) -> None:
    """Distance module"""

    if not has_google_api_key():
        # NB: No Google API key on test server
        return

    json = qmcall(
        client, {"q": "hvað er ég langt frá perlunni", "voice": True}, "Distance"
    )
    assert json["answer"].startswith("3,5 km")
    assert (
        json["voice"].startswith("Perlan er ")
        and "þrjá komma fimm kílómetra" in json["voice"]
    )
    assert json["source"] == "Google Maps"

    json = qmcall(
        client, {"q": "hvað er langt í melabúðina", "voice": True}, "Distance"
    )
    assert json["answer"].startswith("1,") and "km" in json["answer"]
    assert json["voice"].startswith("Melabúðin er ")

    json = qmcall(
        client,
        {"q": "hvað er ég lengi að ganga í kringluna", "voice": True},
        "Distance",
    )
    assert json["key"] == "Kringlan"
    assert "klukkustund" in json["answer"] and " km" in json["answer"]
    assert json["voice"].startswith("Að ganga")

    json = qmcall(
        client, {"q": "hvað tekur langan tíma að keyra til akureyrar"}, "Distance"
    )
    assert json["key"] == "Akureyri"
    assert "klukkustundir" in json["answer"] and " km" in json["answer"]
    assert json["answer"].endswith("(389 km).")


def test_flights(client: FlaskClient) -> None:
    """Flights module"""

    departure_pattern = r"^Flug \w*? til .*? flýgur frá \w*? \d+\. \w*? klukkan \d\d\:\d\d að staðartíma.$"
    arrival_pattern = r"^Flug \w*? frá .*? lendir [í|á] \w*? \d+\. \w*? klukkan \d\d\:\d\d að staðartíma.$"
    no_matching_flight_pattern = (
        r"Ekkert flug fannst (frá .*? )?(til .*? )?næstu \d+ sólarhringa."
    )

    json = qmcall(
        client,
        {"q": "hvenær fer næsta flug til jfk frá keflavík", "voice": True},
        "Flights",
    )
    assert re.search(departure_pattern, json["answer"]) or "aflýst" in json["answer"]
    json = qmcall(
        client,
        {"q": "hvenær flýgur næsta flug til new york frá keflavík", "voice": True},
        "Flights",
    )
    assert re.search(departure_pattern, json["answer"]) or "aflýst" in json["answer"]
    json = qmcall(
        client,
        {"q": "hvenær flýgur næsta flug af stað frá keflavík", "voice": True},
        "Flights",
    )
    assert re.search(departure_pattern, json["answer"]) or "aflýst" in json["answer"]
    json = qmcall(
        client,
        {"q": "hver er brottfarartími næsta flugs frá keflavík", "voice": True},
        "Flights",
    )
    assert re.search(departure_pattern, json["answer"]) or "aflýst" in json["answer"]
    json = qmcall(
        client,
        {"q": "hver er brottfarartíminn fyrir næsta flug frá keflavík", "voice": True},
        "Flights",
    )
    assert re.search(departure_pattern, json["answer"]) or "aflýst" in json["answer"]

    json = qmcall(
        client, {"q": "hvenær lendir næsta flug í keflavík", "voice": True}, "Flights"
    )
    assert re.search(arrival_pattern, json["answer"]) or "aflýst" in json["answer"]
    json = qmcall(
        client, {"q": "hvenær kemur næsta vél á akureyri", "voice": True}, "Flights"
    )
    assert (
        re.search(arrival_pattern, json["answer"])
        or re.search(no_matching_flight_pattern, json["answer"])
        or "aflýst" in json["answer"]
    )  # In case no flights to Akureyri
    json = qmcall(
        client, {"q": "hvenær mætir næsta vél á vopnafjörð", "voice": True}, "Flights"
    )
    assert (
        re.search(arrival_pattern, json["answer"])
        or re.search(no_matching_flight_pattern, json["answer"])
        or "aflýst" in json["answer"]
    )  # In case no flights to Vopnafjörður
    json = qmcall(
        client,
        {"q": "hvenær mætir næsta vél til vopnafjarðar", "voice": True},
        "Flights",
    )
    assert (
        re.search(arrival_pattern, json["answer"])
        or re.search(no_matching_flight_pattern, json["answer"])
        or "aflýst" in json["answer"]
    )  # In case no flights to Vopnafjörður
    json = qmcall(
        client,
        {
            "q": "hver er lendingartími næstu vélar frá reykjavík til vopnafjarðar",
            "voice": True,
        },
        "Flights",
    )
    assert (
        re.search(arrival_pattern, json["answer"])
        or re.search(no_matching_flight_pattern, json["answer"])
        or "aflýst" in json["answer"]
    )
    json = qmcall(
        client,
        {
            "q": "hver er lendingartíminn fyrir næsta flug til reykjavíkur frá akureyri",
            "voice": True,
        },
        "Flights",
    )
    assert (
        re.search(arrival_pattern, json["answer"])
        or re.search(no_matching_flight_pattern, json["answer"])
        or "aflýst" in json["answer"]
    )

    json = qmcall(
        client,
        {"q": "hvenær fer næsta flug til blabla frá ekkitil", "voice": True},
        "Flights",
    )
    assert (
        re.search(no_matching_flight_pattern, json["answer"])
        or "aflýst" in json["answer"]
    )
    json = qmcall(
        client,
        {"q": "hvenær fer næsta flug frá ekkitil til blablab", "voice": True},
        "Flights",
    )
    assert (
        re.search(no_matching_flight_pattern, json["answer"])
        or "aflýst" in json["answer"]
    )


def test_geography(client: FlaskClient) -> None:
    """Geography module"""

    json = qmcall(client, {"q": "hver er höfuðborg spánar", "voice": True}, "Geography")
    assert json["answer"] == "Madríd"
    assert "Spánar" in json["voice"]  # not 'Spáns', which was a bug

    json = qmcall(client, {"q": "Hver er höfuðborg taiwan"}, "Geography")
    assert json["answer"] == "Taípei"

    json = qmcall(client, {"q": "hver er höfuðborg norður-makedóníu"}, "Geography")
    assert json["answer"] == "Skopje"

    json = qmcall(client, {"q": "hver er höfuðborg norður kóreu"}, "Geography")
    assert json["answer"] == "Pjongjang"

    # TODO: Fix me
    # json = qmcall(
    #     client, {"q": "hver er höfuðborg sameinuðu arabísku furstadæmanna"}, "Geography"
    # )
    # assert json["answer"] == "Abú Dabí"

    json = qmcall(client, {"q": "hvað er höfuðborgin í bretlandi"}, "Geography")
    assert json["answer"] == "Lundúnir"

    json = qmcall(client, {"q": "í hvaða landi er jóhannesarborg"}, "Geography")
    assert json["answer"].endswith("Suður-Afríku")

    json = qmcall(client, {"q": "í hvaða landi er kalifornía"}, "Geography")
    assert "Bandaríkjunum" in json["answer"] and json["key"] == "Kalifornía"

    json = qmcall(client, {"q": "í hvaða heimsálfu er míkrónesía"}, "Geography")
    assert json["answer"].startswith("Eyjaálfu")

    json = qmcall(client, {"q": "hvar í heiminum er máritanía"}, "Geography")
    assert "Afríku" in json["answer"]

    json = qmcall(client, {"q": "hvar er Kaupmannahöfn"}, "Geography")
    assert "Danmörku" in json["answer"]

    json = qmcall(client, {"q": "hvar er borgin tókýó"}, "Geography")
    assert "Japan" in json["answer"]

    json = qmcall(client, {"q": "í hvaða landi er borgin osló"}, "Geography")
    assert "Noregi" in json["answer"]


def test_iot(client: FlaskClient) -> None:
    json = qmcall(
        client, {"q": "breyttu litnum á ljósunum í eldhúsinu í rauðan"}, "IoT"
    )
    assert "ég var að kveikja ljósin! " in json["answer"]

    json = qmcall(client, {"q": "settu á grænan lit í eldhúsinu"}, "IoT")
    assert "ég var að kveikja ljósin! " in json["answer"]

    json = qmcall(client, {"q": "stilltu lit ljóssins í eldhúsinu á grænan"}, "IoT")
    assert "ég var að kveikja ljósin! " in json["answer"]

    json = qmcall(client, {"q": "kveiktu á ljósunum í eldhúsinu"}, "IoT")
    assert "ég var að kveikja ljósin! " in json["answer"]

    json = qmcall(client, {"q": "hækkaðu birtuna í eldhúsinu"}, "IoT")
    assert "ég var að kveikja ljósin! " in json["answer"]

    json = qmcall(client, {"q": "gerðu meiri birtu í eldhúsinu"}, "IoT")
    assert "ég var að kveikja ljósin! " in json["answer"]

    json = qmcall(client, {"q": "gerðu eldhúsið bjartara"}, "IoT")
    assert "ég var að kveikja ljósin! " in json["answer"]

    json = qmcall(client, {"q": "gerðu birtu ljóssins inni í eldhúsi meiri"}, "IoT")
    assert "ég var að kveikja ljósin! " in json["answer"]

    json = qmcall(client, {"q": "slökktu ljósið inni í eldhúsi"}, "IoT")
    assert "ég var að kveikja ljósin! " in json["answer"]

    # json = qmcall(client, {"q": "gerðu meiri birtu inni í eldhúsi"}, "IoT")
    # assert "ég var að kveikja ljósin! " in json["answer"]

    # json = qmcall(client, {"q": "gerðu ljósið inni í eldhúsi minna bjart"}, "IoT")
    # assert "ég var að kveikja ljósin! " in json["answer"]

    # json = qmcall(client, {"q": "gerðu grænt í eldhúsinu"}, "IoT")
    # assert "ég var að kveikja ljósin! " in json["answer"]


def test_ja(client: FlaskClient) -> None:
    """Ja.is module"""

    if not has_ja_api_key():
        return

    json = qmcall(
        client,
        {"q": "hver er síminn hjá Sveinbirni Þórðarsyni?", "voice": True},
        "PhoneNum4Name",
    )
    assert "6992422" in json["answer"]
    assert "sex níu níu tveir fjórir tveir tveir" in json["voice"]

    json = qmcall(
        client,
        {
            "q": "hvað er númerið hjá Vilhjálmi Þorsteinssyni?",
            "voice": True,
        },  # There are many of 'em
        "PhoneNum4Name",
    )
    assert "heimilisfang" in json["voice"]

    json = qmcall(
        client,
        {
            "q": "hver er síminn hjá Vilhjálmi Þorsteinssyni hugbúnaðarhönnuði",
            "voice": True,
        },
        "PhoneNum4Name",
    )
    assert "8201020" in json["answer"]
    assert "átta tveir núll einn núll tveir núll" in json["voice"]


def test_news(client: FlaskClient) -> None:
    """News module"""

    json = qmcall(client, {"q": "Hvað er í fréttum", "voice": True}, "News")
    assert len(json["answer"]) > 80  # This is always going to be a long answer
    assert json["voice"].startswith("Í fréttum rúv er þetta helst")

    json = qmcall(client, {"q": "Hvað er helst í fréttum", "voice": True}, "News")
    assert len(json["answer"]) > 80  # This is always going to be a long answer
    assert json["voice"].startswith("Í fréttum rúv er þetta helst")


def test_opinion(client: FlaskClient) -> None:
    """Opinion module"""

    json = qmcall(
        client, {"q": "hvaða skoðun hefurðu á þriðja orkupakkanum"}, "Opinion"
    )
    assert json["answer"].startswith("Ég hef enga sérstaka skoðun")
    assert json["key"] == "þriðji orkupakkinn"

    json = qmcall(
        client, {"q": "hvað finnst þér eiginlega um Katrínu Jakobsdóttur"}, "Opinion"
    )
    assert json["answer"].startswith("Ég hef enga sérstaka skoðun")
    assert json["key"] == "Katrín Jakobsdóttir"

    json = qmcall(client, {"q": "hver er skoðun þín á blurghsmurgdurg"}, "Opinion")
    assert json["answer"].startswith("Ég hef enga sérstaka skoðun")
    assert json["key"] == "blurghsmurgdurg"


def test_petrol(client: FlaskClient) -> None:
    """Petrol module"""

    json = qmcall(client, {"q": "Hvar er næsta bensínstöð", "voice": True}, "Petrol")
    assert "Ánanaust" in json["answer"]
    assert "source" in json and json["source"].startswith("Gasvaktin")

    json = qmcall(
        client, {"q": "Hvar fæ ég ódýrt bensín í nágrenninu", "voice": True}, "Petrol"
    )
    assert "source" in json and json["source"].startswith("Gasvaktin")

    json = qmcall(client, {"q": "Hvar fæ ég ódýrasta bensínið"}, "Petrol")
    assert "source" in json and json["source"].startswith("Gasvaktin")

    json = qmcall(client, {"q": "hvar er bensínið ódýrast"}, "Petrol")
    assert "source" in json and json["source"].startswith("Gasvaktin")


def test_pic(client: FlaskClient) -> None:
    """Pic module"""

    if not has_google_api_key():
        # NB: No Google API key on test server
        return

    json = qmcall(client, {"q": "Sýndu mér mynd af Katrínu Jakobsdóttur"}, "Picture")
    assert "image" in json

    json = qmcall(client, {"q": "sýndu ljósmynd af hörpunni"}, "Picture")
    assert "image" in json

    json = qmcall(client, {"q": "þetta var ekki rétt mynd"}, "Picture")
    assert "answer" in json and json["answer"]


def test_places(client: FlaskClient) -> None:
    """Places module"""

    if not has_google_api_key():
        # NB: No Google API key on test server
        return

    json = qmcall(client, {"q": "Er lokað á Forréttabarnum?"}, "Places")
    assert (
        "answer" in json
        and "Forréttabarinn" in json["answer"]
        and "opinn" in json["answer"]
    )

    json = qmcall(
        client, {"q": "Hvað er opið lengi í Melabúðinni", "voice": True}, "Places"
    )
    assert (
        "answer" in json
        and "voice" in json
        and "Melabúðin" in json["voice"]
        and "opin" in json["voice"]
    )

    json = qmcall(client, {"q": "Hvenær opnar sundhöllin?", "voice": True}, "Places")
    assert "answer" in json and "voice" in json and " opin " in json["voice"]


def test_play(client: FlaskClient) -> None:
    """Play module"""

    if not has_google_api_key():
        # NB: No Google (YouTube) API key on test server
        return

    json = qmcall(client, {"q": "spilaðu einhverja klassíska tónlist"}, "Play")
    assert "open_url" in json

    json = qmcall(client, {"q": "Spilaðu lag með rolling stones"}, "Play")
    assert "open_url" in json

    json = qmcall(client, {"q": "spilaðu skemmtilega tónlist"}, "Play")
    assert "open_url" in json

    json = qmcall(client, {"q": "spilaðu kvikmynd fyrir mig"}, "Play")
    assert "open_url" in json


def test_rand(client: FlaskClient) -> None:
    """Random module"""

    json = qmcall(client, {"q": "Veldu tölu milli sautján og 30"}, "Random")
    assert int(json["answer"]) >= 17 and int(json["answer"]) <= 30

    json = qmcall(client, {"q": "veldu fyrir mig tölu milli 30 og þrjátíu"}, "Random")
    assert int(json["answer"]) == 30

    json = qmcall(client, {"q": "kastaðu teningi"}, "Random")
    assert int(json["answer"]) >= 1 and int(json["answer"]) <= 6

    json = qmcall(client, {"q": "kastaðu átta hliða teningi"}, "Random")
    assert int(json["answer"]) >= 1 and int(json["answer"]) <= 8

    json = qmcall(client, {"q": "fiskur eða skjaldarmerki"}, "Random")
    a = json["answer"].lower()
    assert "fiskur" in a or "skjaldarmerki" in a

    json = qmcall(client, {"q": "kastaðu peningi"}, "Random")
    a = json["answer"].lower()
    assert "fiskur" in a or "skjaldarmerki" in a


def test_repeat(client: FlaskClient) -> None:
    """Repeat module"""

    json = qmcall(client, {"q": "segðu setninguna simmi er bjálfi"}, "Parrot")
    assert json["answer"] == "Simmi er bjálfi"
    assert json["q"] == "Segðu setninguna „Simmi er bjálfi.“"

    json = qmcall(client, {"q": "segðu eitthvað skemmtilegt"})
    assert json["qtype"] != "Parrot"


def test_schedules(client: FlaskClient) -> None:
    """Schedules module"""

    CURR_RE = (
        r"^(Á {0} er verið að (sýna|spila) dagskrárliðinn .*|"
        r"Ekkert er á dagskrá á {0} í augnablikinu\.)$"
    )
    NEXT_RE = (
        r"^(Næst á dagskrá á {0} verður (sýndur|spilaður) dagskrárliðurinn .*|"
        r"Það er ekkert á dagskrá á {0} eftir núverandi dagskrárlið\.)$"
    )
    ANYTIME_RE = (
        r"^(Á {0}( klukkan \d+:\d+)?( í gær| á morgun)? "
        r"(er verið að (spila|sýna)|(var|verður) (spilaður|sýndur)) dagskrárliðurinn .*|"
        r"Ekkert (er|verður|var) á dagskrá á {0} (í augnablikinu|klukkan \d?\d:\d\d( \d+\. \w+| á morgun| í gær)?)\.)$"
    )
    # RÚV tests
    json = qmcall(client, {"q": "hvað er í sjónvarpinu", "voice": True}, "Schedule")
    assert json["key"] == "RÚV - RÚV"
    assert re.fullmatch(CURR_RE.format("RÚV"), json["answer"])
    json = qmcall(client, {"q": "hvaða þáttur er eiginlega á rúv núna"}, "Schedule")
    assert json["key"] == "RÚV - RÚV"
    assert re.fullmatch(CURR_RE.format("RÚV"), json["answer"])
    json = qmcall(
        client, {"q": "hvaða þátt er verið að sýna í sjónvarpinu"}, "Schedule"
    )
    assert json["key"] == "RÚV - RÚV"
    assert re.fullmatch(CURR_RE.format("RÚV"), json["answer"])

    json = qmcall(client, {"q": "dagskrá rúv klukkan 19:00"}, "Schedule")
    assert json["key"] == "RÚV - RÚV"
    assert re.fullmatch(ANYTIME_RE.format("RÚV"), json["answer"])
    json = qmcall(client, {"q": "hvað er í sjónvarpinu í kvöld?"}, "Schedule")
    assert json["key"] == "RÚV - RÚV"
    assert re.fullmatch(ANYTIME_RE.format("RÚV"), json["answer"])
    json = qmcall(client, {"q": "hvað var í sjónvarpinu í gærkvöldi?"}, "Schedule")
    assert json["key"] == "RÚV - RÚV"
    assert re.fullmatch(ANYTIME_RE.format("RÚV"), json["answer"])
    # json = qmcall(client, {"q": "hver er sjónvarpsdagskráin í kvöld?"}, "Schedule")
    # assert json["key"] == "RÚV - RÚV"

    # Stöð 2 tests
    json = qmcall(client, {"q": "hvað er næsti þáttur á stöð 2"}, "Schedule")
    assert json["key"] == "Stöð 2 - Stöð 2"
    assert re.fullmatch(NEXT_RE.format("Stöð 2"), json["answer"])
    json = qmcall(client, {"q": "Hvaða efni er verið að spila á Stöð 2"}, "Schedule")
    assert json["key"] == "Stöð 2 - Stöð 2"
    assert re.fullmatch(CURR_RE.format("Stöð 2"), json["answer"])

    # Radio tests
    json = qmcall(client, {"q": "hvað er í útvarpinu?"}, "Schedule")
    assert json["key"] == "RÚV - Rás 1"
    assert re.fullmatch(CURR_RE.format("Rás 1"), json["answer"])
    json = qmcall(client, {"q": "hvað er eiginlega í gangi á rás eitt?"}, "Schedule")
    assert json["key"] == "RÚV - Rás 1"
    assert re.fullmatch(CURR_RE.format("Rás 1"), json["answer"])
    json = qmcall(client, {"q": "hvað er á dagskrá á rás tvö?"}, "Schedule")
    assert json["key"] == "RÚV - Rás 2"
    assert re.fullmatch(CURR_RE.format("Rás 2"), json["answer"])

    json = qmcall(
        client, {"q": "hvað var í útvarpinu klukkan sjö í morgun"}, "Schedule"
    )
    assert json["key"] == "RÚV - Rás 1"
    assert re.fullmatch(ANYTIME_RE.format("Rás 1"), json["answer"])
    json = qmcall(client, {"q": "hvað verður á rás 2 klukkan sjö í kvöld"}, "Schedule")
    assert json["key"] == "RÚV - Rás 2"
    assert re.fullmatch(ANYTIME_RE.format("Rás 2"), json["answer"])
    json = qmcall(
        client,
        {"q": "hvað verður á rás 2 klukkan fjögur eftir hádegi á morgun"},
        "Schedule",
    )
    assert json["key"] == "RÚV - Rás 2"
    assert re.fullmatch(ANYTIME_RE.format("Rás 2"), json["answer"])
    assert "16:00" in json["answer"]
    json = qmcall(
        client,
        {"q": "hvað verður á rás 2 klukkan átta á morgun fyrir hádegi"},
        "Schedule",
    )
    assert json["key"] == "RÚV - Rás 2"
    assert re.fullmatch(ANYTIME_RE.format("Rás 2"), json["answer"])
    assert "8:00" in json["answer"]
    json = qmcall(
        client, {"q": "hvað var á rás 2 klukkan sex í gær eftir hádegi"}, "Schedule"
    )
    assert json["key"] == "RÚV - Rás 2"
    assert re.fullmatch(ANYTIME_RE.format("Rás 2"), json["answer"])
    assert "18:00" in json["answer"]
    json = qmcall(
        client, {"q": "hvað var á rás 2 klukkan tvö fyrir hádegi í gær"}, "Schedule"
    )
    assert json["key"] == "RÚV - Rás 2"
    assert re.fullmatch(ANYTIME_RE.format("Rás 2"), json["answer"])
    assert "2:00" in json["answer"]


def test_special(client: FlaskClient) -> None:
    """Special module"""

    json = qmcall(client, {"q": "Hver er sætastur?", "voice": True}, "Special")
    assert json["answer"] == "Tumi Þorsteinsson."
    assert json["voice"] == "Tumi Þorsteinsson er langsætastur."

    json = qmcall(client, {"q": "Hver er tilgangur lífsins?"}, "Special")
    assert json["answer"].startswith("42")


def test_stats(client: FlaskClient) -> None:
    """Stats module"""

    qmcall(client, {"q": "hversu marga einstaklinga þekkirðu?"}, "Stats")
    qmcall(client, {"q": "Hversu mörgum spurningum hefur þú svarað?"}, "Stats")
    qmcall(client, {"q": "hvað ertu aðallega spurð um?"}, "Stats")
    qmcall(client, {"q": "hvaða fólk er mest í fréttum"}, "Stats")


def test_sunpos(client: FlaskClient) -> None:
    """Solar position module"""

    json = qmcall(client, {"q": "hvenær reis sólin í dag?"}, "SunPosition")
    assert re.match(r"^Sólin .* um klukkan \d?\d:\d\d .*\.$", json["answer"])
    json = qmcall(client, {"q": "hvenær sest sólin í kvöld?"}, "SunPosition")
    assert re.match(r"^Sólin .* um klukkan \d?\d:\d\d .*\.$", json["answer"])
    json = qmcall(
        client, {"q": "hvenær verður sólarlag á Norðfirði í kvöld?"}, "SunPosition"
    )
    assert re.match(r"^Sólin .* um klukkan \d?\d:\d\d .*\.$", json["answer"])
    json = qmcall(
        client,
        {"q": "hver er sólarhæð í Reykjavík í dag?", "voice": True},
        "SunPosition",
    )
    assert re.match(
        r"^Sólarhæð um hádegi í dag .* um \d+(,\d+)? gráð(a|ur)\.$",
        json["answer"],
    )
    assert not re.findall(r"\d+", json["voice"])  # No numbers in voice string
    json = qmcall(
        client,
        {"q": "hver er hæð sólar í Reykjavík í dag?", "voice": True},
        "SunPosition",
    )
    assert re.match(
        r"^Sólarhæð um hádegi í dag .* um \d+(,\d+)? gráð(a|ur)\.$",
        json["answer"],
    )
    assert not re.findall(r"\d+", json["voice"])
    json = qmcall(
        client, {"q": "hver er hæð sólarinnar í dag?", "voice": True}, "SunPosition"
    )
    assert re.match(
        r"^Sólarhæð um hádegi í dag .* um \d+(,\d+)? gráð(a|ur)\.$",
        json["answer"],
    )
    assert not re.findall(r"\d+", json["voice"])
    # json = qmcall(client, {"q": "hver er hæð sólar í dag?"}, "SunPosition")
    # assert re.match(
    #     r"^Sólarhæð um hádegi í dag (er|var|verður) um \d+,\d+ gráð(a|ur)\.$",
    #     json["answer"],
    # )
    json = qmcall(client, {"q": "hvenær var miðnætti í nótt?"}, "SunPosition")
    assert re.match(r"^Miðnætti .* um klukkan \d?\d:\d\d .*\.$", json["answer"])
    json = qmcall(client, {"q": "hvenær verður miðnætti í kvöld?"}, "SunPosition")
    assert re.match(r"^Miðnætti .* um klukkan \d?\d:\d\d .*\.$", json["answer"])
    json = qmcall(
        client, {"q": "hvenær verður dögun í Keflavík á morgun?"}, "SunPosition"
    )
    assert re.match(r"^Það verður ekki dögun .*\.$", json["answer"]) or re.match(
        r"^Dögun .* um klukkan \d?\d:\d\d .*\.$", json["answer"]
    )
    json = qmcall(
        client, {"q": "klukkan hvað verður birting á Akureyri á morgun?"}, "SunPosition"
    )
    assert re.match(r"^Það verður ekki birting .*\.$", json["answer"]) or re.match(
        r"^Birting .* um klukkan \d?\d:\d\d .*\.$", json["answer"]
    )
    json = qmcall(client, {"q": "hvenær er hádegi á morgun á Ísafirði?"}, "SunPosition")
    assert re.match(r"^Hádegi .* um klukkan \d?\d:\d\d .*\.$", json["answer"])
    json = qmcall(
        client, {"q": "hvenær varð myrkur í gær á Egilsstöðum?"}, "SunPosition"
    )
    assert re.match(r"^Það varð ekki myrkur.*\.$", json["answer"]) or re.match(
        r"^Myrkur .* um klukkan \d?\d:\d\d .*\.$", json["answer"]
    )
    json = qmcall(
        client, {"q": "klukkan hvað varð dagsetur í gær á Reykjanesi?"}, "SunPosition"
    )
    assert re.match(r"^Það varð ekki dagsetur.*\.$", json["answer"]) or re.match(
        r"^Dagsetur .* um klukkan \d?\d:\d\d .*\.$", json["answer"]
    )


def test_tel(client: FlaskClient) -> None:
    """Telephone module"""

    json = qmcall(client, {"q": "Hringdu í síma 6 9 9 2 4 2 2"}, "Telephone")
    assert "open_url" in json
    assert json["open_url"] == "tel:6992422"
    assert json["q"].endswith("6992422")

    json = qmcall(client, {"q": "hringdu fyrir mig í númerið 69 92 42 2"}, "Telephone")
    assert "open_url" in json
    assert json["open_url"] == "tel:6992422"
    assert json["q"].endswith("6992422")

    json = qmcall(client, {"q": "vinsamlegast hringdu í 921-7422"}, "Telephone")
    assert "open_url" in json
    assert json["open_url"] == "tel:9217422"
    assert json["q"].endswith("9217422")

    json = qmcall(client, {"q": "hringdu í 26"}, "Telephone")
    assert "ekki gilt símanúmer" in json["answer"]


def test_test(client: FlaskClient) -> None:
    """Test module"""

    json = qmcall(client, {"q": "keyrðu kóða"}, "Test")
    assert "command" in json and isinstance(json["command"], str)

    json = qmcall(client, {"q": "opnaðu vefsíðu"}, "Test")
    assert "open_url" in json and json["open_url"].startswith("http")

    json = qmcall(client, {"q": "sýndu mynd"}, "Test")
    assert "image" in json and json["image"].startswith("http")


def test_time(client: FlaskClient) -> None:
    """Time module"""

    json = qmcall(
        client, {"q": "hvað er klukkan í Kaupmannahöfn?", "voice": True}, "Time"
    )
    assert json["key"] == "Europe/Copenhagen"
    assert re.search(r"^\d\d:\d\d$", json["answer"])

    json = qmcall(client, {"q": "Hvað er klukkan núna", "voice": True}, "Time")
    assert json["key"] == "Atlantic/Reykjavik"
    assert re.search(r"^\d\d:\d\d$", json["answer"])
    assert json["voice"].startswith("Klukkan er")

    json = qmcall(client, {"q": "Hvað er klukkan í Japan?", "voice": True}, "Time")
    assert json["key"] == "Asia/Tokyo"
    assert re.search(r"^\d\d:\d\d$", json["answer"])
    assert json["voice"].lower().startswith("klukkan í japan er")


def test_unit(client: FlaskClient) -> None:
    """Unit module"""

    json = qmcall(client, {"q": "Hvað eru margir metrar í mílu?"}, "Unit")
    assert json["answer"] == "1.610 metrar"

    json = qmcall(client, {"q": "hvað eru margar sekúndur í tveimur dögum?"}, "Unit")
    assert json["answer"] == "173.000 sekúndur"

    json = qmcall(client, {"q": "hvað eru tíu steinar mörg kíló?"}, "Unit")
    assert json["answer"] == "63,5 kíló"

    json = qmcall(client, {"q": "hvað eru sjö vökvaúnsur margir lítrar"}, "Unit")
    assert json["answer"] == "0,21 lítrar"

    json = qmcall(client, {"q": "hvað eru 18 merkur mörg kíló"}, "Unit")
    assert json["answer"] == "4,5 kíló"

    json = qmcall(client, {"q": "hvað eru mörg korter í einum degi"}, "Unit")
    assert json["answer"].startswith("96")

    json = qmcall(client, {"q": "hvað eru margar mínútur í einu ári"}, "Unit")
    assert json["answer"].startswith("526.000 mínútur")


def test_userinfo(client: FlaskClient) -> None:
    """User info module"""

    json = qmcall(
        client,
        {"q": "ég heiti Gunna Jónsdóttir"},
        "UserInfo",
    )
    assert json["answer"].startswith("Sæl og blessuð") and "Gunna" in json["answer"]

    json = qmcall(client, {"q": "hvað heiti ég"})
    assert "Gunna Jónsdóttir" in json["answer"]

    json = qmcall(client, {"q": "Nafn mitt er Gunnar"}, "UserInfo")
    assert json["answer"].startswith("Sæll og blessaður") and "Gunnar" in json["answer"]

    json = qmcall(client, {"q": "veistu hvað ég heiti"}, "UserInfo")
    assert json["answer"].startswith("Þú heitir Gunnar")

    json = qmcall(client, {"q": "ég heiti Boutros Boutros-Ghali"}, "UserInfo")
    assert json["answer"].startswith("Gaman að kynnast") and "Boutros" in json["answer"]

    json = qmcall(
        client,
        {
            "q": "hvaða útgáfu er ég að keyra",
            "client_type": "ios",
            "client_version": "1.1.0",
            "voice": True,
        },
    )
    assert "iOS" in json["answer"] and "1.1.0" in json["answer"]
    assert "komma" in json["voice"]

    json = qmcall(client, {"q": "á hvaða tæki ertu að keyra?", "client_type": "ios"})
    assert "iOS" in json["answer"]

    # json = qmcall(
    #     c,
    #     {"q": "ég á heima á öldugötu 4 í reykjavík"},
    #     "UserInfo",
    # )
    # assert json["answer"].startswith("Gaman að kynnast") and "Boutros" in json["answer"]

    # json = qmcall(client, {"q": "hvar á ég heima"}, "UserInfo")
    # assert json["answer"].startswith("Gaman að kynnast") and "Boutros" in json["answer"]

    # json = qmcall(client, {"q": "ég á heima á Fiskislóð 31"}, "UserInfo")
    # assert json["answer"].startswith("Gaman að kynnast") and "Boutros" in json["answer"]

    # json = qmcall(client, {"q": "hvar bý ég eiginlega"}, "UserInfo")
    # assert json["answer"].startswith("Gaman að kynnast") and "Boutros" in json["answer"]


def test_userloc(client: FlaskClient) -> None:
    """User location module"""

    if not has_google_api_key():
        # NB: No Google API key on test server
        return

    json = qmcall(client, {"q": "Hvar er ég"}, "UserLocation")
    assert "Fiskislóð 31" in json["answer"]
    json = qmcall(
        client, {"q": "Hvar í heiminum er ég eiginlega staddur?"}, "UserLocation"
    )
    assert "Fiskislóð 31" in json["answer"]

    json = qmcall(client, {"q": "í hvaða landi er ég?"}, "UserLocation")
    assert "Íslandi" in json["answer"]

    _AMSTERDAM = (52.36745478540058, 4.875011776978037)
    json = qmcall(
        client,
        {
            "q": "hvaða landi er ég staddur í?",
            "latitude": _AMSTERDAM[0],
            "longitude": _AMSTERDAM[1],
            "test": False,
        },
        "UserLocation",
    )
    assert "Hollandi" in json["answer"]


def test_weather(client: FlaskClient) -> None:
    """Weather module"""

    json = qmcall(client, {"q": "hvernig er veðrið í Reykjavík?"}, "Weather")
    assert re.search(r"^\-?\d+ °C", json["answer"]) is not None

    json = qmcall(client, {"q": "Hversu hlýtt er úti?"}, "Weather")
    assert re.search(r"^\-?\d+ °C", json["answer"]) is not None

    json = qmcall(client, {"q": "hversu kalt er í dag?"}, "Weather")
    assert re.search(r"^\-?\d+ °C", json["answer"]) is not None

    json = qmcall(client, {"q": "hver er veðurspáin?"}, "Weather")

    json = qmcall(client, {"q": "hver er veðurspáin fyrir morgundaginn"}, "Weather")
    assert len(json["answer"]) > 20 and "." in json["answer"]


def test_whatis(client: FlaskClient) -> None:
    # TODO: Implement me
    pass


def test_wiki(client: FlaskClient) -> None:
    """Wikipedia module"""

    # "Hvað segir Wikipedía um X" queries
    json = qmcall(client, {"q": "Hvað segir wikipedia um Jón Leifs?"}, "Wikipedia")
    assert "Wikipedía" in json["q"]  # Make sure it's being beautified
    assert "tónskáld" in json["answer"]
    assert "source" in json and "wiki" in json["source"].lower()

    json = qmcall(
        client, {"q": "hvað segir vikipedija um jóhann sigurjónsson"}, "Wikipedia"
    )
    assert "Jóhann" in json["answer"]

    json = qmcall(
        client,
        {
            "q": "katrín Jakobsdóttir í vikipediju",
            "private": False,
        },
        "Wikipedia",
    )
    assert "Katrín Jakobsdóttir" in json["answer"]

    json = qmcall(
        client,
        {"q": "hvað segir wikipedía um hana"},
        "Wikipedia",
    )
    assert "Katrín Jakobsdóttir" in json["answer"]

    # "Hvað er X" queries
    json = qmcall(client, {"q": "hvað er mjólk"}, "Wikipedia")
    assert "Mjólk" in json["answer"] and "spendýr" in json["answer"]

    json = qmcall(client, {"q": "hvað er fjall"}, "Wikipedia")
    assert "Fjall" in json["answer"]

    _query_data_cleanup()  # Remove any data logged to DB on account of tests


def test_words(client: FlaskClient) -> None:
    """Words module"""

    json = qmcall(
        client, {"q": "hvernig stafar maður orðið hestur", "voice": True}, "Spelling"
    )
    assert json["answer"] == "H E S T U R"
    assert json["voice"].startswith("Orðið „hestur“ ")

    json = qmcall(
        client, {"q": "hvernig beygist orðið maður", "voice": True}, "Declension"
    )
    assert json["answer"].lower() == "maður, mann, manni, manns"
    assert json["voice"].startswith("Orðið „maður“")
    json = qmcall(
        client, {"q": "hvernig beygir maður nafnorðið splorglobb?", "voice": True}
    )
    assert json["voice"].startswith("Nafnorðið „splorglobb“ fannst ekki")


def test_yulelads(client: FlaskClient) -> None:
    """Yule lads module"""

    qmcall(
        client,
        {"q": "hvenær kemur fyrsti jólasveinninn til byggða", "voice": True},
        "YuleLads",
    )


# NB: Do not move this function. Pytest runs tests in the order they
# appear in the source file, and this test function should be the
# last to run, since it has the fortuitous side effect of deleting
# any logged queries/query data saved to the database due to tests.
def test_query_history_api(client: FlaskClient) -> None:
    """Tests for the query history deletion API endpoint."""

    if not has_greynir_api_key():
        # We don't run these tests unless a Greynir API key is present
        return

    def _verify_basic(r: Any) -> Dict:
        """Make sure the server response is minimally sane."""
        assert r.content_type.startswith(API_CONTENT_TYPE)
        assert r.is_json
        json = r.get_json()
        assert json
        assert "valid" in json
        return json

    def _str2cls(name: str) -> Any:
        """Get class from name string."""
        return getattr(sys.modules[__name__], name)

    def _num_logged_query_info(client_id: str, model_name: str) -> int:
        """Make sure no db model entries associated with
        the provided client_id exists in database."""
        # assert model_name in ["Query", "QueryData"]
        with SessionContext(read_only=True) as session:
            classn = _str2cls(model_name)
            q = session.query(classn).filter(classn.client_id == client_id)
            ql = list(q)
            return len(ql)
        return 0

    # Create basic query param dict
    qdict: Dict[str, Any] = dict(
        api_key=read_api_key("GreynirServerKey"),
        action="clear",
        client_id=DUMMY_CLIENT_ID,
    )

    # Make a query module call and make sure it is logged
    qmcall(client, {"q": "hvað er klukkan", "private": False})
    assert _num_logged_query_info(DUMMY_CLIENT_ID, "Query") > 0
    # And try to clear query history via valid call to API endpoint
    qd = deepcopy(qdict)
    qd["action"] = "clear"
    r = client.get(f"{QUERY_HISTORY_API_ENDPOINT}?{urlencode(qd)}")
    json = _verify_basic(r)
    assert json["valid"] == True
    assert _num_logged_query_info(DUMMY_CLIENT_ID, "Query") == 0

    # Make a query module call that is logged AND saves query data
    qmcall(client, {"q": "Ég heiti Jón Jónsson", "private": False})
    assert _num_logged_query_info(DUMMY_CLIENT_ID, "Query") > 0
    assert _num_logged_query_info(DUMMY_CLIENT_ID, "QueryData") > 0
    # And try to clear query history AND query data via call to API endpoint
    qd = deepcopy(qdict)
    qd["action"] = "clear_all"
    r = client.get(f"{QUERY_HISTORY_API_ENDPOINT}?{urlencode(qd)}")
    json = _verify_basic(r)
    assert json["valid"] == True
    assert _num_logged_query_info(DUMMY_CLIENT_ID, "Query") == 0
    assert _num_logged_query_info(DUMMY_CLIENT_ID, "QueryData") == 0

    # Send invalid requests with missing keys
    # We expect "valid" key to be false in dict returned
    for qkey in ["api_key", "action", "client_id"]:
        qd = deepcopy(qdict)
        qd.pop(qkey, None)  # Remove req. key from query param dict
        r = client.get(f"{QUERY_HISTORY_API_ENDPOINT}?{urlencode(qd)}")
        json = _verify_basic(r)
        assert json["valid"] == False
        assert "errmsg" in json

    # Send invalid request with unsupported action
    qd = deepcopy(qdict)
    qd["action"] = "dance_in_the_moonlight"
    r = client.get(f"{QUERY_HISTORY_API_ENDPOINT}?{urlencode(qd)}")
    json = _verify_basic(r)
    assert json["valid"] == False
    assert "errmsg" in json


def test_query_utility_functions() -> None:
    """Tests for various utility functions used by query modules."""

    from queries import (
        natlang_seq,
        nom2dat,
        is_plural,
        sing_or_plur,
        spell_out,
        country_desc,
        cap_first,
        time_period_desc,
        distance_desc,
        krona_desc,
        strip_trailing_zeros,
        iceformat_float,
        icequote,
        timezone4loc,
        # parse_num,
    )

    assert natlang_seq(["Jón"]) == "Jón"
    assert natlang_seq(["Jón", "Gunna"]) == "Jón og Gunna"
    assert natlang_seq(["Jón", "Gunna", "Siggi"]) == "Jón, Gunna og Siggi"
    assert (
        natlang_seq(["Jón", "Gunna", "Siggi"], oxford_comma=True)
        == "Jón, Gunna, og Siggi"
    )
    assert (
        natlang_seq(["Jón", "Gunna", "pétur", "Siggi"]) == "Jón, Gunna, pétur og Siggi"
    )

    assert nom2dat("hestur") == "hesti"
    assert nom2dat("Hvolsvöllur") == "Hvolsvelli"

    # assert parse_num("11") == 11
    # assert parse_num("17,33") == 17.33

    assert is_plural(22)
    assert is_plural(11)
    assert is_plural("76,3")
    assert is_plural(27.6)
    assert is_plural("19,11")
    assert not is_plural("276,1")
    assert not is_plural(22.1)
    assert not is_plural(22.41)

    assert sing_or_plur(21, "maður", "menn") == "21 maður"
    assert sing_or_plur(11, "köttur", "kettir") == "11 kettir"
    assert sing_or_plur(2.11, "króna", "krónur") == "2,11 krónur"
    assert sing_or_plur(172, "einstaklingur", "einstaklingar") == "172 einstaklingar"
    assert sing_or_plur(72.1, "gráða", "gráður") == "72,1 gráða"

    assert spell_out("LÍÚ") == "ell í ú"
    assert spell_out("líú") == "ell í ú"
    assert spell_out("fTb") == "eff té bé"
    assert spell_out("F t B ") == "eff té bé"
    assert spell_out("YnG") == "ufsilon enn gé"
    assert spell_out(" YnG") == "ufsilon enn gé"

    assert country_desc("DE") == "í Þýskalandi"
    assert country_desc("es") == "á Spáni"
    assert country_desc("IS") == "á Íslandi"
    assert country_desc("us") == "í Bandaríkjunum"
    assert country_desc("IT") == "á Ítalíu"

    assert cap_first("yolo") == "Yolo"
    assert cap_first("YOLO") == "YOLO"
    assert cap_first("yoLo") == "YoLo"
    assert cap_first("Yolo") == "Yolo"
    assert cap_first("þristur") == "Þristur"
    assert cap_first("illur ásetninguR") == "Illur ásetninguR"

    assert time_period_desc(3751) == "1 klukkustund og 3 mínútur"
    assert (
        time_period_desc(3751, omit_seconds=False)
        == "1 klukkustund, 2 mínútur og 31 sekúnda"
    )
    assert time_period_desc(601) == "10 mínútur"
    assert time_period_desc(610, omit_seconds=False) == "10 mínútur og 10 sekúndur"
    assert time_period_desc(61, omit_seconds=False) == "1 mínúta og 1 sekúnda"
    assert (
        time_period_desc(121, omit_seconds=False, case="þgf")
        == "2 mínútum og 1 sekúndu"
    )
    assert time_period_desc(3751, num_to_str=True) == "ein klukkustund og þrjár mínútur"
    assert (
        time_period_desc(3751, omit_seconds=False, num_to_str=True)
        == "ein klukkustund, tvær mínútur og þrjátíu og ein sekúnda"
    )
    assert time_period_desc(601, num_to_str=True) == "tíu mínútur"
    assert (
        time_period_desc(86401, omit_seconds=False, case="ef", num_to_str=True)
        == "eins dags og einnar sekúndu"
    )
    assert (
        time_period_desc(172802, omit_seconds=False, case="þf", num_to_str=True)
        == "tvo daga og tvær sekúndur"
    )
    assert (
        time_period_desc(121, omit_seconds=False, case="þgf", num_to_str=True)
        == "tveimur mínútum og einni sekúndu"
    )

    assert distance_desc(1.1) == "1,1 kílómetri"
    assert distance_desc(1.2) == "1,2 kílómetrar"
    assert distance_desc(0.7) == "700 metrar"
    assert distance_desc(0.021) == "20 metrar"
    assert distance_desc(41, case="þf") == "41 kílómetra"
    assert distance_desc(0.215, case="þgf") == "220 metrum"
    assert distance_desc(1.1, num_to_str=True) == "einn komma einn kílómetri"
    assert distance_desc(1.2, num_to_str=True) == "einn komma tveir kílómetrar"
    assert (
        distance_desc(1.2, case="þgf", num_to_str=True)
        == "einum komma tveimur kílómetrum"
    )
    assert (
        distance_desc(1.2, case="ef", num_to_str=True) == "eins komma tveggja kílómetra"
    )
    assert distance_desc(0.7, num_to_str=True) == "sjö hundruð metrar"
    assert distance_desc(0.021, num_to_str=True) == "tuttugu metrar"
    assert distance_desc(41, case="þf", num_to_str=True) == "fjörutíu og einn kílómetra"
    assert (
        distance_desc(0.215, case="þgf", num_to_str=True)
        == "tvö hundruð og tuttugu metrum"
    )

    assert krona_desc(361) == "361 króna"
    assert krona_desc(28) == "28 krónur"
    assert krona_desc(4264.2) == "4.264,2 krónur"
    assert krona_desc(2443681.1) == "2.443.681,1 króna"

    assert strip_trailing_zeros("17,0") == "17"
    assert strip_trailing_zeros("219.117,0000") == "219.117"
    assert strip_trailing_zeros("170") == "170"
    assert strip_trailing_zeros("170,0") == "170"

    assert iceformat_float(666.0) == "666"
    assert iceformat_float(666, strip_zeros=False) == "666,00"
    assert iceformat_float(217.296) == "217,3"
    assert iceformat_float(2528963.9) == "2.528.963,9"
    assert iceformat_float(123.12341, decimal_places=4) == "123,1234"
    assert iceformat_float(123.1000, strip_zeros=True) == "123,1"
    assert iceformat_float(123.0, decimal_places=4, strip_zeros=False) == "123,0000"

    assert icequote("sæll") == "„sæll“"
    assert icequote(" Góðan daginn ") == "„Góðan daginn“"

    assert timezone4loc((64.157202, -21.948536)) == "Atlantic/Reykjavik"
    assert timezone4loc((40.093368, 57.000067)) == "Asia/Ashgabat"


def test_numbers() -> None:
    """Test number handling functionality in queries"""

    from queries.num import number_to_neutral, number_to_text, numbers_to_text

    assert number_to_neutral(2) == "tvö"
    assert number_to_neutral(1100) == "eitt þúsund og eitt hundrað"
    assert (
        number_to_neutral(-42178249)
        == "mínus fjörutíu og tvær milljónir eitt hundrað sjötíu og átta þúsund tvö hundruð fjörutíu og níu"
    )
    assert number_to_neutral(241000000000) == "tvö hundruð fjörutíu og einn milljarður"
    assert number_to_neutral(100000000) == "eitt hundrað milljónir"
    assert number_to_neutral(1000001000) == "einn milljarður og eitt þúsund"
    assert number_to_neutral(1000000011) == "einn milljarður og ellefu"
    assert number_to_neutral(1001000000) == "einn milljarður og ein milljón"
    assert number_to_neutral(1002000000) == "einn milljarður og tvær milljónir"
    assert number_to_neutral(200000000000) == "tvö hundruð milljarðar"
    assert (
        number_to_text(1000200200)
        == "einn milljarður tvö hundruð þúsund og tvö hundruð"
    )
    assert (
        number_to_neutral(10000000000000000000000000000000000000000000000000000000)
        == "tíu milljónir oktilljóna"
    )
    assert (
        number_to_neutral(1000000000000000000000000000000000000001000000000)
        == "ein oktilljón og einn milljarður"
    )
    assert (
        number_to_neutral(1000000000000000000000000000000000000003000000000)
        == "ein oktilljón og þrír milljarðar"
    )
    assert number_to_neutral(3000400000) == "þrír milljarðar og fjögur hundruð þúsund"
    assert (
        number_to_neutral(2000000000000000000000000000000000100000000000000)
        == "tvær oktilljónir og eitt hundrað billjónir"
    )
    assert number_to_text(320) == "þrjú hundruð og tuttugu"
    assert number_to_text(320000) == "þrjú hundruð og tuttugu þúsund"
    assert (
        number_to_text(3202020202020)
        == "þrjár billjónir tvö hundruð og tveir milljarðar tuttugu milljónir tvö hundruð og tvö þúsund og tuttugu"
    )
    assert (
        number_to_text(320202020)
        == "þrjú hundruð og tuttugu milljónir tvö hundruð og tvö þúsund og tuttugu"
    )

    assert number_to_text(101, gender="kk") == "hundrað og einn"
    assert number_to_text(-102, gender="kvk") == "mínus hundrað og tvær"
    assert (
        number_to_text(-102, gender="kvk", one_hundred=True)
        == "mínus eitt hundrað og tvær"
    )
    assert number_to_text(5, gender="kk") == "fimm"
    assert number_to_text(10001, gender="kvk") == "tíu þúsund og ein"
    assert (
        number_to_text(113305, gender="kk")
        == "eitt hundrað og þrettán þúsund þrjú hundruð og fimm"
    )
    assert number_to_text(400567, gender="hk") == number_to_neutral(400567)
    assert (
        number_to_text(-11220024, gender="kvk")
        == "mínus ellefu milljónir tvö hundruð og tuttugu þúsund tuttugu og fjórar"
    )

    assert numbers_to_text("Baugatangi 1, Reykjavík") == "Baugatangi eitt, Reykjavík"
    assert numbers_to_text("Baugatangi 2, Reykjavík") == "Baugatangi tvö, Reykjavík"
    assert numbers_to_text("Baugatangi 3, Reykjavík") == "Baugatangi þrjú, Reykjavík"
    assert numbers_to_text("Baugatangi 4, Reykjavík") == "Baugatangi fjögur, Reykjavík"
    assert numbers_to_text("Baugatangi 5, Reykjavík") == "Baugatangi fimm, Reykjavík"
    assert numbers_to_text("Baugatangi 10, Reykjavík") == "Baugatangi tíu, Reykjavík"
    assert numbers_to_text("Baugatangi 11, Reykjavík") == "Baugatangi ellefu, Reykjavík"
    assert numbers_to_text("Baugatangi 12, Reykjavík") == "Baugatangi tólf, Reykjavík"
    assert (
        numbers_to_text("Baugatangi 13, Reykjavík") == "Baugatangi þrettán, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 14, Reykjavík") == "Baugatangi fjórtán, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 15, Reykjavík") == "Baugatangi fimmtán, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 20, Reykjavík") == "Baugatangi tuttugu, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 21, Reykjavík")
        == "Baugatangi tuttugu og eitt, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 22, Reykjavík")
        == "Baugatangi tuttugu og tvö, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 23, Reykjavík")
        == "Baugatangi tuttugu og þrjú, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 24, Reykjavík")
        == "Baugatangi tuttugu og fjögur, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 25, Reykjavík")
        == "Baugatangi tuttugu og fimm, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 100, Reykjavík") == "Baugatangi hundrað, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 101, Reykjavík")
        == "Baugatangi hundrað og eitt, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 102, Reykjavík")
        == "Baugatangi hundrað og tvö, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 103, Reykjavík")
        == "Baugatangi hundrað og þrjú, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 104, Reykjavík")
        == "Baugatangi hundrað og fjögur, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 105, Reykjavík")
        == "Baugatangi hundrað og fimm, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 111, Reykjavík")
        == "Baugatangi hundrað og ellefu, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 112, Reykjavík")
        == "Baugatangi hundrað og tólf, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 113, Reykjavík")
        == "Baugatangi hundrað og þrettán, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 114, Reykjavík")
        == "Baugatangi hundrað og fjórtán, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 115, Reykjavík")
        == "Baugatangi hundrað og fimmtán, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 121, Reykjavík")
        == "Baugatangi hundrað tuttugu og eitt, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 174, Reykjavík")
        == "Baugatangi hundrað sjötíu og fjögur, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 200, Reykjavík")
        == "Baugatangi tvö hundruð, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 201, Reykjavík")
        == "Baugatangi tvö hundruð og eitt, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 202, Reykjavík")
        == "Baugatangi tvö hundruð og tvö, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 203, Reykjavík")
        == "Baugatangi tvö hundruð og þrjú, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 204, Reykjavík")
        == "Baugatangi tvö hundruð og fjögur, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 205, Reykjavík")
        == "Baugatangi tvö hundruð og fimm, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 211, Reykjavík")
        == "Baugatangi tvö hundruð og ellefu, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 212, Reykjavík")
        == "Baugatangi tvö hundruð og tólf, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 213, Reykjavík")
        == "Baugatangi tvö hundruð og þrettán, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 214, Reykjavík")
        == "Baugatangi tvö hundruð og fjórtán, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 215, Reykjavík")
        == "Baugatangi tvö hundruð og fimmtán, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 700, Reykjavík")
        == "Baugatangi sjö hundruð, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 1-4, Reykjavík")
        == "Baugatangi eitt-fjögur, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 1-17, Reykjavík")
        == "Baugatangi eitt-sautján, Reykjavík"
    )


def test_years() -> None:
    """Test number to written year conversion."""

    from queries.num import year_to_text, years_to_text

    assert year_to_text(1999) == "nítján hundruð níutíu og níu"
    assert year_to_text(2004) == "tvö þúsund og fjögur"
    assert year_to_text(-501) == "fimm hundruð og eitt fyrir Krist"
    assert year_to_text(1001, after_christ=True) == "eitt þúsund og eitt eftir Krist"
    assert year_to_text(57, after_christ=True) == "fimmtíu og sjö eftir Krist"
    assert year_to_text(2401) == "tvö þúsund fjögur hundruð og eitt"

    assert (
        years_to_text("Ég fæddist 1994") == "Ég fæddist nítján hundruð níutíu og fjögur"
    )
    assert (
        years_to_text("Árið 1461 var borgin Sarajevo stofnuð")
        == "Árið fjórtán hundruð sextíu og eitt var borgin Sarajevo stofnuð"
    )
    assert (
        years_to_text("17. júlí 1210 lést Sverker II")
        == "17. júlí tólf hundruð og tíu lést Sverker II"
    )
    assert (
        years_to_text("2021, 2007 og 1999")
        == "tvö þúsund tuttugu og eitt, tvö þúsund og sjö og nítján hundruð níutíu og níu"
    )


def test_ordinals() -> None:
    """Test number to written ordinal conversion."""

    from queries.num import number_to_ordinal, numbers_to_ordinal

    assert number_to_ordinal(0) == "núllti"
    assert number_to_ordinal(22, case="þgf", gender="kvk") == "tuttugustu og annarri"
    assert number_to_ordinal(302, gender="kvk") == "þrjú hundraðasta og önnur"
    assert number_to_ordinal(302, case="þgf", gender="hk") == "þrjú hundraðasta og öðru"
    assert (
        number_to_ordinal(10202, case="þgf", gender="hk", number="ft")
        == "tíu þúsund tvö hundruðustu og öðrum"
    )
    assert (
        number_to_ordinal(1000000, case="þf", gender="kvk", number="et")
        == "milljónustu"
    )
    assert (
        number_to_ordinal(1000000002, case="þf", gender="kvk", number="et")
        == "milljörðustu og aðra"
    )

    assert (
        numbers_to_ordinal("Ég lenti í 41. sæti.", case="þgf")
        == "Ég lenti í fertugasta og fyrsta sæti."
    )
    assert (
        numbers_to_ordinal("2. í röðinni var hæstur.") == "annar í röðinni var hæstur."
    )
    assert (
        numbers_to_ordinal("1. konan lenti í 2. sæti.", regex=r"1\.", gender="kvk")
        == "fyrsta konan lenti í 2. sæti."
    )
    assert (
        numbers_to_ordinal("fyrsta konan lenti í 2. sæti.", gender="hk", case="þgf")
        == "fyrsta konan lenti í öðru sæti."
    )
    assert (
        numbers_to_ordinal("Ég var 10201. í röðinni.")
        == "Ég var tíu þúsund tvö hundraðasti og fyrsti í röðinni."
    )


def test_floats() -> None:
    """Test float to written text conversion."""

    from queries.num import float_to_text, floats_to_text

    assert float_to_text(-0.12) == "mínus núll komma tólf"
    assert float_to_text(-0.1012) == "mínus núll komma eitt núll eitt tvö"
    assert float_to_text(-21.12, gender="kk") == "mínus tuttugu og einn komma tólf"
    assert (
        float_to_text(-21.123, gender="kk")
        == "mínus tuttugu og einn komma einn tveir þrír"
    )
    assert float_to_text(1.03, gender="kvk") == "ein komma núll þrjár"

    assert (
        floats_to_text("2,13 millilítrar af vökva.", gender="kk")
        == "tveir komma þrettán millilítrar af vökva."
    )
    assert floats_to_text("0,04 prósent.") == "núll komma núll fjögur prósent."
    assert (
        floats_to_text("101,0021 prósent.")
        == "hundrað og eitt komma núll núll tuttugu og eitt prósent."
    )
    assert (
        floats_to_text("10.100,21 prósent.")
        == "tíu þúsund og eitt hundrað komma tuttugu og eitt prósent."
    )
    assert floats_to_text("2.000.000,00.", comma_null=False) == "tvær milljónir."


def test_digits() -> None:
    """Test digit string to written text conversion."""

    from queries.num import digits_to_text

    assert digits_to_text("5885522") == "fimm átta átta fimm fimm tveir tveir"
    assert digits_to_text("112") == "einn einn tveir"
    assert digits_to_text("123-0679") == "einn tveir þrír-núll sex sjö níu"
    assert (
        digits_to_text("Síminn minn er 12342")
        == "Síminn minn er einn tveir þrír fjórir tveir"
    )
    assert digits_to_text("581 2345") == "fimm átta einn tveir þrír fjórir fimm"
    assert (
        digits_to_text("5812345, það er síminn hjá þeim.")
        == "fimm átta einn tveir þrír fjórir fimm, það er síminn hjá þeim."
    )
    assert (
        digits_to_text("010270-2039")
        == "núll einn núll tveir sjö núll-tveir núll þrír níu"
    )
    assert (
        digits_to_text("192 0-1-127", regex=r"\d\d\d")
        == "einn níu tveir 0-1-einn tveir sjö"
    )
    assert (
        digits_to_text("Hringdu í 1-800-BULL", regex=r"\d+-\d+")
        == "Hringdu í einn átta núll núll-BULL"
    )
