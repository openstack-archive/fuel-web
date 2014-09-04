# -*- coding: utf-8 -*-

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

import abc
import six


class Priority(object):
    """Returns a priority sequence from hightest to lowest.

    Node with priority 0 will be deployed first. We have a big step
    because we want to allow user redefine deployment order and
    he can use free space between prioriries.

    :param step: an increment step
    """

    #: default priority step
    default_step = 100

    def __init__(self, step=default_step):
        self._step = step
        self._priority = 0

    def next(self):
        self._priority += self._step
        return self._priority

    @property
    def current(self):
        return self._priority


class PriorityStrategy(object):
    """Set priorities for sequence of nodes using some strategy.
    """

    def __init__(self):
        #: priority sequence generator
        self._priority = Priority()

    def one_by_one(self, nodes):
        """Deploy given nodes one by one."""
        for n in nodes:
            n['priority'] = self._priority.next()

    def in_parallel(self, nodes):
        """Deploy given nodes in parallel mode."""
        self._priority.next()
        for n in nodes:
            n['priority'] = self._priority.current

    def in_parallel_by(self, nodes, amount):
        """Deploy given nodes in parallel by chunks."""
        for index, node in enumerate(nodes):
            if index % amount == 0:
                self._priority.next()
            node['priority'] = self._priority.current


@six.add_metaclass(abc.ABCMeta)
class PrioritySerializer(object):
    """A base interface for implementing priority serializer."""

    def __init__(self):
        self.priority = PriorityStrategy()

    def by_role(self, nodes, role):
        return filter(lambda node: node['role'] == role, nodes)

    def not_roles(self, nodes, roles):
        return filter(lambda node: node['role'] not in roles, nodes)

    @abc.abstractmethod
    def set_deployment_priorities(self, nodes):
        """Set deployment priorities for a given nodes.

        :param nodes: a list of nodes to be prioritized
        """


class PriorityMultinodeSerializer50(PrioritySerializer):

    def set_deployment_priorities(self, nodes):

        self.priority.one_by_one(self.by_role(nodes, 'zabbix-server'))
        self.priority.one_by_one(self.by_role(nodes, 'mongo'))
        self.priority.one_by_one(self.by_role(nodes, 'primary-mongo'))
        self.priority.one_by_one(self.by_role(nodes, 'controller'))

        self.priority.in_parallel(
            self.not_roles(nodes, [
                'controller',
                'mongo',
                'primary-mongo',
                'zabbix-server']))


# Yep, for MultiNode we have no changes between 5.0 and 5.1
PriorityMultinodeSerializer51 = PriorityMultinodeSerializer50


class PriorityHASerializer50(PrioritySerializer):

    def set_deployment_priorities(self, nodes):

        self.priority.in_parallel(self.by_role(nodes, 'zabbix-server'))
        self.priority.in_parallel(self.by_role(nodes, 'primary-swift-proxy'))
        self.priority.in_parallel(self.by_role(nodes, 'swift-proxy'))
        self.priority.in_parallel(self.by_role(nodes, 'storage'))

        self.priority.one_by_one(self.by_role(nodes, 'mongo'))
        self.priority.one_by_one(self.by_role(nodes, 'primary-mongo'))
        self.priority.one_by_one(self.by_role(nodes, 'primary-controller'))

        # We are deploying in parallel, so do not let us deploy more than
        # 6 controllers simultaneously or galera master may be exhausted
        self.priority.one_by_one(self.by_role(nodes, 'controller'))

        self.priority.in_parallel(
            self.not_roles(nodes, [
                'primary-swift-proxy',
                'swift-proxy',
                'storage',
                'primary-controller',
                'controller',
                'quantum',
                'mongo',
                'primary-mongo',
                'zabbix-server']))


class PriorityHASerializer51(PrioritySerializer):

    def set_deployment_priorities(self, nodes):

        self.priority.in_parallel(self.by_role(nodes, 'zabbix-server'))
        self.priority.in_parallel(self.by_role(nodes, 'primary-swift-proxy'))
        self.priority.in_parallel(self.by_role(nodes, 'swift-proxy'))
        self.priority.in_parallel(self.by_role(nodes, 'storage'))

        self.priority.one_by_one(self.by_role(nodes, 'mongo'))
        self.priority.one_by_one(self.by_role(nodes, 'primary-mongo'))
        self.priority.one_by_one(self.by_role(nodes, 'primary-controller'))

        # We are deploying in parallel, so do not let us deploy more than
        # 6 controllers simultaneously or galera master may be exhausted
        self.priority.in_parallel_by(self.by_role(nodes, 'controller'), 6)

        self.priority.in_parallel(
            self.not_roles(nodes, [
                'primary-swift-proxy',
                'swift-proxy',
                'storage',
                'primary-controller',
                'controller',
                'quantum',
                'mongo',
                'primary-mongo',
                'zabbix-server']))
