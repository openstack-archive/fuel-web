Code testing policy
===================

When writing tests, please note the following rules:

1) Each code change *must* be covered with tests

2) The tests *must* be in the same patchset with code changes

3) It's permitted not to write tests in extreme cases. In this case, writing
   tests should be reported as a bug with ``technical-debt`` tag. Extreme cases
   are: hot-fix, bug-fix with ``Critical`` status, patching during
   `FF <https://wiki.openstack.org/wiki/FeatureFreeze>`_ or
   `HCF <https://wiki.openstack.org/wiki/Fuel/Hard_Code_Freeze>`_

4) Before writing tests please consider which type(s) of testing is suitable
   for the unit/module you're covering

5) Nailgun application can be sliced up to tree layers (Presentation, Object,
   Model). Consider usage of unit testing if the testing is performed within
   one of the layers or implementing mock objects is not complicated

6) The tests have to be isolated. The order and count of executions must not
   influence test results

7) Try not to use hardcoded test input values. Test methods should have input
   parameters instead. This gives us additional flexibility in the methods'
   usage

8) Follow DRY principle in tests code. If common code parts are present, please
   extract them to a separate method/class

9) Unit tests are grouped by namespaces as corresponding unit. For instance,
   the unit is located at: ``nailgun/db/deadlock_detector.py``, corresponding
   test would be placed in
   ``nailgun/test/unit/nailgun.db/test_deadlock_detector.py``

10) Integration tests are grouped at the discretion of the developer

