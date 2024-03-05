from dataclasses import dataclass
from typing import Any


@dataclass
class StructField:
    """A structure field."""

    name: str

    def __str__(self) -> str:
        return self.name


@dataclass
class UnionVariant:
    """A union variant."""

    type_: type

    def __str__(self) -> str:
        return f"<{self.type_.__name__}>"


@dataclass
class ListElem:
    """A list element."""

    index: int

    def __str__(self) -> str:
        return f"[{self.index}]"


@dataclass
class DictKey:
    """A dictionary key."""

    key: Any

    def __str__(self) -> str:
        return f"key({self.key})"


@dataclass
class DictValue:
    """A dictionary value."""

    key: Any

    def __str__(self) -> str:
        return f"[{self.key}]"


PathElem = StructField | UnionVariant | ListElem | DictKey | DictValue
