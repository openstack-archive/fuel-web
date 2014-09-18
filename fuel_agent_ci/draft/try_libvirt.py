import sys
import os

sys.path[:0] = [os.path.join(os.path.dirname(__file__), '..')]

from fuel_agent_ci.drivers import libvirt_driver

drv = libvirt_driver.LibvirtDriver()
print drv.pool_list()

if 'fuel_agent_ci' not in drv.pool_list():
    print 'not defined'
    drv.pool_define('fuel_agent_ci', os.path.join('/var/tmp/fuel_agent_ci', 'volumepool'))
if 'fuel_agent_ci' not in drv.pool_list_active():
    print 'not active'
    drv.pool_start(drv.pool_uuid_by_name('fuel_agent_ci'))
