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
    """Set priorities for sequence of tasks using some strategy.
    """

    def __init__(self):
        #: priority sequence generator
        self._priority = Priority()

    def one_by_one(self, tasks):
        """Deploy given tasks one by one."""
        for t in tasks:
            t['priority'] = self._priority.next()

    def in_parallel(self, tasks):
        """Deploy given tasks in parallel mode."""
        self._priority.next()
        for t in tasks:
            t['priority'] = self._priority.current

    def in_parallel_by(self, tasks, amount):
        """Deploy given nodes in parallel by chunks."""
        for index, task in enumerate(tasks):
            if index % amount == 0:
                self._priority.next()
            task['priority'] = self._priority.current
