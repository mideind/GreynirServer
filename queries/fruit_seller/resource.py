from typing import Any, Union, List, Optional

from enum import Enum, auto
from datetime import datetime
from dataclasses import dataclass

BaseResourceTypes = Union[str, int, float, bool, datetime, None]
ListResourceType = List[BaseResourceTypes]


class ResourceState(Enum):
    UNFULFILLED = auto()
    PARTIALLY_FULFILLED = auto()
    FULFILLED = auto()
    CONFIRMED = auto()
    # SKIPPED = auto()


@dataclass
class Resource:
    required: bool = True
    data: Any = None
    state: ResourceState = ResourceState.UNFULFILLED
    prompt: str = ""
    repeat_prompt: Optional[str] = None
    confirm_prompt: Optional[str] = None
    cancel_prompt: Optional[str] = None
    _repeat_count: int = 0

    def next_action(self) -> Any:
        raise NotImplementedError()


class ListResource(Resource):
    data: ListResourceType = []
    available_options: Optional[ListResourceType] = None

    def list_available_options(self) -> str:
        raise NotImplementedError()


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
