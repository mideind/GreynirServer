"""

    Reynir: Natural language processing for Icelandic

    Stats query response module

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


    This module handles queries related to statistics about the query mechanism.

"""


from datetime import datetime, timedelta

from db import SessionContext
from db.models import Person, Query
from db.queries import QueryTypesQuery

from queries import gen_answer

_STATS_QTYPE = "Stats"


_NUM_PEOPLE_Q = (
    "hvað þekkirðu margar manneskjur",
    "hvað þekkir þú margar manneskjur",
    "hvað þekkirðu mikið af fólki",
    "hvað þekkir þú mikið af fólki",
    "hversu marga einstaklinga þekkirðu",
    "hversu marga einstaklinga þekkir þú",
)


_NUM_QUERIES_Q = (
    "hvað hefurðu fengið margar fyrirspurnir",
    "hvað hefur þú fengið margar fyrirspurnir",
    "hvað hefurðu fengið margar spurningar",
    "hvað hefur þú fengið margar spurningar",
    "hvað hefurðu svarað mörgum spurningum",
    "hvað hefur þú svarað mörgum spurningum",
    "hversu mörgum fyrirspurnum hefurðu svarað",
    "hversu mörgum fyrirspurnum hefur þú svarað",
    "hversu mörgum spurningum hefurðu svarað",
    "hversu mörgum spurningum hefur þú svarað",
)


_MOST_FREQ_QUERIES_Q = (
    "hvað er fólk að spyrja þig mest um",
    "hvað er fólk að spyrja mest um",
    "hvað spyr fólk mest um",
    "hvað spyr fólk þig mest um",
    "hvað ertu mest spurð um",
    "hvað ert þú mest spurð um",
    "hvað spyr fólk þig aðallega um",
    "hvaða fyrirspurnir eru algengastar",
    "hvaða spurningar eru algengastar",
    "hvers konar spurningar eru algengastar",
    "hvernig spurningar færðu mest af",
    "hvernig spurningar færð þú mest af",
)


def _gen_num_people_answer(q):
    with SessionContext(read_only=True) as session:
        qr = session.query(Person.id).count()

        answer = "Í gagnagrunni mínum eru {0} einstaklingar.".format(qr or "engir")
        voice = answer
        response = dict(answer=answer)

        q.set_answer(response, answer, voice)
        q.set_qtype(_STATS_QTYPE)


_QUERIES_PERIOD = 30  # days


def _gen_num_queries_answer(q):
    with SessionContext(read_only=True) as session:
        qr = (
            session.query(Query.id)
            .filter(
                Query.timestamp >= datetime.utcnow() - timedelta(days=_QUERIES_PERIOD)
            )
            .count()
        )

        answer = "Á síðustu {0} dögum hef ég svarað {1} fyrirspurnum.".format(
            _QUERIES_PERIOD, qr or "engum"
        )
        voice = answer
        response = dict(answer=answer)

        q.set_answer(response, answer, voice)
        q.set_qtype(_STATS_QTYPE)


_QTYPE_TO_DESC = {
    "Weather": "spurningum um veðrið",
    "Arithmetic": "reiknidæmum",
    "Special": "sérstökum fyrirspurnum",
    "Opinion": "spurningum um skoðanir mínar",
    "Random": "beiðnum um tölur af handahófi",
    "Title": "spurningum um einstaklinga",
    "Geography": "spurningum um landafræði",
    "Location": "spurningum um staðsetningu",
    "Stats": "spurningum um tölfræði",
    "Telephone": "beiðnum um að hringja í símanúmer",
    "Date": "spurningum um dagsetningar",
    "Currency": "spurningum um gjaldmiðla",
    "Wikipedia": "beiðnum um upplýsingar úr Wikipedíu",
}


def _gen_most_freq_queries_answer(q):
    with SessionContext(read_only=True) as session:
        start = datetime.utcnow() - timedelta(days=_QUERIES_PERIOD)
        end = datetime.utcnow()
        qr = QueryTypesQuery.period(start=start, end=end, enclosing_session=session)

        if qr:
            top_qtype = qr[0][1]
            desc = _QTYPE_TO_DESC.get(top_qtype) or "óskilgreindum fyrirspurnum"
            answer = "Undanfarið hef ég mest svarað {0}.".format(desc)
        else:
            answer = "Ég hef ekki svarað neinum fyrirspurnum upp á síðkastið."

        response = dict(answer=answer)
        voice = answer
        q.set_answer(response, answer, voice)
        q.set_qtype(_STATS_QTYPE)


def handle_plain_text(q):
    """ Handle a plain text query about query statistics. """
    ql = q.query_lower.rstrip("?")

    if ql in _NUM_PEOPLE_Q:
        _gen_num_people_answer(q)
        return True

    if ql in _NUM_QUERIES_Q:
        _gen_num_queries_answer(q)
        return True

    if ql in _MOST_FREQ_QUERIES_Q:
        _gen_most_freq_queries_answer(q)
        return True

    return False
