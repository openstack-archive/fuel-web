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

from nailgun.policy import node_attributes
from nailgun.test import base


class TestNodeAttributes(base.BaseUnitTest):

    def test_distribute_node_cpus(self):
        node = mock.Mock()
        node.meta = {'numa_topology': {
            'numa_nodes': [
                {'cpus': [0, 1, 2, 3]},
                {'cpus': [4, 5, 6, 7]}
            ]
        }}
        node.attributes = {
            'cpu_pinning': {
                'nova': {
                    'value': '5'
                },
                'dpdk': {
                    'value': '2'
                }
            }
        }
        expected_data = {
            'components': {
                'nova': [1, 2, 3, 5, 6],
                'dpdk': [0, 4]
            },
            'isolated_cpus': [0, 1, 2, 3, 4, 5, 6]
        }
        self.assertEquals(
            expected_data,
            node_attributes.distribute_node_cpus(node))

    def test_distribute_node_cpus_one_component(self):
        node = mock.Mock()
        node.meta = {'numa_topology': {
            'numa_nodes': [
                {'cpus': [0, 1, 2]},
                {'cpus': [3, 4, 5]}
            ]
        }}
        node.attributes = {
            'cpu_pinning': {
                'dpdk': {
                    'value': '0'
                },
                'nova': {
                    'value': '5'
                }
            }
        }
        expected_data = {
            'components': {
                'nova': [0, 1, 2, 3, 4],
                'dpdk': []
            },
            'isolated_cpus': [0, 1, 2, 3, 4]
        }
        self.assertEquals(
            expected_data,
            node_attributes.distribute_node_cpus(node))

    def test_distribute_node_cpus_few_required(self):
        node = mock.Mock()
        node.meta = {'numa_topology': {
            'numa_nodes': [
                {'cpus': [0, 1, 2]},
                {'cpus': [3, 4, 5]}
            ]
        }}
        node.attributes = {
            'cpu_pinning': {
                'nova': {
                    'value': '1'
                },
                'dpdk': {
                    'value': '1'
                }
            }
        }
        expected_data = {
            'components': {
                'dpdk': [0],
                'nova': [1]
            },
            'isolated_cpus': [0, 1]
        }
        self.assertEquals(
            expected_data,
            node_attributes.distribute_node_cpus(node))

    def test_distribute_node_cpus_empty(self):
        node = mock.Mock()
        node.meta = {'numa_topology': {
            'numa_nodes': [
                {'cpus': [0, 1, 2, 3]},
                {'cpus': [4, 5, 6, 7]}
            ]
        }}
        node.attributes = {
            'cpu_pinning': {
                'nova': {
                    'value': '0'
                },
                'dpdk': {
                    'value': '0'
                }
            }
        }
        expected_data = {
            'components': {
                'dpdk': [],
                'nova': []
            },
            'isolated_cpus': []
        }
        self.assertEquals(
            expected_data,
            node_attributes.distribute_node_cpus(node))
