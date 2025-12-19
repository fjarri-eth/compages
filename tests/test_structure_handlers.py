import re
from dataclasses import dataclass, field
from types import UnionType
from typing import NamedTuple

import pytest
from compages import (
    DataclassBase,
    IntoBool,
    IntoBytes,
    IntoDataclassFromMapping,
    IntoDataclassFromSequence,
    IntoDict,
    IntoFloat,
    IntoInt,
    IntoList,
    IntoNamedTupleFromMapping,
    IntoNamedTupleFromSequence,
    IntoNone,
    IntoStr,
    IntoTuple,
    IntoUnion,
    NamedTupleBase,
    StructLikeOptions,
    Structurer,
    StructuringError,
)
from compages.path import DictKey, DictValue, ListElem, StructField, UnionVariant


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


def test_structure_into_none():
    structurer = Structurer({type(None): IntoNone()})
    assert structurer.structure_into(type(None), None) is None

    with pytest.raises(StructuringError) as exc:
        structurer.structure_into(type(None), 1)
    expected = StructuringError("The value must be `None`")
    assert_exception_matches(exc.value, expected)


def test_structure_into_float():
    structurer = Structurer({float: IntoFloat()})
    assert structurer.structure_into(float, 1.5) == 1.5

    # Specifically allow integers, but check that they are converted to floats.
    res = structurer.structure_into(float, 1)
    assert isinstance(res, float)
    assert res == 1.0

    with pytest.raises(StructuringError) as exc:
        structurer.structure_into(float, "a")
    expected = StructuringError("The value must be a floating-point number")
    assert_exception_matches(exc.value, expected)


def test_structure_into_bool():
    structurer = Structurer({bool: IntoBool()})
    assert structurer.structure_into(bool, True) is True
    assert structurer.structure_into(bool, False) is False

    with pytest.raises(StructuringError) as exc:
        structurer.structure_into(bool, "a")
    expected = StructuringError("The value must be a boolean")
    assert_exception_matches(exc.value, expected)


def test_structure_into_str():
    structurer = Structurer({str: IntoStr()})
    assert structurer.structure_into(str, "abc") == "abc"

    with pytest.raises(StructuringError) as exc:
        structurer.structure_into(str, 1)
    expected = StructuringError("The value must be a string")
    assert_exception_matches(exc.value, expected)


def test_structure_into_bytes():
    structurer = Structurer({bytes: IntoBytes()})
    assert structurer.structure_into(bytes, b"abc") == b"abc"

    with pytest.raises(StructuringError) as exc:
        structurer.structure_into(bytes, 1)
    expected = StructuringError("The value must be a bytestring")
    assert_exception_matches(exc.value, expected)


def test_structure_into_int():
    structurer = Structurer({int: IntoInt()})
    assert structurer.structure_into(int, 1) == 1

    with pytest.raises(StructuringError) as exc:
        structurer.structure_into(int, "a")
    expected = StructuringError("The value must be an integer")
    assert_exception_matches(exc.value, expected)

    # Specifically test that a boolean is not accepted,
    # even though it is a subclass of int in Python.
    with pytest.raises(StructuringError) as exc:
        structurer.structure_into(int, True)
    expected = StructuringError("The value must be an integer")
    assert_exception_matches(exc.value, expected)


def test_structure_into_union():
    structurer = Structurer(
        {
            UnionType: IntoUnion(),
            int: IntoInt(),
            str: IntoStr(),
        }
    )
    assert structurer.structure_into(int | str, "a") == "a"
    assert structurer.structure_into(int | str, 1) == 1

    with pytest.raises(StructuringError) as exc:
        structurer.structure_into(int | str, 1.2)
    expected = StructuringError(
        r"Cannot structure into int | str",
        [
            (UnionVariant(int), StructuringError("The value must be an integer")),
            (UnionVariant(str), StructuringError("The value must be a string")),
        ],
    )
    assert_exception_matches(exc.value, expected)


def test_structure_into_tuple():
    structurer = Structurer(
        {
            tuple: IntoTuple(),
            int: IntoInt(),
            str: IntoStr(),
        }
    )

    assert structurer.structure_into(tuple[()], []) == ()
    assert structurer.structure_into(tuple[int, str], [1, "a"]) == (1, "a")
    assert structurer.structure_into(tuple[int, str], (1, "a")) == (1, "a")
    assert structurer.structure_into(tuple[int, ...], (1, 2, 3)) == (1, 2, 3)

    with pytest.raises(StructuringError) as exc:
        structurer.structure_into(tuple[int, str], {"x": 1, "y": "a"})
    expected = StructuringError("Can only structure a tuple or a list into a tuple generic")
    assert_exception_matches(exc.value, expected)

    with pytest.raises(StructuringError) as exc:
        structurer.structure_into(tuple[int, str, int], [1, "a"])
    expected = StructuringError("Not enough elements to structure into a tuple: got 2, need 3")
    assert_exception_matches(exc.value, expected)

    with pytest.raises(StructuringError) as exc:
        structurer.structure_into(tuple[int], [1, "a"])
    expected = StructuringError("Too many elements to structure into a tuple: got 2, need 1")
    assert_exception_matches(exc.value, expected)

    with pytest.raises(StructuringError) as exc:
        structurer.structure_into(tuple[int, str], [1, 1.2])
    expected = StructuringError(
        r"Cannot structure into tuple\[int, str\]",
        [(ListElem(1), StructuringError("The value must be a string"))],
    )
    assert_exception_matches(exc.value, expected)


def test_structure_into_list():
    structurer = Structurer({list: IntoList(), int: IntoInt()})

    assert structurer.structure_into(list[int], [1, 2, 3]) == [1, 2, 3]
    assert structurer.structure_into(list[int], (1, 2, 3)) == [1, 2, 3]

    with pytest.raises(StructuringError) as exc:
        structurer.structure_into(list[int], {"x": 1, "y": "a"})
    expected = StructuringError("Can only structure a tuple or a list into a list generic")
    assert_exception_matches(exc.value, expected)

    with pytest.raises(StructuringError) as exc:
        structurer.structure_into(list[int], [1, "a"])
    expected = StructuringError(
        r"Cannot structure into list\[int\]",
        [(ListElem(1), StructuringError("The value must be an integer"))],
    )
    assert_exception_matches(exc.value, expected)


def test_structure_into_dict():
    structurer = Structurer(
        {
            dict: IntoDict(),
            int: IntoInt(),
            str: IntoStr(),
        }
    )

    assert structurer.structure_into(dict[int, str], {1: "a", 2: "b"}) == {1: "a", 2: "b"}

    with pytest.raises(StructuringError) as exc:
        structurer.structure_into(dict[int, str], [(1, "a"), (2, "b")])
    expected = StructuringError("Can only structure a dict into a dict generic")
    assert_exception_matches(exc.value, expected)

    # Error structuring a key
    with pytest.raises(StructuringError) as exc:
        structurer.structure_into(dict[int, str], {"a": "b", 2: "c"})
    expected = StructuringError(
        r"Cannot structure into dict\[int, str\]",
        [(DictKey("a"), StructuringError("The value must be an integer"))],
    )
    assert_exception_matches(exc.value, expected)

    # Error structuring a value
    with pytest.raises(StructuringError) as exc:
        structurer.structure_into(dict[int, str], {1: "a", 2: 3})
    expected = StructuringError(
        r"Cannot structure into dict\[int, str\]",
        [(DictValue(2), StructuringError("The value must be a string"))],
    )
    assert_exception_matches(exc.value, expected)


def test_structure_into_dataclass_from_sequence():
    structurer = Structurer(
        {
            int: IntoInt(),
            str: IntoStr(),
            DataclassBase: IntoDataclassFromSequence(),
        },
    )

    @dataclass
    class Container:
        x: int
        y: str
        z: str = "default"
        w: str = field(default_factory=lambda: "other default")

    assert structurer.structure_into(Container, [1, "a"]) == Container(x=1, y="a")
    assert structurer.structure_into(Container, [1, "a", "b"]) == Container(x=1, y="a", z="b")
    assert structurer.structure_into(Container, [1, "a", "b", "c"]) == Container(
        x=1, y="a", z="b", w="c"
    )

    with pytest.raises(StructuringError) as exc:
        structurer.structure_into(Container, {"x": 1, "y": "a", "z": "b"})
    expected = StructuringError("Can only structure a `Sequence` into")
    assert_exception_matches(exc.value, expected)

    with pytest.raises(StructuringError) as exc:
        structurer.structure_into(Container, [1, "a", "b", 2, 3])
    expected = StructuringError("Too many fields to serialize into")
    assert_exception_matches(exc.value, expected)

    with pytest.raises(StructuringError) as exc:
        structurer.structure_into(Container, [1])
    expected = StructuringError(
        "Failed to structure a list into",
        [(StructField("y"), StructuringError("Missing field"))],
    )
    assert_exception_matches(exc.value, expected)

    with pytest.raises(StructuringError) as exc:
        structurer.structure_into(Container, [1, 2, "a"])
    expected = StructuringError(
        "Failed to structure a list into",
        [(StructField("y"), StructuringError("The value must be a string"))],
    )
    assert_exception_matches(exc.value, expected)


def test_structure_sequence_into_dataclass_invalid_handler():
    structurer = Structurer(
        {
            int: IntoInt(),
            str: IntoDataclassFromSequence(),
        },
    )

    message = re.escape(
        "Failed to fetch field metadata for the value `['1']`: "
        "Expected a dataclass, got <class 'str'>"
    )
    with pytest.raises(StructuringError, match=message):
        structurer.structure_into(str, ["1"])


def test_structure_into_dataclass_from_mapping():
    structurer = Structurer(
        {
            int: IntoInt(),
            str: IntoStr(),
            DataclassBase: IntoDataclassFromMapping(
                StructLikeOptions(
                    to_unstructured_name=lambda name, metadata: name + "_"
                    if "foo" not in metadata
                    else name
                )
            ),
        },
    )

    @dataclass
    class Container:
        x: int
        y: str = field(metadata={"foo": True})
        z: str = "default"
        w: str = field(default_factory=lambda: "other default")

    assert structurer.structure_into(Container, {"x_": 1, "y": "a"}) == Container(x=1, y="a")
    assert structurer.structure_into(Container, {"x_": 1, "y": "a", "z_": "b"}) == Container(
        x=1, y="a", z="b"
    )
    assert structurer.structure_into(
        Container, {"x_": 1, "y": "a", "z_": "b", "w_": "c"}
    ) == Container(x=1, y="a", z="b", w="c")

    with pytest.raises(StructuringError) as exc:
        structurer.structure_into(Container, [1, "a", "b"])
    expected = StructuringError("Can only structure a mapping into")
    assert_exception_matches(exc.value, expected)

    with pytest.raises(StructuringError) as exc:
        structurer.structure_into(Container, {"y": "a", "z_": "b"})
    expected = StructuringError(
        "Failed to structure a dict into",
        [(StructField("x"), StructuringError(r"Missing field \(`x_` in the input\)"))],
    )
    assert_exception_matches(exc.value, expected)

    with pytest.raises(StructuringError) as exc:
        structurer.structure_into(Container, {"x_": 1, "y": 2, "z_": "b"})
    expected = StructuringError(
        "Failed to structure a dict into",
        [(StructField("y"), StructuringError("The value must be a string"))],
    )
    assert_exception_matches(exc.value, expected)

    # Need a structurer without a name converter for this one
    structurer = Structurer(
        {
            int: IntoInt(),
            str: IntoStr(),
            DataclassBase: IntoDataclassFromMapping(),
        },
    )
    with pytest.raises(StructuringError) as exc:
        structurer.structure_into(Container, {"x": 1, "z": "b"})
    expected = StructuringError(
        "Failed to structure a dict into",
        [(StructField("y"), StructuringError(r"Missing field"))],
    )
    assert_exception_matches(exc.value, expected)


def test_structure_into_dataclass_from_mapping_invalid_handler():
    structurer = Structurer(
        {
            int: IntoInt(),
            str: IntoDataclassFromMapping(),
        },
    )

    message = re.escape(
        "Failed to fetch field metadata for the value `{'a': '1'}`: "
        "Expected a dataclass, got <class 'str'>"
    )
    with pytest.raises(StructuringError, match=message):
        structurer.structure_into(str, {"a": "1"})


def test_structure_into_named_tuple_from_mapping():
    structurer = Structurer(
        {
            int: IntoInt(),
            str: IntoStr(),
            NamedTupleBase: IntoNamedTupleFromMapping(
                StructLikeOptions(to_unstructured_name=lambda name, _metadata: name + "_")
            ),
        },
    )

    class Container(NamedTuple):
        x: int
        y: str = "default"

    assert structurer.structure_into(Container, {"x_": 1}) == Container(x=1, y="default")
    assert structurer.structure_into(Container, {"x_": 1, "y_": "a"}) == Container(x=1, y="a")


def test_structure_into_named_tuple_from_sequence():
    structurer = Structurer(
        {
            int: IntoInt(),
            str: IntoStr(),
            NamedTupleBase: IntoNamedTupleFromSequence(),
        },
    )

    class Container(NamedTuple):
        x: int
        y: str = "default"

    assert structurer.structure_into(Container, [1]) == Container(x=1, y="default")
    assert structurer.structure_into(Container, [1, "a"]) == Container(x=1, y="a")
