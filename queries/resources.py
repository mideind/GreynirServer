from typing import (
    Any,
    Callable,
    Dict,
    Mapping,
    List,
    Optional,
    Type,
)

import json
import datetime
from enum import IntFlag, auto
from dataclasses import dataclass, field


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
    # Used for comparing states (which one is earlier/later in the dialogue)
    order_index: int = 0

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

    def format_data(self, format_func: Optional[Callable[[Any], str]] = None) -> str:
        if format_func:
            return format_func(self.data)
        return ",".join(str(x) for x in self.data)


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

    # def confirm_children(self, dsm: "DialogueStateManager") -> None:
    #     """Confirm all child/required resources."""
    #     ConfirmResource._confirm_children(self, dsm)

    # @staticmethod
    # def _confirm_children(
    #     res: Resource,
    #     dsm: "DialogueStateManager",
    # ) -> None:
    #     for req in res.requires:
    #         req_res = dsm.get_resource(req)
    #         if not isinstance(req_res, ConfirmResource):
    #             ConfirmResource._confirm_children(req_res, dsm)
    #             req_res.state = ResourceState.CONFIRMED


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


###################################
#    ENCODING/DECODING CLASSES    #
###################################


# Add any new resource types here (for encoding/decoding)
RESOURCE_MAP: Mapping[str, Type[Resource]] = {
    "Resource": Resource,
    "DateResource": DateResource,
    "DatetimeResource": DatetimeResource,
    "FinalResource": FinalResource,
    "ListResource": ListResource,
    "NumberResource": NumberResource,
    "OrResource": OrResource,
    "TimeResource": TimeResource,
    "WrapperResource": WrapperResource,
    "YesNoResource": YesNoResource,
}


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
        if t == "datetime":
            return datetime.datetime(**d)
        if t == "date":
            return datetime.date(**d)
        if t == "time":
            return datetime.time(**d)
        return RESOURCE_MAP[t](**d)
