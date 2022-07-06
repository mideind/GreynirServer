from typing import (
    Any,
    Callable,
    Dict,
    Mapping,
    Set,
    Tuple,
    List,
    Optional,
    Type,
    TypeVar,
    cast,
)
from typing_extensions import TypedDict

import os.path
import json
import datetime
from enum import IntFlag, auto
from dataclasses import dataclass, field

try:
    import tomllib  # type: ignore (module not available in Python <3.11)
except ModuleNotFoundError:
    import tomli as tomllib  # Used for Python <3.11

from queries import AnswerTuple, natlang_seq

# TODO: Add timezone info to json encoding/decoding?
# TODO: FIX TYPE HINTS (esp. 'Any')

# Keys for accessing saved client data for dialogues
_DIALOGUE_KEY = "dialogue"
_DIALOGUE_NAME_KEY = "dialogue_name"
_DIALOGUE_RESOURCES_KEY = "resources"
_DIALOGUE_LAST_INTERACTED_WITH_KEY = "last_interacted_with"
_DIALOGUE_EXTRAS_KEY = "extras"
_DIALOGUE_INITIAL_RESOURCE_KEY = "initial_resource"
_EMPTY_DIALOGUE_DATA = "{}"
_FINAL_RESOURCE_NAME = "Final"
_CALLBACK_LOCATION = "callbacks"

QueryType = TypeVar("QueryType")

# Generic resource type
ResourceType_co = TypeVar("ResourceType_co", bound="Resource")

# Types for use in callbacks
_CallbackType = Callable[[ResourceType_co, "DialogueStateManager", Any], None]
_FilterFuncType = Type[Callable[[ResourceType_co], bool]]
_CallbackTupleType = Tuple[_FilterFuncType["Resource"], _CallbackType["Resource"]]

# Types for use in generating prompts/answers
AnsweringFunctionType = Callable[
    [ResourceType_co, "DialogueStateManager", Any], Optional[AnswerTuple]
]
# TODO: Fix 'Any' in type hint (Callable args are contravariant)
AnsweringFunctionMap = Mapping[str, AnsweringFunctionType[Any]]


class ResourceState(IntFlag):
    """Enum representing the different states a dialogue resource can be in."""

    # Main states (order matters, lower state should equal a lower number)
    UNFULFILLED = auto()
    PARTIALLY_FULFILLED = auto()
    FULFILLED = auto()
    CONFIRMED = auto()
    # ----  Extra states
    PAUSED = auto()
    SKIPPED = auto()
    CANCELLED = auto()
    ALL = (
        UNFULFILLED
        | PARTIALLY_FULFILLED
        | FULFILLED
        | CONFIRMED
        | PAUSED
        | SKIPPED
        | CANCELLED
    )


##########################
#    RESOURCE CLASSES    #
##########################


@dataclass(eq=False, repr=False)
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
    # When this resource's state is changed, change all parent resource states as well
    cascade_state: bool = False

    @property
    def is_unfulfilled(self) -> bool:
        return ResourceState.UNFULFILLED in self.state

    @property
    def is_partially_fulfilled(self) -> bool:
        return ResourceState.PARTIALLY_FULFILLED in self.state

    @property
    def is_fulfilled(self) -> bool:
        return ResourceState.FULFILLED in self.state

    @property
    def is_confirmed(self) -> bool:
        return ResourceState.CONFIRMED in self.state

    @property
    def is_paused(self) -> bool:
        return ResourceState.PAUSED in self.state

    @property
    def is_skipped(self) -> bool:
        return ResourceState.SKIPPED in self.state

    @property
    def is_cancelled(self) -> bool:
        return ResourceState.CANCELLED in self.state

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

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Resource) and self.name == other.name

    def __repr__(self) -> str:
        return f"<{self.name}>"

    def __str__(self) -> str:
        return f"<{self.name}>"


@dataclass(eq=False, repr=False)
class ListResource(Resource):
    """Resource representing a list of items."""

    data: List[Any] = field(default_factory=list)
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


@dataclass(eq=False, repr=False)
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


@dataclass(eq=False, repr=False)
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


@dataclass(eq=False, repr=False)
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


@dataclass(eq=False, repr=False)
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


@dataclass(eq=False, repr=False)
class DatetimeResource(Resource):
    """Resource for wrapping date and time resources."""

    ...


@dataclass(eq=False, repr=False)
class NumberResource(Resource):
    """Resource representing a number."""

    data: int = 0


@dataclass(eq=False, repr=False)
class OrResource(Resource):
    exclusive: bool = False  # Only one of the resources should be fulfilled


@dataclass(eq=False, repr=False)  # Wrapper when multiple resources are required
class WrapperResource(Resource):
    ...


@dataclass(eq=False, repr=False)
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
    "WrapperResource": WrapperResource,
    "OrResource": OrResource,
}

################################
#    DIALOGUE STATE MANAGER    #
################################


class ResourceGraphItem(TypedDict):
    children: List[Resource]
    parents: List[Resource]


ResourceGraph = Dict[Resource, ResourceGraphItem]


class DialogueStructureType(TypedDict, total=False):
    """
    Representation of the dialogue structure,
    as it is read from the TOML files and saved to the database.
    """

    dialogue_name: str
    initial_resource: str
    resources: Dict[str, Resource]
    last_interacted_with: Optional[datetime.datetime]
    extras: Optional[Dict[str, Any]]


class DialogueStateManager:
    def __init__(self, dialogue_name: str, saved_state: Optional[str] = None):
        self._dialogue_name: str = dialogue_name
        self._resources: Dict[str, Resource] = {}
        self._in_this_dialogue: bool = False
        self._extras: Dict[str, Any] = {}
        # self._error: bool = False
        # self._answering_functions = answering_functions
        self._answer_tuple: Optional[AnswerTuple] = None
        self._current_resource: Optional[Resource] = None
        self._resource_graph: ResourceGraph = {}
        self._saved_state: Optional[DialogueStructureType] = None

        if isinstance(saved_state, str):
            # TODO: Add try-except block
            # TODO: Add check for datetime last interaction
            self._saved_state = cast(
                DialogueStructureType, json.loads(saved_state, cls=DialogueJSONDecoder)
            )
            # Check that we have saved data for this dialogue
            if self._saved_state.get(_DIALOGUE_RESOURCES_KEY):
                self._in_this_dialogue = True
            print("setting up dialogue")
            self.setup_dialogue() # TODO: Rename me

    def setup_dialogue(self) -> None:
        """
        Load dialogue structure from TOML file and update resource states from client data.
        Should be called after initializing an instance of
        DialogueStateManager and before calling get_answer.
        """
        obj = self._load_dialogue_structure(self._dialogue_name)
        # TODO: fix type hints
        for rname, resource in obj[_DIALOGUE_RESOURCES_KEY].items():
            if self._saved_state and rname in self._saved_state.get(_DIALOGUE_RESOURCES_KEY, {}):
                # Update empty resource with serialized data
                resource.update(self._saved_state[_DIALOGUE_RESOURCES_KEY][rname])
            # Change from int to enum type
            resource.state = ResourceState(resource.state)
            self._resources[rname] = resource
        if self._saved_state and _DIALOGUE_EXTRAS_KEY in self._saved_state:
            self._extras = self._saved_state.get(_DIALOGUE_EXTRAS_KEY) or self._extras

        assert _DIALOGUE_INITIAL_RESOURCE_KEY in obj
        self._initial_resource = self._resources[obj[_DIALOGUE_INITIAL_RESOURCE_KEY]]
        self._initialize_resource_graph()

        #     # We just started this dialogue,
        # # save an empty dialogue state for this device
        # # (in order to resume dialogue upon next query)
        # self._start_dialogue()

    # def old__init__(
    #     self,
    #     dialogue_name: str,
    #     start_dialogue_qtype: str,
    #     result: Any,
    # ):
    #     self._dialogue_name: str = dialogue_name
    #     self._start_qtype: str = start_dialogue_qtype
    #     self._result: Any = result
    #     self._resources: Dict[str, Resource] = {}
    #     self._saved_state: Optional[DialogueStructureType] = self._get_saved_dialogue_state()
    #     self._answering_functions: AnsweringFunctionMap = {}
    #     self._extras: Dict[str, Any] = {}
    #     self._current_resource: Optional[Resource] = None
    #     # TODO: Delegate answering from a resource to another resource or to another dialogue
    #     # TODO: í ávaxtasamtali "ég vil panta flug" "viltu að ég geymi ávaxtapöntunina eða eyði henni?" ...

    def _initialize_resource_graph(self) -> None:
        """
        Initializes the resource graph with each
        resource having children and parents according
        to what each resource requires.
        """
        for resource in self._resources.values():
            self._resource_graph[resource] = {"children": [], "parents": []}

        for resource in self._resources.values():
            for req in resource.requires:
                self._resource_graph[self._resources[req]]["parents"].append(resource)
                self._resource_graph[resource]["children"].append(self._resources[req])
        print(self._resource_graph)

    def _load_dialogue_structure(self, filename: str) -> DialogueStructureType:
        """Loads dialogue structure from TOML file."""
        basepath, _ = os.path.split(os.path.realpath(__file__))
        fpath = os.path.join(basepath, "dialogues", filename + ".toml")
        with open(fpath, mode="r") as file:
            f = file.read()
        obj: Dict[str, Any] = tomllib.loads(f)  # type: ignore
        assert _DIALOGUE_RESOURCES_KEY in obj
        resource_dict: Dict[str, Resource] = {}
        for resource in obj[_DIALOGUE_RESOURCES_KEY]:
            assert "name" in resource
            if "type" not in resource:
                resource["type"] = "Resource"
            # Create instances of Resource classes (and its subclasses)
            resource_dict[resource["name"]] = _RESOURCE_TYPES[resource["type"]](
                **resource
            )
        obj[_DIALOGUE_RESOURCES_KEY] = resource_dict
        return cast(DialogueStructureType, obj)

    def activate_dialogue(self) -> None:
        self._in_this_dialogue = True
        self.setup_dialogue()

    def not_in_dialogue(self) -> bool:
        """Check if the client is in or wants to start this dialogue"""
        return not self._in_this_dialogue
        # return (
        #     self._result.get("qtype") != self._start_qtype
        #     and self._saved_state.get(_DIALOGUE_NAME_KEY) != self._dialogue_name
        # )
        # TODO: Add check for newest dialogue

    def _start_dialogue(self):
        """Save client's state as having started this dialogue"""
        # New empty dialogue state, with correct dialogue name
        self._set_dialogue_state(
            {
                _DIALOGUE_NAME_KEY: self._dialogue_name,
                _DIALOGUE_RESOURCES_KEY: {},
                _DIALOGUE_LAST_INTERACTED_WITH_KEY: datetime.datetime.now(),
                _DIALOGUE_EXTRAS_KEY: self._extras,
            }
        )

    def update_dialogue_state(self):
        """Update the dialogue state for a client"""
        # Save resources to client data
        self._set_dialogue_state(
            {
                _DIALOGUE_NAME_KEY: self._dialogue_name,
                _DIALOGUE_RESOURCES_KEY: self._resources,
                _DIALOGUE_LAST_INTERACTED_WITH_KEY: datetime.datetime.now(),
                _DIALOGUE_EXTRAS_KEY: self._extras,
            }
        )

    @property
    def current_resource(self) -> Resource:
        if self._current_resource is None:
            self._current_resource = self._find_current_resource()
        return self._current_resource

    def get_resource(self, name: str) -> Resource:
        return self._resources[name]

    def get_extras(self) -> Dict[str, Any]:
        return self._extras

    def get_answer(self, answering_functions: AnsweringFunctionMap, result: Any) -> Optional[AnswerTuple]:
        # Executing callbacks
        # cbs: Optional[List[_CallbackTupleType]] = self._result.get(_CALLBACK_LOCATION)
        # curr_resource = self._resources[_FINAL_RESOURCE_NAME]
        # if cbs:
        #     self._execute_callbacks_postorder(curr_resource, cbs, set())

        self._current_resource = self._find_current_resource()
        # if self._error:
        #     # An error was raised somewhere during the callbacks
        #     return None
        self._answering_functions = answering_functions
        # Check if dialogue was cancelled
        if self._current_resource.is_cancelled:
            self._answer_tuple = self._answering_functions[_FINAL_RESOURCE_NAME](
                self._current_resource, self, result
            )
            if not self._answer_tuple:
                raise ValueError("No answer for cancelled dialogue")
            return self._answer_tuple


        if self._current_resource.name in self._answering_functions:
            ans= self._answering_functions[self._current_resource.name](self._current_resource, self, result)
            print("GENERATED DATE ANSWERRRRRRRRRRRRRRRRR")
            return ans
        # Iterate through resources (inorder traversal)
        # until one generates an answer
        self._answer_tuple = self._get_answer_postorder(self._current_resource, result, set())

        if self._resources[_FINAL_RESOURCE_NAME].is_confirmed:
            # Final callback (performing some operation with the dialogue's data)
            # should be called before ending dialogue
            self.end_dialogue()
        else:
            self.update_dialogue_state()
        return self._answer_tuple

    def _get_answer_postorder(
        self, curr_resource: Resource, result: Any, finished: Set[Resource]
    ) -> Optional[AnswerTuple]:
        for resource in self._resource_graph[curr_resource]["children"]:
            if resource not in finished:
                finished.add(resource)
                ans = self._get_answer_postorder(resource, result, finished)
                if ans:
                    return ans
        if curr_resource.name in self._answering_functions:
            return self._answering_functions[curr_resource.name](curr_resource, self, result)
        return None

    def _execute_callbacks_postorder(
        self,
        curr_resource: Resource,
        cbs: List[_CallbackTupleType],
        finished: Set[Resource],
    ) -> None:
        for resource in self._resource_graph[curr_resource]["children"]:
            if resource not in finished:
                finished.add(resource)
                self._execute_callbacks_postorder(resource, cbs, finished)

        # for filter_func, cb in cbs:
        #     if filter_func(curr_resource):
        #         cb(curr_resource, self, self._result)

    # def _get_saved_dialogue_state(self) -> Optional[DialogueStructureType]:
    #     """Load the dialogue state for a client"""
    #     cd = self._q.client_data(_DIALOGUE_KEY)
    #     dialogue_struct: Optional[DialogueStructureType] = None
    #     if cd:
    #         ds_str = cd.get(self._dialogue_name)
    #         if isinstance(ds_str, str) and ds_str != _EMPTY_DIALOGUE_DATA:
    #             # TODO: Add try-except block
    #             dialogue_struct = json.loads(ds_str, cls=DialogueJSONDecoder)
    #     # if dialogue_struct is None:
    #     #     self._in_this_dialogue = False
    #     #     # Return empty DialogueStructureType in case no dialogue state exists
    #     #     dialogue_struct = {
    #     #         _DIALOGUE_NAME_KEY: "",
    #     #         _DIALOGUE_RESOURCES_KEY: {},
    #     #         _DIALOGUE_LAST_INTERACTED_WITH_KEY: datetime.datetime.now(),
    #     #         _DIALOGUE_EXTRAS_KEY: {},
    #     #     }
    #     return dialogue_struct

    def _set_dialogue_state(self, ds: DialogueStructureType) -> None:
        """Save the state of a dialogue for a client"""
        # TODO: Add try-except block?
        ds_json: str = json.dumps(ds, cls=DialogueJSONEncoder)
        # Wrap data before saving dialogue state into client data
        # (due to custom JSON serialization)
        cd = {self._dialogue_name: ds_json}
        # TODO: add datetime stuff
        # self._q.set_client_data(
        #     _DIALOGUE_KEY,
        #     cast(Any, cd),
        #     update_in_place=True,
        # )

    def set_resource_state(self, resource_name: str, state: ResourceState):
        """
        Set the state of a resource.
        Sets state of all parent resources to unfulfilled
        if cascade_state is set to True for the resource.
        """
        print("SETTING STATE OF RESOURCE:", resource_name, "TO STATE:", state)
        resource = self._resources[resource_name]
        lowered_state = resource.state > state
        resource.state = state
        print("CASCADES?", self._resources[resource_name].cascade_state)
        if resource.cascade_state and lowered_state:
            # Find all parent resources and set to corresponding state
            print("SEARCHING FOR PARENTS")
            parents = self._find_parent_resources(self._resources[resource_name])
            print("PARENTS FOUND:", parents)
            for parent in parents:
                parent.state = ResourceState.UNFULFILLED

    def _find_parent_resources(self, resource: Resource) -> Set[Resource]:
        """Find all parent resources of a resource"""
        all_parents: Set[Resource] = set()
        resource_parents: list[Resource] = self._resource_graph[resource]["parents"]
        if len(resource_parents) > 0:
            for parent in resource_parents:
                if parent not in all_parents:
                    all_parents.add(parent)
                    all_parents.update(self._find_parent_resources(parent))
        return all_parents

    def _find_current_resource(self) -> Resource:
        """
        Finds the current resource in the resource graph.
        """
        curr_res: Resource = self._initial_resource
        while curr_res.is_confirmed:
            for parent in self._resource_graph[curr_res]["parents"]:
                curr_res = parent
                grandparents = self._resource_graph[parent]["parents"]
                if len(grandparents) == 1 and isinstance(
                    grandparents[0], WrapperResource
                ):
                    curr_res = grandparents[0]
                    break
        print("CURRENT RESOURCE:", curr_res)
        return curr_res

    def end_dialogue(self) -> None:
        """End the client's current dialogue"""
        # TODO: Doesn't allow multiple conversations at once
        #       (set_client_data overwrites other conversations)
        self._resources = {}

    def serialize_data(self):
        """Serialize the dialogue's data"""
        # TODO: Add try-except block?
        ds_json: str = json.dumps(
            {
                _DIALOGUE_RESOURCES_KEY: self._resources,
                _DIALOGUE_LAST_INTERACTED_WITH_KEY: datetime.datetime.now(),
                _DIALOGUE_EXTRAS_KEY: self._extras,
            },
            cls=DialogueJSONEncoder,
        )
        # Wrap data before saving dialogue state into client data
        # (due to custom JSON serialization)
        cd = {self._dialogue_name: ds_json}
        # TODO: add datetime stuff
        return cd

    # def set_error(self) -> None:
    #     self._error = True

    @classmethod  # TODO: Fix type hints?
    def add_callback(
        cls,
        result: Any,
        filter_func: _FilterFuncType[Resource],
        cb: _CallbackType[Resource],
    ):
        """Add a callback to the callback list"""
        if _CALLBACK_LOCATION not in result:
            result[_CALLBACK_LOCATION] = []
        result.callbacks.append((filter_func, cb))


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
        if isinstance(o, datetime.datetime):
            return {
                "__type__": "datetime",
                "year": o.year,
                "month": o.month,
                "day": o.day,
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
        if t == "datetime":
            return datetime.datetime(**d)
        return _RESOURCE_TYPES[t](**d)
