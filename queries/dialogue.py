from typing import (
    Any,
    Callable,
    Dict,
    Mapping,
    Set,
    Tuple,
    Union,
    List,
    Optional,
    cast,
)
from typing_extensions import TypedDict

import os.path
import json
import datetime
from enum import IntEnum, auto
from dataclasses import dataclass, field

try:
    import tomllib  # type: ignore (module not available in Python <3.11)
except ModuleNotFoundError:
    import tomli as tomllib

from tree import Result
from query import Query, ClientDataDict
from queries import natlang_seq

# Global key for storing client data for dialogues
DIALOGUE_KEY = "dialogue"
DIALOGUE_NAME_KEY = "dialogue_name"
DIALOGUE_RESOURCES_KEY = "resources"
DIALOGUE_LAST_INTERACTED_WITH_KEY = "last_interacted_with"
EMPTY_DIALOGUE_DATA = "{}"
FINAL_RESOURCE_NAME = "Final"

# Resource types
ResourceDataType = Union[str, int, float, bool, datetime.datetime, None]
ListResourceType = List[ResourceDataType]

# Types for use in callbacks
CallbackType = Callable[["Resource", "DialogueStateManager", Result], None]
FilterFuncType = Callable[["Resource"], bool]
CallbackTupleType = Tuple[FilterFuncType, CallbackType]

# Types for use in generating prompts/answers
AnsweringFunctionType = Callable[["Resource", "DialogueStateManager"], Optional[str]]
AnsweringFunctionMap = Mapping[str, AnsweringFunctionType]


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
    """
    Base class representing a dialogue resource.
    Keeps track of the state of the resource, and the data it contains.
    """

    # Name of resource
    name: str = ""
    # Type (child class) of Resource
    type: str = ""
    # Contained data
    data: Any = None
    # Resource state (unfulfilled, partially fulfilled, etc.)
    state: ResourceState = ResourceState.UNFULFILLED
    # Resources that must be confirmed before moving on to this resource
    requires: List[str] = field(default_factory=list)
    # Dictionary containing different prompts/responses
    prompts: Mapping[str, str] = field(default_factory=dict)

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

    @property
    def is_cancelled(self) -> bool:
        return self.state is ResourceState.CANCELLED

    def update(self, new_data: Optional["Resource"]) -> None:
        """Update resource with attributes from another resource."""
        if new_data:
            self.__dict__.update(new_data.__dict__)

    def format_data(self, format_func: Optional[Callable[[Any], str]] = None) -> str:
        """
        Function to format data for display,
        optionally taking in a formatting function.
        """
        return format_func(self.data) if format_func else self.data


@dataclass
class ListResource(Resource):
    """Resource representing a list of items."""

    data: ListResourceType = field(default_factory=list)
    max_items: Optional[int] = None

    def format_data(self, format_func: Optional[Callable[[Any], str]] = None) -> str:
        if format_func:
            return format_func(self.data)
        return natlang_seq([str(x) for x in self.data])


# TODO: ?
# ExactlyOneResource (choose one resource from options)
# SetResource (a set of resources)?
# UserInfoResource (user info, e.g. name, age, home address, etc., can use saved data to autofill)
# ...


@dataclass
class YesNoResource(Resource):
    """Resource representing a yes/no answer."""

    data: bool = False

    def set_yes(self):
        self.data = True
        self.state = ResourceState.CONFIRMED

    def set_no(self):
        self.data = False
        self.state = ResourceState.CONFIRMED

    def format_data(self, format_func: Optional[Callable[[Any], str]] = None) -> str:
        if format_func:
            return format_func(self.data)
        return "já" if self.data else "nei"


@dataclass
class ConfirmResource(YesNoResource):
    """Resource representing a confirmation of other resources."""

    def set_no(self):
        self.data = False
        self.state = ResourceState.CANCELLED  # TODO: ?

    def confirm_children(self, dsm: "DialogueStateManager") -> None:
        """Confirm all child/required resources."""
        ConfirmResource._confirm_children(self, dsm)

    @staticmethod
    def _confirm_children(
        res: Resource,
        dsm: "DialogueStateManager",
    ) -> None:
        for req in res.requires:
            req_res = dsm.get_resource(req)
            if not isinstance(req_res, ConfirmResource):
                ConfirmResource._confirm_children(req_res, dsm)
                req_res.state = ResourceState.CONFIRMED


@dataclass
class DateResource(Resource):
    """Resource representing a date."""

    data: datetime.date = field(default_factory=datetime.date.today)

    @property
    def date(self) -> Optional[datetime.date]:
        return self.data if self.is_fulfilled else None

    def set_date(self, new_date: datetime.date) -> None:
        self.data = new_date

    def format_data(self, format_func: Optional[Callable[[Any], str]] = None) -> str:
        if format_func:
            return format_func(self.data)
        return self.data.strftime("%x")


@dataclass
class TimeResource(Resource):
    """Resource representing a time (00:00-23:59)."""

    data: datetime.time = field(default_factory=datetime.time)

    @property
    def time(self) -> Optional[datetime.time]:
        return self.data if self.is_fulfilled else None

    def set_time(self, new_time: datetime.time) -> None:
        self.data = new_time

    def format_data(self, format_func: Optional[Callable[[Any], str]] = None) -> str:
        if format_func:
            return format_func(self.data)
        return self.data.strftime("%X")


@dataclass
class DatetimeResource(Resource):
    """Resource for wrapping date and time resources."""

    pass


@dataclass
class NumberResource(Resource):
    """Resource representing a number."""

    data: int = 0


@dataclass
class OrResource(Resource):
    exclusive: bool = False  # Only one of the resources should be fulfilled


@dataclass
class AndResource(Resource):  # For answering multiple resources at the same time
    pass


@dataclass
class FinalResource(Resource):
    """Resource representing the final state of a dialogue."""

    data: Any = None


_RESOURCE_TYPES: Mapping[str, Any] = {
    "Resource": Resource,
    "ListResource": ListResource,
    "YesNoResource": YesNoResource,
    "DateResource": DateResource,
    "TimeResource": TimeResource,
    "DatetimeResource": DatetimeResource,
    "NumberResource": NumberResource,
    "FinalResource": FinalResource,
}

################################
#    DIALOGUE STATE MANAGER    #
################################


class DialogueStructureType(TypedDict):
    """
    Representation of the dialogue structure,
    as it is read from the TOML files and saved to the database.
    """

    dialogue_name: str
    resources: Dict[str, Resource]
    last_interacted_with: Optional[datetime.datetime]


def _load_dialogue_structure(filename: str) -> DialogueStructureType:
    """Loads dialogue structure from TOML file."""
    basepath, _ = os.path.split(os.path.realpath(__file__))
    # TODO: Fix this, causes issues when folders have the same name as a module
    fpath = os.path.join(basepath, filename, filename + ".toml")
    with open(fpath, mode="r") as file:
        f = file.read()
    obj: Dict[str, Any] = tomllib.loads(f)  # type: ignore
    assert DIALOGUE_NAME_KEY in obj
    assert DIALOGUE_RESOURCES_KEY in obj
    resource_dict: Dict[str, Resource] = {}
    for resource in obj[DIALOGUE_RESOURCES_KEY]:
        assert "name" in resource
        if "type" not in resource:
            resource["type"] = "Resource"
        # Create instances of Resource classes (and its subclasses)
        resource_dict[resource["name"]] = _RESOURCE_TYPES[resource["type"]](**resource)
    obj[DIALOGUE_RESOURCES_KEY] = resource_dict
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
        self._resources: Dict[str, Resource] = {}
        self._saved_state: DialogueStructureType = self._get_saved_dialogue_state()
        self._data: Dict[str, Any] = {}
        self._answering_functions: AnsweringFunctionMap = {}
        self._answer: Optional[str] = None
        self._error: bool = False
        # TODO: Delegate answering from a resource to another resource or to another dialogue
        # TODO: í ávaxtasamtali "ég vil panta flug" "viltu að ég geymi ávaxtapöntunina eða eyði henni?" ...

    def not_in_dialogue(self) -> bool:
        """Check if the client is in or wants to start this dialogue"""
        return (
            self._result.get("qtype") != self._start_qtype
            and self._saved_state.get(DIALOGUE_NAME_KEY) != self._dialogue_name
        )

    def setup_dialogue(self, answering_functions: AnsweringFunctionMap) -> None:
        obj = _load_dialogue_structure(self._dialogue_name)
        for rname, resource in obj[DIALOGUE_RESOURCES_KEY].items():
            if rname in self._saved_state[DIALOGUE_RESOURCES_KEY]:
                # Update empty resource with serialized data
                resource.update(self._saved_state[DIALOGUE_RESOURCES_KEY][rname])
            # Change from int to enum type
            resource.state = ResourceState(resource.state)
            self._resources[rname] = resource
        self._answering_functions = answering_functions

    def start_dialogue(self):
        """Save client's state as having started this dialogue"""
        # New empty dialogue state, with correct dialogue name
        self._set_dialogue_state(
            {
                DIALOGUE_NAME_KEY: self._dialogue_name,
                DIALOGUE_RESOURCES_KEY: {},
                DIALOGUE_LAST_INTERACTED_WITH_KEY: datetime.datetime.now(),
            }
        )

    def update_dialogue_state(self):
        """Update the dialogue state for a client"""
        # Save resources to client data
        self._set_dialogue_state(
            {
                DIALOGUE_NAME_KEY: self._dialogue_name,
                DIALOGUE_RESOURCES_KEY: self._resources,
                DIALOGUE_LAST_INTERACTED_WITH_KEY: datetime.datetime.now(),
            }
        )

    def get_resource(self, name: str) -> Resource:
        return self._resources[name]

    def get_result(self) -> Result:
        return self._result

    def get_answer(self) -> Optional[str]:
        # Executing callbacks
        cbs: Optional[List[CallbackTupleType]] = self._result.get("callbacks")
        curr_resource = self._resources[FINAL_RESOURCE_NAME]
        if cbs:
            self._execute_callbacks_postorder(curr_resource, cbs, set())

        if self._error:
            # An error was raised somewhere during the callbacks
            return None

        # Check if dialogue was cancelled
        if curr_resource.is_cancelled:
            self._answer = self._answering_functions[FINAL_RESOURCE_NAME](
                curr_resource, self
            )
            if not self._answer:
                raise ValueError("No answer for cancelled dialogue")
            return self._answer

        # Iterate through resources (inorder traversal)
        # until one generates an answer
        self._answer = self._get_answer_postorder(curr_resource, set())

        if self._resources[FINAL_RESOURCE_NAME].is_confirmed:
            # Final callback (performing some operation with the dialogue's data)
            # should be called before ending dialogue
            self.end_dialogue()
        else:
            self.update_dialogue_state()
        return self._answer

    def _get_answer_postorder(
        self, curr_resource: Resource, finished: Set[str]
    ) -> Optional[str]:
        for rname in curr_resource.requires:
            if rname not in finished:
                finished.add(rname)
                ans = self._get_answer_postorder(self._resources[rname], finished)
                if ans:
                    return ans
        if curr_resource.name in self._answering_functions:
            return self._answering_functions[curr_resource.name](curr_resource, self)
        return None

    def _execute_callbacks_postorder(
        self, curr_resource: Resource, cbs: List[CallbackTupleType], finished: Set[str]
    ) -> None:
        for rname in curr_resource.requires:
            if rname not in finished:
                finished.add(rname)
                self._execute_callbacks_postorder(self._resources[rname], cbs, finished)

        for filter_func, cb in cbs:
            if filter_func(curr_resource):
                cb(curr_resource, self, self._result)

    def _get_saved_dialogue_state(self) -> DialogueStructureType:
        """Load the dialogue state for a client"""
        cd = self._q.client_data(DIALOGUE_KEY)
        # Return empty DialogueStructureType in case no dialogue state exists
        dialogue_struct: DialogueStructureType = {
            DIALOGUE_NAME_KEY: "",
            DIALOGUE_RESOURCES_KEY: {},
            DIALOGUE_LAST_INTERACTED_WITH_KEY: datetime.datetime.now(),
        }
        if cd:
            ds_str = cd.get(self._dialogue_name)
            if isinstance(ds_str, str) and ds_str != EMPTY_DIALOGUE_DATA:
                # TODO: Add try-except block
                dialogue_struct = json.loads(ds_str, cls=DialogueJSONDecoder)
        return dialogue_struct

    def _set_dialogue_state(self, ds: DialogueStructureType) -> None:
        """Save the state of a dialogue for a client"""
        # TODO: Add try-except block?
        ds_json: str = json.dumps(ds, cls=DialogueJSONEncoder)
        # Wrap data before saving dialogue state into client data
        # (due to custom JSON serialization)
        cd = {self._dialogue_name: ds_json}
        self._q.set_client_data(DIALOGUE_KEY, cast(ClientDataDict, cd))

    def end_dialogue(self) -> None:
        """End the client's current dialogue"""
        # TODO: Doesn't allow multiple conversations at once
        #       (set_client_data overwrites other conversations)
        self._q.set_client_data(
            DIALOGUE_KEY, {self._dialogue_name: EMPTY_DIALOGUE_DATA}
        )

    def set_error(self) -> None:
        self._error = True


###################################
#    ENCODING/DECODING CLASSES    #
###################################


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
