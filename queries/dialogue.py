from typing import Any, Callable, Dict, Mapping, Tuple, Union, List, Optional, cast
from typing_extensions import TypedDict

import os.path
import json
import datetime
from enum import IntEnum, auto
from dataclasses import dataclass, field

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

from tree import Result
from query import Query, ClientDataDict

# Global key for storing client data for dialogues
DIALOGUE_KEY = "dialogue"
DIALOGUE_DATA_KEY = "dialogue_data"
DIALOGUE_NAME_KEY = "dialogue_name"
DIALOGUE_RESOURCES_KEY = "resources"
EMPTY_DIALOGUE_DATA = "{}"
FINAL_RESOURCE_NAME = "Final"

# Resource types
ResourceDataType = Union[str, int, float, bool, datetime.datetime, None]
ListResourceType = List[ResourceDataType]

# Types for use in callbacks
CallbackType = Callable[["Resource", Result], None]
FilterFuncType = Callable[["Resource"], bool]
CallbackTupleType = Tuple[FilterFuncType, CallbackType]


class ResourceState(IntEnum):
    """Enum representing the different states a dialogue resource can be in."""

    UNFULFILLED = auto()
    PARTIALLY_FULFILLED = auto()
    FULFILLED = auto()
    CONFIRMED = auto()
    PAUSED = auto()
    SKIPPED = auto()
    CANCELLED = auto()


##########################
#    RESOURCE CLASSES    #
##########################


@dataclass
class Resource:
    name: str = ""
    type: str = ""
    data: Any = None
    state: ResourceState = ResourceState.UNFULFILLED
    requires: List[str] = field(default_factory=list)
    prompts: Mapping[str, str] = field(default_factory=dict)
    _answer: Optional[str] = None

    def set_answer(self, answer_name: str, **kwargs: str) -> None:
        print("SETTING ANSWER:", answer_name, kwargs, self.name)
        self._answer = self.prompts[answer_name].format(**kwargs)
        print("ANSWER SET AS:", self._answer)

    def get_answer(self, dsm: "DialogueStateManager") -> Optional[str]:
        print("CURRENT RESOURCE:", self.name, "ANSWER:", self._answer)
        if self._answer is not None:
            return self._answer
        ans: Optional[str] = None
        if self.requires:
            for rname in self.requires:
                resource = dsm.get_resource(rname)
                if not resource.is_confirmed:
                    ans = resource.get_answer(dsm)
                    if ans:
                        break
        # assert ans is not None, "No answer was generated from resource " + self.name
        return ans

    @property
    def is_unfulfilled(self) -> bool:
        return self.state is ResourceState.UNFULFILLED

    @property
    def is_partially_fulfilled(self) -> bool:
        return self.state is ResourceState.PARTIALLY_FULFILLED

    @property
    def is_fulfilled(self) -> bool:
        return self.state is ResourceState.FULFILLED

    @property
    def is_confirmed(self) -> bool:
        return self.state is ResourceState.CONFIRMED

    @property
    def is_paused(self) -> bool:
        return self.state is ResourceState.PAUSED

    @property
    def is_skipped(self) -> bool:
        return self.state is ResourceState.SKIPPED

    def next_action(self) -> Any:
        raise NotImplementedError()

    def update(self, new_data: Optional["Resource"]) -> None:
        if new_data:
            self.__dict__.update(new_data.__dict__)


@dataclass
class ListResource(Resource):
    data: ListResourceType = field(default_factory=list)
    available_options: Optional[ListResourceType] = None

    def list_available_options(self) -> str:
        raise NotImplementedError()

    # def generate_answer(
    #     self, dsm: "DialogueStateManager", result: Result
    # ) -> Optional[str]:
    #     ans: Optional[str] = self._get_child_answer(dsm, result)
    #     if ans:
    #         return ans
    #     if self.state is ResourceState.UNFULFILLED:
    #         ans = self.prompts["initial"]
    #     if self.state is ResourceState.PARTIALLY_FULFILLED:
    #         ans = (
    #             f"{self.prompts['repeat'].format(list_items = _list_items(self.data))}"
    #         )
    #     if self.state is ResourceState.FULFILLED:
    #         ans = (
    #             f"{self.prompts['confirm'].format(list_items = _list_items(self.data))}"
    #         )
    #     return ans


# TODO:
# ExactlyOneResource (choose one resource from options)
# SetResource (a set of resources)?
# ...


@dataclass
class YesNoResource(Resource):
    data: bool = False

    def set_yes(self):
        self.data = True
        self.state = ResourceState.CONFIRMED

    def set_no(self):
        self.data = False
        self.state = ResourceState.CONFIRMED

    # def generate_answer(
    #     self, dsm: "DialogueStateManager", result: Result
    # ) -> Optional[str]:
    #     ans: Optional[str] = self._get_child_answer(dsm, result)
    #     if ans:
    #         return ans
    #     if self.data:
    #         ans = self.prompts["yes_answer"]
    #     else:
    #         ans = self.prompts["no_answer"]
    #     if ans is None:
    #         raise ValueError("No answer generated")
    #     return ans


@dataclass
class DatetimeResource(Resource):
    data: List[Union[Optional[datetime.date], Optional[datetime.time]]] = field(
        default_factory=lambda: [None, None]
    )

    @property
    def date(self) -> Optional[datetime.date]:
        return self.data[0]

    @property
    def time(self) -> Optional[datetime.time]:
        return self.data[1]

    def has_date(self) -> bool:
        return len(self.data) > 0 and isinstance(self.data[0], datetime.date)

    def has_time(self) -> bool:
        return len(self.data) > 1 and isinstance(self.data[1], datetime.time)

    def set_date(self, new_date: Optional[datetime.date] = None) -> None:
        self.data[0] = new_date

    def set_time(self, new_time: Optional[datetime.time] = None) -> None:
        self.data[1] = new_time

    def get_answer(self, dsm: "DialogueStateManager") -> Optional[str]:
        ans: Optional[str] = super().get_answer(dsm)
        if ans:
            return ans

        if self.state is ResourceState.CONFIRMED:
            return None

        if self.state is ResourceState.UNFULFILLED:
            ans = self.prompts["initial"]

        if self.state is ResourceState.PARTIALLY_FULFILLED:
            if self.has_date():
                ans = self.prompts["date_fulfilled"].format(
                    date=self.data[0].strftime("%Y/%m/%d")
                )
            if self.has_time() and self.prompts["time_fulfilled"]:
                ans = self.prompts["time_fulfilled"].format(
                    time=self.data[1].strftime("%H:%M")
                )

        if self.state is ResourceState.FULFILLED:
            if self.has_date() and self.has_time():
                ans = self.prompts["confirm"].format(
                    date_time=datetime.datetime.combine(
                        cast(datetime.date, self.data[0]),
                        cast(datetime.time, self.data[1]),
                    ).strftime("%Y/%m/%d %H:%M")
                )
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
    assert DIALOGUE_NAME_KEY in obj
    assert DIALOGUE_RESOURCES_KEY in obj
    for i, resource in enumerate(obj[DIALOGUE_RESOURCES_KEY]):
        assert "name" in resource
        assert "type" in resource
        obj[DIALOGUE_RESOURCES_KEY][i] = _RESOURCE_TYPES[resource["type"]](**resource)
    return cast(DialogueStructureType, obj)


class DialogueStateManager:
    def __init__(
        self,
        dialogue_name: str,
        start_dialogue_qtype: str,
        query: Query,
        result: Result,
    ):
        self._dialogue_name: str = dialogue_name
        self._start_qtype: str = start_dialogue_qtype
        self._q: Query = query
        self._result: Result = result
        print("CALLBACKS:", self._result.get("callbacks"))
        self._resources: Dict[str, Resource] = {}
        self._saved_state: DialogueStructureType = self._get_saved_dialogue_state()
        self._data: Dict[str, Any] = {}
        # TODO: CALL STACK!
        # TODO: Delegate answering from a resource to another resource or to another dialogue
        # TODO: í ávaxtasamtali "ég vil panta flug" "viltu að ég geymi ávaxtapöntunina eða eyði henni?" ...

    def not_in_dialogue(self) -> bool:
        """Check if the client is in or wants to start this dialogue"""
        return (
            self._result.get("qtype") != self._start_qtype
            and self._saved_state.get(DIALOGUE_NAME_KEY) != self._dialogue_name
        )

    def setup_dialogue(self) -> None:
        obj = _load_dialogue_structure(self._dialogue_name)
        for i, resource in enumerate(obj[DIALOGUE_RESOURCES_KEY]):
            if self._saved_state and i < len(self._saved_state[DIALOGUE_RESOURCES_KEY]):
                resource.update(self._saved_state[DIALOGUE_RESOURCES_KEY][i])
                resource.state = ResourceState(
                    self._saved_state[DIALOGUE_RESOURCES_KEY][i].state
                )
            self._resources[resource.name] = resource

        self.resourceState: Optional[Resource] = None
        self.ans: Optional[str] = None

    def start_dialogue(self):
        """Save client's state as having started this dialogue"""
        # New empty dialogue state, with correct dialogue name
        self._set_dialogue_state(
            {
                DIALOGUE_NAME_KEY: self._dialogue_name,
                DIALOGUE_RESOURCES_KEY: [],
            }
        )

    def update_dialogue_state(self):
        """Update the dialogue state for a client"""
        # Save resources to client data
        self._set_dialogue_state(
            {
                DIALOGUE_NAME_KEY: self._dialogue_name,
                DIALOGUE_RESOURCES_KEY: list(self._resources.values()),
            }
        )

    def get_resource(self, name: str) -> Resource:
        return self._resources[name]

    def get_result(self) -> Result:
        return self._result

    def get_answer(self) -> str:
        # Executing callbacks
        self._execute_callbacks()

        answer_key: Optional[Tuple[str, str]] = self._result.get("answer_key")
        print("BLAAAA, answer key", answer_key)
        if answer_key:
            # Quick way of setting response (instead of using a callback)
            self._resources[answer_key[0]].set_answer(answer_key[1])
            print("USED ANSWER KEY", answer_key)

        ans = self._resources[FINAL_RESOURCE_NAME].get_answer(self)
        print("GOT ANSWER:", ans)
        if self._resources[FINAL_RESOURCE_NAME].is_confirmed:
            # Final callback (performing some operation with the dialogue's data)
            # should be called before ending dialogue
            self.end_dialogue()
        else:
            self.update_dialogue_state()
        if ans is None:
            ans = self._resources[FINAL_RESOURCE_NAME].prompts["final"]
        return ans

    def _execute_callbacks(self) -> None:
        cbs: Optional[List[CallbackTupleType]] = self._result.get("callbacks")
        print("CBS:", cbs)
        if cbs:
            for filter_func, cb in cbs:
                for resource in self._resources.values():
                    if filter_func(resource):
                        cb(resource, self._result)

    def _get_saved_dialogue_state(self) -> DialogueStructureType:
        """Load the dialogue state for a client"""
        cd = self._q.client_data(DIALOGUE_KEY)
        # Return empty DialogueStructureType in case no dialogue state exists
        ds: DialogueStructureType = {
            DIALOGUE_NAME_KEY: "",
            DIALOGUE_RESOURCES_KEY: [],
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
            for key in list(d.keys()):
                # Skip serializing attributes that start with an underscore
                if key.startswith("_"):
                    del d[key]
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
