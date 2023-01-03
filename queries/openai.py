"""

    Greynir: Natural language processing for Icelandic

    News query response module

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


    This module handles queries by feeding them into OpenAI's GPT-3 API.

"""

import os
import json
import openai
import logging

from queries.util import gen_answer


PRIORITY = 1000


PROMPT = """
You are a highly competent Icelandic-language voice assistant named
Embla. You have been developed to answer all manner of questions in a
factually accurate way to the very best of your abilities. If you are
in doubt as to the answer, you reply in Icelandic saying you
do not know.

You are presented with the following query in Icelandic:

'{}'

And you answer in Icelandic: 


"""


def handle_plain_text(q) -> bool:
    """Handle plain text query."""
    ql = q.query

    print("OpenAI query: " + ql)
    openai_query = PROMPT.format(ql)

    try:
        openai.api_key = os.getenv("OPENAI_API_KEY")
        r = openai.Completion.create(
            model="text-davinci-003", prompt=openai_query, max_tokens=200, temperature=0
        )

        r = json.loads(str(r))

        print(r)

        answ = r["choices"][0]["text"].strip()
        q.set_answer(*gen_answer(answ))
    except Exception as e:
        logging.error("OpenAI error: " + str(e))
        return False
    return True
