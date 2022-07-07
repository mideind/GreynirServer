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

# Keys for accessing saved client data for dialogues
_DIALOGUE_KEY = "dialogue"
_DIALOGUE_NAME_KEY = "dialogue_name"
_DIALOGUE_RESOURCES_KEY = "resources"
_DIALOGUE_LAST_INTERACTED_WITH_KEY = "last_interacted_with"
_DIALOGUE_EXTRAS_KEY = "extras"
_EMPTY_DIALOGUE_DATA = "{}"
_FINAL_RESOURCE_NAME = "Final"
_CALLBACK_LOCATION = "callbacks"

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


################################
#    DIALOGUE STATE MANAGER    #
################################


class ResourceGraphItem(TypedDict):
    children: List[Resource]
    parents: List[Resource]


ResourceGraph = Dict[Resource, ResourceGraphItem]


class DialogueTOMLStructure(TypedDict):
    resources: List[Dict[str, Any]]


class DialogueDBStructure(TypedDict):
    """
    Representation of the dialogue structure,
    as it is saved to the database.
    """

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
        # Database data for this dialogue, if any
        self._saved_state: Optional[DialogueDBStructure] = None

        if isinstance(saved_state, str):
            # TODO: Add try-except block
            # TODO: Add check for datetime last interaction
            self._saved_state = cast(
                DialogueDBStructure, json.loads(saved_state, cls=DialogueJSONDecoder)
            )
            # Check that we have saved data for this dialogue
            if self._saved_state.get(_DIALOGUE_RESOURCES_KEY):
                self._in_this_dialogue = True
            self.setup_dialogue()  # TODO: Rename me

    def setup_dialogue(self) -> None:
        """
        Load dialogue structure from TOML file and update resource states from client data.
        Should be called after initializing an instance of
        DialogueStateManager and before calling get_answer.
        """
        resource_dict: Dict[str, Resource] = self._initialize_resources(
            self._dialogue_name
        )
        for rname, resource in resource_dict.items():
            if self._saved_state and rname in self._saved_state.get(
                _DIALOGUE_RESOURCES_KEY, {}
            ):
                # Update empty resource with data from database
                resource.update(self._saved_state[_DIALOGUE_RESOURCES_KEY][rname])
            # Change from int to enum type
            resource.state = ResourceState(resource.state)
            self._resources[rname] = resource
        if self._saved_state and _DIALOGUE_EXTRAS_KEY in self._saved_state:
            self._extras = self._saved_state.get(_DIALOGUE_EXTRAS_KEY) or self._extras

        self._initialize_resource_graph()

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

    def _initialize_resources(self, filename: str) -> Dict[str, Resource]:
        """Loads dialogue structure from TOML file."""
        basepath, _ = os.path.split(os.path.realpath(__file__))
        fpath = os.path.join(basepath, "dialogues", filename + ".toml")
        with open(fpath, mode="r") as file:
            f = file.read()
        obj: DialogueTOMLStructure = tomllib.loads(f)  # type: ignore
        assert _DIALOGUE_RESOURCES_KEY in obj
        resource_dict: Dict[str, Resource] = {}
        for i, resource in enumerate(obj[_DIALOGUE_RESOURCES_KEY]):
            assert "name" in resource
            if "type" not in resource:
                resource["type"] = "Resource"
            # Create instances of Resource classes (and its subclasses)
            resource_dict[resource["name"]] = RESOURCE_MAP[resource["type"]](
                **resource, order_index=i
            )
        return resource_dict

    def hotword_activated(self) -> None:
        self._in_this_dialogue = True
        self.setup_dialogue()

    def not_in_dialogue(self) -> bool:
        """Check if the client is in or wants to start this dialogue"""
        return not self._in_this_dialogue

    def _start_dialogue(self):
        """Save client's state as having started this dialogue"""
        # New empty dialogue state, with correct dialogue name
        self._set_dialogue_state(
            {
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

    def get_answer(
        self, answering_functions: AnsweringFunctionMap, result: Any
    ) -> Optional[AnswerTuple]:
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
            ans = self._answering_functions[self._current_resource.name](
                self._current_resource, self, result
            )
            print("GENERATED DATE ANSWERRRRRRRRRRRRRRRRR")
            return ans
        # Iterate through resources (inorder traversal)
        # until one generates an answer
        self._answer_tuple = self._get_answer_postorder(
            self._current_resource, result, set()
        )

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
            return self._answering_functions[curr_resource.name](
                curr_resource, self, result
            )
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

    def _set_dialogue_state(self, ds: DialogueDBStructure) -> None:
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
