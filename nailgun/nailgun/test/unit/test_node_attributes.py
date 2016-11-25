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

import mock

from nailgun import objects
from nailgun.test import base

FAKE_HUGEPAGES = ['2048', '1048576']

NODE_ATTRIBUTES = {
    'hugepages': {
        'nova': {
            'type': 'custom_hugepages',
            'value': {}
        }
    }
}

NODE_META = {
    'numa_topology': {
        'supported_hugepages': FAKE_HUGEPAGES,
        'numa_nodes': []
    }
}


class TestNodeAttributes(base.BaseUnitTest):

    @mock.patch.object(objects.Node, 'dpdk_nics')
    @mock.patch.object(objects.NodeAttributes, 'node_cpu_pinning_info')
    @mock.patch('nailgun.policy.cpu_distribution.distribute_node_cpus')
    def test_distribute_node_cpus(self, m_distribute, m_info, m_dpdk_nics):
        fake_numa_nodes = [{'id': 0}]
        comp_entity = {
            'comp1': {
                'cpu_required': [0],
                'name': 'comp1'
            }
        }
        m_info.return_value = {
            'components': comp_entity
        }
        m_dpdk_nics.return_value = [
            mock.Mock(interface_properties={'numa_node': None}),
            mock.Mock(interface_properties={'numa_node': 1}),
        ]

        node = mock.Mock(
            meta={'numa_topology': {
                'numa_nodes': fake_numa_nodes}},
            attributes={'cpu_pinning': {}})

        objects.NodeAttributes.distribute_node_cpus(node)

        m_dpdk_nics.assert_called_once_with(node)
        m_distribute.assert_called_once_with(
            fake_numa_nodes, comp_entity, [0, 1])

    def test_node_cpu_pinning_info(self):
        node = mock.Mock(
            id=1,
            attributes={
                'cpu_pinning': {
                    'meta': {'some': 'info'},
                    'comp1': {'value': 1},
                    'comp2': {'value': 3}}
            }
        )
        self.assertEquals(
            {'total_required_cpus': 4,
             'components': {
                 'comp1': {'name': 'comp1',
                           'required_cpus': 1},
                 'comp2': {'name': 'comp2',
                           'required_cpus': 3}}},
            objects.NodeAttributes.node_cpu_pinning_info(node))

    def test_total_hugepages(self):
        node = mock.Mock(
            id=1,
            attributes={
                'hugepages': {
                    'comp1': {
                        'type': 'custom_hugepages',
                        'value': {
                            '2048': 14,
                            '1048576': 2}},
                    'comp2': {
                        'type': 'number',
                        'value': 20}}},
            meta={'numa_topology': {'numa_nodes': [{'id': 0}]}})
        expected = {
            '2048': 24,
            '1048576': 2}
        self.assertDictEqual(
            expected,
            objects.NodeAttributes.total_hugepages(node))

    def test_hugepages_kernel_opts(self):
        node = mock.Mock(
            id=1,
            attributes={
                'hugepages': {
                    'comp1': {
                        'type': 'custom_hugepages',
                        'value': {
                            '1048576': 2}},
                    'comp2': {
                        'type': 'number',
                        'value': 10}}},
            meta={'numa_topology': {'numa_nodes': [{'id': '0'}]}})
        expected = " hugepagesz=2M hugepages=5 hugepagesz=1G hugepages=2"
        self.assertEqual(
            expected,
            objects.NodeAttributes.hugepages_kernel_opts(node))

    def _make_hugepages_node(self):
        return mock.Mock(
            id=1,
            attributes={
                'hugepages': {
                    'comp1': {
                        'type': 'custom_hugepages',
                        'value': {
                            '2048': 1024,
                            '1048576': 1,
                        }
                    },
                    'comp2': {
                        'type': 'number',
                        'value': 512
                    }
                }
            },
            meta={'numa_topology': {'numa_nodes': [
                {'id': 0, 'memory': 3 * (2 ** 30), 'cpus': [0, 1]},
                {'id': 1, 'memory': 3 * (2 ** 30), 'cpus': [2, 3]},
            ]}}
        )

    @mock.patch.object(objects.NodeAttributes, 'distribute_node_cpus')
    def test_hugepages_distribution(self, m_distribute):
        m_distribute.return_value = {'components': {}}
        node = self._make_hugepages_node()
        expected = [
            {'numa_id': 0, 'size': 1048576, 'count': 1},
            {'numa_id': 0, 'size': 2048, 'count': 512},
            {'numa_id': 1, 'size': 2048, 'count': 1024},
        ]

        self.assertItemsEqual(
            objects.NodeAttributes.distribute_hugepages(node), expected)

    @mock.patch.object(objects.NodeAttributes, 'distribute_node_cpus')
    def test_hugepages_distribution_with_numa_sort(self, m_distribute):
        m_distribute.return_value = {
            'components': {
                'nova': [2, 3],
            }
        }
        node = self._make_hugepages_node()

        expected = [
            {'numa_id': 1, 'size': 1048576, 'count': 1},
            {'numa_id': 1, 'size': 2048, 'count': 1024},
            {'numa_id': 0, 'size': 2048, 'count': 512},
        ]

        self.assertItemsEqual(
            objects.NodeAttributes.distribute_hugepages(node), expected)

    def test_set_default_hugepages(self):
        hugepages = ['2048', '1048576']
        node = mock.Mock(
            id=1,
            attributes=NODE_ATTRIBUTES,
        )
        objects.NodeAttributes.set_default_hugepages(node)
        nova_hugepages = node.attributes['hugepages']['nova']['value']
        for size in FAKE_HUGEPAGES:
            self.assertEqual(0, nova_hugepages[size])

    def test_get_default_hugepages(self):
        node = mock.Mock(
            id=1,
            attributes=NODE_ATTRIBUTES,
            meta=NODE_META
        )

        hugepages = objects.NodeAttributes.get_default_hugepages(node)
        hugepages_value = hugepages['hugepages']['nova']['value']
        for size in FAKE_HUGEPAGES:
            self.assertEqual(0, hugepages_value[size])
