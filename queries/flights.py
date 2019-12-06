"""

    Greynir: Natural language processing for Icelandic

    Flight schedule query response module

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
    along with this program. If not, see http://www.gnu.org/licenses/.


    This module handles queries relating to air travel.

"""

# TODO: Styðja "Köben" :)


import random


_FLIGHTS_QTYPE = "Flights"


TOPIC_LEMMAS = ["flugvél", "flugvöllur", "flug", "lenda"]


def help_text(lemma):
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
        r"hvenær kemur næsta vél frá (.+)$",
        r"hvenær kemur næsta flugvél frá (.+)$",
        r"hver er komutíminn fyrir næstu vél frá (.+)$",
        r"hver er komutíminn fyrir næstu flugvél frá (.+)$",
        r"hver er komutími næstu vélar frá (.+)$",
        r"hver er komutími næstu flugvélar frá (.+)$",
    )
)

_DEPARTING_RX = frozenset(
    (
        r"hvenær fer næsta vél til (.+)$",
        r"hvenær fer næsta flugvél til (.+)$",
        r"hvenær flýgur næsta vél til (.+)$",
        r"hvenær flýgur næsta flugvél til (.+)$",
        r"hver er brottfarartíminn fyrir næstu vél til (.+)$",
        r"hver er brottfarartíminn fyrir næstu flugvél til (.+)$",
        r"hver er brottfarartími næstu vélar til (.+)$",
        r"hver er brottfarartími næstu flugvélar til (.+)$",
    )
)
