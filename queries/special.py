"""

    Reynir: Natural language processing for Icelandic

    Frivolous query response module

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


    This module is an example of a plug-in query response module
    for the Greynir query subsystem. It handles plain text queries, i.e.
    ones that do not require parsing the query text. For this purpose
    it only needs to implement the handle_plain_text() function, as
    shown below.

"""

from datetime import datetime, timedelta
from inspect import isfunction
from random import choice


_SPECIAL_QTYPE = "Special"


_JOKES = (
    "Af hverju taka Hafnfirðingar alltaf stiga út í búð? Því verðið er svo hátt.",
    "Af hverju búa Hafnfirðingar í kringlóttum húsum? Svo enginn mígi í hornin.",
    "Af hverju eru Hafnfirðingar alltaf með stól úti á svölum? Svo sólin geti sest.",
    "Af hverju læðast Hafnfirðingar alltaf fram hjá apótekum? Til að vekja ekki svefnpillurnar.",
    "Af hverju fara Hafnfirðingar alltaf niður í fjöru um jólin? Til þess að bíða eftir jólabókaflóðinu.",
)


def _random_joke():
    return { "answer": choice(_JOKES) }


def _capabilities():
    return { "answer": "Þú getur meðal annars spurt mig um veðrið." }


_SPECIAL_QUERIES = {
    "er þetta spurning": {
        "answer": "Er þetta svar?"
    },
    "er þetta svar": {
        "answer": "Er þetta spurning?"
    },
    "hvað er svarið": {
        "answer": "42.",
        "voice": "Fjörutíu og tveir."
    },
    "hvert er svarið": {
        "answer": "42.",
        "voice": "Fjörutíu og tveir."
    },
    "veistu allt": {
        "answer": "Nei, því miður."
    },
    "hvað veistu": {
        "answer": "Spurðu mig!"
    },
    "veistu svarið": {
        "answer": "Spurðu mig!"
    },
    "hvað heitir þú": {
        "answer": "Greynir. Ég er grey sem reynir að greina íslensku.",
        "voice": "Ég heiti Greynir. Ég er grey sem reynir að greina íslensku."
    },
    "hver ert þú": {
        "answer": "Ég er grey sem reynir að greina íslensku."
    },
    "hver bjó þig til": {
        "answer": "Flotta teymið hjá Miðeind.",
    },
    "hver skapaði þig": {
        "answer": "Flotta teymið hjá Miðeind."
    },
    "hver er skapari þinn": {
        "answer": "Flotta teymið hjá Miðeind."
    },
    "hver er flottastur": {
        "answer": "Teymið hjá Miðeind."
    },
    "hver er sætastur": {
        "answer": "Tumi Þorsteinsson.",
        "voice": "Tumi Þorsteinsson er langsætastur."
    },
    "hver er langsætastur": {
        "answer": "Tumi Þorsteinsson.",
        "voice": "Tumi Þorsteinsson er langsætastur."
    },
    "hver er lang sætastur": {
        "answer": "Tumi Þorsteinsson.",
        "voice": "Tumi Þorsteinsson er langsætastur."
    },
    "hver er ég": {
        "answer": "Þú ert þú."
    },
    "hvað er ég": {
        "answer": "Þú ert væntanlega manneskja sem talar íslensku."
    },
    "er guð til": {
        "answer": "Ég held ekki."
    },
    "hver skapaði guð": {
        "answer": "Enginn sem ég þekki."
    },
    "hver skapaði heiminn": {
        "answer": "Enginn sem ég þekki."
    },
    "hver er tilgangur lífsins": {
        "answer": "42.",
        "voice": "Fjörutíu og tveir."
    },
    "hvar endar alheimurinn": {
        "answer": "Inni í þér."
    },
    "hvar er draumurinn": {
        "answer": "Hvar ertu, lífið sem ég þrái?"
    },

    "hvað get ég spurt þig um": _capabilities,
    "hvað er hægt að spyrja um": _capabilities,
    "hvað er hægt að spyrja þig um": _capabilities,
    "hvaða spurningar skilur þú": _capabilities,
    "hvers konar spurningar skilur þú": _capabilities,

    "ertu með kímnigáfu": {
        "answer": "Afar takmarkaða.",
        "voice": "Já, en afar takmarkaða",
    },
    "segðu mér brandara": _random_joke,
    "segðu brandara": _random_joke,
    "komdu með brandara": _random_joke,
}


def handle_plain_text(q):
    """ Handle a plain text query, contained in the q parameter
        which is an instance of the query.Query class.
        Returns True if the query was handled, and in that case
        the appropriate properties on the Query instance have
        been set, such as the answer and the query type (qtype).
        If the query is not recognized, returns False. """
    ql = q.query_lower.rstrip('?')

    if ql in _SPECIAL_QUERIES:
        # This is a query we recognize and handle
        q.set_qtype(_SPECIAL_QTYPE)
        r = _SPECIAL_QUERIES[ql]
        fixed = not isfunction(r)
        response = r if fixed else r()

        # A non-voice answer is usually a dict or a list
        answer = response.get("answer")
        # A voice answer is always a plain string
        voice = response.get("voice") or answer
        q.set_answer(dict(answer=answer), answer, voice)

        # Caching
        now = datetime.utcnow()
        exp = now + timedelta(minutes=10) if fixed else now
        q.set_expires(exp)

        return True

    return False
