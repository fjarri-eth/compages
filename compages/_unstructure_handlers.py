from collections.abc import Callable, Mapping, Sequence
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
from ._unstructure import (
    UnstructureHandler,
    UnstructurerContext,
    UnstructuringError,
)
from .path import DictKey, DictValue, ListElem, PathElem, StructField, UnionVariant


class AsNone(UnstructureHandler):
    """Unstructures ``None`` as itself."""

    def simple_unstructure(self, _val: None) -> None:
        pass


class AsInt(UnstructureHandler):
    """Unstructures anything convertable to an ``int`` (but not ``bool``) as an ``int``."""

    def simple_unstructure(self, val: int) -> int:
        # Handling a special case of `bool` here since in Python `bool` is an `int`,
        # and we don't want to mix them up.
        if isinstance(val, bool):
            raise UnstructuringError("The value must be of type `int`")
        return int(val)


class AsFloat(UnstructureHandler):
    """Unstructures anything convertable to a ``float`` as a ``float``."""

    def simple_unstructure(self, val: float) -> float:
        return float(val)


class AsBool(UnstructureHandler):
    """Unstructures anything convertable to a ``bool`` as a ``bool``."""

    def simple_unstructure(self, val: bool) -> bool:  # noqa: FBT001
        return bool(val)


class AsBytes(UnstructureHandler):
    """Unstructures anything convertable to ``bytes`` as ``bytes``."""

    def simple_unstructure(self, val: bytes) -> bytes:
        return bytes(val)


class AsStr(UnstructureHandler):
    """Unstructures anything convertable to a ``str`` as ``str``."""

    def simple_unstructure(self, val: str) -> str:
        return str(val)


class AsUnion(UnstructureHandler):
    """
    Attempts to unstructure as every typr in the union in order,
    returns the result of the first succeeded call.

    If none succeeded, raises a :py:class:`UnstructuringError`.
    """

    def unstructure(self, context: UnstructurerContext, val: Any) -> Any:
        variants = get_args(context.unstructure_as)

        exceptions: list[tuple[PathElem, UnstructuringError]] = []
        for variant in variants:
            try:
                return context.nested_unstructure_as(variant, val)
            except UnstructuringError as exc:
                exceptions.append((UnionVariant(variant), exc))

        raise UnstructuringError(f"Cannot unstructure as {context.unstructure_as}", exceptions)


class AsTuple(UnstructureHandler):
    """Unstructures as a ``tuple`` given its type arguments."""

    def unstructure(self, context: UnstructurerContext, val: Any) -> Any:
        if not isinstance(val, Sequence):
            raise UnstructuringError("Can only unstructure a Sequence as a tuple")

        elem_types = get_args(context.unstructure_as)

        # Homogeneous tuples (tuple[some_type, ...])
        if len(elem_types) == 2 and elem_types[1] == ...:
            elem_types = tuple(elem_types[0] for _ in range(len(val)))

        if len(val) < len(elem_types):
            raise UnstructuringError(
                f"Not enough elements to unstructure as a tuple: "
                f"got {len(val)}, need {len(elem_types)}"
            )
        if len(val) > len(elem_types):
            raise UnstructuringError(
                f"Too many elements to unstructure as a tuple: "
                f"got {len(val)}, need {len(elem_types)}"
            )

        result = []
        exceptions: list[tuple[PathElem, UnstructuringError]] = []
        for index, (item, tp) in enumerate(zip(val, elem_types, strict=True)):
            try:
                result.append(context.nested_unstructure_as(tp, item))
            except UnstructuringError as exc:
                exceptions.append((ListElem(index), exc))

        if exceptions:
            raise UnstructuringError(f"Cannot unstructure as {context.unstructure_as}", exceptions)

        return result


class AsDict(UnstructureHandler):
    """Unstructures as a ``dict`` given its type arguments."""

    def unstructure(self, context: UnstructurerContext, val: Any) -> Any:
        if not isinstance(val, Mapping):
            raise UnstructuringError("Can only unstructure a Mapping as a dict")

        key_type, value_type = get_args(context.unstructure_as)

        result = {}
        exceptions: list[tuple[PathElem, UnstructuringError]] = []
        for key, value in val.items():
            success = True
            try:
                unstructured_key = context.nested_unstructure_as(key_type, key)
            except UnstructuringError as exc:
                success = False
                exceptions.append((DictKey(key), exc))

            try:
                unstructured_value = context.nested_unstructure_as(value_type, value)
            except UnstructuringError as exc:
                success = False
                exceptions.append((DictValue(key), exc))

            if success:
                result[unstructured_key] = unstructured_value

        if exceptions:
            raise UnstructuringError(f"Cannot unstructure as {context.unstructure_as}", exceptions)

        return result


class AsList(UnstructureHandler):
    """Unstructures as a ``list`` given its type arguments."""

    def unstructure(self, context: UnstructurerContext, val: list[Any]) -> Any:
        if not isinstance(val, Sequence):
            raise UnstructuringError("Can only unstructure a Sequence as a list")

        (item_type,) = get_args(context.unstructure_as)

        result = []
        exceptions: list[tuple[PathElem, UnstructuringError]] = []
        for index, item in enumerate(val):
            try:
                result.append(context.nested_unstructure_as(item_type, item))
            except UnstructuringError as exc:
                exceptions.append((ListElem(index), exc))

        if exceptions:
            raise UnstructuringError(f"Cannot unstructure as {context.unstructure_as}", exceptions)

        return result


class _AsStructLikeToDict(UnstructureHandler):
    def __init__(
        self,
        get_fields: Callable[[ExtendedType[Any]], list[Field]],
        options: StructLikeOptions,
    ):
        self._get_fields = get_fields
        self._options = options

    def unstructure(self, context: UnstructurerContext, val: Any) -> Any:
        result = {}
        exceptions: list[tuple[PathElem, UnstructuringError]] = []

        try:
            struct_fields = self._get_fields(context.unstructure_as)
        except StructAdapterError as exc:
            raise UnstructuringError(
                f"Failed to fetch field metadata for the value `{val}`: {exc}"
            ) from exc

        for field in struct_fields:
            result_name = self._options.to_unstructured_name(field.name, field.metadata)
            value = getattr(val, field.name)
            # If the value field is equal to the default one, don't add it to the result.

            if (
                self._options.unstructure_skip_defaults
                and (default := field.get_default()) is not NoDefault
            ):
                try:
                    if value == default:
                        continue
                # On the off-chance the comparison is strict
                # and raises an exception on type mismatch
                except Exception:  # noqa: S110, BLE001
                    pass

            try:
                result[result_name] = context.nested_unstructure_as(field.type, value)
            except UnstructuringError as exc:
                exceptions.append((StructField(field.name), exc))

        if exceptions:
            raise UnstructuringError(
                f"Failed to unstructure to a dict as {context.unstructure_as}", exceptions
            )

        return result


class _AsStructLikeToList(UnstructureHandler):
    def __init__(
        self,
        get_fields: Callable[[ExtendedType[Any]], list[Field]],
        options: StructLikeOptions,
    ):
        self._get_fields = get_fields
        self._options = options

    def unstructure(self, context: UnstructurerContext, val: Any) -> Any:
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
                result.append(context.nested_unstructure_as(field.type, getattr(val, field.name)))
            except UnstructuringError as exc:
                exceptions.append((StructField(field.name), exc))

        if self._options.unstructure_skip_defaults:
            # We can omit the default values if they are in the end of the sequence
            for field in reversed(struct_fields):
                default = field.get_default()
                if default is not NoDefault and result[-1] == default:
                    result.pop()
                else:
                    break

        if exceptions:
            raise UnstructuringError(
                f"Failed to unstructure to a list as {context.unstructure_as}", exceptions
            )

        return result


class AsDataclassToList(UnstructureHandler):
    """Unstructures a :py:func:`~dataclasses.dataclass` instance into a ``list``."""

    def __init__(self, options: StructLikeOptions = StructLikeOptions()) -> None:
        self._handler = _AsStructLikeToList(get_fields_dataclass, options)

    def unstructure(self, context: UnstructurerContext, val: Any) -> Any:
        return self._handler.unstructure(context, val)


class AsDataclassToDict(UnstructureHandler):
    """Unstructures a :py:func:`~dataclasses.dataclass` instance into a ``dict``."""

    def __init__(self, options: StructLikeOptions = StructLikeOptions()):
        self._handler = _AsStructLikeToDict(get_fields_dataclass, options)

    def unstructure(self, context: UnstructurerContext, val: Any) -> Any:
        return self._handler.unstructure(context, val)


class AsNamedTupleToList(UnstructureHandler):
    """Unstructures a :py:class:`~typing.NamedTuple` instance into a ``list``."""

    def __init__(self, options: StructLikeOptions = StructLikeOptions()):
        self._handler = _AsStructLikeToList(get_fields_named_tuple, options)

    def unstructure(self, context: UnstructurerContext, val: Any) -> Any:
        return self._handler.unstructure(context, val)


class AsNamedTupleToDict(UnstructureHandler):
    """Unstructures a :py:class:`~typing.NamedTuple` instance into a ``dict``."""

    def __init__(self, options: StructLikeOptions = StructLikeOptions()):
        self._handler = _AsStructLikeToDict(get_fields_named_tuple, options)

    def unstructure(self, context: UnstructurerContext, val: Any) -> Any:
        return self._handler.unstructure(context, val)
