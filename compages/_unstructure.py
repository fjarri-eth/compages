from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Mapping
from typing import Any, NewType, get_origin

from .path import PathElem


class UnstructuringError(Exception):
    def __init__(
        self, message: str, inner_errors: list[tuple[PathElem, "UnstructuringError"]] = []
    ):
        super().__init__(message)
        self.message = message
        self.inner_errors = inner_errors


class PredicateUnstructureHandler(ABC):
    @abstractmethod
    def applies(self, unstructure_as: Any, val: Any) -> bool: ...

    @abstractmethod
    def __call__(self, unstructurer: "Unstructurer", unstructure_as: Any, val: Any) -> Any: ...


class Unstructurer:
    def __init__(
        self,
        handlers: Mapping[Any, Callable[["Unstructurer", Any, Any], Any]] = {},
        predicate_handlers: Iterable[PredicateUnstructureHandler] = [],
    ):
        self._handlers = dict(handlers)
        self._predicate_handlers = list(predicate_handlers)

    def unstructure_as(self, unstructure_as: Any, val: Any) -> Any:
        # First check if there is an exact match registered
        handler = self._handlers.get(unstructure_as, None)

        # If it's a newtype, try to fall back to a handler for the wrapped type
        if handler is None and isinstance(unstructure_as, NewType):
            handler = self._handlers.get(unstructure_as.__supertype__, None)

        # If it's a generic, see if there is a handler for the generic origin
        if handler is None:
            origin = get_origin(unstructure_as)
            if origin is not None:
                handler = self._handlers.get(origin, None)

        # Check all predicate handlers in order and see if there is one that applies
        # TODO (#10): should `applies()` raise an exception which we could collect
        # and attach to the error below, to provide more context on why no handlers were found?
        if handler is None:
            for predicate_handler in self._predicate_handlers:
                if predicate_handler.applies(unstructure_as, val):
                    handler = predicate_handler
                    break

        if handler is None:
            raise UnstructuringError(f"No handlers registered to unstructure as {unstructure_as}")

        return handler(self, unstructure_as, val)
