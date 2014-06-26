# Copyright 2014 Mirantis, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import os

from fuel_agent_ci.objects.network import Network
from fuel_agent_ci.objects.vm import Vm
from fuel_agent_ci.objects.tftp import Tftp
from fuel_agent_ci.objects.dhcp import Dhcp

LOG = logging.getLogger(__name__)


class Environment(object):
    def __init__(self, name):
        self.name = name
        self.networks = []
        self.vms = []
        self.tftp = None
        self.dhcp = None
        self.http = None

    @classmethod
    def new(cls, **kwargs):
        LOG.debug('Creating environment: %s' % kwargs['name'])
        env = cls(kwargs['name'])
        for network_kwargs in kwargs.get('networks', []):
            LOG.debug('Creating network: %s' % network_kwargs)
            env.add_network(**network_kwargs)
        for vm_kwargs in kwargs.get('virtual_machines', []):
            LOG.debug('Creating vm: %s' % vm_kwargs)
            env.add_vm(**vm_kwargs)
        if 'dhcp' in kwargs:
            LOG.debug('Creating dhcp server: %s' % kwargs['dhcp'])
            env.set_dhcp(**kwargs['dhcp'])
        if 'tftp' in kwargs:
            LOG.debug('Creating tftp server: %s' % kwargs['tftp'])
            env.set_tftp(**kwargs['tftp'])
        return env

    def add_network(self, **kwargs):
        network = Network(**kwargs)
        self.networks.append(network)
        return network

    def add_vm(self, **kwargs):
        disks = kwargs.pop('disks', [])
        interfaces = kwargs.pop('interfaces', [])
        vm = Vm(**kwargs)
        for disk_kwargs in disks:
            vm.add_disk(**disk_kwargs)
        for interface_kwargs in interfaces:
            vm.add_interface(**interface_kwargs)
        self.vms.append(vm)
        return vm

    def set_tftp(self, **kwargs):
        if not kwargs['tftp_root'].startswith('/'):
            kwargs['tftp_root'] = os.path.abspath(kwargs['tftp_root'])
        self.tftp = Tftp(**kwargs)
        return self.tftp

    def set_dhcp(self, **kwargs):
        hosts = kwargs.pop('hosts', [])
        bootp_kwargs = kwargs.pop('bootp', None)
        self.dhcp = Dhcp(**kwargs)
        for host_kwargs in hosts:
            self.dhcp.add_host(**host_kwargs)
        if bootp_kwargs is not None:
            self.dhcp.set_bootp(**bootp_kwargs)
        return self.dhcp

    def set_http(self, **kwargs):
        raise NotImplementedError

