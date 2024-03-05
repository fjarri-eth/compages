import re
from dataclasses import dataclass
from typing import NewType

import pytest
from compages import (
    UnstructureDataclassToDict,
    Unstructurer,
    UnstructuringError,
    simple_unstructure,
    unstructure_as_int,
    unstructure_as_list,
)

HexInt = NewType("HexInt", int)


OtherInt = NewType("OtherInt", int)


# TODO (#5): duplicate
def assert_exception_matches(exc, reference_exc):
    assert isinstance(exc, UnstructuringError)
    assert re.match(reference_exc.message, exc.message)
    assert len(exc.inner_errors) == len(reference_exc.inner_errors)
    for (inner_path, inner_exc), (ref_path, ref_exc) in zip(
        exc.inner_errors, reference_exc.inner_errors, strict=True
    ):
        assert inner_path == ref_path
        assert_exception_matches(inner_exc, ref_exc)


@simple_unstructure
def unstructure_as_hex_int(val):
    return hex(val)


def test_unstructure_routing():
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

    @simple_unstructure
    def unstructure_as_custom_generic(val):
        return val

    unstructurer = Unstructurer(
        handlers={
            int: unstructure_as_int,
            HexInt: unstructure_as_hex_int,
            list[int]: unstructure_as_custom_generic,
            list: unstructure_as_list,
        },
        predicate_handlers=[UnstructureDataclassToDict()],
    )

    result = unstructurer.unstructure_as(
        Container,
        Container(regular_int=1, hex_int=2, other_int=3, generic=[4, 5], custom_generic=[6, 7]),
    )
    assert result == dict(
        regular_int=1, hex_int="0x2", other_int=3, generic=["0x4", "0x5"], custom_generic=[6, 7]
    )


def test_unstructure_routing_handler_not_found():
    unstructurer = Unstructurer()

    with pytest.raises(UnstructuringError) as exc:
        unstructurer.unstructure_as(int, 1)
    expected = UnstructuringError("No handlers registered to unstructure as <class 'int'>")
    assert_exception_matches(exc.value, expected)
