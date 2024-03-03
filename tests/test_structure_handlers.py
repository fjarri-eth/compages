import re
from dataclasses import dataclass
from typing import Dict, List, NewType, Tuple, Union

import pytest

from ordinatio import (
    StructureDataclassFromDict,
    StructureDataclassFromList,
    Structurer,
    StructuringError,
    simple_structure,
    structure_bool,
    structure_bytes,
    structure_dict,
    structure_float,
    structure_int,
    structure_list,
    structure_none,
    structure_str,
    structure_tuple,
    structure_union,
)


# TODO: duplicate
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


def test_structure_none():
    structurer = Structurer(handlers={type(None): structure_none})
    assert structurer.structure(type(None), None) is None

    with pytest.raises(StructuringError) as exc:
        structurer.structure(type(None), 1)
    expected = StructuringError([], "The value is not `None`")
    assert_exception_matches(exc.value, expected)


def test_structure_float():
    structurer = Structurer(handlers={float: structure_float})
    assert structurer.structure(float, 1.5) == 1.5

    # Specifically allow integers, but check that they are converted to floats.
    res = structurer.structure(float, 1)
    assert isinstance(res, float) and res == 1.0

    with pytest.raises(StructuringError) as exc:
        structurer.structure(float, "a")
    expected = StructuringError([], "The value must be a floating-point number")
    assert_exception_matches(exc.value, expected)


def test_structure_bool():
    structurer = Structurer(handlers={bool: structure_bool})
    assert structurer.structure(bool, True) is True
    assert structurer.structure(bool, False) is False

    with pytest.raises(StructuringError) as exc:
        structurer.structure(bool, "a")
    expected = StructuringError([], "The value must be a boolean")
    assert_exception_matches(exc.value, expected)


def test_structure_str():
    structurer = Structurer(handlers={str: structure_str})
    assert structurer.structure(str, "abc") == "abc"

    with pytest.raises(StructuringError) as exc:
        structurer.structure(str, 1)
    expected = StructuringError([], "The value must be a string")
    assert_exception_matches(exc.value, expected)


def test_structure_bytes():
    structurer = Structurer(handlers={bytes: structure_bytes})
    assert structurer.structure(bytes, b"abc") == b"abc"

    with pytest.raises(StructuringError) as exc:
        structurer.structure(bytes, 1)
    expected = StructuringError([], "The value must be a bytestring")
    assert_exception_matches(exc.value, expected)


def test_structure_int():
    structurer = Structurer(handlers={int: structure_int})
    assert structurer.structure(int, 1) == 1

    with pytest.raises(StructuringError) as exc:
        structurer.structure(int, "a")
    expected = StructuringError([], "The value must be an integer")
    assert_exception_matches(exc.value, expected)

    # Specifically test that a boolean is not accepted,
    # even though it is a subclass of int in Python.
    with pytest.raises(StructuringError) as exc:
        structurer.structure(int, True)
    expected = StructuringError([], "The value must be an integer")
    assert_exception_matches(exc.value, expected)


def test_structure_union():
    structurer = Structurer(
        handlers={Union: structure_union, int: structure_int, str: structure_str}
    )
    assert structurer.structure(Union[int, str], "a") == "a"
    assert structurer.structure(Union[int, str], 1) == 1

    with pytest.raises(StructuringError) as exc:
        structurer.structure(Union[int, str], 1.2)
    expected = StructuringError(
        [],
        r"Could not structure into any of \(<class 'int'>, <class 'str'>\)",
        [
            StructuringError([], "The value must be an integer"),
            StructuringError([], "The value must be a string"),
        ],
    )
    assert_exception_matches(exc.value, expected)


def test_structure_tuple():
    structurer = Structurer(
        handlers={tuple: structure_tuple, int: structure_int, str: structure_str}
    )

    assert structurer.structure(Tuple[()], []) == ()
    assert structurer.structure(Tuple[int, str], [1, "a"]) == (1, "a")
    assert structurer.structure(Tuple[int, str], (1, "a")) == (1, "a")
    assert structurer.structure(Tuple[int, ...], (1, 2, 3)) == (1, 2, 3)

    with pytest.raises(StructuringError) as exc:
        structurer.structure(Tuple[int, str], {"x": 1, "y": "a"})
    expected = StructuringError([], "Can only structure a tuple or a list into a tuple generic")
    assert_exception_matches(exc.value, expected)

    with pytest.raises(StructuringError) as exc:
        structurer.structure(Tuple[int, str, int], [1, "a"])
    expected = StructuringError([], "Not enough elements to structure into a tuple: got 2, need 3")
    assert_exception_matches(exc.value, expected)

    with pytest.raises(StructuringError) as exc:
        structurer.structure(Tuple[int], [1, "a"])
    expected = StructuringError([], "Too many elements to structure into a tuple: got 2, need 1")
    assert_exception_matches(exc.value, expected)

    with pytest.raises(StructuringError) as exc:
        structurer.structure(Tuple[int, str], [1, 1.2])
    expected = StructuringError(
        [],
        r"Could not structure into typing\.Tuple\[int, str\]",
        [StructuringError([1], "The value must be a string")],
    )
    assert_exception_matches(exc.value, expected)


def test_structure_list():
    structurer = Structurer(handlers={list: structure_list, int: structure_int})

    assert structurer.structure(List[int], [1, 2, 3]) == [1, 2, 3]
    assert structurer.structure(List[int], (1, 2, 3)) == [1, 2, 3]

    with pytest.raises(StructuringError) as exc:
        structurer.structure(List[int], {"x": 1, "y": "a"})
    expected = StructuringError([], "Can only structure a tuple or a list into a list generic")
    assert_exception_matches(exc.value, expected)

    with pytest.raises(StructuringError) as exc:
        structurer.structure(List[int], [1, "a"])
    expected = StructuringError(
        [],
        r"Could not structure into typing\.List\[int\]",
        [StructuringError([1], "The value must be an integer")],
    )
    assert_exception_matches(exc.value, expected)


def test_structure_dict():
    structurer = Structurer(handlers={dict: structure_dict, int: structure_int, str: structure_str})

    assert structurer.structure(Dict[int, str], {1: "a", 2: "b"}) == {1: "a", 2: "b"}

    with pytest.raises(StructuringError) as exc:
        structurer.structure(Dict[int, str], [(1, "a"), (2, "b")])
    expected = StructuringError([], "Can only structure a dict into a dict generic")
    assert_exception_matches(exc.value, expected)

    # Error structuring a key
    with pytest.raises(StructuringError) as exc:
        structurer.structure(Dict[int, str], {"a": "b", 2: "c"})
    expected = StructuringError(
        [],
        r"Could not structure into typing\.Dict\[int, str\]",
        [StructuringError([0, "<key>"], "The value must be an integer")],
    )
    assert_exception_matches(exc.value, expected)

    # Error structuring a value
    with pytest.raises(StructuringError) as exc:
        structurer.structure(Dict[int, str], {1: "a", 2: 3})
    expected = StructuringError(
        [],
        r"Could not structure into typing\.Dict\[int, str\]",
        [StructuringError([1, "<val>"], "The value must be a string")],
    )
    assert_exception_matches(exc.value, expected)


def test_structure_dataclass_from_list():
    structurer = Structurer(
        handlers={int: structure_int, str: structure_str},
        predicate_handlers=[StructureDataclassFromList()],
    )

    @dataclass
    class Container:
        x: int
        y: str
        z: str = "default"

    assert structurer.structure(Container, [1, "a"]) == Container(x=1, y="a", z="default")
    assert structurer.structure(Container, [1, "a", "b"]) == Container(x=1, y="a", z="b")

    with pytest.raises(StructuringError) as exc:
        structurer.structure(Container, [1, "a", "b", 2])
    expected = StructuringError([], "Too many fields to serialize into")
    assert_exception_matches(exc.value, expected)

    with pytest.raises(StructuringError) as exc:
        structurer.structure(Container, [1])
    expected = StructuringError(
        [], "Cannot structure a list into a dataclass", [StructuringError(["y"], "Missing field")]
    )
    assert_exception_matches(exc.value, expected)

    with pytest.raises(StructuringError) as exc:
        structurer.structure(Container, [1, 2, "a"])
    expected = StructuringError(
        [],
        "Cannot structure a list into a dataclass",
        [StructuringError(["y"], "The value must be a string")],
    )
    assert_exception_matches(exc.value, expected)


def test_structure_dataclass_from_dict():
    structurer = Structurer(
        handlers={int: structure_int, str: structure_str},
        predicate_handlers=[
            StructureDataclassFromDict(name_converter=lambda name, metadata: name + "_")
        ],
    )

    @dataclass
    class Container:
        x: int
        y: str
        z: str = "default"

    assert structurer.structure(Container, {"x_": 1, "y_": "a"}) == Container(
        x=1, y="a", z="default"
    )
    assert structurer.structure(Container, {"x_": 1, "y_": "a", "z_": "b"}) == Container(
        x=1, y="a", z="b"
    )

    with pytest.raises(StructuringError) as exc:
        structurer.structure(Container, {"x_": 1, "z_": "b"})
    expected = StructuringError(
        [],
        "Cannot structure a dict into a dataclass",
        [StructuringError(["y"], r"Missing field \(`y_` in the input\)")],
    )
    assert_exception_matches(exc.value, expected)

    with pytest.raises(StructuringError) as exc:
        structurer.structure(Container, {"x_": 1, "y_": 2, "z_": "b"})
    expected = StructuringError(
        [],
        "Cannot structure a dict into a dataclass",
        [StructuringError(["y"], "The value must be a string")],
    )
    assert_exception_matches(exc.value, expected)

    # Need a structurer without a name converter for this one
    structurer = Structurer(
        handlers={int: structure_int, str: structure_str},
        predicate_handlers=[StructureDataclassFromDict()],
    )
    with pytest.raises(StructuringError) as exc:
        structurer.structure(Container, {"x": 1, "z": "b"})
    expected = StructuringError(
        [], "Cannot structure a dict into a dataclass", [StructuringError(["y"], r"Missing field")]
    )
    assert_exception_matches(exc.value, expected)
