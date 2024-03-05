import re
from dataclasses import dataclass
from types import UnionType
from typing import NewType

import pytest
from compages import (
    StructureDictIntoDataclass,
    Structurer,
    StructuringError,
    simple_structure,
    structure_into_dict,
    structure_into_int,
    structure_into_list,
    structure_into_str,
    structure_into_union,
)
from compages.path import DictKey, DictValue, ListElem, StructField, UnionVariant

HexInt = NewType("HexInt", int)


OtherInt = NewType("OtherInt", int)


@simple_structure
def structure_hex_int(val):
    if not isinstance(val, str) or not val.startswith("0x"):
        raise StructuringError("The value must be a hex-encoded integer")
    return int(val, 0)


# TODO (#5): duplicate
def assert_exception_matches(exc, reference_exc):
    assert isinstance(exc, StructuringError)
    assert re.match(reference_exc.message, exc.message)
    assert len(exc.inner_errors) == len(reference_exc.inner_errors)
    for (inner_path, inner_exc), (ref_path, ref_exc) in zip(
        exc.inner_errors, reference_exc.inner_errors, strict=True
    ):
        assert inner_path == ref_path
        assert_exception_matches(inner_exc, ref_exc)


def test_structure_routing():
    # Test possible options for handling a given type.

    @dataclass
    class Container:
        # a regular type, will have a handler for it
        regular_int: int
        # a newtype, will have a handler for it
        hex_int: HexInt
        # a newtype with no handler, will fallback to the `int` handler
        other_int: OtherInt
        # will be routed to the handler for all `list` generics
        generic: list[HexInt]
        # will have a specific `list[int]` handler, which takes priority over the generic `list` one
        custom_generic: list[int]

    @simple_structure
    def structure_custom_generic(val):
        assert isinstance(val, list)
        assert all(isinstance(elem, int) for elem in val)
        return val

    structurer = Structurer(
        handlers={
            int: structure_into_int,
            HexInt: structure_hex_int,
            list[int]: structure_custom_generic,
            list: structure_into_list,
        },
        predicate_handlers=[StructureDictIntoDataclass()],
    )

    result = structurer.structure_into(
        Container,
        dict(
            regular_int=1, hex_int="0x2", other_int=3, generic=["0x4", "0x5"], custom_generic=[6, 7]
        ),
    )
    assert result == Container(
        regular_int=1, hex_int=2, other_int=3, generic=[4, 5], custom_generic=[6, 7]
    )


def test_structure_routing_handler_not_found():
    structurer = Structurer()

    with pytest.raises(StructuringError) as exc:
        structurer.structure_into(int, 1)
    expected = StructuringError("No handlers registered to structure into <class 'int'>")
    assert_exception_matches(exc.value, expected)


def test_structure_routing_error_wrapping():
    structurer = Structurer(
        handlers={int: structure_into_int}, predicate_handlers=[StructureDictIntoDataclass()]
    )

    @dataclass
    class Container:
        x: int

    with pytest.raises(StructuringError) as exc:
        structurer.structure_into(Container, {"x": "a"})
    expected = StructuringError(
        "Cannot structure a dict into a dataclass",
        [(StructField("x"), StructuringError("The value must be an integer"))],
    )
    assert_exception_matches(exc.value, expected)


def test_error_rendering():
    @dataclass
    class Inner:
        u: int | str
        d: dict[int, str]
        lst: list[int]

    @dataclass
    class Outer:
        x: int
        y: Inner

    structurer = Structurer(
        handlers={
            UnionType: structure_into_union,
            list: structure_into_list,
            dict: structure_into_dict,
            int: structure_into_int,
            str: structure_into_str,
        },
        predicate_handlers=[StructureDictIntoDataclass()],
    )

    data = {"x": "a", "y": {"u": 1.2, "d": {"a": "b", 1: 2}, "lst": [1, "a"]}}
    with pytest.raises(StructuringError) as exc:
        structurer.structure_into(Outer, data)
    expected = StructuringError(
        "Cannot structure a dict into a dataclass",
        [
            (StructField("x"), StructuringError("The value must be an integer")),
            (
                StructField("y"),
                StructuringError(
                    "Cannot structure a dict into a dataclass",
                    [
                        (
                            StructField("u"),
                            StructuringError(
                                r"Cannot structure into int | str",
                                [
                                    (
                                        UnionVariant(int),
                                        StructuringError("The value must be an integer"),
                                    ),
                                    (
                                        UnionVariant(str),
                                        StructuringError("The value must be a string"),
                                    ),
                                ],
                            ),
                        ),
                        (
                            StructField("d"),
                            StructuringError(
                                r"Cannot structure into dict\[int, str\]",
                                [
                                    (
                                        DictKey("a"),
                                        StructuringError("The value must be an integer"),
                                    ),
                                    (DictValue(1), StructuringError("The value must be a string")),
                                ],
                            ),
                        ),
                        (
                            StructField("lst"),
                            StructuringError(
                                r"Cannot structure into list\[int\]",
                                [(ListElem(1), StructuringError("The value must be an integer"))],
                            ),
                        ),
                    ],
                ),
            ),
        ],
    )

    assert_exception_matches(exc.value, expected)

    exc_str = """
Cannot structure a dict into a dataclass <class 'test_structure.test_error_rendering.<locals>.Outer'>
  x: The value must be an integer
  y: Cannot structure a dict into a dataclass <class 'test_structure.test_error_rendering.<locals>.Inner'>
    y.u: Cannot structure into int | str
      y.u.<int>: The value must be an integer
      y.u.<str>: The value must be a string
    y.d: Cannot structure into dict[int, str]
      y.d.key(a): The value must be an integer
      y.d.[1]: The value must be a string
    y.lst: Cannot structure into list[int]
      y.lst.[1]: The value must be an integer
""".strip()  # noqa: E501

    assert str(exc.value) == exc_str
