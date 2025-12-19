from collections.abc import Mapping
from typing import Any, NamedTuple, TypeVar

from ._common import ExtendedType, GeneratorStack, Result, get_lookup_order
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


class StructurerContext(NamedTuple):
    structurer: "Structurer"
    structure_into: ExtendedType[Any]


class StructureHandler:
    def structure(
        self,
        context: StructurerContext,  # noqa: ARG002
        value: Any,
    ) -> Any:
        return self.simple_structure(value)

    def simple_structure(self, value: Any) -> Any:
        raise NotImplementedError(
            "`StructureHandler` must implement either `structure()` or `simple_structure()`"
        )


class Structurer:
    def __init__(
        self,
        handlers: Mapping[Any, StructureHandler] = {},
    ):
        self._handlers = dict(handlers)

    def structure_into(self, structure_into: ExtendedType[_T], val: Any) -> _T:
        context = StructurerContext(structurer=self, structure_into=structure_into)
        stack = GeneratorStack[StructurerContext, _T](context, val)
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
