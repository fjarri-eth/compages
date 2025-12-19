from collections.abc import Callable, Mapping, Sequence
from types import MappingProxyType
from typing import Any, get_args

from ._common import ExtendedType
from ._struct_like import (
    Field,
    NoDefault,
    StructAdapterError,
    get_fields_dataclass,
    get_fields_named_tuple,
)
from ._structure import StructureHandler, StructurerContext, StructuringError
from .path import DictKey, DictValue, ListElem, PathElem, StructField, UnionVariant


class IntoNone(StructureHandler):
    def simple_structure(self, val: Any) -> None:
        if val is not None:
            raise StructuringError("The value must be `None`")


class IntoInt(StructureHandler):
    def simple_structure(self, val: Any) -> int:
        # Handling a special case of `bool` here since in Python `bool` is an `int`,
        # and we don't want to mix them up.
        if not isinstance(val, int) or isinstance(val, bool):
            raise StructuringError("The value must be an integer")
        return val


class IntoFloat(StructureHandler):
    def simple_structure(self, val: Any) -> float:
        # Allow integers as well, even though `int` is not a subclass of `float` in Python.
        if not isinstance(val, int | float):
            raise StructuringError("The value must be a floating-point number")
        return float(val)


class IntoBool(StructureHandler):
    def simple_structure(self, val: Any) -> bool:
        if not isinstance(val, bool):
            raise StructuringError("The value must be a boolean")
        return val


class IntoBytes(StructureHandler):
    def simple_structure(self, val: Any) -> bytes:
        if not isinstance(val, bytes):
            raise StructuringError("The value must be a bytestring")
        return val


class IntoStr(StructureHandler):
    def simple_structure(self, val: Any) -> str:
        if not isinstance(val, str):
            raise StructuringError("The value must be a string")
        return val


class IntoUnion(StructureHandler):
    def structure(self, context: StructurerContext, val: Any) -> Any:
        variants = get_args(context.structure_into)

        exceptions: list[tuple[PathElem, StructuringError]] = []
        for variant in variants:
            try:
                return context.structurer.structure_into(variant, val)
            except StructuringError as exc:  # noqa: PERF203
                exceptions.append((UnionVariant(variant), exc))

        raise StructuringError(f"Cannot structure into {context.structure_into}", exceptions)


class IntoTuple(StructureHandler):
    def structure(self, context: StructurerContext, val: Any) -> Any:
        if not isinstance(val, list | tuple):
            raise StructuringError("Can only structure a tuple or a list into a tuple generic")

        elem_types = get_args(context.structure_into)

        # Homogeneous tuples (tuple[some_type, ...])
        if len(elem_types) == 2 and elem_types[1] == ...:
            elem_types = tuple(elem_types[0] for _ in range(len(val)))

        if len(val) < len(elem_types):
            raise StructuringError(
                f"Not enough elements to structure into a tuple: "
                f"got {len(val)}, need {len(elem_types)}"
            )
        if len(val) > len(elem_types):
            raise StructuringError(
                f"Too many elements to structure into a tuple: "
                f"got {len(val)}, need {len(elem_types)}"
            )

        result = []
        exceptions: list[tuple[PathElem, StructuringError]] = []
        for index, (item, tp) in enumerate(zip(val, elem_types, strict=True)):
            try:
                result.append(context.structurer.structure_into(tp, item))
            except StructuringError as exc:  # noqa: PERF203
                exceptions.append((ListElem(index), exc))

        if exceptions:
            raise StructuringError(f"Cannot structure into {context.structure_into}", exceptions)

        return tuple(result)


class IntoList(StructureHandler):
    def structure(self, context: StructurerContext, val: Any) -> Any:
        if not isinstance(val, list | tuple):
            raise StructuringError("Can only structure a tuple or a list into a list generic")

        (item_type,) = get_args(context.structure_into)

        result = []
        exceptions: list[tuple[PathElem, StructuringError]] = []
        for index, item in enumerate(val):
            try:
                result.append(context.structurer.structure_into(item_type, item))
            except StructuringError as exc:  # noqa: PERF203
                exceptions.append((ListElem(index), exc))

        if exceptions:
            raise StructuringError(f"Cannot structure into {context.structure_into}", exceptions)

        return result


class IntoDict(StructureHandler):
    def structure(self, context: StructurerContext, val: Any) -> Any:
        if not isinstance(val, dict):
            raise StructuringError("Can only structure a dict into a dict generic")

        key_type, value_type = get_args(context.structure_into)

        result = {}
        exceptions: list[tuple[PathElem, StructuringError]] = []
        for key, value in val.items():
            success = True

            try:
                structured_key = context.structurer.structure_into(key_type, key)
            except StructuringError as exc:
                success = False
                exceptions.append((DictKey(key), exc))

            try:
                structured_value = context.structurer.structure_into(value_type, value)
            except StructuringError as exc:
                success = False
                exceptions.append((DictValue(key), exc))

            if success:
                result[structured_key] = structured_value

        if exceptions:
            raise StructuringError(f"Cannot structure into {context.structure_into}", exceptions)

        return result


class _SequenceIntoStructLike(StructureHandler):
    def __init__(
        self,
        get_fields: Callable[[ExtendedType[Any]], list[Field]],
    ):
        self._get_fields = get_fields

    def structure(self, context: StructurerContext, val: Any) -> Any:
        if not isinstance(val, Sequence):
            raise StructuringError(f"Can only structure a `Sequence` into {context.structure_into}")

        results = {}
        exceptions: list[tuple[PathElem, StructuringError]] = []

        try:
            struct_fields = self._get_fields(context.structure_into)
        except StructAdapterError as exc:
            raise StructuringError(
                f"Failed to fetch field metadata for the value `{val}`: {exc}"
            ) from exc

        if len(val) > len(struct_fields):
            raise StructuringError(f"Too many fields to serialize into {context.structure_into}")

        for i, field in enumerate(struct_fields[: len(val)]):
            try:
                results[field.name] = context.structurer.structure_into(field.type, val[i])
            except StructuringError as exc:  # noqa: PERF203
                exceptions.append((StructField(field.name), exc))

        for field in struct_fields[len(val) :]:
            default = field.get_default()
            if default is not NoDefault:
                results[field.name] = default
            else:
                exceptions.append((StructField(field.name), StructuringError("Missing field")))

        if exceptions:
            raise StructuringError(
                f"Failed to structure a list into a dataclass {context.structure_into}", exceptions
            )

        return context.structure_into(**results)


class _MappingIntoStructLike(StructureHandler):
    def __init__(
        self,
        get_fields: Callable[[ExtendedType[Any]], list[Field]],
        name_converter: Callable[[str, MappingProxyType[Any, Any]], str] = lambda name,
        _metadata: name,
    ):
        self._get_fields = get_fields
        self._name_converter = name_converter

    def structure(self, context: StructurerContext, val: Any) -> Any:
        if not isinstance(val, Mapping | MappingProxyType):
            raise StructuringError(f"Can only structure a mapping into {context.structure_into}")

        results = {}
        exceptions: list[tuple[PathElem, StructuringError]] = []

        try:
            struct_fields = self._get_fields(context.structure_into)
        except StructAdapterError as exc:
            raise StructuringError(
                f"Failed to fetch field metadata for the value `{val}`: {exc}"
            ) from exc

        for field in struct_fields:
            val_name = self._name_converter(field.name, field.metadata)
            if val_name in val:
                try:
                    results[field.name] = context.structurer.structure_into(
                        field.type, val[val_name]
                    )
                except StructuringError as exc:
                    exceptions.append((StructField(field.name), exc))
                continue

            default = field.get_default()
            if default is not NoDefault:
                results[field.name] = default
            else:
                if val_name == field.name:
                    message = "Missing field"
                else:
                    message = f"Missing field (`{val_name}` in the input)"
                exceptions.append((StructField(field.name), StructuringError(message)))

        if exceptions:
            raise StructuringError(
                f"Failed to structure a dict into {context.structure_into}", exceptions
            )

        return context.structure_into(**results)


class IntoDataclassFromSequence(StructureHandler):
    def __init__(self) -> None:
        self._handler = _SequenceIntoStructLike(get_fields_dataclass)

    def structure(self, context: StructurerContext, val: Any) -> Any:
        return self._handler.structure(context, val)


class IntoDataclassFromMapping(StructureHandler):
    def __init__(
        self,
        name_converter: Callable[[str, MappingProxyType[Any, Any]], str] = lambda name,
        _metadata: name,
    ):
        self._handler = _MappingIntoStructLike(get_fields_dataclass, name_converter=name_converter)

    def structure(self, context: StructurerContext, val: Any) -> Any:
        return self._handler.structure(context, val)


class IntoNamedTupleFromSequence(StructureHandler):
    def __init__(self) -> None:
        self._handler = _SequenceIntoStructLike(get_fields_named_tuple)

    def structure(self, context: StructurerContext, val: Any) -> Any:
        return self._handler.structure(context, val)


class IntoNamedTupleFromMapping(StructureHandler):
    def __init__(
        self,
        name_converter: Callable[[str, MappingProxyType[Any, Any]], str] = lambda name,
        _metadata: name,
    ):
        self._handler = _MappingIntoStructLike(
            get_fields_named_tuple, name_converter=name_converter
        )

    def structure(self, context: StructurerContext, val: Any) -> Any:
        return self._handler.structure(context, val)
