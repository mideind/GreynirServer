"""

    Greynir: Natural language processing for Icelandic

    Copyright (C) 2022 Miðeind ehf.

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

    This module handles picture-related queries.

"""

from typing import Optional

import random
import logging
from datetime import datetime, timedelta
from urllib.parse import urlparse

from query import Query, QueryStateDict
from queries import gen_answer, icequote
from reynir import NounPhrase
from tree import Result, Node
from images import get_image_url, Img


_PIC_QTYPE = "Picture"

TOPIC_LEMMAS = ["mynd", "ljósmynd"]


def help_text(lemma: str) -> str:
    """Help text to return when query.py is unable to parse a query but
    one of the above lemmas is found in it"""
    return "Ég get svarað ef þú segir til dæmis: {0}?".format(
        random.choice(
            (
                "Sýndu mér mynd af Halldóri Laxness",
                "Sýndu ljósmynd af Kára Stefánssyni",
                "Sýndu mynd af Hörpunni",
            )
        )
    )


# This module wants to handle parse trees for queries
HANDLE_TREE = True

# The grammar nonterminals this module wants to handle
QUERY_NONTERMINALS = {"QPic"}

# The context-free grammar for the queries recognized by this plug-in module
GRAMMAR = """

Query →
    QPic

QPic →
    QPicQuery '?'?

QPicQuery →
    QPicShowMePictureQuery | QPicWrongPictureQuery

QPicShowMe →
    "sýndu" | "getur" "þú" "sýnt" | "geturðu" "sýnt" | "viltu" "sýna" |
    "nennirðu" "að" "sýna" | "nennir" "þú" "að" "sýna"

QPicShowMePictureQuery →
    QPicShowMe QPicMeOrUs? QPicPictureOrPhoto "af" QPicSubject

QPicPictureOrPhoto →
    "ljósmynd" | "mynd" | "ljósmyndir" | "myndir"

QPicMeOrUs →
    "mér" | "okkur"

QPicSubject →
    Nl_þgf

QPicWrongPictureQuery →
    "þetta" QPicIsWas QPicWrong QPicPictureOrPhoto

QPicWrong →
    "röng" | "vitlaus" | "ekki" "rétt"

QPicIsWas →
    "er" | "var"

"""


def QPicQuery(node: Node, params: QueryStateDict, result: Result) -> None:
    # Set the query type
    result.qtype = _PIC_QTYPE


def _preprocess(s: str) -> str:
    return s


def QPicSubject(node: Node, params: QueryStateDict, result: Result) -> None:
    n = _preprocess(result._text)
    nom = NounPhrase(n).nominative or n
    result.subject = nom
    result.subject_þgf = result._text


def QPicWrongPictureQuery(node: Node, params: QueryStateDict, result: Result) -> None:
    result.wrong = True


def _gen_pic_answer(result: Result, q: Query):
    """Generate answer to query asking for a picture of something."""
    subj = result["subject"]
    subj_þgf = result["subject_þgf"]

    # Look up picture using Google Images API
    img: Optional[Img] = None
    try:
        img = get_image_url(subj)
        if img and img.src:
            # We found an image of the subject
            answ = f"Hér er mynd sem ég fann af {icequote(subj_þgf)}"
            q.set_answer(*gen_answer(answ))
            q.set_image(img.src)
            src: str = "Google Images"
            o = urlparse(img.src)
            if o and o.hostname:
                src = o.hostname
            q.set_source(src)
            # q.set_expires(datetime.utcnow() + timedelta(hours=1))
        else:
            # No picture found
            q.set_answer(*gen_answer(f"Engin mynd fannst af {icequote(subj_þgf)}"))
    except Exception as e:
        q.set_answer(*gen_answer(f"Ekki tókst að leita í myndagrunni"))

    q.set_key(subj)
    q.set_qtype(result.qtype)


_WRONG_PIC_ANSWER = "Ég biðst afsökunar á því. Enginn er fullkominn."


def _gen_wrong_pic_answer(result: Result, q: Query):
    """Query states that previous picture was wrong."""
    q.set_qtype(result.qtype)
    q.set_answer(*gen_answer(_WRONG_PIC_ANSWER))


def sentence(state: QueryStateDict, result: Result) -> None:
    """Called when sentence processing is complete."""
    q: Query = state["query"]

    if "qtype" in result:
        # Successfully matched a query type
        try:
            if "wrong" in result:
                _gen_wrong_pic_answer(result, q)
            else:
                _gen_pic_answer(result, q)
        except Exception as e:
            logging.warning(f"Exception answering picture query: {e}")
            q.set_error(f"E_EXCEPTION: {e}")
            return
    else:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
