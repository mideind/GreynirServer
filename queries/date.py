"""

    Greynir: Natural language processing for Icelandic

    Date query response module

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


    This particular module handles queries related to dates.

"""

# TODO: Special days should be mentioned by name, not date, in voice answers
# TODO: Fix pronunciation of ordinal day of month (i.e. "29di" vs "29da")
# TODO: "How many weeks between April 3 and June 16?"
# TODO: Restore timezone-awareness
# TODO: "Hvað er mikið eftir af vinnuvikunni", "hvað er langt í helgina"
# TODO: "Hvaða vikudagur er DAGSETNING næstkomandi?"
# TODO: "Hvað gerðist á þessum degi?"
# TODO: "Hvað eru margir dagar eftir af árinu?"
# TODO: "Hvaða vikudagur var 11. september 2001?" "Hvaða (viku)dagur er á morgun?" "Hvaða dagur var í gær?"
# TODO: "Hvenær eru vetrarsólstöður" + more astronomical dates
# TODO: "Hvað er langt í helgina?" "Hvenær er næsti (opinberi) frídagur?"
# TODO: "Hvað eru margir dagar að fram að jólum?"
# TODO: "Hvað eru margir dagar eftir af árinu? mánuðinum? vikunni?"
# TODO: "Hvenær er næst hlaupár?" "Er hlaupár?"
# TODO: "Hvaða árstíð er"
# TODO: "Á hvaða vikudegi er jóladagur?"
# TODO: "Hvenær er fyrsti í aðventu"
# TODO: "Hvað eru margir dagar í árinu"
# TODO: "Hvaða öld er núna"
# TODO: "Hvað eru margir mánuðir í sumardaginn fyrsta" "hvað eru margar vikur í skírdag"
# TODO: "Hvað eru margir dagar eftir af árinu?" "Hvað er mikið eftir af árinu 2020?"
# TODO: "hvaða dagur er á morgun"
# TODO: "Þorláksmessa" not working
# TODO: "Hvenær er næst fullt tungl"
# TODO: Specify weekday in "hvenær er" queries (e.g. "Sjómannadagurinn er *sunnudaginn* 7. júní")
# TODO: "Hvað eru margar [unit of time measurement] í [dagsetningu]"
# TODO: "Hvenær byrjar þorrinn"

import json
import re
import logging
import random
from datetime import datetime, date, timedelta
from pytz import timezone

from queries import timezone4loc, gen_answer, is_plural
from settings import changedlocale


_DATE_QTYPE = "Date"


# Lemmas of keywords that could indicate that the user is trying to use this module
TOPIC_LEMMAS = [
    "dagur",
    "dagsetning",
    "mánaðardagur",
    "vikudagur",
    "vika",
    "mánuður",
    "hvítasunnudagur",
    "uppstigningardagur",
    "öskudagur",
    "bolludagur",
    "hrekkjavaka",
    "fullveldisdagur",
    "sumardagur",
    "þorláksmessa",
    "aðfangadagur",
    "jól",
    "jóladagur",
    "gamlárskvöld",
    "nýársdagur",
    "baráttudagur",
    "páskar",
    "páskadagur",
    "skírdagur",
    "föstudagur",
    "þjóðhátíðardagur",
    "þjóðhátíð",
    "verslunarmannahelgi",
    "frídagur",
    "menningarnótt",
    "áramót",
    "ár",
]


def help_text(lemma):
    """ Help text to return when query.py is unable to parse a query but
        one of the above lemmas is found in it """
    return "Ég get svarað ef þú spyrð til dæmis: {0}?".format(
        random.choice(
            (
                "Hvaða dagur er í dag",
                "Hvað er langt til jóla",
                "Hvenær eru páskarnir",
                "Á hvaða degi er frídagur verslunarmanna",
                "Hvenær er skírdagur",
            )
        )
    )


# Indicate that this module wants to handle parse trees for queries,
# as opposed to simple literal text strings
HANDLE_TREE = True

# The context-free grammar for the queries recognized by this plug-in module
GRAMMAR = """

Query →
    QDate

QDate →
    QDateQuery '?'?

QDateQuery →
    QDateCurrent 
    | QDateHowLongUntil 
    # | QDateHowLongSince  # Disabled for now.
    | QDateWhenIs
    | QDateWhichYear

QDateCurrent →
    "hvað" "er" "dagsetningin" QDateNow?
    | "hver" "er" "dagsetningin" QDateNow?
    | "hvaða" "dagsetning" "er" QDateNow?
    | "hvaða" "dagur" "er" QDateNow?
    | "hvaða" "mánaðardagur" "er" QDateNow?
    | "hvaða" "vikudagur" "er" QDateNow?
    | "hvaða" "mánuður" "er" QDateNow?
    | "hver" "er" "dagurinn" QDateNow?
    | "hver" "er" "mánaðardagurinn" QDateNow?
    | "hver" "er" "vikudagurinn" QDateNow?

QDateNow →
    "í" "dag" | "nákvæmlega"? "núna" | "í" "augnablikinu" | "eins" "og" "stendur"

QDateHowLongUntil →
    "hvað" "er" "langt" "í" QDateItem_þf
    | "hvað" "er" "langt" "fram" "að" QDateItem_þgf
    | "hvað" "er" "langt" "til" QDateItem_ef
    | "hversu" "langt" "er" "í" QDateItem_þf
    | "hversu" "langt" "er" "til" QDateItem_ef
    | "hvað" "eru" "margir" "dagar" "í" QDateItem_þf
    | "hvað" "eru" "margir" "dagar" "til" QDateItem_ef
    # | "hvað" "eru" "margar" "vikur" "í" QDateItem_þf
    # | "hvað" "eru" "margir" "mánuðir" "í" QDateItem_þf

QDateHowLongSince →
    # "hvað" "er" "langt" "síðan" QDateItem
    "hvað" "er" "langt" "um"? "liðið" "frá" QDateItem_þgf
    | "hvað" "er" "langur" "tími" "liðinn" "frá" QDateItem_þgf
    | "hvað" "eru" "margir" "dagar" "liðnir" "frá" QDateItem_þgf
    | "hvað" "eru" "margir" "mánuðir" "liðnir" "frá" QDateItem_þgf
    | "hvað" "eru" "margar" "vikur" "liðnar" "frá" QDateItem_þgf

QDateIsAre → "er" | "eru"

QDateCome → "koma" | "kemur"

QDateWhenIs →
    "hvenær" QDateIsAre QDateSpecialDay_nf QDateThisYear?
    | "hvenær" QDateCome QDateSpecialDay_nf QDateThisYear?
    | "hvaða" "dagur" "er" QDateSpecialDay_nf QDateThisYear?
    | "á" "hvaða" "degi" QDateIsAre QDateSpecialDay_nf QDateThisYear?

QDateThisYear →
    "núna"? "í" "ár" | "þetta" "ár" | "á" "þessu" "ári" | "þetta" "árið"

QDateWhichYear →
    "hvaða" "ár" "er" QDateNow?
    | "hvaða" "ár" "er" "í" "gangi" QDateNow?
    | "hvaða" "ár" "er" "að" "líða" QDateNow?

QDateItem/fall →
    QDateAbsOrRel | QDateSpecialDay/fall

QDateAbsOrRel →
    FöstDagsetning | AfstæðDagsetning

# TODO: Order this by time of year
QDateSpecialDay/fall →
    QDateHalloween/fall
    | QDateWhitsun/fall
    | QDateAscensionDay/fall
    | QDateAshDay/fall
    | QDateBunDay/fall
    | QDateSovereigntyDay/fall
    | QDateFirstDayOfSummer/fall
    | QDateThorlaksMass/fall
    | QDateChristmasEve/fall
    | QDateChristmasDay/fall
    | QDateNewYearsEve/fall
    | QDateNewYearsDay/fall
    | QDateNewYear/fall
    | QDateWorkersDay/fall
    | QDateEaster/fall
    | QDateEasterSunday/fall
    | QDateMaundyThursday/fall
    | QDateGoodFriday/fall
    | QDateNationalDay/fall
    | QDateBankHoliday/fall
    | QDateCultureNight/fall
    | QDateValentinesDay/fall
    | QDateMansDay/fall
    | QDateWomansDay/fall
    | QDateMardiGrasDay/fall
    | QDatePalmSunday/fall
    | QDateMothersDay/fall
    | QDateSeamensDay/fall
    | QDateFathersDay/fall
    | QDateIcelandicTongueDay/fall
    | QDateSecondChristmasDay/fall
    # | QDateFirstDayOfWinter/fall
    # | QDateSummerSolstice/fall
    # | QDateWinterSolstice/fall

QDateWhitsun/fall →
    'hvítasunnudagur:kk'_et/fall 
    | 'hvítasunna:kvk'_et/fall 
    | 'hvítasunnuhelgi:kvk'_et/fall

QDateAscensionDay/fall →
    'uppstigningardagur:kk'_et/fall

QDateAshDay/fall →
    'öskudagur:kk'_et/fall

QDateBunDay/fall →
    'bolludagur:kk'_et/fall

QDateHalloween/fall →
    'hrekkjavaka:kvk'_et/fall
    | "halloween"

QDateSovereigntyDay/fall →
    'fullveldisdagur:kk'_et/fall

QDateFirstDayOfSummer/fall →
    'sumardagur:kk'_et_gr/fall 'fyrstur:lo'_et_kk/fall

QDateThorlaksMass/fall →
    'þorláksmessa:kvk'_et/fall

QDateChristmasEve/fall →
    'aðfangadagur:kk'_et/fall 'jól:hk'_ef?

QDateChristmasDay/fall →
    'jól:hk'/fall 
    | 'jóladagur:kk'_et/fall

QDateNewYearsEve/fall →
    'gamlárskvöld:hk'_et/fall 
    | 'gamlársdagur:kk'_et/fall

QDateNewYearsDay/fall →
    'nýársdagur:kk'_et/fall

QDateNewYear/fall →
    'áramót:hk'_ft/fall

QDateWorkersDay/fall →
    'baráttudagur:kk'_et/fall 'verkalýður:kk'_et_ef

QDateEaster/fall →
    'páskar:kk'/fall

QDateEasterSunday/fall →
    'páskadagur:kk'_et/fall

QDateMaundyThursday/fall →
    'skírdagur:kk'_et/fall

QDateGoodFriday/fall →
    'föstudagur:kk'_et_gr/fall 'langur:lo'_et_kk/fall

QDateNationalDay/fall →
    'þjóðhátíðardagur:kk'_et/fall
    | 'þjóðhátíðardagur:kk'_et/fall 'Íslendingur:kk'_ft_ef
    | 'þjóðhátíðardagur:kk'_et/fall 'Ísland:hk'_et_ef
    | 'þjóðhátíð:kvk'_et/fall 'Íslendingur:kk'_ft_ef
    | 'þjóðhátíð:kvk'_et/fall 'Ísland:hk'_et_ef

QDateBankHoliday/fall →
    'verslunarmannahelgi:kvk'_et/fall
    | 'frídagur:kk'_et/fall 'verslunarmaður:kk'_ft_ef

QDateCultureNight/fall →
    'menningarnótt:kvk'_et/fall

QDateValentinesDay/fall →
    'valentínusardagur:kk'_et/fall

QDateMansDay/fall →
    'bóndadagur:kk'_et/fall

QDateWomansDay/fall →
    'konudagur:kk'_et/fall

QDateMardiGrasDay/fall →
    'sprengidagur:kk'_et/fall
    | 'sprengikvöld:hk'_et/fall

QDatePalmSunday/fall →
    'pálmasunnudagur:kk'_et/fall

QDateMothersDay/fall →
    'mæðradagur:kk'_et/fall

QDateSeamensDay/fall →
    'sjómannadagur:kk'_et/fall

QDateFirstDayOfWinter/fall →
    'fyrstur:lo'_et_kk/fall 'vetrardagur:kk'_et/fall
    | 'vetrardagur:kk'_et_gr/fall 'fyrstur:lo'_et_kk/fall

QDateFathersDay/fall →
    'feðradagur:kk'_et/fall # Why doesn't this work? 
    | "feðradagur" | "feðradagurinn" # Hack

QDateIcelandicTongueDay/fall →
    'dagur:kk'_et/fall "íslenskrar" "tungu"
    | 'dagur:kk'_et/fall "íslenskrar" 'Tunga'_ef_kvk
    | 'Dagur'/fall "íslenskrar" "tungu"
    | 'Dagur'/fall "íslenskrar" 'Tunga'_ef_kvk

QDateSecondChristmasDay/fall →
    'annar:lo'_et_kk/fall "í" "jólum"

QDateSummerSolstice/fall →
    'sumarsólstöður:kvk'_ft/fall

QDateWinterSolstice/fall →
    'vetrarsólstöður:kvk'_ft/fall

$score(+55) QDate

"""


def QDateQuery(node, params, result):
    result.qtype = _DATE_QTYPE


def QDateCurrent(node, params, result):
    result["now"] = True


def QDateHowLongUntil(node, params, result):
    result["until"] = True


def QDateHowLongSince(node, params, result):
    result["since"] = True


def QDateWhenIs(node, params, result):
    result["when"] = True


def QDateWhichYear(node, params, result):
    result["year"] = True


def QDateAbsOrRel(node, params, result):
    t = result.find_descendant(t_base="dagsafs")
    if not t:
        t = result.find_descendant(t_base="dagsföst")
    if t:
        # TODO: Use TerminalNode's contained_date property instead
        d = terminal_date(t)
        if d:
            result["target"] = d
    else:
        raise Exception("No date in {0}".format(str(t)))


def QDateWhitsun(node, params, result):
    result["desc"] = "hvítasunnudagur"
    result["target"] = next_easter() + timedelta(days=49)


def QDateAscensionDay(node, params, result):
    result["desc"] = "uppstigningardagur"
    result["target"] = next_easter() + timedelta(days=39)


def QDateAshDay(node, params, result):
    result["desc"] = "öskudagur"
    result["target"] = next_easter() - timedelta(days=46)


def QDateBunDay(node, params, result):
    result["desc"] = "bolludagur"
    result["target"] = next_easter() - timedelta(days=48)  # 7 weeks before easter


def QDateHalloween(node, params, result):
    result["desc"] = "hrekkjavaka"
    result["target"] = dnext(datetime(year=datetime.today().year, month=10, day=31))


def QDateSovereigntyDay(node, params, result):
    result["desc"] = "fullveldisdagurinn"
    result["target"] = dnext(datetime(year=datetime.today().year, month=12, day=1))


def QDateFirstDayOfSummer(node, params, result):
    result["desc"] = "sumardagurinn fyrsti"
    d = dnext(datetime(year=datetime.today().year, month=4, day=18))
    result["target"] = next_weekday(d, 3)


def QDateThorlaksMass(node, params, result):
    result["desc"] = "þorláksmessa"
    d = dnext(datetime(year=datetime.today().year, month=12, day=23))


def QDateChristmasEve(node, params, result):
    result["desc"] = "aðfangadagur jóla"
    result["target"] = dnext(datetime(year=datetime.today().year, month=12, day=24))


def QDateChristmasDay(node, params, result):
    result["desc"] = "jóladagur"
    result["target"] = dnext(datetime(year=datetime.today().year, month=12, day=25))


def QDateNewYearsEve(node, params, result):
    result["desc"] = "gamlársdagur"
    result["target"] = dnext(datetime(year=datetime.today().year, month=12, day=31))


def QDateNewYearsDay(node, params, result):
    result["desc"] = "nýársdagur"
    result["target"] = dnext(datetime(year=datetime.today().year + 1, month=1, day=1))


def QDateNewYear(node, params, result):
    result["desc"] = "áramótin"
    result["is_verb"] = "eru"
    result["target"] = dnext(
        datetime(
            year=datetime.today().year + 1, month=1, day=1, hour=0, minute=0, second=0
        )
    )


def QDateWorkersDay(node, params, result):
    result["desc"] = "baráttudagur verkalýðsins"
    result["target"] = dnext(datetime(year=datetime.today().year + 1, month=5, day=1))


def QDateEaster(node, params, result):
    result["desc"] = "páskar"
    result["is_verb"] = "eru"
    result["target"] = next_easter()


def QDateEasterSunday(node, params, result):
    result["desc"] = "páskadagur"
    result["target"] = next_easter()


def QDateGoodFriday(node, params, result):
    result["desc"] = "föstudagurinn langi"
    result["target"] = next_easter() + timedelta(days=-2)


def QDateMaundyThursday(node, params, result):
    result["desc"] = "skírdagur"
    result["target"] = next_easter() + timedelta(days=-3)


def QDateNationalDay(node, params, result):
    result["desc"] = "þjóðhátíðardagurinn"
    result["target"] = dnext(datetime(year=datetime.today().year + 1, month=6, day=17))


def QDateBankHoliday(node, params, result):
    result["desc"] = "frídagur verslunarmanna"
    # First Monday of August
    result["target"] = this_or_next_weekday(
        dnext(datetime(year=datetime.today().year + 1, month=8, day=1)), 0  # Monday
    )


def QDateCultureNight(node, params, result):
    result["desc"] = "menningarnótt"
    # Culture night is on the first Saturday after Reykjavík's birthday on Aug 18th
    aug18 = dnext(datetime(year=datetime.today().year, month=8, day=18))
    result["target"] = next_weekday(aug18, 5)  # Find the next Saturday


def QDateValentinesDay(node, params, result):
    result["desc"] = "valentínusardagur"
    result["target"] = dnext(datetime(year=datetime.today().year, month=2, day=14))


def QDateMansDay(node, params, result):
    result["desc"] = "bóndadagur"
    jan19 = dnext(datetime(year=datetime.today().year, month=1, day=19))
    result["target"] = next_weekday(jan19, 4)  # First Friday after Jan 19


def QDateWomansDay(node, params, result):
    result["desc"] = "konudagur"
    feb18 = dnext(datetime(year=datetime.today().year, month=2, day=18))
    result["target"] = next_weekday(feb18, 6)  # First Sunday after Feb 18


def QDateMardiGrasDay(node, params, result):
    result["desc"] = "sprengidagur"
    result["target"] = next_easter() - timedelta(days=47)


def QDatePalmSunday(node, params, result):
    result["desc"] = "pálmasunnudagur"
    result["target"] = next_easter() - timedelta(days=7)  # Week before Easter Sunday


def QDateMothersDay(node, params, result):
    result["desc"] = "mæðradagur"
    may8 = dnext(datetime(year=datetime.today().year, month=5, day=8))
    result["target"] = next_weekday(may8, 6)  # Second Sunday in May


def QDateSeamensDay(node, params, result):
    result["desc"] = "sjómannadagur"
    june1 = dnext(datetime(year=datetime.today().year, month=6, day=1))
    result["target"] = next_weekday(june1, 6)  # First Sunday in June


def QDateFathersDay(node, params, result):
    result["desc"] = "feðradagur"
    nov8 = dnext(datetime(year=datetime.today().year, month=5, day=8))
    result["target"] = next_weekday(nov8, 6)  # Second Sunday in May


def QDateIcelandicTongueDay(node, params, result):
    result["desc"] = "dagur íslenskrar tungu"
    result["target"] = dnext(datetime(year=datetime.today().year, month=11, day=16))


def QDateSecondChristmasDay(node, params, result):
    result["desc"] = "annar í jólum"
    result["target"] = dnext(datetime(year=datetime.today().year, month=12, day=26))


def QDateFirstDayOfWinter(node, params, result):
    result["desc"] = "fyrsti vetrardagur"
    result["target"] = None  # To be completed


def QDateSummerSolstice(node, params, result):
    result["desc"] = "sumarsólstöður"
    result["is_verb"] = "eru"
    result["target"] = None  # To be completed


def QDateWinterSolstice(node, params, result):
    result["desc"] = "vetrarsólstöður"
    result["is_verb"] = "eru"
    result["target"] = None  # To be completed


# Day indices in nominative case
_DAY_INDEX_NOM = {
    1: "fyrsti",
    2: "annar",
    3: "þriðji",
    4: "fjórði",
    5: "fimmti",
    6: "sjötti",
    7: "sjöundi",
    8: "áttundi",
    9: "níundi",
    10: "tíundi",
    11: "ellefti",
    12: "tólfti",
    13: "þrettándi",
    14: "fjórtándi",
    15: "fimmtándi",
    16: "sextándi",
    17: "sautjándi",
    18: "átjándi",
    19: "nítjándi",
    20: "tuttugasti",
    21: "tuttugasti og fyrsti",
    22: "tuttugasti og annar",
    23: "tuttugasti og þriðji",
    24: "tuttugasti og fjórði",
    25: "tuttugasti og fimmti",
    26: "tuttugasti og sjötti",
    27: "tuttugasti og sjöundi",
    28: "tuttugasti og áttundi",
    29: "tuttugasti og níundi",
    30: "þrítugasti",
    31: "þrítugasti og fyrsti",
}


# Day indices in accusative case
_DAY_INDEX_ACC = {
    1: "fyrsta",
    2: "annan",
    3: "þriðja",
    4: "fjórða",
    5: "fimmta",
    6: "sjötta",
    7: "sjöunda",
    8: "áttunda",
    9: "níunda",
    10: "tíunda",
    11: "ellefta",
    12: "tólfta",
    13: "þrettánda",
    14: "fjórtánda",
    15: "fimmtánda",
    16: "sextánda",
    17: "sautjánda",
    18: "átjánda",
    19: "nítjánda",
    20: "tuttugasta",
    21: "tuttugasta og fyrsta",
    22: "tuttugasta og annan",
    23: "tuttugasta og þriðja",
    24: "tuttugasta og fjórða",
    25: "tuttugasta og fimmta",
    26: "tuttugasta og sjötta",
    27: "tuttugasta og sjöunda",
    28: "tuttugasta og áttunda",
    29: "tuttugasta og níunda",
    30: "þrítugasta",
    31: "þrítugasta og fyrsta",
}


# Day indices in dative case
_DAY_INDEX_DAT = _DAY_INDEX_ACC.copy()
_DAY_INDEX_DAT[2] = "öðrum"
_DAY_INDEX_DAT[22] = "tuttugasta og öðrum"


def next_weekday(d, weekday):
    """ Get the date of the next weekday after a given date.
        0 = Monday, 1 = Tuesday, 2 = Wednesday, etc. """
    days_ahead = weekday - d.weekday()
    if days_ahead <= 0:  # Target day already happened this week
        days_ahead += 7
    return d + timedelta(days=days_ahead)


def this_or_next_weekday(d, weekday):
    """ Get the date of the next weekday after or including a given date.
        0 = Monday, 1 = Tuesday, 2 = Wednesday, etc. """
    days_ahead = weekday - d.weekday()
    if days_ahead < 0:  # Target day already happened this week
        days_ahead += 7
    return d + timedelta(days=days_ahead)


def dnext(datetime):
    """ Return datetime with year+1 if date was earlier in current year. """
    now = datetime.utcnow()
    d = datetime
    if d < now:
        d = d.replace(year=d.year + 1)
    return d


def next_easter():
    """ Find the date of next easter in the Gregorian calendar. """
    now = datetime.utcnow()
    e = calc_easter(now.year)
    if e < now:
        e = calc_easter(now.year + 1)
    return e


def calc_easter(year):
    """ An implementation of Butcher's Algorithm for determining the date of Easter 
        for the Western church. Works for any date in the Gregorian calendar (1583 
        and onward). Returns a datetime object. 
        From http://code.activestate.com/recipes/576517-calculate-easter-western-given-a-year/ """
    a = year % 19
    b = year // 100
    c = year % 100
    d = (19 * a + b - b // 4 - ((b - (b + 8) // 25 + 1) // 3) + 15) % 30
    e = (32 + 2 * (b % 4) + 2 * (c // 4) - d - (c % 4)) % 7
    f = d + e - 7 * ((a + 11 * d + 22 * e) // 451) + 114
    month = f // 31
    day = f % 31 + 1
    return datetime(year=year, month=month, day=day)


def terminal_date(t):
    """ Extract array of date values from terminal token's auxiliary info,
        which is attached as a json-encoded array. Returns datetime object. """
    if t and t._node.aux:
        aux = json.loads(t._node.aux)
        if not isinstance(aux, list) or len(aux) < 3:
            raise Exception("Malformed token aux info")

        # Unpack date array
        (y, m, d) = aux
        if not y:
            now = datetime.utcnow()
            y = now.year
            # Bump year if month/day in the past
            if m < now.month or (m == now.month and d < now.day):
                y += 1

        return datetime(year=y, month=m, day=d)


def date_diff(d1, d2, unit="days"):
    """ Get the time difference between two dates. """
    delta = d2 - d1
    cnt = getattr(delta, unit)
    return cnt


def howlong_desc_answ(target):
    """ Generate answer to a query about length of period to a given date. """
    now = datetime.utcnow()
    days = date_diff(now, target, unit="days")

    # Diff. strings for singular vs. plural
    plural = is_plural(days)
    verb = "eru" if plural else "er"
    days_desc = "dagar" if plural else "dagur"

    # Format date
    fmt = "%-d. %B" if now.year == target.year else "%-d. %B %Y"
    tfmt = target.strftime(fmt)

    # Date asked about is current date
    if days == 0:
        return gen_answer("Það er {0} í dag.".format(tfmt))
    elif days < 0:
        # It's in the past
        days = abs(days)
        passed = "liðinn" if sing else "liðnir"
        voice = "Það {0} {1} {2} {3} frá {4}.".format(
            verb, days, days_desc, passed, tfmt
        )
        # Convert '25.' to 'tuttugasta og fimmta'
        voice = re.sub(r" \d+\. ", " " + _DAY_INDEX_DAT[target.day] + " ", voice)
        answer = "{0} {1}".format(days, days_desc)
    else:
        # It's in the future
        voice = "Það {0} {1} {2} þar til {3} gengur í garð.".format(
            verb, days, days_desc, tfmt
        )
        # Convert '25.' to 'tuttugasti og fimmti'
        voice = re.sub(r" \d+\. ", " " + _DAY_INDEX_NOM[target.day] + " ", voice)
        answer = "{0} {1}".format(days, days_desc)

    response = dict(answer=answer)

    return (response, answer, voice)


def sentence(state, result):
    """ Called when sentence processing is complete """
    q = state["query"]
    if "qtype" not in result:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
        return

    # Successfully matched a query type
    try:
        with changedlocale(category="LC_TIME"):
            # Get timezone and date
            # TODO: Restore correct timezone handling
            # tz = timezone4loc(q.location, fallback="IS")
            now = datetime.utcnow()  # datetime.now(timezone(tz))
            qkey = None

            # Asking about current date
            if "now" in result:
                date_str = now.strftime("%A %-d. %B %Y")
                answer = date_str.capitalize()
                voice = "Í dag er {0}".format(date_str)
                # Put a spelled-out ordinal number instead of the numeric one
                # to get the grammar right
                voice = re.sub(r" \d+\. ", " " + _DAY_INDEX_NOM[now.day] + " ", voice)
                response = dict(answer=answer)
                qkey = "CurrentDate"
            # Asking about period until/since a given date
            elif ("until" in result or "since" in result) and "target" in result:
                target = result.target
                # target.replace(tzinfo=timezone(tz))
                # Find the number of days until target date
                (response, answer, voice) = howlong_desc_answ(target)
                qkey = "FutureDate" if "until" in result else "SinceDate"
            # Asking about when a (special) day occurs in the year
            elif "when" in result and "target" in result:
                # TODO: Fix this so it includes weekday, e.g.
                # "Sunnudaginn 1. október"
                # Use plural 'eru' for 'páskar'
                is_verb = "er" if "is_verb" not in result else result.is_verb
                date_str = (
                    result.desc
                    + " "
                    + is_verb
                    + " "
                    + result.target.strftime("%-d. %B")
                )
                answer = voice = date_str[0].upper() + date_str[1:].lower()
                # Put a spelled-out ordinal number instead of the numeric one,
                # in accusative case
                voice = re.sub(
                    r"\d+\. ", _DAY_INDEX_ACC[result.target.day] + " ", voice
                )
                response = dict(answer=answer)
            # Asking which year it is
            elif "year" in result:
                y = now.year
                answer = "{0}.".format(y)
                response = dict(answer=answer)
                voice = "Það er árið {0}.".format(y)
            else:
                # Shouldn't be here
                raise Exception("Unable to handle date query")

            q.set_key(qkey)
            q.set_answer(response, answer, voice)
            # Lowercase the query string to avoid 'Dagur' being
            # displayed with a capital D
            q.lowercase_beautified_query()
            q.set_qtype(_DATE_QTYPE)

    except Exception as e:
        logging.warning("Exception while processing date query: {0}".format(e))
        q.set_error("E_EXCEPTION: {0}".format(e))
