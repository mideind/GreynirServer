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


    Serialization/Deserialization functions for dialogue data and resources.

"""
from typing import Any, Callable, Dict, List, Mapping, Type, Union, cast
from typing_extensions import Required, TypedDict

import datetime
import json
import logging

import queries.extras.resources as res

_json_types = Union[None, int, bool, str, List["_json_types"], Dict[str, "_json_types"]]


class ResourceSerialized(Dict[str, _json_types], TypedDict, total=False):
    """
    Representation of a serialized resource
    and the required keys.
    """

    name: Required[str]
    type: Required[str]
    state: Required[res.ResourceState]


class DialogueDeserialized(TypedDict):
    """
    Representation of the dialogue structure,
    after it is loaded from the database and parsed.
    """

    resources: List[res.Resource]
    extras: Dict[str, _json_types]


class DialogueSerialized(TypedDict):
    """
    Representation of the dialogue structure,
    before it is saved to the database.
    """

    resources: List[ResourceSerialized]
    extras: str


def dialogue_serializer(data: DialogueDeserialized) -> DialogueSerialized:
    """
    Prepare the dialogue data for writing into the database.
    """
    return {
        "resources": [
            cast(ResourceSerialized, res.RESOURCE_SCHEMAS[s.type]().dump(s))
            for s in data["resources"]
        ],
        # We just dump the entire extras dict as a string
        "extras": json.dumps(data["extras"], cls=ExtendedJSONEncoder),
    }


def dialogue_deserializer(data: DialogueSerialized) -> DialogueDeserialized:
    """
    Prepare the dialogue data for working with
    after it has been loaded from the database.
    """
    return {
        "resources": [
            cast(res.Resource, res.RESOURCE_SCHEMAS[s["type"]]().load(s))
            for s in data["resources"]
        ],
        "extras": json.loads(data["extras"], cls=ExtendedJSONDecoder),
    }


class ExtendedJSONEncoder(json.JSONEncoder):
    # Map types other than resources to their serialized forms
    _serializer_functions: Mapping[Type[Any], Callable[[Any], _json_types]] = {
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

    def default(self, o: Any) -> Any:
        f = ExtendedJSONEncoder._serializer_functions.get(type(o))
        return f(o) if f else json.JSONEncoder.default(self, o)


class ExtendedJSONDecoder(json.JSONDecoder):
    _type_conversions: Mapping[str, Type[Any]] = {
        "datetime": datetime.datetime,
        "date": datetime.date,
        "time": datetime.time,
    }

    def __init__(self, *args: Any, **kwargs: Any):
        json.JSONDecoder.__init__(
            self, object_hook=self.dialogue_decoding, *args, **kwargs
        )

    def dialogue_decoding(self, d: Dict[Any, Any]) -> Any:
        if "__type__" not in d:
            return d
        t = d.pop("__type__")

        c = self._type_conversions.get(t)
        if c:
            return c(**d)
        logging.warning(f"No class found for __type__: {t}")
        d["__type__"] = t
        return d
