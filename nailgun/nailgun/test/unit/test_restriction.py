# -*- coding: utf-8 -*-

#    Copyright 2015 Mirantis, Inc.
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

import six
import yaml

from nailgun import errors
from nailgun import objects
from nailgun.test import base
from nailgun.utils.restrictions import AttributesRestriction
from nailgun.utils.restrictions import ComponentsRestrictions
from nailgun.utils.restrictions import LimitsMixin
from nailgun.utils.restrictions import RestrictionBase


DATA = """
    attributes:
      group:
        attribute_1:
          name: attribute_1
          value: true
          restrictions:
            - condition: 'settings:group.attribute_2.value == true'
              message: 'Only one of attributes 1 and 2 allowed'
            - condition: 'settings:group.attribute_3.value == "spam"'
              message: 'Only one of attributes 1 and 3 allowed'
        attribute_2:
          name: attribute_2
          value: true
        attribute_3:
          name: attribute_3
          value: spam
          restrictions:
            - condition: 'settings:group.attribute_3.value ==
                settings:group.attribute_4.value'
              message: 'Only one of attributes 3 and 4 allowed'
              action: enable
        attribute_4:
          name: attribute_4
          value: spam
        attribute_5:
          name: attribute_5
          value: 4
    roles_meta:
      cinder:
        limits:
          min: 1
          overrides:
            - condition: 'settings:group.attribute_2.value == true'
              message: 'At most one role_1 node can be added'
              max: 1
      controller:
        limits:
          recommended: 'settings:group.attribute_5.value'
      mongo:
        limits:
          max: 12
          message: 'At most 12 MongoDB node should be added'
          overrides:
            - condition: 'settings:group.attribute_3.value == "spam"'
              min: 4
              message: 'At least 4 MongoDB node can be added if spam'
            - condition: 'settings:group.attribute_3.value == "egg"'
              recommended: 3
              message: "At least 3 MongoDB nodes are recommended"
"""


class TestRestriction(base.BaseTestCase):

    def setUp(self):
        super(TestRestriction, self).setUp()
        self.data = yaml.load(DATA)

    def test_check_restrictions(self):
        attributes = self.data.get('attributes')

        for gkey, gvalue in six.iteritems(attributes):
            for key, value in six.iteritems(gvalue):
                result = RestrictionBase.check_restrictions(
                    models={'settings': attributes},
                    restrictions=value.get('restrictions', []))
                # check when couple restrictions true for some item
                if key == 'attribute_1':
                    self.assertTrue(result.get('result'))
                    self.assertEqual(
                        result.get('message'),
                        'Only one of attributes 1 and 2 allowed. ' +
                        'Only one of attributes 1 and 3 allowed')
                # check when different values uses in restriction
                if key == 'attribute_3':
                    self.assertTrue(result.get('result'))
                    self.assertEqual(
                        result.get('message'),
                        'Only one of attributes 3 and 4 allowed')

    def test_expand_restriction_format(self):
        string_restriction = 'settings.some_attribute.value != true'
        dict_restriction_long_format = {
            'condition': 'settings.some_attribute.value != true',
            'message': 'Another attribute required'
        }
        dict_restriction_short_format = {
            'settings.some_attribute.value != true':
            'Another attribute required'
        }
        result = {
            'action': 'disable',
            'condition': 'settings.some_attribute.value != true',
        }
        invalid_format = ['some_condition']

        # check string format
        self.assertDictEqual(
            RestrictionBase._expand_restriction(
                string_restriction), result)
        result['message'] = 'Another attribute required'
        # check long format
        self.assertDictEqual(
            RestrictionBase._expand_restriction(
                dict_restriction_long_format), result)
        # check short format
        self.assertDictEqual(
            RestrictionBase._expand_restriction(
                dict_restriction_short_format), result)
        # check invalid format
        self.assertRaises(
            errors.InvalidData,
            RestrictionBase._expand_restriction,
            invalid_format)


class TestLimits(base.BaseTestCase):
    def setUp(self):
        super(TestLimits, self).setUp()
        self.data = yaml.load(DATA)
        self.env.create(
            nodes_kwargs=[
                {"status": "ready", "roles": ["cinder"]},
                {"status": "ready", "roles": ["controller"]},
                {"status": "ready", "roles": ["mongo"]},
                {"status": "ready", "roles": ["mongo"]},
            ]
        )

    def test_check_node_limits(self):
        roles = self.data.get('roles_meta')
        attributes = self.data.get('attributes')

        for role, data in six.iteritems(roles):
            result = LimitsMixin().check_node_limits(
                models={'settings': attributes},
                nodes=self.env.nodes,
                role=role,
                limits=data.get('limits'))

            if role == 'cinder':
                self.assertTrue(result.get('valid'))

            if role == 'controller':
                self.assertFalse(result.get('valid'))
                self.assertEqual(
                    result.get('messages'),
                    'Default message')

            if role == 'mongo':
                self.assertFalse(result.get('valid'))
                self.assertEqual(
                    result.get('messages'),
                    'At least 4 MongoDB node can be added if spam')

    def test_check_override(self):
        roles = self.data.get('roles_meta')
        attributes = self.data.get('attributes')

        limits = LimitsMixin()
        # Set nodes count to 4
        limits.count = 4
        limits.limit_reached = True
        limits.models = {'settings': attributes}
        limits.nodes = self.env.nodes
        # Set "cinder" role to working on
        limits.role = 'cinder'
        limits.limit_types = ['max']
        limits.checked_limit_types = {}
        limits.limit_values = {'max': None}
        override_data = roles['cinder']['limits']['overrides'][0]

        result = limits._check_override(override_data)
        self.assertEqual(
            result[0]['message'], 'At most one role_1 node can be added')

    def test_get_proper_message(self):
        limits = LimitsMixin()
        limits.messages = [
            {'type': 'min', 'value': '1', 'message': 'Message for min_1'},
            {'type': 'min', 'value': '2', 'message': 'Message for min_2'},
            {'type': 'max', 'value': '5', 'message': 'Message for max_5'},
            {'type': 'max', 'value': '8', 'message': 'Message for max_8'}
        ]

        self.assertEqual(
            limits._get_message('min'), 'Message for min_2')

        self.assertEqual(
            limits._get_message('max'), 'Message for max_5')


class TestAttributesRestriction(base.BaseTestCase):

    def setUp(self):
        super(TestAttributesRestriction, self).setUp()
        self.cluster = self.env.create(
            cluster_kwargs={
                'api': False
            }
        )
        attributes_metadata = """
            editable:
                access:
                  user:
                    value: ""
                    type: "text"
                    regex:
                      source: '\S'
                      error: "Invalid username"
                  email:
                    value: "admin@localhost"
                    type: "text"
                    regex:
                      source: '\S'
                      error: "Invalid email"
                  tenant:
                    value: [""]
                    type: "text_list"
                    regex:
                      source: '\S'
                      error: "Invalid tenant name"
                  another_tenant:
                    value: ["test"]
                    type: "text_list"
                    min: 2
                    max: 2
                    regex:
                      source: '\S'
                      error: "Invalid tenant name"
                  another_tenant_2:
                    value: ["test1", "test2", "test3"]
                    type: "text_list"
                    min: 2
                    max: 2
                    regex:
                      source: '\S'
                      error: "Invalid tenant name"
                  password:
                    value: "secret"
                    type: "password"
                    regex:
                      source: '\S'
                      error: "Empty password"
                  nullable_text:
                    label: "Nullable text"
                    value: null
                    nullable: True
                    type: "text"
                    regex:
                      source: '\S'
                      error: "Empty value"
                  not_nullable_text:
                    label: "Not nullable text"
                    value: null
                    type: "text"
                  nullable_number:
                    label: "Nullable number"
                    value: null
                    nullable: True
                    type: "number"
                  not_nullable_number:
                    label: "Not nullable number"
                    value: null
                    type: "number"
        """
        self.attributes_data = yaml.load(attributes_metadata)

    def test_check_with_invalid_values(self):
        objects.Cluster.update_attributes(
            self.cluster, self.attributes_data)
        attributes = objects.Cluster.get_editable_attributes(self.cluster)
        models = {
            'settings': attributes,
            'default': attributes,
        }

        errs = AttributesRestriction.check_data(models, attributes)
        self.assertItemsEqual(
            errs, ['Invalid username', ['Invalid tenant name'],
                   "Value ['test'] should have at least 2 items",
                   "Value ['test1', 'test2', 'test3'] "
                   "should not have more than 2 items",
                   "Null value is forbidden for 'Not nullable text'",
                   "Null value is forbidden for 'Not nullable number'"])

    def test_check_with_valid_values(self):
        access = self.attributes_data['editable']['access']
        access['user']['value'] = 'admin'
        access['tenant']['value'] = ['test']
        access['another_tenant']['value'] = ['test1', 'test2']
        access['another_tenant_2']['value'] = ['test1', 'test2']
        access['not_nullable_text']['value'] = 'test'
        access['not_nullable_number']['value'] = 123

        objects.Cluster.update_attributes(
            self.cluster, self.attributes_data)
        attributes = objects.Cluster.get_editable_attributes(self.cluster)
        models = {
            'settings': attributes,
            'default': attributes,
        }

        errs = AttributesRestriction.check_data(models, attributes)
        self.assertListEqual(errs, [])


class TestComponentsRestrictions(base.BaseTestCase):

    def setUp(self):
        super(TestComponentsRestrictions, self).setUp()
        self.required_components_types = ['hypervisor', 'network', 'storage']
        self.components_metadata = [
            {
                'name': 'hypervisor:test_hypervisor'
            },
            {
                'name': 'network:core:test_network_1',
                'incompatible': [
                    {'name': 'hypervisor:test_hypervisor'}
                ]
            },
            {
                'name': 'network:core:test_network_2'
            },
            {
                'name': 'network:ml2:test_network_3'
            },
            {
                'name': 'storage:test_storage',
                'compatible': [
                    {'name': 'hypervisor:test_hypervisor'}
                ],
                'requires': [
                    {'name': 'hypervisor:test_hypervisor'}
                ]
            },
            {
                'name': 'storage:test_storage_2'
            }
        ]

    def test_components_not_in_available_components(self):
        self._validate_with_expected_errors(
            ['storage:not_existing_component'],
            "['storage:not_existing_component'] components are not related to "
            "used release."
        )

    def test_not_all_required_types_components(self):
        selected_components_list = [
            'hypervisor:test_hypervisor',
            'network:core:test_network_2',
            'storage:test_storage_2'
        ]
        ComponentsRestrictions.validate_components(
            selected_components_list, self.components_metadata,
            self.required_components_types)

        while selected_components_list:
            selected_components_list.pop()
            self._validate_with_expected_errors(
                selected_components_list,
                "Components with {0} types are required but wasn't found "
                "in data.".format(sorted(
                    set(self.required_components_types) - set(
                        [x.split(':')[0] for x in selected_components_list])
                ))
            )

    def test_incompatible_components_found(self):
        self._validate_with_expected_errors(
            ['hypervisor:test_hypervisor', 'network:core:test_network_1'],
            "Incompatible components were found: 'network:core:test_network_1'"
            " incompatible with ['hypervisor:test_hypervisor']."
        )

    def test_requires_components_not_found(self):
        self._validate_with_expected_errors(
            ['storage:test_storage'],
            "Component 'storage:test_storage' requires any of components from "
            "['hypervisor:test_hypervisor'] set."
        )

    def test_requires_mixed_format(self):
        self.components_metadata.append({
            'name': 'storage:wrong_storage',
            'requires': [
                {'any_of': {
                    'items': ['network:core:*']
                }},
                {'name': 'hypervisor:test_hypervisor'}
            ]
        })
        self._validate_with_expected_errors(
            ['storage:wrong_storage'],
            "Component 'storage:wrong_storage' has mixed format of requires."
        )

    def test_requires_any_of_predicate(self):
        self.components_metadata.append({
            'name': 'additional_service:test_service',
            'requires': [
                {'any_of': {
                    'items': ['network:core:*']
                }},
                {'any_of': {
                    'items': [
                        'storage:test_storage_2', 'hypervisor:test_hypervisor'
                    ],
                }}
            ]
        })
        self._validate_with_expected_errors(
            ['additional_service:test_service', 'network:ml2:test_network_3'],
            "Requirements was not satisfied for component "
            "'additional_service:test_service': any_of(['network:core:*'])"
        )

        self._validate_with_expected_errors(
            ['additional_service:test_service', 'network:core:test_network_2'],
            "Requirements was not satisfied for component "
            "'additional_service:test_service': "
            "any_of(['hypervisor:test_hypervisor', 'storage:test_storage_2'])"
        )

        ComponentsRestrictions.validate_components(
            ['additional_service:test_service', 'network:core:test_network_2',
             'hypervisor:test_hypervisor', 'storage:test_storage_2'],
            self.components_metadata,
            self.required_components_types
        )

    def test_requires_one_of_predicate(self):
        self.components_metadata.append({
            'name': 'additional_service:test_service',
            'requires': [
                {'one_of': {
                    'items': ['network:core:*']
                }},
                {'one_of': {
                    'items': [
                        'storage:test_storage_2', 'hypervisor:test_hypervisor'
                    ]
                }}
            ]
        })
        selected_components_list = ['additional_service:test_service',
                                    'network:core:test_network_1',
                                    'network:core:test_network_2',
                                    'storage:test_storage_2']
        self._validate_with_expected_errors(
            selected_components_list,
            "Requirements was not satisfied for component "
            "'additional_service:test_service': one_of(['network:core:*'])"
        )

        self._validate_with_expected_errors(
            ['additional_service:test_service', 'network:core:test_network_1'],
            "Requirements was not satisfied for component "
            "'additional_service:test_service': "
            "one_of(['hypervisor:test_hypervisor', 'storage:test_storage_2'])"
        )

        ComponentsRestrictions.validate_components(
            ['additional_service:test_service', 'network:core:test_network_2',
             'hypervisor:test_hypervisor', 'storage:test_storage'],
            self.components_metadata,
            self.required_components_types
        )

    def test_requires_none_of_predicate(self):
        self.components_metadata.append({
            'name': 'additional_service:test_service',
            'requires': [{
                'none_of': {
                    'items': ['network:core:*', 'storage:test_storage']
                }
            }]
        })
        selected_components_list = ['additional_service:test_service',
                                    'network:core:test_network_1']
        self._validate_with_expected_errors(
            selected_components_list,
            "Requirements was not satisfied for component "
            "'additional_service:test_service': "
            "none_of(['network:core:*', 'storage:test_storage'])"
        )

        ComponentsRestrictions.validate_components(
            ['additional_service:test_service', 'network:ml2:test_network_3',
             'storage:test_storage_2', 'hypervisor:test_hypervisor'],
            self.components_metadata,
            self.required_components_types
        )

    def test_requires_all_of_predicate(self):
        self.components_metadata.append({
            'name': 'additional_service:test_service',
            'requires': [{
                'all_of': {
                    'items': [
                        'network:core:test_network_2',
                        'storage:*',
                        'hypervisor:test_hypervisor'
                    ]
                }
            }]
        })
        selected_components_list = ['additional_service:test_service',
                                    'network:core:test_network_2',
                                    'storage:test_storage_2',
                                    'hypervisor:test_hypervisor']

        self._validate_with_expected_errors(
            selected_components_list,
            "Requirements was not satisfied for component "
            "'additional_service:test_service': all_of(["
            "'hypervisor:test_hypervisor', 'network:core:test_network_2', "
            "'storage:*'])"
        )

        selected_components_list.append('storage:test_storage')
        ComponentsRestrictions.validate_components(
            selected_components_list, self.components_metadata,
            self.required_components_types)

    def _validate_with_expected_errors(self, components_list, error_msg):
        with self.assertRaises(errors.InvalidData) as exc_cm:
            ComponentsRestrictions.validate_components(
                components_list, self.components_metadata,
                self.required_components_types)
        self.assertEqual(exc_cm.exception.message, error_msg)
