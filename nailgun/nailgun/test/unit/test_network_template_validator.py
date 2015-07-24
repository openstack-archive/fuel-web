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

from copy import deepcopy

from oslo_serialization import jsonutils

from nailgun.api.v1.validators.network import NetworkTemplateValidator
from nailgun.errors import errors
from nailgun.test.base import BaseTestCase


class TestNetworkTemplateValidator(BaseTestCase):
    def test_no_key_adv_net_template(self):
        network_template = jsonutils.dumps({"adv_net_template": {}})

        with self.assertRaises(errors.InvalidData) as context:
            NetworkTemplateValidator.validate(network_template)

        self.assertEqual(
            context.exception.message, "No node groups are defined")

    def test_no_defined_templates(self):
        network_template = jsonutils.dumps({
            "adv_net_template": {
                "node_group_1": {
                    "nic_mapping": {"default": {}},
                    "templates_for_node_role": {},
                    "network_assignments": {},
                    "network_scheme": {}
                }
            }
        })

        with self.assertRaises(errors.InvalidData) as context:
            NetworkTemplateValidator.validate(network_template)

        self.assertEqual(
            context.exception.message,
            "No templates are defined for node group node_group_1")

    def test_templates_not_found(self):
        network_template = jsonutils.dumps({
            "adv_net_template": {
                "node_group_1": {
                    "nic_mapping": {"default": {}},
                    "templates_for_node_role": {
                        "controller": ["public", "common"]
                    },
                    "network_assignments": {},
                    "network_scheme": {}
                }
            }
        })

        with self.assertRaises(errors.InvalidData) as context:
            NetworkTemplateValidator.validate(network_template)

        self.assertEqual(
            context.exception.message,
            "Requested templates public, common were "
            "not found for node group node_group_1")


class TestNetworkTemplateSchemaValidation(BaseTestCase):
    _NETWORK_TEMPLATE = {
        "adv_net_template": {
            "node_group_1": {
                "nic_mapping": {"default": {}},
                "templates_for_node_role": {
                    "controller": ["public", "common"]
                },
                "network_assignments": {},
                "network_scheme": {
                    "public": {
                        "transformations": [],
                        "endpoints": [],
                        "roles": {}
                    },
                    "common": {
                        "transformations": [],
                        "endpoints": [],
                        "roles": {}
                    }
                }
            },
        }
    }

    def get_network_template(self):
        return deepcopy(self._NETWORK_TEMPLATE)

    def _get_invalid_data_context(self, network_template):
        network_template_dumped = jsonutils.dumps(network_template)

        with self.assertRaises(errors.InvalidData) as context:
            NetworkTemplateValidator.validate(network_template_dumped)

        return context

    def assertRaisesUnexpectedKey(self, network_template, key='test_key'):
        context = self._get_invalid_data_context(network_template)

        self.assertIn(
            "Additional properties are not allowed",
            context.exception.message)

        self.assertIn(
            "'{0}' was unexpected".format(key),
            context.exception.message)

    def assertRaisesInvalidType(self, network_template, expected_type):
        context = self._get_invalid_data_context(network_template)
        self.assertIn(
            "Failed validating 'type' in schema",
            context.exception.message)

        self.assertIn(
            "is not of type '{0}'".format(expected_type),
            context.exception.message)

    def test_ok(self):
        network_template = jsonutils.dumps(self.get_network_template())
        NetworkTemplateValidator.validate(network_template)

    def test_network_scheme(self):
        nt = self.get_network_template()
        nt['adv_net_template']['node_group_1']['network_scheme'][
            'public'].update({'test_key': {}})
        self.assertRaisesUnexpectedKey(nt)

        nt = self.get_network_template()
        nt['adv_net_template']['node_group_1']['network_scheme'][
            'public'].update({'transformations': {}})
        self.assertRaisesInvalidType(nt, 'array')

        nt = self.get_network_template()
        nt['adv_net_template']['node_group_1']['network_scheme'][
            'public'].update({'endpoints': {}})
        self.assertRaisesInvalidType(nt, 'array')

        nt = self.get_network_template()
        nt['adv_net_template']['node_group_1']['network_scheme'][
            'public'].update({'roles': 1})
        self.assertRaisesInvalidType(nt, 'object')
