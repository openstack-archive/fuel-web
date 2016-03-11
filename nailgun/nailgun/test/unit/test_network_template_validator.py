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
from nailgun.test import base


class BaseNetworkTemplateValidatorTest(base.BaseValidatorUnitTest):
    validator = NetworkTemplateValidator.validate

    def setUp(self):
        self.nt = {
            "adv_net_template": {
                "node_group_1": {
                    "nic_mapping": {"default": {}},
                    "templates_for_node_role": {
                        "controller": ["public", "common"]
                    },
                    "network_assignments": {
                        "public": {"ep": "br-mgmt"}
                    },
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


class TestNetworkTemplateValidator(BaseNetworkTemplateValidatorTest):
    def test_ok(self):
        dumped = jsonutils.dumps(self.nt)
        self.validator(dumped)

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
        self.assertIn(
            context.exception.message,
            ["Requested templates public, common were "
             "not found for node group node_group_1",
             "Requested templates common, public were "
             "not found for node group node_group_1"])


class TestNetworkTemplateValidatorProtocol(BaseNetworkTemplateValidatorTest):
    def test_network_scheme_required_property_transformations(self):
        self.nt['adv_net_template']['node_group_1']['network_scheme'][
            'public'].pop('transformations')
        self.assertRaisesRequiredProperty(self.nt, 'transformations')

    def test_network_scheme_required_property_endpoints(self):
        self.nt['adv_net_template']['node_group_1']['network_scheme'][
            'public'].pop('endpoints')
        self.assertRaisesRequiredProperty(self.nt, 'endpoints')

    def test_network_scheme_required_property_roles(self):
        self.nt['adv_net_template']['node_group_1']['network_scheme'][
            'public'].pop('roles')
        self.assertRaisesRequiredProperty(self.nt, 'roles')

    def test_network_scheme_additional_property(self):
        self.nt['adv_net_template']['node_group_1']['network_scheme'][
            'public'].update({'test_key': {}})
        self.assertRaisesAdditionalProperty(self.nt, 'test_key')

    def test_network_scheme_transformations_invalid_type(self):
        self.nt['adv_net_template']['node_group_1']['network_scheme'][
            'public'].update({'transformations': {}})
        self.assertRaisesInvalidType(self.nt, "{}", "'array'")

    def test_network_scheme_endpoints_invalid_type(self):
        self.nt['adv_net_template']['node_group_1']['network_scheme'][
            'public'].update({'endpoints': {}})
        self.assertRaisesInvalidType(self.nt, "{}", "'array'")

    def test_network_scheme_roles_invalid_type(self):
        self.nt['adv_net_template']['node_group_1']['network_scheme'][
            'public']['roles'] = 1
        self.assertRaisesInvalidType(self.nt, 1, "'object'")

    def test_network_scheme_invalid_type(self):
        self.nt['adv_net_template']['node_group_1']['network_scheme'] = 1
        self.assertRaisesInvalidType(self.nt, 1, "'object'")

    def test_nic_mapping_invalid_type(self):
        self.nt['adv_net_template']['node_group_1']['nic_mapping'] = 1
        self.assertRaisesInvalidType(self.nt, 1, "'object'")

    def test_templates_list_invalid_type(self):
        self.nt['adv_net_template']['node_group_1'][
            'templates_for_node_role'] = 1
        self.assertRaisesInvalidType(self.nt, 1, "'object'")

    def test_templates_list_invalid_type_in_values(self):
        self.nt['adv_net_template']['node_group_1'][
            'templates_for_node_role'] = {"anything": [1]}
        self.assertRaisesInvalidType(self.nt, 1, "'string'")

    def test_network_assignments_invalid_type(self):
        self.nt['adv_net_template']['node_group_1']['network_assignments'] = 1
        self.assertRaisesInvalidType(self.nt, 1, "'object'")

    def test_network_assignments_required_property_ep(self):
        self.nt['adv_net_template']['node_group_1']['network_assignments'][
            'test_key'] = {}
        self.assertRaisesRequiredProperty(self.nt, 'ep')

    def test_network_assignments_additional_property(self):
        self.nt['adv_net_template']['node_group_1']['network_assignments'][
            'public']['test_key'] = {}
        self.assertRaisesAdditionalProperty(self.nt, 'test_key')

    def test_node_group_required_property_nic_mapping(self):
        self.nt['adv_net_template']['node_group_1'].pop('nic_mapping')
        self.assertRaisesRequiredProperty(self.nt, 'nic_mapping')

    def test_node_group_required_property_templates_for_node_role(self):
        self.nt['adv_net_template']['node_group_1'].pop(
            'templates_for_node_role')
        self.assertRaisesRequiredProperty(self.nt, 'templates_for_node_role')

    def test_node_group_required_property_network_assignments(self):
        self.nt['adv_net_template']['node_group_1'].pop('network_assignments')
        self.assertRaisesRequiredProperty(self.nt, 'network_assignments')

    def test_node_group_required_property_network_scheme(self):
        self.nt['adv_net_template']['node_group_1'].pop('network_scheme')
        self.assertRaisesRequiredProperty(self.nt, 'network_scheme')

    def test_node_group_additional_property(self):
        self.nt['adv_net_template']['node_group_1']['test_key'] = {}
        self.assertRaisesAdditionalProperty(self.nt, 'test_key')

    def test_node_group_invalid_type(self):
        self.nt['adv_net_template']['node_group_1']['network_assignments'] = 1
        self.assertRaisesInvalidType(self.nt, 1, "'object'")

    def test_node_group_invalid_type_templates_for_node_role(self):
        self.nt['adv_net_template']['node_group_1'][
            'templates_for_node_role'] = 1
        self.assertRaisesInvalidType(self.nt, 1, "'object'")
