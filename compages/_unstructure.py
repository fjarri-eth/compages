from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Mapping
from typing import Any, NamedTuple, TypeVar

from ._common import ExtendedType, GeneratorStack, Result, get_lookup_order
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


class SequentialUnstructureHandler(ABC):
    @abstractmethod
    def applies(self, unstructure_as: Any, val: Any) -> bool: ...

    @abstractmethod
    def __call__(self, context: "UnstructurerContext", val: Any) -> Any: ...


_T = TypeVar("_T")


class UnstructurerContext(NamedTuple):
    unstructurer: "Unstructurer"
    unstructure_as: ExtendedType[Any]


class Unstructurer:
    def __init__(
        self,
        lookup_handlers: Mapping[Any, Callable[[UnstructurerContext, Any], Any]] = {},
        sequential_handlers: Iterable[SequentialUnstructureHandler] = [],
    ):
        self._lookup_handlers = dict(lookup_handlers)
        self._sequential_handlers = list(sequential_handlers)

    def unstructure_as(self, unstructure_as: ExtendedType[_T], val: _T) -> Any:
        context = UnstructurerContext(unstructurer=self, unstructure_as=unstructure_as)
        stack = GeneratorStack[UnstructurerContext, Any](context, val)
        lookup_order = get_lookup_order(unstructure_as)

        for tp in lookup_order:
            handler = self._lookup_handlers.get(tp, None)
            result = stack.push(handler)
            if result is not Result.UNDEFINED:
                return result

        # Check all sequential handlers in order and see if there is one that applies
        # TODO (#10): should `applies()` raise an exception which we could collect
        # and attach to the error below, to provide more context on why no handlers were found?
        for sequential_handler in self._sequential_handlers:
            if sequential_handler.applies(unstructure_as, val):
                result = stack.push(sequential_handler)
                if result is not Result.UNDEFINED:
                    return result
                break

        if stack.is_empty():
            raise UnstructuringError(f"No handlers registered to unstructure as {unstructure_as}")

        raise UnstructuringError(
            f"Could not find a non-generator handler to unstructure as {unstructure_as}"
        )
