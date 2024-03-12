Changelog
=========

0.2.1 (2024-03-05)
------------------

Added
^^^^^

- Skip fields equal to the defaults when unstructuring dataclasses. (PR_13_)


Fixed
^^^^^

- The metadata type in the name converter parameter of ``StructureDictIntoDataclass`` and ``UnstructureDataclassToDict`` set to the correct ``MappingProxyType``. (PR_1_)


.. _PR_1: https://github.com/fjarri/compages/pull/1
.. _PR_13: https://github.com/fjarri/compages/pull/13


0.2.0 (2024-03-05)
------------------

Changed
^^^^^^^

- Minimum Python version bumped to 3.10.



0.1.0 (2024-03-04)
------------------

Initial version.
