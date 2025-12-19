Changelog
=========

0.4.0 (in development)
----------------------

Changed
^^^^^^^

- Handlers now take a single context argument (``StructurerContext`` or ``UnstructurerContext``) which contain the structurer and the target type. (PR_20_)
- Support any ``Sequence`` type instead of just a list when structuring into a struct-like. Consequently, the handlers had ``list`` changed to ``sequence``. (PR_22_)
- Support any ``Mapping`` type or ``MappingProxyType`` instead of just a dict when structuring into a struct-like. Consequently, the handlers had ``Dict`` changed to ``Mapping``. (PR_22_)
- Uniformized structurer/unstructurers. Now they are all classes based on ``StructureHandler``/``UnstructureHandler``. ``simple_structurer``, ``simple_unstructurer`` removed. (PR_23_)
- ``simple_typechecked_unstructurer`` removed, now ``Unstructurer.unstructure_as`` performs the typecheck. (PR_23_)
- Skip final default values when unstructuring from a struct-like into a sequence. (PR_23_)


Added
^^^^^

- Support for default factory in dataclasses. (PR_21_)
- Support for ``NamedTuple`` types. (PR_21_)


Fixed
^^^^^

- Resolve type hints in dataclasses if they are given as strings. (PR_20_)


.. _PR_20: https://github.com/fjarri-eth/compages/pull/20
.. _PR_21: https://github.com/fjarri-eth/compages/pull/21
.. _PR_22: https://github.com/fjarri-eth/compages/pull/22
.. _PR_23: https://github.com/fjarri-eth/compages/pull/23


0.3.0 (2024-03-15)
------------------

Changed
^^^^^^^

- Renamed "handlers" and "predicate handlers" to "lookup handlers" and "sequential handlers". (PR_15_)


Added
^^^^^

- Skip fields equal to the defaults when unstructuring dataclasses. (PR_13_)
- Generator-based deferring to lower level structuring and unstructuring. (PR_13_)
- Support for ``NewType`` chains. (PR_15_)
- ``simple_typechecked_unstructure()`` decorator. (PR_17_)


.. _PR_13: https://github.com/fjarri-eth/compages/pull/13
.. _PR_15: https://github.com/fjarri-eth/compages/pull/15
.. _PR_17: https://github.com/fjarri-eth/compages/pull/17


0.2.1 (2024-03-05)
------------------

Fixed
^^^^^

- The metadata type in the name converter parameter of ``StructureDictIntoDataclass`` and ``UnstructureDataclassToDict`` set to the correct ``MappingProxyType``. (PR_1_)


.. _PR_1: https://github.com/fjarri-eth/compages/pull/1


0.2.0 (2024-03-05)
------------------

Changed
^^^^^^^

- Minimum Python version bumped to 3.10.



0.1.0 (2024-03-04)
------------------

Initial version.
