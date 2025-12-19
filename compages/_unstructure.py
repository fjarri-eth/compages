from collections.abc import Callable, Mapping
from typing import Any, NamedTuple, TypeVar

from ._common import ExtendedType, GeneratorStack, Result, get_lookup_order, isinstance_ext
from .path import PathElem


class UnstructuringError(Exception):
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


class UnstructurerContext(NamedTuple):
    unstructurer: "Unstructurer"
    unstructure_as: ExtendedType[Any]


class UnstructureHandler:
    def unstructure(
        self,
        context: UnstructurerContext,  # noqa: ARG002
        value: Any,
    ) -> Any:
        """
        Unstructures (serializes) the given ``value`` given ``context``.

        It is guaranteed that
        ``isinstance_ext(val, get_lookup_order(context.unstructure_as)) == True``.
        """
        return self.simple_unstructure(value)

    def simple_unstructure(self, value: Any) -> Any:
        raise NotImplementedError(
            "`UnstructureHandler` must implement either `unstructure()` or `simple_unstructure()`"
        )


class Unstructurer:
    def __init__(
        self,
        handlers: Mapping[Any, Callable[[UnstructurerContext, Any], Any]] = {},
    ):
        self._handlers = dict(handlers)

    def unstructure_as(self, unstructure_as: ExtendedType[_T], val: _T) -> Any:
        lookup_order = get_lookup_order(unstructure_as)

        # We need this check to allow `Union` unstructuring to work
        # (otherwise this check would have to be implemented manually in all handlers).
        if not isinstance_ext(val, lookup_order):
            # Note that `UnionType` does not have `__name__` (for whatever reason),
            # but it always passes `isinstance_ext()`, so it won't appear in this branch.
            raise UnstructuringError(f"The value must be of type `{unstructure_as.__name__}`")

        context = UnstructurerContext(unstructurer=self, unstructure_as=unstructure_as)
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
