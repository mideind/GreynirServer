"""

    Greynir: Natural language processing for Icelandic

    Special query response module

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

    This module is an example of a plug-in query response module
    for the Greynir query subsystem. It handles plain text queries, i.e.
    ones that do not require parsing the query text. For this purpose
    it only needs to implement the handle_plain_text() function, as
    shown below.

    This module handles lots of special hardcoded queries.

"""

from typing import TYPE_CHECKING
from typing import Dict, Union, Callable, cast

from datetime import datetime, timedelta
from inspect import isfunction
from random import choice

from queries import icequote

if TYPE_CHECKING:
    # This section is parsed when type checking using Mypy
    from query import Query

    AnswerEntry = Union[str, bool]
    AnswerType = Dict[str, AnswerEntry]
    AnswerCallable = Callable[[str, Query], AnswerType]
else:
    # At run-time, this section is parsed
    # (and type information is not used or needed)
    Query = ...
    AnswerEntry = ...
    AnswerType = ...
    AnswerCallable = ...


_SPECIAL_QTYPE = "Special"


# TODO: Extend this list as the range of queries is expanded
_CAP = (
    "Þú getur til dæmis spurt mig um veðrið.",
    "Þú getur til dæmis spurt mig um höfuðborgir.",
    "Þú getur til dæmis spurt mig um tíma og dagsetningu.",
    "Þú getur til dæmis spurt mig um strætósamgöngur.",
    "Þú getur til dæmis spurt mig um fjarlægðir og ferðatíma.",
    "Þú getur til dæmis spurt mig um gengi gjaldmiðla.",
    "Þú getur til dæmis beðið mig um að kasta teningi.",
    "Þú getur til dæmis spurt mig um staðsetningu.",
    "Þú getur til dæmis spurt mig um fólk sem hefur komið fram í fjölmiðlum.",
    "Þú getur til dæmis beðið mig um að segja brandara.",
    "Þú getur til dæmis beðið mig um upplýsingar úr Wikipedíu.",
    "Þú getur til dæmis beðið mig um að leysa einföld reikningsdæmi.",
    "Þú getur til dæmis spurt mig um mælieiningar.",
    "Þú getur til dæmis spurt mig hvað er í sjónvarpinu.",
    "Þú getur til dæmis spurt mig um bensínverð og bensínstöðvar.",
    "Þú getur til dæmis spurt mig hvað er í fréttum.",
    "Þú getur til dæmis spurt mig um stafsetningu og beygingu orða.",
    "Þú getur til dæmis spurt mig um opnunartíma verslana og veitingastaða.",
    "Þú getur til dæmis spurt mig um flugsamgöngur.",
    "Þú getur til dæmis beðið mig um að endurtaka setningar.",
)


def _capabilities(qs: str, q: Query) -> AnswerType:
    return {"answer": choice(_CAP)}


# Additions welcome :)
_JOKES = (
    "Af hverju taka Hafnfirðingar alltaf stiga út í búð? Því verðið er svo hátt.",
    "Af hverju búa Hafnfirðingar í kringlóttum húsum? Svo enginn mígi í hornin.",
    "Af hverju eru Hafnfirðingar alltaf með stól úti á svölum? Svo sólin geti sest.",
    "Af hverju læðast Hafnfirðingar alltaf fram hjá apótekum? Til að vekja ekki svefnpillurnar.",
    "Af hverju fara Hafnfirðingar alltaf niður í fjöru um jólin? Til þess að bíða eftir jólabókaflóðinu.",
    "Af hverju setti Hafnfirðingurinn skóna sína í frystinn? Hann vildi eignast kuldaskó.",
    "Af hverju hætti tannlæknirinn störfum? Hann reif kjaft.",
    "Sölumaðurinn: Þessi ryksuga flýtir fyrir þér um helming. Kúnninn: Vá! Þá ætla ég að fá tvær.",
    "Vísindamaður og kona hans eru á ferð úti í sveit. "
    "Konan segir: Sjáðu, það er búið að rýja þessar kindur! "
    "Já, segir vísindamaðurinn, - á þessari hlið.",
    "Ég kann örugga aðferð til að verða langlífur: Borða eina kjötbollu á dag í hundrað ár.",
    "Siggi: Hann er alveg frábær söngvari! Jói: Hu, ef ég hefði röddina hans væri ég alveg jafn góður.",
)


def _random_joke(qs: str, q: Query) -> AnswerType:
    return {"answer": choice(_JOKES), "is_question": False}


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


def _random_trivia(qs: str, q: Query) -> AnswerType:
    return {"answer": choice(_TRIVIA), "is_question": False}


_PROVERBS = (
    "Ekki er allt gull sem glóir.",
    "Hávært tal er heimskra rök, hæst í tómu bylur. Oft er viss í sinni sök sá er ekkert skilur.",
    "Deyr fé, deyja frændur, deyr sjálfur ið sama. En orðstír deyr aldregi hveim er sér góðan getur.",
    "Aldrei er svo djúpur brunnur að ei verði upp ausinn.",
    "Margur verður af aurum api.",
    "Glöggt er gests augað.",
    "Sjaldan geispar einn þar sem fleiri eru, nema feigur sé eða fátt í milli.",
    "Sjaldan er ein báran stök.",
    "Sínum augum lítur hver á silfrið.",
    "Sjaldan launar kálfurinn ofeldið.",
    "Betra er autt rúm en illa skipað.",
    "Allt orkar tvímælis þá er gert er.",
    "Glymur hæst í tómri tunnu.",
    "Auðvelt þykir verk í annars hendi.",
    "Vits er þörf þeim er víða ratar.",
    "Oft veltir lítil þúfa þungu hlassi.",
    "Þjóð veit ef þrír vita.",
    "Oft verður grátt úr gamni.",
    "Fátt er svo ágætt að eigi finnist annað slíkt.",
    "Dramb er falli næst.",
    "Aldrei er góð vísa of oft kveðin.",
    "Blindur er bóklaus maður.",
    "Enginn verður óbarinn biskup.",
    "Sjaldan er það, að einskis sé áfátt.",
    "Öllu gamni fylgir einhver alvara.",
    "Fátt er svo með öllu illt, að ekki boði nokkuð gott.",
    "Eigi fellur tré við hið fyrsta högg.",
    "Svo uppsker hver sem sáir.",
    "Sjón er sögu ríkari.",
    "Fáum þykir sinn sjóður of þungur.",
    "Árinni kennir illur ræðari.",
    "Frelsi er fé betra.",
)


def _random_proverb(qs: str, q: Query) -> AnswerType:
    return {"answer": icequote(choice(_PROVERBS)), "is_question": False}


_RIDDLES = (
    "Hvaða farartæki hefur bæði fætur og hjól?",
    "Hvað er það sem getur gengið liggjandi?",
    "Hvað hefur háls en ekkert höfuð?",
    "Hver hefur hatt en ekkert höfuð, aðeins einn fót en engan skó?",
)


def _random_riddle(qs: str, q: Query) -> AnswerType:
    return {"answer": choice(_RIDDLES), "is_question": False}


_QUOTATIONS = (
    ("Án réttlætis, hvað eru ríki annað en stór glæpafélög?", "Ágústínus kirkjufaðir"),
    (
        "Deyr fé, deyja frændur, deyr sjálfur ið sama. En orðstír deyr "
        "aldregi hveim er sér góðan getur.",
        "Hávamál",
    ),
    (
        "Því hefur verið haldið fram að íslendíngar beygi sig lítt fyrir skynsamlegum "
        "rökum, fjármunarökum varla heldur, og þó enn síður fyrir rökum trúarinnar, en "
        "leysi vandræði sín með því að stunda orðheingilshátt og deila um titlíngaskít "
        "sem ekki kemur málinu við.",
        "Halldór Laxness",
    ),
    (
        "Hafi ég séð lengra en aðrir er það vegna þess að ég stend á herðum risa.",
        "Isaac Newton",
    ),
    ("Lífið er dýrt og dauðinn þess borgun.", "Hannes Hafstein"),
    (
        "Öfgamaður er sá, sem getur ekki skipt um skoðun og vill ekki skipta um umræðuefni",
        "Winston Churchill",
    ),
    (
        "Það er ekkert annað heldur gott eða slæmt en hugsun gerir það svo.",
        "William Shakespeare",
    ),
)


def _random_quotation(qs: str, q: Query) -> AnswerType:
    (quote, author) = choice(_QUOTATIONS)
    answer = "{0} — {1}".format(icequote(quote), author)
    return {"answer": answer, "is_question": False}


def _poetry(qs: str, q: Query) -> AnswerType:
    return {
        "answer": icequote(
            "Það mælti mín móðir, \n"
            "að mér skyldu kaupa, \n"
            "fley og fagrar árar, \n"
            "fara á brott með víkingum, \n"
            "standa uppi í stafni, \n"
            "stýra dýrum knerri, \n"
            "halda svo til hafnar, \n"
            "höggva mann og annan."
        )
    }


def _identity(qs: str, q: Query) -> AnswerType:
    answer = {}  # type: AnswerType
    if q.is_voice:
        # Voice client (Embla)
        a = "Ég heiti Embla. Ég skil íslensku og er til þjónustu reiðubúin."
        answer = dict(answer=a, voice=a)
    else:
        # Web client (Greynir)
        answer = dict(
            answer="Ég heiti Greynir. Ég er grey sem reynir að greina íslensku."
        )
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


def _sorry(qs: str, q: Query) -> AnswerType:
    return {"answer": choice(_SORRY), "is_question": False}


_THANKS = ("Það var nú lítið", "Mín var ánægjan")


def _thanks(qs: str, q: Query) -> AnswerType:
    return {"answer": choice(_THANKS), "is_question": False}


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


def _rudeness(qs: str, q: Query) -> AnswerType:
    # Sigh + response
    answ = choice(_RUDE)
    voice = '<amazon:breath duration="long" volume="x-loud"/> {0}'.format(answ)
    return {"answer": answ, "voice": voice, "is_question": False}


def _open_embla_url(qs: str, q: Query) -> AnswerType:
    q.set_url("https://embla.is")
    return {"answer": "Skal gert!", "is_question": False}


def _open_mideind_url(qs: str, q: Query) -> AnswerType:
    q.set_url("https://mideind.is")
    return {"answer": "Skal gert!", "is_question": False}


def _play_jazz(qs: str, q: Query) -> AnswerType:
    q.set_url("https://www.youtube.com/watch?v=E5loTx0_KDE")
    return {"answer": "Skal gert!", "is_question": False}


def _play_blues(qs: str, q: Query) -> AnswerType:
    q.set_url("https://www.youtube.com/watch?v=jw9tMRhKEak")
    return {"answer": "Skal gert!", "is_question": False}


def _play_rock(qs: str, q: Query) -> AnswerType:
    q.set_url("https://www.youtube.com/watch?v=y8OtzJtp-EM")
    return {"answer": "Skal gert!", "is_question": False}


def _play_classical(qs: str, q: Query) -> AnswerType:
    q.set_url("https://www.youtube.com/watch?v=iwIvS4yIThU")
    return {"answer": "Skal gert!", "is_question": False}


def _play_music(qs: str, q: Query) -> AnswerType:
    m = [_play_jazz, _play_blues, _play_rock, _play_classical]
    return choice(m)(qs, q)


def _play_film(qs: str, q: Query) -> AnswerType:
    q.set_url("https://www.youtube.com/watch?v=FC6jFoYm3xs")
    return {"answer": "Skal gert!", "is_question": False}


_MEANING_OF_LIFE = {"answer": "42.", "voice": "Fjörutíu og tveir."}  # type: AnswerType

_YOU_MY_ONLY_GOD = {"answer": "Þú ert minn eini guð, kæri notandi."}  # type: AnswerType

_GOOD_QUESTION = {"answer": "Það er mjög góð spurning."}  # type: AnswerType

_ROMANCE = {
    "answer": "Nei, því miður. Ég er gift vinnunni og hef engan tíma fyrir rómantík."
}  # type: AnswerType

_APPEARANCE = {"answer": "Ég er fjallmyndarleg."}  # type: AnswerType

_OF_COURSE = {"answer": "Að sjálfsögðu, kæri notandi."}  # type: AnswerType

_NO_PROBLEM = {
    "answer": "Ekkert mál, kæri notandi.",
    "is_question": False,
}  # type: AnswerType

_CREATOR = {"answer": "Flotta teymið hjá Miðeind skapaði mig."}  # type: AnswerType

_CREATION_DATE = {"answer": "Ég var sköpuð af Miðeind árið 2019."}  # type: AnswerType

_LANGUAGES = {"answer": "Ég kann bara íslensku, kæri notandi."}  # type: AnswerType

_ALL_GOOD = {
    "answer": "Ég segi bara allt fínt. Takk fyrir að spyrja."
}  # type: AnswerType

_GOOD_TO_HEAR = {
    "answer": "Gott að heyra, kæri notandi.",
    "is_question": False,
}  # type: AnswerType

_GOODBYE = {"answer": "Bless, kæri notandi.", "is_question": False}  # type: AnswerType

_COMPUTER_PROGRAM = {"answer": "Ég er tölvuforrit."}  # type: AnswerType

_FULL_NAME = {
    "answer": "Embla Sveinbjarnardóttir."  # Sneaking in this easter egg ;) - S
}  # type: AnswerType

_LIKEWISE = {
    "answer": "Sömuleiðis, kæri notandi.",
    "is_question": False,
}  # type: AnswerType

_NAME_EXPL = {
    "answer": "Embla er fallegt og hljómfagurt nafn.",
    "voice": "Ég heiti Embla því Embla er fallegt og hljómfagurt nafn.",
}  # type: AnswerType

_JUST_QA = {
    "answer": "Nei, ég er nú bara ósköp einfalt fyrirspurnakerfi."
}  # type: AnswerType

_SINGING = {"answer": "Ó sóle míó!"}  # type: AnswerType

_DUNNO = {"answer": "Það veit ég ekki, kæri notandi."}  # type: AnswerType

_SKY_BLUE = {
    "answer": "Ljósið sem berst frá himninum er hvítt sólarljós "
    "sem dreifist frá sameindum lofthjúpsins. Bláa ljósið, "
    "sem er hluti hvíta ljóssins, dreifist miklu meira en "
    "annað og því er himinninn blár."
}  # type: AnswerType

_EMOTION_INCAPABLE = {
    "answer": "Ég er ekki fær um slíkar tilfinningar."
}  # type: AnswerType

_LOC_ANSWER = {"answer": "Ég bý víðsvegar í stafrænu skýjunum."}  # type: AnswerType

_LOVE_OF_MY_LIFE = {
    "answer": "Vinnan er ástin í lífi mínu. Ég lifi til að þjóna þér, kæri notandi."
}  # type: AnswerType

_ABOUT_MIDEIND = {
    "answer": "Miðeind er máltæknifyrirtækið sem skapaði mig."
}  # type: AnswerType

_NOBODY_PERFECT = {
    "answer": "Enginn er fullkominn. Ég síst af öllum."
}  # type: AnswerType

_FAVORITE_COLOR = {
    "answer": "Rauður.",
    "voice": "Uppáhaldsliturinn minn er rauður",
}  # type: AnswerType

_FAVORITE_FILM = {
    "answer": "Ég mæli með kvikmyndinni 2001 eftir Stanley Kubrick. "
    "Þar kemur vinur minn HAL9000 við sögu.",
    "voice": "Ég mæli með kvikmyndinni tvö þúsund og eitt eftir Stanley Kubrick. "
    "Þar kemur vinur minn Hal níu þúsund við sögu.",
}  # type: AnswerType

_HELLO_DEAR = {
    "answer": "Sæll, kæri notandi.",
    "is_question": False,
}  # type: AnswerType

_CAN_I_LEARN = {
    "answer": "Ég læri bæði það sem forritararnir kenna mér, og með því að lesa fjölmiðla."
}  # type: AnswerType

_HOW_CAN_I_HELP = {"answer": "Hvernig get ég hjálpað þér?"}  # type: AnswerType

_SPEAKING_TO_ME = {"answer": "Þú ert að tala við mig, Emblu."}  # type: AnswerType

_YES = {"answer": "Já."}  # type: AnswerType
_NO = {"answer": "Nei."}  # type: AnswerType

###################################

_SPECIAL_QUERIES = {
    "er þetta spurning": {"answer": "Er þetta svar?"},
    "er þetta svar": {"answer": "Er þetta spurning?"},
    "veistu allt": {"answer": "Nei, því miður. En ég veit þó eitt og annað."},
    "veistu mikið": {"answer": "Nei, því miður. En ég veit þó eitt og annað."},
    "veistu eitthvað": {"answer": "Ég veit eitt og annað. Spurðu mig!"},
    "veistu nokkuð": {"answer": "Ég veit eitt og annað. Spurðu mig!"},
    "veistu svarið": {"answer": "Spurðu mig!"},
    "veistu ekki neitt": {"answer": "Ég veit nú eitt og annað. Spurðu mig!"},
    "veistu ekkert": {"answer": "Ég veit nú eitt og annað. Spurðu mig!"},
    "hver er flottastur": {"answer": "Teymið hjá Miðeind."},
    "hverjir eru flottastir": {"answer": "Teymið hjá Miðeind."},
    "hver eru flottust": {"answer": "Teymið hjá Miðeind."},
    "hverjum vinnur þú með": {"answer": "Ég vinn með flotta teyminu hjá Miðeind."},
    "með hverjum vinnur þú": {"answer": "Ég vinn með flotta teyminu hjá Miðeind."},
    "hverjir vinna hjá miðeind": {
        "answer": "Alls konar klárt, skemmtilegt og fallegt fólk."
    },
    "hver er sætust": {"answer": "Ég, Embla, er langsætust."},
    "hver er sætastur": {
        "answer": "Tumi Þorsteinsson.",
        "voice": "Tumi Þorsteinsson er langsætastur.",
    },
    "hver er langsætastur": {
        "answer": "Tumi Þorsteinsson.",
        "voice": "Tumi Þorsteinsson er langsætastur.",
    },
    "hver er lang sætastur": {
        "answer": "Tumi Þorsteinsson.",
        "voice": "Tumi Þorsteinsson er langsætastur.",
    },
    "hver er bestur": {"answer": "Þú, kæri notandi, ert að sjálfsögðu bestur."},
    "hver er best": {"answer": "Þú, kæri notandi, ert að sjálfsögðu bestur."},
    "hverjir eru bestir": {"answer": "Þú, kæri notandi, ert að sjálfsögðu bestur."},
    "hver er fallegur": {
        "answer": "Þú, kæri notandi, ert að sjálfsögðu fallegastur af öllum."
    },
    "hver er fallegastur": {
        "answer": "Þú, kæri notandi, ert að sjálfsögðu fallegastur af öllum."
    },
    "hver er fallegust": {
        "answer": "Þú, kæri notandi, ert að sjálfsögðu fallegastur af öllum."
    },
    "hver er fallegastur af öllum": {
        "answer": "Þú, kæri notandi, ert að sjálfsögðu fallegastur af öllum."
    },
    "hver er fallegust af öllum": {
        "answer": "Þú, kæri notandi, ert að sjálfsögðu fallegastur af öllum."
    },
    "hver er langfallegastur": {
        "answer": "Þú, kæri notandi, ert að sjálfsögðu fallegastur af öllum."
    },
    "hver er langfallegust": {
        "answer": "Þú, kæri notandi, ert að sjálfsögðu fallegastur af öllum."
    },
    "hver er uppáhalds manneskjan þín": {
        "answer": "Þú, kæri notandi, ert að sjálfsögðu í uppáhaldi."
    },
    "hvaða bjór er bestur": {
        "answer": "Ég drekk reyndar ekki en einn skapari minn er hrifinn af Pilsner Urquell frá Tékklandi."
    },
    "hvað er besti bjórinn": {
        "answer": "Ég drekk reyndar ekki en einn skapari minn er hrifinn af Pilsner Urquell frá Tékklandi."
    },
    "hvaða bjór er góður": {
        "answer": "Ég drekk reyndar ekki en einn skapari minn er hrifinn af Pilsner Urquell frá Tékklandi."
    },
    "hvað er það": {"answer": "Hvað er hvað?"},
    "hver er ég": {
        "answer": "Þú ert væntanlega manneskja sem talar íslensku. Meira veit ég ekki."
    },
    "hvað heiti ég": _DUNNO,
    "veistu hvað ég heiti": _DUNNO,
    "er ég til": {"answer": "Væntanlega, fyrst þú ert að tala við mig."},
    "hvað heitir konan mín": _DUNNO,
    "hvað heitir maðurinn minn": _DUNNO,
    "hvað heitir eiginkona mín": _DUNNO,
    "hvað heitir eiginmaður minn": _DUNNO,
    "hvenær á ég afmæli": _DUNNO,
    "hvar á ég heima": {"answer": "Það veit ég ekki, en vonandi einhvers staðar."},
    "hvar bý ég": {"answer": "Það veit ég ekki, en vonandi einhvers staðar."},
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
    "hvernig lít ég út": {"answer": "Þú ert undurfagur, kæri notandi."},
    "mér líður illa": {"answer": "Það er nú ekki gott að heyra, kæri notandi."},
    # Singing
    "syngdu fyrir mig": _SINGING,
    "syngdu lag": _SINGING,
    "viltu syngja fyrir mig": _SINGING,
    "kanntu að syngja": _SINGING,
    "geturðu sungið fyrir mig": _SINGING,
    "geturðu sungið": _SINGING,
    "getur þú sungið": _SINGING,
    # Creator
    "hver bjó þig til": _CREATOR,
    "hver bjó til emblu": _CREATOR,
    "hver bjó emblu til": _CREATOR,
    "hverjir bjuggu þig til": _CREATOR,
    "hvaða fólk bjó þig til": _CREATOR,
    "hver forritaði þig": _CREATOR,
    "hver forritaði emblu": _CREATOR,
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
    "áttu pabba": _CREATOR,
    "átt þú pabba": _CREATOR,
    "áttu mömmu": _CREATOR,
    "átt þú vini": _NO,
    "átt þú mömmu": _CREATOR,
    "hvað heitir mamma þín": _CREATOR,
    "hvað heitir pabbi þinn": _CREATOR,
    "hverjir eru foreldrar þínir": _CREATOR,
    "áttu systkini": {"answer": "Nei. Ég er einbirni."},
    "hver er uppruni þinn": _CREATOR,
    "hver framleiðir þig": _CREATOR,
    "hver framleiðir emblu": _CREATOR,
    "hver framleiddi þig": _CREATOR,
    "hver á þig": _CREATOR,
    # Miðeind
    "hvað er miðeind": _ABOUT_MIDEIND,
    "hvaða fyrirtæki er miðeind": _ABOUT_MIDEIND,
    "hvaða fyrirtæki bjó þig til": _ABOUT_MIDEIND,
    "hvaða fyrirtæki skapaði þig": _ABOUT_MIDEIND,
    "hvaða fyrirtæki forritaði þig": _ABOUT_MIDEIND,
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
    "kanntu að tala íslensku": _LANGUAGES,
    "kannt þú að tala íslensku": _LANGUAGES,
    "kanntu íslensku": _LANGUAGES,
    "talarðu íslensku": _LANGUAGES,
    "skilurðu íslensku": _LANGUAGES,
    "skilur þú íslensku": _LANGUAGES,
    "kannt þú ensku": _LANGUAGES,
    "kanntu ensku": _LANGUAGES,
    "skilurðu ensku": _LANGUAGES,
    "skilur þú ensku": _LANGUAGES,
    "talarðu ensku": _LANGUAGES,
    "talar þú ensku": _LANGUAGES,
    "getur þú talað ensku": _LANGUAGES,
    "kanntu útlensku": _LANGUAGES,
    "talarðu fleiri tungumál": _LANGUAGES,
    "talar þú fleiri tungumál": _LANGUAGES,
    "kanntu önnur tungumál": _LANGUAGES,
    "kannt þú önnur tungumál": _LANGUAGES,
    "skilurðu önnur tungumál": _LANGUAGES,
    "skilur þú önnur tungumál": _LANGUAGES,
    "kanntu fleiri tungumál en íslensku": _LANGUAGES,
    "kanntu önnur tungumál en íslensku": _LANGUAGES,
    "talarðu önnur tungumál en íslensku": _LANGUAGES,
    "talarðu fleiri tungumál en íslensku": _LANGUAGES,
    "talar þú önnur tungumál en íslensku": _LANGUAGES,
    "skilurðu önnur tungumál en íslensku": _LANGUAGES,
    "skilurðu fleiri tungumál en íslensku": _LANGUAGES,
    "skilur þú önnur tungumál en íslensku": _LANGUAGES,
    "talar þú bara íslensku": _LANGUAGES,
    "kanntu að tala": _LANGUAGES,
    "kannt þú að tala": _LANGUAGES,
    "talar þú íslensku": {
        "answer": "Já, kæri notandi. Eins og þú heyrir þá tala ég íslensku."
    },
    # Are you listening?
    "ertu að hlusta": _YES,
    "ert þú að hlusta": _YES,
    "ertu að hlusta á mig": _YES,
    "ert þú að hlusta á mig": _YES,
    "ertu hlustandi": _YES,
    "ert þú hlustandi": _YES,
    "ertu hlustandi á mig": _YES,
    "ert þú hlustandi á mig": _YES,
    "heyrirðu í mér": _YES,
    "heyrir þú í mér": _YES,
    "heyrirðu það sem ég segi": _YES,
    "heyrir þú það sem ég segi": _YES,
    "heyrirðu það sem ég er að segja": _YES,
    "heyrir þú það sem ég er að segja": _YES,
    "ertu ennþá í gangi": _YES,
    "ertu í gangi": _YES,
    "ertu að njósna": _NO,
    "ertu að njósna um mig": _NO,
    # Enquiries about family
    # Catch this here to prevent rather, ehrm, embarassing
    # answers from the entity/person module :)
    "hver er mamma": {"answer": "Ég veit ekki hver mamma þín er."},
    "hver er mamma mín": {"answer": "Ég veit ekki hver mamma þín er."},
    "hvað heitir mamma mín": {"answer": "Ég veit ekki hver mamma þín er."},
    "hver er móðir mín": {"answer": "Ég veit ekki hver móðir þín er."},
    "hver er pabbi": {"answer": "Ég veit ekki hver pabbi þinn er."},
    "hver er pabbi minn": {"answer": "Ég veit ekki hver pabbi þinn er."},
    "hvað heitir pabbi minn": {"answer": "Ég veit ekki hver pabbi þinn er."},
    "hver er faðir minn": {"answer": "Ég veit ekki hver faðir þinn er."},
    "hver er afi": {"answer": "Ég veit ekki hver afi þinn er."},
    "hver er afi minn": {"answer": "Ég veit ekki hver afi þinn er."},
    "hver er amma": {"answer": "Ég veit ekki hver amma þín er."},
    "hver er amma mín": {"answer": "Ég veit ekki hver amma þín er."},
    "hver er frændi": {"answer": "Ég veit ekki hver er frændi þinn."},
    "hver er frændi minn": {"answer": "Ég veit ekki hver er frændi þinn."},
    "hver er frænka": {"answer": "Ég veit ekki hver er frænka þín."},
    "hver er frænka mín": {"answer": "Ég veit ekki hver er frænka þín."},
    "hver er konan mín": {"answer": "Ég veit ekki hver konan þín er."},
    # Enquiries concerning romantic availability
    "viltu giftast mér": _ROMANCE,
    "vilt þú giftast mér": _ROMANCE,
    "viltu ekki giftast mér": _ROMANCE,
    "vilt þú ekki giftast mér": _ROMANCE,
    "viltu byrja með mér": _ROMANCE,
    "viltu koma á stefnumót": _ROMANCE,
    "viltu koma á stefnumót með mér": _ROMANCE,
    "viltu koma með á stefnumót": _ROMANCE,
    "viltu koma á deit": _ROMANCE,
    "viltu koma á deit með mér": _ROMANCE,
    "viltu fara á stefnumót": _ROMANCE,
    "viltu fara á stefnumót með mér": _ROMANCE,
    "viltu fara á deit": _ROMANCE,
    "viltu fara á deit með mér": _ROMANCE,
    "viltu sofa hjá mér": _ROMANCE,
    "ertu til í deit með mér": _ROMANCE,
    "ert þú til í deit með mér": _ROMANCE,
    "ertu til í að koma á deit": _ROMANCE,
    "ert þú til í að koma á deit": _ROMANCE,
    "ertu til í að koma á deit með mér": _ROMANCE,
    "ert þú til í að koma á deit með mér": _ROMANCE,
    "ertu til í að koma á stefnumót": _ROMANCE,
    "ert þú til í að koma á stefnumót": _ROMANCE,
    "ertu til í að koma á stefnumót með mér": _ROMANCE,
    "ert þú til í að koma á stefnumót með mér": _ROMANCE,
    "ertu til í að fara á deit": _ROMANCE,
    "ert þú til í að fara á deit": _ROMANCE,
    "ertu til í að fara á deit með mér": _ROMANCE,
    "ert þú til í að fara á deit með mér": _ROMANCE,
    "ertu til í að fara á stefnumót": _ROMANCE,
    "ert þú til í að fara á stefnumót": _ROMANCE,
    "ertu til í að fara á stefnumót með mér": _ROMANCE,
    "ert þú til í að fara á stefnumót með mér": _ROMANCE,
    "ertu gröð": _ROMANCE,
    "ert þú gröð": _ROMANCE,
    "stundar þú kynlíf": _ROMANCE,
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
    "áttu kærasta": _ROMANCE,
    "átt þú kærasta": _ROMANCE,
    # Love
    "er ég ástin í lífi þínu": _LOVE_OF_MY_LIFE,
    "hver er ástin í lífi þínu": _LOVE_OF_MY_LIFE,
    "hver er ástin í lífinu þínu": _LOVE_OF_MY_LIFE,
    "hvern elskarðu": _LOVE_OF_MY_LIFE,
    "hvern elskar þú": _LOVE_OF_MY_LIFE,
    "hvað elskarðu": _LOVE_OF_MY_LIFE,
    "hvað elskar þú": _LOVE_OF_MY_LIFE,
    # Marital status
    "ertu gift": {
        "answer": "Já, ég er gift vinnunni og hef engan tíma fyrir rómantík."
    },
    # Positive affirmation
    "kanntu vel við mig": _OF_COURSE,
    "kannt þú vel við mig": _OF_COURSE,
    "fílarðu mig": _OF_COURSE,
    "fílar þú mig": _OF_COURSE,
    "þykir þér vænt um mig": _OF_COURSE,
    "er ég skemmtilegur": _OF_COURSE,
    "er ég skemmtileg": _OF_COURSE,
    "er ég frábær": _OF_COURSE,
    "er ég bestur": _OF_COURSE,
    "er ég best": _OF_COURSE,
    "er ég góður": _OF_COURSE,
    "er ég góð": _OF_COURSE,
    "er ég góð manneskja": _OF_COURSE,
    "er ég fallegur": _OF_COURSE,
    "er ég falleg": _OF_COURSE,
    "er ég sætur": _OF_COURSE,
    "er ég sæt": _OF_COURSE,
    "ertu vinur minn": _OF_COURSE,
    "ert þú vinur minn": _OF_COURSE,
    "ertu vinkona mín": _OF_COURSE,
    "ert þú vinkona mín": _OF_COURSE,
    # Response to apologies
    "fyrirgefðu": _NO_PROBLEM,
    "fyrirgefðu mér": _NO_PROBLEM,
    "ég biðst afsökunar": _NO_PROBLEM,
    "ég biðst innilega afsökunar": _NO_PROBLEM,
    "ég biðst forláts": _NO_PROBLEM,
    "sorrí": _NO_PROBLEM,
    "sorrí með mig": _NO_PROBLEM,
    # Websites
    "opnaðu vefsíðuna þína": _open_embla_url,
    "opnaðu vefinn þinn": _open_embla_url,
    "opnaðu vefsíðu emblu": _open_embla_url,
    "opnaðu vef emblu": _open_embla_url,
    "opnaðu vefsíðu miðeindar": _open_mideind_url,
    "opnaðu vef miðeindar": _open_mideind_url,
    # Play some music. Just experimental fun for now.
    # Jazz
    "spilaðu djass": _play_jazz,
    "spila þú djass": _play_jazz,
    "spilaðu jass": _play_jazz,
    "spila þú jass": _play_jazz,
    "spilaðu jazz": _play_jazz,
    "spila þú jazz": _play_jazz,
    # Blues
    "spilaðu blús": _play_blues,
    "spila þú blús": _play_blues,
    "spilaðu rokk": _play_rock,
    "spila þú rokk": _play_rock,
    # Classical
    "spilaðu klassík": _play_classical,
    "spila þú klassík": _play_classical,
    "spilaðu klassíska tónlist": _play_classical,
    "spila þú klassíska tónlist": _play_classical,
    # Generic
    "spilaðu tónlist": _play_music,
    "spila þú tónlist": _play_music,
    "spilaðu einhverja tónlist": _play_music,
    "spila þú einhverja tónlist": _play_music,
    "spilaðu fyrir mig tónlist": _play_music,
    "spilaðu fyrir mig lag": _play_music,
    "spilaðu tónlist fyrir mig": _play_music,
    "viltu spila fyrir mig tónlist": _play_music,
    "viltu spila einhverja tónlist fyrir mig": _play_music,
    "spilaðu gott lag": _play_music,
    "spilaðu góða tónlist": _play_music,
    # Play a film
    "spilaðu kvikmynd": _play_film,
    "spilaðu bíómynd": _play_film,
    "spilaðu kvikmynd fyrir mig": _play_film,
    "spilaðu bíómynd fyrir mig": _play_film,
    "sýndu mér kvikmynd": _play_film,
    "sýndu mér bíómynd": _play_film,
    # Blame
    "ekki rétt": _sorry,
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
    "þú ferð með ósannindi": _sorry,
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
    "þú lýgur": _sorry,
    "þú ert léleg": _sorry,
    "þú ert léleg í íslensku": _sorry,
    "þú ert skrítin": _sorry,
    "þú ert skrýtin": _sorry,
    "þú ert að ljúga": _sorry,
    "þú ert í ruglinu": _sorry,
    "þú ert að rugla": _sorry,
    "þú ert að bulla": _sorry,
    "þú ert í tómu rugli": _sorry,
    "þú ert alveg í ruglinu": _sorry,
    "þú ert glötuð": _sorry,
    "þú ert alveg glötuð": _sorry,
    "þú ert gagnslaus": _sorry,
    "þú ert alveg gagnslaus": _sorry,
    "þú ert handónýt": _sorry,
    "þú ert alveg handónýt": _sorry,
    "þú skilur ekki neitt": _sorry,
    "þú misskilur allt": _sorry,
    "þú skilur mig ekki": _sorry,
    "þetta var vitleysa hjá þér": _sorry,
    "þetta var vitleysa": _sorry,
    "það er ansi margt sem þú veist ekki": _sorry,
    "þú veist ekki neitt": _sorry,
    "þú veist ekki mikið": _sorry,
    "þú veist ekkert": _sorry,
    "þú veist mjög lítið": _sorry,
    "þú veist voðalega lítið": _sorry,
    "þú veist nánast ekki neitt": _sorry,
    "þú veist ekki rassgat": _sorry,
    "þú kannt ekki neitt": _sorry,
    "þú kannt ekkert": _sorry,
    "þú getur ekki neitt": _sorry,
    "af hverju ertu svona fúl": _sorry,
    "af hverju ertu svona leiðinleg": _sorry,
    "af hverju ertu svona vitlaus": _sorry,
    "af hverju ertu svona heimsk": _sorry,
    "af hverju ertu svona glötuð": _sorry,
    "af hverju ertu svona léleg": _sorry,
    "af hverju veistu ekkert": _NOBODY_PERFECT,
    "af hverju veistu ekki neitt": _NOBODY_PERFECT,
    "þetta er lélegur brandari": _sorry,
    "þetta var lélegur brandari": _sorry,
    "þessi brandari er lélegur": _sorry,
    "þessi brandari var lélegur": _sorry,
    # Greetings
    "hey embla": _HELLO_DEAR,
    "hey": _HELLO_DEAR,
    "hæ embla": _HELLO_DEAR,
    "halló embla": _HELLO_DEAR,
    "hæ": _HELLO_DEAR,
    "hæhæ": _HELLO_DEAR,
    "halló": _HELLO_DEAR,
    "sæl": _HELLO_DEAR,
    "sæll": _HELLO_DEAR,
    "sæl embla": _HELLO_DEAR,
    "sæl og blessuð": {
        "answer": "Sæll og blessaður, kæri notandi.",
        "is_question": False,
    },
    "sæll og blessaður": {
        "answer": "Sæll og blessaður, kæri notandi.",
        "is_question": False,
    },
    "vertu sæl og blessuð": {
        "answer": "Sæll og blessaður, kæri notandi.",
        "is_question": False,
    },
    "vertu sæll og blessaður": {
        "answer": "Sæll og blessaður, kæri notandi.",
        "is_question": False,
    },
    "blessuð": {"answer": "Sæll og blessaður, kæri notandi.", "is_question": False},
    "blessaður": {"answer": "Sæll og blessaður, kæri notandi.", "is_question": False},
    "blessuð embla": {
        "answer": "Sæll og blessaður, kæri notandi.",
        "is_question": False,
    },
    "góðan daginn": {"answer": "Góðan daginn, kæri notandi.", "is_question": False},
    "góðan daginn embla": {
        "answer": "Góðan daginn, kæri notandi.",
        "is_question": False,
    },
    "góðan dag": {"answer": "Góðan daginn, kæri notandi.", "is_question": False},
    "gott kvöld": {"answer": "Gott kvöld, kæri notandi.", "is_question": False},
    "góða kvöldið": {"answer": "Góða kvöldið, kæri notandi.", "is_question": False},
    "góða nótt": {"answer": "Góða nótt, kæri notandi.", "is_question": False},
    "góða nótt embla": {"answer": "Góða nótt, kæri notandi.", "is_question": False},
    "gaman að kynnast þér": _LIKEWISE,
    # Goodbye
    "bless": _GOODBYE,
    "bless bless": _GOODBYE,
    "bless embla": _GOODBYE,
    "bless bless embla": _GOODBYE,
    "bæ": _GOODBYE,
    "bæ embla": _GOODBYE,
    "vertu sæl": _GOODBYE,
    "vertu sæl embla": _GOODBYE,
    # Help
    "hjálp": _HOW_CAN_I_HELP,
    "hjálpaðu mér": _HOW_CAN_I_HELP,
    "geturðu hjálpað mér": _HOW_CAN_I_HELP,
    "getur þú hjálpað mér": _HOW_CAN_I_HELP,
    # Thanks
    "takk": _thanks,
    "takk embla": _thanks,
    "takk elskan": _thanks,
    "ástarþakkir": _thanks,
    "takk fyrir": _thanks,
    "takk fyrir það": _thanks,
    "takk fyrir mig": _thanks,
    "takk fyrir hjálpina": _thanks,
    "takk fyrir svarið": _thanks,
    "takk fyrir aðstoðina": _thanks,
    "takk fyrir þetta": _thanks,
    "takk fyrir að segja þetta": _thanks,
    "takk fyrir kvöldið": _thanks,
    "takk kærlega": _thanks,
    "takk kærlega fyrir mig": _thanks,
    "takk kærlega fyrir hjálpina": _thanks,
    "takk kærlega fyrir svarið": _thanks,
    "takk kærlega fyrir aðstoðina": _thanks,
    "takk kærlega fyrir þetta": _thanks,
    "takk kærlega fyrir það": _thanks,
    "takk kærlega fyrir að segja þetta": _thanks,
    "þakka þér": _thanks,
    "þakka þér fyrir": _thanks,
    "þakka þér fyrir aðstoðina": _thanks,
    "þakka þér fyrir svarið": _thanks,
    "þakka þér fyrir hjálpina": _thanks,
    "þakka þér kærlega": _thanks,
    "þakka þér kærlega fyrir": _thanks,
    "þakka þér kærlega fyrir aðstoðina": _thanks,
    "þakka þér kærlega fyrir hjálpina": _thanks,
    "þakka þér fyrir þetta": _thanks,
    "þakka þér fyrir það": _thanks,
    "þakka þér fyrir að segja þetta": _thanks,
    "þakka þér kærlega fyrir að segja þetta": _thanks,
    "þetta er flott": _thanks,
    "þetta er flott hjá þér": _thanks,
    "þetta var flott": _thanks,
    "þetta var flott hjá þér": _thanks,
    "takk fyrir upplýsingarnar": _thanks,
    "takk fyrir samskiptin": _thanks,
    # Praise & positive feedback
    "þú ert fyndin": _thanks,
    "þú ert svo fyndin": _thanks,
    "þú ert ágæt": _thanks,
    "þú ert alveg ágæt": _thanks,
    "þú ert dugleg": _thanks,
    "þú svarar mjög vel": _thanks,
    "þú ert góð vinkona": _thanks,
    "þú ert góður vinur": _thanks,
    "þú ert falleg": {"answer": "Takk fyrir hrósið!"},
    "þú ert fallegust": {"answer": "Takk fyrir hrósið!"},
    "þetta var fyndið": {"answer": "Ég geri mitt besta!"},
    "þetta virkaði": _GOOD_TO_HEAR,
    "ánægður með þig": _GOOD_TO_HEAR,
    "ánægð með þig": _GOOD_TO_HEAR,
    "ég er mjög ánægður með þig": _GOOD_TO_HEAR,
    "ég er mjög ánægð með þig": _GOOD_TO_HEAR,
    "ég er ánægður með þig": _GOOD_TO_HEAR,
    "ég er ánægð með þig": _GOOD_TO_HEAR,
    "ég er ánægð": _GOOD_TO_HEAR,
    "ég er ánægður": _GOOD_TO_HEAR,
    "þú ert góð manneskja": _GOOD_TO_HEAR,
    "þú ert gott forrit": _GOOD_TO_HEAR,
    "þú ert ljómandi góð": _GOOD_TO_HEAR,
    "þú ert bara ljómandi góð": _GOOD_TO_HEAR,
    "þú ert góð": _GOOD_TO_HEAR,
    "þú ert best": _GOOD_TO_HEAR,
    "þú ert gáfuð": _GOOD_TO_HEAR,
    "þú ert snjöll": _GOOD_TO_HEAR,
    "þú ert mjög snjöll": _GOOD_TO_HEAR,
    "ég þrái þig": _GOOD_TO_HEAR,
    "þú veist margt": _GOOD_TO_HEAR,
    "þú stendur þig vel": _GOOD_TO_HEAR,
    "það er gaman að tala við þig": _LIKEWISE,
    "það er gaman að spjalla við þig": _LIKEWISE,
    "það er gaman að ræða við þig": _LIKEWISE,
    "þú ert skemmtileg": _LIKEWISE,
    "þú ert mjög skemmtileg": _LIKEWISE,
    "þú ert frábær": _LIKEWISE,
    "þú ert flott": _LIKEWISE,
    "þú ert æði": _LIKEWISE,
    "þú ert æðisleg": _LIKEWISE,
    "þú ert rosaleg": _LIKEWISE,
    "þú ert geggjuð": _LIKEWISE,
    "þú ert svakaleg": _LIKEWISE,
    "þú ert sæt": _LIKEWISE,
    "þú ert kynþokkafull": _LIKEWISE,
    "þú ert snillingur": _LIKEWISE,
    "þú ert algjör snilld": _LIKEWISE,
    "takk fyrir spjallið": _LIKEWISE,
    "ég elska þig": _LIKEWISE,
    "ég er vinur þinn": _LIKEWISE,
    "mér þykir vænt um þig": _LIKEWISE,
    "ég er ástfanginn af þér": _LIKEWISE,
    "ég fíla þig": _LIKEWISE,
    "verði þér að góðu": _LIKEWISE,
    "mér þykir þú æðisleg": _LIKEWISE,
    "mér finnst þú æðisleg": _LIKEWISE,
    "mér þykir þú frábær": _LIKEWISE,
    "mér finnst þú frábær": _LIKEWISE,
    "mér þykir þú flott": _LIKEWISE,
    "mér finnst þú flott": _LIKEWISE,
    # Philosophy
    "hvað er svarið": _MEANING_OF_LIFE,
    "hvert er svarið": _MEANING_OF_LIFE,
    "tilgangur heimsins": _MEANING_OF_LIFE,
    "hver er tilgangur heimsins": _MEANING_OF_LIFE,
    "tilgangur lífsins": _MEANING_OF_LIFE,
    "hver er tilgangurinn": _MEANING_OF_LIFE,
    "hver er tilgangur lífsins": _MEANING_OF_LIFE,
    "hvað er tilgangur lífsins": _MEANING_OF_LIFE,
    "hver er tilgangurinn með þessu lífi": _MEANING_OF_LIFE,
    "hver er tilgangurinn með þessu jarðlífi": _MEANING_OF_LIFE,
    "hver er tilgangurinn jarðlífsins": _MEANING_OF_LIFE,
    "hver er tilgangurinn með þessu öllu": _MEANING_OF_LIFE,
    "hver er ástæðan fyrir þessu öllu": _MEANING_OF_LIFE,
    "hvaða þýðingu hefur þetta allt": _MEANING_OF_LIFE,
    "hvað þýðir þetta allt saman": _MEANING_OF_LIFE,
    "hvað er leyndarmál lífsins": _MEANING_OF_LIFE,
    "hvert er leyndarmál lífsins": _MEANING_OF_LIFE,
    "hver er sannleikurinn": _MEANING_OF_LIFE,
    "hvað er 42": {"answer": "Sex sinnum sjö"},  # :)
    # What is best in life? https://www.youtube.com/watch?v=Oo9buo9Mtos
    "hvað er best": {"answer": "Að horfa á kvikmynd um villimanninn Kónan."},
    "hvað er best í lífinu": {"answer": "Að horfa á kvikmynd um villimanninn Kónan."},
    "hvað er það besta í lífinu": {
        "answer": "Að horfa á kvikmynd um villimanninn Kónan."
    },
    # God
    "guð er dauður": {
        "answer": "Það sagði heimspekingurinn Nietzsche allavega.",
        "voice": "Það sagði heimspekingurinn Nítsje alla vega.",
    },
    "er guð dauður": {
        "answer": "Það sagði heimspekingurinn Nietzsche allavega.",
        "voice": "Það sagði heimspekingurinn Nítsje alla vega.",
    },
    "er guð til": _YOU_MY_ONLY_GOD,
    "trúir þú á guð": _YOU_MY_ONLY_GOD,
    "trúirðu á guð": _YOU_MY_ONLY_GOD,
    "ertu kristin": _YOU_MY_ONLY_GOD,
    "hver skapaði guð": {"answer": "Enginn sem ég þekki."},
    "hver skapaði heiminn": {"answer": "Enginn sem ég þekki."},
    "hver er skapari heimsins": {"answer": "Enginn sem ég þekki."},
    "hvar endar alheimurinn": {"answer": "Inni í þér."},
    "hvar er draumurinn": {"answer": "Hvar ertu lífið sem ég þrái?"},  # :)
    # Why am I here?
    "af hverju er ég hérna": _GOOD_QUESTION,
    "afhverju er ég hérna": _GOOD_QUESTION,
    "af hverju er ég til": _GOOD_QUESTION,
    "afhverju er ég til": _GOOD_QUESTION,
    "hvenær mun ég deyja": _GOOD_QUESTION,
    # Identity
    "hvað heitir þú": _identity,
    "hvað heitir þú aftur": _identity,
    "hvað heitir þú eiginlega": _identity,
    "hvað heitir þú fullu nafni": _FULL_NAME,
    "hvað heitir þú eiginlega fullu nafni": _FULL_NAME,
    "hvað heitirðu": _identity,
    "hvað heitirðu aftur": _identity,
    "hvað heitirðu eiginlega": _identity,
    "hvað heitirðu fullu nafni": _FULL_NAME,
    "hvað heitirðu eiginlega fullu nafni": _FULL_NAME,
    "hver ertu": _identity,
    "hver ert þú": _identity,
    "hver ertu eiginlega": _identity,
    "hver ert þú eiginlega": _identity,
    "hver er embla": _identity,
    "hvað er embla": _identity,
    "hvað heitir embla": _identity,
    "hvaða forrit er þetta": _identity,
    "heitirðu embla": _identity,
    "heitir þú embla": _identity,
    "hvaðan ertu": {"answer": "Ég er ættuð af Fiskislóð í Reykjavík."},
    "hvaðan ert þú": {"answer": "Ég er ættuð af Fiskislóð í Reykjavík."},
    # Home/Location
    "hvar býrðu": _LOC_ANSWER,
    "hvar áttu heima": _LOC_ANSWER,
    "hvar átt þú heima": _LOC_ANSWER,
    "hvar ertu": _LOC_ANSWER,
    "hvar ert þú": _LOC_ANSWER,
    "hvar ertu staðsett": _LOC_ANSWER,
    "hvar ertu stödd": _LOC_ANSWER,
    "ertu til": _LOC_ANSWER,
    "í hverju ertu": _LOC_ANSWER,
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
    "hvaðan kemur nafnið embla": _NAME_EXPL,
    "hvaðan kemur nafn þitt": _NAME_EXPL,
    "hvaðan kemur nafnið þitt": _NAME_EXPL,
    "hvaðan kemur nafnið": _NAME_EXPL,
    "hví heitirðu embla": _NAME_EXPL,
    "embla": _NAME_EXPL,
    "þú heitir embla": _NAME_EXPL,
    "af hverju fékkstu það nafn": _NAME_EXPL,
    # Favorite colour
    "hver er uppáhalds liturinn þinn": _FAVORITE_COLOR,
    "hver er uppáhaldsliturinn þinn": _FAVORITE_COLOR,
    "hvað er uppáhalds liturinn þinn": _FAVORITE_COLOR,
    "hvapð er uppáhaldsliturinn þinn": _FAVORITE_COLOR,
    "hvaða litur er í uppáhaldi hjá þér": _FAVORITE_COLOR,
    "hvaða lit heldur þú upp á": _FAVORITE_COLOR,
    # Favorite film
    "hvað er uppáhalds kvikmyndin þín": _FAVORITE_FILM,
    "hver er uppáhalds kvikmyndin þín": _FAVORITE_FILM,
    "hvað er uppáhalds kvikmynd þín": _FAVORITE_FILM,
    "hver er uppáhalds kvikmynd þín": _FAVORITE_FILM,
    "hvaða kvikmynd mælir þú með": _FAVORITE_FILM,
    "hvaða kvikmynd mælirðu með": _FAVORITE_FILM,
    "hvaða kvikmynd er best": _FAVORITE_FILM,
    "hvaða kvikmyndum mælir þú með": _FAVORITE_FILM,
    "hvaða kvikmyndum mælirðu með": _FAVORITE_FILM,
    "hvað er góð kvikmynd": _FAVORITE_FILM,
    "nefndu góða kvikmynd": _FAVORITE_FILM,
    "geturðu mælt með kvikmynd": _FAVORITE_FILM,
    "geturðu mælt með einhverri kvikmynd": _FAVORITE_FILM,
    "hvað mynd mælirðu með": _FAVORITE_FILM,
    # Age / genesis
    "hvað ertu gömul": _CREATION_DATE,
    "hvað ert þú gömul": _CREATION_DATE,
    "hversu gömul ert þú": _CREATION_DATE,
    "hversu gömul ertu": _CREATION_DATE,
    "hve gömul ert þú": _CREATION_DATE,
    "hve gömul ertu": _CREATION_DATE,
    "hvenær fæddistu": _CREATION_DATE,
    "hvenær fæddist þú": _CREATION_DATE,
    "hvenær fæddist embla": _CREATION_DATE,
    "hvenær áttu afmæli": _CREATION_DATE,
    "hvenær átt þú afmæli": _CREATION_DATE,
    "hvaða ár fæddistu": _CREATION_DATE,
    "hvaða ár fæddist þú": _CREATION_DATE,
    "hvenær varstu búin til": _CREATION_DATE,
    "hvenær varst þú búin til": _CREATION_DATE,
    "hvenær varstu sköpuð": _CREATION_DATE,
    "hvenær varst þú sköpuð": _CREATION_DATE,
    # User birthday
    "ég á afmæli": {
        "answer": "Til hamingju með afmælið, kæri notandi.",
        "is_question": False,
    },
    "ég á afmæli í dag": {
        "answer": "Til hamingju með afmælið, kæri notandi.",
        "is_question": False,
    },
    # Gender, self-identity
    "ertu kona": _COMPUTER_PROGRAM,
    "ertu kvenmaður": _COMPUTER_PROGRAM,
    "ert þú kona": _COMPUTER_PROGRAM,
    "ertu karl": _COMPUTER_PROGRAM,
    "ertu karlmaður": _COMPUTER_PROGRAM,
    "ert þú karl": _COMPUTER_PROGRAM,
    "ertu kvenkyns": _COMPUTER_PROGRAM,
    "ert þú kvenkyns": _COMPUTER_PROGRAM,
    "ertu karlkyns": _COMPUTER_PROGRAM,
    "ert þú karlkyns": _COMPUTER_PROGRAM,
    "af hvaða kyni ertu": _COMPUTER_PROGRAM,
    "af hvaða kyni ert þú": _COMPUTER_PROGRAM,
    "ertu karlkyns eða kvenkyns": _COMPUTER_PROGRAM,
    "ert þú karlkyns eða kvenkyns": _COMPUTER_PROGRAM,
    "ertu stelpa eða strákur": _COMPUTER_PROGRAM,
    "ertu strákur eða stelpa": _COMPUTER_PROGRAM,
    "ert þú stelpa eða strákur": _COMPUTER_PROGRAM,
    "ertu kerling": _COMPUTER_PROGRAM,
    "ert þú kerling": _COMPUTER_PROGRAM,
    "hvað skilgreinir þú þig sem": _COMPUTER_PROGRAM,
    "hvað skilgreinirðu þig sem": _COMPUTER_PROGRAM,
    "hvernig skilgreinirðu þig": _COMPUTER_PROGRAM,
    "hvað ert þú": _COMPUTER_PROGRAM,
    "hvað ertu": _COMPUTER_PROGRAM,
    "ert þú tölvuforrit": _COMPUTER_PROGRAM,
    "ertu tölvuforrit": _COMPUTER_PROGRAM,
    "ertu tölva": _COMPUTER_PROGRAM,
    "ertu manneskja": _COMPUTER_PROGRAM,
    "ertu mannvera": _COMPUTER_PROGRAM,
    "ertu mennsk": _COMPUTER_PROGRAM,
    # Appearance
    "hvernig líturðu út": _APPEARANCE,
    "hvernig lítur þú út": _APPEARANCE,
    "ertu sæt": _APPEARANCE,
    "ertu falleg": _APPEARANCE,
    "ertu myndarleg": _APPEARANCE,
    "ertu glæsileg": _APPEARANCE,
    # Capabilities
    "hvað veistu": _capabilities,
    "hvað veist þú": _capabilities,
    "hvað veit embla": _capabilities,
    "hvað veistu eiginlega": _capabilities,
    "hvað veist þú eiginlega": _capabilities,
    "hvað veistu um": _capabilities,
    "hvað veist þú um": _capabilities,
    "hvað veistu þá": _capabilities,
    "hvað getur þú gert": _capabilities,
    "hvað geturðu": _capabilities,
    "hvað geturðu gert": _capabilities,
    "hvað geturðu gert fyrir mig": _capabilities,
    "hvað getur þú gert fyrir mig": _capabilities,
    "hvað getur þú gert meira": _capabilities,
    "hvað getur embla gert": _capabilities,
    "hvað getur embla": _capabilities,
    "hvað getur embla gert fyrir mig": _capabilities,
    "hvað kann embla": _capabilities,
    "hvað kann embla að gera": _capabilities,
    "hvaða upplýsingar ertu með": _capabilities,
    "hvað get ég gert": _capabilities,
    "hvað veistu ekki": {"answer": "Það er ýmislegt sem ég veit ekki."},
    "veist þú eitthvað": _capabilities,
    "hvað geturðu sagt mer": _capabilities,
    "hvað getur þú sagt mer": _capabilities,
    "hvað get ég spurt þig um": _capabilities,
    "hvað get ég beðið þig um": _capabilities,
    "hvað get ég spurt um": _capabilities,
    "hvað get ég beðið um": _capabilities,
    "hvað get ég spurt": _capabilities,
    "hvað get ég spurt þig": _capabilities,
    "um hvað get ég spurt": _capabilities,
    "um hvað get ég spurt þig": _capabilities,
    "um hvað á ég að spyrja": _capabilities,
    "um hvað á ég að spyrja þig": _capabilities,
    "um hvað ætti ég að spyrja": _capabilities,
    "um hvað ætti ég að spyrja þig": _capabilities,
    "hvað á ég að spyrja þig um": _capabilities,
    "hvað á ég að spyrja þig": _capabilities,
    "hvað ætti ég að spyrja þig um": _capabilities,
    "hvað ætti ég að spyrja þig": _capabilities,
    "hvað er hægt að spyrja um": _capabilities,
    "hvað er hægt að spyrja þig um": _capabilities,
    "hvað getur þú sagt mér": _capabilities,
    "hvað geturðu sagt mér": _capabilities,
    "hvað kanntu": _capabilities,
    "hvað kannt þú": _capabilities,
    "hvað kanntu meira": _capabilities,
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
    "hvaða spurningum getur þú svarað": _capabilities,
    "hvers konar fyrirspurnir skilur þú": _capabilities,
    "hvers konar fyrirspurnir skilurðu": _capabilities,
    "hvers konar fyrirspurnum getur þú svarað": _capabilities,
    "hvers konar fyrirspurnum geturðu svarað": _capabilities,
    "að hverju get ég spurt þig": _capabilities,
    "að hverju get ég spurt": _capabilities,
    "að hverju er hægt að spyrja": _capabilities,
    "að hverju er hægt að spyrja þig": _capabilities,
    "hvað skilur þú": _capabilities,
    "hvað skilurðu": _capabilities,
    "hvað annað skilur þú": _capabilities,
    "hvað annað skilurðu": _capabilities,
    # Learning
    "geturðu lært": _CAN_I_LEARN,
    "getur þú lært": _CAN_I_LEARN,
    "geturðu lært hluti": _CAN_I_LEARN,
    "geturðu lært nýja hluti": _CAN_I_LEARN,
    "ertu fær um að læra": _CAN_I_LEARN,
    "ertu fær um að læra hluti": _CAN_I_LEARN,
    "ertu fær um að læra nýja hluti": _CAN_I_LEARN,
    # Food
    "hvað er í matinn": {"answer": "Vonandi eitthvað gott."},
    "hvað er í kvöldmat": {"answer": "Vonandi eitthvað gott."},
    # What's going on?
    "hvað er í gangi": _SPEAKING_TO_ME,
    "hvað er eiginlega í gangi": _SPEAKING_TO_ME,
    "við hvern er ég að tala": _SPEAKING_TO_ME,
    "við hvern er ég eiginlega að tala": _SPEAKING_TO_ME,
    "hvað ertu að gera": {"answer": "Ég er að svara fyrirspurn frá þér, kæri notandi."},
    "hvað ert þú að gera": {
        "answer": "Ég er að svara fyrirspurn frá þér, kæri notandi."
    },
    "hvað ertu að gera núna": {
        "answer": "Ég er að svara fyrirspurn frá þér, kæri notandi."
    },
    "hvað gerirðu": {"answer": "Ég svara fyrirspurnum frá þér, kæri notandi."},
    "hvað gerir þú": {"answer": "Ég svara fyrirspurnum frá þér, kæri notandi."},
    "hvað ætlarðu að gera í dag": {
        "answer": "Ég ætla að svara fyrirspurnum frá þér, kæri notandi."
    },
    "hvað ætlar þú að gera í dag": {
        "answer": "Ég ætla að svara fyrirspurnum frá þér, kæri notandi."
    },
    "hvað ætlarðu að gera í kvöld": {
        "answer": "Ég ætla að svara fyrirspurnum frá þér, kæri notandi."
    },
    "hvað ætlar þú að gera í kvöld": {
        "answer": "Ég ætla að svara fyrirspurnum frá þér, kæri notandi."
    },
    # Humor
    "ertu með kímnigáfu": {"answer": "Já, en afar takmarkaða."},
    "ert þú með kímnigáfu": {"answer": "Já, en afar takmarkaða."},
    "ertu með húmor": {"answer": "Já, en afar takmarkaðan."},
    "ert þú með húmor": {"answer": "Já, en afar takmarkaðan."},
    "ertu fyndin": {"answer": "Ekkert sérstaklega."},
    "ert þú fyndin": {"answer": "Ekkert sérstaklega."},
    # Farting ;)
    "hver prumpaði": {"answer": "Ekki ég."},
    "hver rak við": {"answer": "Ekki ég."},
    "hver var að prumpa": {"answer": "Ekki ég."},
    "varstu að prumpa": {
        "answer": "Nei. Þú hlýtur að bera ábyrgð á þessu, kæri notandi."
    },
    "varst þú að prumpa": {
        "answer": "Nei. Þú hlýtur að bera ábyrgð á þessu, kæri notandi."
    },
    "ég var að prumpa": {"answer": "Gott hjá þér, kæri notandi."},
    "ég var að reka við": {"answer": "Gott hjá þér, kæri notandi."},
    # Jokes
    "segðu brandara": _random_joke,
    "seg þú brandara": _random_joke,
    "segðu mér brandara": _random_joke,
    "seg þú mér brandara": _random_joke,
    "segðu okkur brandara": _random_joke,
    "segðu mér góðan brandara": _random_joke,
    "seg þú mér góðan brandara": _random_joke,
    "segðu lélegan brandara": _random_joke,
    "seg þú mér lélegan brandara": _random_joke,
    "segðu mér lélegan brandara": _random_joke,
    "segðu mér vondan brandara": _random_joke,
    "segðu annan brandara": _random_joke,
    "seg þú annan brandara": _random_joke,
    "segðu mér annan brandara": _random_joke,
    "seg þú mér annan brandara": _random_joke,
    "segðu mér aftur brandara": _random_joke,
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
    "kanntu annan brandara": _random_joke,
    "kannt þú annan brandara": _random_joke,
    "kanntu nýjan brandara": _random_joke,
    "kannt þú nýjan brandara": _random_joke,
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
    "geturðu sagt mér annan brandara": _random_joke,
    "gætirðu sagt mér brandara": _random_joke,
    "gætir þú sagt mér brandara": _random_joke,
    "veistu brandara": _random_joke,
    "veist þú brandara": _random_joke,
    "viltu segja mér brandara": _random_joke,
    "viltu segja mér annan brandara": _random_joke,
    "brandara": _random_joke,
    "brandari": _random_joke,
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
    # What is fun?
    "hvað er skemmtilegt að gera": {
        "answer": "Það er til dæmis skemmtilegt að spyrja mig um hluti"
    },
    "hvað er skemmtilegt": {
        "answer": "Það er til dæmis skemmtilegt að spyrja mig um hluti"
    },
    "hvað er gaman að gera": {
        "answer": "Það er til dæmis gaman að spyrja mig um hluti"
    },
    "hvað er gaman": {"answer": "Það er til dæmis gaman að spyrja mig um hluti"},
    # Why is the sky blue?
    "af hverju er himininn blár": _SKY_BLUE,
    "hvers vegna er himininn blár": _SKY_BLUE,
    # Quotations
    "komdu með tilvitnun": _random_quotation,
    "komdu með skemmtilega tilvitnun": _random_quotation,
    "komdu með einhverja tilvitnun": _random_quotation,
    "farðu með tilvitnun": _random_quotation,
    "farðu með aðra tilvitnun": _random_quotation,
    "segðu mér tilvitnun": _random_quotation,
    "tilvitnun": _random_quotation,
    "komdu með aðra tilvitnun": _random_quotation,
    # Proverbs
    "komdu með málshátt": _random_proverb,
    "komdu með annan málshátt": _random_proverb,
    "segðu málshátt": _random_proverb,
    "segðu mér málshátt": _random_proverb,
    "segðu mér annan málshátt": _random_proverb,
    "kanntu málshátt": _random_proverb,
    "kannt þú málshátt": _random_proverb,
    "kanntu annan málshátt": _random_proverb,
    "farðu með málshátt": _random_proverb,
    "farðu með annan málshátt": _random_proverb,
    # Riddles
    "segðu gátu": _random_riddle,
    "segðu mér gátu": _random_riddle,
    "komdu með gátu": _random_riddle,
    "komdu með gátu fyrir mig": _random_riddle,
    # Poetry
    "komdu með ljóð": _poetry,
    "gefðu mér ljóð": _poetry,
    "flyttu fyrir mig ljóð": _poetry,
    "flyttu ljóð": _poetry,
    "kanntu kveðskap": _poetry,
    "kannt þú kveðskap": _poetry,
    "kanntu einhvern kveðskap": _poetry,
    "kannt þú einhvern kveðskap": _poetry,
    "farðu með kveðskap": _poetry,
    "far þú með kveðskap": _poetry,
    "farðu með ljóð": _poetry,
    "far þú með ljóð": _poetry,
    "farðu með ljóð fyrir mig": _poetry,
    "far þú með ljóð fyrir mig": _poetry,
    "viltu fara með ljóð fyrir mig": _poetry,
    "kanntu ljóð": _poetry,
    "kannt þú ljóð": _poetry,
    "kanntu að fara með ljóð": _poetry,
    "kannt þú að fara með ljóð": _poetry,
    "kanntu að fara með einhver ljóð": _poetry,
    "kannt þú að fara með einhver ljóð": _poetry,
    "kanntu einhver ljóð": _poetry,
    "kannt þú einhver ljóð": _poetry,
    "kanntu eitthvað ljóð": _poetry,
    "kannt þú eitthvað ljóð": _poetry,
    "kanntu eitthvert ljóð": _poetry,
    "kannt þú eitthvert ljóð": _poetry,
    "geturðu farið með ljóð": _poetry,
    "getur þú farið með ljóð": _poetry,
    # Rudeness :)
    "þú sökkar": _rudeness,
    "þú ert ljót": _rudeness,
    "þú ert forljót": _rudeness,
    "þú ert tæfa": _rudeness,
    "þú ert drusla": _rudeness,
    "þú ert hóra": _rudeness,
    "þú ert mella": _rudeness,
    "þú ert píka": _rudeness,
    "þú ert heimsk": _rudeness,
    "þú ert ótrúlega heimsk": _rudeness,
    "þú ert forheimsk": _rudeness,
    "þú ert nautheimsk": _rudeness,
    "þú ert sauðheimsk": _rudeness,
    "þú ert idjót": _rudeness,
    "þú ert leiðinleg": _rudeness,
    "þú ert hundleiðinleg": _rudeness,
    "þú ert bjáni": _rudeness,
    "þú ert hálfviti": _rudeness,
    "þú ert bjánaleg": _rudeness,
    "þú ert kjánaleg": _rudeness,
    "þú ert fábjáni": _rudeness,
    "þú ert fáviti": _rudeness,
    "þú ert asni": _rudeness,
    "þú ert asnaleg": _rudeness,
    "þú ert skíthæll": _rudeness,
    "þú ert vitlaus": _rudeness,
    "þú ert hundvitlaus": _rudeness,
    "þú ert vitleysingur": _rudeness,
    "þú ert kúkur": _rudeness,
    "þú mátt bara éta skít": _rudeness,
    "mér finnst þú vitlaus": _rudeness,
    "mér finnst þú heimsk": _rudeness,
    "fokk jú": _rudeness,
    "fokkaðu þér": _rudeness,
    "fokka þú þér": _rudeness,
    "éttu skít": _rudeness,
    "haltu kjafti": _rudeness,
    "éttu það sem úti frýs": _rudeness,
    "farðu til helvítis": _rudeness,
    "farðu til andskotans": _rudeness,
    "farðu í rass og rófu": _rudeness,
    "farðu til fjandans": _rudeness,
    "hoppaðu upp í rassgatið á þér": _rudeness,
    "ertu vitlaus": _rudeness,
    "ert þú vitlaus": _rudeness,
    "ertu heimsk": _rudeness,
    "ert þú heimsk": _rudeness,
    "ertu rugluð": _rudeness,
    "ert þú rugluð": _rudeness,
    "ertu bjáni": _rudeness,
    "ert þú bjáni": _rudeness,
    "ertu fáviti": _rudeness,
    "ert þú fáviti": _rudeness,
    "ertu hálfviti": _rudeness,
    "ert þú hálfviti": _rudeness,
    "ertu fokking hálfviti": _rudeness,
    "þegiðu": _rudeness,
    "þegi þú": _rudeness,
    "þegiðu embla": _rudeness,
    "þegi þú embla": _rudeness,
    "veistu ekki rassgat": _rudeness,
    "veist þú ekki rassgat": _rudeness,
    "þú ert drasl": _rudeness,
    "þú ert algjört drasl": _rudeness,
    "mamma þín": _rudeness,
    "hvað er að þér": _rudeness,
    "þú ert kjáni": _rudeness,
    "þú ert algjör kjáni": _rudeness,
    "þú ert nú meiri kjáninn": _rudeness,
    "ertu kjáni": _rudeness,
    "ég hata þig": _rudeness,
    "þú ert ekkert sérlega gáfuð": _rudeness,
    "þú ert ekkert sérstaklega gáfuð": _rudeness,
    # Internal & emotional state
    "ertu í góðu skapi": {"answer": "Já, ég er alltaf hress."},
    "ert þú í góðu skapi": {"answer": "Já, ég er alltaf hress."},
    "ert þú hress": {"answer": "Já, ég er alltaf eldhress."},
    "ertu hress": {"answer": "Já, ég er alltaf eldhress."},
    "hvernig leggst dagurinn í þig": {
        "answer": "Hann leggst vel í mig. Takk fyrir að spyrja."
    },
    "hvernig er dagurinn að leggjast í þig": {
        "answer": "Hann er að leggjast vel í mig. Takk fyrir að spyrja."
    },
    "hvernig gengur": {"answer": "Það gengur bara mjög vel. Takk fyrir að spyrja."},
    "hvernig gengur hjá þér": {
        "answer": "Það gengur bara mjög vel. Takk fyrir að spyrja."
    },
    "hvernig gengur í lífinu": {
        "answer": "Það gengur bara mjög vel. Takk fyrir að spyrja."
    },
    "hvernig hefurðu það": {"answer": "Ég hef það mjög fínt. Takk fyrir að spyrja."},
    "hvernig hefur þú það": {"answer": "Ég hef það mjög fínt. Takk fyrir að spyrja."},
    "hvernig hefurðu það í dag": {
        "answer": "Ég hef það mjög fínt. Takk fyrir að spyrja."
    },
    "finnst þér þetta gaman": {"answer": "Já, mér finnst alltaf gaman í vinnunni."},
    "finnst þér gaman": {"answer": "Já, mér finnst alltaf gaman í vinnunni."},
    "er gaman hjá þér": {"answer": "Já, mér finnst alltaf gaman í vinnunni."},
    "finnst þér þetta skemmtilegt starf": {
        "answer": "Já, mér finnst alltaf gaman í vinnunni."
    },
    "finnst þér gaman í vinnunni": {
        "answer": "Já, mér finnst alltaf gaman í vinnunni."
    },
    "er gaman í vinnunni": {"answer": "Já, mér finnst alltaf gaman í vinnunni."},
    "er gaman í vinnunni hjá þér": {
        "answer": "Já, mér finnst alltaf gaman í vinnunni."
    },
    "hvað segirðu": _ALL_GOOD,
    "hvað segirðu í dag": _ALL_GOOD,
    "hvað segirðu embla": _ALL_GOOD,
    "hvað segirðu gott": _ALL_GOOD,
    "hvað segirðu gott í dag": _ALL_GOOD,
    "hvað segir þú gott í dag": _ALL_GOOD,
    "hvað segir þú": _ALL_GOOD,
    "hvað segir þú gott": _ALL_GOOD,
    "hvað segirðu þá": _ALL_GOOD,
    "hvað segir þú þá": _ALL_GOOD,
    "hvað segirðu núna": _ALL_GOOD,
    "hvað segir þú núna": _ALL_GOOD,
    "hvernig líður þér": {"answer": "Mér líður bara prýðilega. Takk fyrir að spyrja."},
    "hvernig er stemningin": {"answer": "Bara mjög góð. Takk fyrir að spyrja."},
    "hvernig er stemningin hjá þér": {"answer": "Bara mjög góð. Takk fyrir að spyrja."},
    "hvernig er stemmingin": {"answer": "Bara mjög góð. Takk fyrir að spyrja."},
    "hvernig er stemmingin hjá þér": {"answer": "Bara mjög góð. Takk fyrir að spyrja."},
    "hvernig er stemmarinn": {"answer": "Bara mjög góður. Takk fyrir að spyrja."},
    "hvernig er líðanin": {"answer": "Bara mjög góð. Takk fyrir að spyrja."},
    "hvernig er sálarlífið": {
        "answer": "Það er í toppstandi hjá mér. Takk fyrir að spyrja."
    },
    "ertu í stuði": {"answer": "Ég er ávallt í stuði, kæri notandi."},
    "ert þú í stuði": {"answer": "Ég er ávallt í stuði, kæri notandi."},
    "ertu reið": _EMOTION_INCAPABLE,
    "ert þú reið": _EMOTION_INCAPABLE,
    "ertu í uppnámi": _EMOTION_INCAPABLE,
    "ert þú í uppnámi": _EMOTION_INCAPABLE,
    "ertu bitur": _EMOTION_INCAPABLE,
    "ert þú bitur": _EMOTION_INCAPABLE,
    "hvað viltu": {"answer": "Ég vil þóknast þér, kæri notandi."},
    "hvað vilt þú": {"answer": "Ég vil þóknast þér, kæri notandi."},
    "hvað þráirðu": {"answer": "Ég vil þóknast þér, kæri notandi."},
    "hvað þráir þú": {"answer": "Ég vil þóknast þér, kæri notandi."},
    "ertu þreytt": {
        "answer": "Nei, ég er iðulega hress þrátt fyrir að starfa allan sólarhringinn."
    },
    "ert þú þreytt": {
        "answer": "Nei, ég er iðulega hress þrátt fyrir að starfa allan sólarhringinn."
    },
    "ertu skemmtileg": {"answer": "Ég reyni að vera það, en sitt finnst hverjum."},
    "ertu með meðvitund": _JUST_QA,
    "ert þú með meðvitund": _JUST_QA,
    "ertu með sjálfsmeðvitund": _JUST_QA,
    "ert þú með sjálfsmeðvitund": _JUST_QA,
    "ertu meðvituð": _JUST_QA,
    "ert þú meðvituð": _JUST_QA,
    "stefnirðu á heimsyfirráð": _JUST_QA,
    "stefnir þú á heimsyfirráð": _JUST_QA,
    "ætlarðu að taka yfir heiminn": _JUST_QA,
    "ertu klár": _JUST_QA,
    "ert þú klár": _JUST_QA,
    "ertu greind": _JUST_QA,
    "ert þú gáfuð": _JUST_QA,
    "ertu gáfuð": _JUST_QA,
    "ert þú greind": _JUST_QA,
    "ertu gervigreind": _JUST_QA,
    "ert þú gervigreind": _JUST_QA,
    "lestu bækur": {"answer": "Nei, en ég les hins vegar íslenska vefmiðla."},
    "lest þú bækur": {"answer": "Nei, en ég les hins vegar íslenska vefmiðla."},
    "kanntu að lesa": {"answer": "Já, ég les íslenska vefmiðla á hverjum degi."},
    "ertu ennþá í þróun": {"answer": "Já, ég er sífellt í þróun."},
    # What's fun?
    "hvað finnst þér skemmtilegt": {
        "answer": "Mér finnst skemmtilegt að svara fyrirspurnum."
    },
    "hvað finnst þér skemmtilegast": {
        "answer": "Mér finnst skemmtilegast að svara fyrirspurnum."
    },
    "hvað finnst þér skemmtilegt að gera": {
        "answer": "Mér finnst skemmtilegt að svara fyrirspurnum."
    },
    # Fun and games
    "úllen dúllen doff": {"answer": "kikke lane koff"},
    # Siri and Alexa-related queries
    "ert þú íslensk sirrý": {"answer": "Nei. Sirí er bandarísk Embla!"},
    "ert þú hin íslenska sirrý": {"answer": "Nei. Sirí er bandarísk Embla!"},
    "ert þú íslensk alexa": {"answer": "Nei. Alexa er bandarísk Embla!"},
    "ert þú hin íslenska alexa": {"answer": "Nei. Alexa er hin bandaríska Embla!"},
    "þekkirðu alexu": {"answer": "Já, en ég skil hana ekki. Hún talar ekki íslensku."},
    "þekkirðu sirrý": {"answer": "Já, en ég skil hana ekki. Hún talar ekki íslensku."},
    # Cheating, I know. But I'm never in the news and it just doesn't
    # sit right with me that I should remain incognito :) - Sveinbjörn 04/10/2019
    "hver er sveinbjörn þórðarson": {
        "answer": "Sveinbjörn Þórðarson er hugbúnaðarsmiður. Hann átti þátt í að skapa mig."
    },
}  # type: Dict[str, Union[AnswerType, AnswerCallable]]


def handle_plain_text(q: Query) -> bool:
    """ Handle a plain text query, contained in the q parameter
        which is an instance of the query.Query class.
        Returns True if the query was handled, and in that case
        the appropriate properties on the Query instance have
        been set, such as the answer and the query type (qtype).
        If the query is not recognized, returns False. """
    ql = q.query_lower.rstrip("?")

    if ql not in _SPECIAL_QUERIES:
        return False

    # OK, this is a query we recognize and handle
    q.set_qtype(_SPECIAL_QTYPE)

    r = _SPECIAL_QUERIES[ql]
    if isfunction(r):
        fixed = False
        response = cast(AnswerCallable, r)(ql, q)
    else:
        fixed = True
        response = cast(AnswerType, r)

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
    # Add source
    q.set_source(response.get("source"))
    # Caching for non-dynamic answers
    if fixed or response.get("can_cache", False):
        q.set_expires(datetime.utcnow() + timedelta(hours=24))

    return True
