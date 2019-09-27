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


# Additions welcome :)
_JOKES = (
    "Af hverju taka Hafnfirðingar alltaf stiga út í búð? Því verðið er svo hátt.",
    "Af hverju búa Hafnfirðingar í kringlóttum húsum? Svo enginn mígi í hornin.",
    "Af hverju eru Hafnfirðingar alltaf með stól úti á svölum? Svo sólin geti sest.",
    "Af hverju læðast Hafnfirðingar alltaf fram hjá apótekum? Til að vekja ekki svefnpillurnar.",
    "Af hverju fara Hafnfirðingar alltaf niður í fjöru um jólin? Til þess að bíða eftir jólabókaflóðinu.",
)


def _random_joke(qs, q):
    return { "answer": choice(_JOKES) }


# TODO: Extend this list as the range of queries is expanded
_CAP = (
    "Þú getur til dæmis spurt mig um veðrið.",
    "Þú getur til dæmis spurt mig um höfuðborgir.",
    "Þú getur til dæmis spurt mig um tíma og dagsetningu.",
    "Þú getur til dæmis spurt mig um strætósamgöngur.",
    "Þú getur til dæmis spurt mig um fjarlægðir.",
    "Þú getur til dæmis spurt mig um gengi gjaldmiðla.",
    "Þú getur til dæmis beðið mig um að kasta teningi",
    "Þú getur til dæmis spurt mig um fólk sem hefur komið fram í fjölmiðlum.",
)


def _capabilities(qs, q):
    return { "answer": choice(_CAP) }


def _identity(qs, q):
    return { "answer": "Ég heiti Embla og ég skil íslensku." }

_THANKS = (
    "Það var nú lítið",
    "Mín var ánægjan", 
    "Verði þér að góðu",
)

def _thanks(qs, q):
    return { "answer": choice(_THANKS) }

_RUDE = (
    "Þetta var ekki fallega sagt.",
    "Ekki vera með dónaskap.",
    "Ég verðskulda betri framkomu en þetta",
    "Það er alveg óþarfi að vera með leiðindi",
    "Svona munnsöfnuður er alveg óþarfi",
    "Kenndi mamma þín þér svona munnsöfnuð?",
    "Ekki vera með leiðindi",
    "Það er aldeilis sorakjaftur á þér",
    "Æi, ekki vera með leiðindi",
)

def _rudeness(qs, q):
    return { "answer": choice(_RUDE) }


def _open_url(qs, q):
    q.set_url("https://sveinbjorn.org")
    return { "answer": "Skal gert!" }

_MEANING_OF_LIFE = {
    "answer": "42.",
    "voice": "Fjörutíu og tveir."
}


_SPECIAL_QUERIES = {
    "er þetta spurning": {
        "answer": "Er þetta svar?"
    },
    "er þetta svar": {
        "answer": "Er þetta spurning?"
    },
    "veistu allt": {
        "answer": "Nei, því miður. En ég veit ýmislegt."
    },
    "hvað veistu": {
        "answer": "Spurðu mig!"
    },
    "veistu svarið": {
        "answer": "Spurðu mig!"
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
    "hvað er miðeind": {
        "answer": "Miðeind er máltæknifyrirtækið sem skapaði mig."
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
        "answer": "Þú ert væntanlega manneskja sem talar íslensku."
    },
    "hvað er ég": {
        "answer": "Þú ert væntanlega manneskja sem talar íslensku."
    },
    "er guð til": {
        "answer": "Það held ég ekki."
    },
    "hver skapaði guð": {
        "answer": "Enginn sem ég þekki."
    },
    "hver skapaði heiminn": {
        "answer": "Enginn sem ég þekki."
    },
    "hvar endar alheimurinn": {
        "answer": "Inni í þér."
    },
    "hvar er draumurinn": {
        "answer": "Hvar ertu lífið sem ég þrái?"
    },
    "af hverju er ég hérna": {
        "answer": "Það er góð spurning."
    },
    "viltu giftast mér": {
        "answer": "Nei, því miður. Ég er gift vinnunni."
    },
    "þetta var ekki rétt hjá þér": {
        "answer": "Það þykir mér leitt að heyra."
    },

    # Thanks
    "takk fyrir": _thanks,
    "takk kærlega": _thanks,
    "þakka þér fyrir": _thanks,
    "þakka þér kærlega": _thanks,
    "takk fyrir mig": _thanks,
    "takk fyrir hjálpina": _thanks,

    # Philosophy
    "hvað er svarið": _MEANING_OF_LIFE,
    "hvert er svarið": _MEANING_OF_LIFE,
    "hver er tilgangur lífsins": _MEANING_OF_LIFE,
    "hver er tilgangurinn með þessu öllu": _MEANING_OF_LIFE,

    # Identity
    "hvað heitir þú": _identity,
    "hvað heitirðu": _identity,
    "hver ert þú": _identity,
    "hver ertu": _identity,
    "hver er embla": _identity,
    "hvað er embla": _identity,

    # Capabilities
    "hvað get ég spurt þig um": _capabilities,
    "hvað get ég spurt um": _capabilities,
    "hvað get ég spurt": _capabilities,
    "hvað er hægt að spyrja um": _capabilities,
    "hvað er hægt að spyrja þig um": _capabilities,
    "hvað annað get ég spurt um": _capabilities,
    "hvað annað get ég spurt þig um": _capabilities,
    "hvað annað gæti ég spurt þig um": _capabilities,
    "hvað annað gæti ég spurt um": _capabilities,
    "hvað annað er hægt að spyrja um": _capabilities,
    "hvað getur þú sagt mér": _capabilities,
    "hvað geturðu sagt mér": _capabilities,

    "hvaða spurningar skilur þú": _capabilities,
    "hvaða spurningar skilurðu": _capabilities,

    "hvers konar spurningar skilur þú": _capabilities,
    "hvers konar spurningar skilurðu": _capabilities,
    "hvers konar spurningum geturðu svarað": _capabilities,
    "hvers konar spurningum getur þú svarað": _capabilities,

    "hvers konar fyrirspurnir skilur þú": _capabilities,
    "hvers konar fyrirspurnir skilurðu": _capabilities,
    "hvers konar fyrirspurnum getur þú svarað": _capabilities,
    "hvers konar fyrirspurnum geturðu svarað": _capabilities,

    # Jokes
    "ertu með kímnigáfu": {
        "answer": "Afar takmarkaða.",
        "voice": "Já, en afar takmarkaða",
    },
    "segðu brandara": _random_joke,
    "segðu mér brandara": _random_joke,
    "segðu mér annan brandara": _random_joke,
    "segðu brandara": _random_joke,
    "segðu annan brandara": _random_joke,
    "komdu með brandara": _random_joke,
    "komdu með annan brandara": _random_joke,
    "segðu eitthvað fyndið": _random_joke,
    "segðu mér eitthvað fyndið": _random_joke,
    "segðu eitthvað skemmtilegt": _random_joke,
    "segðu mér eitthvað skemmtilegt": _random_joke,
    "vertu skemmtileg": _random_joke,
    "kanntu einhverja brandara": _random_joke,
    "kanntu brandara": _random_joke,

    "opnaðu vefsíðu sveinbjarnar": _open_url,

    # Rudeness :)
    "fokk jú": _rudeness,
    "fokkaðu þér": _rudeness,
    "éttu skít": _rudeness,
    "haltu kjafti": _rudeness,
    "éttu það sem úti frýs": _rudeness,
    "farðu til helvítis": _rudeness,
    "farðu í rass og rófu": _rudeness,
    "hoppaðu upp í rassgatið á þér":  _rudeness,

    # Emotional enquiries
    "ertu í góðu skapi": {
        "answer": "Já, ég er alltaf eldhress.",
    },
    "ert þú í góðu skapi": {
        "answer": "Já, ég er alltaf eldhress.",
    }
}


def handle_plain_text(q):
    """ Handle a plain text query, contained in the q parameter
        which is an instance of the query.Query class.
        Returns True if the query was handled, and in that case
        the appropriate properties on the Query instance have
        been set, such as the answer and the query type (qtype).
        If the query is not recognized, returns False. """
    ql = q.query_lower.rstrip('?')

    if ql not in _SPECIAL_QUERIES:
        return False

    # OK, this is a query we recognize and handle
    q.set_qtype(_SPECIAL_QTYPE)

    r = _SPECIAL_QUERIES[ql]
    fixed = not isfunction(r)
    response = r if fixed else r(ql, q)

    # A non-voice answer is usually a dict or a list
    answer = response.get("answer")
    # A voice answer is always a plain string
    voice = response.get("voice") or answer
    q.set_answer(dict(answer=answer), answer, voice)

    # Caching for non-dynamic answers
    if not fixed:
        q.set_expires(datetime.utcnow() + timedelta(hours=24))

    return True

