from collections.abc import Callable, Mapping, Sequence
from functools import partial, wraps
from types import MappingProxyType
from typing import Any, get_args

from ._common import ExtendedType, TypedNewType
from ._struct_like import (
    Field,
    NoDefault,
    StructAdapterError,
    get_fields_dataclass,
    get_fields_named_tuple,
)
from ._unstructure import (
    UnstructurerContext,
    UnstructuringError,
)
from .path import DictKey, DictValue, ListElem, PathElem, StructField, UnionVariant


def simple_unstructure(func: Callable[[Any], Any]) -> Callable[[UnstructurerContext, Any], Any]:
    @wraps(func)
    def _wrapped(_context: UnstructurerContext, val: Any) -> Any:
        return func(val)

    return _wrapped


def simple_typechecked_unstructure(
    func: Callable[[Any], Any],
) -> Callable[[UnstructurerContext, Any], Any]:
    @wraps(func)
    def _wrapped(context: UnstructurerContext, val: Any) -> Any:
        if isinstance(context.unstructure_as, TypedNewType):
            base_type = context.unstructure_as.__supertype__
            # `NewType`'s `__supertype__` can be another newtype,
            # so we have to follow the chain until we reach something that's not a `NewType`.
            while isinstance(base_type, TypedNewType):
                base_type = base_type.__supertype__
            if not isinstance(val, base_type):
                raise UnstructuringError(f"The value must be of type `{base_type.__name__}`")
        elif not isinstance(val, context.unstructure_as):
            raise UnstructuringError(
                f"The value must be of type `{context.unstructure_as.__name__}`"
            )
        return func(val)

    return _wrapped


@simple_typechecked_unstructure
def unstructure_as_none(_val: None) -> None:
    pass


@simple_typechecked_unstructure
def unstructure_as_int(val: int) -> int:
    # Handling a special case of `bool` here since in Python `bool` is an `int`,
    # and we don't want to mix them up.
    if isinstance(val, bool):
        raise UnstructuringError("The value must be of type `int`")
    return int(val)


@simple_typechecked_unstructure
def unstructure_as_float(val: float) -> float:
    return float(val)


@simple_typechecked_unstructure
def unstructure_as_bool(val: bool) -> bool:  # noqa: FBT001
    return bool(val)


@simple_typechecked_unstructure
def unstructure_as_bytes(val: bytes) -> bytes:
    return bytes(val)


@simple_typechecked_unstructure
def unstructure_as_str(val: str) -> str:
    return str(val)


def unstructure_as_union(context: UnstructurerContext, val: Any) -> Any:
    variants = get_args(context.unstructure_as)

    exceptions: list[tuple[PathElem, UnstructuringError]] = []
    for variant in variants:
        try:
            return context.unstructurer.unstructure_as(variant, val)
        except UnstructuringError as exc:  # noqa: PERF203
            exceptions.append((UnionVariant(variant), exc))

    raise UnstructuringError(f"Cannot unstructure as {context.unstructure_as}", exceptions)


def unstructure_as_tuple(context: UnstructurerContext, val: Any) -> Any:
    if not isinstance(val, Sequence):
        raise UnstructuringError("Can only unstructure a Sequence as a tuple")

    elem_types = get_args(context.unstructure_as)

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
            result.append(context.unstructurer.unstructure_as(tp, item))
        except UnstructuringError as exc:  # noqa: PERF203
            exceptions.append((ListElem(index), exc))

    if exceptions:
        raise UnstructuringError(f"Cannot unstructure as {context.unstructure_as}", exceptions)

    return result


def unstructure_as_dict(context: UnstructurerContext, val: Any) -> Any:
    if not isinstance(val, Mapping):
        raise UnstructuringError("Can only unstructure a Mapping as a dict")

    key_type, value_type = get_args(context.unstructure_as)

    result = {}
    exceptions: list[tuple[PathElem, UnstructuringError]] = []
    for key, value in val.items():
        success = True
        try:
            unstructured_key = context.unstructurer.unstructure_as(key_type, key)
        except UnstructuringError as exc:
            success = False
            exceptions.append((DictKey(key), exc))

        try:
            unstructured_value = context.unstructurer.unstructure_as(value_type, value)
        except UnstructuringError as exc:
            success = False
            exceptions.append((DictValue(key), exc))

        if success:
            result[unstructured_key] = unstructured_value

    if exceptions:
        raise UnstructuringError(f"Cannot unstructure as {context.unstructure_as}", exceptions)

    return result


def unstructure_as_list(context: UnstructurerContext, val: list[Any]) -> Any:
    if not isinstance(val, Sequence):
        raise UnstructuringError("Can only unstructure a Sequence as a list")

    (item_type,) = get_args(context.unstructure_as)

    result = []
    exceptions: list[tuple[PathElem, UnstructuringError]] = []
    for index, item in enumerate(val):
        try:
            result.append(context.unstructurer.unstructure_as(item_type, item))
        except UnstructuringError as exc:  # noqa: PERF203
            exceptions.append((ListElem(index), exc))

    if exceptions:
        raise UnstructuringError(f"Cannot unstructure as {context.unstructure_as}", exceptions)

    return result


class _UnstructureStructLikeToDict:
    def __init__(
        self,
        get_fields: Callable[[ExtendedType[Any]], list[Field]],
        name_converter: Callable[[str, MappingProxyType[Any, Any]], str] = lambda name,
        _metadata: name,
    ):
        self._get_fields = get_fields
        self._name_converter = name_converter

    def __call__(self, context: UnstructurerContext, val: Any) -> Any:
        result = {}
        exceptions: list[tuple[PathElem, UnstructuringError]] = []

        try:
            struct_fields = self._get_fields(context.unstructure_as)
        except StructAdapterError as exc:
            raise UnstructuringError(
                f"Failed to fetch field metadata for the value `{val}`: {exc}"
            ) from exc

        for field in struct_fields:
            result_name = self._name_converter(field.name, field.metadata)
            value = getattr(val, field.name)
            # If the value field is equal to the default one, don't add it to the result.
            try:
                if (field.default is not NoDefault and value == field.default) or (
                    field.default_factory is not None and value == field.default_factory()
                ):
                    continue
            # On the off-chance the comparison is strict and raises an exception on type mismatch
            except Exception:  # noqa: S110, BLE001
                pass
            try:
                result[result_name] = context.unstructurer.unstructure_as(field.type, value)
            except UnstructuringError as exc:
                exceptions.append((StructField(field.name), exc))

        if exceptions:
            raise UnstructuringError(
                f"Failed to unstructure to a dict as {context.unstructure_as}", exceptions
            )

        return result


class _UnstructureStructLikeToList:
    def __init__(
        self,
        get_fields: Callable[[ExtendedType[Any]], list[Field]],
    ):
        self._get_fields = get_fields

    def __call__(self, context: UnstructurerContext, val: Any) -> Any:
        result = []
        exceptions: list[tuple[PathElem, UnstructuringError]] = []

        try:
            struct_fields = self._get_fields(context.unstructure_as)
        except StructAdapterError as exc:
            raise UnstructuringError(
                f"Failed to fetch field metadata for the value `{val}`: {exc}"
            ) from exc

        for field in struct_fields:
            try:
                result.append(
                    context.unstructurer.unstructure_as(field.type, getattr(val, field.name))
                )
            except UnstructuringError as exc:  # noqa: PERF203
                exceptions.append((StructField(field.name), exc))

        if exceptions:
            raise UnstructuringError(
                f"Failed to unstructure to a list as {context.unstructure_as}", exceptions
            )

        return result


unstructure_dataclass_to_list = _UnstructureStructLikeToList(get_fields_dataclass)
UnstructureDataclassToDict = partial(_UnstructureStructLikeToDict, get_fields_dataclass)

unstructure_named_tuple_to_list = _UnstructureStructLikeToList(get_fields_named_tuple)
UnstructureNamedTupleToDict = partial(_UnstructureStructLikeToDict, get_fields_named_tuple)
