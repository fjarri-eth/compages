from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, TypeVar

from ._common import ExtendedType, GeneratorStack, Result, get_lookup_order, isinstance_ext
from .path import PathElem


class UnstructuringError(Exception):
    """
    An error during unstructuring.

    Accumulates possible nested errors.
    """

    def __init__(
        self, message: str, inner_errors: list[tuple[PathElem, "UnstructuringError"]] = []
    ):
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
    path: list[PathElem], exc: UnstructuringError
) -> list[tuple[list[PathElem], str]]:
    result = [(path, exc.message)]
    for path_elem, inner_exc in exc.inner_errors:
        result.extend(collect_messages([*path, path_elem], inner_exc))
    return result


_T = TypeVar("_T")


@dataclass
class UnstructurerContext:
    """A context object passed to handlers during unstructuring."""

    unstructurer: "Unstructurer"
    """The current unstructurer."""

    unstructure_as: ExtendedType[Any]
    """
    The type which the value should be treated as.

    Can be a regular type, a newtype, or a generic type.
    """

    user_context: Any
    """
    The custom object the user passed to :py:meth:`Unstructurer.unstructure_as`.
    """

    def nested_unstructure_as(self, unstructure_as: ExtendedType[_T], val: _T) -> Any:
        """
        Calls :py:meth:`Unstructurer.unstructure_as` of ``self.unstructurer``
        passing on the user context.
        """
        return self.unstructurer.unstructure_as(unstructure_as, val, user_context=self.user_context)


class UnstructureHandler:
    """A base class for unstructuring logic attached to a type."""

    def unstructure(
        self,
        context: UnstructurerContext,  # noqa: ARG002
        value: Any,
    ) -> Any:
        """
        Unstructures (serializes) the given ``value`` given ``context``.

        It is guaranteed that
        ``isinstance_ext(val, get_lookup_order(context.unstructure_as)) == True``
        (see :py:func:`isinstance_ext` and :py:func:`get_lookup_order`).
        """
        return self.simple_unstructure(value)

    def simple_unstructure(self, value: Any) -> Any:
        """
        Unstructures the given ``value``.

        Use for the cases where the information from ``context`` is not needed.
        If :py:meth:`unstructure` is not defined, this method must be defined.
        """
        raise NotImplementedError(
            "`UnstructureHandler` must implement either `unstructure()` or `simple_unstructure()`"
        )


class Unstructurer:
    def __init__(self, handlers: Mapping[Any, UnstructureHandler] = {}):
        self._handlers = dict(handlers)

    def unstructure_as(
        self, unstructure_as: ExtendedType[_T], val: _T, user_context: Any = None
    ) -> Any:
        """
        Unstructures (serializes) the given ``value`` as the type ``unstructure_as``
        with an optional ``user_context`` (which will be passed to the handlers).

        Calls :py:func:`isinstance_ext` at the beginning,
        raising :py:class:`UnstructuringError` on failure.

        Raises :py:class:`UnstructuringError` for any unstructuring-related error.
        """
        lookup_order = get_lookup_order(unstructure_as)

        # We need this check to allow `Union` unstructuring to work
        # (otherwise this check would have to be implemented manually in all handlers).
        if not isinstance_ext(val, lookup_order):
            # Note that `UnionType` does not have `__name__` (for whatever reason),
            # but it always passes `isinstance_ext()`, so it won't appear in this branch.
            raise UnstructuringError(f"The value must be of type `{unstructure_as.__name__}`")

        context = UnstructurerContext(
            unstructurer=self, unstructure_as=unstructure_as, user_context=user_context
        )
        stack = GeneratorStack[UnstructurerContext, Any](context, val)

        for tp in lookup_order:
            handler = self._handlers.get(tp, None)
            result = stack.push(handler.unstructure if handler else None)
            if result is not Result.UNDEFINED:
                return result

        if stack.is_empty():
            raise UnstructuringError(f"No handlers registered to unstructure as {unstructure_as}")

        raise UnstructuringError(
            f"Could not find a non-generator handler to unstructure as {unstructure_as}"
        )
