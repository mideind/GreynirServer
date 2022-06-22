from typing import Any, Dict, Union, List, Optional
from typing_extensions import TypedDict

from enum import IntEnum, auto
from datetime import datetime
from dataclasses import dataclass

from reynir import NounPhrase
from queries import natlang_seq, sing_or_plur

BaseResourceTypes = Union[str, int, float, bool, datetime, None]
ListResourceType = List[BaseResourceTypes]


def _list_items(items: Any) -> str:
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


class ListResource(Resource):
    data: ListResourceType = []
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
                ans = (
                    f"{self.repeat_prompt.format(list_items = _list_items(self.data))}"
                )
        if self.state is ResourceState.FULFILLED:
            if self.confirm_prompt:
                ans = (
                    f"{self.confirm_prompt.format(list_items = _list_items(self.data))}"
                )
        if self.state is ResourceState.CONFIRMED:
            ans = "Pöntunin er staðfest."
        return ans


# TODO:
# ExactlyOneResource (choose one resource from options)
# SetResource (a set of resources)?
# ...


class YesNoResource(Resource):
    data: Optional[bool] = None


class DatetimeResource(Resource):
    data: Optional[datetime] = None


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
