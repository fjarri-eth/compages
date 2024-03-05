from dataclasses import dataclass
from typing import Any, Union


@dataclass
class StructField:
    name: str

    def __str__(self) -> str:
        return self.name


@dataclass
class UnionVariant:
    type_: type

    def __str__(self) -> str:
        return f"<{self.type_.__name__}>"


@dataclass
class ListElem:
    index: int

    def __str__(self) -> str:
        return f"[{self.index}]"


@dataclass
class DictKey:
    key: Any

    def __str__(self) -> str:
        return f"key({self.key})"


@dataclass
class DictValue:
    key: Any

    def __str__(self) -> str:
        return f"[{self.key}]"


PathElem = Union[StructField, UnionVariant, ListElem, DictKey, DictValue]
