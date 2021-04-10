"""

    Greynir: Natural language processing for Icelandic

    Copyright (C) 2021 Miðeind ehf.

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
from datetime import datetime, timedelta
from urllib.parse import urlencode

from flask.testing import FlaskClient

# Shenanigans to enable Pytest to discover modules in the
# main workspace directory (the parent of /tests)
basepath, _ = os.path.split(os.path.realpath(__file__))
mainpath = os.path.join(basepath, "..")
if mainpath not in sys.path:
    sys.path.insert(0, mainpath)

from main import app

from settings import changedlocale
from db import SessionContext
from db.models import Query, QueryData, QueryLog
from util import read_api_key


@pytest.fixture
def client() -> FlaskClient:
    """ Instantiate Flask's modified Werkzeug client to use in tests """
    app.config["TESTING"] = True
    app.config["DEBUG"] = True
    return app.test_client()


API_CONTENT_TYPE = "application/json"


def qmcall(c: FlaskClient, qdict: Dict[str, Any], qtype: Optional[str] = None) -> Dict:
    """Use passed client object to call query API with
    query string key value pairs provided in dict arg."""

    # test=1 ensures that we bypass the cache and have a (fixed) location
    if "test" not in qdict:
        qdict["test"] = True

    # private=1 makes sure the query isn't logged. This prevents the tests from
    # populating the local database query logging table. Some tests may rely
    # on query history, in which case private=0 should be explicitly specified.
    if "private" not in qdict:
        qdict["private"] = True

    # Create query string
    qstr = urlencode(qdict)

    # Use client to call API endpoint
    r = c.get("/query.api?" + qstr)

    # Basic validation of response
    assert r.content_type.startswith(API_CONTENT_TYPE)
    assert r.is_json
    json = r.get_json()
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


def has_google_api_key() -> bool:
    return read_api_key("GoogleServerKey") != ""


DUMMY_CLIENT_ID = "QueryTesting123"


def test_query_api(client):
    """ Make various query API calls and validate response. """

    c = client

    google_key = has_google_api_key()

    # First, make sure nonsensical queries are not answered
    qstr = {"q": "blergh smergh vlurgh"}
    r = c.get("/query.api?" + urlencode(qstr))
    assert r.content_type.startswith(API_CONTENT_TYPE)
    assert r.is_json
    json = r.get_json()
    assert "valid" in json
    assert json["valid"]
    assert "error" in json
    assert "answer" not in json

    # Arithmetic module
    ARITHM_QUERIES = {
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
        "hvað er 17 deilt með fjórum": "4,25",
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
        "reiknaðu sjö x sjö": "49",
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
        json = qmcall(c, {"q": q}, "Arithmetic")
        assert json["answer"] == a

    json = qmcall(
        c, {"q": "hvað er pí", "client_id": DUMMY_CLIENT_ID, "private": False}, "PI"
    )
    assert "π" in json["answer"]
    assert "3,14159" in json["answer"]

    json = qmcall(
        c, {"q": "hvað er það sinnum tveir", "client_id": DUMMY_CLIENT_ID}, "Arithmetic"
    )
    assert json["answer"].startswith("6,")

    # Person and entity title queries are tested using a dummy database
    # populated with data from CSV files stored in tests/test_files/testdb_*.csv

    # Builtin module: title
    json = qmcall(c, {"q": "hver er viðar þorsteinsson", "voice": True}, "Person")
    assert json["voice"].startswith("Viðar Þorsteinsson er ")
    assert json["voice"].endswith(".")

    # Builtin module: title
    json = qmcall(c, {"q": "hver er björn þorsteinsson", "voice": True}, "Person")
    assert json["voice"].startswith("Björn Þorsteinsson er ")
    assert json["voice"].endswith(".")

    # Builtin module: person
    json = qmcall(c, {"q": "hver er forsætisráðherra", "voice": True}, "Title")
    assert json["voice"].startswith("Forsætisráðherra er ")
    assert json["voice"].endswith(".")

    # Bus module
    json = qmcall(
        c, {"q": "hvaða stoppistöð er næst mér", "voice": True}, "NearestStop"
    )
    assert json["answer"] == "Fiskislóð"
    assert json["voice"] == "Næsta stoppistöð er Fiskislóð; þangað eru 310 metrar."

    json = qmcall(
        c,
        {"q": "hvenær er von á vagni númer 17", "voice": True, "test": False},
        "ArrivalTime",
    )
    assert json["answer"] == "Staðsetning óþekkt"  # No location info available

    # Counting module
    json = qmcall(c, {"q": "teldu frá einum upp í tíu"}, "Counting")
    assert json["answer"] == "1…10"

    json = qmcall(c, {"q": "teldu hratt niður frá 4", "voice": True}, "Counting")
    assert json["answer"] == "3…0"
    assert "<break time=" in json["voice"]

    json = qmcall(c, {"q": "teldu upp að 5000", "voice": True}, "Counting")
    assert len(json["voice"]) < 100

    # Currency module
    json = qmcall(c, {"q": "hvert er gengi dönsku krónunnar?"}, "Currency")
    assert re.search(r"^\d+(,\d+)?$", json["answer"]) is not None

    json = qmcall(c, {"q": "hvað kostar evran"}, "Currency")
    assert re.search(r"^\d+(,\d+)?$", json["answer"]) is not None

    json = qmcall(c, {"q": "hvað kostar bandaríkjadalur mikið í krónum"}, "Currency")
    assert re.search(r"^\d+(,\d+)?$", json["answer"]) is not None

    json = qmcall(
        c, {"q": "Hvert er gengi krónunnar gagnvart dollara í dag?"}, "Currency"
    )
    assert re.search(r"^\d+(,\d+)?$", json["answer"]) is not None

    json = qmcall(c, {"q": "hvert er gengi krónunnar á móti dollara í dag"}, "Currency")
    assert re.search(r"^\d+(,\d+)?$", json["answer"]) is not None

    json = qmcall(c, {"q": "hvað eru tíu þúsund krónur margir dalir"}, "Currency")
    assert re.search(r"^\d+(,\d+)?$", json["answer"]) is not None

    json = qmcall(c, {"q": "hvað eru 79 dollarar margar evrur?"}, "Currency")
    assert re.search(r"^\d+(,\d+)?$", json["answer"]) is not None

    # Date module
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
        json = qmcall(c, {"q": qstr}, "Date")

    json = qmcall(c, {"q": "hver er dagsetningin?"}, "Date")
    assert json["answer"].endswith(datetime.now().strftime("%Y"))

    json = qmcall(c, {"q": "Hvað eru margir dagar til jóla?", "voice": True}, "Date")
    assert re.search(r"^\d+", json["answer"])
    assert "dag" in json["voice"]

    json = qmcall(c, {"q": "Hvað eru margir dagar í 12. maí?"}, "Date")
    assert "dag" in json["answer"] or "á morgun" in json["answer"]

    # Test to make sure this kind of query isn't caught by the distance module
    json = qmcall(c, {"q": "Hvað er langt í jólin?"}, "Date")
    json = qmcall(c, {"q": "Hvað er langt í páska?"}, "Date")

    now = datetime.utcnow()

    with changedlocale(category="LC_TIME"):
        # Today
        dstr = now.date().strftime("%-d. %B")
        json = qmcall(c, {"q": "Hvað eru margir dagar í " + dstr})
        assert "í dag" in json["answer"]
        # Tomorrow
        dstr = (now.date() + timedelta(days=1)).strftime("%-d. %B")
        json = qmcall(c, {"q": "Hvað eru margir dagar í " + dstr})
        assert "á morgun" in json["answer"]

    json = qmcall(c, {"q": "hvaða ár er núna?"}, "Date")
    assert str(now.year) in json["answer"]

    json = qmcall(c, {"q": "er hlaupár?"}, "Date")
    assert str(now.year) in json["answer"]

    json = qmcall(c, {"q": "er 2020 hlaupár?"}, "Date")
    assert "var hlaupár" in json["answer"]

    json = qmcall(c, {"q": "var árið 1999 hlaupár?"}, "Date")
    assert "ekki hlaupár" in json["answer"]

    json = qmcall(c, {"q": "hvað eru margir dagar í desember"}, "Date")
    assert json["answer"].startswith("31")
    assert "dag" in json["answer"]

    json = qmcall(c, {"q": "hvað eru margir dagar í febrúar 2024"}, "Date")
    assert json["answer"].startswith("29")
    assert "dag" in json["answer"]

    json = qmcall(c, {"q": "Hvað er langt fram að verslunarmannahelgi"}, "Date")
    assert re.search(r"^\d+", json["answer"])

    # json = qmcall(c, {"q": "hvað er langt liðið frá uppstigningardegi"}, "Date")
    # assert re.search(r"^\d+", json["answer"])

    json = qmcall(c, {"q": "hvenær eru jólin"}, "Date")
    assert re.search(r"25", json["answer"]) is not None

    # Dictionary module
    json = qmcall(
        c, {"q": "hvernig skilgreinir orðabókin orðið kettlingur"}, "Dictionary"
    )
    assert "kettlingur" in json["answer"].lower()

    json = qmcall(c, {"q": "flettu upp orðinu skíthæll í orðabók"}, "Dictionary")
    assert "skíthæll" in json["answer"].lower()
    assert json["source"] == "Íslensk nútímamálsorðabók"

    # Distance module
    # NB: No Google API key on test server
    if google_key:
        json = qmcall(
            c, {"q": "hvað er ég langt frá perlunni", "voice": True}, "Distance"
        )
        assert json["answer"].startswith("3,5 km")
        assert json["voice"].startswith("Perlan er ")
        assert json["source"] == "Google Maps"

        json = qmcall(c, {"q": "hvað er langt í melabúðina", "voice": True}, "Distance")
        assert json["answer"].startswith("1,") and "km" in json["answer"]
        assert json["voice"].startswith("Melabúðin er ")

        json = qmcall(
            c, {"q": "hvað er ég lengi að ganga í kringluna", "voice": True}, "Distance"
        )
        assert json["key"] == "Kringlan"
        assert "klukkustund" in json["answer"] and " km" in json["answer"]
        assert json["voice"].startswith("Að ganga")

        json = qmcall(
            c, {"q": "hvað tekur langan tíma að keyra til akureyrar"}, "Distance"
        )
        assert json["key"] == "Akureyri"
        assert "klukkustundir" in json["answer"] and " km" in json["answer"]
        assert json["answer"].endswith("(389 km).")

    # Flights module
    # TODO: Implement me!

    # Geography module
    json = qmcall(c, {"q": "hver er höfuðborg spánar", "voice": True}, "Geography")
    assert json["answer"] == "Madríd"
    assert "Spánar" in json["voice"]  # not 'Spáns', which was a bug

    json = qmcall(c, {"q": "Hver er höfuðborg taiwan"}, "Geography")
    assert json["answer"] == "Taípei"

    json = qmcall(c, {"q": "hver er höfuðborg norður-makedóníu"}, "Geography")
    assert json["answer"] == "Skopje"

    json = qmcall(c, {"q": "hver er höfuðborg norður kóreu"}, "Geography")
    assert json["answer"] == "Pjongjang"

    # json = qmcall(
    #     c, {"q": "hver er höfuðborg sameinuðu arabísku furstadæmanna"}, "Geography"
    # )
    # assert json["answer"] == "Abú Dabí"

    json = qmcall(c, {"q": "hvað er höfuðborgin í bretlandi"}, "Geography")
    assert json["answer"] == "Lundúnir"

    json = qmcall(c, {"q": "í hvaða landi er jóhannesarborg"}, "Geography")
    assert json["answer"].endswith("Suður-Afríku")

    json = qmcall(c, {"q": "í hvaða landi er kalifornía"}, "Geography")
    assert "Bandaríkjunum" in json["answer"] and json["key"] == "Kalifornía"

    json = qmcall(c, {"q": "í hvaða heimsálfu er míkrónesía"}, "Geography")
    assert json["answer"].startswith("Eyjaálfu")

    json = qmcall(c, {"q": "hvar í heiminum er máritanía"}, "Geography")
    assert "Afríku" in json["answer"]

    json = qmcall(c, {"q": "hvar er Kaupmannahöfn"}, "Geography")
    assert "Danmörku" in json["answer"]

    # News module
    json = qmcall(c, {"q": "Hvað er í fréttum", "voice": True}, "News")
    assert len(json["answer"]) > 80  # This is always going to be a long answer
    assert json["voice"].startswith("Í fréttum rúv er þetta helst")

    # Opinion module
    json = qmcall(c, {"q": "hvaða skoðun hefurðu á þriðja orkupakkanum"}, "Opinion")
    assert json["answer"].startswith("Ég hef enga sérstaka skoðun")
    assert json["key"] == "þriðji orkupakkinn"

    json = qmcall(
        c, {"q": "hvað finnst þér eiginlega um Katrínu Jakobsdóttur"}, "Opinion"
    )
    assert json["answer"].startswith("Ég hef enga sérstaka skoðun")
    assert json["key"] == "Katrín Jakobsdóttir"

    # Petrol module
    json = qmcall(c, {"q": "Hvar er næsta bensínstöð", "voice": True}, "Petrol")
    assert "Ánanaust" in json["answer"]
    assert "source" in json and json["source"].startswith("Gasvaktin")

    json = qmcall(
        c, {"q": "Hvar fæ ég ódýrt bensín í nágrenninu", "voice": True}, "Petrol"
    )
    assert "source" in json and json["source"].startswith("Gasvaktin")

    json = qmcall(c, {"q": "Hvar fæ ég ódýrasta bensínið"}, "Petrol")
    assert "source" in json and json["source"].startswith("Gasvaktin")

    # Places module
    # NB: No Google API key on test server
    if google_key:
        json = qmcall(c, {"q": "Hvað er opið lengi í Melabúðinni"}, "Places")
        json = qmcall(c, {"q": "Er lokað á Forréttabarnum?"}, "Places")

    # Random module
    json = qmcall(c, {"q": "Veldu tölu milli sautján og 30"}, "Random")
    assert int(json["answer"]) >= 17 and int(json["answer"]) <= 30

    json = qmcall(c, {"q": "kastaðu teningi"}, "Random")
    assert int(json["answer"]) >= 1 and int(json["answer"]) <= 6

    json = qmcall(c, {"q": "kastaðu átta hliða teningi"}, "Random")
    assert int(json["answer"]) >= 1 and int(json["answer"]) <= 8

    json = qmcall(c, {"q": "fiskur eða skjaldarmerki"}, "Random")
    a = json["answer"].lower()
    assert "fiskur" in a or "skjaldarmerki" in a

    json = qmcall(c, {"q": "kastaðu peningi"}, "Random")
    a = json["answer"].lower()
    assert "fiskur" in a or "skjaldarmerki" in a

    # Repeat module
    # json = qmcall(c, {"q": "segðu setninguna simmi er bjálfi"}, "Parrot")
    # assert json["answer"] == "Simmi er bjálfi"
    # assert json["q"] == "Segðu setninguna „Simmi er bjálfi.“"

    json = qmcall(c, {"q": "segðu eitthvað skemmtilegt"})
    assert json["qtype"] != "Parrot"

    # Schedules module
    json = qmcall(c, {"q": "hvað er í sjónvarpinu núna", "voice": True}, "Schedule")
    assert json["key"] == "TelevisionSchedule"
    json = qmcall(c, {"q": "Hvaða þáttur er eiginlega á rúv núna"}, "Schedule")
    assert json["key"] == "TelevisionSchedule"
    json = qmcall(c, {"q": "hvað er í sjónvarpinu í kvöld?"}, "Schedule")
    assert json["key"] == "TelevisionEvening"
    json = qmcall(c, {"q": "hver er sjónvarpsdagskráin í kvöld?"}, "Schedule")
    assert json["key"] == "TelevisionEvening"
    # json = qmcall(c, {"q": "hvað er í útvarpinu núna?"}, "Schedule")
    # assert json["qkey"] == "RadioSchedule"
    # json = qmcall(c, {"q": "hvað er eiginlega í gangi á rás eitt?"}, "Schedule")
    # assert json["qkey"] == "RadioSchedule"
    # json = qmcall(c, {"q": "hvað er á dagskrá á rás tvö?"}, "Schedule")
    # assert json["qkey"] == "RadioSchedule"

    # Special module
    json = qmcall(client, {"q": "Hver er sætastur?", "voice": True}, "Special")
    assert json["answer"] == "Tumi Þorsteinsson."
    assert json["voice"] == "Tumi Þorsteinsson er langsætastur."

    # Stats module
    json = qmcall(c, {"q": "hversu marga einstaklinga þekkirðu?"}, "Stats")
    json = qmcall(c, {"q": "Hversu mörgum spurningum hefur þú svarað?"}, "Stats")
    json = qmcall(c, {"q": "hvað ertu aðallega spurð um?"}, "Stats")
    json = qmcall(c, {"q": "hvaða fólk er mest í fréttum"}, "Stats")

    # Telephone module
    json = qmcall(c, {"q": "Hringdu í síma 6 9 9 2 4 2 2"}, "Telephone")
    assert "open_url" in json
    assert json["open_url"] == "tel:6992422"
    assert json["q"].endswith("6992422")

    json = qmcall(c, {"q": "hringdu fyrir mig í númerið 69 92 42 2"}, "Telephone")
    assert "open_url" in json
    assert json["open_url"] == "tel:6992422"
    assert json["q"].endswith("6992422")

    json = qmcall(c, {"q": "vinsamlegast hringdu í 921-7422"}, "Telephone")
    assert "open_url" in json
    assert json["open_url"] == "tel:9217422"
    assert json["q"].endswith("9217422")

    json = qmcall(c, {"q": "hringdu í 26"}, "Telephone")
    assert "ekki gilt símanúmer" in json["answer"]

    # Time module
    json = qmcall(c, {"q": "hvað er klukkan í Kaupmannahöfn?", "voice": True}, "Time")
    assert json["key"] == "Europe/Copenhagen"
    assert re.search(r"^\d\d:\d\d$", json["answer"])

    json = qmcall(c, {"q": "Hvað er klukkan núna", "voice": True}, "Time")
    assert json["key"] == "Atlantic/Reykjavik"
    assert re.search(r"^\d\d:\d\d$", json["answer"])
    assert json["voice"].startswith("Klukkan er")

    json = qmcall(c, {"q": "Hvað er klukkan í Japan?", "voice": True}, "Time")
    assert json["key"] == "Asia/Tokyo"
    assert re.search(r"^\d\d:\d\d$", json["answer"])
    assert json["voice"].lower().startswith("klukkan í japan er")

    # Unit module
    json = qmcall(c, {"q": "Hvað eru margir metrar í mílu?"}, "Unit")
    assert json["answer"] == "1.610 metrar"

    json = qmcall(c, {"q": "hvað eru margar sekúndur í tveimur dögum?"}, "Unit")
    assert json["answer"] == "173.000 sekúndur"

    json = qmcall(c, {"q": "hvað eru tíu steinar mörg kíló?"}, "Unit")
    assert json["answer"] == "63,5 kíló"

    json = qmcall(c, {"q": "hvað eru sjö vökvaúnsur margir lítrar"}, "Unit")
    assert json["answer"] == "0,21 lítrar"

    json = qmcall(c, {"q": "hvað eru 18 merkur mörg kíló"}, "Unit")
    assert json["answer"] == "4,5 kíló"

    json = qmcall(c, {"q": "hvað eru mörg korter í einum degi"}, "Unit")
    assert json["answer"].startswith("96")

    json = qmcall(c, {"q": "hvað eru margar mínútur í einu ári"}, "Unit")
    assert json["answer"].startswith("526.000 mínútur")

    # User info module
    json = qmcall(
        c,
        {"q": "ég heiti Gunna Jónsdóttir", "client_id": DUMMY_CLIENT_ID},
        "UserInfo",
    )
    assert json["answer"].startswith("Sæl og blessuð") and "Gunna" in json["answer"]

    json = qmcall(c, {"q": "hvað heiti ég", "client_id": DUMMY_CLIENT_ID})
    assert "Gunna Jónsdóttir" in json["answer"]

    json = qmcall(
        c, {"q": "Nafn mitt er Gunnar", "client_id": DUMMY_CLIENT_ID}, "UserInfo"
    )
    assert json["answer"].startswith("Sæll og blessaður") and "Gunnar" in json["answer"]

    json = qmcall(
        c, {"q": "veistu hvað ég heiti", "client_id": DUMMY_CLIENT_ID}, "UserInfo"
    )
    assert json["answer"].startswith("Þú heitir Gunnar")

    json = qmcall(c, {"q": "ég heiti Boutros Boutros-Ghali"}, "UserInfo")
    assert json["answer"].startswith("Gaman að kynnast") and "Boutros" in json["answer"]

    json = qmcall(
        c,
        {
            "q": "hvaða útgáfu er ég að keyra",
            "client_type": "ios",
            "client_version": "1.0.3",
            "voice": True,
        },
    )
    assert "iOS" in json["answer"] and "1.0.3" in json["answer"]
    assert "komma" in json["voice"]

    json = qmcall(c, {"q": "á hvaða tæki ertu að keyra?", "client_type": "ios"})
    assert "iOS" in json["answer"]

    # json = qmcall(
    #     c,
    #     {"q": "ég á heima á öldugötu 4 í reykjavík", "client_id": DUMMY_CLIENT_ID},
    #     "UserInfo",
    # )
    # assert json["answer"].startswith("Gaman að kynnast") and "Boutros" in json["answer"]

    # json = qmcall(c, {"q": "hvar á ég heima"}, "UserInfo")
    # assert json["answer"].startswith("Gaman að kynnast") and "Boutros" in json["answer"]

    # json = qmcall(c, {"q": "ég á heima á Fiskislóð 31"}, "UserInfo")
    # assert json["answer"].startswith("Gaman að kynnast") and "Boutros" in json["answer"]

    # json = qmcall(c, {"q": "hvar bý ég eiginlega"}, "UserInfo")
    # assert json["answer"].startswith("Gaman að kynnast") and "Boutros" in json["answer"]

    # User location module
    # NB: No Google API key on test server
    if google_key:
        json = qmcall(c, {"q": "Hvar er ég"}, "UserLocation")
        assert "Fiskislóð 31" in json["answer"]
        json = qmcall(
            c, {"q": "Hvar í heiminum er ég eiginlega staddur?"}, "UserLocation"
        )
        assert "Fiskislóð 31" in json["answer"]

    # Weather module
    json = qmcall(c, {"q": "hvernig er veðrið í Reykjavík?"}, "Weather")
    assert re.search(r"^\-?\d+ °C", json["answer"]) is not None

    json = qmcall(c, {"q": "Hversu hlýtt er úti?"}, "Weather")
    assert re.search(r"^\-?\d+ °C", json["answer"]) is not None

    json = qmcall(c, {"q": "hver er veðurspáin fyrir morgundaginn"}, "Weather")
    assert len(json["answer"]) > 20 and "." in json["answer"]

    # Wikipedia module
    json = qmcall(c, {"q": "Hvað segir wikipedia um Jón Leifs?"}, "Wikipedia")
    assert "Wikipedía" in json["q"]  # Make sure it's being beautified
    assert "tónskáld" in json["answer"]
    assert "source" in json and "wiki" in json["source"].lower()

    json = qmcall(c, {"q": "hvað segir vikipedija um jóhann sigurjónsson"}, "Wikipedia")
    assert "Jóhann" in json["answer"]

    json = qmcall(c, {"q": "fræddu mig um berlín"}, "Wikipedia")
    assert "Berlín" in json["answer"]

    json = qmcall(
        c,
        {
            "q": "katrín Jakobsdóttir í vikipediju",
            "client_id": DUMMY_CLIENT_ID,
            "private": False,
        },
        "Wikipedia",
    )
    assert "Katrín Jakobsdóttir" in json["answer"]

    json = qmcall(
        c,
        {"q": "hvað segir wikipedía um hana", "client_id": DUMMY_CLIENT_ID},
        "Wikipedia",
    )
    assert "Katrín Jakobsdóttir" in json["answer"]

    # Words module
    json = qmcall(
        c, {"q": "hvernig stafar maður orðið hestur", "voice": True}, "Spelling"
    )
    assert json["answer"] == "H E S T U R"
    assert json["voice"].startswith("Orðið „hestur“ ")

    json = qmcall(c, {"q": "hvernig beygist orðið maður", "voice": True}, "Declension")
    assert json["answer"].lower() == "maður, mann, manni, manns"
    assert json["voice"].startswith("Orðið „maður“")
    json = qmcall(c, {"q": "hvernig beygir maður nafnorðið splorglobb?", "voice": True})
    assert json["voice"].startswith("Nafnorðið „splorglobb“ fannst ekki")

    # Yule lads module
    # TODO: Implement me!

    # Delete any queries or query data logged as result of these tests
    with SessionContext(commit=True) as session:
        session.execute(
            Query.table().delete().where(Query.client_id == DUMMY_CLIENT_ID)
        )
        session.execute(
            QueryData.table().delete().where(QueryData.client_id == DUMMY_CLIENT_ID)
        )
        # Note: there is no client_id in the querylog table
        # so we cannot delete the logged queries there by this criterion.


def test_query_utility_functions():
    """ Tests for various utility functions used by query modules. """

    from queries import (
        natlang_seq,
        nom2dat,
        numbers_to_neutral,
        is_plural,
        sing_or_plur,
        country_desc,
        cap_first,
        time_period_desc,
        distance_desc,
        krona_desc,
        strip_trailing_zeros,
        iceformat_float,
        icequote,
        timezone4loc,
    )

    assert natlang_seq(["Jón", "Gunna"]) == "Jón og Gunna"
    assert natlang_seq(["Jón", "Gunna", "Siggi"]) == "Jón, Gunna og Siggi"
    assert (
        natlang_seq(["Jón", "Gunna", "Siggi"], oxford_comma=True)
        == "Jón, Gunna, og Siggi"
    )

    assert nom2dat("hestur") == "hesti"
    assert nom2dat("Hvolsvöllur") == "Hvolsvelli"

    # assert parse_num("11") == 11
    # assert parse_num("17,33") == 17.33
    # assert parse_num

    assert numbers_to_neutral("Öldugötu 4") == "Öldugötu fjögur"
    assert numbers_to_neutral("Fiskislóð 31") == "Fiskislóð þrjátíu og eitt"

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

    assert country_desc("DE") == "í Þýskalandi"
    assert country_desc("es") == "á Spáni"
    assert country_desc("IS") == "á Íslandi"
    assert country_desc("us") == "í Bandaríkjunum"

    assert cap_first("yolo") == "Yolo"
    assert cap_first("YOLO") == "YOLO"
    assert cap_first("Yolo") == "Yolo"

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

    assert distance_desc(1.1) == "1,1 kílómetri"
    assert distance_desc(1.2) == "1,2 kílómetrar"
    assert distance_desc(0.7) == "700 metrar"
    assert distance_desc(0.021) == "20 metrar"
    assert distance_desc(41, case="þf") == "41 kílómetra"
    assert distance_desc(0.215, case="þgf") == "220 metrum"

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
