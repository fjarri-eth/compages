import re
from dataclasses import dataclass
from types import UnionType
from typing import NewType

import pytest
from compages import (
    DataclassBase,
    IntoDataclassFromMapping,
    IntoDict,
    IntoInt,
    IntoList,
    IntoStr,
    IntoUnion,
    StructureHandler,
    Structurer,
    StructuringError,
)
from compages.path import DictKey, DictValue, ListElem, StructField, UnionVariant

HexInt = NewType("HexInt", int)


OtherInt = NewType("OtherInt", int)


class HexIntoInt(StructureHandler):
    def simple_structure(self, val):
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
    # A smoke test for a combination of types requiring different handling.

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

    class AllIntsListIntoSelf(StructureHandler):
        def simple_structure(self, val):
            assert isinstance(val, list)
            assert all(isinstance(elem, int) for elem in val)
            return val

    structurer = Structurer(
        {
            int: IntoInt(),
            HexInt: HexIntoInt(),
            list[int]: AllIntsListIntoSelf(),
            list: IntoList(),
            DataclassBase: IntoDataclassFromMapping(),
        }
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


def test_structure_generators():
    @dataclass
    class Container:
        x: int

    class IntoContainer(StructureHandler):
        def simple_structure(self, val):
            to_lower_level = {"x": val["x"] + 10}
            from_lower_level = yield to_lower_level
            return Container(x=from_lower_level.x * 2)

    structurer = Structurer(
        {
            int: IntoInt(),
            Container: IntoContainer(),
            DataclassBase: IntoDataclassFromMapping(),
        }
    )

    assert structurer.structure_into(Container, {"x": 1}) == Container(x=22)


def test_structure_no_finalizing_handler():
    # Checks that an appropriate error is raised if all the found handlers
    # turned out to be generators, and there was no regular function
    # that would allow us to unroll the stack.

    @dataclass
    class Container:
        x: int

    class PassThrough(StructureHandler):
        def structure(self, _context, val):
            new_val = yield val
            return new_val

    structurer = Structurer({DataclassBase: PassThrough()})

    with pytest.raises(
        StructuringError, match="Could not find a non-generator handler to structure into"
    ):
        structurer.structure_into(Container, {"x": 1})


def test_structure_routing_handler_not_found():
    structurer = Structurer()

    with pytest.raises(StructuringError) as exc:
        structurer.structure_into(int, 1)
    expected = StructuringError("No handlers registered to structure `1` into <class 'int'>")
    assert_exception_matches(exc.value, expected)


def test_structure_handler_fallback():
    class Foo(StructureHandler):
        pass

    structurer = Structurer({int: Foo()})

    message = re.escape(
        "`StructureHandler` must implement either `structure()` or `simple_structure()`"
    )
    with pytest.raises(NotImplementedError, match=message) as exc:
        structurer.structure_into(int, 1)


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
        {
            UnionType: IntoUnion(),
            list: IntoList(),
            dict: IntoDict(),
            int: IntoInt(),
            str: IntoStr(),
            DataclassBase: IntoDataclassFromMapping(),
        }
    )

    data = {"x": "a", "y": {"u": 1.2, "d": {"a": "b", 1: 2}, "lst": [1, "a"]}}
    with pytest.raises(StructuringError) as exc:
        structurer.structure_into(Outer, data)
    expected = StructuringError(
        "Failed to structure a dict into",
        [
            (StructField("x"), StructuringError("The value must be an integer")),
            (
                StructField("y"),
                StructuringError(
                    "Failed to structure a dict into",
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
Failed to structure a dict into <class 'test_structure.test_error_rendering.<locals>.Outer'>
  x: The value must be an integer
  y: Failed to structure a dict into <class 'test_structure.test_error_rendering.<locals>.Inner'>
    y.u: Cannot structure into int | str
      y.u.<int>: The value must be an integer
      y.u.<str>: The value must be a string
    y.d: Cannot structure into dict[int, str]
      y.d.key(a): The value must be an integer
      y.d.[1]: The value must be a string
    y.lst: Cannot structure into list[int]
      y.lst.[1]: The value must be an integer
""".strip()

    assert str(exc.value) == exc_str
