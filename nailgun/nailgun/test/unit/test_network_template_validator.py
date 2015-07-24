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

from oslo_serialization import jsonutils

from nailgun.api.v1.validators.network import NetworkTemplateValidator
from nailgun.test.base import BaseValidatorTest


class TestNetworkTemplateValidator(BaseValidatorTest):
    validator = NetworkTemplateValidator

    def setUp(self):
        super(BaseValidatorTest, self).setUp()
        self.nt = {
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

    def test_ok(self):
        dumped = jsonutils.dumps(self.nt)
        self.validator.validate(dumped)

    def test_no_key_adv_net_template(self):
        context = self.get_invalid_data_context({"adv_net_template": {}})
        self.assertEqual(
            context.exception.message, "No node groups are defined")

    def test_no_defined_templates(self):
        self.nt['adv_net_template']['node_group_1']['network_scheme'] = {}
        self.nt['adv_net_template']['node_group_1'][
            'templates_for_node_role'] = {}
        context = self.get_invalid_data_context(self.nt)
        self.assertEqual(
            context.exception.message,
            "No templates are defined for node group node_group_1")

    def test_templates_not_found(self):
        self.nt['adv_net_template']['node_group_1']['network_scheme'] = {}
        context = self.get_invalid_data_context(self.nt)
        self.assertEqual(
            context.exception.message,
            "Requested templates public, common were "
            "not found for node group node_group_1")

    def test_network_scheme_additional_property(self):
        self.nt['adv_net_template']['node_group_1']['network_scheme'][
            'public'].update({'test_key': {}})
        self.assertRaisesAdditionalProperty(self.nt, 'test_key')

    def test_network_scheme_transformations_invalid_type(self):
        self.nt['adv_net_template']['node_group_1']['network_scheme'][
            'public'].update({'transformations': {}})
        self.assertRaisesInvalidType(self.nt, {}, 'array')

    def test_network_scheme_endpoints_invalid_type(self):
        self.nt['adv_net_template']['node_group_1']['network_scheme'][
            'public'].update({'endpoints': {}})
        self.assertRaisesInvalidType(self.nt, {}, 'array')

    def test_network_scheme_roles_invalid_type(self):
        self.nt['adv_net_template']['node_group_1']['network_scheme'][
            'public'].update({'roles': 1})
        self.assertRaisesInvalidType(self.nt, 1, 'object')

    def test_network_scheme_invalid_type(self):
        self.nt['adv_net_template']['node_group_1']['network_scheme'] = 1
        self.assertRaisesInvalidType(self.nt, 1, 'object')

    def test_nic_mapping(self):
        self.nt['adv_net_template']['node_group_1']['nic_mapping'] = 1
        self.assertRaisesInvalidType(self.nt, 1, 'object')

    def test_templates_list_invalid_type(self):
        self.nt['adv_net_template']['node_group_1'][
            'templates_for_node_role'] = 1
        self.assertRaisesInvalidType(self.nt, 1, 'object')

    def test_templates_list_invalid_type_in_list(self):
        self.nt['adv_net_template']['node_group_1'][
            'templates_for_node_role'] = {"anything": [1]}
        self.assertRaisesInvalidType(self.nt, 1, 'string')
