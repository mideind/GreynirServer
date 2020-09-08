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
# TODO: Handle redirection and disambiguation page results better.
# TODO: Fix regex that cleans wiki text.
# TODO: "Segðu mér meira um X" - Return more article text


import re
import random
from datetime import datetime, timedelta

from queries import query_json_api, gen_answer, cap_first
from query import Query


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
                "Fræddu mig um afstæðiskenninguna",
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
    # These take the subject in the nominative case
    QWikiSubjectNf "í" QWikipedia

    # These take the subject in the accusative case
    | "hvað" "segir" QWikipedia "um"? QWikiSubjectÞf
    | "hvað" "stendur" "í" QWikipedia "um" QWikiSubjectÞf
    | "hvað" "stendur" "um" QWikiSubjectÞf "í" QWikipedia
    | "hvað" "getur" "þú" "sagt" QWikiMeOrUsÞgf? "um" QWikiSubjectÞf
    | "hvað" "geturðu" "sagt" QWikiMeOrUsÞgf? "um" QWikiSubjectÞf
    | "hvað" "getur" QWikipedia "sagt" QWikiMeOrUsÞgf? "um" QWikiSubjectÞf
    | "hvaða" "upplýsingar" "ert" "þú" "með" "um" QWikiSubjectÞf
    | "hvaða" "upplýsingar" "ertu" "með" "um" QWikiSubjectÞf
    | "hvaða" "upplýsingar" "er" QWikipedia "með" "um" QWikiSubjectÞf
    | "hvaða" "upplýsingum" "býr" QWikipedia "yfir" "varðandi" QWikiSubjectÞf
    | "hvaða" "upplýsingum" "býrðu" "yfir" "varðandi" QWikiSubjectÞf
    | "hvað" "myndi" QWikipedia "segja" QWikiMeOrUsÞgf? "um" QWikiSubjectÞf
    | "fræddu" QWikiMeOrUsÞf "um" QWikiSubjectÞf
    | "geturðu" "frætt" QWikiMeOrUsÞf "um" QWikiSubjectÞf
    | "nennirðu" "að" "fræða" QWikiMeOrUsÞf "um" QWikiSubjectÞf

    # These take the subject in the dative case
    | "segðu" QWikiMeOrUsÞgf "frá" QWikiSubjectÞgf
    | "segðu" QWikiMeOrUsÞgf "eitthvað" "um" QWikiSubjectÞf
    | "flettu" "upp" QWikiSubjectÞgf "í" QWikipedia
    | "geturðu" "flett" "upp" QWikiSubjectÞgf "í" QWikipedia
    | "nennirðu" "að" "fletta" "upp" QWikiSubjectÞgf "í" QWikipedia
    | "gætirðu" "flett" "upp" QWikiSubjectÞgf "í" QWikipedia

QWikiMeOrUsÞgf →
    "mér" | "okkur"

QWikiMeOrUsÞf →
    "mig" | "okkur"

QWikiSubjectNf →
    QWikiPrevSubjectNf | QWikiSubjectNlNf

QWikiSubjectNlNf →
    Nl_nf

QWikiSubjectÞf →
    QWikiPrevSubjectÞf | QWikiSubjectNlÞf

QWikiSubjectNlÞf →
    Nl_þf

QWikiSubjectÞgf →
    QWikiPrevSubjectÞgf | QWikiSubjectNlÞgf

QWikiSubjectNlÞgf →
    Nl_þgf

QWikiPrevSubjectNf →
    "hann" | "hún" | "það"

QWikiPrevSubjectÞf →
    "hann" | "hana" | "það"

QWikiPrevSubjectÞgf →
    "honum" | "henni" | "því"

QWikipedia →
    {0}

$score(+35) QWikiPrevSubjectNf
$score(+35) QWikiPrevSubjectÞf
$score(+35) QWikiPrevSubjectÞf

$score(+35) QWikiQuery

""".format(
    " | ".join('"' + v + '"' for v in _WIKI_VARIATIONS)
)


def QWikiQuery(node, params, result):
    # Set the query type
    result.qtype = _WIKI_QTYPE
    result.qkey = result.get("subject_nom")


def QWikiSubjectNlNf(node, params, result):
    result["subject_nom"] = result._nominative


QWikiSubjectNlÞf = QWikiSubjectNlÞgf = QWikiSubjectNlNf


def QWikiPrevSubjectNf(node, params, result):
    """ Reference to previous result, usually via personal
        pronouns ('Hvað segir Wikipedía um hann/hana/það?'). """
    q = result.state.get("query")  # type: Query
    ctx = None if q is None else q.fetch_context()
    ctx_keys = ["person_name", "entity_name", "subject"]
    if ctx is not None:
        keys = list(filter(lambda k: k in ctx, ctx_keys))
        if keys:
            result.context_reference = True
            result["subject_nom"] = ctx[keys[0]]
    if "subject_nom" not in result:
        # There is a reference to a previous result
        # which is not available: flag an error
        result.error_context_reference = True


QWikiPrevSubjectÞgf = QWikiPrevSubjectÞf = QWikiPrevSubjectNf


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


_WIKI_API_URL = (
    "https://is.wikipedia.org/w/api.php?format=json&action=query"
    "&prop=extracts&exintro&explaintext&redirects=1&titles={0}"
)


def _query_wiki_api(subject):
    """ Fetch JSON from Wikipedia API """
    url = _WIKI_API_URL.format(subject)
    return query_json_api(url)


def get_wiki_summary(subject_nom):
    """ Fetch summary of subject from Icelandic Wikipedia """

    def has_entry(r):
        return (
            r
            and "query" in r
            and "pages" in r["query"]
            and "-1" not in r["query"]["pages"]
        )

    # Wiki pages always start with an uppercase character
    cap_subj = cap_first(subject_nom)
    # Talk to API
    res = _query_wiki_api(cap_subj)
    # OK, Wikipedia doesn't have anything with current capitalization
    # or lack thereof. Try uppercasing first character of each word.
    titled_subj = subject_nom.title()
    if not has_entry(res) and cap_subj != titled_subj:
        res = _query_wiki_api(titled_subj)

    not_found = "Ég fann ekkert um '{0}' í Wikipedíu".format(subject_nom)

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
    if "qtype" not in result:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
        return

    # Successfully matched a query type, we're handling it...
    q.set_qtype(result.qtype)

    # Beautify query by fixing spelling of Wikipedia
    b = q.beautified_query
    for w in _WIKI_VARIATIONS:
        b = b.replace(w, _WIKIPEDIA_CANONICAL)
        b = b.replace(w.capitalize(), _WIKIPEDIA_CANONICAL)
    q.set_beautified_query(b)

    # Check for error in context ref
    if "error_context_reference" in result:
        q.set_answer(*gen_answer("Ég veit ekki til hvers þú vísar."))
        return

    # We have a subject
    if "subject_nom" in result:
        # Fetch data from Wikipedia API
        subj = result["subject_nom"]
        answer = get_wiki_summary(subj)
        response = dict(answer=answer)
        voice = _clean_voice_answer(answer)
        # Set query answer
        q.set_answer(response, answer, voice)
        q.set_key(subj)
        q.set_context(dict(subject=subj))
        q.set_source("Wikipedía")
        # Cache reply for 24 hours
        q.set_expires(datetime.utcnow() + timedelta(hours=24))
        return

    q.set_error("E_QUERY_NOT_UNDERSTOOD")
