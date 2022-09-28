"""

    Greynir: Natural language processing for Icelandic

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


    Class for dialogue management.

"""
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    Mapping,
    Set,
    List,
    Optional,
    Tuple,
    Type,
    Union,
    cast,
)
from typing_extensions import Required, TypedDict

import json
import logging
import datetime
from pathlib import Path
from functools import lru_cache

try:
    import tomllib  # type: ignore (module not available in Python <3.11)
except ModuleNotFoundError:
    import tomli as tomllib  # Used for Python <3.11

from db import SessionContext, Session
from db.models import DialogueData as DB_DialogueData, QueryData as DB_QueryData

import queries.extras.resources as res
from queries import AnswerTuple


# TODO:? Delegate answering from a resource to another resource or to another dialogue
# TODO:? í ávaxtasamtali "ég vil panta flug" "viltu að ég geymi ávaxtapöntunina eða eyði henni?" ...
# TODO: Add specific prompt handling to DSM to remove result from DSM.
# TODO: Add try-except blocks where appropriate
# TODO: Add "needs_confirmation" to TOML files (skip fulfilled, go straight to confirmed)

_TOML_FOLDER_NAME = "dialogues"
_DEFAULT_EXPIRATION_TIME = 30 * 60  # By default a dialogue expires after 30 minutes
_FINAL_RESOURCE_NAME = "Final"

_JSONTypes = Union[None, int, bool, str, List["_JSONTypes"], Dict[str, "_JSONTypes"]]
_TOMLTypes = Union[
    int,
    float,
    bool,
    str,
    datetime.datetime,
    datetime.date,
    datetime.time,
    List["_TOMLTypes"],
    Dict[str, "_TOMLTypes"],
]


class _ExtrasType(Dict[str, _TOMLTypes], TypedDict, total=False):
    """Structure of 'extras' key in dialogue TOML files."""

    expiration_time: int


class DialogueTOMLStructure(TypedDict):
    """Structure of a dialogue TOML file."""

    resources: Required[List[Dict[str, _TOMLTypes]]]
    dynamic_resources: List[Dict[str, _TOMLTypes]]
    extras: _ExtrasType


# Keys for accessing saved client data for dialogues
_ACTIVE_DIALOGUE_KEY = "dialogue"
_RESOURCES_KEY = "resources"
_DYNAMIC_RESOURCES_KEY = "dynamic_resources"
_MODIFIED_KEY = "modified"
_EXTRAS_KEY = "extras"
_EXPIRATION_TIME_KEY = "expiration_time"

# List of active dialogues, kept in querydata table
# (newer dialogues have higher indexes)
ActiveDialogueList = List[Tuple[str, str]]


class SerializedResource(Dict[str, _JSONTypes], TypedDict, total=False):
    """
    Representation of the required keys of a serialized resource.
    """

    name: Required[str]
    type: Required[str]
    state: Required[int]


class DialogueDeserialized(TypedDict):
    """
    Representation of the dialogue structure,
    after it is loaded from the database and parsed.
    """

    resources: Iterable[res.Resource]
    extras: _ExtrasType


class DialogueSerialized(TypedDict):
    """
    Representation of the dialogue structure,
    before it is saved to the database.
    """

    resources: Iterable[SerializedResource]
    extras: str


class DialogueDataRow(TypedDict):
    data: DialogueSerialized
    expires_at: datetime.datetime


def _dialogue_serializer(data: DialogueDeserialized) -> DialogueSerialized:
    """
    Prepare the dialogue data for writing into the database.
    """
    return {
        _RESOURCES_KEY: [
            cast(SerializedResource, res.RESOURCE_SCHEMAS[s.type]().dump(s))
            for s in data[_RESOURCES_KEY]
        ],
        # We just dump the entire extras dict as a string
        _EXTRAS_KEY: json.dumps(data[_EXTRAS_KEY], cls=TOMLtoJSONEncoder),
    }


def _dialogue_deserializer(data: DialogueSerialized) -> DialogueDeserialized:
    """
    Prepare the dialogue data for working with
    after it has been loaded from the database.
    """
    return {
        _RESOURCES_KEY: [
            cast(res.Resource, res.RESOURCE_SCHEMAS[s["type"]]().load(s))
            for s in data[_RESOURCES_KEY]
        ],
        # Load the extras dictionary from a JSON serialized string
        _EXTRAS_KEY: json.loads(data[_EXTRAS_KEY], cls=JSONtoTOMLDecoder),
    }


class TOMLtoJSONEncoder(json.JSONEncoder):
    # Map TOML type to a JSON serialized form
    _serializer_functions: Mapping[Type[Any], Callable[[Any], _JSONTypes]] = {
        datetime.datetime: lambda o: {
            "__type__": "datetime",
            "year": o.year,
            "month": o.month,
            "day": o.day,
            "hour": o.hour,
            "minute": o.minute,
            "second": o.second,
            "microsecond": o.microsecond,
        },
        datetime.date: lambda o: {
            "__type__": "date",
            "year": o.year,
            "month": o.month,
            "day": o.day,
        },
        datetime.time: lambda o: {
            "__type__": "time",
            "hour": o.hour,
            "minute": o.minute,
            "second": o.second,
            "microsecond": o.microsecond,
        },
    }

    def default(self, o: _TOMLTypes) -> _JSONTypes:
        f = self._serializer_functions.get(type(o))
        return f(o) if f else json.JSONEncoder.default(self, o)


class JSONtoTOMLDecoder(json.JSONDecoder):
    # Map __type__ to nonserialized form
    _type_conversions: Mapping[str, Type[_TOMLTypes]] = {
        "datetime": datetime.datetime,
        "date": datetime.date,
        "time": datetime.time,
    }

    def __init__(self, *args: Any, **kwargs: Any):
        json.JSONDecoder.__init__(
            self, object_hook=self.dialogue_decoding, *args, **kwargs
        )

    def dialogue_decoding(self, d: Dict[str, Any]) -> _TOMLTypes:
        if "__type__" not in d:
            return d
        t: str = d.pop("__type__")

        c = self._type_conversions.get(t)
        if c:
            return c(**d)
        logging.warning(f"No class found for __type__: {t}")
        d["__type__"] = t
        return d


# Functions for generating prompts/answers
# Arguments: resource, DSM, result object
_AnsweringFunctionType = Callable[..., Optional[AnswerTuple]]

# Difficult to type this correctly as the
# Callable type is contravariant in its arguments parameter
AnsweringFunctionMap = Mapping[str, _AnsweringFunctionType]

# Filter functions for filtering nodes
# when searching resource graph
FilterFuncType = Callable[[res.Resource, int], bool]
_ALLOW_ALL_FILTER: FilterFuncType = lambda r, i: True


class ResourceGraphItem(TypedDict):
    """Type for a node in the resource graph."""

    children: List[res.Resource]
    parents: List[res.Resource]


# Dependency relationship graph type for resources
ResourceGraph = Dict[res.Resource, ResourceGraphItem]


################################
#    DIALOGUE STATE MANAGER    #
################################


class DialogueStateManager:
    def __init__(self, client_id: Optional[str], db_session: Session) -> None:
        """Initialize DSM instance and fetch tthe active dialogues for a client."""
        self._client_id = client_id
        self._db_session = db_session  # Database session of parent Query class
        # Fetch active dialogues for this client (empty list if no client ID provided)
        self._active_dialogues: ActiveDialogueList = self._get_active_dialogues()

    def get_next_active_resource(self, dialogue_name: str) -> str:
        """
        Fetch the next current resource for a given dialogue.
        Used for banning nonterminals.
        """
        for x, y in self._active_dialogues:
            if x == dialogue_name:
                return y
        raise ValueError(
            "get_last_active_resource called "
            f"for non-active dialogue: {dialogue_name}"
        )

    def prepare_dialogue(self, dialogue_name: str):
        """
        Prepare DSM instance for a specific dialogue.
        Fetches saved state from database if dialogue is active.
        """
        self._dialogue_name: str = dialogue_name
        # Dict mapping resource name to resource instance
        self._resources: Dict[str, res.Resource] = {}
        # Boolean indicating if the client is in this dialogue
        self._in_this_dialogue: bool = False
        # Extra information saved with the dialogue state
        self._extras: _ExtrasType = {}
        # Answer for the current query
        self._answer_tuple: Optional[AnswerTuple] = None
        # Latest non-confirmed resource
        self._current_resource: Optional[res.Resource] = None
        # Dependency graph for the resources
        self._resource_graph: ResourceGraph = {}
        # Whether this dialogue is finished (successful/cancelled) or not
        self._finished: bool = False
        self._expiration_time: int = _DEFAULT_EXPIRATION_TIME
        self._timed_out: bool = False
        self._initial_resource = None

        # If dialogue is active, the saved state is loaded,
        # otherwise wait for hotword_activated() to be called
        if self._dialogue_name in (x for x, _ in self._active_dialogues):
            print("loading saved state...")
            self._in_this_dialogue = True
            self._load_saved_state()
        print("done preparing dialogue!")

    @lru_cache(maxsize=30)
    def _read_toml_file(self, dialogue_name: str) -> DialogueTOMLStructure:
        """Read TOML file for given dialogue."""
        p = (
            Path(__file__).parent.parent.resolve()
            / _TOML_FOLDER_NAME
            / f"{dialogue_name}.toml"
        )
        f = p.read_text()

        obj: DialogueTOMLStructure = tomllib.loads(f)  # type: ignore
        return obj

    def _initialize_resources(self) -> None:
        """
        Loads dialogue structure from TOML file and
        fills self._resources with empty Resource instances.
        """
        print("Reading TOML file...")
        # Read TOML file containing a list of resources for the dialogue
        obj: DialogueTOMLStructure = self._read_toml_file(self._dialogue_name)
        assert (
            _RESOURCES_KEY in obj
        ), f"No resources found in TOML file {self._dialogue_name}.toml"
        print("creating resources...")
        # Create resource instances from TOML data and return as a dict
        for i, resource in enumerate(obj[_RESOURCES_KEY]):
            assert "name" in resource, f"Name missing for resource {i+1}"
            if "type" not in resource:
                resource["type"] = "Resource"
            # Create instances of Resource classes (and its subclasses)
            # TODO: Maybe fix the type hinting
            self._resources[resource["name"]] = res.RESOURCE_MAP[resource["type"]](  # type: ignore
                **resource, order_index=i
            )
        print(f"Resources created: {self._resources}")
        # TODO: Create dynamic resource blueprints (factory)!!!!!
        self._extras = obj.get(_EXTRAS_KEY, dict())
        # Get expiration time duration for this dialogue
        self._expiration_time = self._extras.get(
            _EXPIRATION_TIME_KEY, _DEFAULT_EXPIRATION_TIME
        )
        # Create resource dependency relationship graph
        self._initialize_resource_graph()

    def _load_saved_state(self) -> None:
        """
        Fetch saved data from database for this
        dialogue and restore resource class instances.
        """
        saved_row = self._dialogue_data()
        assert saved_row is not None
        self._timed_out = datetime.datetime.now() > saved_row["expires_at"]
        if self._timed_out:
            # TODO: Do something when a dialogue times out
            logging.warning("THIS DIALOGUE IS TIMED OUT!!!")
            return
        saved_state: DialogueDeserialized = _dialogue_deserializer(saved_row["data"])
        # Load resources from saved state
        self._resources = {r.name: r for r in saved_state["resources"]}
        self._extras = saved_state["extras"]

        # Create resource dependency relationship graph
        self._initialize_resource_graph()

    def _initialize_resource_graph(self) -> None:
        """
        Initializes the resource graph with each
        resource having children and parents according
        to what each resource requires.
        """
        print("Creating resource graph...")
        for resource in self._resources.values():
            if resource.order_index == 0 and self._initial_resource is None:
                self._initial_resource = resource
            self._resource_graph[resource] = {"children": [], "parents": []}
        for resource in self._resources.values():
            for req in resource.requires:
                self._resource_graph[self._resources[req]]["parents"].append(resource)
                self._resource_graph[resource]["children"].append(self._resources[req])
        print("Finished resource graph!")

    def add_dynamic_resource(self, resource_name: str, parent_name: str) -> None:
        """
        Adds a dynamic resource to the dialogue from TOML file and
        updates the requirements of it's parents.
        """
        raise NotImplementedError()
        # TODO: Create separate blueprint factory class for creating dynamic resources
        parent_resource: res.Resource = self.get_resource(parent_name)
        order_index: int = parent_resource.order_index
        dynamic_resources: Dict[str, res.Resource] = {}
        # Index of dynamic resource
        dynamic_resource_index = (
            len(
                [
                    i
                    for i in self._resources
                    if self.get_resource(i).name.startswith(resource_name + "_")
                ]
            )
            + 1
        )
        print("<<<<<<<< DYNAMIC INDEX: ", dynamic_resource_index)
        # TODO: Only update index for added dynamic resources (don't loop through all, just the added ones)
        # Adding all dynamic resources to a list
        for dynamic_resource in obj[_DYNAMIC_RESOURCES_KEY]:
            assert "name" in dynamic_resource, f"Name missing for dynamic resource"
            if "type" not in dynamic_resource:
                dynamic_resource["type"] = "Resource"
            # Updating required resources to have indexed name
            dynamic_resource["requires"] = [
                f"{r}_{dynamic_resource_index}"
                for r in dynamic_resource.get("requires", [])
            ]
            # Updating dynamic resource name to have indexed name
            dynamic_resource["name"] = (
                f"{dynamic_resource['name']}_" f"{dynamic_resource_index}"
            )
            # Adding dynamic resource to list
            dynamic_resources[dynamic_resource["name"]] = res.RESOURCE_MAP[
                dynamic_resource["type"]
            ](
                **dynamic_resource,
                order_index=order_index,
            )
        # Indexed resource name of the dynamic resource
        indexed_resource_name = f"{resource_name}_{dynamic_resource_index}"
        resource: res.Resource = dynamic_resources[indexed_resource_name]
        # Appending resource to required list of parent resource
        parent_resource.requires.append(indexed_resource_name)

        def _add_child_resource(resource: res.Resource) -> None:
            """
            Recursively adds a child resource to the resources list
            """
            self._resources[resource.name] = resource
            for req in resource.requires:
                _add_child_resource(dynamic_resources[req])

        _add_child_resource(resource)
        # Initialize the resource graph again with the update resources
        self._initialize_resource_graph()
        self._find_current_resource()

    def duplicate_dynamic_resource(self, original: res.Resource) -> None:
        raise NotImplementedError()
        suffix = (
            len(
                [
                    i
                    for i in self._resources
                    if self.get_resource(i).name.startswith(
                        original.name.split("_")[0] + "_"
                    )
                ]
            )
            + 1
        )

        def _recursive_deep_copy(resource: res.Resource) -> None:
            nonlocal suffix, self
            new_resource = res.RESOURCE_MAP[resource.type](**resource.__dict__)
            prefix = "_".join(new_resource.name.split("_")[:-1])
            new_resource.name = prefix + f"_{suffix}"
            new_resource.requires = [
                "_".join(rn.split("_")[:-1]) + f"_{suffix}"
                for rn in new_resource.requires
            ]
            self._resources[new_resource.name] = new_resource
            print("!!!!!!New resource: ", new_resource.__dict__)
            for child in self._resource_graph[resource]["children"]:
                _recursive_deep_copy(child)

        for parent in self._resource_graph[original]["parents"]:
            parent.requires.append(f"Pizza_{suffix}")

        _recursive_deep_copy(original)
        # Initialize the resource graph again with the update resources
        self._initialize_resource_graph()
        self._find_current_resource()

    def hotword_activated(self) -> None:
        # TODO: Add some checks if we accidentally go into this while the dialogue is ongoing
        self._in_this_dialogue = True
        # Set up resources for working with them
        self._initialize_resources()
        # Set dialogue as newest active dialogue
        self._active_dialogues.append((self._dialogue_name, self.current_resource.name))

    def pause_dialogue(self) -> None:
        ...  # TODO

    def resume_dialogue(self) -> None:
        ...  # TODO

    def not_in_dialogue(self) -> bool:
        """Check if the client is in or wants to start this dialogue"""
        return not self._in_this_dialogue

    @property
    def dialogue_name(self) -> Optional[str]:
        if hasattr(self, "_dialogue_name"):
            return self._dialogue_name
        return None

    @property
    def active_dialogue(self) -> Optional[str]:
        return self._active_dialogues[-1][0] if self._active_dialogues else None

    @property
    def current_resource(self) -> res.Resource:
        if self._current_resource is None:
            self._find_current_resource()
        assert self._current_resource is not None
        return self._current_resource

    def get_resource(self, name: str) -> res.Resource:
        return self._resources[name]

    @property
    def extras(self) -> Dict[str, Any]:
        return self._extras

    @property
    def timed_out(self) -> bool:
        return self._timed_out

    def get_descendants(
        self, resource: res.Resource, filter_func: Optional[FilterFuncType] = None
    ) -> List[res.Resource]:
        """
        Given a resource and an optional filter function
        (with a resource and the depth in tree as args, returns a boolean),
        returns all descendants of the resource that match the function
        (all of them if filter_func is None).
        Returns the descendants in preorder
        """
        descendants: List[res.Resource] = []

        def _recurse_descendants(
            resource: res.Resource, depth: int, filter_func: FilterFuncType
        ) -> None:
            nonlocal descendants
            for child in self._resource_graph[resource]["children"]:
                if filter_func(child, depth):
                    descendants.append(child)
                _recurse_descendants(child, depth + 1, filter_func)

        _recurse_descendants(resource, 0, filter_func or _ALLOW_ALL_FILTER)
        return descendants

    def get_children(self, resource: res.Resource) -> List[res.Resource]:
        """Given a resource, returns all children of the resource"""
        return self._resource_graph[resource]["children"]

    def get_ancestors(
        self, resource: res.Resource, filter_func: Optional[FilterFuncType] = None
    ) -> List[res.Resource]:
        """
        Given a resource and an optional filter function
        (with a resource and the depth in tree as args, returns a boolean),
        returns all ancestors of the resource that match the function
        (all of them if filter_func is None).
        """
        ancestors: List[res.Resource] = []

        def _recurse_ancestors(
            resource: res.Resource, depth: int, filter_func: FilterFuncType
        ) -> None:
            nonlocal ancestors
            for parent in self._resource_graph[resource]["parents"]:
                if filter_func(parent, depth):
                    ancestors.append(parent)
                _recurse_ancestors(parent, depth + 1, filter_func)

        _recurse_ancestors(resource, 0, filter_func or _ALLOW_ALL_FILTER)
        return ancestors

    def get_parents(self, resource: res.Resource) -> List[res.Resource]:
        """Given a resource, returns all parents of the resource"""
        return self._resource_graph[resource]["parents"]

    def get_answer(
        self, answering_functions: AnsweringFunctionMap, result: Any
    ) -> Optional[AnswerTuple]:
        if self._answer_tuple is not None:
            return self._answer_tuple
        self._find_current_resource()
        assert self._current_resource is not None
        self._answering_functions = answering_functions

        # Check if dialogue was cancelled # TODO: Change this (have separate cancel method)
        if self._current_resource.is_cancelled:
            self._answer_tuple = self._answering_functions[_FINAL_RESOURCE_NAME](
                self._current_resource, self, result
            )
            if not self._answer_tuple:
                raise ValueError("No answer for cancelled dialogue")
            return self._answer_tuple

        resource_name = self._current_resource.name.split("_")[0]
        if resource_name in self._answering_functions:
            print("GENERATING ANSWER FOR ", resource_name)
            ans = self._answering_functions[resource_name](
                self._current_resource, self, result
            )
            return ans
        # Iterate through resources (postorder traversal)
        # until one generates an answer
        self._answer_tuple = self._get_answer(self._current_resource, result, set())

        return self._answer_tuple

    # TODO: Can we remove this function?
    def _get_answer(
        self, curr_resource: res.Resource, result: Any, finished: Set[res.Resource]
    ) -> Optional[AnswerTuple]:
        for resource in self._resource_graph[curr_resource]["children"]:
            if resource not in finished:
                finished.add(resource)
                ans = self._get_answer(resource, result, finished)
                if ans:
                    return ans
        if curr_resource.name in self._answering_functions:
            return self._answering_functions[curr_resource.name](
                curr_resource, self, result
            )
        return None

    def set_answer(self, answer: AnswerTuple) -> None:
        self._answer_tuple = answer

    def set_resource_state(self, resource_name: str, state: res.ResourceState):
        """
        Set the state of a resource.
        Sets state of all parent resources to unfulfilled
        if cascade_state is set to True for the resource.
        """
        resource = self._resources[resource_name]
        lowered_state = resource.state > state
        resource.state = state
        if state == res.ResourceState.FULFILLED and not resource.needs_confirmation:
            resource.state = res.ResourceState.CONFIRMED
            return
        if resource.cascade_state and lowered_state:
            # Find all parent resources and set to corresponding state
            ancestors = set(self.get_ancestors(resource))
            for anc in ancestors:
                anc.state = res.ResourceState.UNFULFILLED

    def _find_current_resource(self) -> None:
        """
        Finds the current resource in the resource graph
        using a postorder traversal of the resource graph.
        """
        curr_res: Optional[res.Resource] = None
        finished_resources: Set[res.Resource] = set()

        def _recurse_resources(resource: res.Resource) -> None:
            nonlocal curr_res, finished_resources
            finished_resources.add(resource)
            if resource.is_confirmed or resource.is_skipped:
                # Don't set resource as current if it is confirmed or skipped
                return
            # Current resource is neither confirmed nor skipped,
            # so we try to find candidates lower in the tree first
            for child in self._resource_graph[resource]["children"]:
                if child not in finished_resources:
                    _recurse_resources(child)  # TODO: Unwrap recursion?
                if curr_res is not None:
                    # Found a suitable resource, stop looking
                    return
            curr_res = resource
            while not curr_res.prefer_over_wrapper:
                wrapper_parents = [
                    par
                    for par in self._resource_graph[curr_res]["parents"]
                    if isinstance(par, res.WrapperResource)
                ]
                assert (
                    len(wrapper_parents) <= 1
                ), "A resource cannot have more than one wrapper parent"
                if wrapper_parents:
                    curr_res = wrapper_parents[0]
                else:
                    break

        _recurse_resources(self._resources[_FINAL_RESOURCE_NAME])
        if curr_res is not None:
            print("CURRENT RESOURCE IN FIND CURRENT RESOURCE: ", curr_res.name)
        self._current_resource = curr_res or self._resources[_FINAL_RESOURCE_NAME]

    # TODO: Can we move this function into set_resource_state?
    def skip_other_resources(
        self, or_resource: res.OrResource, resource: res.Resource
    ) -> None:
        """Skips other resources in the or resource"""
        # TODO: Check whether OrResource is exclusive or not
        assert isinstance(
            or_resource, res.OrResource
        ), f"{or_resource} is not an OrResource"
        for r in or_resource.requires:
            if r != resource.name:
                self.set_resource_state(r, res.ResourceState.SKIPPED)

    # TODO: Can we move this function into set_resource_state?
    def update_wrapper_state(self, wrapper: res.WrapperResource) -> None:
        """
        Updates the state of the wrapper resource
        based on the state of its children.
        """
        if wrapper.state == res.ResourceState.UNFULFILLED:
            print("Wrapper is unfulfilled")
            if all(
                [
                    child.state == res.ResourceState.UNFULFILLED
                    for child in self._resource_graph[wrapper]["children"]
                ]
            ):
                print("All children are unfulfilled")
                return
            print("At least one child is fulfilled")
            self.set_resource_state(wrapper.name, res.ResourceState.PARTIALLY_FULFILLED)
        if wrapper.state == res.ResourceState.PARTIALLY_FULFILLED:
            print("Wrapper is partially fulfilled")
            if any(
                [
                    child.state != res.ResourceState.CONFIRMED
                    for child in self._resource_graph[wrapper]["children"]
                ]
            ):
                print("At least one child is not confirmed")
                self.set_resource_state(
                    wrapper.name, res.ResourceState.PARTIALLY_FULFILLED
                )
                return
            print("All children are confirmed")
            self.set_resource_state(wrapper.name, res.ResourceState.FULFILLED)

    def finish_dialogue(self) -> None:
        """Set the dialogue as finished."""
        self._finished = True

    def serialize_data(self) -> Dict[str, Optional[str]]:
        """Serialize the dialogue's data for saving to database"""
        if self._resources[_FINAL_RESOURCE_NAME].is_confirmed:
            # When final resource is confirmed, the dialogue is over
            self.finish_dialogue()
        ds_json: Optional[str] = None
        if not self._finished and not self._timed_out:
            print("!!!!!!!!!!!!!!!Serializing data! with resources: ", self._resources)
            ds_json = json.dumps(
                {
                    _RESOURCES_KEY: self._resources,
                    _EXTRAS_KEY: self._extras,
                },
            )
        # Wrap data before saving dialogue state into client data
        # (due to custom JSON serialization)
        cd: Dict[str, Optional[str]] = {self._dialogue_name: ds_json}
        return cd

    ################################
    #        Database functions    #
    ################################

    def _get_active_dialogues(self) -> ActiveDialogueList:
        """Get list of active dialogues from database for current client."""
        active: ActiveDialogueList = []

        if self._client_id:
            with SessionContext(session=self._db_session, read_only=True) as session:
                try:
                    row: Optional[DB_QueryData] = (
                        session.query(DB_QueryData)
                        .filter(DB_QueryData.client_id == self._client_id)  # type: ignore
                        .filter(DB_QueryData.key == _ACTIVE_DIALOGUE_KEY)
                    ).one_or_none()
                    if row is not None:
                        active = cast(ActiveDialogueList, row.data)
                except Exception as e:
                    logging.error(
                        "Error fetching client '{0}' query data for key '{1}' from db: {2}".format(
                            self._client_id, _ACTIVE_DIALOGUE_KEY, e
                        )
                    )
        return active

    def _dialogue_data(self) -> Optional[DialogueDataRow]:
        """
        Fetch client_id-associated dialogue data stored
        in the dialoguedata table based on the dialogue key.
        """
        assert (
            self._client_id and self._dialogue_name
        ), "_dialogue_data() called without client ID or dialogue name!"

        with SessionContext(session=self._db_session, read_only=True) as session:
            try:
                row: Optional[DB_DialogueData] = (
                    session.query(DB_DialogueData)
                    .filter(DB_DialogueData.dialogue_key == self._dialogue_name)  # type: ignore
                    .filter(DB_DialogueData.client_id == self._client_id)
                ).one_or_none()
                if row:
                    return {
                        "data": cast(DialogueSerialized, row.data),
                        "expires_at": cast(datetime.datetime, row.expires_at),
                    }
            except Exception as e:
                logging.error(
                    "Error fetching client '{0}' dialogue data for key '{1}' from db: {2}".format(
                        self._client_id, self._dialogue_name, e
                    )
                )
        return None

    def update_dialogue_data(self) -> None:
        """
        Save current state of dialogue to dialoguedata table in database,
        along with updating list of active dialogues in querydata table.
        """
        if not self._client_id or not self._dialogue_name:
            # Need both client ID and dialogue name to save any state
            return

        now = datetime.datetime.now()
        expires_at = now + datetime.timedelta(seconds=self._expiration_time)
        with SessionContext(session=self._db_session, commit=True) as session:
            try:
                existing_dd_row: Optional[DB_DialogueData] = session.get(  # type: ignore
                    DB_DialogueData, (self._client_id, self._dialogue_name)
                )
                # Write data to dialoguedata table
                if existing_dd_row:
                    # UPDATE existing row
                    existing_dd_row.modified = now  # type: ignore
                    existing_dd_row.data = _dialogue_serializer(  # type: ignore
                        {
                            _RESOURCES_KEY: self._resources.values(),
                            _EXTRAS_KEY: self._extras,
                        }
                    )
                    existing_dd_row.expires_at = expires_at  # type: ignore
                else:
                    # INSERT new row
                    dialogue_row = DB_DialogueData(
                        client_id=self._client_id,
                        dialogue_key=self._dialogue_name,
                        created=now,
                        modified=now,
                        data=_dialogue_serializer(
                            {
                                _RESOURCES_KEY: self._resources.values(),
                                _EXTRAS_KEY: self._extras,
                            }
                        ),
                        expires_at=expires_at,
                    )
                    session.add(dialogue_row)  # type: ignore
            except Exception as e:
                logging.error(
                    "Error upserting client '{0}' dialogue data for key '{1}' into db: {2}".format(
                        self._client_id, self._dialogue_name, e
                    )
                )
            try:
                # Write active dialogues to querydata table
                existing_qd_row: Optional[DB_QueryData] = session.get(  # type: ignore
                    DB_QueryData, (self._client_id, _ACTIVE_DIALOGUE_KEY)
                )
                if existing_qd_row:
                    # TODO: Move this into some prettier place
                    # Make sure the (dialogue name, current resource) pair is up to date for this dialogue
                    self._active_dialogues = [
                        (x, y)
                        if x != self._dialogue_name
                        else (x, self.current_resource.name)
                        for x, y in self._active_dialogues
                    ]
                    # UPDATE existing row
                    existing_qd_row.data = self._active_dialogues  # type: ignore
                    existing_qd_row.modified = now  # type: ignore
                else:
                    # INSERT new row
                    querydata_row = DB_QueryData(
                        client_id=self._client_id,
                        key=_ACTIVE_DIALOGUE_KEY,
                        created=now,
                        modified=now,
                        data=self._active_dialogues,
                    )
                    session.add(querydata_row)  # type: ignore
            except Exception as e:
                logging.error(
                    "Error upserting client '{0}' dialogue data for key '{1}' into db: {2}".format(
                        self._client_id, self._dialogue_name, e
                    )
                )
        return
