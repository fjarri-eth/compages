import re
from dataclasses import dataclass
from types import UnionType
from typing import NewType

import pytest
from compages import (
    UnstructureDataclassToDict,
    UnstructureDataclassToList,
    Unstructurer,
    UnstructuringError,
    simple_typechecked_unstructure,
    simple_unstructure,
    unstructure_as_bool,
    unstructure_as_bytes,
    unstructure_as_dict,
    unstructure_as_float,
    unstructure_as_int,
    unstructure_as_list,
    unstructure_as_none,
    unstructure_as_str,
    unstructure_as_tuple,
    unstructure_as_union,
)
from compages.path import DictKey, DictValue, ListElem, StructField, UnionVariant


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


def test_simple_typechecked_unstructure():
    A = NewType("A", int)
    B = NewType("B", A)

    @simple_typechecked_unstructure
    def unstructure_int(val):
        return val

    assert unstructure_int(None, A, 1) == 1
    assert unstructure_int(None, B, 1) == 1
    assert unstructure_int(None, int, 1) == 1

    with pytest.raises(UnstructuringError, match="The value must be of type `int`"):
        unstructure_int(None, A, "a")
    with pytest.raises(UnstructuringError, match="The value must be of type `int`"):
        unstructure_int(None, B, "a")
    with pytest.raises(UnstructuringError, match="The value must be of type `int`"):
        unstructure_int(None, int, "a")


def test_unstructure_as_none():
    unstructurer = Unstructurer(lookup_handlers={type(None): unstructure_as_none})
    assert unstructurer.unstructure_as(type(None), None) is None

    with pytest.raises(UnstructuringError) as exc:
        unstructurer.unstructure_as(type(None), 1)
    expected = UnstructuringError("The value must be of type `NoneType`")
    assert_exception_matches(exc.value, expected)


def test_unstructure_as_float():
    unstructurer = Unstructurer(lookup_handlers={float: unstructure_as_float})
    assert unstructurer.unstructure_as(float, 1.5) == 1.5

    with pytest.raises(UnstructuringError) as exc:
        unstructurer.unstructure_as(float, "a")
    expected = UnstructuringError("The value must be of type `float`")
    assert_exception_matches(exc.value, expected)


def test_unstructure_as_bool():
    unstructurer = Unstructurer(lookup_handlers={bool: unstructure_as_bool})
    assert unstructurer.unstructure_as(bool, True) is True
    assert unstructurer.unstructure_as(bool, False) is False

    with pytest.raises(UnstructuringError) as exc:
        unstructurer.unstructure_as(bool, "a")
    expected = UnstructuringError("The value must be of type `bool`")
    assert_exception_matches(exc.value, expected)


def test_unstructure_as_str():
    unstructurer = Unstructurer(lookup_handlers={str: unstructure_as_str})
    assert unstructurer.unstructure_as(str, "abc") == "abc"

    with pytest.raises(UnstructuringError) as exc:
        unstructurer.unstructure_as(str, 1)
    expected = UnstructuringError("The value must be of type `str`")
    assert_exception_matches(exc.value, expected)


def test_unstructure_as_bytes():
    unstructurer = Unstructurer(lookup_handlers={bytes: unstructure_as_bytes})
    assert unstructurer.unstructure_as(bytes, b"abc") == b"abc"

    with pytest.raises(UnstructuringError) as exc:
        unstructurer.unstructure_as(bytes, 1)
    expected = UnstructuringError("The value must be of type `bytes`")
    assert_exception_matches(exc.value, expected)


def test_unstructure_as_int():
    unstructurer = Unstructurer(lookup_handlers={int: unstructure_as_int})
    assert unstructurer.unstructure_as(int, 1) == 1

    with pytest.raises(UnstructuringError) as exc:
        unstructurer.unstructure_as(int, "a")
    expected = UnstructuringError("The value must be of type `int`")
    assert_exception_matches(exc.value, expected)

    # Specifically test that a boolean is not accepted,
    # even though it is a subclass of int in Python.
    with pytest.raises(UnstructuringError) as exc:
        unstructurer.unstructure_as(int, True)
    expected = UnstructuringError("The value must be of type `int`")
    assert_exception_matches(exc.value, expected)


def test_unstructure_as_union():
    unstructurer = Unstructurer(
        lookup_handlers={
            UnionType: unstructure_as_union,
            int: unstructure_as_int,
            str: unstructure_as_str,
        }
    )
    assert unstructurer.unstructure_as(int | str, "a") == "a"
    assert unstructurer.unstructure_as(int | str, 1) == 1

    with pytest.raises(UnstructuringError) as exc:
        unstructurer.unstructure_as(int | str, 1.2)
    expected = UnstructuringError(
        r"Cannot unstructure as int | str",
        [
            (UnionVariant(int), UnstructuringError("The value must be of type `int`")),
            (UnionVariant(str), UnstructuringError("The value must be of type `str`")),
        ],
    )
    assert_exception_matches(exc.value, expected)


def test_unstructure_as_tuple():
    unstructurer = Unstructurer(
        lookup_handlers={
            tuple: unstructure_as_tuple,
            int: unstructure_as_int,
            str: unstructure_as_str,
        }
    )

    assert unstructurer.unstructure_as(tuple[()], []) == []
    assert unstructurer.unstructure_as(tuple[int, str], [1, "a"]) == [1, "a"]
    assert unstructurer.unstructure_as(tuple[int, str], (1, "a")) == [1, "a"]
    assert unstructurer.unstructure_as(tuple[int, ...], (1, 2, 3)) == [1, 2, 3]

    with pytest.raises(UnstructuringError) as exc:
        unstructurer.unstructure_as(tuple[int, str], {"x": 1, "y": "a"})
    expected = UnstructuringError("Can only unstructure a Sequence as a tuple")
    assert_exception_matches(exc.value, expected)

    with pytest.raises(UnstructuringError) as exc:
        unstructurer.unstructure_as(tuple[int, str, int], [1, "a"])
    expected = UnstructuringError("Not enough elements to unstructure as a tuple: got 2, need 3")
    assert_exception_matches(exc.value, expected)

    with pytest.raises(UnstructuringError) as exc:
        unstructurer.unstructure_as(tuple[int], [1, "a"])
    expected = UnstructuringError("Too many elements to unstructure as a tuple: got 2, need 1")
    assert_exception_matches(exc.value, expected)

    with pytest.raises(UnstructuringError) as exc:
        unstructurer.unstructure_as(tuple[int, str], [1, 1.2])
    expected = UnstructuringError(
        r"Cannot unstructure as tuple\[int, str\]",
        [(ListElem(1), UnstructuringError("The value must be of type `str`"))],
    )
    assert_exception_matches(exc.value, expected)


def test_unstructure_as_list():
    unstructurer = Unstructurer(
        lookup_handlers={list: unstructure_as_list, int: unstructure_as_int}
    )

    assert unstructurer.unstructure_as(list[int], [1, 2, 3]) == [1, 2, 3]
    assert unstructurer.unstructure_as(list[int], (1, 2, 3)) == [1, 2, 3]

    with pytest.raises(UnstructuringError) as exc:
        unstructurer.unstructure_as(list[int], {"x": 1, "y": "a"})
    expected = UnstructuringError("Can only unstructure a Sequence as a list")
    assert_exception_matches(exc.value, expected)

    with pytest.raises(UnstructuringError) as exc:
        unstructurer.unstructure_as(list[int], [1, "a"])
    expected = UnstructuringError(
        r"Cannot unstructure as list\[int\]",
        [(ListElem(1), UnstructuringError("The value must be of type `int`"))],
    )
    assert_exception_matches(exc.value, expected)


def test_unstructure_as_dict():
    unstructurer = Unstructurer(
        lookup_handlers={
            dict: unstructure_as_dict,
            int: unstructure_as_int,
            str: unstructure_as_str,
        }
    )

    assert unstructurer.unstructure_as(dict[int, str], {1: "a", 2: "b"}) == {1: "a", 2: "b"}

    with pytest.raises(UnstructuringError) as exc:
        unstructurer.unstructure_as(dict[int, str], [(1, "a"), (2, "b")])
    expected = UnstructuringError("Can only unstructure a Mapping as a dict")
    assert_exception_matches(exc.value, expected)

    # Error structuring a key
    with pytest.raises(UnstructuringError) as exc:
        unstructurer.unstructure_as(dict[int, str], {"a": "b", 2: "c"})
    expected = UnstructuringError(
        r"Cannot unstructure as dict\[int, str\]",
        [(DictKey("a"), UnstructuringError("The value must be of type `int`"))],
    )
    assert_exception_matches(exc.value, expected)

    # Error structuring a value
    with pytest.raises(UnstructuringError) as exc:
        unstructurer.unstructure_as(dict[int, str], {1: "a", 2: 3})
    expected = UnstructuringError(
        r"Cannot unstructure as dict\[int, str\]",
        [(DictValue(2), UnstructuringError("The value must be of type `str`"))],
    )
    assert_exception_matches(exc.value, expected)


def test_unstructure_dataclass_to_dict():
    unstructurer = Unstructurer(
        lookup_handlers={int: unstructure_as_int, str: unstructure_as_str},
        sequential_handlers=[
            UnstructureDataclassToDict(name_converter=lambda name, _metadata: name + "_")
        ],
    )

    @dataclass
    class Container:
        x: int
        y: str
        z: str

    assert unstructurer.unstructure_as(Container, Container(x=1, y="a", z="b")) == {
        "x_": 1,
        "y_": "a",
        "z_": "b",
    }

    with pytest.raises(UnstructuringError) as exc:
        unstructurer.unstructure_as(Container, Container(x=1, y=2, z="b"))
    expected = UnstructuringError(
        "Cannot unstructure as",
        [(StructField("y"), UnstructuringError("The value must be of type `str`"))],
    )
    assert_exception_matches(exc.value, expected)


def test_unstructure_dataclass_to_dict_skip_defaults():
    # Badly behaving classes that raise an error on comparison,
    # so the unstructurer will have to process that when we're comparing
    # `z=A()` with the default `B()`

    class A:
        def __eq__(self, other):
            if not isinstance(other, A):
                raise TypeError("type mismatch")
            return True

    class B:
        def __eq__(self, other):
            if not isinstance(other, A):
                raise TypeError("type mismatch")
            return True

        # Have to define this to be able to use it as a default in a dataclass
        def __hash__(self):
            return 1

    b = B()

    @dataclass
    class Container:
        x: int
        y: str = "b"
        z: A | B = b

    @simple_unstructure
    def unstructure_a(_val):
        return "A"

    @simple_unstructure
    def unstructure_b(_val):
        return "B"

    unstructurer = Unstructurer(
        lookup_handlers={
            UnionType: unstructure_as_union,
            A: unstructure_a,
            B: unstructure_b,
            int: unstructure_as_int,
            str: unstructure_as_str,
        },
        sequential_handlers=[UnstructureDataclassToDict()],
    )

    # `y` will not be present in the results since its value is equal to the default one
    assert unstructurer.unstructure_as(Container, Container(x=1, y="b", z=A())) == {
        "x": 1,
        "z": "A",
    }


def test_unstructure_dataclass_to_list():
    unstructurer = Unstructurer(
        lookup_handlers={int: unstructure_as_int, str: unstructure_as_str},
        sequential_handlers=[UnstructureDataclassToList()],
    )

    @dataclass
    class Container:
        x: int
        y: str
        z: str

    assert unstructurer.unstructure_as(Container, Container(x=1, y="a", z="b")) == [1, "a", "b"]

    with pytest.raises(UnstructuringError) as exc:
        unstructurer.unstructure_as(Container, Container(x=1, y=2, z="b"))
    expected = UnstructuringError(
        "Cannot unstructure as",
        [(StructField("y"), UnstructuringError("The value must be of type `str`"))],
    )
    assert_exception_matches(exc.value, expected)
