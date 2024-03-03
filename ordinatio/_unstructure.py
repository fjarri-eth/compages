from abc import ABC, abstractmethod
from dataclasses import fields, is_dataclass
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Mapping,
    NewType,
    Optional,
    Union,
    get_args,
    get_origin,
)

IR = Union[None, bool, int, str, bytes, List["IR"], Dict[str, "IR"]]


class UnstructuringError(Exception):
    pass


class Unstructurer:
    def __init__(
        self,
        handlers: Mapping[Any, Callable[["Unstructurer", type, Any], IR]],
        predicate_handlers,
    ):
        self._handlers = handlers
        self._predicate_handlers = predicate_handlers

    def unstructure_as(self, unstructure_as: type, obj: Any) -> IR:
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
        # TODO: should `applies()` raise an exception which we could collect
        # and attach to the error below, to provide more context on why no handlers were found?
        if handler is None:
            for predicate_handler in self._predicate_handlers:
                if predicate_handler.applies(unstructure_as, obj):
                    handler = predicate_handler
                    break

        if handler is None:
            raise UnstructuringError(f"No handlers registered to unstructure as {unstructure_as}")

        return handler(self, unstructure_as, obj)

    def unstructure(self, obj: Any) -> IR:
        return self.unstructure_as(type(obj), obj)


class PredicateUnstructureHandler(ABC):
    @abstractmethod
    def applies(self, unstructure_as, obj): ...

    @abstractmethod
    def __call__(self, unstructurer, unstructure_as, obj): ...
