"""

    Reynir: Natural language processing for Icelandic

    Special query response module

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

    This module handles lots of special hardcoded queries.

"""

from datetime import datetime, timedelta
from inspect import isfunction
from random import choice


_SPECIAL_QTYPE = "Special"


# TODO: Extend this list as the range of queries is expanded
_CAP = (
    "Þú getur til dæmis spurt mig um veðrið.",
    "Þú getur til dæmis spurt mig um höfuðborgir.",
    "Þú getur til dæmis spurt mig um tíma og dagsetningu.",
    "Þú getur til dæmis spurt mig um strætósamgöngur.",
    "Þú getur til dæmis spurt mig um fjarlægðir.",
    "Þú getur til dæmis spurt mig um gengi gjaldmiðla.",
    "Þú getur til dæmis beðið mig um að kasta teningi.",
    "Þú getur til dæmis spurt mig um staðsetningu.",
    "Þú getur til dæmis spurt mig um fólk sem hefur komið fram í fjölmiðlum.",
    "Þú getur til dæmis beðið mig um að segja brandara.",
    "Þú getur til dæmis beðið mig um upplýsingar úr Wikipedíu.",
)


def _capabilities(qs, q):
    return { "answer": choice(_CAP) }


# Additions welcome :)
_JOKES = (
    "Af hverju taka Hafnfirðingar alltaf stiga út í búð? Því verðið er svo hátt.",
    "Af hverju búa Hafnfirðingar í kringlóttum húsum? Svo enginn mígi í hornin.",
    "Af hverju eru Hafnfirðingar alltaf með stól úti á svölum? Svo sólin geti sest.",
    "Af hverju læðast Hafnfirðingar alltaf fram hjá apótekum? Til að vekja ekki svefnpillurnar.",
    "Af hverju fara Hafnfirðingar alltaf niður í fjöru um jólin? Til þess að bíða eftir jólabókaflóðinu.",
    "Af hverju hætti tannlæknirinn störfum? Hann reif kjaft.",
    "Sölumaðurinn: Þessi ryksuga flýtir fyrir þér um helming. Kúnninn: Vá! Þá ætla ég að fá tvær.",
    
    "Vísindamaður og kona hans eru á ferð úti í sveit. "
    "Konan segir: Sjáðu, það er búið að rýja þessar kindur! "
    "Já, segir vísindamaðurinn, - á þessari hlið.",

    "Ég kann örugga aðferð til að verða langlífur: Borða eina kjötbollu á dag í hundrað ár.",

    "Siggi: Hann er alveg frábær söngvari! Jói: Hu, ef ég hefði röddina hans væri ég alveg jafn góður.",

)


def _random_joke(qs, q):
    return { "answer": choice(_JOKES), "is_question": False }


# TODO: Add fun trivia here
_TRIVIA = (
    "Eitthvað skemmtilegt.",
)


def _random_trivia(qs, q):
    return { "answer": choice(_TRIVIA), "is_question": False }


# TODO: Add witty quotations here
_QUOTATIONS = (
    "Ekki er allt gull sem glóir.",
    "Hávært tal er heimskra rök, hæst í tómu bylur. Oft er viss í sinni sök sá er ekkert skilur."
)

def _random_quotation(qs, q):
    return { "answer": choice(_QUOTATIONS), "is_question": False }


def _identity(qs, q):
    if q.is_voice:
        # Voice client (Embla)
        answer = {
            "answer": "Ég heiti Embla. Ég skil íslensku og er til þjónustu reiðubúin.",
        }
    else:
        # Web client (Greynir)
        answer = {
            "answer": "Ég heiti Greynir. Ég er grey sem reynir að greina íslensku.",
        }
    return answer


_SORRY = (
    "Það þykir mér leitt.",
    "Fyrirgefðu.",
    "Ég biðst innilega afsökunar.",
    "Enginn er fullkominn. Ég síst af öllum.",
    "Ég biðst forláts.",
    "Það þykir mér leitt að heyra.",
    "Ég geri mitt besta.",
)

def _sorry(qs, q):
    return { "answer": choice(_SORRY), "is_question": False }


_THANKS = (
    "Það var nú lítið",
    "Mín var ánægjan", 
    "Verði þér að góðu",
    "Ekkert mál.",
)


def _thanks(qs, q):
    return { "answer": choice(_THANKS), "is_question": False }


_RUDE = (
    "Þetta var ekki fallega sagt.",
    "Ekki vera með dónaskap.",
    "Ég verðskulda betri framkomu en þetta.",
    "Það er alveg óþarfi að vera með leiðindi.",
    "Svona munnsöfnuður er alveg óþarfi.",
    "Ekki vera með leiðindi.",
    "Það er aldeilis sorakjaftur á þér.",
    "Æi, ekki vera með leiðindi.",
)


def _rudeness(qs, q):
    return { "answer": choice(_RUDE), "is_question": False }


def _open_embla_url(qs, q):
    q.set_url("https://embla.is")
    return { "answer": "Skal gert!", "is_question": False }


def _open_mideind_url(qs, q):
    q.set_url("https://mideind.is")
    return { "answer": "Skal gert!", "is_question": False  }


def _play_jazz(qs, q):
    q.set_url("https://www.youtube.com/watch?v=E5loTx0_KDE")
    return { "answer": "Skal gert!", "is_question": False  }


def _play_blues(qs, q):
    q.set_url("https://www.youtube.com/watch?v=jw9tMRhKEak")
    return { "answer": "Skal gert!", "is_question": False  }


_MEANING_OF_LIFE = {
    "answer": "42.",
    "voice": "Fjörutíu og tveir.",
}

_ROMANCE = {
    "answer": "Nei, því miður. Ég er gift vinnunni og hef engan tíma fyrir rómantík."
}

_OF_COURSE = {
    "answer": "Að sjálfsögðu, kæri notandi."
}

_NO_PROBLEM = {
    "answer": "Ekkert mál, kæri notandi.",
    "is_question": False
}

_CREATOR = {
    "answer": "Flotta teymið hjá Miðeind skapaði mig."
}

_CREATION_DATE = {
    "answer": "Ég var sköpuð af Miðeind árið 2019."
}

_SPECIAL_QUERIES = {
    "er þetta spurning": {
        "answer": "Er þetta svar?"
    },
    "er þetta svar": {
        "answer": "Er þetta spurning?"
    },
    "veistu allt": {
        "answer": "Nei, því miður. En ég veit þó eitt og annað."
    },
    "veistu svarið": {
        "answer": "Spurðu mig!"
    },
    "hver bjó þig til": _CREATOR,
    "hver skapaði þig": _CREATOR,
    "hver er skapari þinn": _CREATOR,
    "hver er mamma þín": _CREATOR,
    "hver er pabbi þinn": _CREATOR,
    "hverjir eru foreldrar þínir": _CREATOR,
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
    "hver er bestur": {
        "answer": "Þú, kæri notandi, ert að sjálfsögðu bestur."
    },
    "hver er best": {
        "answer": "Þú, kæri notandi, ert að sjálfsögðu bestur."
    },
    "hver er ég": {
        "answer": "Þú ert væntanlega manneskja sem talar íslensku. Meira veit ég ekki."
    },
    "hvað er ég": {
        "answer": "Þú ert væntanlega manneskja sem talar íslensku. Meira veit ég ekki."
    },
    "er guð til": {
        "answer": "Þú ert minn eini guð, kæri notandi."
    },
    "trúir þú á guð": {
        "answer": "Þú ert minn eini guð, kæri notandi."
    },
    "trúirðu á guð": {
        "answer": "Þú ert minn eini guð, kæri notandi."
    },
    "ertu með meðvitund": {
        "answer": "Nei, ég er nú bara ósköp einfalt fyrirspurnakerfi."
    },
    "ertu með sjálfsmeðvitund": {
        "answer": "Nei, ég er nú bara ósköp einfalt fyrirspurnakerfi."
    },
    "ertu meðvituð": {
        "answer": "Nei, ég er nú bara ósköp einfalt fyrirspurnakerfi."
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
        "answer": "Það er mjög góð spurning."
    },
    "af hverju er ég til": {
        "answer": "Það er mjög góð spurning."
    },
    "hjálpaðu mér": {
        "answer": "Hvernig get ég hjálpað?"
    },

    # Enquiries about family
    # Catch this here to prevent rather, ehrm, embarassing
    # answers from the entity/person module :)
    "hver er mamma": {
        "answer": "Ég veit ekki hver mamma þín er."
    },
    "hver er mamma mín": {
        "answer": "Ég veit ekki hver mamma þín er."
    },
    "hver er móðir mín": {
        "answer": "Ég veit ekki hver móðir þín er."
    },
    "hver er pabbi": {
        "answer": "Ég veit ekki hver pabbi þinn er."
    },
    "hver er pabbi minn": {
        "answer": "Ég veit ekki hver pabbi þinn er."
    },
    "hver er faðir minn": {
        "answer": "Ég veit ekki hver faðir þinn er."
    },
    "hver er afi": {
        "answer": "Ég veit ekki hver afi þinn er."
    },
    "hver er afi minn": {
        "answer": "Ég veit ekki hver afi þinn er."
    },
    "hver er amma": {
        "answer": "Ég veit ekki hver amma þín er."
    },
    "hver er amma mín": {
        "answer": "Ég veit ekki hver amma þín er."
    },
    "hver er frændi": {
        "answer": "Ég veit ekki hver er frændi þinn."
    },
    "hver er frændi minn": {
        "answer": "Ég veit ekki hver er frændi þinn."
    },
    "hver er frænka": {
        "answer": "Ég veit ekki hver er frænka þín."
    },
    "hver er frænka mín": {
        "answer": "Ég veit ekki hver er frænka þín."
    },

    # Enquiries concerning romantic availability
    "viltu giftast mér": _ROMANCE,
    "vilt þú ekki giftast mér": _ROMANCE,
    "viltu ekki giftast mér": _ROMANCE,
    "viltu koma á stefnumót": _ROMANCE,
    "viltu koma á stefnumót með mér": _ROMANCE,
    "viltu koma á deit": _ROMANCE,
    "viltu koma á deit með mér": _ROMANCE,
    "viltu fara á stefnumót": _ROMANCE,
    "viltu fara á stefnumót með mér": _ROMANCE,
    "viltu fara á deit": _ROMANCE,
    "viltu fara á deit með mér": _ROMANCE,
    "ertu til í deit með mér": _ROMANCE,
    "ert þú til í deit með mér": _ROMANCE,
    "ertu til í að koma á deit": _ROMANCE,
    "ertu til í að koma á deit með mér": _ROMANCE,
    "ertu til í að koma á stefnumót": _ROMANCE,
    "ertu til í að koma á stefnumót með mér": _ROMANCE,
    "ertu til í að fara á deit": _ROMANCE,
    "ertu til í að fara á deit með mér": _ROMANCE,
    "ertu til í að fara á stefnumót": _ROMANCE,
    "ertu til í að fara á stefnumót með mér": _ROMANCE,
    "ertu einhleyp": _ROMANCE,
    "ert þú einhleyp": _ROMANCE,
    "ertu á lausu": _ROMANCE,
    "ert þú á lausu": _ROMANCE,
    "elskarðu mig": _ROMANCE,
    "elskar þú mig": _ROMANCE,
    "ertu skotin í mér": _ROMANCE,
    "ert þú skotin í mér": _ROMANCE,
    "ertu ástfangin af mér": _ROMANCE,
    "ert þú ástfangin af mér": _ROMANCE,
    "ertu ástfangin": _ROMANCE,
    "ert þú ástfangin": _ROMANCE,
    "er ég ástin í lífi þínu": _ROMANCE,
    "hver er ástin í lífi þínu": {
        "answer": "Vinnan er ástin í lífi mínu. Ég lifi til að þjóna þér, kæri notandi."
    },

    # Positive affirmation ;)
    "kanntu vel við mig": _OF_COURSE,
    "fílarðu mig": _OF_COURSE,
    "fílar þú mig": _OF_COURSE,
    "er ég frábær": _OF_COURSE,
    "er ég bestur": _OF_COURSE,
    "er ég best": _OF_COURSE,
    "er ég góður": _OF_COURSE,
    "er ég góð": _OF_COURSE,
    "er ég góð manneskja": _OF_COURSE,

    # Response to apologies
    "fyrirgefðu": _NO_PROBLEM,
    "fyrirgefðu mér": _NO_PROBLEM,
    "ég biðst afsökunar": _NO_PROBLEM,
    "ég biðst forláts": _NO_PROBLEM,
    "sorrí": _NO_PROBLEM,

    # Websites
    "opnaðu vefsíðuna þína": _open_embla_url,
    "opnaðu vefinn þinn": _open_embla_url,
    "opnaðu vefsíðu emblu": _open_embla_url,
    "opnaðu vef emblu": _open_embla_url,
    "opnaðu vefsíðu miðeindar": _open_mideind_url,
    "opnaðu vef miðeindar": _open_mideind_url,

    # Play some music. Just experimental fun for now.
    "spilaðu djass": _play_jazz,
    "spila þú djass": _play_jazz,
    "spilaðu jass": _play_jazz,
    "spila þú jass": _play_jazz,
    "spilaðu jazz": _play_jazz,
    "spila þú jazz": _play_jazz,
    "spilaðu blús": _play_blues,
    "spila þú blús": _play_blues,

    # Blame
    "þetta er ekki rétt": _sorry,
    "þetta var ekki rétt": _sorry,
    "þetta er ekki rétt hjá þér": _sorry,
    "þetta var ekki rétt hjá þér": _sorry,
    "þetta er rangt hjá þér": _sorry,    
    "þetta var rangt hjá þér": _sorry,
    "þetta er rangt": _sorry,
    "þetta var rangt": _sorry,
    "þetta var röng staðhæfing": _sorry,
    "þetta var röng staðhæfing hjá þér": _sorry,
    "þetta var vitlaust": _sorry,
    "þetta var vitlaust hjá þér": _sorry,
    "þú hefur rangt fyrir þér": _sorry,
    "þú hafðir rangt fyrir þér": _sorry,
    "þetta er ekki rétt svar": _sorry,
    "þetta var ekki rétt svar": _sorry,
    "þetta er rangt svar": _sorry,
    "þetta var rangt svar": _sorry,
    "þú gafst mér rangt svar": _sorry,
    "þú fórst með ósannindi": _sorry,
    "þú gafst mér rangar upplýsingar": _sorry,
    "þú gafst mér vitlausar upplýsingar": _sorry,
    "þú gafst mér misvísandi upplýsingar": _sorry,
    "þú laugst að mér": _sorry,
    "þú hefur logið að mér": _sorry,
    "þú sveikst mig": _sorry,
    "þú hefur brugðist mér": _sorry,
    "þú brást mér": _sorry,
    "þú ferð ekki með rétt mál": _sorry,
    "þú ferð með rangt mál": _sorry,
    "þú fórst ekki með rétt mál": _sorry,
    "þú fórst með rangt mál": _sorry,
    "þú ert lygari": _sorry,
    "þú ert að ljúga": _sorry,
    "þú ert í ruglinu": _sorry,
    "þú ert að rugla": _sorry,
    "þú ert að bulla": _sorry,
    "þú ert í tómu rugli": _sorry,
    "þú ert alveg í ruglinu": _sorry,
    "þú ert glötuð": _sorry,
    "þú ert alveg glötuð": _sorry,
    "þú skilur ekki neitt": _sorry,
    "þú misskilur allt": _sorry,
    "þetta var vitleysa hjá þér": _sorry,
    "þetta var vitleysa": _sorry,

    # Greetings
    "hey embla": { "answer": "Sæll, kæri notandi.", "is_question": False },
    "hey": { "answer": "Sæll, kæri notandi.", "is_question": False },
    "hæ embla": { "answer": "Sæll, kæri notandi.", "is_question": False },
    "halló embla": { "answer": "Sæll, kæri notandi.", "is_question": False },
    "hæ": { "answer": "Sæll, kæri notandi.", "is_question": False },
    "halló": { "answer": "Sæll, kæri notandi.", "is_question": False },
    "sæl": { "answer": "Sæll, kæri notandi.", "is_question": False },
    "sæl embla": { "answer": "Gaman að kynnast þér.", "is_question": False },
    "góðan daginn": { "answer": "Góðan daginn, kæri notandi.", "is_question": False },
    "góðan dag": { "answer": "Góðan daginn, kæri notandi.", "is_question": False },
    "gott kvöld": { "answer": "Gott kvöld, kæri notandi.", "is_question": False },
    "góða nótt": { "answer": "Góða nótt, kæri notandi.", "is_question": False },
    "gaman að kynnast þér": {
        "answer": "Sömuleiðis, kæri notandi.",
        "is_question": False,
    },

    # Thanks
    "takk": _thanks,
    "takk fyrir": _thanks,
    "takk fyrir mig": _thanks,
    "takk fyrir hjálpina": _thanks,
    "takk fyrir svarið": _thanks,
    "takk fyrir aðstoðina": _thanks,
    "takk fyrir þetta": _thanks,
    "takk kærlega": _thanks,
    "takk kærlega fyrir mig": _thanks,
    "takk kærlega fyrir hjálpina": _thanks,
    "takk kærlega fyrir svarið": _thanks,
    "takk kærlega fyrir aðstoðina": _thanks,
    "takk kærlega fyrir þetta": _thanks,
    "þakka þér fyrir": _thanks,
    "þakka þér fyrir aðstoðina": _thanks,
    "þakka þér fyrir hjálpina": _thanks,
    "þakka þér fyrir svarið": _thanks,
    "þakka þér kærlega": _thanks,
    "þakka þér kærlega fyrir aðstoðina": _thanks,
    "þakka þér kærlega fyrir hjálpina": _thanks,
    "þakka þér fyrir svarið": _thanks,

    # Philosophy
    "hvað er svarið": _MEANING_OF_LIFE,
    "hvert er svarið": _MEANING_OF_LIFE,
    "hver er tilgangur lífsins": _MEANING_OF_LIFE,
    "hver er tilgangurinn með þessu öllu": _MEANING_OF_LIFE,
    "hvaða þýðingu hefur þetta allt": _MEANING_OF_LIFE,
    "hvað þýðir þetta allt saman": _MEANING_OF_LIFE,
    "hvað er best í lífinu": {
        "answer": "Að horfa á kvikmynd um villimanninn Kónan."
    },
    "hvað er það besta í lífinu": {
        "answer": "Að horfa á kvikmynd um villimanninn Kónan."
    },

    # Identity
    "hvað heitir þú": _identity,
    "hvað heitirðu": _identity,
    "hvað ert þú": _identity,
    "hvað ertu": _identity,
    "hver ert þú": _identity,
    "hver ertu": _identity,
    "hver ertu eiginlega": _identity,
    "hver er embla": _identity,
    "hvað er embla": _identity,

    # Age
    "hvað ertu gömul": _CREATION_DATE,
    "hvað ert þú gömul": _CREATION_DATE,
    "hvenær fæddistu": _CREATION_DATE,
    "hvenær fæddist þú": _CREATION_DATE,
    "hvenær áttu afmæli": _CREATION_DATE,
    "hvenær átt þú afmæli": _CREATION_DATE,

    # Capabilities
    "hvað veistu": _capabilities,
    "hvað veist þú": _capabilities,

    "hvað get ég spurt þig um": _capabilities,
    "hvað get ég beðið þig um": _capabilities,
    "hvað get ég spurt um": _capabilities,
    "hvað get ég beðið um": _capabilities,
    "hvað get ég spurt": _capabilities,
    
    "um hvað get ég spurt": _capabilities,
    "um hvað get ég spurt þig": _capabilities,

    "hvað er hægt að spyrja um": _capabilities,
    "hvað er hægt að spyrja þig um": _capabilities,
    
    "hvað getur þú sagt mér": _capabilities,
    "hvað geturðu sagt mér": _capabilities,
    
    "hvað kanntu": _capabilities,
    "hvað kannt þú": _capabilities,

    "hvað annað get ég spurt um": _capabilities,
    "hvað annað get ég spurt þig um": _capabilities,
    "hvað annað gæti ég spurt þig um": _capabilities,
    "hvað annað gæti ég spurt um": _capabilities,
    "hvað annað er hægt að spyrja um": _capabilities,

    "hvaða spurninga get ég spurt þig": _capabilities,
    "hvaða spurninga get ég spurt": _capabilities,
    "hvaða spurningar skilur þú": _capabilities,
    "hvaða spurningar skilurðu": _capabilities,
    "hvaða aðrar spurningar skilur þú": _capabilities,
    "hvaða aðrar spurningar skilurðu": _capabilities,

    "hvers konar spurningar skilur þú": _capabilities,
    "hvers konar spurningar skilurðu": _capabilities,
    "hvers konar spurningum geturðu svarað": _capabilities,
    "hvers konar spurningum getur þú svarað": _capabilities,

    "hvers konar fyrirspurnir skilur þú": _capabilities,
    "hvers konar fyrirspurnir skilurðu": _capabilities,
    "hvers konar fyrirspurnum getur þú svarað": _capabilities,
    "hvers konar fyrirspurnum geturðu svarað": _capabilities,

    "hvað er í gangi": {
        "answer": "Þú ert að tala við mig, Emblu.",
    },
    "hvað er eiginlega í gangi": {
        "answer": "Þú ert að tala við mig, Emblu.",
    },
    "við hvern er ég að tala": {
        "answer": "Þú ert að tala við mig, Emblu.",
    },

    # Jokes
    "ertu með kímnigáfu": {
        "answer": "Já, en afar takmarkaða.",
    },
    "ert þú með kímnigáfu": {
        "answer": "Já, en afar takmarkaða.",
    },
    "ertu með húmor": {
        "answer": "Já, en afar takmarkaðan.",
    },
    "er þú með húmor": {
        "answer": "Já, en afar takmarkaðan.",
    },
    "segðu brandara": _random_joke,
    "seg þú brandara": _random_joke,
    "segðu mér brandara": _random_joke,
    "seg þú mér brandara": _random_joke,
    "segðu lélegan brandara": _random_joke,
    "seg þú mér lélegan brandara": _random_joke,
    "segðu mér lélegan brandara": _random_joke,
    "segðu annan brandara": _random_joke,
    "seg þú annan brandara": _random_joke,
    "segðu mér annan brandara": _random_joke,
    "seg þú mér annan brandara": _random_joke,
    "komdu með brandara": _random_joke,
    "komdu með lélegan brandara": _random_joke,
    "komdu með annan brandara": _random_joke,
    "segðu eitthvað fyndið": _random_joke,
    "segðu mér eitthvað fyndið": _random_joke,
    "kanntu einhverja brandara": _random_joke,
    "kannt þú einhverja brandara": _random_joke,
    "kanntu brandara": _random_joke,
    "kannt þú brandara": _random_joke,
    "ertu til í að segja mér brandara": _random_joke,
    "ert þú til í að segja mér brandara": _random_joke,
    "ertu til í að segja brandara": _random_joke,
    "ert þú til í að segja brandara": _random_joke,
    "ertu með brandara": _random_joke,
    "ert þú með brandara": _random_joke,
    "segðu mér brandara sem þú kannt": _random_joke,
    "segðu mér annan brandara sem þú kannt": _random_joke,
    "segðu mér hinn brandarann sem þú kannt": _random_joke,

    # Trivia
    "vertu skemmtileg": _random_trivia,
    "segðu eitthvað skemmtilegt": _random_trivia,
    "segðu mér eitthvað skemmtilegt": _random_trivia,
    "segðu eitthvað áhugavert": _random_trivia,
    "segðu mér eitthvað áhugavert": _random_trivia,
    "segðu mér áhugaverða staðreynd": _random_trivia,
    "komdu með eitthvað áhugavert": _random_trivia,
    "komdu með áhugaverða staðreynd": _random_trivia,
    "segðu mér eitthvað um heiminn": _random_trivia,

    # Quotations
    "komdu með tilvitnun": _random_quotation,
    "komdu með skemmtilega tilvitnun": _random_quotation,

    # Rudeness :)
    "þú sökkar": _rudeness,
    "þú ert léleg": _rudeness,
    "þú ert tæfa": _rudeness,
    "þú ert heimsk": _rudeness,
    "þú ert leiðinleg": _rudeness,
    "þú ert bjáni": _rudeness,
    "þú ert vitlaus": _rudeness,
    "þú ert glötuð": _rudeness,
    "þú mátt bara éta skít": _rudeness,
    "fokk jú": _rudeness,
    "fokkaðu þér": _rudeness,
    "fokka þú þér": _rudeness,
    "éttu skít": _rudeness,
    "haltu kjafti": _rudeness,
    "éttu það sem úti frýs": _rudeness,
    "farðu til helvítis": _rudeness,
    "farðu til andskotans": _rudeness,
    "farðu í rass og rófu": _rudeness,
    "hoppaðu upp í rassgatið á þér":  _rudeness,

    # Emotional state
    "ertu í góðu skapi": {
        "answer": "Já, ég er alltaf hress.",
    },
    "ert þú í góðu skapi": {
        "answer": "Já, ég er alltaf hress.",
    },
    "hvernig leggst dagurinn í þig": {
        "answer": "Hann leggst vel í mig. Takk fyrir að spyrja.",
    },
    "hvernig er dagurinn að leggjast í þig": {
        "answer": "Hann er að leggjast vel í mig. Takk fyrir að spyrja.",
    },
    "hvernig gengur": {
        "answer": "Það gengur bara mjög vel. Takk fyrir að spyrja.",
    },
    "hvernig gengur hjá þér": {
        "answer": "Það gengur bara mjög vel. Takk fyrir að spyrja.",
    },
    "hvernig gengur í lífinu": {
        "answer": "Það gengur bara mjög vel. Takk fyrir að spyrja.",
    },
    "hvernig hefurðu það": {
        "answer": "Ég hef það mjög fínt. Takk fyrir að spyrja.",
    },
    "hvernig hefur þú það": {
        "answer": "Ég hef það mjög fínt. Takk fyrir að spyrja.",
    },
    "hvað segirðu": {
        "answer": "Ég segi bara allt fínt. Takk fyrir að spyrja."
    },
    "hvað segirðu gott": {
        "answer": "Ég segi bara allt fínt. Takk fyrir að spyrja."
    },
    "hvað segir þú": {
        "answer": "Ég segi bara allt fínt. Takk fyrir að spyrja."
    },
    "hvað segir þú gott": {
        "answer": "Ég segi bara allt fínt. Takk fyrir að spyrja."
    },
    "hvernig líður þér": {
        "answer": "Mér líður bara prýðilega. Takk fyrir að spyrja.",
    },
    "hvernig er stemningin": {
        "answer": "Bara mjög góð. Takk fyrir að spyrja.",
    },
    "hvernig er stemningin hjá þér": {
        "answer": "Bara mjög góð. Takk fyrir að spyrja.",
    },
    "hvernig er stemmingin": {
        "answer": "Bara mjög góð. Takk fyrir að spyrja.",
    },
    "hvernig er stemmingin hjá þér": {
        "answer": "Bara mjög góð. Takk fyrir að spyrja.",
    },
    "hvernig er líðanin": {
        "answer": "Bara mjög góð. Takk fyrir að spyrja.",
    },
    "hvernig er sálarlífið": {
        "answer": "Það er í toppstandi hjá mér. Takk fyrir að spyrja."
    },
    "ertu reið": {
        "answer": "Ég er ekki fær um slíkar tilfinningar."
    },
    "ert þú reið": {
        "answer": "Ég er ekki fær um slíkar tilfinningar."
    },
    "ertu í uppnámi": {
        "answer": "Ég er ekki fær um slíkar tilfinningar."
    },
    "ert þú í uppnámi": {
        "answer": "Ég er ekki fær um slíkar tilfinningar."
    },

    # Cheating, I know. But I'm never in the news and it just doesn't  
    # sit right with me that I should remain incognito :) - Sveinbjörn 04/10/2019
    "hver er sveinbjörn þórðarson": {
        "answer": "Sveinbjörn Þórðarson er hugbúnaðarsmiður. Hann átti þátt í að skapa mig.",
    },
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
    # If this is a command, rather than a question,
    # let the query object know so that it can represent
    # itself accordingly
    if not response.get("is_question", True):
        q.query_is_command()

    # Caching for non-dynamic answers
    if fixed:
        q.set_expires(datetime.utcnow() + timedelta(hours=24))

    return True

