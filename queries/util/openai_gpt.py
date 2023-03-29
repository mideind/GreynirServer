"""

    Greynir: Natural language processing for Icelandic

    OpenAI GPT interface module

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


    This module provides an interface to OpenAI's GPT language models.

"""

from __future__ import annotations

from typing import (
    Any,
    Dict,
    Iterable,
    List,
    Mapping,
    Tuple,
    cast,
)
from typing_extensions import TypedDict

import re
import os
import json

import openai

from settings import Settings


class ChatMessage(TypedDict):
    """A single chat message"""

    role: str
    content: str


class OpenAiChoiceDict(TypedDict):
    """The 'choices' part of the GPT model response"""

    finish_reason: str
    index: int
    message: ChatMessage


class UsageDict(TypedDict):
    """The 'usage' part of the GPT model response"""

    completion_tokens: int
    prompt_tokens: int
    total_tokens: int


class OpenAiDict(TypedDict):
    """The GPT model response"""

    choices: List[OpenAiChoiceDict]
    created: int
    id: str
    model: str
    object: str
    usage: UsageDict


class HistoryDict(TypedDict):
    """A single history item"""

    q: str
    a: str


# The list of previous Q/A pairs
HistoryList = List[HistoryDict]

# Set the OpenAI API key
api_key = os.getenv("OPENAI_API_KEY") or ""
openai.api_key = api_key

OPENAI_KEY_PRESENT = bool(api_key)

# GPT model to use
MODEL = os.getenv("OPENAI_MODEL") or "text-davinci-003"

LANG_MACRO = "$LANG="
LANG_REGEX = re.compile(r"\$LANG=([a-z]{2}_[A-Z]{2})\$(.*)", re.DOTALL)


def jdump(s: Any) -> str:
    """Dump a JSON-serializable object to a string"""
    return json.dumps(s, ensure_ascii=False)


class Completion:

    """Generates OpenAI completions"""

    @classmethod
    def _create(cls, *args: Any, **kwargs: Any) -> OpenAiDict:
        """
        Creates a new completion while handling formatting and parsing.
        """
        return cast(Any, openai).ChatCompletion.create(*args, model=MODEL, **kwargs)

    @classmethod
    def create_from_preamble_and_history(
        cls, *, system: str, preamble: str = "", history_list: HistoryList = [], query: str, **kwargs: Any,
    ) -> OpenAiDict:
        """Assemble a prompt for the GPT model given a preamble and history"""
        messages: List[ChatMessage] = []
        messages.append({"role": "system", "content": system})
        for h in history_list:
            if "q" in h and "a" in h:
                # Put the preamble in front of the first user query
                user = preamble + "\n" + h["q"] if preamble else h["q"]
                preamble = ""
                messages.append({"role": "user", "content": user})
                messages.append({"role": "assistant", "content": h["a"]})
        # Put the preamble in front of the query, if not already included
        query = preamble + "\n" + query if preamble else query
        messages.append({"role": "user", "content": query})
        if Settings.DEBUG:
            print(json.dumps(messages, ensure_ascii=False, indent=2))
        return cls._create(messages=messages, **kwargs)


def detect_language(answer: str) -> Tuple[str, str]:
    # Use regex to extract language code from $LANG=...$ prefix, if present
    if not answer:
        return "", ""
    locale = ""
    m = re.match(LANG_REGEX, answer)
    if m:
        # A language code is specified:
        # set the voice synthesizer locale accordingly
        answer = m.group(2).strip()
        locale = m.group(1)
    # Delete additional (spurious) $LANG=...$ prefixes and any text that follows
    ix = answer.find(LANG_MACRO)
    if ix >= 0:
        answer = answer[0:ix].strip()
    return locale, answer


LANGUAGE_NAMES: Mapping[str, str] = {
    "is_IS": "Icelandic",
    "en_US": "English",
    "pl_PL": "Polish",
}


def summarize(text: str, languages: Iterable[str]) -> Dict[str, str]:
    """Summarize the given text in Icelandic and English using the GPT model"""
    # Compose a one-shot guidance prompt for GPT
    examples = ", ".join(
        f'"{lang}": "{{{LANGUAGE_NAMES.get(lang, lang)} summary}}"'
        for lang in languages
    )
    query = (
        f"The following text is a news article that is probably in Icelandic:\n\n"
        f"---\n\n{text}\n\n---\n\n"
        "Summarize the article in each of the languages indicated, "
        "in 3 sentences or less for each language. "
        "Output the summaries in JSON, like so:"
        f"\n\n{{ {examples} }}\n\n"
    )
    response = Completion.create_from_preamble_and_history(
        system="You are an expert at summarizing text in multiple languages.",
        query=query,
        max_tokens=500,
        temperature=0.0,
    )
    try:
        choice = response["choices"][0]
        answ = json.loads(choice["message"]["content"].strip())
        return answ
    except Exception:
        return dict()  # No answer from GPT model: No summary available
