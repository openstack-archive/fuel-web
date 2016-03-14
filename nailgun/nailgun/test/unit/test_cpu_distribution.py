# -*- coding: utf-8 -*-

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

import six

from nailgun.policy import cpu_distribution
from nailgun.test import base


class TestCpuDistributor(base.BaseTestCase):

    def test_cpu_distributor(self):
        component = {'name': 'test_name',
                     'required_cpus': 5}
        distributor = cpu_distribution.CpuDistributor(component)
        self.assertEquals(component['name'], distributor.name)
        self.assertEquals(component['required_cpus'], distributor.required)
        self.assertEquals(0, len(distributor.cpus))

    def test_consume(self):
        component = {'name': 'test_name',
                     'required_cpus': 2}
        distributor = cpu_distribution.CpuDistributor(component)
        cpus = [0, 1, 2, 3]
        self.assertFalse(distributor.consume(cpus))
        self.assertEquals([0, 1], distributor.cpus)
        self.assertEquals([2, 3], cpus)
        self.assertEquals(0, distributor.required)

    def test_consume_limit(self):
        component = {'name': 'test_name',
                     'required_cpus': 4}
        distributor = cpu_distribution.CpuDistributor(component)
        cpus = [0, 1, 2, 3]
        self.assertTrue(distributor.consume(cpus, 1))
        self.assertEqual([0], distributor.cpus)
        self.assertEqual([1, 2, 3], cpus)
        self.assertEqual(3, distributor.required)

    def test_consume_few_cpus(self):
        component = {'name': 'test_name',
                     'required_cpus': 5}
        distributor = cpu_distribution.CpuDistributor(component)
        cpus = [0, 1]
        self.assertTrue(distributor.consume(cpus))
        self.assertEqual([0, 1], distributor.cpus)
        self.assertEqual([], cpus)
        self.assertEqual(3, distributor.required)


class TestGroupCpuDistributor(base.BaseTestCase):

    def _create_group_distributor(self, *required_cpus):
        components = []
        for idx, required in enumerate(required_cpus):
            components.append({'name': 'comp{0}'.format(idx),
                               'required_cpus': required})
        return cpu_distribution.GroupCpuDistributor(components)

    def test_group_cpu_distributor(self):
        required_cpus = [1, 2, 3, 4]
        distributor = self._create_group_distributor(*required_cpus)
        self.assertEquals(10, distributor.total_required)
        self.assertEquals(4, len(distributor.components))
        for required, component in six.moves.zip(
                required_cpus, distributor.components):
            self.assertEquals(required, component.required)

    def test_consume(self):
        required_cpus = [1, 2, 2]
        distributor = self._create_group_distributor(*required_cpus)
        cpus = [0, 1, 2, 3, 4]

        self.assertFalse(distributor.consume(cpus))
        self.assertEquals([], cpus)
        self.assertEquals(0, distributor.total_required)

        expected = [
            [0],
            [1, 2],
            [3, 4]]
        for cpus, component in zip(expected, distributor.components):
            self.assertEquals(cpus, component.cpus)


class TestDistributeNodeCPUs(base.BaseTestCase):

    def test_many_cpus_required(self):
        numa_nodes = [
            {'cpus': [0, 1, 2, 3]},
            {'cpus': [4, 5, 6, 7]}]
        components = [
            {'name': 'nova',
             'required_cpus': 5},
            {'name': 'dpdk',
             'required_cpus': 2}]
        expected_data = {
            'components': {
                'nova': [1, 2, 3, 5, 6],
                'dpdk': [0, 4]
            },
            'isolated_cpus': [0, 1, 2, 3, 4, 5, 6]
        }
        saved_numa_nodes = copy.deepcopy(numa_nodes)
        self.assertEquals(
            expected_data,
            cpu_distribution.distribute_node_cpus(numa_nodes, components))
        self.assertEquals(saved_numa_nodes, numa_nodes)

    def test_one_component(self):
        numa_nodes = [
            {'cpus': [0, 1, 2]},
            {'cpus': [3, 4, 5]}]
        components = [
            {'name': 'nova',
             'required_cpus': 5},
            {'name': 'dpdk',
             'required_cpus': 0}]
        expected_data = {
            'components': {
                'nova': [0, 1, 2, 3, 4],
                'dpdk': []
            },
            'isolated_cpus': [0, 1, 2, 3, 4]
        }
        self.assertEquals(
            expected_data,
            cpu_distribution.distribute_node_cpus(numa_nodes, components))

    def test_few_cpus_required(self):
        numa_nodes = [
            {'cpus': [0, 1, 2]},
            {'cpus': [3, 4, 5]}]
        components = [
            {'name': 'nova',
             'required_cpus': 1},
            {'name': 'dpdk',
             'required_cpus': 1}]
        expected_data = {
            'components': {
                'dpdk': [0],
                'nova': [1]
            },
            'isolated_cpus': [0, 1]
        }
        self.assertEquals(
            expected_data,
            cpu_distribution.distribute_node_cpus(numa_nodes, components))

    def test_no_cpus_required(self):
        numa_nodes = [
            {'cpus': [0, 1, 2, 3]},
            {'cpus': [4, 5, 6, 7]}]
        components = [
            {'name': 'nova',
             'required_cpus': 0},
            {'name': 'dpdk',
             'required_cpus': 0}]
        expected_data = {
            'components': {
                'dpdk': [],
                'nova': []
            },
            'isolated_cpus': []
        }
        self.assertEquals(
            expected_data,
            cpu_distribution.distribute_node_cpus(numa_nodes, components))
