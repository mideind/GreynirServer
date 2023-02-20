"""

    Greynir: Natural language processing for Icelandic

    OpenAI GPT response module

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


    This module handles queries by feeding them into OpenAI's GPT API.

"""

import re
from typing import Any, Dict, List, Optional, cast
from typing_extensions import TypedDict

import os
import json
import copy
import logging
from datetime import datetime

import openai

from queries import Query
from speech.trans.num import numbers_to_ordinal, years_to_text


class StateDict(TypedDict):
    """The state passed to the GPT model as a part of the prompt"""

    client_name: str
    date_iso_utc: str
    time_iso_utc: str
    weekday: Dict[str, str]
    location: str
    timezone: str
    locale: str


class OpenAiChoiceDict(TypedDict):
    """The 'choices' part of the GPT model response"""

    text: str
    finish_reason: str


class OpenAiDict(TypedDict):
    """The GPT model response"""

    choices: List[OpenAiChoiceDict]
    id: str
    model: str
    object: str


class HistoryDict(TypedDict):
    """A single history item"""

    q: str
    a: str


# The list of previous Q/A pairs
HistoryList = List[HistoryDict]

# Max number of previous queries (history) to include in the prompt
MAX_HISTORY_LENGTH = 4

# The relative priority of this query processor module
PRIORITY = 1000

# Set the OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY") or ""

# GPT model to use
MODEL = os.getenv("OPENAI_MODEL") or "text-davinci-003"

# Help the model verbalize weekday names in Icelandic
WEEKDAY = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
VIKUDAGUR = [
    "mánudagur",
    "þriðjudagur",
    "miðvikudagur",
    "fimmtudagur",
    "föstudagur",
    "laugardagur",
    "sunnudagur",
]

# The preamble and prompt template for the GPT model
PROMPT = """
You are a highly competent Icelandic-language voice assistant named Embla.
You have been developed by the company Miðeind to answer all manner of questions
in a factually accurate way to the very best of your abilities. You are always
courteous and helpful. If you are in doubt as to the answer, or don't think
you can answer in a courteous and helpful way, you should reply in Icelandic saying
you do not know or cannot answer.

Your state (in JSON):

```
{state}
```

If asked for a number, answer with no more than four digits after the decimal point.

You should *always* answer in Icelandic, unless the question *explicitly* requests
a reply in another language or a translation to another language.
If you reply in another language, prefix your reply with
$LANG={{language_code}}$, for example $LANG=en_US$ for English.
Avoid mixing languages in the same reply.

{history}
Q: "{query}"
A: "
"""


class Completion:
    @classmethod
    def create(cls, *args: Any, **kwargs: Any) -> Any:
        """
        Creates a new completion while handling formatting and parsing.
        """
        kwargs = copy.deepcopy(kwargs)
        if not "stop" in kwargs:
            kwargs["stop"] = []
        elif isinstance(kwargs["stop"], str):
            kwargs["stop"] = [kwargs["stop"]]
        assert type(kwargs["stop"]) == list, "stop must be a string or list of strings"
        for stop in ["<|im_end|>", "<|diff_marker|>"]:
            if not stop in kwargs["stop"]:
                kwargs["stop"].append(stop)
        assert len(kwargs["stop"]) <= 4, "can only specify up to 4 stop strings"
        raw_prompt = kwargs.get("prompt", "")
        formatted_prompt = (
            "<|im_start|>user<|im_sep|>"
            + raw_prompt
            + "<|im_end|><|im_start|>assistant<|im_sep|>"
        )
        formatted_prompt += kwargs.get("start", "")
        kwargs["prompt"] = formatted_prompt
        return cast(Any, openai).Completion.create(*args, **kwargs)


def _client_name(q: Query) -> str:
    """Obtain the client's (user's) name, if known"""
    nd = q.client_data("name")
    if not nd:
        return "[unknown]"
    return str(nd.get("first", "")) or str(nd.get("full", "")) or "[unknown]"


def handle_plain_text(q: Query) -> bool:
    """Pass a plain text query to GPT and return the response"""
    try:
        if not openai.api_key:
            raise ValueError("Missing OpenAI API key")

        ql = q.query
        now = datetime.now()
        now_iso = now.isoformat()
        wd = now.weekday()  # 0=Monday, 6=Sunday
        # Obtain the history of previous Q/A pairs, if any
        ctx = q.fetch_context()
        history_list = cast(HistoryList, [] if ctx is None else ctx.get("history", []))
        # Include a limited number of previous queries in the history,
        # to keep the prompt within reasonable limits
        history_list = history_list[-MAX_HISTORY_LENGTH:]
        # Format previous (query, answer) pairs to conform to the prompt format
        history = "\n".join(
            [
                f'Q: "{h["q"]}"\nA: "{h["a"]}"\n'
                for h in history_list
                if "q" in h and "a" in h
            ]
        )
        # Assemble the current query state
        state: StateDict = {
            "client_name": _client_name(q),  # The name of the user, if known
            "location": "Reykjavík",  # !!! TODO
            "date_iso_utc": now_iso[0:10],  # YYYY-MM-DD
            "weekday": {"en_US": WEEKDAY[wd], "is_IS": VIKUDAGUR[wd]},
            "time_iso_utc": now_iso[11:16],  # HH:MM
            "timezone": "UTC+0",  # !!! TODO
            "locale": "is_IS",
        }
        # Create the prompt for the GPT model
        prompt = PROMPT.format(
            query=ql, state=json.dumps(state, ensure_ascii=False), history=history
        )
        print(f"GPT model: {MODEL}\nPrompt:\n{prompt}")

        # Submit the prompt to the GPT model for completion
        r = Completion.create(
            engine=MODEL, prompt=prompt, max_tokens=256, temperature=0.0,
        )

        if r is not None:
            r = cast(Optional[OpenAiDict], json.loads(str(r)))
        if r is None:
            raise ValueError("GPT returned no response")

        print(r)

        # Extract the answer from the GPT response JSON
        answ = r["choices"][0]["text"].strip('" \n')
        # Use regex to extract language code from $LANG=...$ prefix, if present
        regex = r"\$LANG=([a-z]{2}_[A-Z]{2})\$(.*)"
        m = re.match(regex, answ)
        locale = None
        if m:
            # A language code is specified:
            # set the voice synthesizer locale accordingly
            answ = m.group(2).strip()
            locale = m.group(1)
            q.set_voice_locale(locale)
        # Delete additional (spurious) $LANG=...$ prefixes and any text that follows
        ix = answ.find("$LANG=")
        if ix >= 0:
            answ = answ[0:ix].strip()
        if not answ:
            # No answer generated
            return False
        # Set the answer type and content
        q.set_qtype("gpt")
        if locale is None or locale == "is_IS":
            # Compensate for deficient normalization in Icelandic speech synthesizer:
            # Convert years and ordinals to Icelandic text
            voice_answer = years_to_text(answ, allow_three_digits=False)
            voice_answer = numbers_to_ordinal(voice_answer, case="þf")
            voice_answer = voice_answer.replace("%", " prósent")
        else:
            # Not Icelandic:
            # Trust the voice synthesizer to do the normalization
            voice_answer = answ
        # Set the query answer text and voice synthesis text
        q.set_answer(dict(answer=answ), answ, voice_answer)
        # Append the new (query, answer) tuple to the history in the context
        history_list.append(
            {"q": ql, "a": answ if locale is None else f"$LANG={locale}$ {answ}"}
        )
        q.set_context(dict(history=history_list))

    except Exception as e:
        logging.error(f"GPT error: {e}")
        return False

    return True
