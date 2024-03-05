import re
from dataclasses import dataclass
from types import UnionType

import pytest
from compages import (
    UnstructureDataclassToDict,
    UnstructureDataclassToList,
    Unstructurer,
    UnstructuringError,
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


def test_unstructure_as_none():
    unstructurer = Unstructurer(handlers={type(None): unstructure_as_none})
    assert unstructurer.unstructure_as(type(None), None) is None

    with pytest.raises(UnstructuringError) as exc:
        unstructurer.unstructure_as(type(None), 1)
    expected = UnstructuringError("The value must be `None`")
    assert_exception_matches(exc.value, expected)


def test_unstructure_as_float():
    unstructurer = Unstructurer(handlers={float: unstructure_as_float})
    assert unstructurer.unstructure_as(float, 1.5) == 1.5

    with pytest.raises(UnstructuringError) as exc:
        unstructurer.unstructure_as(float, "a")
    expected = UnstructuringError("The value must be a floating-point number")
    assert_exception_matches(exc.value, expected)


def test_unstructure_as_bool():
    unstructurer = Unstructurer(handlers={bool: unstructure_as_bool})
    assert unstructurer.unstructure_as(bool, True) is True
    assert unstructurer.unstructure_as(bool, False) is False

    with pytest.raises(UnstructuringError) as exc:
        unstructurer.unstructure_as(bool, "a")
    expected = UnstructuringError("The value must be a boolean")
    assert_exception_matches(exc.value, expected)


def test_unstructure_as_str():
    unstructurer = Unstructurer(handlers={str: unstructure_as_str})
    assert unstructurer.unstructure_as(str, "abc") == "abc"

    with pytest.raises(UnstructuringError) as exc:
        unstructurer.unstructure_as(str, 1)
    expected = UnstructuringError("The value must be a string")
    assert_exception_matches(exc.value, expected)


def test_unstructure_as_bytes():
    unstructurer = Unstructurer(handlers={bytes: unstructure_as_bytes})
    assert unstructurer.unstructure_as(bytes, b"abc") == b"abc"

    with pytest.raises(UnstructuringError) as exc:
        unstructurer.unstructure_as(bytes, 1)
    expected = UnstructuringError("The value must be a bytestring")
    assert_exception_matches(exc.value, expected)


def test_unstructure_as_int():
    unstructurer = Unstructurer(handlers={int: unstructure_as_int})
    assert unstructurer.unstructure_as(int, 1) == 1

    with pytest.raises(UnstructuringError) as exc:
        unstructurer.unstructure_as(int, "a")
    expected = UnstructuringError("The value must be an integer")
    assert_exception_matches(exc.value, expected)

    # Specifically test that a boolean is not accepted,
    # even though it is a subclass of int in Python.
    with pytest.raises(UnstructuringError) as exc:
        unstructurer.unstructure_as(int, True)
    expected = UnstructuringError("The value must be an integer")
    assert_exception_matches(exc.value, expected)


def test_unstructure_as_union():
    unstructurer = Unstructurer(
        handlers={UnionType: unstructure_as_union, int: unstructure_as_int, str: unstructure_as_str}
    )
    assert unstructurer.unstructure_as(int | str, "a") == "a"
    assert unstructurer.unstructure_as(int | str, 1) == 1

    with pytest.raises(UnstructuringError) as exc:
        unstructurer.unstructure_as(int | str, 1.2)
    expected = UnstructuringError(
        r"Cannot unstructure as int | str",
        [
            (UnionVariant(int), UnstructuringError("The value must be an integer")),
            (UnionVariant(str), UnstructuringError("The value must be a string")),
        ],
    )
    assert_exception_matches(exc.value, expected)


def test_unstructure_as_tuple():
    unstructurer = Unstructurer(
        handlers={tuple: unstructure_as_tuple, int: unstructure_as_int, str: unstructure_as_str}
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
        [(ListElem(1), UnstructuringError("The value must be a string"))],
    )
    assert_exception_matches(exc.value, expected)


def test_unstructure_as_list():
    unstructurer = Unstructurer(handlers={list: unstructure_as_list, int: unstructure_as_int})

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
        [(ListElem(1), UnstructuringError("The value must be an integer"))],
    )
    assert_exception_matches(exc.value, expected)


def test_unstructure_as_dict():
    unstructurer = Unstructurer(
        handlers={dict: unstructure_as_dict, int: unstructure_as_int, str: unstructure_as_str}
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
        [(DictKey("a"), UnstructuringError("The value must be an integer"))],
    )
    assert_exception_matches(exc.value, expected)

    # Error structuring a value
    with pytest.raises(UnstructuringError) as exc:
        unstructurer.unstructure_as(dict[int, str], {1: "a", 2: 3})
    expected = UnstructuringError(
        r"Cannot unstructure as dict\[int, str\]",
        [(DictValue(2), UnstructuringError("The value must be a string"))],
    )
    assert_exception_matches(exc.value, expected)


def test_unstructure_dataclass_to_dict():
    unstructurer = Unstructurer(
        handlers={int: unstructure_as_int, str: unstructure_as_str},
        predicate_handlers=[
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
        [(StructField("y"), UnstructuringError("The value must be a string"))],
    )
    assert_exception_matches(exc.value, expected)


def test_unstructure_dataclass_to_list():
    unstructurer = Unstructurer(
        handlers={int: unstructure_as_int, str: unstructure_as_str},
        predicate_handlers=[UnstructureDataclassToList()],
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
        [(StructField("y"), UnstructuringError("The value must be a string"))],
    )
    assert_exception_matches(exc.value, expected)
