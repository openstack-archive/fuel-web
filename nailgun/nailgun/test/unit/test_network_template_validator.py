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
from nailgun.errors import errors
from nailgun.test.base import BaseTestCase


class TestNetworkTemplateValidator(BaseTestCase):
    def test_ok(self):
        network_template = jsonutils.dumps({
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
        })

        NetworkTemplateValidator.validate(network_template)

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
