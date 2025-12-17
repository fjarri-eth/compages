import dataclasses
from collections.abc import Callable
from types import MappingProxyType
from typing import Any, NamedTuple, get_type_hints

from ._common import ExtendedType, is_named_tuple


class StructAdapterError(Exception):
    pass


class NoDefault:
    pass


class Field(NamedTuple):
    name: str
    type: type[Any]
    default: Any
    default_factory: None | Callable[[], Any]
    metadata: MappingProxyType[Any, Any]


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
    metadata: MappingProxyType[Any, Any] = MappingProxyType({})
    for field_name in field_names:
        fields.append(
            Field(
                name=field_name,
                type=field_types[field_name],
                default=defaults.get(field_name, NoDefault),
                metadata=metadata,
                default_factory=None,
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
        # TODO: support default factory

        fields.append(
            Field(
                name=dc_field.name,
                type=field_types[dc_field.name],
                default=default,
                metadata=dc_field.metadata,
                default_factory=None,
            )
        )

    return fields
