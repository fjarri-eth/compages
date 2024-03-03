from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


class PathElem(ABC):
    @abstractmethod
    def __str__(self) -> str: ...


@dataclass
class StructField(PathElem):
    name: str

    def __str__(self):
        return self.name


@dataclass
class UnionVariant(PathElem):
    type_: type

    def __str__(self):
        return f"<{self.type_.__name__}>"


@dataclass
class ListElem(PathElem):
    index: int

    def __str__(self):
        return f"[{self.index}]"


@dataclass
class DictKey(PathElem):
    key: Any

    def __str__(self):
        return f"key({self.key})"


@dataclass
class DictValue(PathElem):
    key: Any

    def __str__(self):
        return f"[{self.key}]"
