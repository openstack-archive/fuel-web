#    Copyright 2013 Mirantis, Inc.
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
from dhcp_checker import utils
import re
import traceback
import imp
# net_probe rpm should be refactored tobe importable
net_probe = imp.load_source('net_probe', '/usr/bin/net_probe.py')

class VlansActor(net_probe.Actor):

    def __init__(self, config):
        """
        @ifaces - list or tuple of (iface, vlan) pairs
        """
        interfaces = {}
        for iface, vlans in config.iteritems():
            interfaces[iface] = ', '.join(str(v) for v in vlans)
        self.logger = self._define_logger()
        super(VlansActor, self).__init__({'interfaces': interfaces})


    def _vlans_str_generator(self):
        for iface, vlan in self._iface_vlan_iterator():
            yield '{0}.{1}'.format(iface, vlan)
        for iface in self._iface_iterator():
            yield str(iface)

    def __enter__(self):
        for iface, vlan in self._iface_vlan_iterator():
            self._ensure_iface_up(iface)

            if vlan > 0:
                self._ensure_viface_create_and_up(iface, vlan)
                viface = self._viface_by_iface_vid(iface, vlan)
            else:
                viface = iface
        return self._vlans_str_generator()

    def __exit__(self, type, value, trace):
        for iface in self._iface_iterator():
            self._ensure_iface_down(iface)
