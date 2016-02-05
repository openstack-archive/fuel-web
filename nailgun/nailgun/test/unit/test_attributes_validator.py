# -*- coding: utf-8 -*-
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
from mock import Mock
from mock import patch

import json
import yaml

from nailgun.api.v1.validators.cluster import AttributesValidator
from nailgun.errors import errors
from nailgun.test.base import BaseTestCase


class TestAttributesValidator(BaseTestCase):
    def test_generated_attributes_validation(self):
        self.assertRaises(errors.InvalidData,
                          AttributesValidator.validate,
                          '{"generated": {"name": "test"}}')

    def test_editable_attributes_validation(self):
        self.assertRaises(errors.InvalidData,
                          AttributesValidator.validate,
                          '{"editable": "name"}')

    def test_missing_type(self):
        attrs = '''
            editable:
              storage:
                osd_pool_size:
                  description: desc
                  label: OSD Pool Size
                  value: 'x'
                  weight: 80
        '''

        self.assertRaises(errors.InvalidData,
                          AttributesValidator.validate_editable_attributes,
                          yaml.load(attrs))

    def test_missing_value(self):
        attrs = '''
            editable:
              storage:
                osd_pool_size:
                  description: desc
                  label: OSD Pool Size
                  type: checkbox
                  weight: 80
        '''

        self.assertRaises(errors.InvalidData,
                          AttributesValidator.validate_editable_attributes,
                          yaml.load(attrs))

    def test_invalid_regexp(self):
        attrs = '''
        editable:
          storage:
            osd_pool_size:
              description: desc
              label: OSD Pool Size
              type: text
              value: '212a'
              regex:
                error: Invalid
                source: ^\d+$
              weight: 80
        '''

        self.assertRaises(errors.InvalidData,
                          AttributesValidator.validate_editable_attributes,
                          yaml.load(attrs))

    def test_checkbox_value(self):
        attrs = '''
        editable:
          storage:
            osd_pool_size:
              description: desc
              label: OSD Pool Size
              type: checkbox
              value: true
              weight: 80
        '''

        self.assertNotRaises(errors.InvalidData,
                             AttributesValidator.validate_editable_attributes,
                             yaml.load(attrs))
        attrs = '''
        editable:
          storage:
            osd_pool_size:
              description: desc
              label: OSD Pool Size
              type: checkbox
              value: 'x'
              weight: 80
        '''

        self.assertRaises(errors.InvalidData,
                          AttributesValidator.validate_editable_attributes,
                          yaml.load(attrs))

    def test_custom_repo_configuration_value(self):
        attrs = '''
        editable:
          storage:
            repos:
              description: desc
              type: custom_repo_configuration
              value:
              - name: ubuntu
                priority: null
                section: main universe multiverse
                suite: trusty
                type: deb
                uri: http://archive.ubuntu.com/ubuntu/
              - name: ubuntu-updates
                priority: null
                section: main universe multiverse
                suite: trusty-updates
                type: deb
                uri: http://archive.ubuntu.com/ubuntu/
        '''

        self.assertNotRaises(errors.InvalidData,
                             AttributesValidator.validate_editable_attributes,
                             yaml.load(attrs))

    def test_password_value(self):
        attrs = '''
        editable:
          storage:
            osd_pool_size:
              description: desc
              label: OSD Pool Size
              type: password
              value: '2'
              weight: 80
        '''

        self.assertNotRaises(errors.InvalidData,
                             AttributesValidator.validate_editable_attributes,
                             yaml.load(attrs))
        attrs = '''
        editable:
          storage:
            osd_pool_size:
              description: desc
              label: OSD Pool Size
              type: password
              value: 2
              weight: 80
        '''

        self.assertRaises(errors.InvalidData,
                          AttributesValidator.validate_editable_attributes,
                          yaml.load(attrs))

    def test_radio_value(self):
        attrs = '''
        editable:
          storage:
            syslog_transport:
              label: Syslog transport protocol
              type: radio
              value: tcp
              values:
              - data: udp
                description: ''
                label: UDP
              - data: tcp
                description: ''
                label: TCP
              - data: missing-description
                label: Missing Description
              weight: 3
        '''

        self.assertNotRaises(errors.InvalidData,
                             AttributesValidator.validate_editable_attributes,
                             yaml.load(attrs))

    def test_select_value(self):
        attrs = '''
        editable:
          common:
            libvirt_type:
              label: Hypervisor type
              type: select
              value: qemu
              values:
                - data: kvm
                  label: KVM
                  description: KVM description
                - data: qemu
                  label: QEMU
                  description: QEMU description
        '''

        self.assertNotRaises(errors.InvalidData,
                             AttributesValidator.validate_editable_attributes,
                             yaml.load(attrs))

    def test_text_value(self):
        attrs = '''
        editable:
          storage:
            osd_pool_size:
              description: desc
              label: OSD Pool Size
              type: text
              value: '2'
              weight: 80
        '''

        self.assertNotRaises(errors.InvalidData,
                             AttributesValidator.validate_editable_attributes,
                             yaml.load(attrs))
        attrs = '''
        editable:
          storage:
            osd_pool_size:
              description: desc
              label: OSD Pool Size
              type: text
              value: 2
              weight: 80
        '''

        self.assertRaises(errors.InvalidData,
                          AttributesValidator.validate_editable_attributes,
                          yaml.load(attrs))

    def test_textarea_value(self):
        attrs = '''
        editable:
          storage:
            osd_pool_size:
              description: desc
              label: OSD Pool Size
              type: textarea
              value: '2'
              weight: 80
        '''

        self.assertNotRaises(errors.InvalidData,
                             AttributesValidator.validate_editable_attributes,
                             yaml.load(attrs))
        attrs = '''
        editable:
          storage:
            osd_pool_size:
              description: desc
              label: OSD Pool Size
              type: textarea
              value: 2
              weight: 80
        '''

        self.assertRaises(errors.InvalidData,
                          AttributesValidator.validate_editable_attributes,
                          yaml.load(attrs))

    def test_text_list_value(self):
        attrs = '''
        editable:
          storage:
            osd_pool_size:
              description: desc
              label: OSD Pool Size
              type: text_list
              value: ['2']
              weight: 80
        '''
        # check that text_list value is a list
        self.assertNotRaises(errors.InvalidData,
                             AttributesValidator.validate_editable_attributes,
                             yaml.load(attrs))
        attrs = '''
        editable:
          storage:
            osd_pool_size:
              description: desc
              label: OSD Pool Size
              type: text_list
              value: 2
              weight: 80
        '''

        self.assertRaises(errors.InvalidData,
                          AttributesValidator.validate_editable_attributes,
                          yaml.load(attrs))

    @patch('nailgun.objects.Cluster.get_updated_editable_attributes')
    def test_invalid_provisioning_method(self, mock_cluster_attrs):
        attrs = {'editable': {'provision': {'method':
                 {'value': 'not_image', 'type': 'text'}}}}
        mock_cluster_attrs.return_value = attrs
        cluster_mock = Mock(release=Mock(environment_version='7.0'))
        self.assertRaises(errors.InvalidData,
                          AttributesValidator.validate,
                          json.dumps(attrs), cluster_mock)

    @patch('nailgun.objects.Cluster.get_updated_editable_attributes')
    def test_provision_method_missing(self, mock_cluster_attrs):
        attrs = {'editable': {'method':
                 {'value': 'not_image', 'type': 'text'}}}
        mock_cluster_attrs.return_value = attrs
        cluster_mock = Mock(release=Mock(environment_version='7.0'))
        self.assertRaises(errors.InvalidData,
                          AttributesValidator.validate,
                          json.dumps(attrs), cluster_mock)

    @patch('nailgun.objects.Cluster.get_updated_editable_attributes')
    def test_provision_method_passed(self, mock_cluster_attrs):
        attrs = {'editable': {'provision': {'method':
                 {'value': 'image', 'type': 'text'}}}}
        mock_cluster_attrs.return_value = attrs
        cluster_mock = Mock(
            is_locked=False, release=Mock(environment_version='7.0')
        )
        self.assertNotRaises(errors.InvalidData,
                             AttributesValidator.validate,
                             json.dumps(attrs), cluster_mock)

    @patch('nailgun.objects.Cluster.get_updated_editable_attributes')
    def test_provision_method_passed_old(self, mock_cluster_attrs):
        attrs = {'editable': {'provision': {'method':
                 {'value': 'image', 'type': 'text'}}}}
        mock_cluster_attrs.return_value = attrs
        cluster_mock = Mock(
            is_locked=False, release=Mock(environment_version='6.0')
        )
        self.assertNotRaises(errors.InvalidData,
                             AttributesValidator.validate,
                             json.dumps(attrs), cluster_mock)

    def test_valid_attributes(self):
        valid_attibutes = [
            '{"editable": {"name": "test"}}',
            '{"name": "test"}',
        ]

        for attributes in valid_attibutes:
            self.assertNotRaises(errors.InvalidData,
                                 AttributesValidator.validate,
                                 attributes)
            self.assertNotRaises(
                errors.InvalidData,
                AttributesValidator.validate_editable_attributes,
                yaml.load(attributes))
