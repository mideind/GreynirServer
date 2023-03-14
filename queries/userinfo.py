"""

    Greynir: Natural language processing for Icelandic

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


    This module handles statements and queries related to user info, e.g.
    name, address, phone number, device type, etc.

"""

# TODO: "Heinsaðu fyrirspurnasögu [mína]", "Hreinsaðu öll gögn um mig", etc. commands
# TODO: "hvernig veistu hvað ég heiti?", "hvernig veistu X um mig?"

from typing import Dict, Match, Optional, cast

import re

from reynir import NounPhrase
from reynir.bindb import GreynirBin

from geo import icelandic_addr_info, iceprep_for_placename, iceprep_for_street
from queries import ClientDataDict, Query
from queries.util import gen_answer
from speech.trans.num import numbers_to_text


_USERINFO_QTYPE = "UserInfo"


_WHO_IS_ME = "hver er {0}"
_YOU_ARE = "Þú, kæri notandi, heitir {0}."


def _whoisme_handler(q: Query, ql: str) -> bool:
    """Handle queries of the form "Hver er [nafn notanda]?" """
    nd = q.client_data("name")
    if not nd:
        return False

    for t in ["full", "first"]:
        if t not in nd:
            continue
        name = cast(str, nd[t])
        if ql == _WHO_IS_ME.format(name.lower()):
            q.set_answer(*gen_answer(_YOU_ARE.format(name)))
            return True

    return False


_WHATS_MY_NAME = frozenset(
    (
        "hvað heiti ég fullu nafni",
        "hvað heiti ég",
        "hvað heitir ég",
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
        "segðu nafn mitt",
        "segðu nafnið mitt",
        "manstu hvað ég heiti",
        "manst þú hvað ég heiti",
        "þekkir þú mig",
        "þekkirðu mig",
    )
)


_DUNNO_NAME = "Ég veit ekki hvað þú heitir, en þú getur sagt mér það."


def _whatsmyname_handler(q: Query, ql: str) -> bool:
    """Handle queries of the form "Hvað heiti ég?" """
    if ql not in _WHATS_MY_NAME:
        return False
    answ: str
    nd = q.client_data("name")
    if nd and "full" in nd:
        answ = f"Þú heitir {nd['full']}."
    elif nd and "first" in nd:
        answ = f"Þú heitir {nd['first']}."
        if nd["first"] == "Embla":
            answ += " alveg eins og ég!"
    else:
        answ = _DUNNO_NAME
    q.set_key("UserNameInfo")
    q.set_answer(*gen_answer(answ))
    return True


_MY_NAME_IS_REGEXES = frozenset(
    (
        r"^ég heiti (.+)$",
        r"^hæ ég heiti (.+)$",
        r"^hæ embla ég heiti (.+)$",
        r"^nafn mitt er (.+)$",
        r"^nafnið mitt er (.+)$",
        r"^fullt nafn mitt er (.+)$",
        r"^ég ber heitið (.+)$",
        r"^ég ber nafnið (.+)$",
        r"^ég er kallaður (.+)$",
        r"^ég kallast (.+)$",
    )
)

_MY_NAME_IS_RESPONSES = {
    "hk": "Gaman að kynnast þér, {0}. Ég heiti Embla.",
    "kk": "Sæll og blessaður, {0}. Ég heiti Embla.",
    "kvk": "Sæl og blessuð, {0}. Ég heiti Embla.",
}


def _mynameis_handler(q: Query, ql: str) -> bool:
    """Handle queries of the form "Ég heiti X", store this information."""
    m: Optional[Match[str]] = None
    for rx in _MY_NAME_IS_REGEXES:
        m = re.search(rx, ql)
        if m:
            break
    if m:
        fname = m.group(1).strip()
        if not fname:
            return False

        # Clean up name string
        name = fname.split(" og ")[0]  # "ég heiti X og blablabla"
        name = name.split(" hvað ")[0]  # "ég heiti X hvað heitir þú"

        # Handle "ég heiti ekki X", "ég heiti það ekki"
        components = name.split()
        if components[0] == "ekki" or (
            len(components) >= 2 and components[:2] == ("það", "ekki")
        ):
            q.set_answer(*gen_answer("Hvað heitirðu þá?"))
            return True

        # Get first name, look up gender for a gender-tailored response
        with GreynirBin.get_db() as bdb:
            fn = components[0].title()
            gender = bdb.lookup_name_gender(fn) or "hk"
            resp = _MY_NAME_IS_RESPONSES[gender]
            answ = resp.format(fn)
            if fn == "Embla":
                answ = "Sæl og blessuð. Ég heiti líka Embla!"

        # Save this info about user to query data table
        if q.client_id:
            qdata: ClientDataDict = dict(full=name.title(), first=fn, gender=gender)
            q.set_client_data("name", qdata)

        # Beautify query by capitalizing the name provided
        bq = q.beautified_query
        q.set_beautified_query(bq.replace(name, name.title()))

        # Generate answer
        voice = answ.replace(",", "")
        q.set_answer(dict(answer=answ), answ, voice)
        q.query_is_command()
        q.set_key("SetUserName")

        return True

    return False


def _addr2str(addr: Dict[str, str], case: str = "nf") -> str:
    """Format address canonically given dict w. address info."""
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
    return astr


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
    """Handle queries of the form "Hvar á ég heima?" """
    if ql not in _WHATS_MY_ADDR:
        return False
    answ = None
    ad = q.client_data("address")
    if not ad:
        q.set_answer(*gen_answer(_DUNNO_ADDRESS))
    else:
        addr = cast(Dict[str, str], ad)
        street = addr["street"]
        prep = iceprep_for_street(street)
        answ = f'Þú átt heima {prep} {_addr2str(addr, case="þgf")}'
        voice = numbers_to_text(answ)
        resp = dict(answer=answ)
        q.set_answer(resp, answ, voice)
    return True


_MY_ADDRESS_REGEXES = (
    r"ég á heima á (.+)$",
    r"ég á heima í (.+)$",
    r"ég bý á (.+)$",
    r"ég bý í (.+)$",
    r"heimili mitt er á (.+)$",
    r"heimili mitt er í (.+)$",
    r"heimili mitt er (.+)$",
    r"heimilisfang mitt er á (.+)$",
    r"heimilisfang mitt er í (.+)$",
    r"heimilisfang mitt er (.+)$",
)

_ADDR_LOOKUP_FAIL = "Ég fann ekki þetta heimilisfang í staðfangaskrá."
_ADDR_CLIENT_ID_MISSING = """Ég get ekki vistað heimilisfangið því
 ég veit ekki auðkenni tækisins sem þú notar."""


def _myaddris_handler(q: Query, ql: str) -> bool:
    """Handle queries of the form "Ég á heima á [heimilisfang]".
    Store this info as query data."""
    m: Optional[Match[str]] = None
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
    m = re.search(r"^(\w+)\s(\d+)\s?(([í|á]\s)?(\w+)?)?$", addr_str.strip())
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
        answ = f"Heimilisfang þitt hefur verið skráð sem {_addr2str(d)}"
        q.set_answer(*gen_answer(answ))
    else:
        q.set_answer(*gen_answer(_ADDR_CLIENT_ID_MISSING))

    return True


#def _whatsmynum_handler(q: Query, ql: str) -> bool:
#    """Handle queries of the form "Hvað er símanúmerið mitt?"""
#    return False
#
#_MY_PHONE_IS_REGEXES = (
#    r"símanúmer mitt er (.+)$",
#    r"símanúmerið mitt er (.+)$",
#    r"ég er með símanúmer (.+)$",
#    r"ég er með símanúmerið (.+)$",
#)
#
#_DUNNO_PHONE_NUM = "Ég veit ekki hvert símanúmer þitt er, en þú getur sagt mér það."


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
    "www": "Ég er að keyra í vafra.",
    "ios": "Ég er að keyra á iOS stýrikerfinu frá Apple.",
    "ios_flutter": "Ég er að keyra á iOS stýrikerfinu frá Apple.",
    "android": "Ég er að keyra á Android stýrikerfinu frá Google.",
    "android_flutter": "Ég er að keyra á Android stýrikerfinu frá Google.",
    "python_linux": "Ég er að keyra á Linux stýrikerfinu.",
}


def _device_type_handler(q: Query, ql: str) -> bool:
    """Handle queries about user's device."""
    if ql not in _DEVICE_TYPE_QUERIES:
        return False

    q.set_key("DeviceInfo")

    if q.client_type:
        for prefix in _DEVICE_TYPE_TO_DESC.keys():
            if q.client_type.startswith(prefix):
                answ = _DEVICE_TYPE_TO_DESC[prefix] + " Meira veit ég ekki."
                q.set_answer(*gen_answer(answ))
                return True

    q.set_answer(*gen_answer(_DUNNO_DEVICE_TYPE))
    return True


_CLIENT_VERSION_QUERIES = frozenset(
    (
        "hvaða útgáfu er ég með",
        "hvaða útgáfu er ég að keyra",
        "hvaða útgáfu er ég keyrandi",
        "hvaða útgáfu er verið að keyra",
        "hvaða útgáfu af emblu er ég að keyra",
        "hvaða útgáfu af emblu er ég með",
        "hvaða útgáfu af emblu er ég með í gangi",
        "hvaða útgáfa af emblu er að keyra",
        "hvaða útgáfa af emblu er ég að keyra",
        "hvaða útgáfa er keyrandi",
        "hvaða útgáfa er í gangi",
        "hvaða útgáfa ertu",
        "hvaða útgáfa ert þú",
        "hvaða útgáfa af emblu ertu",
        "hvaða útgáfa af emblu ert þú",
        "útgáfa af emblu",
        "útgáfan af emblu",
    )
)

_DUNNO_CLIENT_VERSION = "Ég veit ekki hvaða útgáfa er að keyra."

_DEVICE_TYPE_TO_APPENDED_DESC = {
    "www": "í vafra",
    "ios": "fyrir iOS",
    "ios_flutter": "fyrir iOS",
    "android": "fyrir Android",
    "android_flutter": "fyrir Android",
    "python_linux": "fyrir Linux",
}


def _client_version_handler(q: Query, ql: str) -> bool:
    """Handle queries about client version."""
    if ql not in _CLIENT_VERSION_QUERIES:
        return False

    q.set_key("ClientVersion")

    if not q.client_version:
        q.set_answer(*gen_answer(_DUNNO_CLIENT_VERSION))
        return True

    platform = (
        _DEVICE_TYPE_TO_APPENDED_DESC.get(q.client_type, "") if q.client_type else ""
    )

    answ = "Emblu {0} {1}".format(q.client_version, platform)
    vers4voice = q.client_version.replace(".", " komma ")
    voice = "Þú ert að keyra Emblu {0} {1}".format(vers4voice, platform).strip()
    q.set_answer(dict(answer=answ), answ, voice)

    return True


# Handler functions for all query types supported by this module.
_HANDLERS = tuple(
    [
        _whoisme_handler,
        _whatsmyname_handler,
        _mynameis_handler,
        _whatsmyaddr_handler,
        _myaddris_handler,
        # _whatsmynum_handler,
        # _mynumis_handler,
        _device_type_handler,
        _client_version_handler,
    ]
)


def handle_plain_text(q: Query) -> bool:
    """Handle plain text query."""
    ql = q.query_lower.rstrip("?")

    # Iterate over all handlers, see if any
    # of them wants to handle the query
    for h in _HANDLERS:
        handled = h(q, ql)
        if handled:
            q.set_qtype(_USERINFO_QTYPE)
            return True

    return False
