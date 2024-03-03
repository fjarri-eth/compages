import re
from dataclasses import dataclass
from typing import Dict, List, NewType, Tuple, Union

import pytest

from ordinatio import (
    HandlingError,
    StructureDataclassFromDict,
    StructureDataclassFromList,
    Structurer,
    StructuringError,
    simple_structure,
    structure_dict,
    structure_int,
    structure_list,
    structure_none,
    structure_str,
    structure_tuple,
    structure_union,
)

HexInt = NewType("HexInt", int)


OtherInt = NewType("OtherInt", int)


@simple_structure
def structure_hex_int(val):
    if not isinstance(val, str) or not val.startswith("0x"):
        raise HandlingError("The value must be a hex-encoded integer")
    return int(val, 0)


def assert_exception_matches(exc, reference_exc):
    if isinstance(reference_exc, StructuringError):
        assert isinstance(exc, StructuringError)
        assert exc.path == reference_exc.path
        assert re.match(reference_exc.message, exc.message)
        assert len(exc.inner_errors) == len(reference_exc.inner_errors)
        for inner, reference_inner in zip(exc.inner_errors, reference_exc.inner_errors):
            assert_exception_matches(inner, reference_inner)

    else:
        assert issubclass(type(exc), type(reference_exc))
        assert re.match(str(reference_exc), str(exc))


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
        generic: List[HexInt]
        # will have a specific `List[int]` handler, which takes priority over the generic `list` one
        custom_generic: List[int]

    @simple_structure
    def structure_custom_generic(val):
        assert isinstance(val, list) and all(isinstance(elem, int) for elem in val)
        return val

    structurer = Structurer(
        handlers={
            int: structure_int,
            HexInt: structure_hex_int,
            List[int]: structure_custom_generic,
            list: structure_list,
        },
        predicate_handlers=[StructureDataclassFromDict()],
    )

    result = structurer.structure(
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
        structurer.structure(int, 1)
    expected = StructuringError([], "No handlers registered to structure into <class 'int'>")
    assert_exception_matches(exc.value, expected)


def test_structure_routing_error_wrapping():
    structurer = Structurer(
        handlers={int: structure_int}, predicate_handlers=[StructureDataclassFromDict()]
    )

    @dataclass
    class Container:
        x: int

    with pytest.raises(StructuringError) as exc:
        structurer.structure(Container, {"x": "a"})
    expected = StructuringError(
        [],
        "Cannot structure a dict into a dataclass",
        [StructuringError(["x"], "The value must be an integer")],
    )
    assert_exception_matches(exc.value, expected)


def test_error_rendering():
    @dataclass
    class Inner:
        d: Dict[int, str]
        l: List[int]

    @dataclass
    class Outer:
        x: int
        y: Inner

    structurer = Structurer(
        handlers={
            list: structure_list,
            dict: structure_dict,
            int: structure_int,
            str: structure_str,
        },
        predicate_handlers=[StructureDataclassFromDict()],
    )

    data = {"x": "a", "y": {"d": {"a": "b", 1: 2}, "l": [1, "a"]}}
    with pytest.raises(StructuringError) as exc:
        structurer.structure(Outer, data)
    expected = StructuringError(
        [],
        "Cannot structure a dict into a dataclass",
        [
            StructuringError(["x"], "The value must be an integer"),
            StructuringError(
                ["y"],
                "Cannot structure a dict into a dataclass",
                [
                    StructuringError(
                        ["y", "d"],
                        r"Could not structure into typing\.Dict\[int, str\]",
                        [
                            StructuringError(
                                ["y", "d", 0, "<key>"], "The value must be an integer"
                            ),
                            StructuringError(["y", "d", 1, "<val>"], "The value must be a string"),
                        ],
                    ),
                    StructuringError(
                        ["y", "l"],
                        r"Could not structure into typing\.List\[int\]",
                        [StructuringError(["y", "l", 1], "The value must be an integer")],
                    ),
                ],
            ),
        ],
    )
    assert_exception_matches(exc.value, expected)

    exc_str = """
Cannot structure a dict into a dataclass <class 'test_structure.test_error_rendering.<locals>.Outer'>
  x: The value must be an integer
  y: Cannot structure a dict into a dataclass <class 'test_structure.test_error_rendering.<locals>.Inner'>
    y.d: Could not structure into typing.Dict[int, str]
      y.d.0.<key>: The value must be an integer
      y.d.1.<val>: The value must be a string
    y.l: Could not structure into typing.List[int]
      y.l.1: The value must be an integer
""".strip()

    print(str(exc.value))

    assert str(exc.value) == exc_str
