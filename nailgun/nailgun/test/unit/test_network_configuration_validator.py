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

from nailgun.api.v1.validators.network import NetworkConfigurationValidator
from nailgun.errors import errors
from nailgun.test import base


class TestNetworkConfigurationValidatorProtocol(base.BaseValidatorTest):
    validator = NetworkConfigurationValidator.validate_networks_update

    def setUp(self):
        super(TestNetworkConfigurationValidatorProtocol, self).setUp()
        self.network_config = {
            "networks": [
                {
                    "cidr": "172.16.0.0/24",
                    "gateway": "172.16.0.1",
                    "group_id": 1,
                    "id": 2,
                    "ip_ranges": [["172.16.0.2", "172.16.0.126"]],
                    "meta": {
                        "name": "public",
                        "cidr": "172.16.0.0/24",
                        "gateway": "172.16.0.1",
                        "ip_range": ["172.16.0.2", "172.16.0.126"],
                        "vlan_start": None,
                        "use_gateway": True,
                        "notation": "ip_ranges",
                        "render_type": None,
                        "map_priority": 1,
                        "configurable": True,
                        "floating_range_var": "floating_ranges",
                        "ext_net_data": [],
                        "vips": ["haproxy", "vrouter"]
                    },

                    "name": "public",
                    "vlan_start": None}
            ]
        }

    def test_ok(self):
        dumped = jsonutils.dumps(self.network_config)
        self.validator(dumped)

    def test_required_property_networks(self):
        self.network_config['test_key'] = self.network_config.pop('networks')
        self.assertRaisesRequiredProperty(self.network_config, 'networks')

    def test_networks_invalid_type(self):
        self.network_config['networks'] = {}
        self.assertRaisesInvalidType(self.network_config, {}, 'array')

    def test_networks_additional_property(self):
        self.network_config['networks'][0]['test_key'] = 1
        self.assertRaisesAdditionalProperty(self.network_config, 'test_key')

    def test_networks_required_property_network_id(self):
        self.network_config['networks'][0].pop('id')
        self.assertRaisesRequiredProperty(self.network_config, 'id')

    def test_networks_invalid_type_id(self):
        self.network_config['networks'][0]['id'] = {}
        self.assertRaisesInvalidType(self.network_config, {}, 'integer')

    def test_networks_invalid_type_group_id(self):
        self.network_config['networks'][0]['group_id'] = {}
        self.assertRaisesInvalidType(self.network_config, {}, 'integer')

    def test_networks_invalid_type_name(self):
        self.network_config['networks'][0]['name'] = {}
        self.assertRaisesInvalidType(self.network_config, {}, 'string')

    def test_networks_invalid_type_gateway(self):
        self.network_config['networks'][0]['gateway'] = {}
        self.assertRaisesInvalidAnyOf(self.network_config, {})

    def test_networks_invalid_type_cidr(self):
        self.network_config['networks'][0]['cidr'] = {}
        self.assertRaisesInvalidAnyOf(self.network_config, {})

    def test_networks_invalid_type_vlan_start(self):
        self.network_config['networks'][0]['vlan_start'] = {}
        self.assertRaisesInvalidAnyOf(self.network_config, {})

    def test_networks_invalid_type_ip_ranges(self):
        self.network_config['networks'][0]['ip_ranges'] = {}
        self.assertRaisesInvalidType(self.network_config, {}, 'array')

    # networks.meta
    def test_networks_meta_invalid_type(self):
        self.network_config['networks'][0]['meta'] = []
        self.assertRaisesInvalidType(self.network_config, [], 'object')

    def test_networks_meta_additional_property(self):
        self.network_config['networks'][0]['meta']['test_key'] = 1
        self.assertRaisesAdditionalProperty(self.network_config, 'test_key')

    def test_networks_meta_invalid_type_name(self):
        self.network_config['networks'][0]['meta']['name'] = {}
        self.assertRaisesInvalidType(self.network_config, {}, 'string')

    def test_networks_meta_invalid_type_ip_range(self):
        self.network_config['networks'][0]['meta']['ip_range'] = {}
        self.assertRaisesInvalidType(self.network_config, {}, 'array')

    def test_networks_meta_invalid_type_vlan_start(self):
        self.network_config['networks'][0]['meta']['vlan_start'] = {}
        self.assertRaisesInvalidAnyOf(self.network_config, {})

    def test_networks_meta_invalid_type_use_gateway(self):
        self.network_config['networks'][0]['meta']['use_gateway'] = {}
        self.assertRaisesInvalidType(self.network_config, {}, 'boolean')

    def test_networks_invalid_type_notation(self):
        self.network_config['networks'][0]['meta']['notation'] = {}
        self.assertRaisesInvalidType(self.network_config, {}, 'string', 'null')

    def test_networks_invalid_type_render_type(self):
        self.network_config['networks'][0]['meta']['render_type'] = {}
        self.assertRaisesInvalidType(self.network_config, {}, 'string', 'null')

    def test_networks_invalid_type_render_addr_mask(self):
        self.network_config['networks'][0]['meta']['render_addr_mask'] = {}
        self.assertRaisesInvalidType(self.network_config, {}, 'string', 'null')

    def test_networks_invalid_type_unmovable(self):
        self.network_config['networks'][0]['meta']['unmovable'] = {}
        self.assertRaisesInvalidType(self.network_config, {}, 'boolean', 'null')

    def test_networks_meta_invalid_type_map_priority(self):
        self.network_config['networks'][0]['meta']['map_priority'] = {}
        self.assertRaisesInvalidType(self.network_config, {}, 'integer')

    def test_networks_meta_invalid_type_configurable(self):
        self.network_config['networks'][0]['meta']['configurable'] = {}
        self.assertRaisesInvalidType(self.network_config, {}, 'boolean')

    def test_networks_meta_invalid_type_floating_range_var(self):
        self.network_config['networks'][0]['meta']['floating_range_var'] = {}
        self.assertRaisesInvalidType(self.network_config, {}, 'string')

    def test_networks_meta_invalid_type_ext_net_data(self):
        self.network_config['networks'][0]['meta']['ext_net_data'] = {}
        self.assertRaisesInvalidType(self.network_config, {}, 'array')


class TestNetworkConfigurationValidator(base.BaseIntegrationTest):

    def setUp(self):
        super(TestNetworkConfigurationValidator, self).setUp()

        cluster = self.env.create(
            cluster_kwargs={
                "api": False,
                "net_provider": "neutron"
            },
            nodes_kwargs=[
                {"api": False,
                 "pending_addition": True},
            ]
        )

        self.config = self.env.neutron_networks_get(cluster.id).json_body
        self.validator = NetworkConfigurationValidator

    def get_config(self):
        return jsonutils.dumps(self.config)

    def find_net_by_name(self, name):
        for net in self.config['networks']:
            if net['name'] == name:
                return net

    def assertRaisesInvalidData(self, message):
        with self.assertRaises(errors.InvalidData) as context:
            self.validator.validate_networks_update(self.get_config())
        self.assertIn(message, context.exception.message)

    def assertNotRaisesInvalidData(self):
        self.assertNotRaises(
            errors.InvalidData,
            self.validator.validate_networks_update,
            self.get_config())

    def test_validate_network_notation(self):
        mgmt = self.find_net_by_name('management')
        mgmt['meta']['notation'] = 'notation'
        self.assertRaisesInvalidData(
            "Invalid notation 'notation' was specified for network")

    def test_validate_network_cidr(self):
        mgmt = self.find_net_by_name('management')
        mgmt['cidr'] = 'a.b.c.d'
        mgmt['meta']['notation'] = 'cidr'
        self.assertRaisesInvalidData(
            "Invalid CIDR 'a.b.c.d' was specified for network "
            "{0}".format(mgmt['id']))

        mgmt['meta']['notation'] = 'ip_ranges'
        self.assertRaisesInvalidData(
            "Invalid CIDR 'a.b.c.d' was specified for network "
            "{0}".format(mgmt['id']))

    def test_validate_network_no_cidr(self):
        mgmt = self.find_net_by_name('management')
        mgmt['cidr'] = None
        mgmt['meta']['notation'] = 'cidr'
        self.assertRaisesInvalidData(
            "Invalid CIDR 'None' was specified for network "
            "{0}".format(mgmt['id']))

        mgmt['meta']['notation'] = None
        self.assertRaisesInvalidData(
            "Invalid CIDR 'None' was specified for network "
            "{0}".format(mgmt['id']))

    def test_validate_network_no_cidr_no_notation(self):
        mgmt = self.find_net_by_name('management')
        mgmt['meta'].pop('notation')
        mgmt['meta'].pop('cidr')
        self.assertNotRaisesInvalidData()

    def test_validate_network_ip_ranges(self):
        mgmt = self.find_net_by_name('management')
        mgmt['meta']['notation'] = 'ip_ranges'
        mgmt['ip_ranges'] = None
        self.assertRaisesInvalidData(
            "Invalid IP ranges 'None' were specified for network "
            "{0}".format(mgmt['id']))

        mgmt['ip_ranges'] = ['1.1.1.11']
        self.assertRaisesInvalidData(
            "Invalid IP ranges '['1.1.1.11']' were specified for network "
            "{0}".format(mgmt['id']))

        mgmt['ip_ranges'] = ['1.1.1.11', '1.1.1.22']
        self.assertRaisesInvalidData(
            "Invalid IP ranges '['1.1.1.11', '1.1.1.22']' were specified "
            "for network {0}".format(mgmt['id']))

        mgmt['ip_ranges'] = [['1.1.1.11', '1.1.1.']]
        self.assertRaisesInvalidData(
            "Invalid IP ranges '[['1.1.1.11', '1.1.1.']]' were specified "
            "for network {0}".format(mgmt['id']))
