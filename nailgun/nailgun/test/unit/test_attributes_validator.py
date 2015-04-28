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
              weight: 3
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
