from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from ._common import GeneratorStack, get_lookup_order
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
    def __call__(self, unstructurer: "Unstructurer", unstructure_as: Any, val: Any) -> Any: ...


class Unstructurer:
    def __init__(
        self,
        lookup_handlers: Mapping[Any, Callable[["Unstructurer", Any, Any], Any]] = {},
        sequential_handlers: Iterable[SequentialUnstructureHandler] = [],
    ):
        self._lookup_handlers = dict(lookup_handlers)
        self._sequential_handlers = list(sequential_handlers)

    def unstructure_as(self, unstructure_as: Any, val: Any) -> Any:
        stack = GeneratorStack((self, unstructure_as), val)
        lookup_order = get_lookup_order(unstructure_as)

        for tp in lookup_order:
            handler = self._lookup_handlers.get(tp, None)
            if stack.push(handler):
                return stack.result()

        # Check all sequential handlers in order and see if there is one that applies
        # TODO (#10): should `applies()` raise an exception which we could collect
        # and attach to the error below, to provide more context on why no handlers were found?
        for sequential_handler in self._sequential_handlers:
            if sequential_handler.applies(unstructure_as, val):
                if stack.push(sequential_handler):
                    return stack.result()
                break

        if stack.is_empty():
            raise UnstructuringError(f"No handlers registered to unstructure as {unstructure_as}")

        raise UnstructuringError(
            f"Could not find a non-generator handler to unstructure as {unstructure_as}"
        )
