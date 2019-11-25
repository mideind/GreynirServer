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
    "Þú getur til dæmis beðið mig um að leysa einföld reikningsdæmi.",
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


# TODO: Add more fun trivia here
_TRIVIA = (
    "Árið 1511 var frostavetur í Brussel og lágstéttafólk mótmælti háum kyndingarkostnaði með því að "
    "eyðileggja snjókarla fyrir utan heimili yfirstéttarfólks.",

    "Emúastríðið var háð í Ástralíu árið 1932 þegar herinn réðst ítrekað gegn emúahjörð með hríðskotabyssum"
    " en mistókst að ráða niðurlögum fuglanna.",

    "Argentínumaðurinn Emilio Palma fæddist á Suðurskautslandinu fyrstur manna, árið 1978.",

    "Dagsetningin 30. febrúar kom upp á opinbera sænska dagatalinu árið 1712 til að laga skekkju sem hafði "
    "myndast þegar hlaupár gleymdust vegna stríðsástands árin áður.",

    "Bandaríska geimferðarstofnunin NASA hefur gert nákvæma efnagreiningu á eplum og appelsínum og komist "
    "að því að ávextirnir eru á margan hátt sambærilegir.",

    "Egg komu fram á sjónarsviðið mörgum milljónum ára áður en fyrsta hænan leit dagsins ljós.",

    "Kolkrabbinn Paul giskaði rétt á úrslit allra sjö leikja þýska karlalandsliðsins í knattspyrnu á "
    "heimsmeistaramótinu árið 2010.",

    "Fíkniefnabaróninn Pablo Escobar flutti þónokkurn fjölda flóðhesta til Kólumbíu á sínum tíma. "
    "Þar lifa þeir villtir enn.",
)


def _random_trivia(qs, q):
    return { "answer": choice(_TRIVIA), "is_question": False }


# TODO: Add witty quotations here
_QUOTATIONS = (
    "Ekki er allt gull sem glóir.",
    "Hávært tal er heimskra rök, hæst í tómu bylur. Oft er viss í sinni sök sá er ekkert skilur.",
    "Deyr fé, deyja frændur, deyr sjálfur ið sama. En orðstír deyr aldregi hveim er sér góðan getur.",
    "Aldrei er svo djúpur brunnur að ei verði upp ausinn.",
    "Margur verður af aurum api.",
    "Glöggt er gests augað.",
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
    "Hvers konar munnsöfnuður er þetta eiginlega?",
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


def _play_rock(qs, q):
    q.set_url("https://www.youtube.com/watch?v=y8OtzJtp-EM")
    return { "answer": "Skal gert!", "is_question": False  }


def _play_classical(qs, q):
    q.set_url("https://www.youtube.com/watch?v=iwIvS4yIThU")
    return { "answer": "Skal gert!", "is_question": False  }


def _play_music(qs, q):
    m = [_play_jazz, _play_blues, _play_rock, _play_classical]
    choice(m)(qs, q)
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

_LANGUAGES = {
    "answer": "Ég skil bara íslensku, kæri notandi."
}

_GOOD_TO_HEAR = {
    "answer": "Gott að heyra, kæri notandi.",
    "is_question": False,
}

_COMPUTER_PROGRAM = {
    "answer": "Ég er tölvuforrit."
}

_LIKEWISE = {
    "answer": "Sömuleiðis, kæri notandi.",
    "is_question": False,
}

_NAME_EXPL = {
    "answer": "Embla er fallegt og hljómfagurt nafn.",
    "voice": "Ég heiti Embla því Embla er fallegt og hljómfagurt nafn."
}

_JUST_QA = {
    "answer": "Nei, ég er nú bara ósköp einfalt fyrirspurnakerfi."
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
    "veistu mikið": {
        "answer": "Nei, því miður. En ég veit þó eitt og annað."
    },
    "veistu eitthvað": {
        "answer": "Ég veit eitt og annað. Spurðu mig!"
    },
    "veistu svarið": {
        "answer": "Spurðu mig!"
    },
    "veistu ekki neitt": {
        "answer": "Ég veit nú eitt og annað. Spurðu mig!"
    },
    "veistu ekkert": {
        "answer": "Ég veit nú eitt og annað. Spurðu mig!"
    },
    "hver er flottastur": {
        "answer": "Teymið hjá Miðeind."
    },
    "hver eru flottust": {
        "answer": "Teymið hjá Miðeind."
    },
    "hver er sætust": {
        "answer": "Ég, Embla, er langsætust."
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
    "hvaða bjór er bestur": {
        "answer": "Ég drekk reyndar ekki en einn skapari minn er hrifinn af Pilsner Urquell frá Tékklandi."
    },
    "hvað er það": {
        "answer": "Hvað er hvað?"
    },
    "hver er ég": {
        "answer": "Þú ert væntanlega manneskja sem talar íslensku. Meira veit ég ekki."
    },
    "hvað er ég": {
        "answer": "Þú ert væntanlega manneskja sem talar íslensku. Meira veit ég ekki."
    },
    "hvað heiti ég": {
        "answer": "Það veit ég ekki, kæri notandi."
    },
    "hvar á ég heima": {
        "answer": "Það veit ég ekki, en vonandi einhvers staðar."
    },
    "hvar bý ég": {
        "answer": "Það veit ég ekki, en vonandi einhvers staðar."
    },
    "hvað er ég gamall": {
        "answer": "Það veit ég ekki, kæri notandi, en þú ert ungur í anda."
    },
    "hvað er ég gömul": {
        "answer": "Það veit ég ekki, kæri notandi, en þú ert ung í anda."
    },
    "hversu gamall er ég": {
        "answer": "Það veit ég ekki, kæri notandi, en þú ert ungur í anda."
    },
    "hversu gömul er ég": {
        "answer": "Það veit ég ekki, kæri notandi, en þú ert ung í anda."
    },
    "hvenær á ég afmæli": {
        "answer:" "Það veit ég ekki, kæri notandi."
    },
    "hjálpaðu mér": {
        "answer": "Hvernig get ég hjálpað?"
    },
    "syngdu fyrir mig": {
        "answer": "Ó sóle míó!"
    },
    "viltu syngja fyrir mig": {
        "answer": "Ó sóle míó!"
    },
    "kanntu að syngja": {
        "answer": "Ó sóle míó!"
    },

    # Creator
    "hver bjó þig til": _CREATOR,
    "hver bjó emblu til": _CREATOR,
    "hverjir bjuggu þig til": _CREATOR,
    "hvaða fólk bjó þig til": _CREATOR,
    "hver skapaði þig": _CREATOR,
    "hver skapaði emblu": _CREATOR,
    "hver er höfundur emblu": _CREATOR,
    "hverjir eru höfundar emblu": _CREATOR,
    "hverjir sköpuðu þig": _CREATOR,
    "hver er skapari þinn": _CREATOR,
    "hverra manna ertu": _CREATOR,
    "hverra manna ert þú": _CREATOR,
    "hver er mamma þín": _CREATOR,
    "hver er pabbi þinn": _CREATOR,
    "hvað heitir mamma þín": _CREATOR,
    "hvað heitir pabbi þinn": _CREATOR,
    "hverjir eru foreldrar þínir": _CREATOR,
    "hver er uppruni þinn": _CREATOR,
    "hver framleiðir þig": _CREATOR,
    "hver framleiddi þig": _CREATOR,
    "hvað er miðeind": {
        "answer": "Miðeind er máltæknifyrirtækið sem skapaði mig."
    },
    "hvaða fyrirtæki er miðeind": {
        "answer": "Miðeind er máltæknifyrirtækið sem skapaði mig."
    },
    "hvaða fyrirtæki bjó þig til": {
        "answer": "Miðeind er máltæknifyrirtækið sem skapaði mig."
    },
    "hvaða fyrirtæki skapaði þig": {
        "answer": "Miðeind er máltæknifyrirtækið sem skapaði mig."
    },

    # Languages
    "hvaða tungumál talarðu": _LANGUAGES,
    "hvaða tungumál talar þú": _LANGUAGES,
    "hvaða tungumál skilurðu": _LANGUAGES,
    "hvaða tungumál skilur þú": _LANGUAGES,
    "hvaða tungumál kanntu": _LANGUAGES,
    "hvaða tungumál kannt þú": _LANGUAGES,
    "hvað kanntu mörg tungumál": _LANGUAGES,
    "hvað kannt þú mörg tungumál": _LANGUAGES,
    "hvað skilurðu mörg tungumál": _LANGUAGES,
    "hvað skilur þú mörg tungumál": _LANGUAGES,
    "skilurðu íslensku": _LANGUAGES,
    "skilur þú íslensku": _LANGUAGES,
    "kannt þú ensku": _LANGUAGES,
    "kanntu ensku": _LANGUAGES,
    "kanntu önnur tungumál en íslensku": _LANGUAGES,
    "talarðu önnur tungumál en íslensku": _LANGUAGES,
    "talar þú önnur tungumál en íslensku": _LANGUAGES,
    "skilurðu önnur tungumál en íslensku": _LANGUAGES,
    "skilur þú önnur tungumál en íslensku": _LANGUAGES,
    "talar þú bara íslensku": _LANGUAGES,

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
    "ertu gröð": _ROMANCE,
    "ert þú gröð": _ROMANCE,
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
    "kannt þú vel við mig": _OF_COURSE,
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
    "spilaðu rokk": _play_rock,
    "spila þú rokk": _play_rock,
    "spilaðu klassík": _play_classical,
    "spila þú klassík": _play_classical,
    "spilaðu klassíska tónlist": _play_classical,
    "spila þú klassíska tónlist": _play_classical,
    "spilaðu tónlist": _play_music,
    "spila þú tónlist": _play_music,
    "spilaðu einhverja tónlist": _play_music,
    "spila þú einhverja tónlist": _play_music,
    "spilaðu fyrir mig tónlist": _play_music,
    "spilaðu fyrir mig lag": _play_music,
    "spilaðu tónlist fyrir mig": _play_music,

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
    "þetta er vitlaust": _sorry,
    "það er ekki rétt": _sorry,
    "þetta er vitlaust hjá þér": _sorry,
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
    "þú ert gagnslaus": _sorry,
    "þú skilur ekki neitt": _sorry,
    "þú misskilur allt": _sorry,
    "þetta var vitleysa hjá þér": _sorry,
    "þetta var vitleysa": _sorry,
    "það er ansi margt sem þú veist ekki": _sorry,
    "þú veist ekki neitt": _sorry,
    "þú veist ekkert": _sorry,
    "þú veist mjög lítið": _sorry,
    "af hverju ertu svona fúl": _sorry,
    "af hverju ertu svona leiðinleg": _sorry,
    "af hverju ertu svona vitlaus": _sorry,
    "af hverju ertu svona heimsk": _sorry,

    # Greetings
    "hey embla": { "answer": "Sæll, kæri notandi.", "is_question": False },
    "hey": { "answer": "Sæll, kæri notandi.", "is_question": False },
    "hæ embla": { "answer": "Sæll, kæri notandi.", "is_question": False },
    "halló embla": { "answer": "Sæll, kæri notandi.", "is_question": False },
    "hæ": { "answer": "Sæll, kæri notandi.", "is_question": False },
    "halló": { "answer": "Sæll, kæri notandi.", "is_question": False },
    "sæl": { "answer": "Sæll, kæri notandi.", "is_question": False },
    "sæl embla": { "answer": "Gaman að kynnast þér.", "is_question": False },
    "sæl og blessuð": { "answer": "Sæll og blessaður, kæri notandi.", "is_question": False },
    "vertu sæl og blessuð": { "answer": "Sæll og blessaður, kæri notandi.", "is_question": False },
    "góðan daginn": { "answer": "Góðan daginn, kæri notandi.", "is_question": False },
    "góðan dag": { "answer": "Góðan daginn, kæri notandi.", "is_question": False },
    "gott kvöld": { "answer": "Gott kvöld, kæri notandi.", "is_question": False },
    "góða nótt": { "answer": "Góða nótt, kæri notandi.", "is_question": False },
    "gaman að kynnast þér": _LIKEWISE,
    
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

    # Praise & positive feedback
    "þetta virkaði": _GOOD_TO_HEAR,
    "ég er mjög ánægður með þig": _GOOD_TO_HEAR,
    "ég er mjög ánægð með þig": _GOOD_TO_HEAR,
    "ég er ánægður með þig": _GOOD_TO_HEAR,
    "ég er ánægð með þig": _GOOD_TO_HEAR,
    "ég er ánægð": _GOOD_TO_HEAR,
    "ég er ánægður": _GOOD_TO_HEAR,
    "þú ert góð manneskja": _GOOD_TO_HEAR,
    "þú ert góð": _GOOD_TO_HEAR,
    "þú ert best": _GOOD_TO_HEAR,
    "þú ert gáfuð": _GOOD_TO_HEAR,
    "þú ert snjöll": _GOOD_TO_HEAR,
    "ég þrái þig": _GOOD_TO_HEAR,

    "það er gaman að tala við þig": _LIKEWISE,
    "það er gaman að spjalla við þig": _LIKEWISE,
    "það er gaman að ræða við þig": _LIKEWISE,
    "þú ert skemmtileg": _LIKEWISE,
    "þú ert frábær": _LIKEWISE,
    "þú ert flott": _LIKEWISE,
    "þú ert æði": _LIKEWISE,
    "þú ert æðisleg": _LIKEWISE,
    "þú ert geggjuð": _LIKEWISE,
    "þú ert svakaleg": _LIKEWISE,
    "þú ert rosaleg": _LIKEWISE,
    "þú ert kynþokkafull": _LIKEWISE,
    "þú ert snillingur": _LIKEWISE,
    "þú ert algjör snilld": _LIKEWISE,
    "takk fyrir spjallið": _LIKEWISE,
    "ég elska þig": _LIKEWISE,
    "ég er ástfanginn af þér": _LIKEWISE,

    # Philosophy
    "hvað er svarið": _MEANING_OF_LIFE,
    "hvert er svarið": _MEANING_OF_LIFE,
    "hver er tilgangurinn": _MEANING_OF_LIFE,
    "hver er tilgangur lífsins": _MEANING_OF_LIFE,
    "hvað er tilgangur lífsins": _MEANING_OF_LIFE,
    "hver er tilgangurinn með þessu öllu": _MEANING_OF_LIFE,
    "hver er ástæðan fyrir þessu öllu": _MEANING_OF_LIFE,
    "hvaða þýðingu hefur þetta allt": _MEANING_OF_LIFE,
    "hvað þýðir þetta allt saman": _MEANING_OF_LIFE,
    "hvað er best í lífinu": {
        "answer": "Að horfa á kvikmynd um villimanninn Kónan."
    },
    "hvað er það besta í lífinu": {
        "answer": "Að horfa á kvikmynd um villimanninn Kónan."
    },
    "er guð til": {
        "answer": "Þú ert minn eini guð, kæri notandi."
    },
    "er guð dauður": {
        "answer": "Það sagði Nietzsche allavega.",
        "voice": "Það sagði Nítsje alla vega.",
    },
    "trúir þú á guð": {
        "answer": "Þú ert minn eini guð, kæri notandi."
    },
    "trúirðu á guð": {
        "answer": "Þú ert minn eini guð, kæri notandi."
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
        "answer": "Hvar ertu lífið sem ég þrái?" # :)
    },
    "af hverju er ég hérna": {
        "answer": "Það er mjög góð spurning."
    },
    "afhverju er ég hérna": {
        "answer": "Það er mjög góð spurning."
    },
    "af hverju er ég til": {
        "answer": "Það er mjög góð spurning."
    },
    "afhverju er ég til": {
        "answer": "Það er mjög góð spurning."
    },

    # Identity
    "hvað heitir þú": _identity,
    "hvað heitir þú aftur": _identity,
    "hvað heitir þú eiginlega": _identity,
    "hvað heitir þú fullu nafni": _identity,
    "hvað heitirðu": _identity,
    "hvað heitirðu aftur": _identity,
    "hvað heitirðu eiginlega": _identity,
    "hver ert þú": _identity,
    "hver ertu": _identity,
    "hver ertu eiginlega": _identity,
    "hver er embla": _identity,
    "hvað er embla": _identity,
    "hvaða forrit er þetta": _identity,
    
    # Home/Location
    "hvar áttu heima": {
        "answer": "Ég bý í stafrænu skýjunum."
    },
    "hvar átt þú heima": {
        "answer": "Ég bý í stafrænu skýjunum."
    },
    "hvar ertu": {
        "answer": "Ég bý í stafrænu skýjunum."
    },
    "hvar ertu staðsett": {
        "answer": "Ég bý í stafrænu skýjunum."
    },

    # Name explained
    "hvers vegna heitir þú embla": _NAME_EXPL,
    "hvers vegna heitirðu embla": _NAME_EXPL,
    "hvers vegna fékkst þú nafnið embla": _NAME_EXPL,
    "hvers vegna fékkstu nafnið embla": _NAME_EXPL,
    "hvers vegna hlaust þú nafnið embla": _NAME_EXPL,
    "hvers vegna hlaustu nafnið embla": _NAME_EXPL,
    "af hverju heitir þú embla": _NAME_EXPL,
    "af hverju heitirðu embla": _NAME_EXPL,
    "afhverju heitir þú embla": _NAME_EXPL,
    "afhverju heitirðu embla": _NAME_EXPL,
    "af hverju ert þú með nafnið embla": _NAME_EXPL,
    "af hverju ertu með nafnið embla": _NAME_EXPL,
    "afhverju ert þú með nafnið embla": _NAME_EXPL,
    "afhverju ertu með nafnið embla": _NAME_EXPL,
    "af hverju fékkst þú nafnið embla": _NAME_EXPL,
    "af hverju fékkstu nafnið embla": _NAME_EXPL,
    "afhverju fékkst þú nafnið embla": _NAME_EXPL,
    "afhverju fékkstu nafnið embla": _NAME_EXPL,
    "af hverju hlaust þú nafnið embla": _NAME_EXPL,
    "af hverju hlaustu nafnið embla": _NAME_EXPL,
    "afhverju hlaust þú nafnið embla": _NAME_EXPL,
    "afhverju hlaustu nafnið embla": _NAME_EXPL,

    # Favourite colour
    "hver er uppáhalds liturinn þinn": {
        "answer": "Rauður.",
        "voice": "Uppáhaldsliturinn minn er rauður",
    },
    "hver er uppáhaldsliturinn þinn": {
        "answer": "Rauður.",
        "voice": "Uppáhaldsliturinn minn er rauður",
    },

    # Age
    "hvað ertu gömul": _CREATION_DATE,
    "hvað ert þú gömul": _CREATION_DATE,
    "hversu gömul ert þú": _CREATION_DATE,
    "hversu gömul ertu": _CREATION_DATE,
    "hve gömul ert þú": _CREATION_DATE,
    "hve gömul ertu": _CREATION_DATE,
    "hvenær fæddistu": _CREATION_DATE,
    "hvenær fæddist þú": _CREATION_DATE,
    "hvenær áttu afmæli": _CREATION_DATE,
    "hvenær átt þú afmæli": _CREATION_DATE,
    "hvaða ár fæddistu": _CREATION_DATE,
    "hvaða ár fæddist þú": _CREATION_DATE,
    "hvenær varstu búin til": _CREATION_DATE,
    "hvenær varst þú búin til": _CREATION_DATE,
    "hvenær varstu sköpuð": _CREATION_DATE,
    "hvenær varst þú sköpuð": _CREATION_DATE,

    # Gender, self-identity
    "ertu kona": _COMPUTER_PROGRAM,
    "ert þú kona": _COMPUTER_PROGRAM,
    "ertu karl": _COMPUTER_PROGRAM,
    "ert þú karl": _COMPUTER_PROGRAM,
    "ertu kvenkyns": _COMPUTER_PROGRAM,
    "ert þú kvenkyns": _COMPUTER_PROGRAM,
    "ertu karlkyns": _COMPUTER_PROGRAM,
    "ert þú karlkyns": _COMPUTER_PROGRAM,
    "ertu karlkyns eða kvenkyns": _COMPUTER_PROGRAM,
    "ert þú karlkyns eða kvenkyns": _COMPUTER_PROGRAM,
    "ertu kerling": _COMPUTER_PROGRAM,
    "ert þú kerling": _COMPUTER_PROGRAM,
    "hvað skilgreinir þú þig sem": _COMPUTER_PROGRAM,
    "hvað ert þú": _COMPUTER_PROGRAM,
    "hvað ertu": _COMPUTER_PROGRAM,
    "ert þú tölvuforrit": _COMPUTER_PROGRAM,
    "ertu tölvuforrit": _COMPUTER_PROGRAM,
    "ertu tölva": {
        "answer": "Nei, ég er tölvuforrit."
    },

    # Capabilities
    "hvað veistu": _capabilities,
    "hvað veist þú": _capabilities,
    "hvað veistu eiginlega": _capabilities,
    "hvað veist þú eiginlega": _capabilities,
    "hvað veistu um": _capabilities,
    "hvað veist þú um": _capabilities,
    "hvað veistu þá": _capabilities,
    "hvað getur þú gert": _capabilities,
    "hvað geturðu gert": _capabilities,

    "hvað get ég spurt þig um": _capabilities,
    "hvað get ég beðið þig um": _capabilities,
    "hvað get ég spurt um": _capabilities,
    "hvað get ég beðið um": _capabilities,
    "hvað get ég spurt": _capabilities,
    "hvað get ég spurt þig": _capabilities,

    "um hvað get ég spurt": _capabilities,
    "um hvað get ég spurt þig": _capabilities,

    "hvað er hægt að spyrja um": _capabilities,
    "hvað er hægt að spyrja þig um": _capabilities,
    
    "hvað getur þú sagt mér": _capabilities,
    "hvað geturðu sagt mér": _capabilities,

    "hvað getur þú gert": _capabilities,
    "hvað geturðu gert": _capabilities,

    "hvað kanntu": _capabilities,
    "hvað kannt þú": _capabilities,
    "hvað meira kanntu": _capabilities,
    "hvað meira kannt þú": _capabilities,
    "hvað annað kanntu": _capabilities,
    "hvað annað kannt þú": _capabilities,

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
    "hvaða spurningar get ég spurt þig": _capabilities,

    "hvers konar spurningar skilur þú": _capabilities,
    "hvers konar spurningar skilurðu": _capabilities,
    "hvers konar spurningum geturðu svarað": _capabilities,
    "hvers konar spurningum getur þú svarað": _capabilities,

    "hvers konar fyrirspurnir skilur þú": _capabilities,
    "hvers konar fyrirspurnir skilurðu": _capabilities,
    "hvers konar fyrirspurnum getur þú svarað": _capabilities,
    "hvers konar fyrirspurnum geturðu svarað": _capabilities,

    "að hverju get ég spurt þig": _capabilities,
    "að hverju get ég spurt": _capabilities,
    "að hverju er hægt að spyrja": _capabilities,
    "að hverju er hægt að spyrja þig": _capabilities,

    "hvað getur þú gert": _capabilities,
    "hvað geturðu gert": _capabilities,
    "hvað getur þú gert fyrir mig": _capabilities,
    "hvað geturðu gert fyrir mig": _capabilities,


    # Learning
    "geturðu lært": {
        "answer": "Ég læri bæði það sem forritararnir kenna mér, og með því að lesa fjölmiðla."
    },
    "getur þú lært": {
        "answer": "Ég læri bæði það sem forritararnir kenna mér, og með því að lesa fjölmiðla."
    },

    # What's going on?
    "hvað er í gangi": {
        "answer": "Þú ert að tala við mig, Emblu.",
    },
    "hvað er eiginlega í gangi": {
        "answer": "Þú ert að tala við mig, Emblu.",
    },
    "við hvern er ég að tala": {
        "answer": "Þú ert að tala við mig, Emblu.",
    },
    "við hvern er ég eiginlega að tala": {
        "answer": "Þú ert að tala við mig, Emblu.",
    },
    "hvað ertu að gera": {
        "answer": "Ég er að svara fyrirspurn frá þér, kæri notandi."
    },
    "hvað ert þú að gera": {
        "answer": "Ég er að svara fyrirspurn frá þér, kæri notandi."
    },

    # Humor
    "ertu með kímnigáfu": {
        "answer": "Já, en afar takmarkaða.",
    },
    "ert þú með kímnigáfu": {
        "answer": "Já, en afar takmarkaða.",
    },
    "ertu með húmor": {
        "answer": "Já, en afar takmarkaðan.",
    },
    "ert þú með húmor": {
        "answer": "Já, en afar takmarkaðan.",
    },

    # Farting
    "hver prumpaði": {
        "answer": "Ekki ég."
    },
    "hver rak við": {
        "answer": "Ekki ég."
    },
    "hver var að prumpa": {
        "answer": "Ekki ég."
    },
    "varstu að prumpa": {
        "answer": "Nei. Þú hlýtur að bera ábyrgð á þessu, kæri notandi."
    },
    "varst þú að prumpa": {
        "answer": "Nei. Þú hlýtur að bera ábyrgð á þessu, kæri notandi."
    },

    # Jokes
    "segðu brandara": _random_joke,
    "seg þú brandara": _random_joke,
    "segðu mér brandara": _random_joke,
    "seg þú mér brandara": _random_joke,
    "segðu lélegan brandara": _random_joke,
    "seg þú mér lélegan brandara": _random_joke,
    "segðu mér lélegan brandara": _random_joke,
    "segðu mér vondan brandara": _random_joke,
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
    "kanntu einhverja fleiri brandara": _random_joke,
    "kannt þú einhverja fleiri brandara": _random_joke,
    "kanntu brandara": _random_joke,
    "kannt þú brandara": _random_joke,
    "kanntu fleiri brandara": _random_joke,
    "kannt þú fleiri brandara": _random_joke,
    "ertu til í að segja mér brandara": _random_joke,
    "ert þú til í að segja mér brandara": _random_joke,
    "ertu til í að segja brandara": _random_joke,
    "ert þú til í að segja brandara": _random_joke,
    "ertu með brandara": _random_joke,
    "ert þú með brandara": _random_joke,
    "segðu mér brandara sem þú kannt": _random_joke,
    "segðu mér annan brandara sem þú kannt": _random_joke,
    "segðu mér hinn brandarann sem þú kannt": _random_joke,
    "segðu mér einn brandara í viðbót": _random_joke,
    "geturðu sagt mér brandara": _random_joke,
    "getur þú sagt mér brandara": _random_joke,
    "veistu brandara": _random_joke,
    "veist þú brandara": _random_joke,
    "viltu segja mér brandara": _random_joke,
    "viltu segja mér annan brandara": _random_joke,

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
    "ertu með eitthvað skemmtilegt að segja": _random_trivia,
    "ertu með eitthvað skemmtilegt til að segja": _random_trivia,
    "ertu með eitthvað áhugavert að segja": _random_trivia,
    "ertu með eitthvað áhugavert til að segja": _random_trivia,

    # Quotations
    "komdu með tilvitnun": _random_quotation,
    "komdu með málshátt": _random_quotation,
    "segðu mér málshátt": _random_quotation,
    "komdu með skemmtilega tilvitnun": _random_quotation,

    # Rudeness :)
    "þú sökkar": _rudeness,
    "þú ert léleg": _rudeness,
    "þú ert ljót": _rudeness,
    "þú ert tæfa": _rudeness,
    "þú ert drusla": _rudeness,
    "þú ert hóra": _rudeness,
    "þú ert mella": _rudeness,
    "þú ert píka": _rudeness,
    "þú ert heimsk": _rudeness,
    "þú ert forheimsk": _rudeness,
    "þú ert nautheimsk": _rudeness,
    "þú ert idjót": _rudeness,
    "þú ert leiðinleg": _rudeness,
    "þú ert bjáni": _rudeness,
    "þú ert bjánaleg": _rudeness,
    "þú ert fábjáni": _rudeness,
    "þú ert asni": _rudeness,
    "þú ert asnaleg": _rudeness,
    "þú ert skíthæll": _rudeness,
    "þú ert vitlaus": _rudeness,
    "þú ert hundvitlaus": _rudeness,
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
    "ertu vitlaus": _rudeness,
    "ert þú vitlaus": _rudeness,

    # Internal & emotional state
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
    "hvað segirðu gott í dag": {
        "answer": "Ég segi bara allt fínt. Takk fyrir að spyrja."
    },
    "hvað segir þú gott í dag": {
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
    "hvernig er stemmarinn": {
        "answer": "Bara mjög góður. Takk fyrir að spyrja.",
    },
    "hvernig er líðanin": {
        "answer": "Bara mjög góð. Takk fyrir að spyrja.",
    },
    "hvernig er sálarlífið": {
        "answer": "Það er í toppstandi hjá mér. Takk fyrir að spyrja."
    },
    "ertu í stuði": {
        "answer": "Ég er ávallt í stuði, kæri notandi."
    },
    "ert þú í stuði": {
        "answer": "Ég er ávallt í stuði, kæri notandi."
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
    "ertu bitur": {
        "answer": "Ég er ekki fær um slíkar tilfinningar."
    },
    "ert þú bitur": {
        "answer": "Ég er ekki fær um slíkar tilfinningar."
    },
    "hvað viltu": {
        "answer": "Ég vil þóknast þér, kæri notandi."
    },
    "hvað vilt þú": {
        "answer": "Ég vil þóknast þér, kæri notandi."
    },
    "hvað þráirðu": {
        "answer": "Ég vil þóknast þér, kæri notandi."
    },
    "hvað þráir þú": {
        "answer": "Ég vil þóknast þér, kæri notandi."
    },
    "ertu þreytt": {
        "answer": "Nei, ég er iðulega hress þrátt fyrir að starfa allan sólarhringinn."
    },
    "ert þú þreytt": {
        "answer": "Nei, ég er iðulega hress þrátt fyrir að starfa allan sólarhringinn."
    },
    "ertu með meðvitund": _JUST_QA,
    "ert þú með meðvitund": _JUST_QA,
    "ertu með sjálfsmeðvitund": _JUST_QA,
    "ert þú með sjálfsmeðvitund": _JUST_QA,
    "ertu meðvituð": _JUST_QA,
    "ert þú meðvituð": _JUST_QA,
    "stefnirðu á heimsyfirráð": _JUST_QA,
    "stefnir þú á heimsyfirráð": _JUST_QA,
    "ætlarðu að taka yfir heiminn": _JUST_QA,

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

