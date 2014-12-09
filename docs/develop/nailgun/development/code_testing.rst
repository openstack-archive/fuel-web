Code testing policy
===================

When writing tests, please note the following rules:

1) Each code change *must* be covered with tests. The test for specific code
   change must fail if that change to code is reverted, i.e. the test must
   really cover the code change and not some general case. Bug fixes should
   have tests for failing case

2) The tests *must* be in the same patchset with code changes

3) It's permitted not to write tests in extreme cases. The extreme cases are:
   hot-fix, bug-fix with ``Critical`` status, patching during
   `FF <https://wiki.openstack.org/wiki/FeatureFreeze>`_ or
   `HCF <https://wiki.openstack.org/wiki/Fuel/Hard_Code_Freeze>`_. In this
   case, request for writing tests should be reported as a bug with
   ``technical-debt`` tag. It has to be related to the bug which was fixed with
   a patchset that didn't have the tests included

4) Before writing tests please consider which type(s) of testing is suitable
   for the unit/module you're covering

5) Test coverage should not be decreased

5) Nailgun application can be sliced up to tree layers (Presentation, Object,
   Model). Consider usage of unit testing if the testing is performed within
   one of the layers or implementing mock objects is not complicated

6) The tests have to be isolated. The order and count of executions must not
   influence test results

7) Tests must be repetitive and must always pass regardless of how many times
   they are run

8) Parametrize tests to avoid testing many times the same behaviour but with
   different data. This gives an additional flexibility in the methods' usage

9) Follow DRY principle in tests code. If common code parts are present, please
   extract them to a separate method/class

10) Unit tests are grouped by namespaces as corresponding unit. For instance,
    the unit is located at: ``nailgun/db/dl_detector.py``, corresponding test
    would be placed in ``nailgun/test/unit/nailgun.db/test_dl_detector.py``

11) Integration tests are grouped at the discretion of the developer

12) Consider implementing performance tests for the cases:
    - new handler is added which depends on number of resources in the database
    - new logic is added which parses/operates on elements like nodes

