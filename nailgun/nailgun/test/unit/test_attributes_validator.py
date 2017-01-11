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

import json
import mock

from nailgun.api.v1.validators import base
from nailgun.api.v1.validators import cluster
from nailgun import errors
from nailgun.test import base as base_test


class TestClusterAttributesValidator(base_test.BaseTestCase):
    def test_generated_attributes_validation(self):
        self.assertRaises(
            errors.InvalidData,
            cluster.ClusterAttributesValidator.validate,
            '{"generated": {"name": "test"}}')

    def test_editable_attributes_validation(self):
        self.assertRaises(
            errors.InvalidData,
            cluster.ClusterAttributesValidator.validate,
            '{"editable": "name"}')

    @mock.patch('nailgun.objects.Cluster.get_updated_editable_attributes')
    def test_invalid_provisioning_method(self, mock_cluster_attrs):
        attrs = {'editable': {'provision': {'method':
                 {'value': 'not_image', 'type': 'text'}}}}
        mock_cluster_attrs.return_value = attrs
        cluster_mock = mock.Mock(release=mock.Mock(environment_version='7.0'))
        self.assertRaises(
            errors.InvalidData,
            cluster.ClusterAttributesValidator.validate,
            json.dumps(attrs), cluster_mock)

    @mock.patch('nailgun.objects.Cluster.get_updated_editable_attributes')
    def test_provision_method_missing(self, mock_cluster_attrs):
        attrs = {'editable': {'method':
                 {'value': 'not_image', 'type': 'text'}}}
        mock_cluster_attrs.return_value = attrs
        cluster_mock = mock.Mock(release=mock.Mock(environment_version='7.0'))
        self.assertRaises(
            errors.InvalidData,
            cluster.ClusterAttributesValidator.validate,
            json.dumps(attrs), cluster_mock)

    @mock.patch('nailgun.objects.Cluster.get_updated_editable_attributes')
    def test_provision_method_passed(self, mock_cluster_attrs):
        attrs = {'editable': {'provision': {'method':
                 {'value': 'image', 'type': 'text'}}}}
        mock_cluster_attrs.return_value = attrs
        cluster_mock = mock.Mock(
            is_locked=False, release=mock.Mock(environment_version='7.0')
        )
        self.assertNotRaises(
            errors.InvalidData,
            cluster.ClusterAttributesValidator.validate,
            json.dumps(attrs), cluster_mock)

    @mock.patch('nailgun.objects.Cluster.get_updated_editable_attributes')
    def test_provision_method_passed_old(self, mock_cluster_attrs):
        attrs = {'editable': {'provision': {'method':
                 {'value': 'image', 'type': 'text'}}}}
        mock_cluster_attrs.return_value = attrs
        cluster_mock = mock.Mock(
            is_locked=False, release=mock.Mock(environment_version='6.0')
        )
        self.assertNotRaises(
            errors.InvalidData,
            cluster.ClusterAttributesValidator.validate,
            json.dumps(attrs), cluster_mock)

    def test_valid_attributes(self):
        valid_attibutes = [
            '{"group": {"name": "test"}}',
            '{"name": "test"}',
        ]
        for attributes in valid_attibutes:
            self.assertNotRaises(
                errors.InvalidData,
                cluster.ClusterAttributesValidator.validate,
                attributes)
            attribute_dict = json.loads(attributes)
            self.assertNotRaises(
                errors.InvalidData,
                cluster.ClusterAttributesValidator.validate_attributes,
                attribute_dict)


class TestBasicAttributesValidator(base_test.BaseTestCase):
    def test_missing_type(self):
        attrs = {
            'storage': {
                'osd_pool_size': {
                    'description': 'desc',
                    'label': 'OSD Pool Size',
                    'value': 'x',
                    'weight': 80
                }
            }
        }
        self.assertRaises(
            errors.InvalidData,
            base.BasicAttributesValidator.validate_attributes,
            attrs)

    def test_missing_value(self):
        attrs = {
            'storage': {
                'osd_pool_size': {
                    'description': 'desc',
                    'label': 'OSD Pool Size',
                    'type': 'checkbox',
                    'weight': 80
                }
            }
        }
        self.assertRaises(
            errors.InvalidData,
            base.BasicAttributesValidator.validate_attributes,
            attrs)

    def test_invalid_regexp(self):
        attrs = {
            'storage': {
                'osd_pool_size': {
                    'description': 'desc',
                    'label': 'OSD Pool Size',
                    'type': 'text',
                    'value': '212a',
                    'regex': {
                        'error': 'Invalid',
                        'source': '^\d+$'
                    },
                    'weight': 80
                }
            }
        }
        self.assertRaises(
            errors.InvalidData,
            base.BasicAttributesValidator.validate_attributes,
            attrs)

    def test_checkbox_value(self):
        attrs = {
            'storage': {
                'osd_pool_size': {
                    'description': 'desc',
                    'label': 'OSD Pool Size',
                    'type': 'checkbox',
                    'value': True,
                    'weight': 80
                }
            }
        }
        self.assertNotRaises(
            errors.InvalidData,
            base.BasicAttributesValidator.validate_attributes,
            attrs)
        attrs = {
            'storage': {
                'osd_pool_size': {
                    'description': 'desc',
                    'label': 'OSD Pool Size',
                    'type': 'checkbox',
                    'value': 'x',
                    'weight': 80
                }
            }
        }
        self.assertRaises(
            errors.InvalidData,
            base.BasicAttributesValidator.validate_attributes,
            attrs)

    def test_custom_repo_configuration_value(self):
        attrs = {
            'storage': {
                'repos': {
                    'description': 'desc',
                    'type': 'custom_repo_configuration',
                    'value': [{
                        'name': 'ubuntu',
                        'priority': None,
                        'section': 'main universe multiverse',
                        'suite': 'trusty',
                        'type': 'deb',
                        'uri': 'http://archive.ubuntu.com/ubuntu/'
                    }, {
                        'name': 'ubuntu-updates',
                        'priority': None,
                        'section': 'main universe multiverse',
                        'suite': 'trusty-updates',
                        'type': 'deb',
                        'uri': 'http://archive.ubuntu.com/ubuntu/'
                    }]
                }
            }
        }
        self.assertNotRaises(
            errors.InvalidData,
            base.BasicAttributesValidator.validate_attributes,
            attrs)

    def test_password_value(self):
        attrs = {
            'storage': {
                'osd_pool_size': {
                    'description': 'desc',
                    'label': 'OSD Pool Size',
                    'type': 'password',
                    'value': '2',
                    'weight': 80
                }
            }
        }
        self.assertNotRaises(
            errors.InvalidData,
            base.BasicAttributesValidator.validate_attributes,
            attrs)

        attrs = {
            'storage': {
                'osd_pool_size': {
                    'description': 'desc',
                    'label': 'OSD Pool Size',
                    'type': 'password',
                    'value': 2,
                    'weight': 80
                }
            }
        }
        self.assertRaises(
            errors.InvalidData,
            base.BasicAttributesValidator.validate_attributes,
            attrs)

    def test_radio_value(self):
        attrs = {
            'storage': {
                'syslog_transport': {
                    'label': 'Syslog transport protocol',
                    'type': 'radio',
                    'value': 'tcp',
                    'values': [{
                        'data': 'udp',
                        'description': '',
                        'label': 'UDP'
                    }, {
                        'data': 'tcp',
                        'description': '',
                        'label': 'TCP'
                    }, {
                        'data': 'missing-description',
                        'label': 'Missing Description'
                    }],
                    'weight': 3
                }
            }
        }

        self.assertNotRaises(
            errors.InvalidData,
            base.BasicAttributesValidator.validate_attributes,
            attrs)

    def test_select_value(self):
        attrs = {
            'common': {
                'libvirt_type': {
                    'label': 'Hypervisor type',
                    'type': 'select',
                    'value': 'qemu',
                    'values': [{
                        'data': 'kvm',
                        'label': 'KVM',
                        'description': 'KVM description'
                    }, {
                        'data': 'qemu',
                        'label': 'QEMU',
                        'description': 'QEMU description'
                    }]
                }
            }
        }

        self.assertNotRaises(
            errors.InvalidData,
            base.BasicAttributesValidator.validate_attributes,
            attrs)

    def test_text_value(self):
        attrs = {
            'storage': {
                'osd_pool_size': {
                    'description': 'desc',
                    'label': 'OSD Pool Size',
                    'type': 'text',
                    'value': '2',
                    'weight': 80
                }
            }
        }
        self.assertNotRaises(
            errors.InvalidData,
            base.BasicAttributesValidator.validate_attributes,
            attrs)

        attrs = {
            'storage': {
                'osd_pool_size': {
                    'description': 'desc',
                    'label': 'OSD Pool Size',
                    'type': 'text',
                    'value': 2,
                    'weight': 80
                }
            }
        }
        self.assertRaises(
            errors.InvalidData,
            base.BasicAttributesValidator.validate_attributes,
            attrs)

        attrs = {
            'storage': {
                'osd_pool_size': {
                    'description': 'desc',
                    'label': 'OSD Pool Size',
                    'type': 'text',
                    'nullable': True,
                    'value': '2',
                    'weight': 80
                }
            }
        }
        self.assertNotRaises(
            errors.InvalidData,
            base.BasicAttributesValidator.validate_attributes,
            attrs)

        attrs = {
            'storage': {
                'osd_pool_size': {
                    'description': 'desc',
                    'label': 'OSD Pool Size',
                    'type': 'text',
                    'nullable': True,
                    'value': None,
                    'weight': 80
                }
            }
        }
        self.assertNotRaises(
            errors.InvalidData,
            base.BasicAttributesValidator.validate_attributes,
            attrs)

    def test_textarea_value(self):
        attrs = {
            'storage': {
                'osd_pool_size': {
                    'description': 'desc',
                    'label': 'OSD Pool Size',
                    'type': 'textarea',
                    'value': '2',
                    'weight': 80
                }
            }
        }
        self.assertNotRaises(
            errors.InvalidData,
            base.BasicAttributesValidator.validate_attributes,
            attrs)

        attrs = {
            'storage': {
                'osd_pool_size': {
                    'description': 'desc',
                    'label': 'OSD Pool Size',
                    'type': 'textarea',
                    'value': 2,
                    'weight': 80
                }
            }
        }
        self.assertRaises(
            errors.InvalidData,
            base.BasicAttributesValidator.validate_attributes,
            attrs)

    def test_text_list_value(self):
        attrs = {
            'storage': {
                'osd_pool_size': {
                    'description': 'desc',
                    'label': 'OSD Pool Size',
                    'type': 'text_list',
                    'value': ['2'],
                    'weight': 80
                }
            }
        }
        # check that text_list value is a list
        self.assertNotRaises(
            errors.InvalidData,
            base.BasicAttributesValidator.validate_attributes,
            attrs)

        attrs = {
            'storage': {
                'osd_pool_size': {
                    'description': 'desc',
                    'label': 'OSD Pool Size',
                    'type': 'text_list',
                    'value': 2,
                    'weight': 80
                }
            }
        }
        self.assertRaises(
            errors.InvalidData,
            base.BasicAttributesValidator.validate_attributes,
            attrs)

    def test_valid_attributes(self):
        valid_attibutes = [
            '{"group": {"name": "test"}}',
            '{"name": "test"}',
        ]

        for attributes in valid_attibutes:
            self.assertNotRaises(
                errors.InvalidData,
                base.BasicAttributesValidator.validate,
                attributes)
            attribute_dict = json.loads(attributes)
            self.assertNotRaises(
                errors.InvalidData,
                base.BasicAttributesValidator.validate_attributes,
                attribute_dict)

    def test_custom_hugepages_value(self):
        attrs = {
            'hugepages': {
                'nova': {
                    'description': 'desc',
                    'label': 'Label',
                    'type': 'custom_hugepages',
                    'value': {
                        '2048': 4,
                        '1048576': 2
                    },
                    'weight': 10
                }
            }
        }
        self.assertNotRaises(
            errors.InvalidData,
            base.BasicAttributesValidator.validate_attributes,
            attrs)

        attrs = {
            'storage': {
                'osd_pool_size': {
                    'description': 'desc',
                    'label': 'OSD Pool Size',
                    'type': 'custrom_hugepages',
                    'value': {
                        '2048': '1'
                    },
                    'weight': 10
                }
            }
        }
        self.assertRaises(
            errors.InvalidData,
            base.BasicAttributesValidator.validate_attributes,
            attrs)

    def test_number_value(self):
        attrs = {
            'cpu_pinning': {
                'nova': {
                    'description': 'desc',
                    'label': 'Label',
                    'type': 'number',
                    'value': 1,
                    'min': 0,
                    'weight': 10
                }
            }
        }
        self.assertNotRaises(
            errors.InvalidData,
            base.BasicAttributesValidator.validate_attributes,
            attrs)

        attrs = {
            'cpu_pinning': {
                'nova': {
                    'description': 'desc',
                    'label': 'Label',
                    'type': 'number',
                    'value': -1,
                    'min': 0,
                    'weight': 10
                }
            }
        }
        self.assertRaises(
            errors.InvalidData,
            base.BasicAttributesValidator.validate_attributes,
            attrs)

        attrs = {
            'cpu_pinning': {
                'nova': {
                    'description': 'desc',
                    'label': 'Label',
                    'type': 'number',
                    'nullable': True,
                    'value': 1,
                    'min': 0,
                    'weight': 10
                }
            }
        }
        self.assertNotRaises(
            errors.InvalidData,
            base.BasicAttributesValidator.validate_attributes,
            attrs)

        attrs = {
            'cpu_pinning': {
                'nova': {
                    'description': 'desc',
                    'label': 'Label',
                    'type': 'number',
                    'nullable': True,
                    'value': None,
                    'min': 0,
                    'weight': 10
                }
            }
        }
        self.assertNotRaises(
            errors.InvalidData,
            base.BasicAttributesValidator.validate_attributes,
            attrs)

    def test_restriction_strict(self):
        context = {'context': {'existing': {'value': 13}}}

        for strict in (False, True):
            attrs = {
                'section': {
                    'subsection': {
                        'restrictions': [{
                            'condition': 'context:nonexisting.value == 42',
                            'strict': strict,
                        }],
                    },
                },
            }

            if strict:
                assert_fn = self.assertRaises
            else:
                assert_fn = self.assertNotRaises

            assert_fn(
                TypeError,
                base.BasicAttributesValidator.validate_attributes,
                attrs,
                models=context)
