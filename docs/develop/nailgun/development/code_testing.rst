Code testing policy
===================

Please follow the rules when writing tests:

1) Each code change *must* be followed with unit tests
2) Attach the tests to same patch
3) Patch won't be merged with upstream until the tests are present
4) It's permitted not to write tests in extreme cases. In this case, writing tests has to be filed as a bug with ``technical-debt`` tag
5) Before writing tests please consider which type(s) of testing is suitable for the unit/module you're covering
6) Nailgun application can be sliced up to tree layers (Presentation, Object, Model). Consider usage of unit testing if the testing is performed within one of the layers or implementing mock objects is not complicated
7) The tests have to be isolated. The order and count of executions don't have to make an influence on the tests results
8) Don't use hardcoded test input values
9) DRY in tests code. If you have common code parts, please extract them to a separate method/class
