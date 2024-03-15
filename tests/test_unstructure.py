import re
from dataclasses import dataclass
from types import UnionType
from typing import NewType

import pytest
from compages import (
    UnstructureDataclassToDict,
    Unstructurer,
    UnstructuringError,
    simple_unstructure,
    unstructure_as_dict,
    unstructure_as_int,
    unstructure_as_list,
    unstructure_as_str,
    unstructure_as_union,
)
from compages.path import DictKey, DictValue, ListElem, StructField, UnionVariant

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

    @simple_unstructure
    def unstructure_as_custom_generic(val):
        return val

    unstructurer = Unstructurer(
        lookup_handlers={
            int: unstructure_as_int,
            HexInt: unstructure_as_hex_int,
            list[int]: unstructure_as_custom_generic,
            list: unstructure_as_list,
        },
        sequential_handlers=[UnstructureDataclassToDict()],
    )

    result = unstructurer.unstructure_as(
        Container,
        Container(regular_int=1, hex_int=2, other_int=3, generic=[4, 5], custom_generic=[6, 7]),
    )
    assert result == dict(
        regular_int=1, hex_int="0x2", other_int=3, generic=["0x4", "0x5"], custom_generic=[6, 7]
    )


def test_unstructure_generators():
    @dataclass
    class Container:
        x: int

    @simple_unstructure
    def unstructure_container(val):
        to_lower_level = Container(val.x + 10)
        from_lower_level = yield to_lower_level
        return {"x": from_lower_level["x"] * 2}

    unstructurer = Unstructurer(
        lookup_handlers={
            int: unstructure_as_int,
            Container: unstructure_container,
        },
        sequential_handlers=[UnstructureDataclassToDict()],
    )

    assert unstructurer.unstructure_as(Container, Container(x=1)) == {"x": 22}


def test_unstructure_no_finalizing_handler():
    # Checks that an appropriate error is raised if all the found handlers
    # turned out to be generators, and there was no regular function
    # that would allow us to unroll the stack.

    @dataclass
    class Container:
        x: int

    class MyUnstructureDataclass:
        def applies(self, _unstructure_as, _val):
            return True

        def __call__(self, _unstructurer, _unstructure_as, val):
            new_val = yield val
            return new_val

    unstructurer = Unstructurer(
        sequential_handlers=[MyUnstructureDataclass()],
    )

    with pytest.raises(
        UnstructuringError, match="Could not find a non-generator handler to unstructure as"
    ):
        unstructurer.unstructure_as(Container, Container(x=1))


def test_unstructure_routing_handler_not_found():
    unstructurer = Unstructurer()

    with pytest.raises(UnstructuringError) as exc:
        unstructurer.unstructure_as(int, 1)
    expected = UnstructuringError("No handlers registered to unstructure as <class 'int'>")
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

    unstructurer = Unstructurer(
        lookup_handlers={
            UnionType: unstructure_as_union,
            list: unstructure_as_list,
            dict: unstructure_as_dict,
            int: unstructure_as_int,
            str: unstructure_as_str,
        },
        sequential_handlers=[UnstructureDataclassToDict()],
    )

    data = Outer(x="a", y=Inner(u=1.2, d={"a": "b", 1: 2}, lst=[1, "a"]))
    with pytest.raises(UnstructuringError) as exc:
        unstructurer.unstructure_as(Outer, data)
    expected = UnstructuringError(
        "Cannot unstructure as",
        [
            (StructField("x"), UnstructuringError("The value must be of type `int`")),
            (
                StructField("y"),
                UnstructuringError(
                    "Cannot unstructure as",
                    [
                        (
                            StructField("u"),
                            UnstructuringError(
                                r"Cannot unstructure as int | str",
                                [
                                    (
                                        UnionVariant(int),
                                        UnstructuringError("The value must be of type `int`"),
                                    ),
                                    (
                                        UnionVariant(str),
                                        UnstructuringError("The value must be of type `str`"),
                                    ),
                                ],
                            ),
                        ),
                        (
                            StructField("d"),
                            UnstructuringError(
                                r"Cannot unstructure as dict\[int, str\]",
                                [
                                    (
                                        DictKey("a"),
                                        UnstructuringError("The value must be of type `int`"),
                                    ),
                                    (
                                        DictValue(1),
                                        UnstructuringError("The value must be of type `str`"),
                                    ),
                                ],
                            ),
                        ),
                        (
                            StructField("lst"),
                            UnstructuringError(
                                r"Cannot unstructure as list\[int\]",
                                [
                                    (
                                        ListElem(1),
                                        UnstructuringError("The value must be of type `int`"),
                                    )
                                ],
                            ),
                        ),
                    ],
                ),
            ),
        ],
    )

    assert_exception_matches(exc.value, expected)

    exc_str = """
Cannot unstructure as <class 'test_unstructure.test_error_rendering.<locals>.Outer'>
  x: The value must be of type `int`
  y: Cannot unstructure as <class 'test_unstructure.test_error_rendering.<locals>.Inner'>
    y.u: Cannot unstructure as int | str
      y.u.<int>: The value must be of type `int`
      y.u.<str>: The value must be of type `str`
    y.d: Cannot unstructure as dict[int, str]
      y.d.key(a): The value must be of type `int`
      y.d.[1]: The value must be of type `str`
    y.lst: Cannot unstructure as list[int]
      y.lst.[1]: The value must be of type `int`
""".strip()

    assert str(exc.value) == exc_str
