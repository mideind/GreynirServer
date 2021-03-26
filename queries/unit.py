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


    This module handles queries related to measurement units, mostly
    conversions between units. An explanation is given if the user
    asks for a conversion between incompatible units. Results are
    rounded to three significant digits.

"""

# TODO: Hvað eru fjórir hnútar margir metrar á sekúndu?
# TODO: Hvað eru 20 metrar á sekúndu mörg vindstig?
# TODO: Hvað eru 40 stig á selsíus mörg stig á fahrenheit
# TODO: "hvað eru 3 metrar í tommum"

from typing import Tuple

import random
from math import floor, log10

import query
from query import Query
from queries import iceformat_float, parse_num


# Lemmas of keywords that could indicate that the user is trying to use this module
TOPIC_LEMMAS = [
    "kíló",
    "kílógramm",
    "gramm",
    "únsa",
    "tonn",
    "lítri",
    "rúmmetri",
    "desilítri",
    "millilítri",
    "metri",
    "míla",
    "kílómetri",
    "sentimetri",
    "sentímetri",
    "millimetri",
    "þumlungur",
    "tomma",
    "fet",
    "ferfet",
    "fermetri",
    "fersentimetri",
    "fersentímetri",
    "hektari",
    "bolli",
    "matskeið",
    "teskeið",
    "vökvaúnsa",
    "pint",
]


def help_text(lemma: str) -> str:
    """Help text to return when query.py is unable to parse a query but
    one of the above lemmas is found in it"""
    return "Ég get svarað ef þú spyrð til dæmis: {0}?".format(
        random.choice(
            (
                "Hvað eru fjögur fet margir metrar",
                "Hvað eru þrjú hundruð grömm margar únsur",
                "Hversu margir bollar eru í einum lítra",
                "Hvað er hálf míla margir metrar",
                "Hversu margar teskeiðar eru í einum desilítra",
                "Hvað samsvara 15 pund mörgum kílóum",
            )
        )
    )


_UNIT_QTYPE = "Unit"


_UNITS = {
    # Volume (standard unit is m³)
    "lítri": ("m³", 1.0e-3),
    "millilítri": ("m³", 1.0e-6),
    "desílítri": ("m³", 1.0e-4),
    "sentílítri": ("m³", 1.0e-5),
    "hektólítri": ("m³", 1.0e-1),
    "rúmmetri": ("m³", 1.0),
    "rúmsentímetri": ("m³", 1.0e-6),
    "bolli": ("m³", 2.5e-4),  # More exactly 1 US cup is 2.36588e-4 m³
    "matskeið": ("m³", 15.0e-6),  # Rounded to 15 ml
    "teskeið": ("m³", 5.0e-6),  # Rounded to 5 ml
    "tunna": ("m³", 160.0e-3),  # Rounded to 160 liters
    "olíutunna": ("m³", 160.0e-3),  # Rounded to 160 liters
    "gallon": ("m³", 3.8e-3),  # Rounded
    "gallón": ("m³", 3.8e-3),  # Rounded
    "vökvaúnsa": ("m³", 0.0295735e-3),  # US fl. oz.
    "vökva únsa": ("m³", 0.0295735e-3),  # US fl. oz.
    "vökva únsur": ("m³", 0.0295735e-3),  # US fl. oz.
    "pint": ("m³", 0.568e-3),  # British pint
    # Weight (standard unit is kg)
    "kíló": ("kg", 1.0),
    "kílógramm": ("kg", 1.0),
    "gramm": ("kg", 1.0e-3),
    "hektógramm": ("kg", 1.0e-1),
    "tonn": ("kg", 1.0e3),
    "smálest": ("kg", 1.0e3),
    "lest": ("kg", 1.0e3),
    "únsa": ("kg", 28.35e-3),
    "pund": ("kg", 454.0e-3),
    "karat": ("kg", 0.2e-3),
    "steinn": ("kg", 6.35),
    "mörk": ("kg", 0.25),
    # Distance (standard unit is m)
    "metri": ("m", 1.0),
    "kílómetri": ("m", 1.0e3),
    "desímetri": ("m", 1.0e-1),
    "sentímetri": ("m", 1.0e-2),
    "millimetri": ("m", 1.0e-3),
    "ljósár": ("m", 9460730472580.8e3),
    "fet": ("m", 0.305),
    "jard": ("m", 0.915),
    "yard": ("m", 0.915),
    "míla": ("m", 1609.0),
    "sjómíla": ("m", 1852.0),
    "tomma": ("m", 2.54e-2),
    "þumlungur": ("m", 2.54e-2),
    "faðmur": ("m", 1.829),
    # Area (standard unit is m²)
    "fermetri": ("m²", 1.0),
    "fersentímetri": ("m²", 1.0e-4),
    "ferkílómetri": ("m²", 1.0e6),
    "ferfet": ("m²", 0.305 ** 2),
    "fermíla": ("m²", 1609.0 ** 2),
    "hektari": ("m²", 100.0 ** 2),
    "fertomma": ("m²", 2.54e-2 ** 2),
    "ferþumlungur": ("m²", 2.54e-2 ** 2),
    "ekra": ("m²", 4047.0),
    # Time (standard unit is second)
    "árþúsund": ("s", 3600.0 * 24 * 365.25 * 1000),
    "öld": ("s", 3600.0 * 24 * 365.25 * 100),
    "áratugur": ("s", 3600.0 * 24 * 365.25 * 10),
    "ár": ("s", 3600.0 * 24 * 365.25),
    "mánuður": ("s", 3600.0 * 24 * (365.25 / 12.0)),  # Average length of month
    "vika": ("s", 3600.0 * 24 * 7),
    "dagur": ("s", 3600.0 * 24),
    "sólarhringur": ("s", 3600.0 * 24),
    "klukkustund": ("s", 3600.0),
    "klukkutími": ("s", 3600.0),
    "hálftími": ("s", 1800.0),
    "kortér": ("s", 900.0),
    "stundarfjórðungur": ("s", 900.0),
    "mínúta": ("s", 60.0),
    "sekúnda": ("s", 1.0),
    "sekúndubrot": ("s", 1.0 / 100),
    "millisekúnda": ("s", 1.0 / 1000),
    "míkrósekúnda": ("s", 1.0 / 1.0e6),
    "nanósekúnda": ("s", 1.0 / 1.0e9),
}

# Convert irregular unit forms to canonical ones
# These forms can inter alia occur when the unit is matched by
# a person name token, which does not match a regular lemma terminal
_CONVERT_UNITS = {
    "bolla": "bolli",
    "bollar": "bolli",
    "bollum": "bolli",
    "dag": "dagur",
    "daga": "dagur",
    "degi": "dagur",
    "dags": "dagur",
    "dagar": "dagur",
    "dögum": "dagur",
    "merkur": "mörk",
    "marka": "mörk",
    "markar": "mörk",
    "mílu": "míla",
    "aldar": "öld",
    "aldir": "öld",
    "steinar": "steinn",
    "steina": "steinn",
    "steini": "steinn",
    "steins": "steinn",
    "steinum": "steinn",
    "sentimetri": "sentímetri",
    "desimetri": "desímetri",
    "fersentimetri": "fersentímetri",
    "desilítri": "desílítri",
    "sentilítri": "sentílítri",
    "rúmsentimetri": "rúmsentímetri",
    "korter": "kortér",
}

# Indicate that this module wants to handle parse trees for queries,
# as opposed to simple literal text strings
HANDLE_TREE = True

# The grammar nonterminals this module wants to handle
QUERY_NONTERMINALS = {"QUnitQuery"}

# The context-free grammar for the queries recognized by this plug-in module
GRAMMAR = """

# A plug-in query grammar always starts with the following,
# adding one or more query productions to the Query nonterminal

Query →
    QUnitQuery

QUnitQuery →
    QUnitConversion '?'?

$score(+35) QUnitQuery

QUnitPrefix_nf →
    "hvað" "er" | "hvað" "eru"

QUnitPrefix_þgf →
    "hvað" "jafngildir" | "hvað" "jafngilda" | "hvað" "samsvarar" | "hvað" "samsvara"

QUnitMany/fall/kyn → 'margur:lo'_sb_ft/fall/kyn

QUnitConversion →
    # Hvað eru X kíló mörg pund [?]
    # Hvað eru Y pund mörg kíló [?]
    QUnitPrefix_nf QUnitFrom_nf QUnitMany_nf/kyn QUnitTo_nf/kyn
    # Hvað eru mörg pund í X kílóum [?]
    | QUnitPrefix_nf QUnitMany_nf/kyn QUnitTo_nf/kyn "í" QUnitFrom_þgf
    # Hversu mörg pund eru í X kílóum [?]
    | "hversu" QUnitMany_nf/kyn QUnitTo_nf/kyn "eru" "í" QUnitFrom_þgf
    # Hvað jafngilda X kíló mörgum pundum [?]
    | QUnitPrefix_þgf QUnitFrom_nf QUnitMany_þgf/kyn QUnitTo_þgf/kyn

QUnitFrom/fall →
    QUnitFrom/fall/kyn
    | QUnitFromPounds/fall

QUnitFrom/fall/kyn →
    QUnitNumber/kyn/fall? QUnit/kyn/fall

# Special case hack: '150 pund' is tokenized as an amount
# (Note that this will also allow '150 sterlingspund' but we let that slide ;-) )
QUnitFromPounds/fall →
    amount_gbp/fall

QUnitTo/fall/kyn →
    QUnit/kyn/fall

$tag(keep) QUnitTo/fall/kyn # Keep this from being optimized away

QUnitNumber/kyn/fall →
    # to is a declinable number word ('tveir/tvo/tveim/tveggja')
    # töl is an undeclinable number word ('sautján')
    # tala is a number ('17')
    to/kyn/fall | töl | tala
    | 'hálfur:lo'_sb/kyn/fall
    | 'Eina:kvk'

# Volume

QUnit_kk/fall →
    'lítri:kk'/fall
    | 'millilítri:kk'/fall
    | 'desilítri:kk'/fall
    | 'desílítri:kk'/fall
    | 'sentilítri:kk'/fall
    | 'sentílítri:kk'/fall
    | 'hektólítri:kk'/fall
    | 'rúmmetri:kk'/fall
    | 'rúmsentimetri:kk'/fall
    | 'rúmsentímetri:kk'/fall
    | 'bolli:kk'/fall
    | 'Bolli'/fall
    | 'pint:kk'/fall

QUnit_kvk/fall →
    'matskeið:kvk'/fall
    | 'teskeið:kvk'/fall
    | 'tunna:kvk'/fall
    | 'olíutunna:kvk'/fall
    | 'vökvaúnsa:kvk'/fall
    | "vökva" "únsa"
    | "vökva" "únsur"

QUnit_hk/fall →
    'gallon:hk'/fall
    | 'gallón:hk'/fall

# Weight

QUnit_kk/fall →
    'steinn:kk'/fall
    | 'Steinn'/fall
    | 'Steinar'/fall

QUnit_kvk/fall →
    'únsa:kvk'/fall
    | 'lest:kvk'/fall
    | 'smálest:kvk'/fall

QUnit_hk/fall →
    'kíló:hk'/fall
    | 'gramm:hk'/fall
    | 'kílógramm:hk'/fall
    | 'hektógramm:hk'/fall
    | 'tonn:hk'/fall
    | 'pund:hk'/fall
    | 'karat:hk'/fall
    | 'mörk:kvk'/fall
    | 'Mörk'/fall

# Distance

QUnit_kk/fall →
    'metri:kk'/fall
    | 'kílómetri:kk'/fall
    | 'sentimetri:kk'/fall
    | 'sentímetri:kk'/fall
    | 'millimetri:kk'/fall
    | 'yard:kk'/fall
    | 'jard:kk'/fall
    | 'þumlungur:kk'/fall
    | 'faðmur:kk'/fall

QUnit_kvk/fall →
    'míla:kvk'/fall
    | 'Míla'/fall
    | 'sjómíla:kvk'/fall
    | 'tomma:kvk'/fall

QUnit_hk/fall →
    'ljósár:hk'/fall
    | 'fet:hk'/fall

# Area

QUnit_kk/fall →
    'fermetri:kk'/fall
    | 'fersentímetri:kk'/fall
    | 'fersentimetri:kk'/fall
    | 'ferkílómetri:kk'/fall
    | 'hektari:kk'/fall
    | 'ferþumlungur:kk'/fall

QUnit_hk/fall →
    'ferfet:hk'/fall

QUnit_kvk/fall →
    'fermíla:kvk'/fall
    | 'fertomma:kvk'/fall
    | 'ekra:kvk'/fall

# Time

QUnit_kk/fall →
    'mánuður:kk'/fall
    | 'dagur:kk'/fall
    | 'Dagur'/fall
    | 'áratugur:kk'/fall
    | 'klukkutími:kk'/fall
    | 'hálftími:kk'/fall
    | 'stundarfjórðungur:kk'/fall

QUnit_hk/fall →
    'árþúsund:hk'/fall | "árþúsund" # Often incorrectly declined
    | 'ár:hk'/fall
    | 'sekúndubrot:hk'/fall
    | 'kortér:hk'/fall | "korter"

QUnit_kvk/fall →
    'nanósekúnda:kvk'/fall
    | 'míkrósekúnda:kvk'/fall
    | 'millisekúnda:kvk'/fall
    | 'sekúnda:kvk'/fall
    | 'mínúta:kvk'/fall
    | 'klukkustund:kvk'/fall
    | 'vika:kvk'/fall
    | 'öld:kvk'/fall

"""


def QUnitConversion(node, params, result):
    """ Unit conversion query """
    result.qtype = "Unit"
    result.qkey = result.unit_to


def QUnitNumber(node, params, result):
    result.number = parse_num(node, result._canonical)


def QUnit(node, params, result):
    # Unit in canonical (nominative, singular, indefinite) form
    unit = result._canonical.lower()
    # Convert irregular forms ('mílu', 'bollum') to canonical ones
    result.unit = _CONVERT_UNITS.get(unit, unit)
    # Unit in nominative form
    result.unit_nf = result._nominative.lower()


def QUnitTo(node, params, result):
    result.unit_to = result.unit
    result.unit_to_nf = result.unit_nf
    del result["unit"]
    del result["unit_nf"]


def QUnitFrom(node, params, result):
    if "unit" in result:
        result.unit_from = result.unit
        result.unit_from_nf = result.unit_nf
        result.desc = result._nominative
        del result["unit"]
        del result["unit_nf"]


def QUnitFromPounds(node, params, result):
    """Special hack for the case of '150 pund' which is
    tokenized as an amount token"""
    amount = node.first_child(lambda n: n.has_t_base("amount"))
    assert amount is not None
    # Extract quantity from the amount token associated with the amount terminal
    result.number, curr = amount.contained_amount
    assert curr == "GBP"
    result.unit = "pund"
    result.unit_nf = "pund"
    result._nominative = str(result.number).replace(".", ",") + " pund"


def _convert(quantity: float, unit_from: str, unit_to: str) -> Tuple:
    """Converts a quantity from unit_from to unit_to, returning a tuple of:
    valid, result, si_unit, si_quantity"""
    u_from, factor_from = _UNITS[unit_from]
    u_to, factor_to = _UNITS[unit_to]
    if u_from != u_to:
        # Converting between units of different type:
        # signal this to the caller
        return False, 0.0, "", 0.0
    if quantity == 0.0:
        return True, 0.0, u_to, 0.0
    result = quantity * factor_from / factor_to
    if result < 1.0e-3:
        # We consider anything less than one-thousandth to be zero
        # and don't bother rounding it
        return True, result, u_to, 0.0
    # Round to three significant digits
    # Note that quantity cannot be negative
    return (
        True,
        round(result, 2 - int(floor(log10(result)))),
        u_to,
        quantity * factor_from,
    )


def sentence(state, result):
    """ Called when sentence processing is complete """
    q: Query = state["query"]
    if "qtype" in result and result.qtype == "Unit":
        # Successfully matched a query type
        # If no number is mentioned in the query
        # ('Hvað eru margir metrar í kílómetra?')
        # we use 1.0
        val_from = result.get("number", 1.0)
        # Convert between units, getting also the base SI unit and quantity
        valid, val, si_unit, si_quantity = _convert(
            val_from, result.unit_from, result.unit_to
        )
        if not valid:
            answer = voice_answer = "Það er ekki hægt að umbreyta {0} í {1}.".format(
                query.to_dative(result.unit_from), query.to_accusative(result.unit_to)
            )
            response = dict(answer=answer)
        else:
            answer = iceformat_float(val)
            if (0.0 < val < 1.0e-3) or (val > 0.0 and answer == "0"):
                answer = "næstum núll " + result.unit_to_nf
                val = 0.0
            else:
                answer += " " + result.unit_to_nf
            verb = "eru"
            if int(val_from) % 10 == 1 and int(val_from) % 100 != 11:
                # 'Einn lítri er...', 'Tuttugu og einn lítri er...',
                # but on the other hand 'Ellefu lítrar eru...'
                verb = "er"
            elif "hálf" in result.desc:
                # Hack to reply 'Hálfur kílómetri er 500 metrar'
                verb = "er"
            unit_to = result.unit_to
            response = dict(answer=answer)
            voice_answer = "{0} {1} {2}.".format(result.desc, verb, answer).capitalize()
            # Store the resulting quantity in the query context
            q.set_context(
                {
                    "quantity": {
                        "unit": unit_to,
                        "value": val,
                        "si_unit": si_unit,
                        "si_value": si_quantity,
                    }
                }
            )
        q.set_key(result.unit_to)
        q.set_answer(response, answer, voice_answer)
        q.set_qtype(_UNIT_QTYPE)
        q.lowercase_beautified_query()
        return

    q.set_error("E_QUERY_NOT_UNDERSTOOD")
