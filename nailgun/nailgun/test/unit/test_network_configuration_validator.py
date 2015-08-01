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

import mock
from oslo_serialization import jsonutils

from nailgun.api.v1.validators.network import NetworkConfigurationValidator
from nailgun.errors import errors
from nailgun.test import base


class TestNetworkConfigurationValidatorProtocol(base.BaseValidatorTest):
    validator = NetworkConfigurationValidator.validate_networks_update

    def setUp(self):
        super(TestNetworkConfigurationValidatorProtocol, self).setUp()
        self.nc = {
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

    @mock.patch('nailgun.api.v1.validators.network.db')
    def test_ok(self, _):
        dumped = jsonutils.dumps(self.nc)
        self.validator(dumped)

    # networks
    def test_required_property_networks(self):
        self.nc['test_key'] = self.nc.pop('networks')
        self.assertRaisesRequiredProperty(self.nc, 'networks')

    def test_networks_invalid_type(self):
        self.nc['networks'] = {}
        self.assertRaisesInvalidType(self.nc, "{}", "'array'")

    def test_networks_additional_property(self):
        self.nc['networks'][0]['test_key'] = 1
        self.assertRaisesAdditionalProperty(self.nc, 'test_key')

    def test_networks_required_property_network_id(self):
        self.nc['networks'][0].pop('id')
        self.assertRaisesRequiredProperty(self.nc, 'id')

    def test_networks_invalid_type_id(self):
        self.nc['networks'][0]['id'] = {}
        self.assertRaisesInvalidType(self.nc, "{}", "'integer'")

    def test_networks_invalid_type_group_id(self):
        self.nc['networks'][0]['group_id'] = 'x'
        self.assertRaisesInvalidAnyOf(self.nc, "u'x'")

    def test_networks_invalid_type_name(self):
        self.nc['networks'][0]['name'] = {}
        self.assertRaisesInvalidType(self.nc, "{}", "'string'")

    def test_networks_invalid_type_gateway(self):
        self.nc['networks'][0]['gateway'] = []
        self.assertRaisesInvalidAnyOf(self.nc, [])

    def test_networks_invalid_type_cidr(self):
        self.nc['networks'][0]['cidr'] = 1
        self.assertRaisesInvalidAnyOf(self.nc, 1)

    def test_networks_invalid_type_vlan_start(self):
        self.nc['networks'][0]['vlan_start'] = {}
        self.assertRaisesInvalidAnyOf(self.nc, {})

    def test_networks_invalid_type_ip_ranges(self):
        self.nc['networks'][0]['ip_ranges'] = {}
        self.assertRaisesInvalidType(self.nc, "{}", "'array'")

    # networks.meta
    def test_networks_meta_invalid_type(self):
        self.nc['networks'][0]['meta'] = []
        self.assertRaisesInvalidType(self.nc, "[]", "'object'")

    def test_networks_meta_additional_property(self):
        self.nc['networks'][0]['meta']['test_key'] = 1
        self.assertRaisesAdditionalProperty(self.nc, 'test_key')

    def test_networks_meta_invalid_type_name(self):
        self.nc['networks'][0]['meta']['name'] = {}
        self.assertRaisesInvalidType(self.nc, "{}", "'string'")

    def test_networks_meta_invalid_type_gateway(self):
        self.nc['networks'][0]['meta']['gateway'] = {}
        self.assertRaisesInvalidAnyOf(self.nc, {})

    def test_networks_meta_invalid_type_cidr(self):
        self.nc['networks'][0]['meta']['cidr'] = {}
        self.assertRaisesInvalidAnyOf(self.nc, {})

    # networks.meta.ip_range
    def test_networks_meta_ip_range(self):
        self.nc['networks'][0]['meta']['ip_range'] = {}
        self.assertRaisesInvalidType(self.nc, "{}", "'array'")

        self.nc['networks'][0]['meta']['ip_range'] = [1, 2]
        self.assertRaisesInvalidType(self.nc, "1", "'string'")

        self.nc['networks'][0]['meta']['ip_range'] = \
            ["1.1.1.1", "1.1.1.2", "1.1.1.3"]
        self.assertRaisesTooLong(
            self.nc,
            "[u'1.1.1.1', u'1.1.1.2', u'1.1.1.3']")

        self.nc['networks'][0]['meta']['ip_range'] = ["1.1.1.1"]
        self.assertRaisesTooShort(self.nc, "[u'1.1.1.1']")

        self.nc['networks'][0]['meta']['ip_range'] = [1, 1]
        self.assertRaisesNonUnique(self.nc, "[1, 1]")

        self.nc['networks'][0]['meta']['ip_range'] = ["1.1.1.1", "1.2.3.x"]
        self.assertRaisesInvalidAnyOf(self.nc, "u'1.2.3.x'")

    def test_networks_meta_invalid_type_vlan_start(self):
        self.nc['networks'][0]['meta']['vlan_start'] = {}
        self.assertRaisesInvalidAnyOf(self.nc, {})

    def test_networks_meta_invalid_type_seg_type(self):
        self.nc['networks'][0]['meta']['seg_type'] = 'x'
        self.assertRaisesInvalidEnum(self.nc, "u'x'", "['vlan', 'gre']")

    def test_networks_invalid_type_neutron_vlan_range(self):
        self.nc['networks'][0]['meta']['neutron_vlan_range'] = 'z'
        self.assertRaisesInvalidType(self.nc, "u'z'", "'boolean', 'null'")

    def test_networks_meta_invalid_type_use_gateway(self):
        self.nc['networks'][0]['meta']['use_gateway'] = {}
        self.assertRaisesInvalidType(self.nc, "{}", "'boolean'")

    def test_networks_invalid_type_notation(self):
        self.nc['networks'][0]['meta']['notation'] = 'x'
        self.assertRaisesInvalidEnum(
            self.nc, "u'x'", "['cidr', 'ip_ranges', None]")

    def test_networks_invalid_type_render_type(self):
        self.nc['networks'][0]['meta']['render_type'] = 1
        self.assertRaisesInvalidType(self.nc, "1", "'string', 'null'")

    def test_networks_invalid_type_render_addr_mask(self):
        self.nc['networks'][0]['meta']['render_addr_mask'] = []
        self.assertRaisesInvalidType(self.nc, "[]", "'string', 'null'")

    def test_networks_invalid_type_unmovable(self):
        self.nc['networks'][0]['meta']['unmovable'] = 5
        self.assertRaisesInvalidType(self.nc, "5", "'boolean', 'null'")

    def test_networks_meta_invalid_type_map_priority(self):
        self.nc['networks'][0]['meta']['map_priority'] = {}
        self.assertRaisesInvalidType(self.nc, "{}", "'integer'")

    def test_networks_meta_invalid_type_configurable(self):
        self.nc['networks'][0]['meta']['configurable'] = 'hello'
        self.assertRaisesInvalidType(self.nc, "u'hello'", "'boolean'")

    def test_networks_meta_invalid_type_floating_range_var(self):
        self.nc['networks'][0]['meta']['floating_range_var'] = {}
        self.assertRaisesInvalidType(self.nc, "{}", "'string'")

    def test_networks_meta_invalid_type_ext_net_data(self):
        self.nc['networks'][0]['meta']['ext_net_data'] = {}
        self.assertRaisesInvalidType(self.nc, "{}", "'array'")

    # networks.meta.vips
    def test_networks_meta_vips(self):
        self.nc['networks'][0]['meta']['vips'] = {}
        self.assertRaisesInvalidType(self.nc, "{}", "'array'")

        self.nc['networks'][0]['meta']['vips'] = [1]
        self.assertRaisesInvalidType(self.nc, "1", "'string'")

        self.nc['networks'][0]['meta']['vips'] = [1, 1]
        self.assertRaisesNonUnique(self.nc, "[1, 1]")

        self.nc['networks'][0]['meta']['vips'] = ["a", "b", "c1"]
        self.assertRaisesNotMatchPattern(self.nc, "u'c1'")


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

    def test_validate_network_no_cidr(self):
        mgmt = self.find_net_by_name('management')
        mgmt['meta']['notation'] = 'cidr'
        mgmt['cidr'] = None
        self.assertRaisesInvalidData(
            "No CIDR was specified for network {0}".format(mgmt['id']))
