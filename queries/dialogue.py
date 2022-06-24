import json
from typing import Any, Dict, Mapping, Union, List, Optional, cast
from typing_extensions import TypedDict

import os.path
import datetime

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib
from enum import IntEnum, auto
from dataclasses import dataclass, field

from tree import Result
from query import Query, ClientDataDict
from reynir import NounPhrase
from queries import natlang_seq, sing_or_plur

# Global key for storing client data for dialogues
DIALOGUE_KEY = "dialogue"
DIALOGUE_DATA_KEY = "dialogue_data"
EMPTY_DIALOGUE_DATA = "{}"
FINAL_RESOURCE_NAME = "Final"

ResourceType = Union[str, int, float, bool, datetime.datetime, None]
ListResourceType = List[ResourceType]


class ResourceState(IntEnum):
    """Enum representing the different states a dialogue resource can be in."""

    INITIAL = auto()
    UNFULFILLED = auto()
    PARTIALLY_FULFILLED = auto()
    FULFILLED = auto()
    CONFIRMED = auto()
    PAUSED = auto()
    SKIPPED = auto()


##########################
#    RESOURCE CLASSES    #
##########################


@dataclass
class Resource:
    name: str = ""
    data: Any = None
    state: ResourceState = ResourceState.INITIAL
    prompt: str = ""
    type: str = ""
    repeatable: bool = False
    repeat_prompt: Optional[str] = None
    confirm_prompt: Optional[str] = None
    cancel_prompt: Optional[str] = None
    requires: List[str] = field(default_factory=list)
    _repeat_count: int = 0

    def next_action(self) -> Any:
        raise NotImplementedError()

    def generate_answer(self, dsm: "DialogueStateManager", result: Result) -> str:
        raise NotImplementedError()

    def update(self, new_data: Optional["Resource"]) -> None:
        if new_data:
            self.__dict__.update(new_data.__dict__)

    def _execute_children(
        self, dsm: "DialogueStateManager", result: Result
    ) -> Optional[str]:
        if "callbacks" in result:
            while len(result.callbacks) > 0:
                rnames, cb = result.callbacks.pop(0)
                if self.name in rnames:
                    cb(self, result)
        if self.requires:
            for rname in self.requires:
                resource = dsm.get_resource(rname)
                if resource.state is not ResourceState.CONFIRMED:
                    return resource.generate_answer(dsm, result)
        return None


def _list_items(items: Any) -> str:
    item_list: List[str] = []
    for num, name in items:
        # TODO: get general plural form
        plural_name: str = NounPhrase(name).dative or name
        item_list.append(sing_or_plur(num, name, plural_name))
    return natlang_seq(item_list)


@dataclass
class ListResource(Resource):
    data: ListResourceType = field(default_factory=list)
    available_options: Optional[ListResourceType] = None

    def list_available_options(self) -> str:
        raise NotImplementedError()

    def generate_answer(self, dsm: "DialogueStateManager", result: Result) -> str:
        ans: Optional[str] = self._execute_children(dsm, result)
        if ans:
            return ans
        if self.state is ResourceState.INITIAL:
            self.state = ResourceState.UNFULFILLED
        if self.state is ResourceState.UNFULFILLED:
            if self._repeat_count == 0 or not self.repeatable:
                ans = self.prompt
        if self.state is ResourceState.PARTIALLY_FULFILLED:
            if self.repeat_prompt:
                ans = (
                    f"{self.repeat_prompt.format(list_items = _list_items(self.data))}"
                )
        if self.state is ResourceState.FULFILLED:
            if self.confirm_prompt:
                ans = (
                    f"{self.confirm_prompt.format(list_items = _list_items(self.data))}"
                )
        if ans is None:
            raise ValueError("No answer generated")
        return ans


# TODO:
# ExactlyOneResource (choose one resource from options)
# SetResource (a set of resources)?
# ...


@dataclass
class YesNoResource(Resource):
    data: bool = False
    yes_answer: Optional[str] = None
    no_answer: Optional[str] = None

    def set_yes(self):
        self.data = True
        self.state = ResourceState.CONFIRMED

    def set_no(self):
        self.data = False
        self.state = ResourceState.CONFIRMED

    def generate_answer(self, dsm: "DialogueStateManager", result: Result) -> str:
        ans: Optional[str] = self._execute_children(dsm, result)
        if ans:
            return ans
        if self.state is ResourceState.INITIAL:
            self.state = ResourceState.UNFULFILLED
        if self.data:
            if self.yes_answer:
                ans = self.yes_answer
        else:
            if self.no_answer:
                ans = self.no_answer
        if ans is None:
            raise ValueError("No answer generated")
        return ans


@dataclass
class DatetimeResource(Resource):
    data: List[Union[Optional[datetime.date], Optional[datetime.time]]] = field(
        default_factory=lambda: [None, None]
    )
    date_fulfilled_prompt: Optional[str] = None
    time_fulfilled_prompt: Optional[str] = None

    def has_date(self) -> bool:
        return isinstance(self.data[0], datetime.date)

    def has_time(self) -> bool:
        return isinstance(self.data[1], datetime.time)

    def set_date(self, new_date: Optional[datetime.date] = None) -> None:
        self.data[0] = new_date

    def set_time(self, new_time: Optional[datetime.time] = None) -> None:
        self.data[1] = new_time

    def generate_answer(self, dsm: "DialogueStateManager", result: Result) -> str:
        ans: Optional[str] = self._execute_children(dsm, result)
        if ans:
            return ans
        if self.state is ResourceState.INITIAL:
            self.state = ResourceState.UNFULFILLED
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
        if ans is None:
            raise ValueError("No answer generated")
        return ans


@dataclass
class NumberResource(Resource):
    data: int = 0


@dataclass
class OrResource(Resource):
    data: Dict[str, Any] = field(default_factory=dict)
    exclusive: bool = False  # Only one of the resources should be fulfilled


@dataclass
class FinalResource(Resource):
    data: Any = None
    final_prompt: str = ""

    def generate_answer(self, dsm: "DialogueStateManager", result: Result) -> str:
        ans: Optional[str] = self._execute_children(dsm, result)
        if ans:
            return ans
        return self.final_prompt


##############################
#    RESOURCE CLASSES END    #
##############################


class DialogueStructureType(TypedDict):
    """ """

    dialogue_name: str
    resources: List[Resource]


_RESOURCE_TYPES: Mapping[str, Any] = {
    "Resource": Resource,
    "ListResource": ListResource,
    "YesNoResource": YesNoResource,
    "DatetimeResource": DatetimeResource,
    "NumberResource": NumberResource,
    "FinalResource": FinalResource,
}


def _load_dialogue_structure(filename: str) -> DialogueStructureType:
    """Loads dialogue structure from TOML file."""
    basepath, _ = os.path.split(os.path.realpath(__file__))
    fpath = os.path.join(basepath, filename, filename + ".toml")
    with open(fpath, mode="r") as file:
        f = file.read()
    obj: Dict[str, Any] = tomllib.loads(f)  # type:ignore
    assert "dialogue_name" in obj
    assert "resources" in obj
    for i, resource in enumerate(obj["resources"]):
        assert "name" in resource
        assert "type" in resource
        obj["resources"][i] = _RESOURCE_TYPES[resource["type"]](**resource)
    return cast(DialogueStructureType, obj)


class DialogueStateManager:
    def __init__(self, dialogue_name: str, query: Query, result: Result):
        self._dialogue_name: str = dialogue_name
        self._q: Query = query
        self._result: Result = result
        self._resources: Dict[str, Resource] = {}
        self._saved_state: DialogueStructureType = self._get_saved_dialogue_state()
        self._data: Dict[str, Any] = {}
        # TODO: CALL STACK!
        # TODO: Delegate answering from a resource to another resource or to another dialogue
        # TODO: í ávaxtasamtali "ég vil panta flug" "viltu að ég geymi ávaxtapöntunina eða eyði henni?" ...

    def not_in_dialogue(self, start_dialogue_qtype: str) -> bool:
        """Check if the client is in or wants to start this dialogue"""
        qt = self._result.get("qtype")
        return (
            qt != start_dialogue_qtype
            and self._saved_state.get("dialogue_name") != self._dialogue_name
        )

    def setup_dialogue(self):
        obj = _load_dialogue_structure(self._dialogue_name)
        print(obj)
        for i, resource in enumerate(obj["resources"]):
            if self._saved_state and i < len(self._saved_state["resources"]):
                resource.update(self._saved_state["resources"][i])
                resource.state = ResourceState(self._saved_state["resources"][i].state)
            self._resources[resource.name] = resource

        self.resourceState: Optional[Resource] = None
        self.ans: Optional[str] = None

    def start_dialogue(self):
        """Save client's state as having started this dialogue"""
        # New empty dialogue state, with correct dialogue name
        self._set_dialogue_state(
            {
                "dialogue_name": self._dialogue_name,
                "resources": [],
            }
        )

    def update_dialogue_state(self):
        """Update the dialogue state for a client"""
        # Save resources to client data
        self._set_dialogue_state(
            {
                "dialogue_name": self._dialogue_name,
                "resources": list(self._resources.values()),
            }
        )

    def get_resource(self, name: str) -> Resource:
        return self._resources[name]

    def generate_answer(self, result: Result) -> str:
        # if self._resources[FINAL_RESOURCE_NAME].state is not ResourceState.CONFIRMED:
        ans = self._resources[FINAL_RESOURCE_NAME].generate_answer(self, result)
        if self._resources[FINAL_RESOURCE_NAME].state is ResourceState.CONFIRMED:
            # Final callback (performing some operation with the dialogue's data)
            # should be called before ending dialogue
            self.end_dialogue()
        return ans

        # i = 0
        # while i < len(self.resources):
        #     resource = self.resources[i]
        #     if resource.required and resource.state is not ResourceState.CONFIRMED:
        #         if resource.state is ResourceState.INITIAL:
        #             resource.state = ResourceState.UNFULFILLED
        #         if "callbacks" in result:
        #             while len(result.callbacks) > 0:
        #                 r_name, cb = result.callbacks.pop(0)
        #                 if self.resources[i].name in r_name:
        #                     cb(resource, result)
        #                 else:
        #                     while i > -1:
        #                         i -= 1
        #                         if self.resources[i].name in r_name:
        #                             cb(self.resources[i], result)
        #                             break
        #             if (
        #                 resource.state is ResourceState.CONFIRMED
        #                 and resource != self.resources[-1]
        #             ):
        #                 self._data[resource.name] = resource.data
        #                 i += 1
        #                 continue
        #         return self.resources[i].generate_answer()
        #     i += 1
        # return "Upp kom villa, reyndu aftur."

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

    def _set_dialogue_state(self, ds: DialogueStructureType) -> None:
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
        # Add JSON encoding for any new classes here

        if isinstance(o, Resource):
            # CLASSES THAT INHERIT FROM RESOURCE
            d = o.__dict__.copy()
            d["__type__"] = o.__class__.__name__
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
        if t == "date":
            return datetime.date(**d)
        if t == "time":
            return datetime.time(**d)
        return _RESOURCE_TYPES[t](**d)
