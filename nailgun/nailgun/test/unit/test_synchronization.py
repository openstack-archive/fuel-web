# -*- coding: utf-8 -*-

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
import multiprocessing as mp
import Queue

from nailgun import consts
from nailgun.test import base
from nailgun.utils import synchronization


BARRIER_PASSED_MSG = 'passed'


class TestBarrier(base.BaseUnitTest):
    GROUP_NAME = 'nailgun-barrier-test'
    TIMEOUT = 2

    queue = mp.Queue()

    def test_single_barrier(self):
        p = self._spawn_barriering_process(self.GROUP_NAME, 1)

        p.start()

        self.assertEqual(self.queue.get(True, self.TIMEOUT),
                         BARRIER_PASSED_MSG)

    def test_multi_barrier(self):
        n = 5
        processes = [self._spawn_barriering_process(self.GROUP_NAME, n) for _
                     in range(0, n)]

        for i in range(0, n - 1):
            processes[i].start()
            self.assertRaises(Queue.Empty, self.queue.get, True,
                              self.TIMEOUT)

        processes[n - 1].start()

        for _ in range(0, n):
            self.assertEqual(self.queue.get(True, self.TIMEOUT),
                             BARRIER_PASSED_MSG)

    def _spawn_barriering_process(self, group, limit):
        def wait_on_barrier(group, limit, q):
            b = synchronization.Barrier(group, limit)
            b.wait()
            q.put(BARRIER_PASSED_MSG)

        p = mp.Process(target=wait_on_barrier, args=(group, limit, self.queue))
        return p

    def test_barrier_by_const(self):
        n = 5

        barrier_const = consts.Enum(
            self.GROUP_NAME,
            n,
            names=(
                'group',
                'limit'
            )
        )

        processes = [self._spawn_barriering_process_by_const(barrier_const)
                     for _ in range(0, n)]

        for i in range(0, n - 1):
            processes[i].start()
            self.assertRaises(Queue.Empty, self.queue.get, True,
                              self.TIMEOUT)

        processes[n - 1].start()

        for _ in range(0, n):
            self.assertEqual(self.queue.get(True, self.TIMEOUT),
                             BARRIER_PASSED_MSG)

    def _spawn_barriering_process_by_const(self, const):
        def wait_on_barrier(const, q):
            synchronization.barrier_by_const(const)
            q.put(BARRIER_PASSED_MSG)

        p = mp.Process(target=wait_on_barrier, args=(const, self.queue))
        return p
