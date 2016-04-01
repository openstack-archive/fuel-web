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


class TestNodeAttributes(base.BaseUnitTest):

    @mock.patch.object(objects.NodeAttributes, 'node_cpu_pinning_info')
    @mock.patch('nailgun.policy.cpu_distribution.distribute_node_cpus')
    def test_distribute_node_cpus(self, m_distribute, m_info):
        fake_numa_nodes = [{'id': 0}]
        comp_entity = {
            'cpu_required': [0],
            'name': 'comp1'
        }
        m_info.return_value = {
            'components': {
                'comp1': comp_entity
            }
        }
        node = mock.Mock(
            meta={'numa_topology': {
                'numa_nodes': fake_numa_nodes}},
            attributes={'cpu_pinning': {}})
        objects.NodeAttributes.distribute_node_cpus(node)
        m_distribute.assert_called_once_with(
            fake_numa_nodes, [comp_entity])

    def test_node_cpu_pinning_info(self):
        node = mock.Mock(attributes={
            'cpu_pinning': {
                'meta': {
                    'some': 'info'},
                'comp1': {
                    'value': 1},
                'comp2': {
                    'value': 3}}})
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
            attributes={
                'hugepages': {
                    'comp1': {
                        'type': 'custom_hugepages',
                        'value': {
                            '2048': 14,
                            '1048576': '2'}},
                    'comp2': {
                        'type': 'text',
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
            attributes={
                'hugepages': {
                    'comp1': {
                        'type': 'custom_hugepages',
                        'value': {
                            '1048576': 2}},
                    'comp2': {
                        'type': 'text',
                        'value': '10'}}},
            meta={'numa_topology': {'numa_nodes': [{'id': '0'}]}})
        expected = " hugepagesz=2M hugepages=5 hugepagesz=1G hugepages=2"
        self.assertEqual(
            expected,
            objects.NodeAttributes.hugepages_kernel_opts(node))

    def test_hugepages_distribution(self):
        node = mock.Mock(
            attributes={
                'hugepages': {
                    'comp1': {
                        'type': 'custom_hugepages',
                        'value': {
                            '2048': 512,
                            '1048576': 1,
                        }
                    },
                    'comp2': {
                        'type': 'text',
                        'value': '512'}}},
            meta={'numa_topology': {'numa_nodes': [
                {'id': 0, 'memory': 2 ** 31},
                {'id': 1, 'memory': 2 ** 31},
            ]}}
        )

        expected = [
            {'numa_id': 0, 'size': 2048, 'count': 512},
            {'numa_id': 1, 'size': 2048, 'count': 512},
            {'numa_id': 1, 'size': 1048576, 'count': 1},
        ]

        self.assertEqual(
            objects.NodeAttributes.distribute_hugepages(node), expected)

    def test_set_default_hugepages(self):
        fake_hugepages = ['0', '1', '2', '3']
        node = mock.Mock(
            attributes={
                'hugepages': {
                    'nova': {
                        'type': 'custom_hugepages',
                        'value': {}
                    }
                }
            },
            meta={
                'numa_topology': {
                    'supported_hugepages': fake_hugepages,
                    'numa_nodes': []}}
        )
        objects.NodeAttributes.set_default_hugepages(node)
        hugepages = node.attributes['hugepages']['nova']['value']
        for size in fake_hugepages:
            self.assertEqual(0, hugepages[size])
