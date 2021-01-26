"""

    Greynir: Natural language processing for Icelandic

    Flight schedule query response module

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
    along with this program. If not, see http://www.gnu.org/licenses/.


    This module handles queries relating to air travel.

"""

import re
import random
import logging
from datetime import datetime, timedelta

from queries import query_json_api


_FLIGHTS_QTYPE = "Flights"


TOPIC_LEMMAS = ["flugvél", "flugvöllur", "flug", "lenda"]


def help_text(lemma: str) -> str:
    """ Help text to return when query.py is unable to parse a query but
        one of the above lemmas is found in it """
    return "Ég get svarað ef þú spyrð til dæmis: {0}?".format(
        random.choice(
            (
                "Hvenær lendir næsta vél frá Kaupmannahöfn",
                "Hvenær fer næsta vél til Lundúna",
            )
        )
    )


_LANDING_RX = frozenset(
    (
        r"hvenær lendir næsta vél frá (.+)$",
        r"hvenær lendir næsta flugvél frá (.+)$",
        r"hvenær lendir næsta flug frá (.+)$",
        r"hvenær kemur næsta vél frá (.+)$",
        r"hvenær kemur næsta flugvél frá (.+)$",
        r"hvenær kemur næsta flug frá (.+)$",
        r"hver er komutíminn fyrir næstu vél frá (.+)$",
        r"hver er komutíminn fyrir næstu flugvél frá (.+)$",
        r"hver er komutíminn fyrir næsta flug frá (.+)$",
        r"hver er komutími næstu vélar frá (.+)$",
        r"hver er komutími næstu flugvélar frá (.+)$",
        r"hver er komutími næsta flugs frá (.+)$",
    )
)

_DEPARTING_RX = frozenset(
    (
        r"hvenær fer næsta vél til (.+)$",
        r"hvenær fer næsta flugvél til (.+)$",
        r"hvenær fer næsta flug til (.+)$",
        r"hvenær flýgur næsta vél til (.+)$",
        r"hvenær flýgur næsta flugvél til (.+)$",
        r"hvenær flýgur næsta flug til (.+)$",
        r"hver er brottfarartíminn fyrir næstu vél til (.+)$",
        r"hver er brottfarartíminn fyrir næstu flugvél til (.+)$",
        r"hver er brottfarartíminn fyrir næsta flug til (.+)$",
        r"hver er brottfarartími næstu vélar til (.+)$",
        r"hver er brottfarartími næstu flugvélar til (.+)$",
        r"hver er brottfarartími næsta flugs til (.+)$",
    )
)

_ISAVIA_URL = (
    "https://www.isavia.is/json/flight/?cargo=0&airport={0}"
    "&dateFrom={1}&dateTo={2}&language=is&arrivals={3}"
)


def _fetch_flight_info(from_date, to_date, ftype="arrivals"):
    """ Fetch flight data from Isavia's JSON API. """
    assert ftype in ("arrivals", "departures")

    fmt = "%Y-%m-%d %H:%M"
    from_str = from_date.strftime(fmt)
    to_str = to_date.isoformat(fmt)
    arr = "true" if ftype == "arrivals" else "false"
    airport = "KEF"

    url = _ISAVIA_URL.format(airport, from_str, to_str, arr)

    res = query_json_api(url)

    # Verify sanity of result
    if not res or "Success" not in res or not res["Success"] or "Items" not in res:
        return None

    print(res)

    return res["Items"]


_AIRPORT_ABBR_MAP = {"Köben": "Kaupmannahöfn"}


def handle_plain_text(q) -> bool:
    """ Handle a plain text query, contained in the q parameter """
    return False  # This module is disabled for now

    ql = q.query_lower.rstrip("?")

    airport = None
    departure = False

    # Flight arrival queries
    for rx in _LANDING_RX:
        matches = re.search(rx, ql)
        if matches:
            airport = matches.group(1)
            break

    # Flight departure queries
    if not airport:
        for rx in _DEPARTING_RX:
            matches = re.search(rx, ql)
            if matches:
                airport = matches.group(1)
                departure = True
                break

    # Nothing caught by regexes, bail
    if not matches:
        return False

    # Look up in Isavia API for flights at KEF
    try:
        answ = False
        _fetch_flight_info(datetime.utcnow(), datetime.utcnow() + timedelta(hours=24))
    except Exception as e:
        logging.warning("Exception generating answer from flight data: {0}".format(e))
        q.set_error("E_EXCEPTION: {0}".format(e))
        answ = None

    if answ:
        q.set_qtype(_FLIGHTS_QTYPE)
        q.set_answer(*answ)
        return True

    return False
