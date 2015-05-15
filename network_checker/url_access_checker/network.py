#    Copyright 2015 Mirantis, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from contextlib import contextmanager
from logging import getLogger

import netifaces

from url_access_checker.utils import execute


logger = getLogger(__name__)


def get_default_gateway():
    """Return ipaddress, interface pair for default gateway
    """
    gws = netifaces.gateways()
    if 'default' in gws:
        return gws['default'][netifaces.AF_INET]
    return None, None


def check_ifaddress_present(iface, addr):
    """Check if required ipaddress already assigned to the iface
    """
    for ifaddress in netifaces.ifaddresses(iface)[netifaces.AF_INET]:
        if ifaddress['addr'] in addr:
            return True
    return False


def check_exist(iface):
    rc, stdout, stderr = execute(['ip', 'link', 'show', iface],
                                 check_errors=False)
    if rc == 1 and 'does not exist' in stderr:
        return False
    return True


def check_up(iface):
    rc, stdout, _ = execute(['ip', 'link', 'show', iface])
    return 'UP' in stdout


def log_network_info(stage):
    logger.info('Logging networking info at %s', stage)
    stdout = execute(['ip', 'a'])[1]
    logger.info('ip a: %s', stdout)
    stdout = execute(['ip', 'ro'])[1]
    logger.info('ip ro: %s', stdout)


class Eth(object):

    def __init__(self, iface):
        self.iface = iface
        self.is_up = None

    def setup(self):
        self.is_up = check_up(self.iface)
        if self.is_up is False:
            execute(['ip', 'link', 'set', 'dev', self.iface, 'up'])

    def teardown(self):
        if self.is_up is False:
            execute(['ip', 'link', 'set', 'dev', self.iface, 'down'])


class Vlan(Eth):

    def __init__(self, iface, vlan):
        self.parent = iface
        self.vlan = vlan
        self.iface = '{0}.{1}'.format(iface, vlan)
        self.is_present = None
        self.is_up = None

    def setup(self):
        self.is_present = check_exist(self.iface)
        if self.is_present is False:
            execute(['ip', 'link', 'add',
                    'link', self.parent, 'name',
                    self.iface, 'type', 'vlan', 'id', self.vlan])
        super(Vlan, self).setup()

    def teardown(self):
        if self.is_present is False:
            execute(['ip', 'link', 'delete', self.iface])
        super(Vlan, self).teardown()


class IP(object):

    def __init__(self, iface, addr):
        self.iface = iface
        self.addr = addr
        self.is_present = None

    def setup(self):
        self.is_present = check_ifaddress_present(self.iface, self.addr)
        if self.is_present is False:
            execute(['ip', 'a', 'add', self.addr, 'dev', self.iface])

    def teardown(self):
        if self.is_present is False:
            execute(['ip', 'a', 'del', self.addr, 'dev', self.iface])


class Route(object):

    def __init__(self, iface, gateway):
        self.iface = iface
        self.gateway = gateway
        self.default_gateway = None
        self.df_iface = None

    def setup(self):
        self.default_gateway, self.df_iface = get_default_gateway()

        if (self.default_gateway, self.df_iface) == (None, None):
            execute(['ip', 'ro', 'add',
                    'default', 'via', self.gateway, 'dev', self.iface])
        elif ((self.default_gateway, self.df_iface)
              != (self.gateway, self.iface)):
            execute(['ip', 'ro', 'change',
                    'default', 'via', self.gateway, 'dev', self.iface])

    def teardown(self):
        if (self.default_gateway, self.df_iface) == (None, None):
            execute(['ip', 'ro', 'del',
                    'default', 'via', self.gateway, 'dev', self.iface])
        elif ((self.default_gateway, self.df_iface)
              != (self.gateway, self.iface)):
            execute(['ip', 'ro', 'change',
                    'default', 'via', self.defaul_gateway,
                    'dev', self.df_iface])


@contextmanager
def manage_network(iface, addr, gateway, vlan=None):

    log_network_info('before setup')

    actions = [Eth(iface)]
    if vlan:
        vlan_action = Vlan(iface, vlan)
        actions.append(vlan_action)
        iface = vlan_action.iface
    actions.append(IP(iface, addr))
    actions.append(Route(iface, gateway))
    executed = []
    try:
        for a in actions:
            a.setup()
            executed.append(a)

        log_network_info('after setup')

        yield

    finally:
        for a in reversed(executed):
            a.teardown()

        log_network_info('after teardown')
