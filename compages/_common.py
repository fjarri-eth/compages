from collections.abc import Callable, Generator
from enum import Enum
from types import GeneratorType
from typing import Any, Generic, Literal, NewType, ParamSpec, TypeVar, cast, get_origin

P = ParamSpec("P")

_ResultType = TypeVar("_ResultType")


class Result(Enum):
    UNDEFINED = "result undefined"


class GeneratorStack(Generic[_ResultType]):
    """
    Maintains a stack of suspended continuations that take fixed arguments (``args``)
    and a value, yield a value to use to create the next continuation,
    and wait for the result of that continuation to be sent back to it.

    The stack is unrolled as soon as a function returning a result and not a continuation is pushed.
    """

    def __init__(self, args: tuple[Any, ...], value: Any):
        self._args = args
        self._generators: list[Generator[_ResultType, Any, Any]] = []
        self._value = value

    def push(
        self, func: None | Callable[P, _ResultType]
    ) -> _ResultType | Literal[Result.UNDEFINED]:
        """
        Takes a function that takes the fixed ``args`` passed to the constructor
        and the current ``value``, and either returns a result or a continuation.

        If ``func`` is ``None``, no action is taken.

        If the function returns a continuation, it is saved in the stack,
        and the yielded value is saved to pass to the next function.
        Returns ``Result.UNDEFINED``.

        If the function returns a result, the stack is unrolled by sending the result
        to the last continuation, sending its result to the second to last continuation,
        and so on.
        Returns the result.
        """
        if func is None:
            return Result.UNDEFINED

        result = func(*self._args, self._value)

        if isinstance(result, GeneratorType):
            # Advance to the first `yield` and get the value to pass to the lower levels.
            self._value = next(result)
            self._generators.append(result)
            return Result.UNDEFINED

        # Unroll the stack
        for generator in reversed(self._generators):
            try:
                generator.send(result)
            except StopIteration as exc:
                result = exc.value
                continue
            raise RuntimeError("Expected only one yield in a generator")

        return result

    def is_empty(self) -> bool:
        return not self._generators


def get_lookup_order(tp: Any) -> list[Any]:
    """
    Returns the structuring/unstructuring handler lookup order for regular types, generic types,
    or newtypes.

    The order is the following:
    - For a regular type, it equals to its ``.mro()`` without the last element
      (``builtins.object``).
    - For a ``typing.NewType`` instance, the order is the ``tp`` followed by the lookup order for
      ``tp.__supertype__``.
    - For a generic (something with a non-``None`` ``typing.get_origin()``),
      the order is ``tp`` followed by the lookup order for the origin.

    .. note::

        If you want to assign a handler for generic unions, note that ``typing.Union[...]``
        has the origin ``typing.Union``, but ``type1 | type2 | ...`` has the origin
        ``types.UnionType``.
    """
    if isinstance(tp, NewType):
        return [tp, *get_lookup_order(tp.__supertype__)]

    origin = get_origin(tp)
    if origin is not None:
        return [tp, *get_lookup_order(origin)]

    if hasattr(tp, "mro"):
        return cast("list[Any]", tp.mro()[:-1])

    return [tp]
