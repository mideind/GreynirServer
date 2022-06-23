import json
from typing import Any, Dict, Union, List, Optional, cast
from typing_extensions import TypedDict

from enum import IntEnum, auto
import datetime
from dataclasses import dataclass

from reynir import NounPhrase
from tree import Result
from queries import natlang_seq, sing_or_plur, load_dialogue_structure

BaseResourceTypes = Union[str, int, float, bool, datetime.datetime, None]
ListResourceType = List[BaseResourceTypes]


def list_items(items: Any) -> str:
    item_list: List[str] = []
    for num, name in items:
        # TODO: get general plural form
        plural_name: str = NounPhrase(name).dative or name
        item_list.append(sing_or_plur(num, name, plural_name))
    return natlang_seq(item_list)


class DialogueStructureType(TypedDict):
    """
    A dialogue structure is a list of resources used in a dialogue.
    """

    dialogue_name: str
    variables: Optional[List[Any]]
    resources: List[Dict[Any, Any]]


class ResourceState(IntEnum):
    UNFULFILLED = auto()
    PARTIALLY_FULFILLED = auto()
    FULFILLED = auto()
    CONFIRMED = auto()
    # SKIPPED = auto()


class DialogueStateManager:
    def __init__(
        self, yaml_file: str, saved_state: Optional[DialogueStructureType] = None
    ):
        obj = load_dialogue_structure(yaml_file)
        print(obj)
        self.resources: List[Resource] = []
        for i, resource in enumerate(obj["resources"]):
            newResource: Resource
            if resource.get("type") == "ListResource":
                newResource = ListResource(**resource)
            else:
                print(resource)
                newResource = DatetimeResource(**resource)
            if saved_state and i < len(saved_state["resources"]):
                newResource.__dict__.update(saved_state["resources"][i])
                newResource.state = ResourceState(saved_state["resources"][i]["state"])
            self.resources.append(newResource)

        self.resourceState: Optional[Resource] = None
        self.ans: Optional[str] = None

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

class DialogueJSONEncoder(json.JSONEncoder):
    # TODO: check resource state
    def default(self, o: Any) -> Any:
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
                '__type__' : 'date',
                'year' : o.year,
                'month' : o.month,
                'day' : o.day,
            }
        if isinstance(o, datetime.time):
            return {
                '__type__' : 'time',
                'hour' : o.hour,
                'minute' : o.minute,
                'second' : o.second,
                'microsecond' : o.microsecond,
            }
        if isinstance(o, Resource):
            d = o.__dict__.copy()
            d["__type__"] = "Resource"
            return d
        return json.JSONEncoder.default(self, o)

class DialogueJSONDecoder(json.JSONDecoder):

    def __init__(self, *args: Any, **kwargs: Any):
        json.JSONDecoder.__init__(self, object_hook=self.dialogue_decoding, *args, **kwargs)

    def dialogue_decoding(self, d: Dict[Any, Any]) -> Any:
        if '__type__' not in d:
            return d
        t = d.pop('__type__')
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
