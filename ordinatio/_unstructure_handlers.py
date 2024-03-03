from dataclasses import fields, is_dataclass
from typing import Any, List, Optional, get_args

from ._unstructure import IR, PredicateUnstructureHandler


def unstructure_list(unstructurer: "Unstructurer", unstructure_as: type, obj: List[Any]) -> IR:
    # TODO: check that get_origin() is a List
    args = get_args(unstructure_as)
    if len(args) > 0:
        return [unstructurer.unstructure_as(args[0], item) for item in obj]

    # This can happen if we're just give a list of items to unstructure,
    # as opposed to pulling a List[...] annotation out of a dataclass.
    return [unstructurer.unstructure(item) for item in obj]


def unstructure_union(unstructurer: "Unstructurer", unstructure_as: type, obj: Optional[Any]) -> IR:
    args = get_args(unstructure_as)
    for arg in args:
        try:
            return unstructurer.unstructure_as(arg, obj)
        except UnstructuringError:  # noqa: PERF203
            continue

    raise UnstructuringError(f"Cannot unstructure as {unstructure_as}")


def unstructure_none(_unstructurer: "Unstructurer", _unstructure_as: type, _obj: None) -> IR:
    return None


class UnstructureDataclassAsDict(PredicateUnstructureHandler):
    def __init__(self, name_converter=lambda name, metadata: name):
        self._name_converter = name_converter

    def applies(self, unstructure_as, obj):
        return is_dataclass(unstructure_as)

    def __call__(self, unstructurer, unstructure_as, obj):
        result = {}
        for field in fields(unstructure_as):
            result_name = self._name_converter(field.name, field.metadata)
            result[result_name] = unstructurer.unstructure_as(field.type, getattr(obj, field.name))
        return result
