from typing import (
    Any,
    Callable,
    Dict,
    Mapping,
    Set,
    List,
    Optional,
    TypeVar,
    cast,
)
from typing_extensions import TypedDict

import os.path
import json
import datetime

try:
    import tomllib  # type: ignore (module not available in Python <3.11)
except ModuleNotFoundError:
    import tomli as tomllib  # Used for Python <3.11

from queries import AnswerTuple
from queries.resources import (
    RESOURCE_MAP,
    Resource,
    DialogueJSONDecoder,
    DialogueJSONEncoder,
    ResourceState,
    WrapperResource,
)

# TODO:? Delegate answering from a resource to another resource or to another dialogue
# TODO:? í ávaxtasamtali "ég vil panta flug" "viltu að ég geymi ávaxtapöntunina eða eyði henni?" ...
# TODO: Add timezone info to json encoding/decoding?
# TODO: FIX TYPE HINTS (esp. 'Any')
# TODO: Add specific prompt handling to DSM to remove result from DSM.
# TODO: Add try-except blocks where appropriate

_TOML_FOLDER_NAME = "dialogues"
_EXPIRATION_TIME = 30 * 60  # a dialogue expires after 30 minutes
_FINAL_RESOURCE_NAME = "Final"

# Generic resource type
ResourceType_co = TypeVar("ResourceType_co", bound="Resource")

# Types for use in generating prompts/answers
AnsweringFunctionType = Callable[
    [ResourceType_co, "DialogueStateManager", Any], Optional[AnswerTuple]
]
# TODO: Fix 'Any' in type hint (Callable args are contravariant)
AnsweringFunctionMap = Mapping[str, AnsweringFunctionType[Any]]


################################
#    DIALOGUE STATE MANAGER    #
################################


class ResourceNotFoundError(Exception):
    ...


class ResourceGraphItem(TypedDict):
    """Type for a node in the resource graph."""

    children: List[Resource]
    parents: List[Resource]


# Dependency relationship graph type for resources
ResourceGraph = Dict[Resource, ResourceGraphItem]


class DialogueTOMLStructure(TypedDict):
    """Structure of a dialogue TOML file."""

    resources: List[Dict[str, Any]]


# Keys for accessing saved client data for dialogues
# (must match typed dict attributes below)
_RESOURCES_KEY = "resources"
_MODIFIED_KEY = "modified"
_EXTRAS_KEY = "extras"


class DialogueDBStructure(TypedDict):
    """
    Representation of the dialogue structure,
    as it is saved to the database.
    """

    resources: Dict[str, Resource]
    modified: datetime.datetime
    extras: Dict[str, Any]


class DialogueStateManager:
    DIALOGUE_DATA_KEY = "dialogue"

    def __init__(self, dialogue_name: str, saved_state: Optional[str] = None):
        self._dialogue_name: str = dialogue_name
        # Dict mapping resource name to resource instance
        self._resources: Dict[str, Resource] = {}
        # Boolean indicating if the client is in this dialogue
        self._in_this_dialogue: bool = False
        # Extra information saved with the dialogue state
        self._extras: Dict[str, Any] = {}
        # Answer for the current query
        self._answer_tuple: Optional[AnswerTuple] = None
        # Latest non-confirmed resource
        self._current_resource: Optional[Resource] = None
        # Dependency graph for the resources
        self._resource_graph: ResourceGraph = {}
        # Database data for this dialogue, if any
        self._saved_state: Optional[DialogueDBStructure] = None
        # Whether this dialogue is finished (successful/cancelled) or not
        self._finished: bool = False

        if isinstance(saved_state, str):
            self._saved_state = cast(
                DialogueDBStructure, json.loads(saved_state, cls=DialogueJSONDecoder)
            )
            time_from_last_interaction = (
                datetime.datetime.now() - self._saved_state[_MODIFIED_KEY]
            )
            # Check that we have saved data for this dialogue and that it is not expired
            if (
                self._saved_state[_RESOURCES_KEY]
                and time_from_last_interaction.total_seconds() < _EXPIRATION_TIME
            ):
                self._in_this_dialogue = True
                self.setup_resources()
            # TODO: IF EXPIRED DO SOMETHING

    def setup_resources(self) -> None:
        """
        Load dialogue resources from TOML file and update their state from database data.
        """
        # Fetch empty resources from TOML
        self._initialize_resources(self._dialogue_name)
        # Update empty resources with data from database
        for rname, resource in self._resources.items():
            if self._saved_state and rname in self._saved_state["resources"]:
                resource.update(self._saved_state[_RESOURCES_KEY][rname])
            # Change from int to enum type
            resource.state = ResourceState(resource.state)
        # Set extra data from database
        if self._saved_state and _EXTRAS_KEY in self._saved_state:
            self._extras = self._saved_state.get(_EXTRAS_KEY) or self._extras
        # Create resource dependency relationship graph
        print("SETTING UP RESOURCE GRAPH")
        self._initialize_resource_graph()
        print("FINISHED SETTING UP RESOURCE GRAPH")

    def _initialize_resource_graph(self) -> None:
        """
        Initializes the resource graph with each
        resource having children and parents according
        to what each resource requires.
        """
        for resource in self._resources.values():
            if resource.order_index == 0:
                self._initial_resource = resource
            self._resource_graph[resource] = {"children": [], "parents": []}

        for resource in self._resources.values():
            for req in resource.requires:
                self._resource_graph[self._resources[req]]["parents"].append(resource)
                self._resource_graph[resource]["children"].append(self._resources[req])
        print(self._resource_graph)

    def _initialize_resources(self, filename: str) -> None:
        """
        Loads dialogue structure from TOML file and
        fills self._resources with empty Resource instances.
        """
        basepath, _ = os.path.split(os.path.realpath(__file__))
        fpath = os.path.join(basepath, _TOML_FOLDER_NAME, filename + ".toml")
        with open(fpath, mode="r") as file:
            f = file.read()
        # Read TOML file containing a list of resources for the dialogue
        obj: DialogueTOMLStructure = tomllib.loads(f)  # type: ignore
        assert _RESOURCES_KEY in obj, f"No resources found in TOML file {f}"
        # Create resource instances from TOML data and return as a dict
        for i, resource in enumerate(obj[_RESOURCES_KEY]):
            assert "name" in resource, f"Name missing for resource {i+1}"
            if "type" not in resource:
                resource["type"] = "Resource"
            # Create instances of Resource classes (and its subclasses)
            self._resources[resource["name"]] = RESOURCE_MAP[resource["type"]](
                **resource, order_index=i
            )

    def hotword_activated(self) -> None:
        self._in_this_dialogue = True
        print("STARTING RESOURCE SETUP")
        self.setup_resources()
        print("FINISHED RESOURCE SETUP")

    def pause_dialogue(self) -> None:
        ...  # TODO

    def resume_dialogue(self) -> None:
        ...  # TODO

    def not_in_dialogue(self) -> bool:
        """Check if the client is in or wants to start this dialogue"""
        return not self._in_this_dialogue

    @property
    def current_resource(self) -> Resource:
        if self._current_resource is None:
            self._current_resource = self._find_current_resource()
        return self._current_resource

    def get_resource(self, name: str) -> Resource:
        return self._resources[name]

    @property
    def extras(self) -> Dict[str, Any]:
        return self._extras

    def get_answer(
        self, answering_functions: AnsweringFunctionMap, result: Any
    ) -> Optional[AnswerTuple]:
        if self._answer_tuple is not None:
            return self._answer_tuple
        self._current_resource = self._find_current_resource()
        self._answering_functions = answering_functions

        # Check if dialogue was cancelled # TODO: Change this (have separate cancel method)
        if self._current_resource.is_cancelled:
            self._answer_tuple = self._answering_functions[_FINAL_RESOURCE_NAME](
                self._current_resource, self, result
            )
            if not self._answer_tuple:
                raise ValueError("No answer for cancelled dialogue")
            return self._answer_tuple

        if self._current_resource.name in self._answering_functions:
            ans = self._answering_functions[self._current_resource.name](
                self._current_resource, self, result
            )
            return ans
        # Iterate through resources (inorder traversal)
        # until one generates an answer
        self._answer_tuple = self._get_answer_postorder(
            self._current_resource, result, set()
        )

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
            return self._answering_functions[curr_resource.name](
                curr_resource, self, result
            )
        return None

    def set_answer(self, answer: AnswerTuple) -> None:
        self._answer_tuple = answer

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

    def finish_dialogue(self) -> None:
        """Set the dialogue as finished."""
        self._finished = True

    def serialize_data(self) -> Dict[str, Optional[str]]:
        """Serialize the dialogue's data for saving to database"""
        if self._resources[_FINAL_RESOURCE_NAME].is_confirmed:
            # When final resource is confirmed, the dialogue is over
            self.finish_dialogue()
        ds_json: Optional[str] = None
        if not self._finished:
            ds_json = json.dumps(
                {
                    _RESOURCES_KEY: self._resources,
                    _MODIFIED_KEY: datetime.datetime.now(),
                    _EXTRAS_KEY: self._extras,
                },
                cls=DialogueJSONEncoder,
            )
        # Wrap data before saving dialogue state into client data
        # (due to custom JSON serialization)
        cd: Dict[str, Optional[str]] = {self._dialogue_name: ds_json}
        return cd
