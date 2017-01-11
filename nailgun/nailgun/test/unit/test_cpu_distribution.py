#    Copyright 2016 Mirantis, Inc.
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

import copy

from nailgun.policy import cpu_distribution
from nailgun.test import base


class TestDistributeNodeCPUs(base.BaseTestCase):

    def _create_numa_nodes(self, numa_count, cpus_per_numa):
        numa_nodes = []
        for numa_id in range(numa_count):
            begin = numa_id * cpus_per_numa
            numa_nodes.append({
                'id': numa_id,
                'cpus': list(range(begin, begin + cpus_per_numa)),
            })
        return numa_nodes

    def _create_nova_dpdk(self, nova_req, dpdk_req):
        return {
            'nova': {
                'name': 'nova',
                'required_cpus': nova_req,
            },
            'dpdk': {
                'name': 'dpdk',
                'required_cpus': dpdk_req,
            }
        }

    def test_many_cpus_required(self):
        numa_nodes = self._create_numa_nodes(2, 4)
        components = self._create_nova_dpdk(4, 3)
        nics_numas = [1]

        expected_data = {
            'components': {
                'nova': [0, 1, 2, 3],
                'ovs_core_mask': [4],
                'ovs_pmd_core_mask': [5, 6],
            },
            'isolated_cpus': [0, 1, 2, 3, 4, 5, 6],
        }

        saved_numa_nodes = copy.deepcopy(numa_nodes)
        self.assertEqual(
            expected_data,
            cpu_distribution.distribute_node_cpus(
                numa_nodes, components, nics_numas))
        self.assertEqual(saved_numa_nodes, numa_nodes)

    def test_one_component(self):
        numa_nodes = self._create_numa_nodes(2, 3)
        components = self._create_nova_dpdk(5, 0)
        nics_numas = []

        expected_data = {
            'components': {
                'nova': [0, 1, 2, 3, 4],
            },
            'isolated_cpus': [0, 1, 2, 3, 4],
        }

        self.assertEqual(
            expected_data,
            cpu_distribution.distribute_node_cpus(
                numa_nodes, components, nics_numas))

    def test_few_cpus_required(self):
        numa_nodes = self._create_numa_nodes(2, 3)
        components = self._create_nova_dpdk(1, 2)
        nics_numas = [0]

        expected_data = {
            'components': {
                'ovs_core_mask': [0],
                'ovs_pmd_core_mask': [1],
                'nova': [3]
            },
            'isolated_cpus': [0, 1, 3]
        }
        self.assertEqual(
            expected_data,
            cpu_distribution.distribute_node_cpus(
                numa_nodes, components, nics_numas))

    def test_no_cpus_required(self):
        numa_nodes = self._create_numa_nodes(2, 4)
        components = self._create_nova_dpdk(0, 0)
        nics_numas = []

        expected_data = {
            'components': {
            },
            'isolated_cpus': []
        }

        self.assertEqual(
            expected_data,
            cpu_distribution.distribute_node_cpus(
                numa_nodes, components, nics_numas))

    def test_dpdk_bond(self):
        numa_nodes = self._create_numa_nodes(4, 8)
        components = self._create_nova_dpdk(15, 12)
        nics_numas = [0, 1]

        expected_data = {
            'components': {
                'ovs_core_mask': [0],
                'ovs_pmd_core_mask': (list(range(1, 5))
                                      + list(range(8, 12))
                                      + [16, 24, 12]),
                'nova': (list(range(17, 24))
                         + list(range(25, 32))
                         + [13]),
            },
            'isolated_cpus': (list(range(0, 5))
                              + list(range(8, 14))
                              + list(range(16, 32))),
        }

        actual = cpu_distribution.distribute_node_cpus(
            numa_nodes, components, nics_numas)

        for name in expected_data['components']:
            self.assertItemsEqual(expected_data['components'][name],
                                  actual['components'][name])

        self.assertItemsEqual(
            expected_data['isolated_cpus'],
            actual['isolated_cpus'])

    def test_custom_components(self):
        numa_nodes = self._create_numa_nodes(2, 4)
        components = {
            'comp1': {
                'name': 'comp1',
                'required_cpus': 3,
            },
            'comp2': {
                'name': 'comp2',
                'required_cpus': 2,
            }
        }
        nics_numas = []

        expected_data = {
            'components': {
                'comp1': [0, 1, 2],
                'comp2': [4, 5],
            },
            'isolated_cpus': [0, 1, 2, 4, 5],
        }

        self.assertEqual(
            expected_data,
            cpu_distribution.distribute_node_cpus(
                numa_nodes, components, nics_numas))
