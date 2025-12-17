from dataclasses import dataclass, field
from typing import NamedTuple

import pytest
from compages._struct_like import (
    Field,
    StructAdapterError,
    get_fields_dataclass,
    get_fields_named_tuple,
)


def test_get_fields_named_tuple():
    class Container(NamedTuple):
        x: int
        y: str = "foo"

    fields = get_fields_named_tuple(Container)

    assert fields == [Field(name="x", type=int), Field(name="y", type=str, default="foo")]


def test_get_fields_named_tuple_hint_resolution():
    class Container(NamedTuple):
        x: "int"

    fields = get_fields_named_tuple(Container)

    assert fields == [Field(name="x", type=int)]

    class Container2(NamedTuple):
        x: "int2"  # noqa: F821

    with pytest.raises(
        StructAdapterError,
        match="Field type annotation cannot be resolved: name 'int2' is not defined",
    ):
        get_fields_named_tuple(Container2)


def test_get_fields_named_tuple_type_check():
    with pytest.raises(StructAdapterError, match="Expected a named tuple, got <class 'str'>"):
        get_fields_named_tuple(str)


def test_get_fields_dataclass():
    def factory():
        return "foo"

    metadata = {"a": "b"}

    @dataclass
    class Container:
        w: str = field(metadata=metadata)
        x: int
        y: str = "foo"
        z: str = field(default_factory=factory)

    fields = get_fields_dataclass(Container)

    assert fields == [
        Field(name="w", type=str, metadata=metadata),
        Field(name="x", type=int, metadata={}),
        Field(name="y", type=str, default="foo", metadata={}),
        Field(name="z", type=str, default_factory=factory, metadata={}),
    ]


def test_get_fields_dataclass_hint_resolution():
    @dataclass
    class Container:
        x: "int"

    fields = get_fields_dataclass(Container)

    assert fields == [Field(name="x", type=int, metadata={})]

    @dataclass
    class Container2:
        x: "int2"  # noqa: F821

    with pytest.raises(
        StructAdapterError,
        match="Field type annotation cannot be resolved: name 'int2' is not defined",
    ):
        get_fields_dataclass(Container2)


def test_get_fields_dataclass_type_check():
    with pytest.raises(StructAdapterError, match="Expected a dataclass, got <class 'str'>"):
        get_fields_dataclass(str)
