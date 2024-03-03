import typing
from abc import ABC, abstractmethod
from dataclasses import MISSING, fields, is_dataclass
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Mapping,
    NewType,
    Optional,
    Sequence,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
    get_args,
    get_origin,
)

Path = List[Union[str, int]]


# TODO: a better name? Should emphasize that it's only to raise in handlers,
# not to catch externally.
class HandlingError(Exception):
    pass


class StructuringError(Exception):
    def __init__(self, path: Path, message: str, inner_errors=[]):
        super().__init__(message)
        self.message = message
        self.path = path
        self.inner_errors = inner_errors

    def path_str(self) -> str:
        return ".".join(str(item) for item in self.path) if self.path else "<root>"

    def __str__(self):
        messages = collect_messages(0, self)

        message_strings = [
            (" " * (level * 2) + f"{path}: {msg}") if level > 0 else msg
            for level, path, msg in messages]

        return "\n".join(message_strings)

def collect_messages(level: int, exc: StructuringError) -> List[Tuple[int, str, str]]:
    message = exc.args[0]
    result = [(level, exc.path_str(), exc.message)]
    for exc in exc.inner_errors:
        result.extend(collect_messages(level + 1, exc))
    return result


_T = TypeVar("_T")


class Structurer:
    def __init__(
        self,
        handlers: Mapping[Any, Callable[["Structurer", type, Path, Any], Any]] = {},
        predicate_handlers: Iterable["PredicateHandler"] = [],
    ):
        self._handlers = handlers
        self._predicate_handlers = predicate_handlers

    def structure_at_path(self, structure_into: Type[_T], path: Path, obj: Any) -> _T:
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
        # TODO: should `applies()` raise an exception which we could collect
        # and attach to the error below, to provide more context on why no handlers were found?
        if handler is None:
            for predicate_handler in self._predicate_handlers:
                if predicate_handler.applies(structure_into, obj):
                    handler = predicate_handler
                    break

        if handler is None:
            raise StructuringError(
                path, f"No handlers registered to structure into {structure_into}"
            )

        try:
            result = handler(self, structure_into, path, obj)
        except HandlingError as exc:
            raise StructuringError(path, str(exc)) from exc

        # Python typing is not advanced enough to enforce it,
        # so we are relying on the handler returning the type it was assigned to.
        return cast(_T, handler(self, structure_into, path, obj))

    def structure(self, structure_into: Type[_T], obj: Any) -> _T:
        return self.structure_at_path(structure_into, [], obj)


class PredicateHandler(ABC):
    @abstractmethod
    def applies(self, structure_into, obj): ...

    @abstractmethod
    def __call__(self, structurer, structure_into, path, obj): ...
