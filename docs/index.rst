Compages, structuring/unstructuring library
===========================================

Overview
--------

``compages`` is a library converting data between well-typed representation (that's what a program typically operates with) and a combination of builtin types (suitable for serializing into some storage/transfer format, or used directly as JSON).

``compages`` is designed to be non-invasive, that is it does not require the user to employ any base types, specific annotations, or magic methods.


Similar libraries
-----------------

- `cattrs <https://pypi.org/project/cattrs/>`_ (which is very similar to ``compages``, and is the source of the terms "structure/unstructure")
- `marshmallow <https://pypi.org/project/marshmallow/>`_
- `pydantic <https://pypi.org/project/pydantic/>`_
- `maat <https://pypi.org/project/Maat2/>`_
- `mashumaro <https://pypi.org/project/mashumaro/>`_
- `desert <https://pypi.org/project/desert/>`_

Why not just use either of these libraries?
If you already use one of them, and it works for you, there is no need to change.
``pydantic``, in particular, is (most likely) a superset of ``compages`` in terms functionality, but to support (de)serialization for non-standard types you will have to write more code.
If you're starting a new project, ``compages`` offers a tiny codebase, support for third-party types, and low boilerplate for a certain subset of problems.


A bit of philosophy
-------------------

The overview actually simplifies things a little.
If you are familiar with Rust's ``serde``, ``compages`` can be viewed as its Python analogue --- it can convert typed data into an "intermediate representation" (a combination of integers, strings, lists etc) which can be further passed to a specific format implementation (e.g. JSON or MessagePack).
In this analogy, :py:class:`~compages.Structurer` is ``serde::Deserializer``, and :py:class:`~compages.Unstructurer` is ``serde::Serializer``.

But, in general, ``compages`` does not mandate any specific source or target representations --- you can unstructure into, say, a combination of AST tokens, or something else.
The only asymmetry between the "structured" and "unstructured" representations is that the conversion in either direction is driven by the types from the "structured" side.
That is, when you structure (read: deserialize), you structure *into* some type (the type of the value you expect to get); when you unstructure (serialize), you unstructure *as* some type (the type you currently have at hand).


Basic operation
---------------

The operation of an (un)structurer is very simple.
An (un)structurer contains a mapping of types to handlers.
Types can be either regular Python types (derived from ``type``), or more exotic ones like ``NewType`` instances, generics, or special type markers (which will be covered later).

When :py:meth:`~compages.Structurer.structure_into` or :py:meth:`~compages.Unstructurer.unstructure_as` are called, they take the ethalon type (to deserialize into, or serialize from, respectively) and the value.
In the unstructuring case, the value is expected to be an instance of the given type (see :py:func:`~compages.isinstance_ext` for specifics about the exotic cases).
``compages`` generates the lookup order for the type (see :py:func:`~compages.get_lookup_order` for details), which, for regular types, is just MRO without the finalizing ``object``.
Then it goes through the lookup order until it finds a type present in the handler mapping, and calls that handler, returning whatever it returns.

.. testcode::

   from compages import *

   class A: pass
   class B(A): pass

   class AsA(UnstructureHandler):
       def unstructure(self, context, value):
           return type(value).__name__


   unstructurer = Unstructurer({A: AsA()})
   # The handler for `A` is called.
   print(unstructurer.unstructure_as(A, A()))
   # The handler for `B` is not found, the next in MRO is `A`,
   # which has a handler registered.
   print(unstructurer.unstructure_as(B, B()))

.. testoutput::

   A
   B


Newtypes
--------

One might wonder, why would you need to give the type explicitly to :py:meth:`~~compages.Unstructurer.unstructure_as`?
Cannot it just take it from the given value?

For regular types it can, but many types in Python do not exist in runtime (that is, they cannot be extracted from the value via reflection).
The examples of that are newtypes or generic types.

A type created with :py:class:`typing.NewType` is essentially an identity function that is processed in a certain way by the type checker.
If you wrap an ``int`` with a custom ``NewType``, the value will still have the type ``int`` at runtime.
But it is often necessary to (de)serialize some newtype differently to its wrapped type.
For example, you may have a ``HexInt`` newtype that should be serialized as a hex string to JSON, while ``int`` values should just be serialized as integers.

.. testcode::

   from compages import *
   from typing import NewType

   HexInt = NewType("HexInt", int)
   OtherInt = NewType("OtherInt", int)

   class AsHexInt(UnstructureHandler):
       def unstructure(self, context, value):
           return hex(value)

   # Using the built-in `compages.AsInt` handler that just returns the integer.
   unstructurer = Unstructurer({int: AsInt(), HexInt: AsHexInt()})

   # Normal integer serializes as an integer
   print(unstructurer.unstructure_as(int, 10))
   # HexInt serializes as a hex string
   print(unstructurer.unstructure_as(HexInt, 10))
   # There is no handler for OtherInt, so it users the handler of the supertype (int)
   print(unstructurer.unstructure_as(OtherInt, 10))

.. testoutput::

   10
   0xa
   10


Lists and other generics
------------------------

The general principle of working with nested types in ``compages`` is that the handler for a type will recursively call the same (un)structurer for its fields or elements.
The (un)structurer is passed as a part of the ``context`` variable you saw in the handlers above.

``compages`` has built-in handlers for lists and dictionaries, but the user can write their own if they wish --- they only use public types and functions.

.. testcode::

   from compages import *

   class AsHexInt(UnstructureHandler):
       def unstructure(self, context, value):
           return hex(value)

   unstructurer = Unstructurer({int: AsHexInt(), list: AsList()})
   print(unstructurer.unstructure_as(list[int], [10, 20]))

.. testoutput::

   ['0xa', '0x14']

.. note::

   An important moment here is that even though the handler is attached to ``list`` (that it, it works for any list) you cannot just call ``unstructure_as(list, ...)`` --- unstructuring is driven by **type annotations**, not runtime types.
   So the unstructurer must be told what is the type the items of the list must be treated as (which, as was explained in the previous section, could be a newtype, or a generic type, which are not accessible at runtime).

   To be more precise, this is not a limitation of the library, but specifically of the built-in ``AsList`` handler (the built-in dictionary, named tuple, and dataclass handlers have the same requirement).
   You are free to write your own one free from this limitation if your code operates under some additional assumptions.


Dataclasses and marker types
----------------------------

``compages`` has built-in handlers for dataclasses and named tuples.
The problem is that neither of those have a base class they can be identified by.
That is why :py:func:`~compages.get_lookup_order` adds marker types :py:class:`~compages.DataclassBase` and :py:class:`~compages.NamedTupleBase` allowing one to assign handlers to them.

.. testcode::

   from compages import *
   from dataclasses import dataclass

   @dataclass
   class Foo:
       x: int
       y: str

   unstructurer = Unstructurer({
      int: AsInt(),
      str: AsStr(),
      DataclassBase: AsDataclassToDict()
   })
   print(unstructurer.unstructure_as(Foo, Foo(x=1, y="bar")))

.. testoutput::

   {'x': 1, 'y': 'bar'}


Union types
-----------

There is a built-in handler for union types.
The logic it employs is pretty simple: try each type in turn until something returns a result.

For this section we are using ``Structure`` since it is more illustrative.

.. testcode::

   from compages import *
   from dataclasses import dataclass
   from types import UnionType

   @dataclass
   class Foo:
       x: int | str

   structurer = Structurer({
      int: IntoInt(),
      str: IntoStr(),
      DataclassBase: IntoDataclassFromMapping(),
      UnionType: IntoUnion()
   })
   print(structurer.structure_into(Foo, {"x": 1}))
   print(structurer.structure_into(Foo, {"x": "a"}))

.. testoutput::

   Foo(x=1)
   Foo(x='a')


Note that there are two union types in Python: ``typing.Union[...]`` produces :py:class`typing.Union` types, while ``|`` produces :py:class`types.UnionType` types.
If you want to support both, you have to assign handlers to both.

You may wonder, what happens when the value is neither integer nor string? See `Errors`_.


Handler stack
-------------

When we said above that we call the handler and return whatever it returns, that was a simplification.
That will be enough most of the time, but sometimes more a complicated logic is necessary.

In Ethereum, there are several transaction types that are identified by ``"type": <number>`` in the transaction dictionary.
You don't want to have the ``type`` field in the datastructures in the code (since they are already typed), but yoou want it to be present in the serialized transaction.
You could manually call :py:class`~compages.AsDataclassToDict` in the handler for each transaction type and then amend the result, but that leads to code duplication (especially when you want to use some non-default options of ``AsDataclassToDict()``).

Instead, a handler can ``yield``, which will pass the execution to the next handler in the lookup order list.
The result will be returned from ``yield``, and the handler can amend it.
This can happen multiple times, but should finish with a handler that does not call ``yield``.

.. testcode::

   from compages import *
   from dataclasses import dataclass

   @dataclass
   class Type1Tx:
       x: int
       y: str

   @dataclass
   class Type2Tx:
       z: int
       w: str

   class AsTx(UnstructureHandler):
       def __init__(self, type):
           self.type = type

       def unstructure(self, context, value):
           tx_dict = yield value
           tx_dict["type"] = self.type
           return tx_dict

   unstructurer = Unstructurer({
      int: AsInt(),
      str: AsStr(),
      DataclassBase: AsDataclassToDict(),
      Type1Tx: AsTx(1),
      Type2Tx: AsTx(2)
   })
   print(unstructurer.unstructure_as(Type1Tx, Type1Tx(x=1, y="a")))
   print(unstructurer.unstructure_as(Type2Tx, Type2Tx(z=3, w="b")))

.. testoutput::

   {'x': 1, 'y': 'a', 'type': 1}
   {'z': 3, 'w': 'b', 'type': 2}


Errors
------

Handlers are expected to nest errors from (un)structuring nested fields or elements.
That is, when a handler is calling :py:meth:`~compages.StructurerContext.nested_structure_into` or :py:meth:`~compages.UnstructurerContext.nested_unstructure_as`, it is expected to catch :py:class:`~compages.StructuringError` or :py:class:`~compages.UnstructuringError`, collect them, and raise a new error with the nested errors and their corresponding path elements (that is, item number, item key, or field name).
You can look at how the built-in handlers do it.

As a result, ``str()`` of the final error will contain all the nested errors that occurred deep in the hierarchy.

.. testcode::

   from compages import *
   from dataclasses import dataclass
   from types import UnionType

   @dataclass
   class Foo:
       x: int | str
       y: list[int]

   @dataclass
   class Bar:
       f: Foo

   structurer = Structurer({
      int: IntoInt(),
      str: IntoStr(),
      list: IntoList(),
      DataclassBase: IntoDataclassFromMapping(),
      UnionType: IntoUnion()
   })
   try:
       structurer.structure_into(Bar, {"f": {"x": None, "y": ["a"]}})
   except StructuringError as exc:
       print(exc)

.. testoutput::

    Failed to structure a dict into <class 'Bar'>
      f: Failed to structure a dict into <class 'Foo'>
        f.x: Cannot structure into int | str
          f.x.<int>: The value must be an integer
          f.x.<str>: The value must be a string
        f.y: Cannot structure into list[int]
          f.y.[0]: The value must be an integer


.. toctree::
   :maxdepth: 2
   :caption: Contents:

   api
   changelog


Indices and tables
------------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

