# -*- coding: utf-8 -*-

#    Copyright 2014 Mirantis, Inc.
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

    @mock.patch('six.itervalues', mock.Mock(return_value=[42]))
    @mock.patch('nailgun.policy.cpu_distribution.distribute_node_cpus')
    def test_distribute_node_cpus(self, m_distribute):
        fake_numa_nodes = [{'id': 0}]
        node = mock.Mock(
            meta={'numa_topology': {
                'numa_nodes': fake_numa_nodes}},
            attributes={'cpu_pinning': {}})
        objects.NodeAttributes.distribute_node_cpus(node)
        m_distribute.assert_called_once_with(
            fake_numa_nodes, [42])

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
                            2048: '14',
                            1048576: '2'}},
                    'comp2': {
                        'type': 'text',
                        'value': 20}}},
            meta={'numa_topology': {'numa_nodes': [{'id': 0}]}})
        expected = {
            2048: 24,
            1048576: 2}
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
                            1048576: '2'}},
                    'comp2': {
                        'type': 'text',
                        'value': '10'}}},
            meta={'numa_topology': {'numa_nodes': [{'id': '0'}]}})
        expected = " hugepagesz=2M hugepages=5 hugepagesz=1G hugepages=2"
        self.assertEqual(
            expected,
            objects.NodeAttributes.hugepages_kernel_opts(node))
