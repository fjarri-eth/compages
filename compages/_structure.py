from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ._common import ExtendedType, GeneratorStack, Result, get_lookup_order
from .path import PathElem


class StructuringError(Exception):
    """
    An error during structuring.

    Accumulates possible nested errors.
    """

    def __init__(self, message: str, inner_errors: list[tuple[PathElem, "StructuringError"]] = []):
        super().__init__(message)
        self.message = message
        self.inner_errors = inner_errors

    def __str__(self) -> str:
        messages = collect_messages([], self)

        _, msg = messages[0]
        message_strings = [msg] + [
            "  " * len(path) + ".".join(str(elem) for elem in path) + f": {msg}"
            for path, msg in messages[1:]
        ]

        return "\n".join(message_strings)


def collect_messages(
    path: list[PathElem], exc: StructuringError
) -> list[tuple[list[PathElem], str]]:
    result = [(path, exc.message)]
    for path_elem, inner_exc in exc.inner_errors:
        result.extend(collect_messages([*path, path_elem], inner_exc))
    return result


@dataclass
class StructurerContext:
    """A context object passed to handlers during structuring."""

    structurer: "Structurer"
    """The current structurer."""

    structure_into: ExtendedType[Any]
    """
    The requested return value type.

    Can be a regular type, a newtype, or a generic type.
    """

    user_context: Any
    """
    The custom object the user passed to :py:meth:`Unstructurer.unstructure_as`.
    """

    def nested_structure_into[T](self, structure_into: ExtendedType[T], val: Any) -> T:
        """
        Calls :py:meth:`Structurer.structure_into` of ``self.structurer``
        passing on the user context.
        """
        return self.structurer.structure_into(structure_into, val, user_context=self.user_context)


class StructureHandler:
    """A base class for structuring logic attached to a type."""

    def structure(
        self,
        context: StructurerContext,  # noqa: ARG002
        value: Any,
    ) -> Any:
        """
        Structures the given ``value`` returning an instance of ``context.structure_into``.

        If not defined, falls back to :py:meth:`simple_structure`.
        """
        return self.simple_structure(value)

    def simple_structure(self, value: Any) -> Any:
        """
        Structures the given ``value``.

        Use for the cases where the information from ``context`` is not needed.
        If :py:meth:`structure` is not defined, this method must be defined.
        """
        raise NotImplementedError(
            "`StructureHandler` must implement either `structure()` or `simple_structure()`"
        )


class Structurer:
    def __init__(self, handlers: Mapping[Any, StructureHandler] = {}):
        self._handlers = dict(handlers)

    def structure_into[T](
        self, structure_into: ExtendedType[T], val: Any, user_context: Any = None
    ) -> T:
        """
        Structures (deserializes) the given ``value`` into the type ``structure_into``
        with an optional ``user_context`` (which will be passed to the handlers).

        Raises :py:class:`StructuringError` for any structuring-related error.
        """
        context = StructurerContext(
            structurer=self, structure_into=structure_into, user_context=user_context
        )
        stack = GeneratorStack[StructurerContext, T](context, val)
        lookup_order = get_lookup_order(structure_into)

        for tp in lookup_order:
            handler = self._handlers.get(tp, None)
            result = stack.push(handler.structure if handler else None)
            if result is not Result.UNDEFINED:
                return result

        if stack.is_empty():
            raise StructuringError(
                f"No handlers registered to structure `{val}` into {structure_into}"
            )

        raise StructuringError(
            f"Could not find a non-generator handler to structure into {structure_into}"
        )
