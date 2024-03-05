from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Mapping
from typing import Any, NewType, TypeVar, get_origin, overload

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


_T = TypeVar("_T")


class Structurer:
    def __init__(
        self,
        handlers: Mapping[Any, Callable[["Structurer", type, Any], Any]] = {},
        predicate_handlers: Iterable["PredicateStructureHandler"] = [],
    ):
        self._handlers = handlers
        self._predicate_handlers = predicate_handlers

    @overload
    def structure_into(self, structure_into: NewType, obj: Any) -> Any: ...

    @overload
    def structure_into(self, structure_into: type[_T], obj: Any) -> _T: ...

    def structure_into(self, structure_into: Any, obj: Any) -> Any:
        # First check if there is an exact match registered
        handler = self._handlers.get(structure_into, None)

        # If it's a newtype, try to fall back to a handler for the wrapped type
        if handler is None and isinstance(structure_into, NewType):
            handler = self._handlers.get(structure_into.__supertype__, None)

        # If it's a generic, see if there is a handler for the generic origin
        if handler is None:
            origin = get_origin(structure_into)
            if origin is not None:
                handler = self._handlers.get(origin, None)

        # Check all predicate handlers in order and see if there is one that applies
        # TODO (#10): should `applies()` raise an exception which we could collect
        # and attach to the error below, to provide more context on why no handlers were found?
        if handler is None:
            for predicate_handler in self._predicate_handlers:
                if predicate_handler.applies(structure_into, obj):
                    handler = predicate_handler
                    break

        if handler is None:
            raise StructuringError(f"No handlers registered to structure into {structure_into}")

        return handler(self, structure_into, obj)


class PredicateStructureHandler(ABC):
    @abstractmethod
    def applies(self, structure_into: Any, obj: Any) -> bool: ...

    @abstractmethod
    def __call__(self, structurer: Structurer, structure_into: Any, obj: Any) -> Any: ...
