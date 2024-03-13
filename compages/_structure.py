from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Mapping
from typing import Any, NewType, TypeVar, overload

from ._common import GeneratorStack, get_lookup_order
from .path import PathElem


class StructuringError(Exception):
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


class SequentialStructureHandler(ABC):
    @abstractmethod
    def applies(self, structure_into: Any, val: Any) -> bool: ...

    @abstractmethod
    def __call__(self, structurer: "Structurer", structure_into: Any, val: Any) -> Any: ...


_T = TypeVar("_T")


class Structurer:
    def __init__(
        self,
        lookup_handlers: Mapping[Any, Callable[["Structurer", type, Any], Any]] = {},
        sequential_handlers: Iterable[SequentialStructureHandler] = [],
    ):
        self._lookup_handlers = lookup_handlers
        self._sequential_handlers = sequential_handlers

    @overload
    def structure_into(self, structure_into: NewType, val: Any) -> Any: ...

    @overload
    def structure_into(self, structure_into: type[_T], val: Any) -> _T: ...

    def structure_into(self, structure_into: Any, val: Any) -> Any:
        stack = GeneratorStack((self, structure_into), val)
        lookup_order = get_lookup_order(structure_into)

        for tp in lookup_order:
            handler = self._lookup_handlers.get(tp, None)
            if stack.push(handler):
                return stack.result()

        # Check all sequential handlers in order and see if there is one that applies
        # TODO (#10): should `applies()` raise an exception which we could collect
        # and attach to the error below, to provide more context on why no handlers were found?
        for sequential_handler in self._sequential_handlers:
            if sequential_handler.applies(structure_into, val):
                if stack.push(sequential_handler):
                    return stack.result()
                break

        if stack.is_empty():
            raise StructuringError(f"No handlers registered to structure into {structure_into}")

        raise StructuringError(
            f"Could not find a non-generator handler to structure into {structure_into}"
        )
