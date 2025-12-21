from collections import namedtuple
from dataclasses import dataclass
from types import UnionType
from typing import Any, NamedTuple, NewType, Union

import pytest
from compages._common import (
    DataclassBase,
    GeneratorStack,
    NamedTupleBase,
    Result,
    get_lookup_order,
    isinstance_ext,
)


def test_normal_operation():
    ref_context = "some context"
    stack = GeneratorStack(ref_context, ["a"])

    assert stack.is_empty()

    # `None` is just ignored, and stack is not finalized
    assert stack.push(None) is Result.UNDEFINED

    def f1(context, val):
        assert context == ref_context
        new_val = yield [*val, "b"]
        return [*new_val, "c"]

    # We pushed a generator, so the stack is not finalized yet
    assert stack.push(f1) is Result.UNDEFINED

    def f2(context, val):
        assert context == ref_context
        return [*val, "d"]

    # This is a normal function, so the stack is finalized and unrolled
    assert stack.push(f2) == ["a", "b", "d", "c"]


def test_multiple_yields():
    ref_context = "some context"
    stack = GeneratorStack(ref_context, ["a"])

    def f1(context, val):
        assert context == ref_context
        new_val = yield [*val, "b"]
        new_val = yield [*new_val, "d"]
        return [*val, "c"]

    # We can't tell that there is a second yield until we start unrolling, so this passes
    stack.push(f1)

    def f2(context, val):
        assert context == ref_context
        return [*val, "d"]

    with pytest.raises(RuntimeError, match="Expected only one yield in a generator"):
        stack.push(f2)


def test_isinstance_ext():
    class A:
        pass

    class B(A):
        pass

    C = NewType("C", int)
    D = NewType("D", C)

    assert isinstance_ext(B(), get_lookup_order(A))
    assert not isinstance_ext(A(), get_lookup_order(B))
    assert isinstance_ext(1, get_lookup_order(D))
    assert isinstance_ext([1], get_lookup_order(list[int]))

    # Anything is an instance of `Any`
    assert isinstance_ext(1, [Any])
    assert isinstance_ext(None, [Any])

    # Note: `isinstance_ext()` cannot introspect the value
    assert isinstance_ext(["a"], get_lookup_order(list[int]))

    assert isinstance_ext(1, get_lookup_order(int | str))

    # Since the value cannot be introspected any value is `isinstance_ext(..., UnionType)`
    assert isinstance_ext(None, get_lookup_order(int | str))
    assert isinstance_ext(None, get_lookup_order(Union[int, str]))  # noqa: UP007


def test_lookup_order():
    class A:
        pass

    class B(A):
        pass

    C = NewType("C", int)
    D = NewType("D", C)
    E = NewType("E", list[D])

    assert get_lookup_order(B) == [B, A]
    assert get_lookup_order(list[A]) == [list[A], list]
    assert get_lookup_order(C) == [C, int]
    assert get_lookup_order(D) == [D, C, int]
    assert get_lookup_order(E) == [E, list[D], list]
    assert get_lookup_order(int | str) == [int | str, UnionType]
    assert get_lookup_order(Union[int, str]) == [Union[int, str], Union]  # noqa: UP007

    @dataclass
    class DataclassContainer:
        x: int

    assert get_lookup_order(DataclassContainer) == [DataclassContainer, DataclassBase]

    class NamedTupleContainer(NamedTuple):
        x: int

    assert get_lookup_order(NamedTupleContainer) == [NamedTupleContainer, NamedTupleBase, tuple]

    # Test that `namedtuple`-created classes pass the check as well
    NamedTupleContainerAlt = namedtuple("NamedTupleContainerAlt", ["x"])  # noqa: PYI024
    assert get_lookup_order(NamedTupleContainerAlt) == [
        NamedTupleContainerAlt,
        NamedTupleBase,
        tuple,
    ]
