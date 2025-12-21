from collections.abc import Callable, Generator
from dataclasses import is_dataclass
from enum import Enum
from types import GeneratorType, UnionType
from typing import Any, Literal, Protocol, Union, cast, get_origin, runtime_checkable


class Result(Enum):
    UNDEFINED = "result undefined"


class GeneratorStack[ContextType, ResultType]:
    """
    Maintains a stack of suspended continuations that take fixed arguments (``args``)
    and a value, yield a value to use to create the next continuation,
    and wait for the result of that continuation to be sent back to it.

    The stack is unrolled as soon as a function returning a result and not a continuation is pushed.
    """

    def __init__(self, context: ContextType, value: Any):
        self._context = context
        self._generators: list[Generator[ResultType, Any, Any]] = []
        self._value = value

    def push(
        self, func: None | Callable[[ContextType, Any], ResultType]
    ) -> ResultType | Literal[Result.UNDEFINED]:
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


@runtime_checkable
class TypedNewType[T_co](Protocol):
    """
    Unfortunately, :py:class:`typing.NewType` in Python is not generic,
    so we cannot express the concept of "the type of instances of of this type,
    given the type's type annotation".

    This protocol covers any instance of :py:class:`typing.NewType`
    and has the same properties as ``type[T]``.
    """

    def __call__(self, value: Any) -> T_co: ...

    __supertype__: "type[Any] | TypedNewType[Any]"

    __name__: str


type ExtendedType[T] = type[T] | TypedNewType[T]


class DataclassBase:
    """
    A marker type for built-in dataclasses (since they don't have a common base type).
    Use to attach dataclass-related handlers (e.g. :py:class:`IntoDataclassFromMapping`).
    """


class NamedTupleBase:
    """
    A marker type for built-in named tuples (since they don't have a common base type).
    Use to attach NamedTuple-related handlers (e.g. :py:class:`IntoNamedTupleFromMapping`).
    """


def is_named_tuple(tp: ExtendedType[Any]) -> bool:
    # There is no analogue of `is_dataclass()` for named tuples, so we have to write our own.
    # After Py3.12 there is `types.get_original_bases()` which should help.
    # Note: check that it works both for `collections.namedtuple` and `typing.NamedTuple`.
    return isinstance(tp, type) and issubclass(tp, tuple) and hasattr(tp, "_fields")


def isinstance_ext(val: Any, lookup_order: list[ExtendedType[Any]]) -> bool:
    """
    An extended :py:func:`isinstance` working with newtypes and generic types.

    Instead of an actual type ``tp`` takes the return value of ``get_lookup_order(tp)``
    (for performance reasons).

    If ``tp`` is a regular type, returns ``isinstance(val, tp)``.

    If ``tp`` is a `NewType`, returns ``isinstance(val, base_tp)`` where ``base_tp``
    is the first regular supertype of the newtype hierarchy.

    If ``tp`` is a generic, ``isinstance_ext()`` **does not** attempt to introspect the value
    (not that it has any means to, at this level),
    only checking for ``isinstance()`` with the origin.
    That is, ``isinstance_ext(val, list[int]) == isinstance(val, list)``,
    regardless of what type the elements of `val` are
    (checking that is the responsibility of handlers).

    As a corollary or that, ``isinstance_ext(val, UnionType[...])`` is always ``True``.
    """
    for tp in lookup_order:
        if tp is UnionType:
            return True
        # Mypy doesn't like it, but that's how Python works.
        if tp is Union:  # type: ignore[comparison-overlap]
            return True
        if isinstance(tp, type) and get_origin(tp) is None:
            return isinstance(val, tp)

    # There must be at least one regular type in the lookup order.
    raise RuntimeError(  # pragma: no cover
        f"This is supposed to be unreachable. "
        f"Value was {val} and its lookup order was {lookup_order}"
    )


def get_lookup_order(tp: ExtendedType[Any]) -> list[ExtendedType[Any]]:
    """
    Returns the structuring/unstructuring handler lookup order for regular types, generic types,
    or newtypes.

    The order is the following:

    - For a regular type, it equals to its ``.mro()`` without the last element
      (``builtins.object``).
    - For a :py:class`typing.NewType` instance, the order is the ``tp``
      followed by the lookup order for ``tp.__supertype__``.
    - For a generic (something with a non-``None`` ``typing.get_origin()``),
      the order is ``tp`` followed by the lookup order for the origin.
    - For a dataclass, a :py:class:`DataclassBase` marker type is appended
      to the end of the returned list.
    - For a named tuple, a :py:class:`NamedTupleBase` marker type
      is inserted just before ``tuple``.

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
