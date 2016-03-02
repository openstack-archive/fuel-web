# coding: utf-8

# Copyright 2016 Mirantis, Inc.
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

from nailgun.policy import hugepages_distribution as hpd
from nailgun.test import base

# page size constants in KiBs
PAGE_2MiB = 2048
PAGE_1GiB = 1048576


class BaseHPDTestCase(base.BaseTestCase):
    # overload setUp and tearDown from base, because we don't need database
    def setUp(self):
        pass

    def tearDown(self):
        pass

    @classmethod
    def setUpClass(self):
        pass


class TestHPDNumaNode(BaseHPDTestCase):
    def setUp(self):
        self.nnode_memory = 128 * 1048576  # 128 GiB in KiBs
        self.nnode = hpd.NumaNode(0, self.nnode_memory)

    def test_report(self):
        self.nnode.pages[PAGE_2MiB] = 4
        expected = [{'count': 4, 'numa_id': self.nnode.id, 'size': '2048'}]
        self.assertEqual(self.nnode.report(), expected)

        self.nnode.pages[PAGE_1GiB] = 5
        expected.append({'count': 5, 'numa_id': self.nnode.id,
                         'size': '1048576'})
        self.assertEqual(self.nnode.report(), expected)

    def test_allocation_enough_memory(self):
        comp = hpd.Component({'2048': 3, '1048576': 2})
        allocated = self.nnode.allocate(comp)
        self.assertTrue(allocated)
        self.assertEqual(self.nnode.free_memory,
                         self.nnode_memory - (PAGE_2MiB * 3) - (PAGE_1GiB * 2))
        self.assertEqual(self.nnode.pages, {PAGE_2MiB: 3, PAGE_1GiB: 2})
        self.assertTrue(comp.is_done())

    def test_allocation_not_enough_memory(self):
        comp = hpd.Component({'2048': 513, '1048576': 127})
        allocated = self.nnode.allocate(comp)
        self.assertTrue(allocated)

        # Checks that we allocate 127 1GiB pages and 512 2MiB pages.
        # And component steel need 1 2MiB page
        self.assertEqual(self.nnode.free_memory, 0)
        self.assertEqual(self.nnode.pages, {PAGE_2MiB: 512, PAGE_1GiB: 127})
        self.assertFalse(comp.is_done())
        self.assertEqual(comp._pages, {PAGE_2MiB: 1})

    def test_failed_allocation_on_full_node(self):
        nnode = hpd.NumaNode(0, 1024)  # node with 1 MiB memory
        comp = hpd.Component({'2048': 1})
        allocated = nnode.allocate(comp)

        self.assertFalse(allocated)
        self.assertEqual(comp._pages, {PAGE_2MiB: 1})
        self.assertEqual(nnode.pages, {})

    def test_empty_component_allocation(self):
        comp = hpd.Component({'2048': 0})
        self.assertTrue(comp.is_done())

        allocated = self.nnode.allocate(comp)
        self.assertTrue(allocated)
        self.assertEqual(self.nnode.pages, {})


class TestHPDComponent(BaseHPDTestCase):
    def test_initialization(self):
        comp = hpd.Component({'2048': 1, '1048576': 3})
        self.assertEqual(comp._pages, {PAGE_2MiB: 1, PAGE_1GiB: 3})

        # check ordering
        self.assertEqual(list(comp._pages.keys()), [PAGE_1GiB, PAGE_2MiB])

    def test_allocation(self):
        comp = hpd.Component({'2048': 1, '1048576': 3})
        allocated = comp.allocate(PAGE_2MiB, 2)
        self.assertEqual(allocated, 1)
        self.assertEqual(list(comp._pages.values()), [3])

        allocated = comp.allocate(PAGE_1GiB, 1)
        self.assertEqual(allocated, 1)
        self.assertEqual(list(comp._pages.values()), [2])

        allocated = comp.allocate(PAGE_2MiB, 1)
        self.assertEqual(allocated, 0)
        self.assertEqual(list(comp._pages.values()), [2])

    def test_is_done(self):
        comp = hpd.Component({'2048': 1, '1048576': 0})
        self.assertFalse(comp.is_done())

        comp.allocate(PAGE_2MiB, 1)
        self.assertTrue(comp.is_done())

    def test_empty(self):
        comp = hpd.Component({'2048': 0})
        self.assertEqual(comp._pages, {})

    def test_pages(self):
        comp = hpd.Component({'2048': 1, '1048576': 3})
        self.assertEqual(list(comp.pages()), [(PAGE_1GiB, 3), (PAGE_2MiB, 1)])


class TestHugePagesAllocations(BaseHPDTestCase):
    def setUp(self):
        # two nodes: first with 2GiB ram, second with 1GiB (in KiBs)
        self.numa_nodes = [hpd.NumaNode(0, 2 * 1048576),
                           hpd.NumaNode(1, 1048576)]

    def _check(self, *data):
        self.assertEqual(
            [(n.free_memory, dict(n.pages)) for n in self.numa_nodes],
            list(data))

    def test_all_allocation(self):
        all_comps = [hpd.Component({'2048': 512})]
        self.assertNotRaises(ValueError,
                             hpd._allocate_all,
                             self.numa_nodes, all_comps)

        self._check((PAGE_1GiB, {PAGE_2MiB: 512}), (0, {PAGE_2MiB: 512}))

    def test_all_allocation_raises(self):
        all_comps = [hpd.Component({'1048576': 100500})]
        self.assertRaisesWithMessageIn(
            ValueError,
            'could not require more memory than node has',
            hpd._allocate_all,
            self.numa_nodes,
            all_comps)

    def test_any_allocation_simple(self):
        any_comps = [hpd.Component({'1048576': 1})]
        self.assertNotRaises(ValueError,
                             hpd._allocate_any,
                             self.numa_nodes, any_comps)

        self._check((PAGE_1GiB, {PAGE_1GiB: 1}), (PAGE_1GiB, {}))

    def test_any_allocation_complex(self):
        any_comps = [hpd.Component({'1048576': 3})]
        self.assertNotRaises(ValueError,
                             hpd._allocate_any,
                             self.numa_nodes, any_comps)

        self._check((0, {PAGE_1GiB: 2}), (0, {PAGE_1GiB: 1}))

    def test_any_allocation_multy_component(self):
        any_comps = [hpd.Component({'2048': 512}),
                     hpd.Component({'1048576': 2})]

        self.assertNotRaises(ValueError,
                             hpd._allocate_any,
                             self.numa_nodes, any_comps)

        self._check((0, {PAGE_1GiB: 2}), (0, {PAGE_2MiB: 512}))

    def test_any_allocation_multy_page(self):
        any_comps = [hpd.Component({'1048576': 1, '2048': 1024})]

        self.assertNotRaises(ValueError,
                             hpd._allocate_any,
                             self.numa_nodes, any_comps)

        self._check((0, {PAGE_1GiB: 1, PAGE_2MiB: 512}), (0, {PAGE_2MiB: 512}))

    def test_full_allocations(self):
        all_comps = [hpd.Component({'2048': 256})]
        any_comps = [hpd.Component({'1048576': 1, '2048': 512})]

        hpd._allocate_all(self.numa_nodes, all_comps)
        hpd._allocate_any(self.numa_nodes, any_comps)

        self._check((0, {PAGE_2MiB: 512, PAGE_1GiB: 1}), (0, {PAGE_2MiB: 512}))

    def test_full_allocations2(self):
        self.numa_nodes = list(reversed(self.numa_nodes))

        all_comps = [hpd.Component({'2048': 256})]
        any_comps = [hpd.Component({'1048576': 1, '2048': 512})]

        hpd._allocate_all(self.numa_nodes, all_comps)
        hpd._allocate_any(self.numa_nodes, any_comps)

        self._check((0, {PAGE_2MiB: 512}), (0, {PAGE_2MiB: 512, PAGE_1GiB: 1}))

    def test_distribution(self):
        topology = {'numa_nodes': [{'id': 0, 'memory': PAGE_1GiB * 1024},
                                   {'id': 1, 'memory': 2 * PAGE_1GiB * 1024}]}
        components = {
            'any': [{
                '2048': 512,
                '1048576': 1,
            }],
            'all': [{
                '2048': 256,
            }],
        }

        expected = [
            {'numa_id': 0, 'size': '2048', 'count': 512},
            {'numa_id': 1, 'size': '2048', 'count': 512},
            {'numa_id': 1, 'size': '1048576', 'count': 1},
        ]

        self.assertEqual(
            hpd.distribute_hugepages(topology, components), expected)
