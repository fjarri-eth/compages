import dataclasses
from collections.abc import Callable
from typing import Any, NamedTuple, get_type_hints

from ._common import ExtendedType, is_named_tuple


class StructAdapterError(Exception):
    pass


class NoDefault:
    pass


class Field(NamedTuple):
    name: str
    type: type[Any]
    default: Any = NoDefault
    default_factory: None | Callable[[], Any] = None
    metadata: Any = None

    def get_default(self) -> Any:
        if self.default is not NoDefault:
            return self.default
        if self.default_factory is not None:
            return self.default_factory()
        return NoDefault


def get_fields_named_tuple(tp: ExtendedType[Any]) -> list[Field]:
    try:
        field_types = get_type_hints(tp)
    except NameError as exc:
        raise StructAdapterError(f"Field type annotation cannot be resolved: {exc}") from exc

    if not is_named_tuple(tp):
        raise StructAdapterError(f"Expected a named tuple, got {tp}")

    # Because of the check above we know we have a named tuple on our hands,
    # but `mypy` cannot assert that.
    defaults = tp._field_defaults  # type: ignore[union-attr]
    field_names = tp._fields  # type: ignore[union-attr]

    fields = []
    for field_name in field_names:
        fields.append(
            Field(
                name=field_name,
                type=field_types[field_name],
                default=defaults.get(field_name, NoDefault),
            )
        )

    return fields


def get_fields_dataclass(tp: ExtendedType[Any]) -> list[Field]:
    try:
        field_types = get_type_hints(tp)
    except NameError as exc:
        raise StructAdapterError(f"Field type annotation cannot be resolved: {exc}") from exc

    if not dataclasses.is_dataclass(tp):
        raise StructAdapterError(f"Expected a dataclass, got {tp}")

    dataclass_fields = dataclasses.fields(tp)

    fields = []
    for dc_field in dataclass_fields:
        if dc_field.default is dataclasses.MISSING:
            default = NoDefault
        else:
            default = dc_field.default

        if dc_field.default_factory is dataclasses.MISSING:
            default_factory = None
        else:
            default_factory = dc_field.default_factory

        fields.append(
            Field(
                name=dc_field.name,
                type=field_types[dc_field.name],
                default=default,
                metadata=dc_field.metadata,
                default_factory=default_factory,
            )
        )

    return fields


@dataclasses.dataclass
class StructLikeOptions:
    """Options for handlers working with struct-like types (dataclasses, named tuples etc)."""

    to_unstructured_name: Callable[[str, Any], str] = lambda name, _metadata: name
    """
    A function converting a field name of a typed representation
    into a field name of the corresponding unstructured representation.

    The second argument is the metadata attached to the field (if any).
    """

    unstructure_skip_defaults: bool = True
    """If the field value equals to the default when unstructuring, do not output it."""

    structure_fill_in_defaults: bool = True
    """
    If the field value is missing when structuring, substitute the default.

    If this value is ``False``, an error will be raised instead.
    """
