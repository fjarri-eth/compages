Public API
==========

.. currentmodule:: compages


Entry points
------------

.. autoclass:: Structurer
   :members:

.. autoclass:: Unstructurer
   :members:


Custom handlers
---------------

.. autoclass:: StructureHandler()
   :members:

.. autoclass:: StructurerContext()
   :members:

.. autoclass:: UnstructureHandler()
   :members:

.. autoclass:: UnstructurerContext()
   :members:

.. autoclass:: StructLikeOptions
   :members:


Type resolution
---------------

.. autoclass:: DataclassBase()

.. autoclass:: NamedTupleBase()


Type resolution (**hazmat**)
----------------------------

These functions define the logic of type lookup in structurers and unstructurers.
They are not supposed to be used by themselves, they are exported to keep the documentation of that logic in one place.


.. autoclass:: TypedNewType()
   :show-inheritance:

.. autofunction:: get_lookup_order

.. autofunction:: isinstance_ext


Built-in structuring handlers
-----------------------------

.. autoclass:: IntoBool
   :show-inheritance:

.. autoclass:: IntoBytes
   :show-inheritance:

.. autoclass:: IntoDataclassFromMapping
   :show-inheritance:

.. autoclass:: IntoDataclassFromSequence
   :show-inheritance:

.. autoclass:: IntoDict
   :show-inheritance:

.. autoclass:: IntoFloat
   :show-inheritance:

.. autoclass:: IntoInt
   :show-inheritance:

.. autoclass:: IntoList
   :show-inheritance:

.. autoclass:: IntoNamedTupleFromMapping
   :show-inheritance:

.. autoclass:: IntoNamedTupleFromSequence
   :show-inheritance:

.. autoclass:: IntoNone
   :show-inheritance:

.. autoclass:: IntoStr
   :show-inheritance:

.. autoclass:: IntoTuple
   :show-inheritance:

.. autoclass:: IntoUnion
   :show-inheritance:


Built-in structuring handlers
-----------------------------

.. autoclass:: AsBool
   :show-inheritance:

.. autoclass:: AsBytes
   :show-inheritance:

.. autoclass:: AsDataclassToDict
   :show-inheritance:

.. autoclass:: AsDataclassToList
   :show-inheritance:

.. autoclass:: AsDict
   :show-inheritance:

.. autoclass:: AsFloat
   :show-inheritance:

.. autoclass:: AsInt
   :show-inheritance:

.. autoclass:: AsList
   :show-inheritance:

.. autoclass:: AsNamedTupleToDict
   :show-inheritance:

.. autoclass:: AsNamedTupleToList
   :show-inheritance:

.. autoclass:: AsNone
   :show-inheritance:

.. autoclass:: AsStr
   :show-inheritance:

.. autoclass:: AsTuple
   :show-inheritance:

.. autoclass:: AsUnion
   :show-inheritance:


Errors
------

.. autoclass:: StructuringError
   :members:

.. autoclass:: UnstructuringError
   :members:

.. automodule:: compages.path
   :members:

