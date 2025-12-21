from collections.abc import Callable, Mapping, Sequence
from types import MappingProxyType
from typing import Any, get_args

from ._common import ExtendedType
from ._struct_like import (
    Field,
    NoDefault,
    StructAdapterError,
    StructLikeOptions,
    get_fields_dataclass,
    get_fields_named_tuple,
)
from ._structure import StructureHandler, StructurerContext, StructuringError
from .path import DictKey, DictValue, ListElem, PathElem, StructField, UnionVariant


class IntoNone(StructureHandler):
    """
    If ``val`` is ``None``, structures into itself,
    otherwise raises a :py:class:`StructuringError`.
    """

    def simple_structure(self, val: Any) -> None:
        if val is not None:
            raise StructuringError("The value must be `None`")


class IntoInt(StructureHandler):
    """
    If ``val`` is an ``int`` (but not ``bool``), structures into itself,
    otherwise raises a :py:class:`StructuringError`.
    """

    def simple_structure(self, val: Any) -> int:
        # Handling a special case of `bool` here since in Python `bool` is an `int`,
        # and we don't want to mix them up.
        if not isinstance(val, int) or isinstance(val, bool):
            raise StructuringError("The value must be an integer")
        return val


class IntoFloat(StructureHandler):
    """
    If ``val`` is a ``float`` or ``int``, converts into ``float``,
    otherwise raises a :py:class:`StructuringError`.
    """

    def simple_structure(self, val: Any) -> float:
        # Allow integers as well, even though `int` is not a subclass of `float` in Python.
        if not isinstance(val, int | float):
            raise StructuringError("The value must be a floating-point number")
        return float(val)


class IntoBool(StructureHandler):
    """
    If ``val`` is a ``bool``, structures into itself,
    otherwise raises a :py:class:`StructuringError`.
    """

    def simple_structure(self, val: Any) -> bool:
        if not isinstance(val, bool):
            raise StructuringError("The value must be a boolean")
        return val


class IntoBytes(StructureHandler):
    """
    If ``val`` is a ``bytes``, structures into itself,
    otherwise raises a :py:class:`StructuringError`.
    """

    def simple_structure(self, val: Any) -> bytes:
        if not isinstance(val, bytes):
            raise StructuringError("The value must be a bytestring")
        return val


class IntoStr(StructureHandler):
    """
    If ``val`` is a ``str``, structures into itself,
    otherwise raises a :py:class:`StructuringError`.
    """

    def simple_structure(self, val: Any) -> str:
        if not isinstance(val, str):
            raise StructuringError("The value must be a string")
        return val


class IntoUnion(StructureHandler):
    """
    Attempts to structure into every type in the union in order,
    returns the result of the first succeeded call.

    If none succeeded, raises a :py:class:`StructuringError`.
    """

    def structure(self, context: StructurerContext, val: Any) -> Any:
        variants = get_args(context.structure_into)

        exceptions: list[tuple[PathElem, StructuringError]] = []
        for variant in variants:
            try:
                return context.nested_structure_into(variant, val)
            except StructuringError as exc:
                exceptions.append((UnionVariant(variant), exc))

        raise StructuringError(f"Cannot structure into {context.structure_into}", exceptions)


class IntoTuple(StructureHandler):
    """Attempts to structure into a ``tuple`` given its type arguments."""

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
                result.append(context.nested_structure_into(tp, item))
            except StructuringError as exc:
                exceptions.append((ListElem(index), exc))

        if exceptions:
            raise StructuringError(f"Cannot structure into {context.structure_into}", exceptions)

        return tuple(result)


class IntoList(StructureHandler):
    """Attempts to structure into a ``list`` given its type arguments."""

    def structure(self, context: StructurerContext, val: Any) -> Any:
        if not isinstance(val, list | tuple):
            raise StructuringError("Can only structure a tuple or a list into a list generic")

        (item_type,) = get_args(context.structure_into)

        result = []
        exceptions: list[tuple[PathElem, StructuringError]] = []
        for index, item in enumerate(val):
            try:
                result.append(context.nested_structure_into(item_type, item))
            except StructuringError as exc:
                exceptions.append((ListElem(index), exc))

        if exceptions:
            raise StructuringError(f"Cannot structure into {context.structure_into}", exceptions)

        return result


class IntoDict(StructureHandler):
    """Attempts to structure into a ``dict`` given its type arguments."""

    def structure(self, context: StructurerContext, val: Any) -> Any:
        if not isinstance(val, dict):
            raise StructuringError("Can only structure a dict into a dict generic")

        key_type, value_type = get_args(context.structure_into)

        result = {}
        exceptions: list[tuple[PathElem, StructuringError]] = []
        for key, value in val.items():
            success = True

            try:
                structured_key = context.nested_structure_into(key_type, key)
            except StructuringError as exc:
                success = False
                exceptions.append((DictKey(key), exc))

            try:
                structured_value = context.nested_structure_into(value_type, value)
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
        options: StructLikeOptions,
    ):
        self._get_fields = get_fields
        self._options = options

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
                results[field.name] = context.nested_structure_into(field.type, val[i])
            except StructuringError as exc:
                exceptions.append((StructField(field.name), exc))

        for field in struct_fields[len(val) :]:
            if (
                self._options.structure_fill_in_defaults
                and (default := field.get_default()) is not NoDefault
            ):
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
        options: StructLikeOptions,
    ):
        self._get_fields = get_fields
        self._options = options

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
            val_name = self._options.to_unstructured_name(field.name, field.metadata)
            if val_name in val:
                try:
                    results[field.name] = context.nested_structure_into(field.type, val[val_name])
                except StructuringError as exc:
                    exceptions.append((StructField(field.name), exc))
                continue

            if (
                self._options.structure_fill_in_defaults
                and (default := field.get_default()) is not NoDefault
            ):
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
    """
    Attempts to structure into a :py:func:`~dataclasses.dataclass` instance
    from a :py:class:`~collections.abc.Sequence` type.
    """

    def __init__(self, options: StructLikeOptions = StructLikeOptions()):
        self._handler = _SequenceIntoStructLike(get_fields_dataclass, options)

    def structure(self, context: StructurerContext, val: Any) -> Any:
        return self._handler.structure(context, val)


class IntoDataclassFromMapping(StructureHandler):
    """
    Attempts to structure into a :py:func:`~dataclasses.dataclass` instance
    from a :py:class:`~collections.abc.Mapping` type.
    """

    def __init__(self, options: StructLikeOptions = StructLikeOptions()):
        self._handler = _MappingIntoStructLike(get_fields_dataclass, options)

    def structure(self, context: StructurerContext, val: Any) -> Any:
        return self._handler.structure(context, val)


class IntoNamedTupleFromSequence(StructureHandler):
    """
    Attempts to structure into a :py:class:`~typing.NamedTuple` instance
    from a :py:class:`~collections.abc.Sequence` type.
    """

    def __init__(self, options: StructLikeOptions = StructLikeOptions()):
        self._handler = _SequenceIntoStructLike(get_fields_named_tuple, options)

    def structure(self, context: StructurerContext, val: Any) -> Any:
        return self._handler.structure(context, val)


class IntoNamedTupleFromMapping(StructureHandler):
    """
    Attempts to structure into a :py:class:`~typing.NamedTuple` instance
    from a :py:class:`~collections.abc.Mapping` type.
    """

    def __init__(self, options: StructLikeOptions = StructLikeOptions()):
        self._handler = _MappingIntoStructLike(get_fields_named_tuple, options)

    def structure(self, context: StructurerContext, val: Any) -> Any:
        return self._handler.structure(context, val)
