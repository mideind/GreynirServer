import json
from typing import Any, Dict, Union, List, Optional, cast
from typing_extensions import TypedDict

import os.path
import datetime
import yaml

# try:
#     import tomllib
# except ModuleNotFoundError:
#     import tomli as tomllib
from enum import IntEnum, auto
from dataclasses import dataclass

from tree import Result
from query import Query, ClientDataDict
from reynir import NounPhrase
from queries import natlang_seq, sing_or_plur

# Global key for storing client data for dialogues
DIALOGUE_KEY = "dialogue"
DIALOGUE_DATA_KEY = "dialogue_data"
EMPTY_DIALOGUE_DATA = "{}"

ResourceType = Union[str, int, float, bool, datetime.datetime, None]
ListResourceType = List[ResourceType]


class DialogueStructureType(TypedDict):
    """ """

    dialogue_name: str
    resources: List["Resource"]


class ResourceState(IntEnum):
    """Enum representing the different states a dialogue resource can be in."""

    UNFULFILLED = auto()
    PARTIALLY_FULFILLED = auto()
    FULFILLED = auto()
    CONFIRMED = auto()
    # SKIPPED = auto()


def load_dialogue_structure(filename: str) -> Any:
    """Loads dialogue structure from YAML file."""
    basepath, _ = os.path.split(os.path.realpath(__file__))
    fpath = os.path.join(basepath, filename, filename + ".yaml")  # TODO: Fix this
    obj = None
    with open(fpath, mode="r") as file:
        obj = yaml.safe_load(file)
    return obj


def list_items(items: Any) -> str:
    item_list: List[str] = []
    for num, name in items:
        # TODO: get general plural form
        plural_name: str = NounPhrase(name).dative or name
        item_list.append(sing_or_plur(num, name, plural_name))
    return natlang_seq(item_list)


class DialogueStateManager:
    def __init__(self, dialogue_name: str, query: Query, result: Result):
        self._dialogue_name = dialogue_name
        self._q = query
        self._result = result
        self._saved_state = self._get_saved_dialogue_state()

    def not_in_dialogue(self, start_dialogue_qtype: str) -> bool:
        """Check if the client is in or wants to start this dialogue"""
        qt = self._result.get("qtype")
        return (
            qt != start_dialogue_qtype
            and self._saved_state.get("dialogue_name") != self._dialogue_name
        )

    def setup_dialogue(self):
        obj = load_dialogue_structure(self._dialogue_name)
        print(obj)
        self.resources: List[Resource] = []
        for i, resource in enumerate(obj["resources"]):
            newResource: Resource
            if resource.get("type") == "ListResource":
                newResource = ListResource(**resource)
            else:
                print(resource)
                newResource = DatetimeResource(**resource)
            if self._saved_state and i < len(self._saved_state["resources"]):
                newResource.update(self._saved_state["resources"][i])
                newResource.state = ResourceState(
                    self._saved_state["resources"][i].state
                )
            self.resources.append(newResource)

        self.resourceState: Optional[Resource] = None
        self.ans: Optional[str] = None

    def start_dialogue(self):
        """Save client's state as having started this dialogue"""
        self.set_dialogue_state(
            {
                "dialogue_name": self._dialogue_name,
                "resources": [],
            }
        )

    def update_dialogue_state(self):
        """Update the dialogue state for a client"""
        self.set_dialogue_state(
            {
                "dialogue_name": self._dialogue_name,
                "resources": self.resources,
            }
        )
        # self.set_dialogue_state()

    def generate_answer(self, result: Result) -> str:
        for resource in self.resources:
            if resource.required and resource.state is not ResourceState.CONFIRMED:
                if "callbacks" in result:
                    for cb in result.callbacks:
                        cb(resource, result)
                    if (
                        resource.state is ResourceState.CONFIRMED
                        and resource != self.resources[-1]
                    ):
                        continue
                return resource.generate_answer()
        return "Upp kom villa, reyndu aftur."

    def _get_saved_dialogue_state(self) -> DialogueStructureType:
        """Load the dialogue state for a client"""
        cd = self._q.client_data(DIALOGUE_KEY)
        # Return empty DialogueStructureType in case no dialogue state exists
        ds: DialogueStructureType = {
            "dialogue_name": "",
            "resources": [],
        }
        if cd:
            ds_str = cd.get(DIALOGUE_DATA_KEY)
            if isinstance(ds_str, str) and ds_str != EMPTY_DIALOGUE_DATA:
                # TODO: Add try-except block
                ds = json.loads(ds_str, cls=DialogueJSONDecoder)
        return ds

    def set_dialogue_state(self, ds: DialogueStructureType) -> None:
        """Save the state of a dialogue for a client"""
        ds_json: str = json.dumps(ds, cls=DialogueJSONEncoder)
        # Wrap data before saving dialogue state into client data
        # (due to custom JSON serialization)
        cd = {DIALOGUE_DATA_KEY: ds_json}
        self._q.set_client_data(DIALOGUE_KEY, cast(ClientDataDict, cd))

    def end_dialogue(self) -> None:
        """End the client's current dialogue"""
        # TODO: Remove line from database?
        self._q.set_client_data(DIALOGUE_KEY, {DIALOGUE_DATA_KEY: EMPTY_DIALOGUE_DATA})


class DialogueJSONEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        # Add JSON encoding for any new Resource classes here!
        # CUSTOM RESOURCE CLASSES

        # BASE RESOURCE CLASSES
        if isinstance(o, ListResource):
            d = o.__dict__.copy()
            d["__type__"] = "ListResource"
            return d
        if isinstance(o, YesNoResource):
            d = o.__dict__.copy()
            d["__type__"] = "YesNoResource"
            return d
        if isinstance(o, DatetimeResource):
            d = o.__dict__.copy()
            d["__type__"] = "DatetimeResource"
            return d
        if isinstance(o, NumberResource):
            d = o.__dict__.copy()
            d["__type__"] = "NumberResource"
            return d
        if isinstance(o, datetime.date):
            return {
                "__type__": "date",
                "year": o.year,
                "month": o.month,
                "day": o.day,
            }
        if isinstance(o, datetime.time):
            return {
                "__type__": "time",
                "hour": o.hour,
                "minute": o.minute,
                "second": o.second,
                "microsecond": o.microsecond,
            }
        if isinstance(o, Resource):
            d = o.__dict__.copy()
            d["__type__"] = "Resource"
            return d
        return json.JSONEncoder.default(self, o)


class DialogueJSONDecoder(json.JSONDecoder):
    def __init__(self, *args: Any, **kwargs: Any):
        json.JSONDecoder.__init__(
            self, object_hook=self.dialogue_decoding, *args, **kwargs
        )

    def dialogue_decoding(self, d: Dict[Any, Any]) -> Any:
        if "__type__" not in d:
            return d
        t = d.pop("__type__")
        if t == "ListResource":
            return ListResource(**d)
        if t == "YesNoResource":
            return YesNoResource(**d)
        if t == "DatetimeResource":
            return DatetimeResource(**d)
        if t == "NumberResource":
            return NumberResource(**d)
        if t == "date":
            return datetime.date(**d)
        if t == "time":
            return datetime.time(**d)
        if t == "Resource":
            return Resource(**d)


@dataclass
class Resource:
    name: str = ""
    required: bool = True
    data: Any = None
    state: ResourceState = ResourceState.UNFULFILLED
    prompt: str = ""
    type: str = ""
    repeatable: bool = False
    repeat_prompt: Optional[str] = None
    confirm_prompt: Optional[str] = None
    cancel_prompt: Optional[str] = None
    _repeat_count: int = 0

    def next_action(self) -> Any:
        raise NotImplementedError()

    def generate_answer(self) -> str:
        raise NotImplementedError()

    def update(self, new_data: Optional["Resource"]) -> None:
        if new_data:
            self.__dict__.update(new_data.__dict__)


@dataclass
class ListResource(Resource):
    data: Optional[ListResourceType] = None
    available_options: Optional[ListResourceType] = None

    def list_available_options(self) -> str:
        raise NotImplementedError()

    def generate_answer(self) -> str:
        print("State: ", self.state)
        ans: str = ""
        if self.state is ResourceState.UNFULFILLED:
            if self._repeat_count == 0 or not self.repeatable:
                ans = self.prompt
        if self.state is ResourceState.PARTIALLY_FULFILLED:
            if self.repeat_prompt:
                ans = f"{self.repeat_prompt.format(list_items = list_items(self.data))}"
        if self.state is ResourceState.FULFILLED:
            if self.confirm_prompt:
                ans = (
                    f"{self.confirm_prompt.format(list_items = list_items(self.data))}"
                )
        return ans


# TODO:
# ExactlyOneResource (choose one resource from options)
# SetResource (a set of resources)?
# ...


@dataclass
class YesNoResource(Resource):
    data: Optional[bool] = None


@dataclass
class DatetimeResource(Resource):
    data: Optional[List[Union[Optional[datetime.date], Optional[datetime.time]]]] = None
    date_fulfilled_prompt: Optional[str] = None
    time_fulfilled_prompt: Optional[str] = None

    def generate_answer(self) -> str:
        ans = ""
        if self.state is ResourceState.UNFULFILLED:
            if self._repeat_count == 0 or not self.repeatable:
                ans = self.prompt
        if self.state is ResourceState.PARTIALLY_FULFILLED:
            if self.data:
                if len(self.data) > 0 and self.data[0] and self.date_fulfilled_prompt:
                    ans = self.date_fulfilled_prompt.format(
                        date=self.data[0].strftime("%Y/%m/%d")
                    )
                if len(self.data) > 1 and self.data[1] and self.time_fulfilled_prompt:
                    ans = self.time_fulfilled_prompt.format(
                        time=self.data[1].strftime("%H:%M")
                    )
        if self.state is ResourceState.FULFILLED:
            if (
                self.data
                and self.confirm_prompt
                and len(self.data) == 2
                and self.data[0]
                and self.data[1]
            ):
                ans = self.confirm_prompt.format(
                    date_time=datetime.datetime.combine(
                        cast(datetime.date, self.data[0]),
                        cast(datetime.time, self.data[1]),
                    ).strftime("%Y/%m/%d %H:%M")
                )
        if self.state is ResourceState.CONFIRMED:
            ans = "Pöntunin er staðfest."
        return ans


@dataclass
class NumberResource(Resource):
    data: Optional[int] = None


""" Three classes implemented for each resource
    class DataState():
        pass

    class PartiallyFulfilledState():
        pass

    class FulfillState(DataState):
        pass
"""
