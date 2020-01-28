"""

    Greynir: Natural language processing for Icelandic

    Wikipedia query response module

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


    This modules answers queries by fetching information on diverse topics
    from the Icelandic Wikipedia API.

"""

# TODO: Shorten overly long first paragraphs.
# TODO: Fix regex that cleans wiki text.


import re
import random
from datetime import datetime, timedelta

from queries import query_json_api


_WIKI_QTYPE = "Wikipedia"


# For end user presentation
_WIKIPEDIA_CANONICAL = "Wikipedía"

_WIKI_VARIATIONS = (
    # Nominative
    "vikipedija",
    "víkípedija",
    "vikípedija",
    "víkipedija",
    "víkípedía",
    "víkipedía",
    "vikípedía",
    "vikipedía",
    "wikipedia",
    "wikipedía",
    # Dative
    "vikipediju",
    "víkípediju",
    "vikípediju",
    "víkipediju",
    "víkípedíu",
    "víkipedíu",
    "vikípedíu",
    "vikipedíu",
    "wikipediu",
    "wikipedíu",
)


TOPIC_LEMMAS = _WIKI_VARIATIONS


def help_text(lemma):
    """ Help text to return when query.py is unable to parse a query but
        one of the above lemmas is found in it """
    return "Ég get svarað ef þú spyrð til dæmis: {0}?".format(
        random.choice(
            (
                "Hvað segir Wikipedía um Berlín",
                "Hvað getur Wikipedía sagt mér um heimspeki",
                "Fræddu mig um afstæðiskenninguna" "Flettu upp ",
            )
        )
    )


# Indicate that this module wants to handle parse trees for queries,
# as opposed to simple literal text strings
HANDLE_TREE = True

# The context-free grammar for the queries recognized by this plug-in module
GRAMMAR = """

Query →
    QWikiQuery '?'?

QWikiQuery →
    # These take the subject in the accusative case
    "hvað" "segir" QWikipedia "um" QWikiSubjectÞf
    | "hvað" "stendur" "í" QWikipedia "um" QWikiSubjectÞf
    | "hvað" "stendur" "um" QWikiSubjectÞf "í" QWikipedia
    | "hvað" "getur" "þú" "sagt" "mér"? "um" QWikiSubjectÞf
    | "hvað" "geturðu" "sagt" "mér"? "um" QWikiSubjectÞf
    | "hvað" "getur" QWikipedia "sagt" "mér"? "um" QWikiSubjectÞf
    | "hvaða" "upplýsingar" "ert" "þú" "með" "um" QWikiSubjectÞf
    | "hvaða" "upplýsingar" "ertu" "með" "um" QWikiSubjectÞf
    | "hvaða" "upplýsingar" "er" QWikipedia "með" "um" QWikiSubjectÞf
    | "hvaða" "upplýsingum" "býr" QWikipedia "yfir" "varðandi" QWikiSubjectÞf
    | "hvaða" "upplýsingum" "býrðu" "yfir" "varðandi" QWikiSubjectÞf
    | "hvað" "myndi" QWikipedia "segja" "mér"? "um" QWikiSubjectÞf
    | "fræddu" "mig" "um" QWikiSubjectÞf
    | "geturðu" "frætt" "mig" "um" QWikiSubjectÞf
    | "nennirðu" "að" "fræða" "mig" "um" QWikiSubjectÞf

    # These take the subject in the dative case
    | "segðu" "mér" "frá" QWikiSubjectÞgf
    | "flettu" "upp" QWikiSubjectÞgf "í" QWikipedia
    | "geturðu" "flett" "upp" QWikiSubjectÞgf "í" QWikipedia
    | "nennirðu" "að" "fletta" "upp" QWikiSubjectÞgf "í" QWikipedia
    | "gætirðu" "flett" "upp" QWikiSubjectÞgf "í" QWikipedia

QWikiSubjectÞf →
    Nl_þf

QWikiSubjectÞgf →
    Nl_þgf

QWikipedia →
    {0}

$score(+35) QWikiQuery

""".format(
    " | ".join('"' + v + '"' for v in _WIKI_VARIATIONS)
)


def QWikiQuery(node, params, result):
    # Set the query type
    result.qtype = _WIKI_QTYPE
    result.qkey = result["subject_nom"]


def QWikiSubjectÞf(node, params, result):
    result["subject_nom"] = result._nominative
    result["subject_dat"] = result._text


def QWikiSubjectÞgf(node, params, result):
    result["subject_nom"] = result._nominative
    result["subject_dat"] = result._text


def EfLiður(node, params, result):
    """ Don't change the case of possessive clauses """
    result._nominative = result._text


def FsMeðFallstjórn(node, params, result):
    """ Don't change the case of prepositional clauses """
    result._nominative = result._text


def _clean_answer(answer):
    # Split on newline, use only first paragraph
    a = answer.split("\n")[0].strip()
    # Get rid of "Getur líka átt við" leading sentence
    if a.startswith("Getur líka átt"):
        a = ". ".join(a.split(".")[1:])
    # Remove text within parentheses
    a = re.sub(r"\([^)]+\)", "", a)
    # Fix any whitespace formatting issues created by
    # removing text within parentheses
    a = re.sub(r"\s+", " ", a)
    a = re.sub(r"\s\.$", ".", a)
    a = re.sub(r"\s,\s", ", ", a)
    a = re.sub(r"\s\.\s", ". ", a)
    # E.g. "100-700" becomes "100 til 700"
    a = re.sub(r"(\d+)\s?\-\s?(\d+)", r"\1 til \2", a)
    return a


def _clean_voice_answer(answer):
    a = answer.replace(" m.a. ", " meðal annars ")
    a = a.replace(" þ.e. ", " það er ")
    a = a.replace(" t.d. ", " til dæmis ")
    return a


_WIKI_API_URL = "https://is.wikipedia.org/w/api.php?format=json&action=query&prop=extracts&exintro&explaintext&redirects=1&titles={0}"


def _query_wiki_api(subject):
    """ Fetch JSON from Wikipedia API """
    url = _WIKI_API_URL.format(subject)
    return query_json_api(url)


def get_wiki_summary(subject_nom, subject_dat):
    """ Fetch summary of subject from Icelandic Wikipedia """

    def has_entry(r):
        return r and "query" in r and "pages" in r["query"]

    # Wiki pages always start with an uppercase character
    cap_subj = subject_nom[0].upper() + subject_nom[1:]
    # Talk to API
    res = _query_wiki_api(cap_subj)
    # OK, Wikipedia doesn't have anything with current capitalization
    # or lack thereof. Try uppercasing first character of each word.
    if not has_entry(res):
        res = _query_wiki_api(subject_nom.title())

    not_found = "Ég fann ekkert um {0} í Wikipedíu".format(subject_dat)

    if not has_entry(res):
        return not_found

    pages = res["query"]["pages"]
    keys = pages.keys()
    if not len(keys) or "-1" in keys:
        return not_found

    # Pick first matching entry
    k = sorted(keys)[0]
    text = pages[k].get("extract", "")

    return _clean_answer(text)


def sentence(state, result):
    """ Called when sentence processing is complete """
    q = state["query"]
    if "qtype" in result and "subject_nom" in result:
        # Successfully matched a query type
        q.set_qtype(result.qtype)
        q.set_key(result.qkey)

        # Fetch from Wikipedia API
        answer = get_wiki_summary(result["subject_nom"], result["subject_dat"])
        response = dict(answer=answer)
        voice = _clean_voice_answer(answer)
        q.set_answer(response, answer, voice)

        # Beautify query by fixing spelling of Wikipedia
        b = q.beautified_query
        for w in _WIKI_VARIATIONS:
            b = b.replace(w, _WIKIPEDIA_CANONICAL)
            b = b.replace(w.capitalize(), _WIKIPEDIA_CANONICAL)
        q.set_beautified_query(b)
        q.set_source("Wikipedía")
        # Cache reply for 24 hours
        q.set_expires(datetime.utcnow() + timedelta(hours=24))

    else:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
