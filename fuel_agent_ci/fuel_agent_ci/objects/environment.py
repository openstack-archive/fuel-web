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

import functools
import logging
import os
import tempfile

from fuel_agent_ci import drivers
from fuel_agent_ci.objects.dhcp import Dhcp
from fuel_agent_ci.objects import OBJECT_TYPES
from fuel_agent_ci.objects.vm import Vm

LOG = logging.getLogger(__name__)


class Environment(object):
    def __init__(self, name, envdir, driver=None):
        self.name = name
        self.envdir = envdir
        self.driver = driver or drivers.Driver()
        self.items = []

    @classmethod
    def new(cls, **kwargs):
        LOG.debug('Creating environment: %s' % kwargs['name'])
        envdir = kwargs.get('envdir') or os.path.join(
            tempfile.gettempdir(), kwargs['name'])
        if not os.path.exists(envdir):
            LOG.debug('Envdir %s does not exist. Creating envdir.' % envdir)
            os.makedirs(envdir)
        env = cls(kwargs['name'], envdir)
        for item_type in OBJECT_TYPES.keys():
            for item_kwargs in kwargs.get(item_type, []):
                LOG.debug('Creating %s: %s' % (item_type, item_kwargs))
                getattr(env, '%s_add' % item_type)(**item_kwargs)
        return env

    def __getattr__(self, attr_name):
        """This method maps item_add, item_by_name, item_action attributes into
        attributes for particular types like artifact_add or dhcp_by_name.

        :param attr_name: Attribute name to map (e.g. net_add, repo_clone)

        :returns: Lambda which implements a particular attribute.
        """
        try:
            item_type, item_action = attr_name.split('_', 1)
        except Exception:
            raise AttributeError('Attribute %s not found' % attr_name)
        else:
            if item_action == 'add':
                return functools.partial(self.item_add, item_type)
            elif item_action == 'by_name':
                return functools.partial(self.item_by_name, item_type)
            else:
                return functools.partial(self.item_action,
                                         item_type, item_action)

    def item_add(self, item_type, **kwargs):
        if self.item_by_name(item_type, kwargs.get('name')):
            raise Exception('Error while adding item: %s %s already exist' %
                            (item_type, kwargs.get('name')))
        item = OBJECT_TYPES[item_type](env=self, **kwargs)
        self.items.append(item)
        return item

    def vm_add(self, **kwargs):
        if self.item_by_name('vm', kwargs.get('name')):
            raise Exception('Error while adding vm: vm %s already exist' %
                            kwargs.get('name'))
        disks = kwargs.pop('disks', [])
        interfaces = kwargs.pop('interfaces', [])
        vm = Vm(env=self, **kwargs)
        for disk_kwargs in disks:
            vm.add_disk(**disk_kwargs)
        for interface_kwargs in interfaces:
            vm.add_interface(**interface_kwargs)
        self.items.append(vm)
        return vm

    def dhcp_add(self, **kwargs):
        if self.item_by_name('dhcp', kwargs.get('name')):
            raise Exception('Error while adding dhcp: dhcp %s already exist' %
                            kwargs.get('name'))
        hosts = kwargs.pop('hosts', [])
        bootp_kwargs = kwargs.pop('bootp', None)
        dhcp = Dhcp(env=self, **kwargs)
        for host_kwargs in hosts:
            dhcp.add_host(**host_kwargs)
        if bootp_kwargs is not None:
            dhcp.set_bootp(**bootp_kwargs)
        self.items.append(dhcp)
        return dhcp

    def item_by_name(self, item_type, item_name):
        found = filter(
            lambda x: x.typename == item_type and x.name == item_name,
            self.items
        )
        if not found or len(found) > 1:
            LOG.debug('Item %s %s not found' % (item_type, item_name))
            return None
        return found[0]

    def item_action(self, item_type, item_action, item_name=None, **kwargs):
        if item_name:
            item = self.item_by_name(item_type, item_name)
            return {item_name: getattr(item, item_action)(**kwargs)}
        else:
            result = {}
            for item in [i for i in self.items if i.typename == item_type]:
                LOG.debug('Trying to do action on item: '
                          'type=%s name=%s action=%s' %
                          (item_type, item.name, item_action))
                result[item.name] = getattr(item, item_action)(**kwargs)
            return result

    # TODO(kozhukalov): implement this method as classmethod in tftp object
    def tftp_by_network(self, network):
        found = filter(
            lambda x: x.typename == 'tftp' and x.network == network,
            self.items
        )
        if not found or len(found) > 1:
            LOG.debug('Tftp not found')
            return None
        return found[0]

    # TODO(kozhukalov): implement this method as classmethod in dhcp object
    def dhcp_by_network(self, network):
        found = filter(
            lambda x: x.typename == 'dhcp' and x.network == network,
            self.items
        )
        if not found or len(found) > 1:
            LOG.debug('Dhcp not found')
            return None
        return found[0]

    def start(self):
        LOG.debug('Starting environment')
        self.artifact_get()
        self.repo_clone()
        self.net_start()
        self.tftp_start()
        self.dhcp_start()
        self.http_start()
        self.vm_start()

    def stop(self, artifact_clean=False, repo_clean=False):
        LOG.debug('Stopping environment')
        self.vm_stop()
        self.tftp_stop()
        self.dhcp_stop()
        self.http_stop()
        self.net_stop()
        if artifact_clean:
            self.artifact_clean()
        if repo_clean:
            self.repo_clean()

    def status(self):
        return all((item.status() for item in self.items))
