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


    Collection of resource types for dialogues.
    Resources are slots for information extracted from dialogue.

"""
from typing import (
    Any,
    Dict,
    Mapping,
    List,
    MutableMapping,
    Optional,
    Type,
    Union,
)

import datetime
from enum import IntFlag, auto
from dataclasses import dataclass, field as data_field
from marshmallow import Schema, fields, post_load

_json_types = Union[None, int, bool, str, List["_json_types"], Dict[str, "_json_types"]]


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


# Map resource name to type (for encoding/decoding)
RESOURCE_MAP: MutableMapping[str, Type["Resource"]] = {}
RESOURCE_SCHEMAS: MutableMapping[str, Type["ResourceSchema"]] = {}

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
    type: str = "Resource"
    # Contained data
    data: Any = None
    # Resource state (unfulfilled, partially fulfilled, etc.)
    state: ResourceState = ResourceState.UNFULFILLED
    # Resources that must be confirmed before moving on to this resource
    requires: List[str] = data_field(default_factory=list)
    # Dictionary containing different prompts/responses
    prompts: Mapping[str, str] = data_field(default_factory=dict)
    # When this resource's state is changed, change all parent resource states as well
    cascade_state: bool = False
    # When set to True, this resource will be used
    # as the current resource instead of its wrapper
    prefer_over_wrapper: bool = False
    # When set to True, this resource will need
    # to be confirmed before moving on to the next resource
    needs_confirmation: bool = False
    # Used for comparing states (which one is earlier/later in the dialogue)
    order_index: int = 0
    # Extra variables to be used for specific situations
    extras: Dict[str, Any] = data_field(default_factory=dict)

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

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Resource) and self.name == other.name

    def __repr__(self) -> str:
        return f"<{self.name}>"

    def __str__(self) -> str:
        return f"<{self.name}>"


class ResourceSchema(Schema):
    """
    Marshmallow schema for validation and
    serialization/deserialization of a resource class.
    """

    name = fields.Str(required=True)
    type = fields.Str(required=True)
    data = fields.Raw()
    state = fields.Enum(IntFlag, by_value=True, required=True)
    requires = fields.List(fields.Str(), required=True)
    prompts = fields.Mapping(fields.Str(), fields.Str())
    cascade_state = fields.Bool()
    prefer_over_wrapper = fields.Bool()
    needs_confirmation = fields.Bool()
    order_index = fields.Int()
    extras = fields.Dict(fields.Str(), fields.Inferred())

    @post_load
    def instantiate(self, data: Dict[str, Any], **kwargs: Dict[str, Any]):
        return RESOURCE_MAP[data["type"]](**data)


# Add resource to RESOURCE_MAP,
# should always be done for new Resource classes
RESOURCE_MAP[Resource.__name__] = Resource
# Add schema to RESOURCE_SCHEMAS,
# should also be done for new Resource classes
RESOURCE_SCHEMAS[Resource.__name__] = ResourceSchema


@dataclass(eq=False, repr=False)
class ListResource(Resource):
    """Resource representing a list of items."""

    data: List[Any] = data_field(default_factory=list)


class ListResourceSchema(ResourceSchema):
    data = fields.List(fields.Inferred())


RESOURCE_MAP[ListResource.__name__] = ListResource
RESOURCE_SCHEMAS[ListResource.__name__] = ListResourceSchema


@dataclass(eq=False, repr=False)
class DictResource(Resource):
    """Resource representing a dictionary of items."""

    data: Dict[str, Any] = data_field(default_factory=dict)


class DictResourceSchema(ResourceSchema):
    data = fields.Dict(fields.Str(), fields.Inferred())


RESOURCE_MAP[DictResource.__name__] = DictResource
RESOURCE_SCHEMAS[DictResource.__name__] = DictResourceSchema

# TODO: ?
# ExactlyOneResource (choose one resource from options)
# SetResource (a set of resources)?
# UserInfoResource (user info, e.g. name, age, home address, etc., can use saved data to autofill)
# ...


@dataclass(eq=False, repr=False)
class YesNoResource(Resource):
    """Resource representing a yes/no answer."""

    data: bool = False


class YesNoResourceSchema(ResourceSchema):
    data = fields.Bool()


RESOURCE_MAP[YesNoResource.__name__] = YesNoResource
RESOURCE_SCHEMAS[YesNoResource.__name__] = YesNoResourceSchema


@dataclass(eq=False, repr=False)
class DateResource(Resource):
    """Resource representing a date."""

    data: datetime.date = data_field(default_factory=datetime.date.today)


class DateResourceSchema(ResourceSchema):
    data = fields.Date()


RESOURCE_MAP[DateResource.__name__] = DateResource
RESOURCE_SCHEMAS[DateResource.__name__] = DateResourceSchema


@dataclass(eq=False, repr=False)
class TimeResource(Resource):
    """Resource representing a time (00:00-23:59)."""

    data: datetime.time = data_field(default_factory=datetime.time)


class TimeResourceSchema(ResourceSchema):
    data = fields.Time()


RESOURCE_MAP[TimeResource.__name__] = TimeResource
RESOURCE_SCHEMAS[TimeResource.__name__] = TimeResourceSchema


@dataclass(eq=False, repr=False)
class DatetimeResource(Resource):
    """Resource for wrapping date and time resources."""

    ...


class DatetimeResourceSchema(ResourceSchema):
    data = fields.NaiveDateTime()


RESOURCE_MAP[DatetimeResource.__name__] = DatetimeResource
RESOURCE_SCHEMAS[DatetimeResource.__name__] = DatetimeResourceSchema


@dataclass(eq=False, repr=False)
class NumberResource(Resource):
    """Resource representing a number."""

    data: int = 0


class NumberResourceSchema(ResourceSchema):
    data = fields.Int()


RESOURCE_MAP[NumberResource.__name__] = NumberResource
RESOURCE_SCHEMAS[NumberResource.__name__] = NumberResourceSchema


@dataclass(eq=False, repr=False)
class StringResource(Resource):
    """Resource representing a string."""

    data: str = ""


class StringResourceSchema(ResourceSchema):
    data = fields.Str()


RESOURCE_MAP[StringResource.__name__] = StringResource
RESOURCE_SCHEMAS[StringResource.__name__] = StringResourceSchema

# Wrapper, when multiple resources are required
@dataclass(eq=False, repr=False)
class WrapperResource(Resource):
    # Wrappers by default prefer to be the current
    # resource rather than a wrapper parent
    prefer_over_wrapper: bool = True


class WrapperResourceSchema(ResourceSchema):
    ...


RESOURCE_MAP[WrapperResource.__name__] = WrapperResource
RESOURCE_SCHEMAS[WrapperResource.__name__] = WrapperResourceSchema


@dataclass(eq=False, repr=False)
class OrResource(WrapperResource):
    ...


class OrResourceSchema(ResourceSchema):
    ...


RESOURCE_MAP[OrResource.__name__] = OrResource
RESOURCE_SCHEMAS[OrResource.__name__] = OrResourceSchema


@dataclass(eq=False, repr=False)
class FinalResource(Resource):
    """Resource representing the final state of a dialogue."""

    data: Any = None


class FinalResourceSchema(ResourceSchema):
    ...


RESOURCE_MAP[FinalResource.__name__] = FinalResource
RESOURCE_SCHEMAS[FinalResource.__name__] = FinalResourceSchema
