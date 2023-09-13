"""

    Greynir: Natural language processing for Icelandic

    Stats query response module

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


    This module handles queries related to statistics about the query mechanism.

"""

# TODO: Transition this module over to using query grammar.

from datetime import datetime, timedelta

from db import SessionContext
from db.models import Person
from db.models import Query as QueryModel
from db.sql import QueryTypesQuery

from queries import Query
from queries.util import gen_answer, natlang_seq, is_plural, iceformat_float
from routes.people import top_persons
from icespeak import gssml

_STATS_QTYPE = "Stats"


_NUM_PEOPLE_QUERIES = frozenset(
    (
        "hvað þekkirðu marga",
        "hvað þekkirðu margar manneskjur",
        "hvað þekkir þú margar manneskjur",
        "hvað þekkirðu marga einstaklinga",
        "hvað þekkir þú marga einstaklinga",
        "þekkirðu marga",
        "þekkirðu margar manneskjur",
        "þekkir þú margar manneskjur",
        "þekkirðu marga einstaklinga",
        "þekkir þú marga einstaklinga",
        "þekkirðu mikið af fólki",
        "þekkir þú mikið af fólki",
        "hvað þekkirðu mikið af fólki",
        "hvað þekkir þú mikið af fólki",
        "þekkirðu margt fólk",
        "þekkir þú margt fólk",
        "hvað þekkirðu margt fólk",
        "hvað þekkir þú margt fólk",
        "hversu marga einstaklinga þekkirðu",
        "hversu marga einstaklinga þekkir þú",
        "hversu margar manneskjur þekkirðu",
        "hversu margar manneskjur þekkir þú",
        "hve marga einstaklinga þekkirðu",
        "hve marga einstaklinga þekkir þú",
        "hve margar manneskjur þekkirðu",
        "hve margar manneskjur þekkir þú",
        "hvaða fólk þekkir þú",
        "hvaða fólk þekkirðu",
        "hverja þekkir þú",
        "hverja þekkirðu",
        "hvaða einstaklinga þekkir þú",
        "hvaða einstaklinga þekkirðu",
    )
)


_NUM_QUERIES = frozenset(
    (
        "hvað hefurðu fengið margar fyrirspurnir",
        "hvað hefur þú fengið margar fyrirspurnir",
        "hvað hefurðu fengið margar spurningar",
        "hvað hefur þú fengið margar spurningar",
        "hvað hefurðu svarað mörgum spurningum",
        "hvað hefurðu svarað mörgum spurningum á síðustu dögum",
        "hvað hefur þú svarað mörgum spurningum á síðustu dögum",
        "hvað hefur þú svarað mörgum spurningum frá upphafi",
        "hvað hefurðu svarað mörgum spurningum frá upphafi"
        "hvað hefur þú svarað mörgum spurningum",
        "hvað hefurðu svarað mörgum fyrirspurnum",
        "hvað hefur þú svarað mörgum fyrirspurnum",
        "hversu mörgum fyrirspurnum hefurðu svarað",
        "hversu mörgum fyrirspurnum hefur þú svarað",
        "hversu mörgum spurningum hefurðu svarað",
        "hversu mörgum spurningum hefur þú svarað",
        "hve mörgum fyrirspurnum hefurðu svarað",
        "hve mörgum fyrirspurnum hefur þú svarað",
        "hve mörgum spurningum hefurðu svarað",
        "hve mörgum spurningum hefur þú svarað",
        "hvað ertu búin að svara mörgum spurningum",
        "hvað ert þú búin að svara mörgum spurningum",
        "hvað ertu búin að svara mörgum fyrirspurnum",
        "hvað ert þú búin að svara mörgum fyrirspurnum",
    )
)


_MOST_FREQ_QUERIES = frozenset(
    (
        "hvað er fólk að spyrja þig um",
        "hvað er fólk að spyrja þig mest um",
        "hvað er fólk að spyrja mest um",
        "hvað spyr fólk um",
        "hvað spyr fólk mest um",
        "hvað spyr fólk þig mest um",
        "hvað ertu mest spurð um",
        "hvað ert þú mest spurð um",
        "hvað ertu aðallega spurð um",
        "hvað ert þú aðallega spurð um",
        "hvað spyr fólk þig aðallega um",
        "hvaða fyrirspurnir eru algengastar",
        "hvaða spurningar eru algengastar",
        "hvers konar spurningar eru algengastar",
        "hvernig spurningar færðu mest af",
        "hvernig spurningar færð þú mest af",
        "hvernig fyrirspurnum hefurðu svarað",
        "hvernig fyrirspurnum hefur þú svarað",
        "hvernig fyrirspurnum hefurðu svarað nýlega",
        "hvernig fyrirspurnum hefur þú svarað nýlega",
        "hvers konar fyrirspurnum hefurðu svarað nýlega",
        "hvers konar fyrirspurnum hefur þú svarað nýlega",
        "hvaða spurningum hefur þú svarað",
        "hvaða spurningum hefurðu svarað",
        "hvernig spurningum svararðu oftast",
        "hvers konar spurningum svararðu oftast",
        "hvers konar spurningum hefur þú svarað",
        "hvers konar spurningum hefurðu svarað",
        "um hvað ertu mest spurð",
        "um hvað ert þú mest spurð",
        "um hvað ertu spurð",
        "um hvað ert þú spurð",
        "hvað er algengasta spurningin",
        "hvað er algengast að þú sért spurð",
        "hvað er algengast að þú sért spurð um",
    )
)


# TODO: Refactor this mess
_MOST_MENTIONED_PEOPLE_QUERIES = frozenset(
    (
        "um hverja er verið að tala",
        "um hverja er verið að fjalla í fjölmiðlum",
        "um hverja er mest fjallað í fjölmiðlum",
        "um hverja er mest talað í fjölmiðlum",
        "hverjir eru í fréttum",
        "hverjir eru í fréttum núna",
        "hverjir eru í fréttum þessa dagana",
        "hverjir eru mest í fréttum",
        "hverjir eru mest í fréttum núna",
        "hverjir eru mest í fréttum þessa dagana",
        "hverjir eru mest í fréttum upp á síðkastið",
        "hverjir eru mest áberandi í fjölmiðlum",
        "hverjir eru mest áberandi í fjölmiðlum þessa dagana",
        "hverjir eru áberandi í fjölmiðlum",
        "hverjir eru áberandi í fjölmiðlum þessa dagana",
        "hverjir eru mest í fjölmiðlum",
        "hverjir eru mest í fjölmiðlum núna",
        "hverjir eru mest í fjölmiðlum þessa dagana",
        "hverjir eru mest í fjölmiðlum upp á síðkastið",
        "hvaða fólk hefur verið mest í fjölmiðlum síðustu daga",
        "hvaða fólk er mest í fréttum",
        "hvaða fólk er mest í fréttum núna",
        "hvaða fólk er mest í fréttum þessa dagana",
        "hvaða fólk hefur verið mest í fréttum",
        "hvaða fólk hefur verið mest í fréttum nýlega",
        "hvaða fólk hefur verið mest í fréttum undanfarið",
        "hvaða fólk hefur verið mest í fréttum upp á síðkastið",
        "hvaða fólk hefur verið mest í fréttum að undanförnu",
        "hvaða fólk hefur verið mest í fréttum síðustu daga",
        "hverjir hafa verið í fréttum",
        "hverjir hafa verið í fréttum nýlega",
        "hverjir hafa verið í fréttum undanfarið",
        "hverjir hafa verið í fréttum að undanförnu",
        "hverjir hafa verið í fréttum upp á síðkastið",
        "hverjir hafa verið í fréttum síðustu daga",
        "hverjir hafa verið mest í fréttum",
        "hverjir hafa verið mest í fréttum nýlega",
        "hverjir hafa verið mest í fréttum undanfarið",
        "hverjir hafa verið mest í fréttum að undanförnu",
        "hverjir hafa verið mest í fréttum upp á síðkastið",
        "hverjir hafa verið mest í fréttum síðustu daga",
        "hverjir hafa verið mikið í fréttum",
        "hverjir hafa verið mikið í fréttum nýlega",
        "hverjir hafa verið mikið í fréttum undanfarið",
        "hverjir hafa verið mikið í fréttum að undanförnu",
        "hverjir hafa verið mikið í fréttum upp á síðkastið",
        "hverjir hafa verið mikið í fréttum síðustu daga",
        "hvaða fólk hefur verið mest í fjölmiðlum",
        "hvaða fólk hefur verið mest í fjölmiðlum nýlega",
        "hvaða fólk hefur verið mest í fjölmiðlum undanfarið",
        "hvaða fólk hefur verið mest í fjölmiðlum að undanförnu",
        "hvaða fólk hefur verið mest í fjölmiðlum upp á síðkastið",
        "hvaða fólk hefur verið mest í fjölmiðlum síðustu daga",
        "hvaða einstaklingar hafa verið mest í fjölmiðlum",
        "hvaða einstaklingar hafa verið mest í fjölmiðlum nýlega",
        "hvaða einstaklingar hafa verið mest í fjölmiðlum undanfarið",
        "hvaða einstaklingar hafa verið mest í fjölmiðlum að undanförnu",
        "hvaða einstaklingar hafa verið mest í fjölmiðlum upp á síðkastið",
        "hvaða einstaklingar hafa verið mest í fjölmiðlum síðustu daga",
        "hvaða einstaklingar hafa verið áberandi í fjölmiðlum",
        "hvaða einstaklingar hafa verið áberandi í fjölmiðlum nýlega",
        "hvaða einstaklingar hafa verið áberandi í fjölmiðlum undanfarið",
        "hvaða einstaklingar hafa verið áberandi í fjölmiðlum að undanförnu",
        "hvaða einstaklingar hafa verið áberandi í fjölmiðlum upp á síðkastið",
        "hvaða einstaklingar hafa verið áberandi í fjölmiðlum síðustu daga",
        "hverjir hafa verið mest í fjölmiðlum",
        "hverjir hafa verið mest í fjölmiðlum nýlega",
        "hverjir hafa verið mest í fjölmiðlum undanfarið",
        "hverjir hafa verið mest í fjölmiðlum að undanförnu",
        "hverjir hafa verið mest í fjölmiðlum upp á síðkastið",
        "hverjir hafa verið mest í fjölmiðlum síðustu daga",
        "hverjir hafa oftast komið fyrir í fjölmiðlum",
        "hverjir hafa oftast komið fyrir í fjölmiðlum nýlega",
        "hverjir hafa oftast komið fyrir í fjölmiðlum undanfarið",
        "hverjir hafa oftast komið fyrir í fjölmiðlum að undanförnu",
        "hverjir hafa oftast komið fyrir í fjölmiðlum upp á síðkastið",
        "hverjir hafa oftast komið fyrir í fjölmiðlum síðustu daga",
        "hverjir eru umtöluðustu einstaklingarnir á Íslandi",
        "hverjir eru umtalaðastir",
        "hverjir eru umtalaðastir á Íslandi",
        "um hverja er mest talað",
        "um hverja er mest skrifað",
        "hverjir hafa verið áberandi í fjölmiðlum",
        "hverjir hafa verið áberandi í fjölmiðlum síðustu daga",
        "hverjir hafa verið áberandi í fjölmiðlum undanfarið",
        "hverjir hafa verið áberandi í fjölmiðlum að undanförnu",
        "hverjir hafa verið áberandi í fjölmiðlum nýlega",
        "hverjir hafa verið áberandi í fjölmiðlum upp á síðkastið",
        "hverjir hafa verið mikið í fjölmiðlum",
        "hverjir hafa verið mikið í fjölmiðlum síðustu daga",
        "hverjir hafa verið mikið í fjölmiðlum undanfarið",
        "hverjir hafa verið mikið í fjölmiðlum að undanförnu",
        "hverjir hafa verið mikið í fjölmiðlum nýlega",
        "hverjir hafa verið mikið í fjölmiðlum upp á síðkastið",
    )
)


def _gen_num_people_answer(q: Query) -> bool:
    """Answer questions about person database."""
    with SessionContext(read_only=True) as session:
        qr = session.query(Person.name).distinct().count()

        # TODO: Use single_or_plural() here
        pl = is_plural(qr)
        verb = "eru" if pl else "er"
        indiv = "einstaklingar" if pl else "einstaklingur"
        count = qr or "engir"
        vcount = gssml(qr, type="number", gender="kk") or "engir"
        answer = f"Í gagnagrunni mínum {verb} {{count}} {indiv}."
        voice = answer.format(count=vcount)
        answer = answer.format(count=count)
        response = dict(answer=answer)

        q.set_expires(datetime.utcnow() + timedelta(hours=1))
        q.set_answer(response, answer, voice)
        q.set_key("NumPeople")
        q.set_qtype(_STATS_QTYPE)

    return True


_QUERIES_PERIOD = 30  # days


def _gen_num_queries_answer(q: Query) -> bool:
    """Answer questions concerning the number of queries handled."""
    with SessionContext(read_only=True) as session:
        qr = (
            session.query(QueryModel.id)
            .filter(
                QueryModel.timestamp
                >= datetime.utcnow() - timedelta(days=_QUERIES_PERIOD)
            )
            .count()
        )

        fs = "fyrirspurnum" if is_plural(qr) else "fyrirspurn"
        answer = f"Á síðustu {{ndays}} dögum hef ég svarað {{nfs}} {fs}."
        voice = answer.format(
            ndays=gssml(_QUERIES_PERIOD, type="number", case="þgf", gender="kk"),
            nfs=gssml(qr, type="number", case="þgf", gender="kvk"),
        )
        answer = answer.format(
            ndays=_QUERIES_PERIOD,
            nfs=iceformat_float(qr),
        )
        response = dict(answer=answer)

        q.set_key("NumQueries")
        q.set_answer(response, answer, voice)
        q.set_qtype(_STATS_QTYPE)

    return True


# TODO: Qtypes are too inconsistent between modules
_QTYPE_TO_DESC = {
    "Weather": "spurningum um veðrið",
    "WeatherForecast": "spurningum um veðrið",
    "WeatherCurrent": "spurningum um veðrið",
    "Arithmetic": "reiknidæmum",
    "Special": "sérstökum fyrirspurnum",
    "Opinion": "spurningum um skoðanir mínar",
    "Random": "beiðnum um tölur af handahófi",
    "Title": "spurningum um titla",
    "Person": "spurningum um einstaklinga",
    "Entity": "spurningum um fyrirbæri",
    "Flights": "spurningum um flugsamgöngur",
    "Geography": "spurningum um landafræði",
    "Location": "spurningum um staðsetningu",
    "Stats": "spurningum um tölfræði",
    "Telephone": "beiðnum um að hringja í símanúmer",
    "Date": "spurningum um dagsetningar",
    "FutureDate": "spurningum um dagsetningar",
    "Currency": "spurningum um gjaldmiðla",
    "Distance": "spurningum um fjarlægðir",
    "Counting": "beiðnum um að telja",
    "Television": "spurningum um sjónvarpsdagskrána",
    "TelevisionEvening": "spurningum um sjónvarpsdagskrána",
    "Unit": "spurningum um mælieiningar",
    "Wikipedia": "beiðnum um upplýsingar úr Wikipedíu",
    "Petrol": "fyrirspurnum um bensínstöðvar",
    "Spelling": "fyrirspurnum um stafsetningu",
    "Declension": "fyrirspurnum um beygingarmyndir",
    "Places": "spurningum um verslanir og opnunartíma",
    "News": "fyrirspurnum um fréttir",
    "Parrot": "beiðnum um að endurtaka setningar",
}


def _gen_most_freq_queries_answer(q: Query) -> bool:
    """Answer question concerning most frequent queries."""
    with SessionContext(read_only=True) as session:
        now = datetime.utcnow()
        start = now - timedelta(days=_QUERIES_PERIOD)
        end = now
        qr = list(
            QueryTypesQuery.period(start=start, end=end, enclosing_session=session)
        )

        if qr:
            top_qtype = qr[0][1]
            desc = _QTYPE_TO_DESC.get(top_qtype, "óskilgreindum fyrirspurnum")
            answer = f"Undanfarið hef ég mest svarað {desc}."
        else:
            answer = "Ég hef ekki svarað neinum fyrirspurnum upp á síðkastið."

        response = dict(answer=answer)
        voice = answer

        q.set_expires(now + timedelta(hours=1))
        q.set_answer(response, answer, voice)
        q.set_qtype(_STATS_QTYPE)
        q.set_key("FreqQuery")

    return True


_MOST_MENTIONED_COUNT = 3  # Individuals
_MOST_MENTIONED_PERIOD = 7  # Days


def _gen_most_mentioned_answer(q: Query) -> bool:
    """Answer questions about the most mentioned/talked about people in Icelandic news."""
    top = top_persons(limit=_MOST_MENTIONED_COUNT, days=_MOST_MENTIONED_PERIOD)

    q.set_qtype(_STATS_QTYPE)
    q.set_key("MostMentioned")

    if not top:
        # No people for the period, empty scraper db?
        q.set_answer(*gen_answer("Engar manneskjur fundust í gagnagrunni"))
    else:
        answer = natlang_seq([t["name"] for t in top if "name" in t])
        response = dict(answer=answer)
        voice = f"Umtöluðustu einstaklingar síðustu daga eru {answer}."
        q.set_expires(datetime.utcnow() + timedelta(hours=1))
        q.set_answer(response, answer, voice)

    return True


# Map hashable query category frozenset to corresponding handler function
_Q2HANDLER = {
    _NUM_PEOPLE_QUERIES: _gen_num_people_answer,
    _NUM_QUERIES: _gen_num_queries_answer,
    _MOST_FREQ_QUERIES: _gen_most_freq_queries_answer,
    _MOST_MENTIONED_PEOPLE_QUERIES: _gen_most_mentioned_answer,
}


def handle_plain_text(q: Query) -> bool:
    """Handle a plain text query about query statistics."""
    ql = q.query_lower.rstrip("?")

    for qset, handler in _Q2HANDLER.items():
        if ql in qset:
            return handler(q)

    return False
