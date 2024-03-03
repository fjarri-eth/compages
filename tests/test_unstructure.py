from dataclasses import dataclass
from typing import List, NewType

import pytest

from ordinatio import (
    UnstructureDataclassAsDict,
    Unstructurer,
    UnstructuringError,
    unstructure_list,
)

HexInt = NewType("HexInt", int)


OtherInt = NewType("OtherInt", int)


def unstructure_int(unstructurer, unstructure_as, obj):
    return obj


def unstructure_hex_int(unstructurer, unstructure_as, obj):
    return hex(obj)


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
        generic: List[HexInt]
        # will have a specific `List[int]` handler, which takes priority over the generic `list` one
        custom_generic: List[int]

    def unstructure_custom_generic(unstructurer, unstructure_as, obj):
        return obj

    unstructurer = Unstructurer(
        handlers={
            int: unstructure_int,
            HexInt: unstructure_hex_int,
            List[int]: unstructure_custom_generic,
            list: unstructure_list,
        },
        predicate_handlers=[UnstructureDataclassAsDict()],
    )

    result = unstructurer.unstructure(
        Container(regular_int=1, hex_int=2, other_int=3, generic=[4, 5], custom_generic=[6, 7]),
    )
    assert result == dict(
        regular_int=1, hex_int="0x2", other_int=3, generic=["0x4", "0x5"], custom_generic=[6, 7]
    )
