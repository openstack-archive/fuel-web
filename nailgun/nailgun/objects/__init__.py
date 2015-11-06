from stevedore import driver

mgr = driver.DriverManager(
    namespace='nailgun.objects',
    name='core',
)

from core import *
