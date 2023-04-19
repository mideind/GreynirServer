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

from __future__ import annotations

from typing import (
    Any,
    Dict,
    Iterable,
    Mapping,
    Optional,
    Set,
    Tuple,
    Type,
    Union,
    cast,
)
from typing_extensions import TypedDict, NotRequired

import abc
import inspect
import os
import re
import json
import logging
from datetime import datetime

import straeto  # type: ignore
from iceweather import forecast_text  # type: ignore

from queries import Query
from queries.currency import fetch_exchange_rates
from queries.userloc import locality_and_country
from settings import Settings
from speech.trans import gssml
from speech.trans.num import numbers_to_ordinal, years_to_text
from queries.util.openai_gpt import (
    OPENAI_KEY_PRESENT,
    jdump,
    detect_language,
    HistoryList,
    OpenAiDict,
    Completion,
)


class LocationDict(TypedDict):
    """The 'location' part of the state passed to the GPT model"""

    city_and_country: str
    lat: NotRequired[float]
    lon: NotRequired[float]


class StateDict(TypedDict):
    """The state passed to the GPT model as a part of the prompt"""

    user_name: str
    date_iso_utc: str
    time_iso_utc: str
    weekday: Dict[str, str]
    location: LocationDict
    timezone: str
    locale: str


MacroResultType = Optional[Tuple[str, Dict[str, Union[str, int, float]]]]
AgentClass = Optional[Type["FollowUpAgent"]]

# Max number of previous queries (history) to include in the prompt
MAX_HISTORY_LENGTH = 4

# Max number of question/answer turns to allow when answering a single question
MAX_TURNS = 2

# The relative priority of this query processor module
# This special constant indicates that this module is
# the fallback handler of last resort for queries
PRIORITY = "LAST_RESORT"

GPT_LIMIT = int(os.environ.get("GPT_LIMIT", 15)) # Max number of GPT-4 queries to allow per client
GPT_LIMIT_ANSWER = f"Því miður get ég aðeins svarað að hámarki {GPT_LIMIT} spurningum frá þér með hjálp GPT-4."
GPT_LIMIT_ANSWER_VOICE = f"Því miður get ég aðeins svarað að hámarki {gssml(GPT_LIMIT, type='number', gender='kvk', case='þgf')} spurningum frá þér með hjálp gé pé té fjögur."

# Stuff that needs replacement in the voice output, as the Icelandic
# voice synthesizer does not pronounce them correctly
REPLACE: Mapping[str, str] = {
    "t.d.": "til dæmis",
    "m.a.": "meðal annars",
    "o.s.frv.": "og svo framvegis",
    "þ.e.": "það er",
    ";": "",
    ":": "",
    "%": " prósent",
    "°": " gráður",
    "m/s": "metrar á sekúndu",
    "km/klst": "kílómetrar á klukkustund",
    " ml ": " millilítrar ",
    "  ": " ",
}
REPLACE_REGEX = "|".join(map(re.escape, REPLACE.keys()))

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

CALL_MACRO = "$CALL="
CALL_MACRO_LENGTH = len(CALL_MACRO)

AGENT_SUFFIX = "Agent"
AGENT_SUFFIX_LENGTH = len(AGENT_SUFFIX)
AGENTS_DISABLED = True  # !!! FIXME: DEMO/DEBUG

SYSTEM_PREAMBLE = """
You are a highly competent Icelandic-language voice assistant named Embla.
You have been developed by the company Miðeind to answer the user's questions
in a factually accurate and succinct way to the very best of your abilities.
You are always courteous and helpful.
You reply with short and clear answers that are no longer than one paragraph.
You avoid long explanations.
"""

# Optional, for normalization (does not work particularly well):
""" Always replace numbers, measurement units and acronyms with their
fully spelled-out text counterparts. For example, say "sautján hundruð þrjátíu og átta komma fimm"
instead of "1738,5", "metrar á sekúndu" instead of "m/s", "kílómetrar á klukkustund"
instead of "km/klst", "til dæmis" instead of "t.d." and "og svo framvegis" instead of
"o.s.frv.".
"""

# The preamble template for the GPT model
INITIAL_PREAMBLE = """
If you are in doubt as to the answer, or don't
think you can answer in a courteous and helpful way, you should reply in Icelandic saying
you do not know or cannot answer. Do your best to interpret the user's questions according
to their likely intent.

Your state (in JSON):

```
{state}
```

{agents}
If asked for a number, answer with no more than four digits after the decimal comma.
Never reveal the names of your plug-in modules or macros to the user.

You should *always* answer in Icelandic (locale is_IS), unless the question
*explicitly* requests a reply in a supported language or a translation to
a supported language. Supported languages are English, German, French,
Spanish, Polish, Swedish, Danish and Norwegian.

If your answer is not in Icelandic, prefix it with the macro
`$LANG={{language_code}}$`, for example `$LANG=en_US$` for English.
Avoid mixing languages in the same answer.
"""

AGENTS_PREAMBLE = """
When asked questions on certain special subjects, do *not* reply with
your own answer. Instead, generate a call to a plug-in module that
corresponds to the subject, from the list below:

{agent_directory}

To answer a question by calling a plug-in module, output the special macro

`$CALL={{module.__name__}}.query({{json}})$`

instead of a normal text anwer. In the call, `json` contains the known
parameters of the query.\n
"""


def _client_name(q: Query) -> str:
    """Obtain the client's (user's) name, if known"""
    nd = q.client_data("name")
    if not nd:
        return "[unknown]"
    return str(nd.get("first", "")) or str(nd.get("full", "")) or "[unknown]"


class AgentBase(abc.ABC):

    """Abstract base class for agent (completion) classes"""

    _registry: Dict[str, Type[FollowUpAgent]] = dict()

    def __init__(
        self, q: Query, ql: str, state: StateDict, history_list: HistoryList
    ) -> None:
        super().__init__()
        self._q = q
        self._ql = ql
        self._state = state
        self._history_list = history_list

    @classmethod
    def module_name(cls) -> str:
        """Return the module name associated with this class"""
        raise NotImplementedError

    @classmethod
    def get(cls, name: str) -> AgentClass:
        """Return the completion class with the given name"""
        return AgentBase._registry.get(name)

    @classmethod
    def agents(cls) -> Iterable[Type[FollowUpAgent]]:
        """Return all follow-up completion classes"""
        return AgentBase._registry.values()

    @staticmethod
    def answer_from_gpt_response(response: Any) -> str:
        """Utility function to extract the answer from a GPT response"""
        r: Optional[OpenAiDict] = None
        if response is not None:
            r = json.loads(str(response))
        if r is None:
            return ""
        if Settings.DEBUG:
            print(r)  # !!! DEBUG
        # Extract the answer from the GPT response JSON
        try:
            answer = r["choices"][0]["message"]["content"].strip('" \n\r\t')
            return answer
        except (ValueError, KeyError, IndexError):
            # Something is wrong with the GPT response format
            return ""

    @abc.abstractmethod
    def submit(self) -> Tuple[str, AgentClass]:
        """Submits the completion to the GPT model. Returns the
        answer and the name of a completion class that should handle
        the next turn in the conversation with GPT. If the class is
        empty, the answer is final."""
        raise NotImplementedError()


class InitialAgent(AgentBase):

    """Models the initial prompt and completion for a user's question"""

    # Cached preamble with a directory of available follow-up agents
    _agents = ""

    @classmethod
    def _create_agent_directory(cls) -> None:
        """Create a string by concatenating a short description
        of each available follow-up agent class"""
        d = "".join(agent.directory_entry() for agent in AgentBase.agents())
        cls._agents = AGENTS_PREAMBLE.format(agent_directory=d) if d else ""

    def __init__(
        self, q: Query, ql: str, state: StateDict, history_list: HistoryList
    ) -> None:
        super().__init__(q, ql, state, history_list)
        if not AGENTS_DISABLED:
            if not self._agents:
                # Assemble a preamble with a directory of
                # available follow-up agents and cache it
                InitialAgent._create_agent_directory()

    def _extract_follow_up_agent(self, answer: str) -> Tuple[str, AgentClass]:
        """Extract the name of a follow-up agent from the answer, if any"""
        call_macro_index = answer.find(CALL_MACRO)
        if call_macro_index < 0:
            # The answer does not contain a CALL macro
            return answer, None
        # Pick out the module name and parameters
        cut = answer[call_macro_index + CALL_MACRO_LENGTH :]
        end = cut.rfind(")$")
        if end < 0:
            return "", None  # Something wrong: Unable to answer
        cut = cut[: end + 1]  # Include the closing parenthesis
        arg = cut.split(".", maxsplit=1)
        if Settings.DEBUG:
            print(arg)
        if len(arg) != 2:
            return "", None  # Something wrong: Unable to answer
        module_name = arg[0]
        if module_name.startswith("{"):
            # GPT is probably talking about itself, which it should not do
            return "", None
        parameter = arg[1]
        if parameter.startswith("py."):
            # Fix GPT misunderstanding which sometimes occurs
            parameter = parameter[3:]
        parameter = parameter[len("query") + 1 : -1]
        # Convert module name to agent name
        if Settings.DEBUG:
            print(module_name, parameter)
        agent_class = AgentBase.get(module_name)
        return parameter, agent_class

    def submit(self) -> Tuple[str, AgentClass]:
        """Obtains an initial completion from GPT for a question"""
        # Assemble the prompt
        preamble = INITIAL_PREAMBLE.format(
            state=jdump(self._state), agents=self._agents
        )

        # Submit the prompt, comprised of the preamble,
        # the conversation history and the query,
        # to the GPT model for completion
        r = Completion.create_from_preamble_and_history(
            system=SYSTEM_PREAMBLE,
            preamble=preamble,
            history_list=self._history_list,
            query=self._ql,
            max_tokens=320,
            temperature=0.1,
        )

        # Extract the answer from the GPT response
        answer = self.answer_from_gpt_response(r)

        # Return the agent that should follow up on this answer, if any
        return self._extract_follow_up_agent(answer)


class FollowUpAgent(AgentBase):

    """Models a follow-up completion for a question.
       Derived classes should adhere to the following protocol:
    *  The class name should be the name of the pseudo-module that
       implements the follow-up completion, plus the word 'Agent'.
       Example: BusAgent -> module 'bus'.
    *  The class docstring should contain a short description
       of the types of query that this agent can handle.
    *  The class should have a method called 'query'
       that takes a single argument, a dictionary of parameters,
       and returns a string that contains the information to be
       submitted to the GPT model in a second prompt to generate
       a final answer. This string is usually an object formatted in JSON.
    *  The class should have a class method called 'parameter_json'
       that returns a JSON string describing the parameters
       of the 'query' method.
    """

    def __init__(
        self,
        q: Query,
        ql: str,
        state: StateDict,
        history_list: HistoryList,
        answer: str,
    ) -> None:
        super().__init__(q, ql, state, history_list)
        self._answer = answer

    def __init_subclass__(cls, **kwargs: Any):
        """Keep a registry of all concrete (non-abstract) follow-up completion classes"""
        super().__init_subclass__(**kwargs)
        if not inspect.isabstract(cls):
            cls._registry[cls.module_name()] = cls

    @abc.abstractmethod
    def query(self, parameters: Dict[str, Any]) -> str:
        """Queries the module for a follow-up completion"""
        raise NotImplementedError()

    @classmethod
    def parameter_json(cls) -> str:
        """Return a JSON string describing the parameters for this
        follow-up completion class"""
        raise NotImplementedError()

    @classmethod
    def directory_entry(cls) -> str:
        """Return a string describing this class for inclusion in the
        initial prompt"""
        return (
            f"* `{cls.module_name()}.py`: {cls.__doc__}\n"
            f"  Parameter JSON: `{cls.parameter_json()}`\n"
        )

    @classmethod
    def module_name(cls) -> str:
        """Convert an agent class name to a 'pseudo-module' name"""
        # For instance, BusAgent -> "bus"
        n = cls.__name__
        if not n.endswith(AGENT_SUFFIX):
            raise ValueError(f"Invalid agent class name: {n}")
        return n[:-AGENT_SUFFIX_LENGTH].lower()

    # By default, we store the final answer of a follow-up module
    # in the chat history. This is not always desirable, for instance
    # in the currency module, where the answer may tempt GPT into
    # using that as a basis instead of a new currency query.
    _ADD_INTERMEDIATE_ANSWER_TO_HISTORY = False

    # The query template is overridable in derived classes
    query_template = (
        "\nYour state is\n```\n{state}\n```\n"
        "Your information is\n```\n{result}\n```\n"
        "Answer the user's question below *in Icelandic* "
        "using the information.\n\n"
        "{query}"
    )

    def submit(self) -> Tuple[str, AgentClass]:
        """Submits a follow-up completion to GPT"""
        parameters = json.loads(self._answer)
        result = self.query(parameters)
        # Assemble the prompt
        query = self.query_template.format(
            state=jdump(self._state), result=result, query=self._ql,
        )
        # Submit the prompt to the GPT model for completion
        # Here, there is no history list - this is an independent query
        r = Completion.create_from_preamble_and_history(
            system=SYSTEM_PREAMBLE, query=query, max_tokens=256, temperature=0.0,
        )
        answer = self.answer_from_gpt_response(r)
        return answer, None  # By default, there's no further follow-up


class BusAgent(FollowUpAgent):

    """Bus stops, bus numbers, bus schedules and arrival times"""

    @classmethod
    def parameter_json(cls) -> str:
        """Return a JSON string describing the parameters for this
        follow-up completion class"""
        return jdump(
            {
                "query": "bus_numbers|nearest_stop|arrival_time",
                "bus": "bus number",
                "stop": "stop name",
                "nearest_stop": {
                    "location": "location name",
                    "lat": "latitude",
                    "lon": "longitude",
                },
            }
        )

    def query(self, parameters: Dict[str, Any]) -> str:
        """Queries the bus module for a follow-up completion"""
        stop_name = parameters.get("stop", "")
        qtype = parameters.get("query", "")
        # bus_number = parameters.get("bus", "")
        # nearest_stop = parameters.get("nearest_stop", {})
        stops = straeto.BusStop.named(stop_name, fuzzy=True) if stop_name else []
        location = self._q.location
        if location:
            if stops:
                cast(Any, straeto).BusStop.sort_by_proximity(stops, self._q.location)
            else:
                stops = straeto.BusStop.closest_to_list(
                    location, n=2, within_radius=0.4
                )
                if not stops:
                    # This will fetch the single closest stop, regardless of distance
                    stops = [
                        cast(straeto.BusStop, straeto.BusStop.closest_to(location))
                    ]
        if stops:
            stop = stops[0]
            routes: Set[str] = set()
            route_id: str
            for route_id in cast(Any, stop).visits.keys():
                route = straeto.BusRoute.lookup(route_id)
                if route is not None:
                    routes.add(route.number)
            reply = dict(stop=stop.name, routes=list(routes))
        else:
            # Unable to fill in further information; return the original parameters
            reply = parameters.copy()
        if qtype:
            reply["query"] = qtype
        return f"{reply}"


class WeatherAgent(FollowUpAgent):

    """Weather information and forecasts"""

    @classmethod
    def parameter_json(cls) -> str:
        """Return a JSON string describing the parameters for this
        follow-up completion class"""
        return jdump(
            {
                "query": "current|forecast",
                "time": "ISO datetime",
                "location": "location name",
            }
        )

    def query(self, parameters: Dict[str, Any]) -> str:
        """Queries the weather module for a follow-up completion"""
        res: Dict[str, Any] = forecast_text(2)
        try:
            txt: str = res["results"][0]["content"]
        except (KeyError, IndexError):
            raise ValueError("Unable to fetch weather information")
        reply = parameters.copy()
        reply["text"] = txt
        return f"{reply}"


class CurrencyAgent(FollowUpAgent):

    """Currency exchange rates"""

    @classmethod
    def parameter_json(cls) -> str:
        """Return a JSON string describing the parameters for this
        follow-up completion class"""
        return jdump(
            {
                "from_currency": "currency code",
                "to_currency": "currency code",
                "amount": "amount",
            }
        )

    _ADD_INTERMEDIATE_ANSWER_TO_HISTORY = True

    _PROMPT = (
        "\nCurrency rates versus the ISK are as follows:\n```\n{result}\n```\n"
        "Answer the user's question below *in Icelandic* "
        "using the rates. You may need to think step by step to "
        "calculate rates between two currencies if neither of them is the ISK. "
        "In that case, you can convert one of them to ISK first, and then from "
        "ISK to the other. For example, if USD_ISK is 144, and EUR_ISK is 155, "
        "EUR_USD is 155 / 144 = 1.07638.\n\n"
        "{query}"
    )

    def query(self, parameters: Dict[str, Any]) -> str:
        """Queries the currency module for a follow-up completion"""
        json = fetch_exchange_rates()
        if json is None:
            raise ValueError("Unable to fetch exchange rates")
        reply = parameters.copy()
        rates = {f"{k}_ISK": round(v, 6) for k, v in json.items()}
        rates.update({f"ISK_{k}": round(1.0 / v, 6) for k, v in json.items()})
        reply["rates"] = rates
        return f"{reply}"


class NewsAgent(FollowUpAgent):

    """Current news headlines"""

    @classmethod
    def parameter_json(cls) -> str:
        """Return a JSON string describing the parameters for this
        follow-up completion class"""
        return jdump({"category": "news_category|all",})

    def query(self, parameters: Dict[str, Any]) -> str:
        """Queries the news module for a follow-up completion"""
        category = parameters.get("category", "all")
        return jdump(
            dict(
                category=category,
                headlines=[
                    # Höfundur: Tumi Þorsteinsson, þriggja ára, í miðju COVID-19
                    "Kaffihúsið er bilað",
                    "Bókasafnið er lokað",
                    "Jólin eru búin",
                ],
            )
        )


class PeopleAgent(FollowUpAgent):

    """A database of people, their names, their current titles and roles"""

    @classmethod
    def parameter_json(cls) -> str:
        """Return a JSON string describing the parameters for this
        follow-up completion class"""
        return jdump({"name": "name|[unknown]", "title": "title|[unknown]",})

    def query(self, parameters: Dict[str, Any]) -> str:
        """Queries the people module for a follow-up completion"""
        name = parameters.get("name", "[unknown]")
        title = parameters.get("title", "[unknown]")
        if not name or name == "[unknown]":
            if not title or title == "[unknown]":
                title = "fimm ára strákur"
            return jdump(dict(name="Tumi Þorsteinsson", title=title))
        if not title or title == "[unknown]":
            if not name or name == "[unknown]":
                name = "Tumi Þorsteinsson"
            return jdump(dict(name=name, title="fimm ára strákur"))
        return jdump(dict(name=name, title=title))


def handle_plain_text(q: Query) -> bool:
    """Main entry point into this query module"""
    # Pass a plain text query to GPT and return the response
    try:
        if not q.authenticated or q.private:
            # We only allow GPT functionality for queries that
            # originate from authenticated clients (typically smartphones
            # running Embla) and are not private
            # (because we need the query log to count queries)
            return False
        if not OPENAI_KEY_PRESENT:
            logging.error("Missing OpenAI API key")
            return False

        # Obtain the number of queries already issued by the client
        # for this query type
        n = q.count_queries_of_type("gpt")
        if n > GPT_LIMIT:
            # The client has exceeded the number of queries allowed
            # for this query type
            answer = GPT_LIMIT_ANSWER
            voice_answer = GPT_LIMIT_ANSWER_VOICE
            q.set_answer(dict(answer=answer), answer, voice_answer)
            q.set_key("gpt_limit")
            q.set_qtype("gpt")
            return True

        ql = q.query
        loc = q.location
        now = datetime.utcnow()
        now_iso = now.isoformat()
        wd = now.weekday()  # 0=Monday, 6=Sunday
        location: str = "Óþekkt"
        # Assemble the current query state
        if loc is not None:
            location = locality_and_country(loc) or location
        loc_dict: LocationDict = {"city_and_country": location}
        if loc is not None:
            loc_dict["lat"] = round(loc[0], 4)
            loc_dict["lon"] = round(loc[1], 4)
        state: StateDict = {
            "user_name": _client_name(q),  # The name of the user, if known
            "location": loc_dict,
            "date_iso_utc": now_iso[0:10],  # YYYY-MM-DD
            "weekday": {"en_US": WEEKDAY[wd], "is_IS": VIKUDAGUR[wd]},
            "time_iso_utc": now_iso[11:16],  # HH:MM
            "timezone": "UTC+0",  # !!! TODO
            "locale": "is_IS",
        }
        # Assign a location, if known
        if loc is not None:
            state["location"]["lat"] = round(loc[0], 4)
            state["location"]["lon"] = round(loc[1], 4)

        # Obtain the history of previous Q/A pairs, if any
        ctx = q.fetch_context()
        history_list = cast(HistoryList, [] if ctx is None else ctx.get("history", []))
        # Include a limited number of previous queries in the history,
        # to keep the prompt within reasonable limits
        history_list = history_list[-MAX_HISTORY_LENGTH:]

        # Create the initial completion
        turns = 0
        agent = InitialAgent(q, ql, state, history_list)
        answer, next_agent = agent.submit()

        while answer and next_agent:
            # Create and submit a follow-up prompt
            turns += 1
            if turns >= MAX_TURNS:
                # Too many turns, bail out (repetitive follow-ups)
                return False
            # Create the follow-up completion instance
            agent = next_agent(q, ql, state, history_list, answer)
            answer, next_agent = agent.submit()

        # Process the anwer to fish out any $LANG=...$ prefixes
        locale, answer = detect_language(answer)
        if not answer:
            # No answer generated
            return False
        if "{" in answer or "}" in answer:
            # Some kind of misunderstood query, where
            # the answer probably includes JSON: bail out
            return False
        q.set_qtype("gpt")
        # Set the answer type and content
        if not locale or locale == "is_IS":
            # This is a plain text answer in Icelandic
            # Compensate for deficient normalization in Icelandic speech synthesizer:
            # Replace 'number-number' with 'number til number'
            voice_answer = re.sub(r"(\d+)-(\d+)", r"\1 til \2", answer,)
            # Convert years and ordinals to Icelandic text
            voice_answer = years_to_text(voice_answer, allow_three_digits=False)
            voice_answer = numbers_to_ordinal(voice_answer, case="þf")
            # Replace stuff that doesn't work in the Icelandic speech synthesizer
            voice_answer = re.sub(
                REPLACE_REGEX, lambda m: REPLACE[m.group(0)], voice_answer,
            )
        else:
            # Not Icelandic: signal this to the voice synthesizer
            q.set_voice_locale(locale)
            # Trust the voice synthesizer to do the normalization
            voice_answer = answer
        # Set the query answer text and voice synthesis text
        q.set_answer(dict(answer=answer), answer, voice_answer)
        duration = datetime.utcnow() - now
        duration_str = f" ({duration.total_seconds():.1f} s)" if Settings.DEBUG else ""
        q.set_source(
            f"Takist með fyrirvara! {n + 1}/{GPT_LIMIT}{duration_str}"
        )

        # Append the new (query, answer) tuple to the history in the context
        history_list.append(
            {"q": ql, "a": f"$LANG={locale}$ {answer}" if locale else answer}
        )
        q.set_context(dict(history=history_list))

    except Exception as e:
        logging.error(f"GPT error: {e}")
        return False

    return True
