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


@six.add_metaclass(abc.ABCMeta)
class PriorityHAStrategy(object):
    """A base interface for implementing HA priority strategy."""

    def __init__(self):
        #: priority manager to generate a sequence of priorities
        self._priority = Priority()

    @abc.abstractmethod
    def set_zabbix_server(self, nodes):
        pass

    @abc.abstractmethod
    def set_primary_swift_proxy(self, nodes):
        pass

    @abc.abstractmethod
    def set_swift_proxy(self, nodes):
        pass

    @abc.abstractmethod
    def set_storage(self, nodes):
        pass

    @abc.abstractmethod
    def set_mongo(self, nodes):
        pass

    @abc.abstractmethod
    def set_primary_mongo(self, nodes):
        pass

    @abc.abstractmethod
    def set_primary_controller(self, nodes):
        pass

    @abc.abstractmethod
    def set_controller(self, nodes):
        pass

    @abc.abstractmethod
    def set_others(self, nodes):
        pass


class PriorityHAStrategy50(PriorityHAStrategy):

    def set_zabbix_server(self, nodes):
        self._priority.next()
        for n in nodes:
            n['priority'] = self._priority.current

    def set_primary_swift_proxy(self, nodes):
        self._priority.next()
        for n in nodes:
            n['priority'] = self._priority.current

    def set_swift_proxy(self, nodes):
        self._priority.next()
        for n in nodes:
            n['priority'] = self._priority.current

    def set_storage(self, nodes):
        self._priority.next()
        for n in nodes:
            n['priority'] = self._priority.current

    def set_mongo(self, nodes):
        for n in nodes:
            n['priority'] = self._priority.next()

    def set_primary_mongo(self, nodes):
        for n in nodes:
            n['priority'] = self._priority.next()

    def set_primary_controller(self, nodes):
        for n in nodes:
            n['priority'] = self._priority.next()

    def set_controller(self, nodes):
        for n in nodes:
            n['priority'] = self._priority.next()

    def set_others(self, nodes):
        self._priority.next()
        for n in nodes:
            n['priority'] = self._priority.current


class PriorityHAStrategy51(PriorityHAStrategy):

    def set_zabbix_server(self, nodes):
        self._priority.next()
        for n in nodes:
            n['priority'] = self._priority.current

    def set_primary_swift_proxy(self, nodes):
        self._priority.next()
        for n in nodes:
            n['priority'] = self._priority.current

    def set_swift_proxy(self, nodes):
        self._priority.next()
        for n in nodes:
            n['priority'] = self._priority.current

    def set_storage(self, nodes):
        self._priority.next()
        for n in nodes:
            n['priority'] = self._priority.current

    def set_mongo(self, nodes):
        for n in nodes:
            n['priority'] = self._priority.next()

    def set_primary_mongo(self, nodes):
        for n in nodes:
            n['priority'] = self._priority.next()

    def set_primary_controller(self, nodes):
        for n in nodes:
            n['priority'] = self._priority.next()

    def set_controller(self, nodes):
        # We are deploying in parallel, so do not let us deploy more
        # than 6 controllers simultaneously or galera master may be
        # exhausted.
        max_parallel = 6

        for index, node in enumerate(nodes):
            if index % max_parallel == 0:
                self._priority.next()
            node['priority'] = self._priority.current

    def set_others(self, nodes):
        self._priority.next()
        for n in nodes:
            n['priority'] = self._priority.current


class PriorityHAStrategyPatching(PriorityHAStrategy):
    """No matter what we has to patch nodes one-by-one."""

    def _set_priority_sequentially(self, nodes):
        for n in nodes:
            n['priority'] = self._priority.next()

    def set_zabbix_server(self, nodes):
        self._set_priority_sequentially(nodes)

    def set_primary_swift_proxy(self, nodes):
        self._set_priority_sequentially(nodes)

    def set_swift_proxy(self, nodes):
        self._set_priority_sequentially(nodes)

    def set_storage(self, nodes):
        self._set_priority_sequentially(nodes)

    def set_mongo(self, nodes):
        self._set_priority_sequentially(nodes)

    def set_primary_mongo(self, nodes):
        self._set_priority_sequentially(nodes)

    def set_primary_controller(self, nodes):
        self._set_priority_sequentially(nodes)

    def set_controller(self, nodes):
        self._set_priority_sequentially(nodes)

    def set_others(self, nodes):
        self._set_priority_sequentially(nodes)
