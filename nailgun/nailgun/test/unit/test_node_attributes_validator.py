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

import json
import mock
from nailgun.api.v1.validators import node as node_validator
from nailgun import consts
from nailgun import errors
from nailgun import objects
from nailgun.test import base


validator = node_validator.NodeAttributesValidator.validate


def mock_cluster_attributes(func):
    def wrapper(*args, **kwargs):
        cluster_attr_mock = mock.patch.object(
            objects.Cluster,
            'get_editable_attributes',
            return_value={
                'common': {
                    'libvirt_type': {
                        'value': consts.HYPERVISORS.kvm,
                    }
                }
            }
        )
        node_dpdk_mock = mock.patch.object(
            objects.Node,
            'dpdk_enabled',
            return_value=True
        )
        with cluster_attr_mock, node_dpdk_mock:
            func(*args, **kwargs)

    return wrapper


class BaseNodeAttributeValidatorTest(base.BaseTestCase):
    def setUp(self):
        super(BaseNodeAttributeValidatorTest, self).setUp()

        meta = self.env.default_metadata()

        meta['numa_topology'] = {
            "supported_hugepages": [2048, 1048576],
            "numa_nodes": [
                {"id": 0, "cpus": [0, 1], 'memory': 3 * 1024 ** 3},
                {"id": 1, "cpus": [2, 3], 'memory': 3 * 1024 ** 3},
            ]
        }
        meta['cpu']['total'] = 4

        attributes = {
            'hugepages': {
                'nova': {
                    'type': 'custom_hugepages',
                    'value': {},
                },
                'dpdk': {
                    'type': 'number',
                    'value': 1024,
                },
            },
            'cpu_pinning': {
                'dpdk': {
                    'type': 'number',
                    'value': 0,
                },
                'nova': {
                    'type': 'number',
                    'value': 0,
                }
            }
        }
        self.node = mock.Mock(id=1, meta=meta, attributes=attributes)
        self.cluster = mock.Mock()


@mock.patch.object(objects.Node, 'dpdk_nics', return_value=[])
class TestNodeAttributesValidatorHugepages(BaseNodeAttributeValidatorTest):

    @mock_cluster_attributes
    def test_defaults(self, m_dpdk_nics):
        data = {}

        self.assertNotRaises(errors.InvalidData, validator,
                             json.dumps(data), self.node, self.cluster)

    @mock_cluster_attributes
    def test_valid_hugepages(self, m_dpdk_nics):
        data = {
            'hugepages': {
                'nova': {
                    'value': {
                        '2048': 1,
                        '1048576': 1,
                    },
                },
                'dpdk': {
                    'value': 1024,
                },
            }
        }

        self.assertNotRaises(errors.InvalidData, validator,
                             json.dumps(data), self.node, self.cluster)

    @mock_cluster_attributes
    def test_too_much_hugepages(self, m_dpdk_nics):
        data = {
            'hugepages': {
                'nova': {
                    'value': {
                        '2048': 100500,
                        '1048576': 100500,
                    },
                },
            },
        }

        self.assertRaisesWithMessageIn(
            errors.InvalidData, 'Not enough memory for components',
            validator, json.dumps(data), self.node, self.cluster)

    @mock_cluster_attributes
    def test_not_enough_dpdk_hugepages(self, m_dpdk_nics):
        data = {
            'hugepages': {
                'nova': {
                    'value': {
                        '2048': 1,
                        '1048576': 0,
                    },
                },
                'dpdk': {
                    'value': 1023,
                    'min': 1024
                },
            }
        }
        message = ("Node {0} does not have enough hugepages for dpdk. "
                   "Need to allocate at least {1} MB.").format(self.node.id,
                                                               1024)
        self.assertRaisesWithMessageIn(
            errors.InvalidData, message,
            validator, json.dumps(data), self.node, self.cluster)

    @mock_cluster_attributes
    @mock.patch.object(objects.Node, 'dpdk_enabled', return_value=False)
    def test_valid_hugepages_non_dpdk(self, m_dpdk_nics, m_dpdk_enabled):
        data = {
            'hugepages': {
                'nova': {
                    'value': {
                        '2048': 1,
                        '1048576': 1,
                    },
                },
                'dpdk': {
                    'value': 0,
                },
            }
        }
        self.assertNotRaises(errors.InvalidData, validator,
                             json.dumps(data), self.node, self.cluster)

    @mock_cluster_attributes
    @mock.patch.object(objects.Node, 'dpdk_enabled', return_value=False)
    def test_non_zero_value_hugepages_non_dpdk(self, m_dpdk_nics,
                                               m_dpdk_enabled):
        data = {
            'hugepages': {
                'dpdk': {
                    'value': 1,
                },
            }
        }
        message = ("Hugepages for dpdk should be equal to 0 "
                   "if dpdk is disabled.")
        self.assertRaisesWithMessageIn(
            errors.InvalidData, message,
            validator, json.dumps(data), self.node, self.cluster)

    @mock_cluster_attributes
    def test_dpdk_requires_too_much(self, m_dpdk_nics):
        data = {
            'hugepages': {
                'dpdk': {
                    'value': 2049,
                },
            }
        }

        self.assertRaisesWithMessageIn(
            errors.InvalidData, 'could not require more memory than node has',
            validator, json.dumps(data), self.node, self.cluster)

    @mock_cluster_attributes
    def test_limited_supported_hugepages(self, m_dpdk_nics):
        data = {
            'hugepages': {
                'nova': {
                    'value': {
                        '2048': 3,
                        '1048576': 0,
                    },
                },
            },
        }

        self.node.meta['numa_topology']['supported_hugepages'] = ['2048']
        self.assertNotRaises(errors.InvalidData, validator,
                             json.dumps(data), self.node, self.cluster)

        data['hugepages']['nova']['value']['1048576'] = 1
        self.assertRaisesWithMessageIn(
            errors.InvalidData,
            "Node 1 doesn't support 1048576 Huge Page(s),"
            " supported Huge Page(s): 2048.",
            validator, json.dumps(data), self.node, self.cluster)


@mock.patch.object(objects.Node, 'dpdk_nics', return_value=[])
class TestNodeAttributesValidatorCpuPinning(BaseNodeAttributeValidatorTest):
    @mock_cluster_attributes
    def test_valid_data(self, m_dpdk_nics):
        data = {
            'cpu_pinning': {
                'nova': {'value': 1},
            },
        }

        self.assertNotRaises(errors.InvalidData, validator,
                             json.dumps(data), self.node, self.cluster)

    @mock_cluster_attributes
    def test_no_cpu_for_os(self, m_dpdk_nics):
        pinned_count = self.node.meta['cpu']['total']

        data = {
            'cpu_pinning': {
                'nova': {'value': pinned_count},
            },
        }

        self.assertRaisesWithMessageIn(
            errors.InvalidData, 'at least one cpu',
            validator, json.dumps(data), self.node, self.cluster)

    @mock_cluster_attributes
    def test_one_cpu_for_os(self, m_dpdk_nics):
        pinned_count = self.node.meta['cpu']['total'] - 1

        data = {
            'cpu_pinning': {
                'nova': {'value': pinned_count},
            },
        }

        self.assertNotRaises(errors.InvalidData, validator,
                             json.dumps(data), self.node, self.cluster)
