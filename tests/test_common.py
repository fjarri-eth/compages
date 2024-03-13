import pytest
from compages._common import GeneratorStack


def test_normal_operation():
    args = (1, 2)
    stack = GeneratorStack(args, ["a"])

    assert stack.is_empty()

    # `None` is just ignored, and stack is not finalized
    assert not stack.push(None)

    def f1(arg1, arg2, val):
        assert (arg1, arg2) == args
        new_val = yield [*val, "b"]
        return [*new_val, "c"]

    # We pushed a generator, so the stack is not finalized yet
    assert not stack.push(f1)

    def f2(arg1, arg2, val):
        assert (arg1, arg2) == args
        return [*val, "d"]

    # This is a normal function, so the stack is finalized and unrolled
    assert stack.push(f2)
    assert stack.result() == ["a", "b", "d", "c"]


def test_multiple_yields():
    args = (1, 2)
    stack = GeneratorStack(args, ["a"])

    def f1(arg1, arg2, val):
        assert (arg1, arg2) == args
        new_val = yield [*val, "b"]
        new_val = yield [*new_val, "d"]
        return [*val, "c"]

    # We can't tell that there is a second yield until we start unrolling, so this passes
    stack.push(f1)

    def f2(arg1, arg2, val):
        assert (arg1, arg2) == args
        return [*val, "d"]

    with pytest.raises(RuntimeError, match="Expected only one yield in a generator"):
        stack.push(f2)
