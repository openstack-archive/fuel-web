Code testing policy
===================

When writing tests, please note the following rules:

#. Each code change MUST be covered with tests. The test for specific code
   change must fail if that change to code is reverted, i.e. the test must
   really cover the code change and not the general case. Bug fixes should
   have tests for failing case.

#. The tests MUST be in the same patchset with the code changes.

#. It's permitted not to write tests in extreme cases. The extreme cases are:

   * hot-fix / bug-fix with *Critical* status.
   * patching during Feature Freeze (FF_) or Hard Code Freeze (HCF_).

   In this case, request for writing tests should be reported as a bug with
   *technical-debt* tag. It has to be related to the bug which was fixed with
   a patchset that didn't have the tests included.

   .. _FF: https://wiki.openstack.org/wiki/FeatureFreeze
   .. _HCF: https://wiki.openstack.org/wiki/Fuel/Hard_Code_Freeze

#. Before writing tests please consider which type(s) of testing is suitable
   for the unit/module you're covering.

#. Test coverage should not be decreased.

#. Nailgun application can be sliced up to tree layers (Presentation, Object,
   Model). Consider usage of the unit testing if it is performed within one of
   the layers or implementing mock objects is not complicated.

#. The tests have to be isolated. The order and count of executions must not
   influence test results.

#. Tests must be repetitive and must always pass regardless of how many times
   they are run.

#. Parametrize tests to avoid testing many times the same behaviour but with
   different data. This gives an additional flexibility in the methods' usage.

#. Follow DRY principle in tests code. If common code parts are present, please
   extract them to a separate method/class.

#. Unit tests are grouped by namespaces as corresponding unit. For instance,
   the unit is located at: ``nailgun/db/dl_detector.py``, corresponding test
   would be placed in ``nailgun/test/unit/nailgun.db/test_dl_detector.py``

#. Integration tests are grouped at the discretion of the developer.

#. Consider implementing performance tests for the cases:

   * new handler is added which depends on number of resources in the database.
   * new logic is added which parses/operates on elements like nodes.

