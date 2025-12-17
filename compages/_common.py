from collections.abc import Callable, Generator
from dataclasses import is_dataclass
from enum import Enum
from types import GeneratorType
from typing import (
    Any,
    Generic,
    Literal,
    Protocol,
    TypeAlias,
    TypeVar,
    cast,
    get_origin,
    runtime_checkable,
)

_ResultType = TypeVar("_ResultType")

_ContextType = TypeVar("_ContextType")


class Result(Enum):
    UNDEFINED = "result undefined"


class GeneratorStack(Generic[_ContextType, _ResultType]):
    """
    Maintains a stack of suspended continuations that take fixed arguments (``args``)
    and a value, yield a value to use to create the next continuation,
    and wait for the result of that continuation to be sent back to it.

    The stack is unrolled as soon as a function returning a result and not a continuation is pushed.
    """

    def __init__(self, context: _ContextType, value: Any):
        self._context = context
        self._generators: list[Generator[_ResultType, Any, Any]] = []
        self._value = value

    def push(
        self, func: None | Callable[[_ContextType, Any], _ResultType]
    ) -> _ResultType | Literal[Result.UNDEFINED]:
        """
        Takes a function that takes two arguments (``context`` passed to the constructor
        and the current ``value``), and either returns a result or a continuation.

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

        result = func(self._context, self._value)

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


_T_co = TypeVar("_T_co", covariant=True)


# Unfortunately, `NewType` in Python is not generic, so we cannot express the concept of
# "the type of instances of of this type, given the type's type annotation"
#
# This protocol covers any instance of `NewType` and has the same properties as `type[_T]`.
@runtime_checkable
class TypedNewType(Protocol, Generic[_T_co]):
    def __call__(self, value: Any) -> _T_co: ...

    __supertype__: "type[Any] | TypedNewType[Any]"


_T = TypeVar("_T")


ExtendedType: TypeAlias = type[_T] | TypedNewType[_T]


class DataclassBase:
    pass


class NamedTupleBase:
    pass


def is_named_tuple(tp: ExtendedType[Any]) -> bool:
    # There is no analogue of `is_dataclass()` for named tuples, so we have to write our own.
    # After Py3.12 there is `types.get_original_bases()` which should help.
    # Note: check that it works both for `collections.namedtuple` and `typing.NamedTuple`.
    return isinstance(tp, type) and issubclass(tp, tuple) and hasattr(tp, "_fields")


def get_lookup_order(tp: ExtendedType[Any]) -> list[ExtendedType[Any]]:
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
    if isinstance(tp, TypedNewType):
        return [tp, *get_lookup_order(tp.__supertype__)]

    origin = get_origin(tp)
    if origin is not None:
        return [tp, *get_lookup_order(origin)]

    if hasattr(tp, "mro"):
        # [:-1] removes the last element of the MRO (`object`).
        mro = tp.mro()[:-1]

        if is_dataclass(tp):
            mro.append(DataclassBase)

        if is_named_tuple(tp):
            # Add the marker in front of `tuple` (which will be present in the MRO),
            # so that the `NamedTuple` handler would trigger before the handlers
            # attached to `tuple`.
            mro.insert(mro.index(tuple), NamedTupleBase)

        # Can cast here since all the elements will be isntances of `type`.
        return cast("list[ExtendedType[Any]]", mro)

    return [tp]
