from collections.abc import Callable, Mapping, Sequence
from dataclasses import fields, is_dataclass
from functools import wraps
from types import MappingProxyType
from typing import Any, get_args

from ._unstructure import PredicateUnstructureHandler, Unstructurer, UnstructuringError
from .path import DictKey, DictValue, ListElem, PathElem, StructField, UnionVariant


def simple_unstructure(func: Callable[[Any], Any]) -> Callable[[Unstructurer, Any, Any], Any]:
    @wraps(func)
    def _wrapped(_unstructurer: Unstructurer, _unstructure_as: Any, val: Any) -> Any:
        return func(val)

    return _wrapped


@simple_unstructure
def unstructure_as_none(val: Any) -> None:
    if val is not None:
        raise UnstructuringError("The value must be `None`")


@simple_unstructure
def unstructure_as_int(val: Any) -> int:
    # Handling a special case of `bool` here since in Python `bool` is an `int`,
    # and we don't want to mix them up.
    if not isinstance(val, int) or isinstance(val, bool):
        raise UnstructuringError("The value must be an integer")
    return val


@simple_unstructure
def unstructure_as_float(val: Any) -> float:
    if not isinstance(val, float):
        raise UnstructuringError("The value must be a floating-point number")
    return float(val)


@simple_unstructure
def unstructure_as_bool(val: Any) -> bool:
    if not isinstance(val, bool):
        raise UnstructuringError("The value must be a boolean")
    return val


@simple_unstructure
def unstructure_as_bytes(val: Any) -> bytes:
    if not isinstance(val, bytes):
        raise UnstructuringError("The value must be a bytestring")
    return val


@simple_unstructure
def unstructure_as_str(val: Any) -> str:
    if not isinstance(val, str):
        raise UnstructuringError("The value must be a string")
    return val


def unstructure_as_union(unstructurer: Unstructurer, unstructure_as: Any, val: Any) -> Any:
    variants = get_args(unstructure_as)

    exceptions: list[tuple[PathElem, UnstructuringError]] = []
    for variant in variants:
        try:
            return unstructurer.unstructure_as(variant, val)
        except UnstructuringError as exc:  # noqa: PERF203
            exceptions.append((UnionVariant(variant), exc))

    raise UnstructuringError(f"Cannot unstructure as {unstructure_as}", exceptions)


def unstructure_as_tuple(unstructurer: Unstructurer, unstructure_as: Any, val: Any) -> Any:
    if not isinstance(val, Sequence):
        raise UnstructuringError("Can only unstructure a Sequence as a tuple")

    elem_types = get_args(unstructure_as)

    # Homogeneous tuples (tuple[some_type, ...])
    if len(elem_types) == 2 and elem_types[1] == ...:
        elem_types = tuple(elem_types[0] for _ in range(len(val)))

    if len(val) < len(elem_types):
        raise UnstructuringError(
            f"Not enough elements to unstructure as a tuple: got {len(val)}, need {len(elem_types)}"
        )
    if len(val) > len(elem_types):
        raise UnstructuringError(
            f"Too many elements to unstructure as a tuple: got {len(val)}, need {len(elem_types)}"
        )

    result = []
    exceptions: list[tuple[PathElem, UnstructuringError]] = []
    for index, (item, tp) in enumerate(zip(val, elem_types, strict=True)):
        try:
            result.append(unstructurer.unstructure_as(tp, item))
        except UnstructuringError as exc:  # noqa: PERF203
            exceptions.append((ListElem(index), exc))

    if exceptions:
        raise UnstructuringError(f"Cannot unstructure as {unstructure_as}", exceptions)

    return result


def unstructure_as_dict(unstructurer: Unstructurer, unstructure_as: type, val: Any) -> Any:
    if not isinstance(val, Mapping):
        raise UnstructuringError("Can only unstructure a Mapping as a dict")

    key_type, value_type = get_args(unstructure_as)

    result = {}
    exceptions: list[tuple[PathElem, UnstructuringError]] = []
    for key, value in val.items():
        success = True
        try:
            unstructured_key = unstructurer.unstructure_as(key_type, key)
        except UnstructuringError as exc:
            success = False
            exceptions.append((DictKey(key), exc))

        try:
            unstructured_value = unstructurer.unstructure_as(value_type, value)
        except UnstructuringError as exc:
            success = False
            exceptions.append((DictValue(key), exc))

        if success:
            result[unstructured_key] = unstructured_value

    if exceptions:
        raise UnstructuringError(f"Cannot unstructure as {unstructure_as}", exceptions)

    return result


def unstructure_as_list(unstructurer: Unstructurer, unstructure_as: type, val: list[Any]) -> Any:
    if not isinstance(val, Sequence):
        raise UnstructuringError("Can only unstructure a Sequence as a list")

    (item_type,) = get_args(unstructure_as)

    result = []
    exceptions: list[tuple[PathElem, UnstructuringError]] = []
    for index, item in enumerate(val):
        try:
            result.append(unstructurer.unstructure_as(item_type, item))
        except UnstructuringError as exc:  # noqa: PERF203
            exceptions.append((ListElem(index), exc))

    if exceptions:
        raise UnstructuringError(f"Cannot unstructure as {unstructure_as}", exceptions)

    return result


class UnstructureDataclassToDict(PredicateUnstructureHandler):
    def __init__(
        self,
        name_converter: Callable[[str, MappingProxyType[Any, Any]], str] = lambda name,
        _metadata: name,
    ):
        self._name_converter = name_converter

    def applies(self, unstructure_as: Any, val: Any) -> bool:
        return is_dataclass(unstructure_as) and isinstance(val, unstructure_as)

    def __call__(self, unstructurer: Unstructurer, unstructure_as: Any, val: Any) -> Any:
        result = {}
        exceptions: list[tuple[PathElem, UnstructuringError]] = []
        for field in fields(unstructure_as):
            result_name = self._name_converter(field.name, field.metadata)
            try:
                result[result_name] = unstructurer.unstructure_as(
                    field.type, getattr(val, field.name)
                )
            except UnstructuringError as exc:
                exceptions.append((StructField(field.name), exc))

        if exceptions:
            raise UnstructuringError(f"Cannot unstructure as {unstructure_as}", exceptions)

        return result


class UnstructureDataclassToList(PredicateUnstructureHandler):
    def applies(self, unstructure_as: Any, val: Any) -> bool:
        return is_dataclass(unstructure_as) and isinstance(val, unstructure_as)

    def __call__(self, unstructurer: Unstructurer, unstructure_as: Any, val: Any) -> Any:
        result = []
        exceptions: list[tuple[PathElem, UnstructuringError]] = []
        for field in fields(unstructure_as):
            try:
                result.append(unstructurer.unstructure_as(field.type, getattr(val, field.name)))
            except UnstructuringError as exc:  # noqa: PERF203
                exceptions.append((StructField(field.name), exc))

        if exceptions:
            raise UnstructuringError(f"Cannot unstructure as {unstructure_as}", exceptions)

        return result
