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

from typing import Any, List, Optional, cast
from typing_extensions import TypedDict

import os
import json
import copy
import logging
from datetime import datetime

import openai

from queries import Query
from queries.util import gen_answer


PRIORITY = 1000
MODEL = os.getenv("OPENAI_MODEL") or "text-davinci-003"

openai.api_key = os.getenv("OPENAI_API_KEY") or ""


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
            "<|im_start|>user<|im_sep|>" + raw_prompt + "<|im_end|><|im_start|>assistant<|im_sep|>"
        )
        formatted_prompt += kwargs.get("start", "")
        kwargs["prompt"] = formatted_prompt
        return cast(Any, openai).Completion.create(*args, **kwargs)


class StateDict(TypedDict):
    client_name: str
    timestamp: str
    weekday: str
    location: str


class OpenAiChoiceDict(TypedDict):
    text: str


class OpenAiDict(TypedDict):
    choices: List[OpenAiChoiceDict]


PROMPT = """
You are a highly competent Icelandic-language voice assistant named
Embla. You have been developed to answer all manner of questions in a
factually accurate way to the very best of your abilities. You are always
courteous and helpful. If you are in doubt as to the answer, or don't think
you can answer in a courteous and helpful way, you reply
in Icelandic saying you do not know.

Your state is as follows (expressed in JSON):

```
{state}
```

Always answer in Icelandic, unless the query explicitly asks for
a reply in another language or a translation to another language.
If you reply in another language, prefix your reply with
$LANG={{language_code}}$, for example $LANG=en$ for English.

Q: "{query}"
A: "
"""

def _client_name(q: Query) -> str:
    nd = q.client_data("name")
    if not nd:
        return "[unknown]"
    return str(nd.get("first", "")) or str(nd.get("full", "")) or "[unknown]"


def handle_plain_text(q: Query) -> bool:
    """Handle plain text query"""
    try:
        if not openai.api_key:
            raise ValueError("Missing OpenAI API key")

        ql = q.query
        now = datetime.now()
        weekday = now.strftime("%A")

        state: StateDict = {
            "client_name": _client_name(q),
            "timestamp": now.isoformat(),
            "weekday": weekday,
            "location": "Reykjavík",
        }
        prompt = PROMPT.format(query=ql, state=json.dumps(state, ensure_ascii=False))
        print(f"OpenAI model: {MODEL}\nPrompt:\n{prompt}")

        # r = Completion.create(
        r = cast(Any, openai).Completion.create(
            # model=MODEL,
            # engine=MODEL,
            model="text-davinci-003",
            prompt=prompt,
            max_tokens=256,
            temperature=0.2,
        )

        r = cast(Optional[OpenAiDict], json.loads(str(r)))
        if r is None:
            raise ValueError("OpenAI returned no response")

        print(r)

        answ = r["choices"][0]["text"].strip('" \n')
        q.set_answer(*gen_answer(answ))

    except Exception as e:
        logging.error(f"OpenAI error: {e}")
        return False
    return True
