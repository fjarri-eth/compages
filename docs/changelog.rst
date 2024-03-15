Changelog
=========

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


.. _PR_13: https://github.com/fjarri/compages/pull/13
.. _PR_15: https://github.com/fjarri/compages/pull/15
.. _PR_17: https://github.com/fjarri/compages/pull/17


0.2.1 (2024-03-05)
------------------

Fixed
^^^^^

- The metadata type in the name converter parameter of ``StructureDictIntoDataclass`` and ``UnstructureDataclassToDict`` set to the correct ``MappingProxyType``. (PR_1_)


.. _PR_1: https://github.com/fjarri/compages/pull/1


0.2.0 (2024-03-05)
------------------

Changed
^^^^^^^

- Minimum Python version bumped to 3.10.



0.1.0 (2024-03-04)
------------------

Initial version.
