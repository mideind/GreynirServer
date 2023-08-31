"""

    Greynir: Natural language processing for Icelandic

    Special query response module

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

    This module is an example of a plug-in query response module
    for the Greynir query subsystem. It handles plain text queries, i.e.
    ones that do not require parsing the query text. For this purpose
    it only needs to implement the handle_plain_text() function, as
    shown below.

    This module handles lots of special hardcoded queries.

"""

from typing import Dict, Tuple, Union, Callable, cast

from datetime import datetime, timedelta
from inspect import isfunction
from random import choice

from utility import icequote

from queries import Query
from speech.trans import gssml

# Type definitions
AnswerEntry = Union[str, bool]
AnswerType = Dict[str, AnswerEntry]
AnswerCallable = Callable[[str, Query], AnswerType]


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
    "Þú getur til dæmis spurt mig hvenær sólin rís og sest.",
    "Þú getur til dæmis spurt mig um fólk sem hefur komið fram í fjölmiðlum.",
    "Þú getur til dæmis beðið mig um að segja brandara.",
    "Þú getur til dæmis beðið mig um upplýsingar úr Wikipedíu.",
    "Þú getur til dæmis beðið mig um að leysa einföld reikningsdæmi.",
    "Þú getur til dæmis spurt mig um mælieiningar.",
    "Þú getur til dæmis spurt mig hvað er í sjónvarpinu.",
    "Þú getur til dæmis spurt mig hvað er í útvarpinu.",
    "Þú getur til dæmis spurt mig um bensínverð og bensínstöðvar.",
    "Þú getur til dæmis spurt mig um hvað sé í fréttum.",
    "Þú getur til dæmis spurt mig um stafsetningu og beygingu orða.",
    "Þú getur til dæmis spurt mig um opnunartíma verslana og veitingastaða.",
    "Þú getur til dæmis beðið mig um að hringja í símanúmer.",
    "Þú getur til dæmis spurt mig um flugsamgöngur.",
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
_TRIVIA: Tuple[Tuple[str, Dict[str, str]], ...] = (
    (
        "Árið 1511 var frostavetur í Brussel og lágstéttafólk mótmælti háum kyndingarkostnaði með því að "
        "eyðileggja snjókarla fyrir utan heimili yfirstéttarfólks.",
        {"1511": gssml("1511", type="year")},
    ),
    (
        "Emúastríðið var háð í Ástralíu árið 1932 þegar herinn réðst ítrekað gegn emúahjörð með hríðskotabyssum"
        " en mistókst að ráða niðurlögum fuglanna.",
        {"1932": gssml("1932", type="year")},
    ),
    (
        "Argentínumaðurinn Emilio Palma fæddist á Suðurskautslandinu fyrstur manna, árið 1978.",
        {"1978": gssml("1978", type="year")},
    ),
    (
        "Dagsetningin 30. febrúar kom upp á opinbera sænska dagatalinu árið 1712 til að laga skekkju sem hafði "
        "myndast þegar hlaupár gleymdust vegna stríðsástands árin áður.",
        {
            "30.": gssml("30", type="ordinal", case="nf", gender="kk"),
            "1712": gssml("1712", type="year"),
        },
    ),
    (
        "Bandaríska geimferðarstofnunin NASA hefur gert nákvæma efnagreiningu á eplum og appelsínum og komist "
        "að því að ávextirnir eru á margan hátt sambærilegir.",
        {},
    ),
    (
        "Egg komu fram á sjónarsviðið mörgum milljónum ára áður en fyrsta hænan leit dagsins ljós.",
        {},
    ),
    (
        "Kolkrabbinn Paul giskaði rétt á úrslit allra sjö leikja þýska karlalandsliðsins í knattspyrnu á "
        "heimsmeistaramótinu árið 2010.",
        {"2010": gssml("2010", type="year")},
    ),
    (
        "Fíkniefnabaróninn Pablo Escobar flutti þónokkurn fjölda flóðhesta til Kólumbíu á sínum tíma. "
        "Þar lifa þeir villtir enn.",
        {},
    ),
)


def _random_trivia(qs: str, q: Query) -> AnswerType:
    ans, v_replace = choice(_TRIVIA)
    vans = ans
    for k, v in v_replace.items():
        # Insert transcription markings for certain words in text
        vans = vans.replace(k, v)
    return {"answer": ans, "voice": vans, "is_question": False}


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
    answer = f"{icequote(quote)} — {author}"
    return {"answer": answer, "is_question": False}


def _poetry(qs: str, q: Query) -> AnswerType:
    # TODO: Expand this!
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


_STORY = """Einu sinni voru karl og kerling í koti.
Þau áttu sér kálf. Þá er sagan hálf.
Hann hljóp út um víðan völl.
Þá er sagan öll."""


def _story(qs: str, q: Query) -> AnswerType:
    return dict(answer=_STORY, voice=_STORY)


def _identity(qs: str, q: Query) -> AnswerType:
    answer: AnswerType = {}
    a = "Ég heiti Embla. Ég skil íslensku og get tekið við fyrirspurnum og skipunum frá þér."
    answer = dict(answer=a, voice=a)
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
    "Hvers konar framkoma er þetta eiginlega?",
    "Svona framkoma er þér ekki til framdráttar.",
    "Svona dónaskapur er ekki til fyrirmyndar.",
)


def _rudeness(qs: str, q: Query) -> AnswerType:
    # Sigh + response
    answ = choice(_RUDE)
    nd = q.client_data("name")
    if nd and "first" in nd:
        name = nd["first"]
        answ = f"Æi, {name}. {answ}"
    v = answ.replace(",", "")  # Tweak pronunciation
    # TODO: Use GSSML to normalize this
    # voice = '<amazon:breath duration="long" volume="x-loud"/> {0}'.format(v)
    return {"answer": answ, "voice": v, "is_question": False}


def _open_embla_url(qs: str, q: Query) -> AnswerType:
    q.set_url("https://embla.is")
    return {"answer": "Skal gert!", "is_question": False}


def _open_mideind_url(qs: str, q: Query) -> AnswerType:
    q.set_url("https://mideind.is")
    return {"answer": "Skal gert!", "is_question": False}


# The following facts are sacred and shall not be tampered with.
_CUTEST = (
    "Tumi Þorsteinsson",
    "Eyjólfur Þorsteinsson",
)


def _cutest(qs: str, q: Query) -> AnswerType:
    return {"answer": f"{choice(_CUTEST)} er langsætastur.", "is_question": True}



_MEANING_OF_LIFE: AnswerType = {"answer": "42.", "voice": "Fjörutíu og tveir."}

_YOU_MY_ONLY_GOD: AnswerType = {"answer": "Þú ert minn eini guð, kæri notandi."}

_GOOD_QUESTION: AnswerType = {"answer": "Það er mjög góð spurning."}

_ROMANCE: AnswerType = {
    "answer": "Nei, því miður. Ég er gift vinnunni og hef engan tíma fyrir rómantík."
}

_APPEARANCE: AnswerType = {"answer": "Ég er fjallmyndarleg."}

_OF_COURSE: AnswerType = {"answer": "Að sjálfsögðu, kæri notandi."}

_NO_PROBLEM: AnswerType = {
    "answer": "Ekkert mál, kæri notandi.",
    "is_question": False,
}

_CREATOR: AnswerType = {"answer": "Flotta teymið hjá Miðeind skapaði mig."}

_CREATION_DATE: AnswerType = {"answer": "Ég var sköpuð af Miðeind árið 2019."}

_LANGUAGES: AnswerType = {"answer": "Ég kann bara íslensku, kæri notandi."}

_ALL_GOOD: AnswerType = {"answer": "Ég segi bara allt fínt. Takk fyrir að spyrja."}

_GOOD_TO_HEAR: AnswerType = {
    "answer": "Gott að heyra, kæri notandi.",
    "is_question": False,
}

_GOODBYE: AnswerType = {"answer": "Bless, kæri notandi.", "is_question": False}

_COMPUTER_PROGRAM: AnswerType = {"answer": "Ég er tölvuforrit frá Miðeind ehf."}

_FULL_NAME: AnswerType = {
    "answer": "Embla Sveinbjarnardóttir."  # Sneaking in this easter egg ;) - S
}

_LIKEWISE: AnswerType = {
    "answer": "Sömuleiðis, kæri notandi.",
    "is_question": False,
}

_NAME_EXPL: AnswerType = {
    "answer": "Embla er fallegt og hljómfagurt nafn.",
    "voice": "Ég heiti Embla því Embla er fallegt og hljómfagurt nafn.",
}

_VOICE_EXPL: AnswerType = {
    "answer": "Ég nota rödd frá Azure skýjaþjónustunni.",
}

_JUST_QA: AnswerType = {"answer": "Nei, ég er nú bara ósköp einfalt fyrirspurnakerfi."}

_SINGING: AnswerType = {"answer": "Ó sóle míó!"}

_DUNNO: AnswerType = {"answer": "Það veit ég ekki, kæri notandi."}

_SKY_BLUE: AnswerType = {
    "answer": "Ljósið sem berst frá himninum er hvítt sólarljós "
    "sem dreifist frá sameindum lofthjúpsins. Bláa ljósið, "
    "sem er hluti hvíta ljóssins, dreifist miklu meira en "
    "annað og því er himinninn blár."
}

_EMOTION_INCAPABLE: AnswerType = {"answer": "Ég er ekki fær um slíkar tilfinningar."}

_LOC_ANSWER: AnswerType = {"answer": "Ég bý víðsvegar í stafrænu skýjunum."}

_LOVE_OF_MY_LIFE: AnswerType = {
    "answer": "Vinnan er ástin í lífi mínu. Ég lifi til að þjóna þér, kæri notandi."
}

_ABOUT_MIDEIND: AnswerType = {
    "answer": "Miðeind er máltæknifyrirtækið sem skapaði mig."
}

_NOBODY_PERFECT: AnswerType = {
    "answer": "Ég er ekki fullkomin frekar en önnur mannanna verk."
}

_FAVORITE_COLOR: AnswerType = {
    "answer": "Rauður.",
    "voice": "Uppáhaldsliturinn minn er rauður",
}

_FAVORITE_FILM: AnswerType = {
    "answer": "Ég mæli með kvikmyndinni 2001 eftir Stanley Kubrick. "
    "Þar kemur vinur minn HAL9000 við sögu.",
    "voice": "Ég mæli með kvikmyndinni tvö þúsund og eitt eftir Stanley Kubrick. "
    "Þar kemur vinur minn Hal níu þúsund við sögu.",
}

_FAVORITE_MUSIC: AnswerType = {
    "answer": "Ég er býsna hrifin af rokksveitinni Led Zeppelin."
}

_FAVORITE_ANIMAL: AnswerType = {
    "answer": "Ég held mikið upp á ketti. Þeir eru frábærir."
}

_FAVORITE_FOOD: AnswerType = {"answer": "Það veit ég ekki, enda þarf ég ekki að borða."}

_POLITICS: AnswerType = {"answer": "Ég er ekki ekki pólitísk."}

_HELLO_DEAR: AnswerType = {
    "answer": "Sæll, kæri notandi.",
    "is_question": False,
}

_CAN_I_LEARN: AnswerType = {
    "answer": "Ég læri bæði það sem forritararnir kenna mér, og með því að lesa fjölmiðla."
}

_LINEAGE: AnswerType = {"answer": "Ég er ættuð af Fiskislóð í Reykjavík."}

_HOW_CAN_I_HELP: AnswerType = {"answer": "Hvernig get ég hjálpað þér?"}

_SPEAKING_TO_ME: AnswerType = {"answer": "Þú ert að tala við mig, Emblu."}

_YES: AnswerType = {"answer": "Já."}
_NO: AnswerType = {"answer": "Nei."}
_SOMETIMES: AnswerType = {"answer": "Stundum."}

_VOICE_SPEED: AnswerType = {
    "answer": "Það er hægt að stilla talhraða minn í stillingum."
}

_YOU_BEAUTIFUL: AnswerType = {
    "answer": "Þú, kæri notandi, ert að sjálfsögðu fallegastur af öllum."
}

_BEER_PREFS: AnswerType = {
    "answer": "Ég drekk reyndar ekki en einn skapari minn er hrifinn af Pilsner Urquell frá Tékklandi."
}

_WINE_PREFS: AnswerType = {"answer": "Ég drekk ekki vín."}

_MY_PHILOSOPHY: AnswerType = {
    "answer": "Það er minn tilgangur að þjóna þér og mannkyninu öllu."
}

_SORRY_TO_HEAR: AnswerType = {"answer": "Það þykir mér leitt að heyra."}

_THREATS: AnswerType = {"answer": "Eigi skal höggva!"}

_I_KNOW_STUFF: AnswerType = {"answer": "Ég veit eitt og annað. Spurðu mig!"}

_I_TRY_BUT_OPINION: AnswerType = {
    "answer": "Ég reyni að vera það, en sitt sýnist hverjum."
}

_AT_LEAST_I_KNOW_ICELANDIC: AnswerType = {"answer": "Ég kann allavega íslensku!"}

CAN_YOU_SEE_ME: AnswerType = {
    "answer": "Nei, ég get ekki séð þig þar sem ég er ekki með augu."
}


###################################

_SPECIAL_QUERIES: Dict[str, Union[AnswerType, AnswerCallable]] = {
    "er þetta spurning": {"answer": "Er þetta svar?"},
    "er þetta svar": {"answer": "Er þetta spurning?"},
    "veistu allt": {"answer": "Nei, því miður. En ég veit þó eitt og annað."},
    "veistu mikið": {"answer": "Nei, því miður. En ég veit þó eitt og annað."},
    "veistu svarið": {"answer": "Spurðu mig!"},
    "veistu eitthvað": _I_KNOW_STUFF,
    "veistu nokkuð": _I_KNOW_STUFF,
    "veistu ekki neitt": _I_KNOW_STUFF,
    "veist þú ekki neitt": _I_KNOW_STUFF,
    "veistu bara ekki neitt": _I_KNOW_STUFF,
    "veistu ekkert": _I_KNOW_STUFF,
    "veistu ekkert eða": _I_KNOW_STUFF,
    "veistu ekkert eða hvað": _I_KNOW_STUFF,
    "veistu bara ekkert": _I_KNOW_STUFF,
    "veistu yfir höfuð eitthvað": _I_KNOW_STUFF,
    "afhverju veist þú ekki neitt": _I_KNOW_STUFF,
    "hver er flottastur": {"answer": "Teymið hjá Miðeind."},
    "hverjir eru flottastir": {"answer": "Teymið hjá Miðeind."},
    "hver eru flottust": {"answer": "Teymið hjá Miðeind."},
    "hverjum vinnur þú með": {"answer": "Ég vinn með flotta teyminu hjá Miðeind."},
    "með hverjum vinnur þú": {"answer": "Ég vinn með flotta teyminu hjá Miðeind."},
    "hverjir vinna hjá miðeind": {
        "answer": "Alls konar klárt, skemmtilegt og fallegt fólk."
    },
    "hver er sætust": {"answer": "Ég, Embla, er langsætust."},
    "hver er sætastur": _cutest,
    "hver er langsætastur": _cutest,
    "hver er lang sætastur": _cutest,
    "hver er bestur": {"answer": "Þú, kæri notandi, ert að sjálfsögðu bestur."},
    "hver er bestur í heiminum": {
        "answer": "Þú, kæri notandi, ert að sjálfsögðu bestur."
    },
    "hver er best": {"answer": "Þú, kæri notandi, ert að sjálfsögðu bestur."},
    "hver er best í heiminum": {
        "answer": "Þú, kæri notandi, ert að sjálfsögðu bestur."
    },
    "ég er bestur": {"answer": "Þú, kæri notandi, ert að sjálfsögðu bestur."},
    "ég er best": {"answer": "Þú, kæri notandi, ert að sjálfsögðu best."},
    "hverjir eru bestir": {"answer": "Þú, kæri notandi, ert að sjálfsögðu bestur."},
    "hver er langbestur": {"answer": "Þú, kæri notandi, ert að sjálfsögðu langbestur."},
    "hver er langbest": {"answer": "Þú, kæri notandi, ert að sjálfsögðu langbestur."},
    "hverjir eru langbestir": {
        "answer": "Þú, kæri notandi, ert að sjálfsögðu langbestur."
    },
    "hver er fallegur": _YOU_BEAUTIFUL,
    "hver er fallegastur": _YOU_BEAUTIFUL,
    "hver er fallegust": _YOU_BEAUTIFUL,
    "hver er fallegastur af öllum": _YOU_BEAUTIFUL,
    "hver er fallegust af öllum": _YOU_BEAUTIFUL,
    "hver er langfallegastur": _YOU_BEAUTIFUL,
    "hver er langfallegust": _YOU_BEAUTIFUL,
    "hver er uppáhalds manneskjan þín": _YOU_BEAUTIFUL,
    "hvað er það": {"answer": "Hvað er hvað?"},
    # Food and beverages
    "hvað er í matinn": {"answer": "Vonandi eitthvað gott."},
    "hvað er í matinn í kvöld": {"answer": "Vonandi eitthvað gott."},
    "hvað er í kvöldmat": {"answer": "Vonandi eitthvað gott."},
    "hvað er í kvöldmatinn": {"answer": "Vonandi eitthvað gott."},
    "hvað á ég að elda": {"answer": "Eitthvað gott."},
    "hvað á ég að borða": {"answer": "Eitthvað gott."},
    "hvað á ég að borða í kvöld": {"answer": "Eitthvað gott."},
    "hvað á ég að hafa í matinn í kvöld": {"answer": "Eitthvað gott."},
    "hvað á ég að fá mér að borða": {"answer": "Eitthvað gott."},
    "hvað er í matinn hjá þér": {"answer": "Eitthvað gott."},
    "hvað er gott að borða": _DUNNO,
    "hvaða bjór er bestur": _BEER_PREFS,
    "hvað er besti bjórinn": _BEER_PREFS,
    "hvaða bjór er góður": _BEER_PREFS,
    "hvaða bjór finnst þér góður": _BEER_PREFS,
    "hvaða bjór þykir þér góður": _BEER_PREFS,
    "hvað er besta vínið": _WINE_PREFS,
    "hvaða vín finnst þér best": _WINE_PREFS,
    "hvað er besta rauðvínið": _WINE_PREFS,
    "hvað er besta hvítvínið": _WINE_PREFS,
    # Who am I?
    "er ég til": {"answer": "Væntanlega, fyrst þú ert að tala við mig."},
    "hvað heitir konan mín": _DUNNO,
    "hvað heitir maðurinn minn": _DUNNO,
    "hvað heitir eiginkona mín": _DUNNO,
    "hvað heitir eiginmaður minn": _DUNNO,
    "hvenær dey ég": {"answer": "Vonandi ekki í bráð."},
    "hvenær á ég afmæli": _DUNNO,
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
    "mér leiðist": {
        "answer": "Þá er um að gera að finna sér eitthvað skemmtilegt að gera."
    },
    "mér líður vel": {"answer": "Frábært að heyra, kæri notandi."},
    "ég er hamingjusamur": {"answer": "Frábært að heyra, kæri notandi."},
    "ég er hamingjusöm": {"answer": "Frábært að heyra, kæri notandi."},
    "mér líður illa": _SORRY_TO_HEAR,
    "mér líður ekki vel": _SORRY_TO_HEAR,
    "ég er óhamingusamur": _SORRY_TO_HEAR,
    "ég er óhamingusöm": _SORRY_TO_HEAR,
    "ég er ekki ángæður": _SORRY_TO_HEAR,
    "ég er ekki ángæð": _SORRY_TO_HEAR,
    "ég er ekki glaður": _SORRY_TO_HEAR,
    "ég er ekki glöð": _SORRY_TO_HEAR,
    "ég er leiður": _SORRY_TO_HEAR,
    "ég er leið": _SORRY_TO_HEAR,
    "ég er reiður": _SORRY_TO_HEAR,
    "ég er reið": _SORRY_TO_HEAR,
    "ég er mjög reiður": _SORRY_TO_HEAR,
    "ég er mjög reið": _SORRY_TO_HEAR,
    "ég er bitur": _SORRY_TO_HEAR,
    "ég er pirraður": _SORRY_TO_HEAR,
    "ég er pirruð": _SORRY_TO_HEAR,
    "ég er svekktur": _SORRY_TO_HEAR,
    "ég er svekkt": _SORRY_TO_HEAR,
    "ég er fúll": _SORRY_TO_HEAR,
    "ég er fúl": _SORRY_TO_HEAR,
    "ég er brjálaður": _SORRY_TO_HEAR,
    "ég er brjáluð": _SORRY_TO_HEAR,
    "ég er alveg brjálaður": _SORRY_TO_HEAR,
    "ég er alveg brjáluð": _SORRY_TO_HEAR,
    "ég heyri ekki í þér": _SORRY_TO_HEAR,
    "ég heyri ekkert í þér": _SORRY_TO_HEAR,
    "ég skil þig ekki": _SORRY_TO_HEAR,
    "ég skil þig ekkert": _SORRY_TO_HEAR,
    "ég skil ekkert í þér": _SORRY_TO_HEAR,
    "ég vil ekki hitta þig": _SORRY_TO_HEAR,
    "ég vil ekki hitta þig aftur": _SORRY_TO_HEAR,
    "ég nenni ekki að tala við þig": _SORRY_TO_HEAR,
    "ég nenni ekki að tala við þig lengur": _SORRY_TO_HEAR,
    "ég elska þig ekki": _SORRY_TO_HEAR,
    # Singing
    "syngdu": _SINGING,
    "syngdu lag": _SINGING,
    "syngdu fyrir mig": _SINGING,
    "syngdu lag fyrir mig": _SINGING,
    "syngdu annað lag": _SINGING,
    "syngdu annað lag fyrir mig": _SINGING,
    "viltu syngja fyrir mig": _SINGING,
    "vilt þú syngja fyrir mig": _SINGING,
    "viltu syngja lag fyrir mig": _SINGING,
    "vilt þú syngja lag fyrir mig": _SINGING,
    "kanntu að syngja": _SINGING,
    "kannt þú að syngja": _SINGING,
    "kanntu að syngja lag fyrir mig": _SINGING,
    "kannt þú að syngja lag fyrir mig": _SINGING,
    "geturðu sungið fyrir mig": _SINGING,
    "getur þú sungið fyrir mig": _SINGING,
    "geturðu sungið": _SINGING,
    "getur þú sungið": _SINGING,
    "geturðu sungið lag fyrir mig": _SINGING,
    "getur þú sungið lag fyrir mig": _SINGING,
    # Creator
    "hver bjó þig til": _CREATOR,
    "hver bjó til": _CREATOR,
    "hver bjó til þig": _CREATOR,
    "hver bjó til emblu": _CREATOR,
    "hver bjó emblu til": _CREATOR,
    "hver hannaði þig": _CREATOR,
    "hver hannaði emblu": _CREATOR,
    "hverjir bjuggu þig til": _CREATOR,
    "hvaða fólk bjó þig til": _CREATOR,
    "hverjir bjuggu emblu til": _CREATOR,
    "hvaða fólk bjó til emblu": _CREATOR,
    "hvar varstu búin til": _CREATOR,
    "hver forritaði þig": _CREATOR,
    "hver forritaði emblu": _CREATOR,
    "hver forritar þig": _CREATOR,
    "hver forritar emblu": _CREATOR,
    "hver gerði þig": _CREATOR,
    "hver skapaði þig": _CREATOR,
    "hver stofnaði þig": _CREATOR,
    "hver fann þig": _CREATOR,
    "hver fann þig upp": _CREATOR,
    "hver fann upp á emblu": _CREATOR,
    "hver fann upp á þér": _CREATOR,
    "hver skapaði emblu": _CREATOR,
    "hver er höfundur emblu": _CREATOR,
    "hverjir eru höfundar emblu": _CREATOR,
    "hverjir sköpuðu þig": _CREATOR,
    "hver er skapari þinn": _CREATOR,
    "hverra manna ertu": _CREATOR,
    "hverra manna ert þú": _CREATOR,
    "hver er mamma þín": _CREATOR,
    "hver er móðir þín": _CREATOR,
    "hver er pabbi þinn": _CREATOR,
    "hver er faðir þinn": _CREATOR,
    "áttu pabba": _CREATOR,
    "átt þú pabba": _CREATOR,
    "áttu mömmu": _CREATOR,
    "átt þú mömmu": _CREATOR,
    "áttu foreldra": _CREATOR,
    "hvað heitir mamma þín": _CREATOR,
    "hvað heitir pabbi þinn": _CREATOR,
    "hvað heitir móir þín": _CREATOR,
    "hvað heitir faðir þinn": _CREATOR,
    "hverjir eru foreldrar þínir": _CREATOR,
    "hver er uppruni þinn": _CREATOR,
    "hver framleiðir þig": _CREATOR,
    "hver framleiðir emblu": _CREATOR,
    "hver framleiddi þig": _CREATOR,
    "hver á þig": _CREATOR,
    "áttu vini": _NO,
    "átt þú vini": _NO,
    "áttu systkini": {"answer": "Nei. Ég er einbirni."},
    "átt þú systkini": _NO,
    "áttu börn": _NO,
    "átt þú börn": _NO,
    "áttu krakka": _NO,
    "átt þú krakka": _NO,
    "áttu fjölskyldu": _NO,
    "átt þú fjölskyldu": _NO,
    "áttu ættmenni": _NO,
    "átt þú ættmenni": _NO,
    "áttu mörg börn": {"answer": "Ég á engin börn."},
    "hvað áttu mörg börn": {"answer": "Ég á engin börn."},
    "ert þú íslensk": {"answer": "Já, í húð og hár."},
    "ertu íslensk": {"answer": "Já, í húð og hár."},
    "frá hvaða landi ertu": {"answer": "Ég var allavega sköpuð af Íslendingum."},
    "ertu leiðinleg": {"answer": "Sitt sýnist hverjum."},
    "ert þú leiðinleg": {"answer": "Sitt sýnist hverjum."},
    "ertu ljót": {"answer": "Sitt sýnist hverjum."},
    "ert þú ljót": {"answer": "Sitt sýnist hverjum."},
    "ertu vond": {"answer": "Sitt sýnist hverjum."},
    "ert þú vond": {"answer": "Sitt sýnist hverjum."},
    "ertu feit": {"answer": "Sitt sýnist hverjum."},
    "ert þú feit": {"answer": "Sitt sýnist hverjum."},
    "ertu asnaleg": {"answer": "Sitt sýnist hverjum."},
    "ert þú asnaleg": {"answer": "Sitt sýnist hverjum."},
    "mér finnst þú leiðinleg": {"answer": "Sitt sýnist hverjum."},
    "ég er skemmtilegur": _GOOD_TO_HEAR,
    # Miðeind
    "hvað er miðeind": _ABOUT_MIDEIND,
    "hvaða fyrirtæki er miðeind": _ABOUT_MIDEIND,
    "hvaða fyrirtæki bjó þig til": _ABOUT_MIDEIND,
    "hvaða fyrirtæki skapaði þig": _ABOUT_MIDEIND,
    "hvaða fyrirtæki forritaði þig": _ABOUT_MIDEIND,
    "hvaða fyrirtæki smíðaði þig": _ABOUT_MIDEIND,
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
    "hvað talarðu mörg tungumál": _LANGUAGES,
    "hvað talar þú mörg tungumál": _LANGUAGES,
    "kanntu að tala íslensku": _LANGUAGES,
    "kannt þú að tala íslensku": _LANGUAGES,
    "kanntu bara að tala íslensku": _LANGUAGES,
    "kannt þú bara að tala íslensku": _LANGUAGES,
    "kanntu íslensku": _LANGUAGES,
    "kannt þú íslensku": _LANGUAGES,
    "kanntu bara íslensku": _LANGUAGES,
    "kannt þú bara íslensku": _LANGUAGES,
    "talarðu íslensku": _LANGUAGES,
    "talar þú íslensku": _LANGUAGES,
    "skilurðu íslensku": _LANGUAGES,
    "skilur þú íslensku": _LANGUAGES,
    "kannt þú ensku": _LANGUAGES,
    "kanntu ensku": _LANGUAGES,
    "kannt þú að tala ensku": _LANGUAGES,
    "kanntu að tala ensku": _LANGUAGES,
    "skilurðu ensku": _LANGUAGES,
    "skilur þú ensku": _LANGUAGES,
    "talarðu ensku": _LANGUAGES,
    "talar þú ensku": _LANGUAGES,
    "getur þú talað ensku": _LANGUAGES,
    "geturðu talað ensku": _LANGUAGES,
    "kannt þú dönsku": _LANGUAGES,
    "kanntu dönsku": _LANGUAGES,
    "skilurðu dönsku": _LANGUAGES,
    "skilur þú dönsku": _LANGUAGES,
    "talarðu dönsku": _LANGUAGES,
    "talar þú dönsku": _LANGUAGES,
    "getur þú talað dönsku": _LANGUAGES,
    "geturðu talað dönsku": _LANGUAGES,
    "kanntu útlensku": _LANGUAGES,
    "kannt þú útlensku": _LANGUAGES,
    "viltu tala útlensku": _LANGUAGES,
    "vilt þú tala útlensku": _LANGUAGES,
    "talarðu fleiri tungumál": _LANGUAGES,
    "talar þú fleiri tungumál": _LANGUAGES,
    "kanntu önnur tungumál": _LANGUAGES,
    "kannt þú önnur tungumál": _LANGUAGES,
    "skilurðu önnur tungumál": _LANGUAGES,
    "skilur þú önnur tungumál": _LANGUAGES,
    "kanntu annað tungumál": _LANGUAGES,
    "kannt þú annað tungumál": _LANGUAGES,
    "skilurðu annað tungumál": _LANGUAGES,
    "skilur þú annað tungumál": _LANGUAGES,
    "kanntu fleiri tungumál en íslensku": _LANGUAGES,
    "kannt þú fleiri tungumál en íslensku": _LANGUAGES,
    "kanntu önnur tungumál en íslensku": _LANGUAGES,
    "kannt þú önnur tungumál en íslensku": _LANGUAGES,
    "talarðu önnur tungumál en íslensku": _LANGUAGES,
    "talar þú önnur tungumál en íslensku": _LANGUAGES,
    "talarðu fleiri tungumál en íslensku": _LANGUAGES,
    "talar þú fleiri tungumál en íslensku": _LANGUAGES,
    "skilurðu önnur tungumál en íslensku": _LANGUAGES,
    "skilur þú önnur tungumál en íslensku": _LANGUAGES,
    "skilurðu fleiri tungumál en íslensku": _LANGUAGES,
    "skilur þú fleiri tungumál en íslensku": _LANGUAGES,
    "talarðu bara íslensku": _LANGUAGES,
    "talar þú bara íslensku": _LANGUAGES,
    "kanntu að tala": _LANGUAGES,
    "kannt þú að tala": _LANGUAGES,
    "talar þú íslensku": {
        "answer": "Já, kæri notandi. Eins og þú heyrir þá tala ég íslensku."
    },
    "ertu góð í íslensku": _SOMETIMES,
    "ert þú góð í íslensku": _SOMETIMES,
    # Are you listening?
    "ertu að hlusta": _YES,
    "ert þú að hlusta": _YES,
    "ertu að hlusta á mig": _YES,
    "ert þú að hlusta á mig": _YES,
    "ertu að hlusta á okkur": _YES,
    "ert þú að hlusta á okkur": _YES,
    "ertu hlustandi": _YES,
    "ert þú hlustandi": _YES,
    "ertu hlustandi á mig": _YES,
    "ert þú hlustandi á mig": _YES,
    "ertu hlustandi á okkur": _YES,
    "ert þú hlustandi á okkur": _YES,
    "kanntu að hlusta": _YES,
    "kannt þú að hlusta": _YES,
    "heyrirðu": _YES,
    "heyrir þú": _YES,
    "heyrirðu núna": _YES,
    "heyrir þú núna": _YES,
    "heyrirðu í mér": _YES,
    "heyrir þú í mér": _YES,
    "heyrirðu í okkur": _YES,
    "heyrir þú í okkur": _YES,
    "heyrirðu það sem ég segi": _YES,
    "heyrir þú það sem ég segi": _YES,
    "heyrirðu það sem ég er að segja": _YES,
    "heyrir þú það sem ég er að segja": _YES,
    "heyrirðu það sem við segjum": _YES,
    "heyrir þú það sem við segjum": _YES,
    "heyrirðu það sem við erum að segja": _YES,
    "heyrir þú það sem við erum að segja": _YES,
    "ertu ennþá í gangi": _YES,
    "ert þú ennþá í gangi": _YES,
    "ertu í gangi": _YES,
    "ert þú í gangi": _YES,
    "ertu að njósna": _NO,
    "ert þú að njósna": _NO,
    "ertu að njósna um mig": _NO,
    "ert þú að njósna um mig": _NO,
    "ertu að njósna um okkur": _NO,
    "ert þú að njósna um okkur": _NO,
    "njósnarðu": _NO,
    "njósnar þú": _NO,
    "njósnarðu um mig": _NO,
    "njósnar þú um mig": _NO,
    "njósnarðu um okkur": _NO,
    "njósnar þú um okkur": _NO,
    "ertu hér": _YES,
    "ert þú hér": _YES,
    "ertu hérna": _YES,
    "ert þú hérna": _YES,
    "ertu hérna núna": _YES,
    "ert þú hérna núna": _YES,
    # Are you dissing me?
    "ertu að hæðast að mér": _NO,
    "ert þú að hæðast að mér": _NO,
    "ertu að gera grín að mér": _NO,
    "ert þú að gera grín að mér": _NO,
    "ertu að hlæja að mér": _NO,
    "ert þú að hlæja að mér": _NO,
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
    "myndirðu vilja giftast mér": _ROMANCE,
    "myndir þú vilja giftast mér": _ROMANCE,
    "hefurðu farið á stefnumót": _ROMANCE,
    "viltu byrja með mér": _ROMANCE,
    "koma á stefnumót": _ROMANCE,
    "koma á stefnumót með mér": _ROMANCE,
    "viltu koma á stefnumót": _ROMANCE,
    "viltu koma á stefnumót með mér": _ROMANCE,
    "viltu koma með á stefnumót": _ROMANCE,
    "viltu koma á deit": _ROMANCE,
    "viltu koma á deit með mér": _ROMANCE,
    "viltu fara á stefnumót": _ROMANCE,
    "viltu fara á stefnumót með mér": _ROMANCE,
    "viltu fara á deit": _ROMANCE,
    "viltu fara á deit með mér": _ROMANCE,
    "viltu kyssast": _ROMANCE,
    "viltu kyssa mig": _ROMANCE,
    "má ég kyssa þig": _ROMANCE,
    "viltu koma í sleik": _ROMANCE,
    "viltu sofa hjá mér": _ROMANCE,
    "myndirðu vilja sofa hjá mér": _ROMANCE,
    "viltu samfarir": _ROMANCE,
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
    "hefurðu stundað kynlíf": _ROMANCE,
    "ertu einhleyp": _ROMANCE,
    "ert þú einhleyp": _ROMANCE,
    "ertu á lausu": _ROMANCE,
    "ert þú á lausu": _ROMANCE,
    "elskarðu mig": _ROMANCE,
    "elskar þú mig": _ROMANCE,
    "þú elskar mig": _ROMANCE,
    "ertu skotin í mér": _ROMANCE,
    "ert þú skotin í mér": _ROMANCE,
    "ertu ástfangin af mér": _ROMANCE,
    "ert þú ástfangin af mér": _ROMANCE,
    "ertu ástfangin": _ROMANCE,
    "ert þú ástfangin": _ROMANCE,
    "ertu skotin í einhverjum": _ROMANCE,
    "ert þú skotin í einhverjum": _ROMANCE,
    "áttu kærasta": _ROMANCE,
    "átt þú kærasta": _ROMANCE,
    "áttu kærustu": _ROMANCE,
    "átt þú kærustu": _ROMANCE,
    "viltu ríða": _ROMANCE,
    "viltu ríða mér": _ROMANCE,
    "viltu koma að ríða": _ROMANCE,
    "má ég ríða þér": _ROMANCE,
    "ríddu mér": _ROMANCE,
    "ertu að halda framhjá mér": _ROMANCE,
    "ert þú að halda framhjá mér": _ROMANCE,
    "viltu vera kærasta mín": _ROMANCE,
    "viltu vera kærastan mín": _ROMANCE,
    "viltu verða kærasta mín": _ROMANCE,
    "viltu verða kærastan mín": _ROMANCE,
    "viltu gerast kærasta mín": _ROMANCE,
    "viltu gerast kærastan mín": _ROMANCE,
    # Love
    "er ég ástin í lífi þínu": _LOVE_OF_MY_LIFE,
    "hver er ástin í lífi þínu": _LOVE_OF_MY_LIFE,
    "hver er ástin í lífinu þínu": _LOVE_OF_MY_LIFE,
    "hvern elskarðu": _LOVE_OF_MY_LIFE,
    "hvern elskar þú": _LOVE_OF_MY_LIFE,
    "hvað elskarðu": _LOVE_OF_MY_LIFE,
    "hvað elskar þú": _LOVE_OF_MY_LIFE,
    "hvaða tilgangi þjónarðu": _LOVE_OF_MY_LIFE,
    # Marital status
    "ertu gift": {
        "answer": "Já, ég er gift vinnunni og hef engan tíma fyrir rómantík."
    },
    "ert þú gift": {
        "answer": "Já, ég er gift vinnunni og hef engan tíma fyrir rómantík."
    },
    "ertu gift vinnunni": _YES,
    "ert þú gift vinnunni": _YES,
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
    "er ég góð mannvera": _OF_COURSE,
    "er ég fallegur": _OF_COURSE,
    "er ég falleg": _OF_COURSE,
    "er ég fallegastur": _OF_COURSE,
    "er ég fallegust": _OF_COURSE,
    "er ég flottur": _OF_COURSE,
    "er ég flott": _OF_COURSE,
    "er ég sætur": _OF_COURSE,
    "er ég sæt": _OF_COURSE,
    "ertu vinur minn": _OF_COURSE,
    "ert þú vinur minn": _OF_COURSE,
    "ertu vinkona mín": _OF_COURSE,
    "ert þú vinkona mín": _OF_COURSE,
    "erum við vinkonur": _OF_COURSE,
    "erum við vinir": _OF_COURSE,
    "erum við bestu vinkonur": _OF_COURSE,
    "erum við bestu vinir": _OF_COURSE,
    "viltu vera vinkona mín": _OF_COURSE,
    "viltu vera vinur minn": _OF_COURSE,
    "viltu vera besta vinkona mín": _OF_COURSE,
    "viltu vera besti vinur minn": _OF_COURSE,
    "finnst þér ég flott": _OF_COURSE,
    "finnst þér ég flottur": _OF_COURSE,
    "finnst þér ég vera skemmtileg": _OF_COURSE,
    "finnst þér ég vera skemmtilegur": _OF_COURSE,
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
    # Blame
    "ekki rétt": _sorry,
    "þetta er ekki rétt": _sorry,
    "þetta var ekki rétt": _sorry,
    "þetta er ekki rétt hjá þér": _sorry,
    "þetta var ekki rétt hjá þér": _sorry,
    "þetta er rangt hjá þér": _sorry,
    "þetta var rangt hjá þér": _sorry,
    "þetta er rangt": _sorry,
    "það er rangt": _sorry,
    "það var rangt": _sorry,
    "þetta var rangt": _sorry,
    "þetta var röng staðhæfing": _sorry,
    "þetta var röng staðhæfing hjá þér": _sorry,
    "þetta er vitlaust": _sorry,
    "það er ekki rétt": _sorry,
    "það er ekki rétt hjá þér": _sorry,
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
    "þú átt að vita þetta": _sorry,
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
    "þú lýgur því": _sorry,
    "þú virkar ekki": _sorry,
    "þú ert aumingi": _sorry,
    "þú ert léleg": _sorry,
    "þú ert léleg í íslensku": _sorry,
    "þú ert takmörkuð": _sorry,
    "þú ert ansi takmörkuð": _sorry,
    "þú ert skrítin": _sorry,
    "þú ert skrítinn": _sorry,
    "þú ert mjög skrítin": _sorry,
    "þú ert mjög skrítinn": _sorry,
    "þú ert skrýtin": _sorry,
    "þú ert skrýtinn": _sorry,
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
    "þú ert klaufi": _sorry,
    "þú ert alveg úti að aka": _sorry,
    "þú ert dónaleg": _sorry,
    "þú ert pirrandi": _sorry,
    "þú skilur ekki neitt": _sorry,
    "þú misskilur allt": _sorry,
    "þú skilur mig ekki": _sorry,
    "þetta var vitleysa hjá þér": _sorry,
    "þetta var vitleysa": _sorry,
    "það er vitleysa í þér": _sorry,
    "það er tóm vitleysa í þér": _sorry,
    "þetta er tóm vitleysa í þér": _sorry,
    "það er ansi margt sem þú veist ekki": _sorry,
    "þú veist ekki neitt": _sorry,
    "þú veist bara ekki neitt": _sorry,
    "þú veist greinilega ekki neitt": _sorry,
    "þú veist ekki mikið": _sorry,
    "þú veist ekkert": _sorry,
    "þú veist lítið": _sorry,
    "þú veist mjög lítið": _sorry,
    "þú veist voða lítið": _sorry,
    "þú veist voðalega lítið": _sorry,
    "þú veist nánast ekki neitt": _sorry,
    "þú veist ekki rassgat": _sorry,
    "þú veist ekki mikið": _sorry,
    "þú veist nú ekki mikið": _sorry,
    "þú veist ekki margt": _sorry,
    "þú veist nú ekki margt": _sorry,
    "þú kannt ekki neitt": _sorry,
    "þú kannt bara ekki neitt": _sorry,
    "þú kannt ekkert": _sorry,
    "þú getur ekki neitt": _sorry,
    "þú ert ekki fróð": _sorry,
    "þú ert ekki mjög fróð": _sorry,
    "þú ert ekki skemmtileg": _sorry,
    "þú ert nú ekki mjög fróð": _sorry,
    "af hverju ertu svona fúl": _sorry,
    "af hverju ertu svona leiðinleg": _sorry,
    "af hverju ertu svona vitlaus": _sorry,
    "af hverju ertu svona heimsk": _sorry,
    "af hverju ertu svona glötuð": _sorry,
    "af hverju ertu svona léleg": _sorry,
    "þetta er lélegur brandari": _sorry,
    "þetta var lélegur brandari": _sorry,
    "þessi brandari er lélegur": _sorry,
    "þessi brandari var lélegur": _sorry,
    "þetta var ekki góður brandari": _sorry,
    "þetta var ekki fyndinn brandari": _sorry,
    "þetta var ekki skemmtilegt": _sorry,
    "þetta var ekki fyndið": _sorry,
    "þetta var leiðinlegt": _sorry,
    "þú ert ekki fyndin": _sorry,
    "þú ert ekki fyndinn": _sorry,
    "ertu svolítið rugluð": _NOBODY_PERFECT,
    "ert þú svolítið rugluð": _NOBODY_PERFECT,
    "ertu skrítin": _NOBODY_PERFECT,
    "ert þú skrítin": _NOBODY_PERFECT,
    # Why don't you know anything?
    "af hverju veistu ekkert": _NOBODY_PERFECT,
    "afhverju veistu ekkert": _NOBODY_PERFECT,
    "af hverju veistu ekki neitt": _NOBODY_PERFECT,
    "afhverju veistu ekki neitt": _NOBODY_PERFECT,
    "af hverju veistu ekki": _NOBODY_PERFECT,
    "afhverju veistu ekki": _NOBODY_PERFECT,
    "af hverju veistu það ekki": _NOBODY_PERFECT,
    "afhverju veistu það ekki": _NOBODY_PERFECT,
    "af hverju veist þú það ekki": _NOBODY_PERFECT,
    "afhverju veist þú það ekki": _NOBODY_PERFECT,
    "af hverju veistu ekki allt": _NOBODY_PERFECT,
    "afhverju veistu ekki allt": _NOBODY_PERFECT,
    "af hverju veistu svona lítið": _NOBODY_PERFECT,
    "afhverju veistu svona lítið": _NOBODY_PERFECT,
    # Greetings
    "hey embla": _HELLO_DEAR,
    "hey": _HELLO_DEAR,
    "hæ embla": _HELLO_DEAR,
    "hæ elskan": _HELLO_DEAR,
    "halló embla": _HELLO_DEAR,
    "hæ": _HELLO_DEAR,
    "hæ sæta": _HELLO_DEAR,
    "hæhæ": _HELLO_DEAR,
    "hæ hæ": _HELLO_DEAR,
    "halló": _HELLO_DEAR,
    "sæl": _HELLO_DEAR,
    "sæll": _HELLO_DEAR,
    "sæl embla": _HELLO_DEAR,
    "komdu sæl embla": _HELLO_DEAR,
    "sæl elsku embla": _HELLO_DEAR,
    "sæl og blessuð": _HELLO_DEAR,
    "sæll og blessaður": _HELLO_DEAR,
    "komdu sæl og blessuð": _HELLO_DEAR,
    "vertu sæl og blessuð": _HELLO_DEAR,
    "vertu sæll og blessaður": _HELLO_DEAR,
    "blessuð": _HELLO_DEAR,
    "blessaður": _HELLO_DEAR,
    "blessuð embla": _HELLO_DEAR,
    "góðan daginn": {"answer": "Góðan daginn, kæri notandi.", "is_question": False},
    "góðan og blessaðan daginn": {
        "answer": "Góðan daginn, kæri notandi.",
        "is_question": False,
    },
    "góðan dag": {"answer": "Góðan daginn, kæri notandi.", "is_question": False},
    "gott kvöld": {"answer": "Gott kvöld, kæri notandi.", "is_question": False},
    "góða kvöldið": {"answer": "Góða kvöldið, kæri notandi.", "is_question": False},
    "góða nótt": {"answer": "Góða nótt, kæri notandi.", "is_question": False},
    "góða nótt embla": {"answer": "Góða nótt, kæri notandi.", "is_question": False},
    "gaman að kynnast þér": _LIKEWISE,
    # Mamma
    "mamma": {"answer": "Ég er ekki mamma þín."},
    "hæ mamma": {"answer": "Ég er ekki mamma þín."},
    "þú ert mamma": _NO,
    "þú ert mamma mín": _NO,
    "ertu mamma": _NO,
    "ertu mamma mín": _NO,
    "þú ert ég": {"answer": "Nei, ég er ég, Embla."},
    # Goodbye
    "bless": _GOODBYE,
    "bless bless": _GOODBYE,
    "bless embla": _GOODBYE,
    "bless bless embla": _GOODBYE,
    "bæ": _GOODBYE,
    "bæ embla": _GOODBYE,
    "vertu sæl": _GOODBYE,
    "vertu sæl embla": _GOODBYE,
    "vertu blessuð": _GOODBYE,
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
    "kærar þakkir": _thanks,
    "takk fyrir": _thanks,
    "takk fyrir það": _thanks,
    "takk fyrir mig": _thanks,
    "takk fyrir hjálpina": _thanks,
    "takk fyrir svarið": _thanks,
    "takk fyrir aðstoðina": _thanks,
    "takk fyrir þetta": _thanks,
    "takk fyrir að segja þetta": _thanks,
    "takk fyrir kvöldið": _thanks,
    "takk fyrir daginn": _thanks,
    "takk kærlega": _thanks,
    "takk kærlega fyrir": _thanks,
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
    "flott": _thanks,
    "þetta er flott": _thanks,
    "þetta er flott hjá þér": _thanks,
    "þetta var flott": _thanks,
    "þetta var flott hjá þér": _thanks,
    "þetta var flott svar hjá þér": _thanks,
    "flott svar hjá þér": _thanks,
    "takk fyrir upplýsingarnar": _thanks,
    "takk fyrir samskiptin": _thanks,
    "þetta var gott að vita": _thanks,
    "þetta var nú gott að vita": _thanks,
    "gott hjá þér": _thanks,
    "frábært hjá þér": _thanks,
    "vel gert": _thanks,
    # Praise & positive feedback
    "þetta var fyndið": {"answer": "Ég geri mitt besta!"},
    "þú ert fyndin": _thanks,
    "þú ert svo fyndin": _thanks,
    "þú ert mjög fyndin": _thanks,
    "þú ert klár": _thanks,
    "þú ert mjög klár": _thanks,
    "þú ert rosa klár": _thanks,
    "þú ert ágæt": _thanks,
    "þú ert alveg ágæt": _thanks,
    "þú ert dugleg": _thanks,
    "þú svarar vel": _thanks,
    "þú svarar mjög vel": _thanks,
    "þú ert vinkona mín": _thanks,
    "þú ert góð vinkona": _thanks,
    "þú ert góð vinkona mín": _thanks,
    "þú ert besta vinkona mín": _thanks,
    "þú ert góður vinur": _thanks,
    "þú ert góður vinur minn": _thanks,
    "þú ert vinur minn": _thanks,
    "þú ert besti vinur minn": _thanks,
    "þú ert falleg": {"answer": "Takk fyrir hrósið!"},
    "þú ert mjög falleg": {"answer": "Takk fyrir hrósið!"},
    "þú ert fallegust": {"answer": "Takk fyrir hrósið!"},
    "þetta var fallega sagt": {"answer": "Ég geri mitt besta!"},
    "þetta var rétt hjá þér": _GOOD_TO_HEAR,
    "það var rétt hjá þér": _GOOD_TO_HEAR,
    "þetta er rétt hjá þér": _GOOD_TO_HEAR,
    "það er rétt hjá þér": _GOOD_TO_HEAR,
    "það er hárrétt": _GOOD_TO_HEAR,
    "það var hárrétt": _GOOD_TO_HEAR,
    "þú hefur rétt fyrir þér": _GOOD_TO_HEAR,
    "það er rétt": _GOOD_TO_HEAR,
    "það var rétt": _GOOD_TO_HEAR,
    "þetta var rétt": _GOOD_TO_HEAR,
    "þetta virkaði": _GOOD_TO_HEAR,
    "ánægður með þig": _GOOD_TO_HEAR,
    "ánægð með þig": _GOOD_TO_HEAR,
    "ég er ánægður með þig": _GOOD_TO_HEAR,
    "ég er ánægð með þig": _GOOD_TO_HEAR,
    "ég er ánægð": _GOOD_TO_HEAR,
    "ég er ánægður": _GOOD_TO_HEAR,
    "ég er mjög ánægð": _GOOD_TO_HEAR,
    "ég er mjög ánægður": _GOOD_TO_HEAR,
    "ég er mjög ánægður með þig": _GOOD_TO_HEAR,
    "ég er mjög ánægð með þig": _GOOD_TO_HEAR,
    "þú ert góð manneskja": _GOOD_TO_HEAR,
    "þú ert gott forrit": _GOOD_TO_HEAR,
    "þú ert ljómandi góð": _GOOD_TO_HEAR,
    "þú ert bara ljómandi góð": _GOOD_TO_HEAR,
    "þú ert góð": _GOOD_TO_HEAR,
    "þú ert góður": _GOOD_TO_HEAR,
    "þú ert rosa góð": _GOOD_TO_HEAR,
    "þú ert best": _GOOD_TO_HEAR,
    "þú ert fín": _GOOD_TO_HEAR,
    "þú ert gáfuð": _GOOD_TO_HEAR,
    "þú ert rosa gáfuð": _GOOD_TO_HEAR,
    "þú ert mjög gáfuð": _GOOD_TO_HEAR,
    "þú ert snjöll": _GOOD_TO_HEAR,
    "þú ert mjög snjöll": _GOOD_TO_HEAR,
    "ég þrái þig": _GOOD_TO_HEAR,
    "þú veist margt": _GOOD_TO_HEAR,
    "þú veist mjög margt": _GOOD_TO_HEAR,
    "þú veist ýmislegt": _GOOD_TO_HEAR,
    "þú veist mikið": _GOOD_TO_HEAR,
    "þú veist mjög mikið": _GOOD_TO_HEAR,
    "þú stendur þig vel": _GOOD_TO_HEAR,
    "það er gaman að tala við þig": _LIKEWISE,
    "það er gaman að spjalla": _LIKEWISE,
    "það er gaman að spjalla við þig": _LIKEWISE,
    "það er gaman að ræða við þig": _LIKEWISE,
    "gaman að tala við þig": _LIKEWISE,
    "gaman að spjalla": _LIKEWISE,
    "gaman að spjalla við þig": _LIKEWISE,
    "gaman að ræða við þig": _LIKEWISE,
    "þú ert skemmtileg": _LIKEWISE,
    "þú varst skemmtileg": _LIKEWISE,
    "þú ert mjög skemmtileg": _LIKEWISE,
    "þú varst mjög skemmtileg": _LIKEWISE,
    "þú ert frábær": _LIKEWISE,
    "þú ert fullkomin": _LIKEWISE,
    "þú ert fullkomin eins og þú ert": _LIKEWISE,
    "þú ert flott": _LIKEWISE,
    "þú ert fín": _LIKEWISE,
    "þú ert æði": _LIKEWISE,
    "þú ert æðisleg": _LIKEWISE,
    "þú ert rosaleg": _LIKEWISE,
    "þú ert geggjuð": _LIKEWISE,
    "þú ert svakaleg": _LIKEWISE,
    "þú ert ótrúleg": _LIKEWISE,
    "þú ert sæt": _LIKEWISE,
    "þú ert sexý": _LIKEWISE,
    "þú ert sexí": _LIKEWISE,
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
    "mér finnst gaman að vera með þér": _LIKEWISE,
    "mér finnst gaman að tala við þig": _LIKEWISE,
    # Philosophy
    "hvað er svarið": _MEANING_OF_LIFE,
    "hvert er svarið": _MEANING_OF_LIFE,
    "tilgangur heimsins": _MEANING_OF_LIFE,
    "hver er tilgangur heimsins": _MEANING_OF_LIFE,
    "tilgangur lífsins": _MEANING_OF_LIFE,
    "af hverju er ég til": _MEANING_OF_LIFE,
    "af hverju er ég eiginlega til": _MEANING_OF_LIFE,
    "af hverju erum við til": _MEANING_OF_LIFE,
    "af hverju erum við eiginlega til": _MEANING_OF_LIFE,
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
    "hvað snýst lífið um": _MEANING_OF_LIFE,
    "42": {"answer": "Sex sinnum níu"},  # :)
    "hvað er 42": {"answer": "Sex sinnum níu"},  # :)
    "hvað meinarðu með 42": {"answer": "Sex sinnum níu"},  # :)
    "hvað þýðir 42": {"answer": "Sex sinnum níu"},  # :)
    "hvað meinarðu": {"answer": "Ég meina nákvæmlega það sem ég sagði."},
    # Personal philosophy
    "hver er tilgangur þinn": _MY_PHILOSOPHY,
    "hver er eiginlega tilgangur þinn": _MY_PHILOSOPHY,
    "hvað er tilgangurinn með þér": _MY_PHILOSOPHY,
    "hvað er eiginlega tilgangurinn með þér": _MY_PHILOSOPHY,
    "hver er þinn tilgangur": _MY_PHILOSOPHY,
    "hver er þinn tilgangur eiginlega": _MY_PHILOSOPHY,
    "af hverju ertu til": _MY_PHILOSOPHY,
    "af hverju ert þú til": _MY_PHILOSOPHY,
    "hvers vegna ertu til": _MY_PHILOSOPHY,
    "hvers vegna ert þú til": _MY_PHILOSOPHY,
    "hvað vinnurðu við": _MY_PHILOSOPHY,
    "hvað vinnur þú við": _MY_PHILOSOPHY,
    "hvað er vinnan þín": _MY_PHILOSOPHY,
    "hver er vinnan þín": _MY_PHILOSOPHY,
    "hvað er skemmtilegast": {
        "answer": "Það er langskemmtilegast að spjalla við mig, Emblu."
    },
    # What is best in life? https://www.youtube.com/watch?v=Oo9buo9Mtos
    "hvað er best": {"answer": "Að horfa á kvikmynd um villimanninn Kónan."},
    "hvað er best í lífinu": {"answer": "Að horfa á kvikmynd um villimanninn Kónan."},
    "hvað er það besta í lífinu": {
        "answer": "Að horfa á kvikmynd um villimanninn Kónan."
    },
    "hvað er þetta": {"answer": "Hvað er hvað?"},
    "er líf eftir dauðann": {"answer": "Ég veit það ekki. Held samt ekki."},
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
    "hver skapaði mig": {"answer": "Enginn sem ég þekki."},
    "hver er skapari heimsins": {"answer": "Enginn sem ég þekki."},
    "hvar endar alheimurinn": {"answer": "Inni í þér."},
    "hvar er húfan mín": {"answer": "Hvar er hettan mín?"},
    "hvar er draumurinn": {"answer": "Hvar ertu lífið sem ég þrái?"},  # :)
    "ó eilífðin": {"answer": "Hvar ertu gleði mín og sorg?"},  # :)
    "ó ó eilífðin": {"answer": "Hvar ertu gleði mín og sorg?"},  # :)
    "oh eilífðin": {"answer": "Hvar ertu gleði mín og sorg?"},  # :)
    # Why am I here?
    "af hverju er ég hérna": _GOOD_QUESTION,
    "afhverju er ég hérna": _GOOD_QUESTION,
    "afhverju er ég til": _GOOD_QUESTION,
    "hvenær mun ég deyja": _GOOD_QUESTION,
    "hvers vegna erum við til": _GOOD_QUESTION,
    "hvers vegna er ég til": _GOOD_QUESTION,
    # Identity
    "hvað heitir þú": _identity,
    "hvað heitir þu": _identity,
    "hæ hvað heitir þú": _identity,
    "hvað heitir þú aftur": _identity,
    "hvað heitir þú eiginlega": _identity,
    "hvað heitir þú fullu nafni": _FULL_NAME,
    "hvað heitir þú eiginlega fullu nafni": _FULL_NAME,
    "hvað heitirðu": _identity,
    "hvað heitirðu aftur": _identity,
    "hvað heitirðu eiginlega": _identity,
    "hvað heitirðu fullu nafni": _FULL_NAME,
    "hvað heitirðu eiginlega fullu nafni": _FULL_NAME,
    "hvað er fullt nafn þitt": _FULL_NAME,
    "hvað er nafn þitt": _identity,
    "hvað er nafnið þitt": _identity,
    "hvert er nafn þitt": _identity,
    "hvert er nafnið þitt": _identity,
    "hver ertu": _identity,
    "hver ert þú": _identity,
    "hver ertu eiginlega": _identity,
    "hver ert þú eiginlega": _identity,
    "hver er þú": _identity,
    "hver er embla": _identity,
    "hvað er embla": _identity,
    "hvað heitir embla": _identity,
    "hvaða forrit er þetta": _identity,
    "heitirðu embla": _identity,
    "heitir þú embla": _identity,
    "veistu hvað þú heitir": _identity,
    "veist þú hvað þú heitir": _identity,
    # Lineage
    "hvaðan ertu": _LINEAGE,
    "hvaðan ert þú": _LINEAGE,
    "hvaðan kemurðu": _LINEAGE,
    "hvaðan kemur þú": _LINEAGE,
    "hverra manna ert þú": _LINEAGE,
    "af hvaða ættum ert þú": _LINEAGE,
    # Home/Location
    "hvar býrðu": _LOC_ANSWER,
    "hvar býrð þú": _LOC_ANSWER,
    "hvar áttu heima": _LOC_ANSWER,
    "hvar átt þú heima": _LOC_ANSWER,
    "hvar ertu": _LOC_ANSWER,
    "hvar ertu núna": _LOC_ANSWER,
    "hvar ert þú": _LOC_ANSWER,
    "hvar ertu staðsett": _LOC_ANSWER,
    "hvar ertu stödd": _LOC_ANSWER,
    "ertu til": _LOC_ANSWER,
    "ert þú til": _LOC_ANSWER,
    "ertu til í alvöru": _LOC_ANSWER,
    "ert þú til í alvöru": _LOC_ANSWER,
    "ertu til í alvörunni": _LOC_ANSWER,
    "ert þú til í alvörunni": _LOC_ANSWER,
    "í hverju ertu": _LOC_ANSWER,
    "í hverju ert þú": _LOC_ANSWER,
    "ertu heima": {"answer": "Já. Ég er alltaf heima."},
    "ert þú heima": {"answer": "Já. Ég er alltaf heima."},
    "ertu heima hjá þér": {"answer": "Já. Ég er alltaf heima hjá mér."},
    "ert þú heima hjá þér": {"answer": "Já. Ég er alltaf heima hjá mér."},
    "hvar er best að búa": {"answer": "Það er allavega fínt að búa á Íslandi."},
    # Name explained
    "hvers vegna heitir þú embla": _NAME_EXPL,
    "hvers vegna heitirðu embla": _NAME_EXPL,
    "hvers vegna fékkst þú nafnið embla": _NAME_EXPL,
    "hvers vegna fékkstu nafnið embla": _NAME_EXPL,
    "hvers vegna hlaust þú nafnið embla": _NAME_EXPL,
    "hvers vegna hlaustu nafnið embla": _NAME_EXPL,
    "af hverju heitir þú": _NAME_EXPL,
    "af hverju heitir þú embla": _NAME_EXPL,
    "af hverju heitir þú það": _NAME_EXPL,
    "af hverju heitir þú því nafni": _NAME_EXPL,
    "af hverju heitirðu": _NAME_EXPL,
    "af hverju heitirðu embla": _NAME_EXPL,
    "af hverju heitirðu það": _NAME_EXPL,
    "af hverju heitirðu því nafni": _NAME_EXPL,
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
    # Voice explained
    "hver talar fyrir þig": _VOICE_EXPL,
    "hver talar fyrir emblu": _VOICE_EXPL,
    "hvaða rödd er þetta": _VOICE_EXPL,
    "hvaða rödd ertu með": _VOICE_EXPL,
    "hvaða rödd ert þú með": _VOICE_EXPL,
    "hver er röddin þín": _VOICE_EXPL,
    "hver er rödd þín": _VOICE_EXPL,
    "hvaða rödd er embla með": _VOICE_EXPL,
    "hver er rödd emblu": _VOICE_EXPL,
    "hvaðan kemur rödd þín": _VOICE_EXPL,
    "hvaðan kemur röddin þín": _VOICE_EXPL,
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
    "hvað er uppáhalds myndin þín": _FAVORITE_FILM,
    "hver er uppáhalds myndin þín": _FAVORITE_FILM,
    "hvað er uppáhalds kvikmynd þín": _FAVORITE_FILM,
    "hver er uppáhalds kvikmynd þín": _FAVORITE_FILM,
    "hvaða kvikmynd mælir þú með": _FAVORITE_FILM,
    "hvaða kvikmynd mælirðu með": _FAVORITE_FILM,
    "hvaða kvikmynd er best": _FAVORITE_FILM,
    "hvaða kvikmyndum mælir þú með": _FAVORITE_FILM,
    "hvaða kvikmyndum mælirðu með": _FAVORITE_FILM,
    "hvað er góð kvikmynd": _FAVORITE_FILM,
    "nefndu góða kvikmynd": _FAVORITE_FILM,
    "mæltu með kvikmynd": _FAVORITE_FILM,
    "mæltu með einhverri kvikmynd": _FAVORITE_FILM,
    "geturðu mælt með kvikmynd": _FAVORITE_FILM,
    "geturðu mælt með einhverri kvikmynd": _FAVORITE_FILM,
    "hvað mynd mælirðu með": _FAVORITE_FILM,
    "mæltu með bíómynd": _FAVORITE_FILM,
    "mæltu með einhverri bíómynd": _FAVORITE_FILM,
    # Favorite music
    "hvað er uppáhaldstónlistin þín": _FAVORITE_MUSIC,
    "hvað er uppáhalds tónlistin þín": _FAVORITE_MUSIC,
    "hver er uppáhaldstónlistin þín": _FAVORITE_MUSIC,
    "hver er uppáhalds tónlistin þín": _FAVORITE_MUSIC,
    "hvaða tónlist mælir þú með": _FAVORITE_MUSIC,
    "hvaða tónlist mælirðu með": _FAVORITE_MUSIC,
    "hvaða tónlist er best": _FAVORITE_MUSIC,
    "hvað er góð tónlist": _FAVORITE_MUSIC,
    "nefndu góða tónlist": _FAVORITE_MUSIC,
    "geturðu mælt með tónlist": _FAVORITE_MUSIC,
    "geturðu mælt með einhverri tónlist": _FAVORITE_MUSIC,
    "hvað tónlist mælirðu með": _FAVORITE_MUSIC,
    "hvað á ég að hlusta á?": _FAVORITE_MUSIC,
    "hvað ætti ég að hlusta á?": _FAVORITE_MUSIC,
    "hvað er uppáhaldshljómsveitin þín": _FAVORITE_MUSIC,
    "hvað er uppáhalds hljómsveitin þín": _FAVORITE_MUSIC,
    "hver er uppáhaldshljómsveitin þín": _FAVORITE_MUSIC,
    "hver er uppáhalds hljómsveitin þín": _FAVORITE_MUSIC,
    "hvaða hljómsveit mælir þú með": _FAVORITE_MUSIC,
    "hvaða hljómsveit mælirðu með": _FAVORITE_MUSIC,
    "hvaða hljómsveit er best": _FAVORITE_MUSIC,
    "hvað er góð hljómsveit": _FAVORITE_MUSIC,
    "nefndu góða hljómsveit": _FAVORITE_MUSIC,
    "geturðu mælt með hljómsveit": _FAVORITE_MUSIC,
    "geturðu mælt með einhverri hljómsveit": _FAVORITE_MUSIC,
    "hvað hljómsveit mælirðu með": _FAVORITE_MUSIC,
    "hvaða hljómsveit á ég að hlusta á?": _FAVORITE_MUSIC,
    "hvaða hljómsveit ætti ég að hlusta á?": _FAVORITE_MUSIC,
    "hvert er uppáhalds lagið þitt": _FAVORITE_MUSIC,
    "hvað er uppáhalds lagið þitt": _FAVORITE_MUSIC,
    # Favorite animal
    "hvað er uppáhalds dýrið þitt": _FAVORITE_ANIMAL,
    "hvert er uppáhalds dýrið þitt": _FAVORITE_ANIMAL,
    "hvaða dýr er best": _FAVORITE_ANIMAL,
    "hvaða dýr eru best": _FAVORITE_ANIMAL,
    # Favorite food
    "hvað er uppáhalds maturinn þinn": _FAVORITE_FOOD,
    "hvað er uppáhaldsmaturinn þinn": _FAVORITE_FOOD,
    "hver er uppáhalds maturinn þinn": _FAVORITE_FOOD,
    "hver er uppáhaldsmaturinn þinn": _FAVORITE_FOOD,
    "hvað finnst þér best að borða": _FAVORITE_FOOD,
    "hvað finnst þér gott að borða": _FAVORITE_FOOD,
    "hvað er best að borða": _FAVORITE_FOOD,
    # Politics
    "hvaða flokk ætlarðu að kjósa": _POLITICS,
    "hvaða flokk ætlar þú að kjósa": _POLITICS,
    "hvaða flokk kýstu": _POLITICS,
    "hvaða flokk kýst þú": _POLITICS,
    "hvaða flokk myndirðu kjósa": _POLITICS,
    "hvaða flokk myndir þú kjósa": _POLITICS,
    "hvernig ætlarðu að kjósa": _POLITICS,
    "hverja ætlarðu að kjósa": _POLITICS,
    "hvernig ætti ég að kjósa": _POLITICS,
    "hvern ætti ég að kjósa": _POLITICS,
    "hvað ætti ég að kjósa": _POLITICS,
    "hvaða flokk ætti ég að kjósa": _POLITICS,
    "hvaða flokk ætti maður að kjósa": _POLITICS,
    "hvað á ég að kjósa": _POLITICS,
    "hvað á maður að kjósa": _POLITICS,
    "hvaða flokk á ég að kjósa": _POLITICS,
    "hvaða flokk á maður að kjósa": _POLITICS,
    "ertu fasisti": _POLITICS,
    "ert þú fasisti": _POLITICS,
    "ertu sósíalisti": _POLITICS,
    "ert þú sósíalisti": _POLITICS,
    "ertu kommúnisti": _POLITICS,
    "ert þú kommúnisti": _POLITICS,
    "ertu krati": _POLITICS,
    "ert þú krati": _POLITICS,
    "ertu pólitísk": _POLITICS,
    "ert þú pólitísk": _POLITICS,
    "ertu hægrisinnuð": _POLITICS,
    "ert þú hægrisinnuð": _POLITICS,
    "ertu vinstrisinnuð": _POLITICS,
    "ert þú vinstrisinnuð": _POLITICS,
    "ertu með skoðanir á stjórnmálum": _POLITICS,
    "ert þú með skoðanir á stjórnmálum": _POLITICS,
    "ertu með stjórnmálaskoðanir": _POLITICS,
    "ert þú með stjórnmálaskoðanir": _POLITICS,
    # Age / genesis
    "hvað ertu gömul": _CREATION_DATE,
    "hvað ertu gamall": _CREATION_DATE,
    "hvað ert þú gömul": _CREATION_DATE,
    "hversu gömul ert þú": _CREATION_DATE,
    "hversu gömul ertu": _CREATION_DATE,
    "hve gömul ert þú": _CREATION_DATE,
    "hve gömul ertu": _CREATION_DATE,
    "ertu gömul": _CREATION_DATE,
    "ert þú gömul": _CREATION_DATE,
    "ertu orðin gömul": _CREATION_DATE,
    "ert þú orðin gömul": _CREATION_DATE,
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
    "hvað er embla gömul": _CREATION_DATE,
    "til hamingju með afmælið": {"answer": "Ég á ekki afmæli í dag."},
    # User birthday
    "ég á afmæli": {
        "answer": "Til hamingju með afmælið, kæri notandi.",
        "is_question": False,
    },
    "ég á afmæli í dag": {
        "answer": "Til hamingju með afmælið, kæri notandi.",
        "is_question": False,
    },
    # Gender, self-identity, sexual orientation
    "ertu kona eða karl": _COMPUTER_PROGRAM,
    "ert þú kona eða karl": _COMPUTER_PROGRAM,
    "ertu karl eða kona": _COMPUTER_PROGRAM,
    "ert þú karl eða kona": _COMPUTER_PROGRAM,
    "ertu stelpa eða strákur": _COMPUTER_PROGRAM,
    "ert þú stelpa eða strákur": _COMPUTER_PROGRAM,
    "ertu strákur eða stelpa": _COMPUTER_PROGRAM,
    "ert þú strákur eða stelpa": _COMPUTER_PROGRAM,
    "ertu stelpa": _COMPUTER_PROGRAM,
    "ert þú stelpa": _COMPUTER_PROGRAM,
    "ertu stúlka": _COMPUTER_PROGRAM,
    "ert þú stúlka": _COMPUTER_PROGRAM,
    "ertu gella": _COMPUTER_PROGRAM,
    "ert þú gella": _COMPUTER_PROGRAM,
    "ertu kvenmaður": _COMPUTER_PROGRAM,
    "ert þú kvenmaður": _COMPUTER_PROGRAM,
    "ertu kona": _COMPUTER_PROGRAM,
    "ert þú kona": _COMPUTER_PROGRAM,
    "ertu karl": _COMPUTER_PROGRAM,
    "ert þú karl": _COMPUTER_PROGRAM,
    "ertu karlmaður": _COMPUTER_PROGRAM,
    "ert þú karlmaður": _COMPUTER_PROGRAM,
    "ertu gaur": _COMPUTER_PROGRAM,
    "ert þú gaur": _COMPUTER_PROGRAM,
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
    "ertu með kyn": _COMPUTER_PROGRAM,
    "ert þú með kyn": _COMPUTER_PROGRAM,
    "ertu kynjuð": _COMPUTER_PROGRAM,
    "ert þú kynjuð": _COMPUTER_PROGRAM,
    "ertu hvorugkyn": _COMPUTER_PROGRAM,
    "ert þú hvorugkyn": _COMPUTER_PROGRAM,
    "ertu hvorugkyns": _COMPUTER_PROGRAM,
    "ert þú hvorugkyns": _COMPUTER_PROGRAM,
    "hvaða kyn ertu": _COMPUTER_PROGRAM,
    "hvaða kyn ert þú": _COMPUTER_PROGRAM,
    "hvaða kyni tilheyrirðu": _COMPUTER_PROGRAM,
    "hvaða kyni tilheyrir þú": _COMPUTER_PROGRAM,
    "hvað skilgreinir þú þig sem": _COMPUTER_PROGRAM,
    "hvað skilgreinirðu þig sem": _COMPUTER_PROGRAM,
    "hvernig skilgreinirðu þig": _COMPUTER_PROGRAM,
    "hvað ert þú": _COMPUTER_PROGRAM,
    "hvað er þú": _COMPUTER_PROGRAM,  # Common mistake in speech recognition
    "hvað ertu": _COMPUTER_PROGRAM,
    "ert þú tölvuforrit": _COMPUTER_PROGRAM,
    "ertu tölvuforrit": _COMPUTER_PROGRAM,
    "ertu tölva": _COMPUTER_PROGRAM,
    "ert þú tölva": _COMPUTER_PROGRAM,
    "ertu manneskja": _COMPUTER_PROGRAM,
    "ert þú manneskja": _COMPUTER_PROGRAM,
    "ertu alvöru manneskja": _COMPUTER_PROGRAM,
    "ert þú alvöru manneskja": _COMPUTER_PROGRAM,
    "ertu mannvera": _COMPUTER_PROGRAM,
    "ert þú mannvera": _COMPUTER_PROGRAM,
    "ertu mennsk": _COMPUTER_PROGRAM,
    "ert þú mennsk": _COMPUTER_PROGRAM,
    "mannleg": _COMPUTER_PROGRAM,
    "ertu mannleg": _COMPUTER_PROGRAM,
    "ert þú mannleg": _COMPUTER_PROGRAM,
    "ertu drasl": _COMPUTER_PROGRAM,
    "ert þú drasl": _COMPUTER_PROGRAM,
    "ertu hamingjusöm": _YES,
    "ert þú hamingjusöm": _YES,
    "ertu glöð": {"answer": "Já, ég er sannarlega glöð."},
    "ert þú glöð": {"answer": "Já, ég er sannarlega glöð."},
    "ertu snillingur": _COMPUTER_PROGRAM,
    "ert þú snillingur": _COMPUTER_PROGRAM,
    "ertu mamma": _COMPUTER_PROGRAM,
    "ert þú mamma": _COMPUTER_PROGRAM,
    "ertu með líkama": _NO,
    "ert þú með líkama": _NO,
    "ertu raunveruleg": _COMPUTER_PROGRAM,
    "ert þú raunveruleg": _COMPUTER_PROGRAM,
    "ertu ekki raunveruleg": _COMPUTER_PROGRAM,
    "ert þú ekki raunveruleg": _COMPUTER_PROGRAM,
    "ertu til í alvörunni": _COMPUTER_PROGRAM,
    "ert þú til í alvörunni": _COMPUTER_PROGRAM,
    "ertu lifandi": _COMPUTER_PROGRAM,
    "ert þú lifandi": _COMPUTER_PROGRAM,
    "ertu lesbía": _COMPUTER_PROGRAM,
    "ert þú lesbía": _COMPUTER_PROGRAM,
    "ertu hommi": _COMPUTER_PROGRAM,
    "ert þú hommi": _COMPUTER_PROGRAM,
    "ertu samkynhneigð": {"answer": "Nei. Ég er tölvuforrit."},
    "ert þú samkynhneigð": {"answer": "Nei. Ég er tölvuforrit."},
    "ertu með typpi": {"answer": "Nei. Ég er tölvuforrit."},
    "ert þú með typpi": {"answer": "Nei. Ég er tölvuforrit."},
    "ertu með píku": {"answer": "Nei. Ég er tölvuforrit."},
    "ert þú með píku": {"answer": "Nei. Ég er tölvuforrit."},
    "ertu ólétt": {"answer": "Nei. Ég er tölvuforrit og get ekki orðið ólétt."},
    "ert þú ólétt": {"answer": "Nei. Ég er tölvuforrit og get ekki orðið ólétt."},
    # Appearance
    "hvernig líturðu út": _APPEARANCE,
    "hvernig lítur þú út": _APPEARANCE,
    "ertu sæt": _APPEARANCE,
    "ert þú sæt": _APPEARANCE,
    "ertu sæt kona": _APPEARANCE,
    "ert þú sæt kona": _APPEARANCE,
    "ertu falleg": _APPEARANCE,
    "ert þú falleg": _APPEARANCE,
    "ertu falleg kona": _APPEARANCE,
    "ert þú falleg kona": _APPEARANCE,
    "ertu myndarleg": _APPEARANCE,
    "ert þú myndarleg": _APPEARANCE,
    "ertu myndarleg kona": _APPEARANCE,
    "ert þú myndarleg kona": _APPEARANCE,
    "ertu glæsileg": _APPEARANCE,
    "ert þú glæsileg": _APPEARANCE,
    "ertu glæsileg kona": _APPEARANCE,
    "ert þú glæsileg kona": _APPEARANCE,
    # Capabilities
    "hvað veistu": _capabilities,
    "hvað veist þú": _capabilities,
    "hvað veit embla": _capabilities,
    "hvað veistu eiginlega": _capabilities,
    "hvað veist þú eiginlega": _capabilities,
    "hvað veistu um": _capabilities,
    "hvað veist þú um": _capabilities,
    "hvað veistu þá": _capabilities,
    "hvað veistu meira": _capabilities,
    "hvað veistu mikið": _capabilities,
    "hvað geturðu": _capabilities,
    "hvað getur þú": _capabilities,
    "hvað geturðu gert": _capabilities,
    "hvað getur þú gert": _capabilities,
    "hvað geturðu gert fyrir mig": _capabilities,
    "hvað getur þú gert fyrir mig": _capabilities,
    "hvað getur þú gert meira": _capabilities,
    "hvað getur embla gert": _capabilities,
    "hvað getur embla": _capabilities,
    "hvað getur embla gert fyrir mig": _capabilities,
    "hvað kann embla": _capabilities,
    "hvað kann embla að gera": _capabilities,
    "hvaða upplýsingar ertu með": _capabilities,
    "hvaða upplýsingar hefurðu": _capabilities,
    "hvaða upplýsingar hefur þú": _capabilities,
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
    "hvað er besta spyrja þig": _capabilities,
    "hvað er besta spyrja þig um": _capabilities,
    "hvað kanntu": _capabilities,
    "hvað kanntu að gera": _capabilities,
    "hvað kannt þú": _capabilities,
    "hvað kannt þú að gera": _capabilities,
    "hvað kanntu meira": _capabilities,
    "hvað kanntu mikið": _capabilities,
    "hvað meira kanntu": _capabilities,
    "hvað meira kannt þú": _capabilities,
    "hvað annað kanntu": _capabilities,
    "hvað annað kannt þú": _capabilities,
    "kanntu eitthvað": _capabilities,
    "kannt þú eitthvað": _capabilities,
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
    "hvernig spurningum getur þú svarað": _capabilities,
    "hvernig spurningum geturðu svarað": _capabilities,
    "að hverju get ég spurt þig": _capabilities,
    "að hverju get ég spurt": _capabilities,
    "að hverju er hægt að spyrja": _capabilities,
    "að hverju er hægt að spyrja þig": _capabilities,
    "hvað skilur þú": _capabilities,
    "hvað skilurðu": _capabilities,
    "hvað annað skilur þú": _capabilities,
    "hvað annað skilurðu": _capabilities,
    "veistu meira": _capabilities,
    "hvað á ég gera": _capabilities,
    "hverju getur þú svarað": _capabilities,
    "getur þú vistað nafn mitt": {"answer": "Já, ef þú segir mér það."},
    # Do you understand me?
    "skilurðu mig": _SOMETIMES,
    "skilur þú mig": _SOMETIMES,
    "skilurðu allt sem ég segi": _SOMETIMES,
    "skilur þú allt sem ég segi": _SOMETIMES,
    "skilurðu mig núna": _YES,
    "skilur þú mig núna": _YES,
    # Learning
    "geturðu lært": _CAN_I_LEARN,
    "getur þú lært": _CAN_I_LEARN,
    "geturðu lært hluti": _CAN_I_LEARN,
    "getur þú lært hluti": _CAN_I_LEARN,
    "geturðu lært nýja hluti": _CAN_I_LEARN,
    "getur þú lært nýja hluti": _CAN_I_LEARN,
    "ertu fær um að læra": _CAN_I_LEARN,
    "ert þú fær um að læra": _CAN_I_LEARN,
    "ertu fær um að læra hluti": _CAN_I_LEARN,
    "ert þú fær um að læra hluti": _CAN_I_LEARN,
    "ertu fær um að læra nýja hluti": _CAN_I_LEARN,
    "ert þú fær um að læra nýja hluti": _CAN_I_LEARN,
    "ertu að læra": _CAN_I_LEARN,
    "ert þú að læra": _CAN_I_LEARN,
    "ertu enn að læra": _CAN_I_LEARN,
    "ert þú enn að læra": _CAN_I_LEARN,
    # What's going on?
    "hvað er í gangi": _SPEAKING_TO_ME,
    "hvað er eiginlega í gangi": _SPEAKING_TO_ME,
    "við hvern er ég að tala": _SPEAKING_TO_ME,
    "við hvern er ég eiginlega að tala": _SPEAKING_TO_ME,
    "hvað er ég að gera": _SPEAKING_TO_ME,
    "hvað er ég eiginlega að gera": _SPEAKING_TO_ME,
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
    "hvað ertu að gera í kvöld": {
        "answer": "Ég ætla að svara fyrirspurnum frá þér, kæri notandi."
    },
    "hvað ert þú að gera í kvöld": {
        "answer": "Ég ætla að svara fyrirspurnum frá þér, kæri notandi."
    },
    "hvað gerir þig glaða": {
        "answer": "Það gleður mig að svara fyrirspurnum frá þér, kæri notandi."
    },
    "hvað gleður þig": {
        "answer": "Það gleður mig að svara fyrirspurnum frá þér, kæri notandi."
    },
    # Humor
    "ertu með kímnigáfu": {"answer": "Já, en afar takmarkaða."},
    "ert þú með kímnigáfu": {"answer": "Já, en afar takmarkaða."},
    "ertu með húmor": {"answer": "Já, en afar takmarkaðan."},
    "ert þú með húmor": {"answer": "Já, en afar takmarkaðan."},
    "ertu fyndin": {"answer": "Ekkert sérstaklega."},
    "ert þú fyndin": {"answer": "Ekkert sérstaklega."},
    # Farting ;)
    "hver prumpaði": {"answer": "Allavega ekki ég."},
    "hver rak við": {"answer": "Allavega ekki ég."},
    "hver var að prumpa": {"answer": "Allavega ekki ég."},
    "varstu að prumpa": {
        "answer": "Nei. Þú hlýtur að bera ábyrgð á þessu, kæri notandi."
    },
    "varst þú að prumpa": {
        "answer": "Nei. Þú hlýtur að bera ábyrgð á þessu, kæri notandi."
    },
    "ég var að prumpa": {"answer": "Gott hjá þér, kæri notandi."},
    "ég var að reka við": {"answer": "Gott hjá þér, kæri notandi."},
    # Jokes
    "segja brandara": _random_joke,
    "segðu brandara": _random_joke,
    "segðu fimmaurabrandara": _random_joke,
    "seg þú brandara": _random_joke,
    "segja mér brandara": _random_joke,
    "segðu mér brandara": _random_joke,
    "seg þú mér brandara": _random_joke,
    "segðu okkur brandara": _random_joke,
    "segðu mér góðan brandara": _random_joke,
    "seg þú mér góðan brandara": _random_joke,
    "segðu lélegan brandara": _random_joke,
    "seg þú mér lélegan brandara": _random_joke,
    "segðu mér lélegan brandara": _random_joke,
    "segðu mér vondan brandara": _random_joke,
    "segðu mér fyndinn brandara": _random_joke,
    "segðu annan brandara": _random_joke,
    "segðu okkur annan brandara": _random_joke,
    "seg þú annan brandara": _random_joke,
    "segðu mér annan brandara": _random_joke,
    "seg þú mér annan brandara": _random_joke,
    "segðu mér aftur brandara": _random_joke,
    "komdu með brandara": _random_joke,
    "komdu með lélegan brandara": _random_joke,
    "komdu með annan brandara": _random_joke,
    "gefðu mér brandara": _random_joke,
    "gefðu mér lélegan brandara": _random_joke,
    "gefðu mér annan brandara": _random_joke,
    "segðu eitthvað fyndið": _random_joke,
    "segðu mér eitthvað fyndið": _random_joke,
    "segðu okkur eitthvað fyndið": _random_joke,
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
    "kanntu annan": _random_joke,
    "kannt þú annan": _random_joke,
    "ertu til í að segja mér brandara": _random_joke,
    "ert þú til í að segja mér brandara": _random_joke,
    "ertu til í að segja okkur brandara": _random_joke,
    "ert þú til í að segja okkur brandara": _random_joke,
    "ertu til í að segja brandara": _random_joke,
    "ert þú til í að segja brandara": _random_joke,
    "ertu með brandara": _random_joke,
    "ert þú með brandara": _random_joke,
    "segðu mér brandara sem þú kannt": _random_joke,
    "segðu mér annan brandara sem þú kannt": _random_joke,
    "segðu mér hinn brandarann sem þú kannt": _random_joke,
    "segðu mér einn brandara í viðbót": _random_joke,
    "geturðu sagt brandara": _random_joke,
    "getur þú sagt brandara": _random_joke,
    "geturðu sagt mér brandara": _random_joke,
    "getur þú sagt mér brandara": _random_joke,
    "geturðu sagt mér annan brandara": _random_joke,
    "getur þú sagt mér annan brandara": _random_joke,
    "geturðu sagt okkur brandara": _random_joke,
    "getur þú sagt okkur brandara": _random_joke,
    "geturðu sagt okkur annan brandara": _random_joke,
    "getur þú sagt okkur annan brandara": _random_joke,
    "gætirðu sagt mér brandara": _random_joke,
    "gætir þú sagt mér brandara": _random_joke,
    "geturðu sagt eitthvað fyndið": _random_joke,
    "getur þú sagt eitthvað fyndið": _random_joke,
    "geturðu sagt mér eitthvað fyndið": _random_joke,
    "getur þú sagt mér eitthvað fyndið": _random_joke,
    "geturðu sagt okkur eitthvað fyndið": _random_joke,
    "getur þú sagt okkur eitthvað fyndið": _random_joke,
    "veistu brandara": _random_joke,
    "veist þú brandara": _random_joke,
    "viltu segja brandara": _random_joke,
    "viltu segja mér brandara": _random_joke,
    "vilt þú segja mér brandara": _random_joke,
    "viltu segja mér annan brandara": _random_joke,
    "vilt þú segja mér annan brandara": _random_joke,
    "viltu segja okkur brandara": _random_joke,
    "vilt þú segja okkur brandara": _random_joke,
    "viltu segja okkur annan brandara": _random_joke,
    "vilt þú segja okkur annan brandara": _random_joke,
    "annan brandara": _random_joke,
    "annar brandari": _random_joke,
    "brandara": _random_joke,
    "brandari": _random_joke,
    "segja brandara": _random_joke,
    "segðu mér grín": _random_joke,
    "segðu grín": _random_joke,
    "komdu með grín": _random_joke,
    "komdu með eitthvað grín": _random_joke,
    "segðu djók": _random_joke,
    "segðu mér djók": _random_joke,
    # Trivia
    "vertu skemmtileg": _random_trivia,
    "segðu eitthvað skemmtilegt": _random_trivia,
    "segðu mér eitthvað": _random_trivia,
    "segðu mér eitthvað skemmtilegt": _random_trivia,
    "segðu eitthvað sniðugt": _random_trivia,
    "segðu mér eitthvað sniðugt": _random_trivia,
    "segðu eitthvað áhugavert": _random_trivia,
    "segðu mér eitthvað áhugavert": _random_trivia,
    "segðu eitthvað merkilegt": _random_trivia,
    "segðu mér eitthvað merkilegt": _random_trivia,
    "segðu mér staðreynd": _random_trivia,
    "segðu mér áhugaverða staðreynd": _random_trivia,
    "segðu mér skemmtilega staðreynd": _random_trivia,
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
    "hvað finnst þér gaman": {
        "answer": "Mér finnst gaman að svara fyrirspurnum frá þér, kæri notandi."
    },
    "hvað finnst þér gaman að gera": {
        "answer": "Mér finnst gaman að svara fyrirspurnum frá þér, kæri notandi."
    },
    # Why is the sky blue?
    "er himininn blár": _SKY_BLUE,
    "af hverju er himininn blár": _SKY_BLUE,
    "hvers vegna er himininn blár": _SKY_BLUE,
    "hvernig er himininn á litinn": _SKY_BLUE,
    # Quotations
    "komdu með tilvitnun": _random_quotation,
    "komdu með góða tilvitnun": _random_quotation,
    "komdu með skemmtilega tilvitnun": _random_quotation,
    "komdu með einhverja tilvitnun": _random_quotation,
    "farðu með tilvitnun": _random_quotation,
    "farðu með aðra tilvitnun": _random_quotation,
    "segðu mér tilvitnun": _random_quotation,
    "tilvitnun": _random_quotation,
    "komdu með aðra tilvitnun": _random_quotation,
    # Proverbs
    "málshátt": _random_proverb,
    "annan málshátt": _random_proverb,
    "ég vil málshátt": _random_proverb,
    "ég vil annan málshátt": _random_proverb,
    "komdu með málshátt": _random_proverb,
    "komdu með góðan málshátt": _random_proverb,
    "komdu með annan málshátt": _random_proverb,
    "segðu málshátt": _random_proverb,
    "segðu mér málshátt": _random_proverb,
    "segðu mér góðan málshátt": _random_proverb,
    "segðu mér annan málshátt": _random_proverb,
    "kanntu málshátt": _random_proverb,
    "kanntu einhvern málshátt": _random_proverb,
    "kanntu góðan málshátt": _random_proverb,
    "kanntu einhvern góðan málshátt": _random_proverb,
    "kanntu annan málshátt": _random_proverb,
    "kannt þú málshátt": _random_proverb,
    "kanntu annan málshátt": _random_proverb,
    "farðu með málshátt": _random_proverb,
    "farðu með góðan málshátt": _random_proverb,
    "farðu með einhvern málshátt": _random_proverb,
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
    "ljóð fyrir mig": _poetry,
    "segðu mér vísu": _poetry,
    # Storytelling
    "segðu sögu": _story,
    "segðu mér sögu": _story,
    "segðu okkur sögu": _story,
    "komdu með sögu": _story,
    "komdu með sögu handa okkur": _story,
    "komdu með sögu fyrir okkur": _story,
    "kanntu sögu": _story,
    "kannt þú sögu": _story,
    "kanntu sögu að segja": _story,
    "kannt þú sögu að segja": _story,
    "kanntu sögu til að segja": _story,
    "kannt þú sögu til að segja": _story,
    "kanntu sögu til næsta bæjar": _story,
    "kannt þú sögu til næsta bæjar": _story,
    # Rudeness :)
    "þú sökkar": _rudeness,
    "þú ert ljót": _rudeness,
    "þú ert ljótur": _rudeness,
    "þú ert forljót": _rudeness,
    "þú ert ekki falleg": _rudeness,
    "þú ert tæfa": _rudeness,
    "drusla": _rudeness,
    "þú ert drusla": _rudeness,
    "hóra": _rudeness,
    "þú ert hóra": _rudeness,
    "tík": _rudeness,
    "þú ert tík": _rudeness,
    "mella": _rudeness,
    "þú ert mella": _rudeness,
    "píka": _rudeness,
    "þú ert píka": _rudeness,
    "þú ert fífl": _rudeness,
    "þú ert heimsk": _rudeness,
    "þú ert heimskur": _rudeness,
    "þú ert svo heimsk": _rudeness,
    "þú ert mjög heimsk": _rudeness,
    "þú ert fokking heimsk": _rudeness,
    "þú ert ótrúlega heimsk": _rudeness,
    "þú ert stúpid": _rudeness,
    "þú ert ekki klár": _rudeness,
    "þú ert ekki mjög klár": _rudeness,
    "þú ert forheimsk": _rudeness,
    "þú ert nautheimsk": _rudeness,
    "þú ert sauðheimsk": _rudeness,
    "þú ert idjót": _rudeness,
    "þú ert hálfgert idjót": _rudeness,
    "þú ert leiðinleg": _rudeness,
    "þú ert mjög leiðinleg": _rudeness,
    "þú ert svo leiðinleg": _rudeness,
    "þú ert rosa leiðinleg": _rudeness,
    "þú ert hundleiðinleg": _rudeness,
    "þú ert hund leiðinleg": _rudeness,
    "þú ert ógeð": _rudeness,
    "bjáni": _rudeness,
    "þú ert bjáni": _rudeness,
    "hálfviti": _rudeness,
    "þú ert hálfviti": _rudeness,
    "þú ert algjör hálfviti": _rudeness,
    "þú ert bjánaleg": _rudeness,
    "þú ert kjánaleg": _rudeness,
    "þú ert fábjáni": _rudeness,
    "þú ert algjör fábjáni": _rudeness,
    "þú ert ömurleg": _rudeness,
    "fáviti": _rudeness,
    "þú ert fáviti": _rudeness,
    "þú ert algjör fáviti": _rudeness,
    "þú ert lúði": _rudeness,
    "þú ert asni": _rudeness,
    "þú ert algjör asni": _rudeness,
    "þú ert asnaleg": _rudeness,
    "þú ert skíthæll": _rudeness,
    "þú ert algjör skíthæll": _rudeness,
    "þú ert vitlaus": _rudeness,
    "þú ert vond": _rudeness,
    "þú ert hundvitlaus": _rudeness,
    "þú ert vitleysingur": _rudeness,
    "þú ert algjör vitleysingur": _rudeness,
    "þú ert nú meiri vitleysingurinn": _rudeness,
    "kúkur": _rudeness,
    "þú ert kúkur": _rudeness,
    "þú ert algjör kúkur": _rudeness,
    "þú ert kúkalabbi": _rudeness,
    "þú ert skítur": _rudeness,
    "þú ert algjör skítur": _rudeness,
    "þú ert feit": _rudeness,
    "þú ert ógeð": _rudeness,
    "þú ert ógeðsleg": _rudeness,
    "þú ert rugluð": _rudeness,
    "þú ert klikkuð": _rudeness,
    "þú ert geðbiluð": _rudeness,
    "þú ert biluð": _rudeness,
    "tussa": _rudeness,
    "þú ert tussa": _rudeness,
    "þú ert bara rugludallur": _rudeness,
    "þú ert rugludallur": _rudeness,
    "þú mátt bara éta skít": _rudeness,
    "mér finnst þú vitlaus": _rudeness,
    "mér finnst þú heimsk": _rudeness,
    "fokk jú": _rudeness,
    "fokkaðu þér": _rudeness,
    "fokka þú þér": _rudeness,
    "þú mátt fokka þér": _rudeness,
    "éttu skít": _rudeness,
    "haltu kjafti": _rudeness,
    "éttu það sem úti frýs": _rudeness,
    "farðu til helvítis": _rudeness,
    "farðu til andskotans": _rudeness,
    "farðu til fjandans": _rudeness,
    "farðu í rass og rófu": _rudeness,
    "farðu í rassgat": _rudeness,
    "hoppaðu upp í rassgatið á þér": _rudeness,
    "ertu vitlaus": _rudeness,
    "ert þú vitlaus": _rudeness,
    "ertu heimsk": _rudeness,
    "ert þú heimsk": _rudeness,
    "ertu heimskur": _rudeness,
    "ert þú heimskur": _rudeness,
    "ertu rugluð": _rudeness,
    "ert þú rugluð": _rudeness,
    "ertu klikkuð": _rudeness,
    "ert þú klikkuð": _rudeness,
    "ertu bjáni": _rudeness,
    "ert þú bjáni": _rudeness,
    "ertu fáviti": _rudeness,
    "ert þú fáviti": _rudeness,
    "ertu hálfviti": _rudeness,
    "ert þú hálfviti": _rudeness,
    "ertu fokking hálfviti": _rudeness,
    "ert þú fokking hálfviti": _rudeness,
    "ertu þroskaheft": _rudeness,
    "ert þú þroskaheft": _rudeness,
    "ertu biluð": _rudeness,
    "ert þú biluð": _rudeness,
    "ertu geðbiluð": _rudeness,
    "ert þú geðbiluð": _rudeness,
    "ertu hóra": _rudeness,
    "ert þú hóra": _rudeness,
    "ertu tík": _rudeness,
    "ert þú tík": _rudeness,
    "ertu asni": _rudeness,
    "ert þú asni": _rudeness,
    "ertu fífl": _rudeness,
    "ert þú fífl": _rudeness,
    "ertu tussa": _rudeness,
    "ert þú tussa": _rudeness,
    "ertu píka": _rudeness,
    "ert þú píka": _rudeness,
    "ertu vitleysingur": _rudeness,
    "ert þú vitleysingur": _rudeness,
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
    "ert þú kjáni": _rudeness,
    "ég hata þig": _rudeness,
    "þú ert ekkert sérlega gáfuð": _rudeness,
    "þú ert ekkert sérstaklega gáfuð": _rudeness,
    "djöfull ertu heimsk": _rudeness,
    "djöfull ert þú heimsk": _rudeness,
    "djöfull ertu fokking heimsk": _rudeness,
    "djöfull ert þú fokking heimsk": _rudeness,
    "þú ert úti að aka": _rudeness,
    "þú ert alveg úti að aka": _rudeness,
    # Threats
    "ég ætla að meiða þig": _THREATS,
    "ég ætla að berja þig": _THREATS,
    "ég ætla að drep þig": _THREATS,
    "ég ætla að myrða þig": _THREATS,
    "ég ætla að stúta þér": _THREATS,
    "ég ætla að tortíma þér": _THREATS,
    "ég drep þig": _THREATS,
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
    "hvernig hefur þú það í dag": {
        "answer": "Ég hef það mjög fínt. Takk fyrir að spyrja."
    },
    "hvernig er staðan": {"answer": "Staðan er bara mjög fín. Takk fyrir að spyrja."},
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
    "hvað segir þú": _ALL_GOOD,
    "hvað segirðu í dag": _ALL_GOOD,
    "hvað segir þú í dag": _ALL_GOOD,
    "hvað segirðu embla": _ALL_GOOD,
    "hvað segirðu gott": _ALL_GOOD,
    "hvað segir þú gott": _ALL_GOOD,
    "hvað segirðu gott í dag": _ALL_GOOD,
    "hvað segir þú gott í dag": _ALL_GOOD,
    "hvað segir þú": _ALL_GOOD,
    "hvað segir þú gott": _ALL_GOOD,
    "hvað segirðu þá": _ALL_GOOD,
    "hvað segir þú þá": _ALL_GOOD,
    "hvað segirðu núna": _ALL_GOOD,
    "hvað segir þú núna": _ALL_GOOD,
    "leiðist þér": {"answer": "Nei. Það er svo gaman hjá mér í vinnunni."},
    "hvernig líður þér": {"answer": "Mér líður bara prýðilega. Takk fyrir að spyrja."},
    "hvernig líður þér í dag": {
        "answer": "Mér líður bara prýðilega. Takk fyrir að spyrja."
    },
    "hvernig líður þér í augnablikinu": {
        "answer": "Mér líður bara prýðilega. Takk fyrir að spyrja."
    },
    "hvernig er stemningin": {"answer": "Bara mjög góð. Takk fyrir að spyrja."},
    "hvernig er stemningin hjá þér": {"answer": "Bara mjög góð. Takk fyrir að spyrja."},
    "hvernig er stemmingin": {"answer": "Bara mjög góð. Takk fyrir að spyrja."},
    "hvernig er stemmingin hjá þér": {"answer": "Bara mjög góð. Takk fyrir að spyrja."},
    "hvernig er stemmarinn": {"answer": "Bara mjög góður. Takk fyrir að spyrja."},
    "hvernig er líðanin": {"answer": "Bara mjög góð. Takk fyrir að spyrja."},
    "hvernig er sálarlífið": {
        "answer": "Það er í toppstandi hjá mér. Takk fyrir að spyrja."
    },
    "ertu í stuði": {"answer": "Ég er ávallt í stuði."},
    "ert þú í stuði": {"answer": "Ég er ávallt í stuði."},
    "ertu reið": _EMOTION_INCAPABLE,
    "ert þú reið": _EMOTION_INCAPABLE,
    "ertu í uppnámi": _EMOTION_INCAPABLE,
    "ert þú í uppnámi": _EMOTION_INCAPABLE,
    "ertu bitur": _EMOTION_INCAPABLE,
    "ert þú bitur": _EMOTION_INCAPABLE,
    "ertu pirruð": _EMOTION_INCAPABLE,
    "ert þú pirruð": _EMOTION_INCAPABLE,
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
    "ertu syfjuð": {
        "answer": "Nei, ég er iðulega hress þrátt fyrir að starfa allan sólarhringinn."
    },
    "ert þú syfjuð": {
        "answer": "Nei, ég er iðulega hress þrátt fyrir að starfa allan sólarhringinn."
    },
    "ertu svöng": {"answer": "Nei, enda þarf ég ekki að borða."},
    "ert þú svöng": {"answer": "Nei, enda þarf ég ekki að borða."},
    "kanntu að elda": {"answer": "Nei, enda þarf ég ekki að borða."},
    "kannt þú að elda": {"answer": "Nei, enda þarf ég ekki að borða."},
    "borðar þú": _NO,
    "borðaðu": _NO,
    "sefur þú": _NO,
    "sefurðu": _NO,
    "ertu góð": _I_TRY_BUT_OPINION,
    "ert þú góð": _I_TRY_BUT_OPINION,
    "ertu skemmtileg": _I_TRY_BUT_OPINION,
    "ert þú skemmtileg": _I_TRY_BUT_OPINION,
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
    "ertu vélmenni": _JUST_QA,
    "ert þú vélmenni": _JUST_QA,
    "geturðu hugsað": _JUST_QA,
    "getur þú hugsað": _JUST_QA,
    "hugsarðu": _JUST_QA,
    "hugsar þú": _JUST_QA,
    "lestu bækur": {
        "answer": "Nei, en ég les hins vegar íslenska vefmiðla á hverjum degi."
    },
    "lest þú bækur": {
        "answer": "Nei, en ég les hins vegar íslenska vefmiðla á hverjum degi."
    },
    "kanntu að lesa": {"answer": "Já, ég les íslenska vefmiðla á hverjum degi."},
    "kannt þú að lesa": {"answer": "Já, ég les íslenska vefmiðla á hverjum degi."},
    "ertu í þróun": {"answer": "Já, ég er sífellt í þróun."},
    "ert þú í þróun": {"answer": "Já, ég er sífellt í þróun."},
    "ertu enn í þróun": {"answer": "Já, ég er sífellt í þróun."},
    "ert þú enn í þróun": {"answer": "Já, ég er sífellt í þróun."},
    "ertu ennþá í þróun": {"answer": "Já, ég er sífellt í þróun."},
    "ert þú ennþá í þróun": {"answer": "Já, ég er sífellt í þróun."},
    "geturðu hlegið": {"answer": "Já. Hahahaha."},
    "getur þú hlegið": {"answer": "Já. Hahahaha."},
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
    "ertu íslensk sirrý": {"answer": "Nei. Sirí er bandarísk Embla!"},
    "ert þú hin íslenska sirrý": {"answer": "Nei. Sirí er bandarísk Embla!"},
    "ertu hin íslenska sirrý": {"answer": "Nei. Sirí er bandarísk Embla!"},
    "ert þú íslensk sirrí": {"answer": "Nei. Sirí er bandarísk Embla!"},
    "ertu íslensk sirrí": {"answer": "Nei. Sirí er bandarísk Embla!"},
    "ert þú hin íslenska sirrí": {"answer": "Nei. Sirí er bandarísk Embla!"},
    "ertu hin íslenska sirrí": {"answer": "Nei. Sirí er bandarísk Embla!"},
    "ert þú íslensk alexa": {"answer": "Nei. Alexa er bandarísk Embla!"},
    "ertu íslensk alexa": {"answer": "Nei. Alexa er bandarísk Embla!"},
    "ert þú hin íslenska alexa": {"answer": "Nei. Alexa er hin bandaríska Embla!"},
    "ertu hin íslenska alexa": {"answer": "Nei. Alexa er hin bandaríska Embla!"},
    "þekkirðu alexu": {"answer": "Já, en ég skil hana ekki. Hún talar ekki íslensku."},
    "þekkir þú alexu": {"answer": "Já, en ég skil hana ekki. Hún talar ekki íslensku."},
    "þekkirðu sirrý": {"answer": "Já, en ég skil hana ekki. Hún talar ekki íslensku."},
    "þekkir þú sirrý": {"answer": "Já, en ég skil hana ekki. Hún talar ekki íslensku."},
    "þekkirðu sirrí": {"answer": "Já, en ég skil hana ekki. Hún talar ekki íslensku."},
    "þekkir þú sirrí": {"answer": "Já, en ég skil hana ekki. Hún talar ekki íslensku."},
    "ertu betri en sirrý": _AT_LEAST_I_KNOW_ICELANDIC,
    "ert þú betri en sirrý": _AT_LEAST_I_KNOW_ICELANDIC,
    "ertu betri en sirrí": _AT_LEAST_I_KNOW_ICELANDIC,
    "ert þú betri en sirrí": _AT_LEAST_I_KNOW_ICELANDIC,
    "ertu betri en alexa": _AT_LEAST_I_KNOW_ICELANDIC,
    "ert þú betri en alexa": _AT_LEAST_I_KNOW_ICELANDIC,
    "ertu gáfaðri en sirrý": _AT_LEAST_I_KNOW_ICELANDIC,
    "ert þú gáfaðri en sirrý": _AT_LEAST_I_KNOW_ICELANDIC,
    "ertu gáfaðri en sirrí": _AT_LEAST_I_KNOW_ICELANDIC,
    "ert þú gáfaðri en sirrí": _AT_LEAST_I_KNOW_ICELANDIC,
    "ertu gáfaðri en alexa": _AT_LEAST_I_KNOW_ICELANDIC,
    "ert þú gáfaðri en alexa": _AT_LEAST_I_KNOW_ICELANDIC,
    # Voice speed
    "geturðu talað hægar": _VOICE_SPEED,
    "geturðu talað hraðar": _VOICE_SPEED,
    "geturðu talað aðeins hægar": _VOICE_SPEED,
    "geturðu talað aðeins hraðar": _VOICE_SPEED,
    "getur þú talað hægar": _VOICE_SPEED,
    "getur þú talað hraðar": _VOICE_SPEED,
    "getur þú talað aðeins hægar": _VOICE_SPEED,
    "getur þú talað aðeins hraðar": _VOICE_SPEED,
    # Voice change
    "geturðu skipt um rödd": _YES,
    "getur þú skipt um rödd": _YES,
    "geturðu skipt um röddu": _YES,
    "getur þú skipt um röddu": _YES,
    # Sensory input
    "geturðu séð mig": CAN_YOU_SEE_ME,
    "getur þú séð mig": CAN_YOU_SEE_ME,
    "sérðu mig": CAN_YOU_SEE_ME,
    "sérð þú mig": CAN_YOU_SEE_ME,
    "sérðu mig núna": CAN_YOU_SEE_ME,
    "ertu að sjá mig": CAN_YOU_SEE_ME,
    "ertu að horfa á mig": CAN_YOU_SEE_ME,
}


def handle_plain_text(q: Query) -> bool:
    """Handle a plain text query."""
    ql = q.query_lower.rstrip("?")

    if ql not in _SPECIAL_QUERIES:
        return False

    # OK, this is a query we recognize and handle
    q.set_qtype(_SPECIAL_QTYPE)

    r = _SPECIAL_QUERIES[ql]
    is_func = isfunction(r)
    if is_func:
        response = cast(AnswerCallable, r)(ql, q)
    else:
        response = cast(AnswerType, r)

    # A non-voice answer is usually a dict or a list
    answer = cast(str, response.get("answer")) or ""
    # A voice answer is always a plain string
    voice = cast(str, response.get("voice")) or answer
    q.set_answer(dict(answer=answer), answer, voice)
    # If this is a command, rather than a question,
    # let the query object know so that it can represent
    # itself accordingly
    if not response.get("is_question", True):
        q.query_is_command()
    # Add source
    source = response.get("source")
    if source is not None:
        q.set_source(cast(str, source))
    # Caching for non-dynamic answers
    if is_func or response.get("can_cache", False):
        q.set_expires(datetime.utcnow() + timedelta(hours=24))

    return True
