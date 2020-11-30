"""

    Greynir: Natural language processing for Icelandic

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


    This module handles statements and queries related to user info, e.g.
    name, address, phone number, device type, etc.

"""

from typing import Dict

import re

from reynir import NounPhrase
from reynir.bindb import BIN_Db

from geo import icelandic_addr_info, iceprep_for_placename, iceprep_for_street
from query import Query
from . import gen_answer, numbers_to_neutral


_USERINFO_QTYPE = "UserInfo"


_WHO_IS_ME = "hver er {0}"
_YOU_ARE = "Þú, kæri notandi, heitir {0}"


def _whoisme_handler(q: Query, ql: str) -> bool:
    """ Handle queries of the form "Hver er [nafn notanda]?" """
    nd = q.client_data("name")
    if not nd:
        return False

    for t in ["full", "first"]:
        if t not in nd:
            continue
        if ql == _WHO_IS_ME.format(nd[t].lower()):
            q.set_answer(*gen_answer(_YOU_ARE.format(nd[t])))
            return True

    return False


_WHATS_MY_NAME = frozenset(
    (
        "hvað heiti ég fullu nafni",
        "hvað heiti ég",
        "veistu hvað ég heiti",
        "veistu hvað ég heiti fullu nafni",
        "veist þú hvað ég heiti",
        "veist þú hvað ég heiti fullu nafni",
        "veistu ekki hvað ég heiti",
        "veist þú ekki hvað ég heiti",
        "hver er ég",
        "veistu hver ég er",
        "veistu ekki hver ég er",
        "veist þú hver ég er",
        "veist þú ekki hver ég er",
        "hvaða nafn er ég með",
        "hvaða nafni heiti ég",
        "veistu hvaða nafni ég heiti",
        "hvað heiti ég eiginlega",
        "hvaða nafn ber ég",
        "hvað er nafnið mitt",
        "hvað er nafn mitt",
        "hvert er nafnið mitt",
        "hvert er nafn mitt",
    )
)


_DUNNO_NAME = "Ég veit ekki hvað þú heitir, en þú getur sagt mér það."


def _whatsmyname_handler(q: Query, ql: str) -> bool:
    """ Handle queries of the form "Hvað heiti ég?" """
    if ql in _WHATS_MY_NAME:
        answ: str = None
        nd = q.client_data("name")
        if nd and "full" in nd:
            answ = f"Þú heitir {nd['full']}"
        elif nd and "first" in nd:
            answ = f"Þú heitir {nd['first']}"
        else:
            answ = _DUNNO_NAME
        q.set_answer(*gen_answer(answ))
        return True


_MY_NAME_IS_REGEXES = frozenset(
    (
        r"^ég heiti (.+)$",
        r"^hæ ég heiti (.+)$",
        r"^nafn mitt er (.+)$",
        r"^nafnið mitt er (.+)$",
        r"^ég ber heitið (.+)$",
        r"^ég ber nafnið (.+)$",
    )
)

_MY_NAME_IS_RESPONSES = {
    "hk": "Gaman að kynnast þér, {0}. Ég heiti Embla.",
    "kk": "Sæll og blessaður, {0}. Ég heiti Embla.",
    "kvk": "Sæl og blessuð, {0}. Ég heiti Embla.",
}


def _mynameis_handler(q: Query, ql: str) -> bool:
    """ Handle queries of the form "Ég heiti X", store this information. """
    for rx in _MY_NAME_IS_REGEXES:
        m = re.search(rx, ql)
        if m:
            break
    if m:
        name = m.group(1).strip()
        if not name:
            return False

        # Clean up name string
        name = name.split(" og ")[0]  # "ég heiti X og blablabla"
        name = name.split(" hvað ")[0]  # "ég heiti X hvað heitir þú"

        # Handle "ég heiti ekki X"
        components = name.split()
        if components[0] == "ekki":
            q.set_answer(*gen_answer("Hvað heitirðu þá?"))
            return True

        # Get first name, look up gender for a gender-tailored response
        with BIN_Db.get_db() as bdb:
            fn = components[0].title()
            gender = bdb.lookup_name_gender(fn) or "hk"
            answ = _MY_NAME_IS_RESPONSES[gender].format(fn)

        # Save this info about user to query data table
        if q.client_id:
            qdata = dict(full=name.title(), first=fn, gender=gender)
            q.set_client_data("name", qdata)

        # Generate answer
        voice = answ.replace(",", "")
        q.set_answer(dict(answer=answ), answ, voice)
        q.query_is_command()
        return True

    return False


def _addr2str(addr: Dict[str, str], case: str = "nf") -> str:
    """ Format address canonically given dict w. address info. """
    assert case in ["nf", "þgf"]
    prep = iceprep_for_placename(addr["placename"])
    astr = "{0} {1} {2} {3}".format(
        addr["street"], addr["number"], prep, addr["placename"]
    )
    if case == "þgf":
        try:
            n = NounPhrase(astr)
            if n:
                astr = n.dative or astr
        except Exception:
            pass
    return numbers_to_neutral(astr)


_WHATS_MY_ADDR = frozenset(
    (
        "hvar á ég heima",
        "hvar á ég eiginlega heima",
        "veistu hvar ég á heima",
        "veist þú hvar ég á heima",
        "hvar bý ég",
        "hvar bý ég eiginlega",
        "veistu hvar ég bý",
        "veist þú hvar ég bý",
        "hvað er heimilisfang mitt",
        "hvað er heimilisfangið mitt",
        "hvert er heimilisfang mitt",
        "hvert er heimilisfangið mitt",
    )
)


_DUNNO_ADDRESS = "Ég veit ekki hvar þú átt heima, en þú getur sagt mér það."


def _whatsmyaddr_handler(q: Query, ql: str) -> bool:
    """ Handle queries of the form "Hvar á ég heima?" """
    if ql not in _WHATS_MY_ADDR:
        return False

    answ = None
    ad = q.client_data("address")
    if not ad:
        answ = _DUNNO_ADDRESS
    else:
        prep = iceprep_for_street(ad["street"])
        answ = "Þú átt heima {0} {1}".format(prep, _addr2str(ad, case="þgf"))
    q.set_answer(*gen_answer(answ))
    return True


_MY_ADDRESS_REGEXES = (
    r"ég á heima á (.+)$",
    r"ég á heima í (.+)$",
    r"heimilisfang mitt er á (.+)$",
    r"heimilisfang mitt er í (.+)$",
    r"heimilisfang mitt er (.+)$",
)

_ADDR_LOOKUP_FAIL = "Ég fann ekki þetta heimilisfang."


def _myaddris_handler(q: Query, ql: str) -> bool:
    """ Handle queries of the form "Ég á heima á [heimilisfang]".
        Store this info as query data. """
    for rx in _MY_ADDRESS_REGEXES:
        m = re.search(rx, ql)
        if m:
            break
    if not m:
        return False

    addr_str = m.group(1).strip()
    if not addr_str:
        return False

    # Try to parse address, e.g. "Öldugötu 4 [í Reykjavík]"
    m = re.search(r"^(\w+)\s(\d+)\s?([í|á]\s)?(\w+)?$", addr_str.strip())
    if not m:
        q.set_answer(*gen_answer(_ADDR_LOOKUP_FAIL))
        return True

    # Matches a reasonable address
    groups = m.groups()
    (street, num) = (groups[0], groups[1])
    placename = None
    if len(groups) == 3 and groups[2] not in ["í", "á"]:
        placename = groups[2]
    elif len(groups) == 4:
        placename = groups[3]

    # Look up info about address
    addrfmt = f"{street} {num}"
    addrinfo = icelandic_addr_info(addrfmt, placename=placename)

    if not addrinfo:
        q.set_answer(*gen_answer(_ADDR_LOOKUP_FAIL))
        return True

    # Save this info about user to query data table
    if q.client_id:
        d = {
            "street": addrinfo["heiti_nf"],
            "number": addrinfo["husnr"],
            "lat": addrinfo["lat_wgs84"],
            "lon": addrinfo["long_wgs84"],
            "placename": addrinfo["stadur_nf"],
            "area": addrinfo["svaedi_nf"],
        }
        q.set_client_data("address", d)

        # Generate answer
        answ = "Heimilisfang þitt hefur verið skráð sem {0}".format(_addr2str(d))
        q.set_answer(*gen_answer(answ))
    else:
        q.set_answer(*gen_answer("Ekki tókst að vista heimilisfang. Auðkenni tækis vantar."))

    return True


def _whatsmynum_handler(q: Query, ql: str) -> bool:
    """ Handle queries of the form "Hvað er símanúmerið mitt? """
    pass


_MY_PHONE_IS_REGEXES = (
    r"símanúmer mitt er (.+)$",
    r"símanúmerið mitt er (.+)$",
    r"ég er með símanúmer (.+)$",
    r"ég er með símanúmerið (.+)$",
)


_DUNNO_PHONE_NUM = "Ég veit ekki hvert símanúmer þitt er, en þú getur sagt mér það."


def _mynumis_handler(q: Query, ql: str) -> bool:
    """ Handle queries of the form "Hvað er símanúmerið mitt? """
    return False


_DEVICE_TYPE_QUERIES = frozenset(
    (
        "hvernig síma er ég með",
        "hvernig síma á ég",
        "hvernig síma ertu á",
        "hvernig tæki ertu á",
        "hvernig tæki er ég með",
        "hvers konar síma á ég",
        "hvers konar síma er ég með",
        "hvers konar tæki á ég",
        "hvers konar tæki er ég með",
        "á hvaða tæki ertu að keyra",
        "á hvaða síma ertu",
        "á hvaða síma ertu að keyra",
        "á hvaða stýrikerfi ertu",
        "á hvaða stýrikerfi ertu að keyra",
        "á hvernig tæki ertu að keyra",
        "á hvernig síma ertu",
        "á hvernig síma ertu að keyra",
        "á hvernig stýrikerfi ertu",
        "á hvernig stýrikerfi ertu að keyra",
        "hvaða tæki ertu að keyra á",
        "hvaða síma ertu á",
        "hvaða síma ertu að keyra á",
        "hvaða stýrikerfi ertu á",
        "hvaða stýrikerfi ertu að keyra",
        "hvaða stýrikerfi er ég að keyra",
        "hvaða stýrikerfi ertu að keyra á",
        "hvaða síma er ég með",
        "hvaða síma á ég",
    )
)

_DUNNO_DEVICE_TYPE = "Ég veit ekki á hvaða tæki ég er að keyra."

_DEVICE_TYPE_TO_DESC = {
    "www": "Ég er að keyra í vafra. Meira veit ég ekki.",
    "ios": "Ég er að keyra á iOS stýrikerfinu frá Apple. Meira veit ég ekki.",
    "ios_flutter": "Ég er að keyra á iOS stýrikerfinu frá Apple. Meira veit ég ekki.",
    "android": "Ég er að keyra á Android stýrikerfinu frá Google. Meira veit ég ekki.",
    "android_flutter": "Ég er að keyra á Android stýrikerfinu frá Google. Meira veit ég ekki.",
}


def _device_type_handler(q: Query, ql: str) -> bool:
    """ Handle queries about user's device. """
    if ql not in _DEVICE_TYPE_QUERIES:
        return False

    if not q.client_type:
        q.set_key("DeviceInfo")
        q.set_answer(*gen_answer(_DUNNO_DEVICE_TYPE))
        return True

    for prefix in _DEVICE_TYPE_TO_DESC.keys():
        if q.client_type.startswith(prefix):
            answ = _DEVICE_TYPE_TO_DESC[prefix]
            q.set_answer(*gen_answer(answ))
            q.set_key("DeviceInfo")
            return True

    return False


# Handler functions for all query types supported by this module.
_HANDLERS = tuple(
    [
        _whoisme_handler,
        _whatsmyname_handler,
        _mynameis_handler,
        # _whatsmyaddr_handler,
        # _myaddris_handler,
        # _whatsmynum_handler,
        # _mynumis_handler,
        _device_type_handler,
    ]
)


def handle_plain_text(q: Query) -> bool:
    """ Handle plain text query. """
    ql = q.query_lower.rstrip("?")

    # Iterate over all handlers, see if any
    # of them wants to handle the query
    for h in _HANDLERS:
        handled = h(q, ql)
        if handled:
            q.set_qtype(_USERINFO_QTYPE)
            return True

    return False
