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
from nailgun.api.v1.validators.network import \
    NeutronNetworkConfigurationValidator
from nailgun.api.v1.validators.network import NovaNetworkConfigurationValidator
from nailgun import consts
from nailgun.db.sqlalchemy.models import Cluster
from nailgun.db.sqlalchemy.models import NetworkGroup
from nailgun.db.sqlalchemy.models import NodeGroup
from nailgun.errors import errors
from nailgun.network.neutron import NeutronManager
from nailgun.test import base


class BaseNetworkConfigurationValidatorProtocolTest(base.BaseValidatorTest):

    def get_invalid_data_context(self, obj):
        """The method is used by assertRaises* methods of base class
           and should be overridden because by default it calls
           validator with only one argument.
        """
        with self.assertRaises(errors.InvalidData) as context:
            with mock.patch('nailgun.db.sqlalchemy.models.Cluster.is_locked',
                            new_callable=mock.PropertyMock,
                            return_value=False):
                cluster_mock = Cluster()
                self.validator(jsonutils.dumps(obj), cluster_mock)

        return context


class TestNetworkConfigurationValidatorProtocol(
    BaseNetworkConfigurationValidatorProtocolTest
):

    validator = NetworkConfigurationValidator.validate_networks_data

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
                        "name": consts.NETWORKS.public,
                        "cidr": "172.16.0.0/24",
                        "gateway": "172.16.0.1",
                        "ip_range": ["172.16.0.2", "172.16.0.126"],
                        "vlan_start": None,
                        "use_gateway": True,
                        "notation": consts.NETWORK_NOTATION.ip_ranges,
                        "render_type": None,
                        "map_priority": 1,
                        "configurable": True,
                        "floating_range_var": "floating_ranges",
                        "ext_net_data": [],
                        "vips": consts.NETWORK_VIP_TYPES,
                    },
                    "name": consts.NETWORKS.public,
                    "vlan_start": None
                }
            ]
        }

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
        self.assertRaisesInvalidAnyOf(
            self.nc,
            "'x'",
            "['networks'][0]['group_id']")

    def test_networks_invalid_type_gateway(self):
        self.nc['networks'][0]['gateway'] = []
        self.assertRaisesInvalidAnyOf(
            self.nc, [], "['networks'][0]['gateway']")

    def test_networks_invalid_type_cidr(self):
        self.nc['networks'][0]['cidr'] = 1
        self.assertRaisesInvalidAnyOf(self.nc, 1, "['networks'][0]['cidr']")

    def test_networks_invalid_type_vlan_start(self):
        self.nc['networks'][0]['vlan_start'] = {}
        self.assertRaisesInvalidAnyOf(
            self.nc, {}, "['networks'][0]['vlan_start']")

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
        self.assertRaisesInvalidAnyOf(
            self.nc, {}, "['networks'][0]['meta']['gateway']")

    def test_networks_meta_invalid_type_cidr(self):
        self.nc['networks'][0]['meta']['cidr'] = {}
        self.assertRaisesInvalidAnyOf(
            self.nc, {}, "['networks'][0]['meta']['cidr']")

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

        self.nc['networks'][0]['meta']['ip_range'] = ['1.2.3.4', '1.2.3.4']
        self.assertRaisesNonUnique(self.nc, "[u'1.2.3.4', u'1.2.3.4']")

        self.nc['networks'][0]['meta']['ip_range'] = ["1.1.1.1", "1.2.3.x"]
        self.assertRaisesInvalidAnyOf(
            self.nc, "'1.2.3.x'", "['networks'][0]['meta']['ip_range']")

    def test_networks_meta_invalid_type_vlan_start(self):
        self.nc['networks'][0]['meta']['vlan_start'] = {}
        self.assertRaisesInvalidAnyOf(
            self.nc, {}, "['networks'][0]['meta']['vlan_start']")

    def test_networks_meta_invalid_type_seg_type(self):
        self.nc['networks'][0]['meta']['seg_type'] = 'x'
        self.assertRaisesInvalidEnum(self.nc, "'x'", "['vlan', 'gre', 'tun']")

    def test_networks_invalid_type_neutron_vlan_range(self):
        self.nc['networks'][0]['meta']['neutron_vlan_range'] = 'z'
        self.assertRaisesInvalidType(self.nc, "'z'", "'boolean'")

    def test_networks_meta_invalid_type_use_gateway(self):
        self.nc['networks'][0]['meta']['use_gateway'] = {}
        self.assertRaisesInvalidType(self.nc, "{}", "'boolean'")

    def test_networks_invalid_type_notation(self):
        self.nc['networks'][0]['meta']['notation'] = 'x'
        self.assertRaisesInvalidEnum(
            self.nc, "'x'", "['cidr', 'ip_ranges', None]")

    def test_networks_invalid_type_render_type(self):
        self.nc['networks'][0]['meta']['render_type'] = 1
        self.assertRaisesInvalidType(self.nc, "1", "'string', 'null'")

    def test_networks_invalid_type_render_addr_mask(self):
        self.nc['networks'][0]['meta']['render_addr_mask'] = []
        self.assertRaisesInvalidType(self.nc, "[]", "'string', 'null'")

    def test_networks_invalid_type_unmovable(self):
        self.nc['networks'][0]['meta']['unmovable'] = 5
        self.assertRaisesInvalidType(self.nc, "5", "'boolean'")

    def test_networks_meta_invalid_type_map_priority(self):
        self.nc['networks'][0]['meta']['map_priority'] = {}
        self.assertRaisesInvalidType(self.nc, "{}", "'integer'")

    def test_networks_meta_invalid_type_configurable(self):
        self.nc['networks'][0]['meta']['configurable'] = 'hello'
        self.assertRaisesInvalidType(self.nc, "'hello'", "'boolean'")

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

        self.nc['networks'][0]['meta']['vips'] = ['vip_a', 'vip_a']
        self.assertRaisesNonUnique(self.nc, "[u'vip_a', u'vip_a']")

        self.nc['networks'][0]['meta']['vips'] = ["a", "b", "c1"]
        self.assertRaisesNotMatchPattern(self.nc, "'c1'")


class TestNetworkConfigurationValidator(base.BaseIntegrationTest):
    def setUp(self):
        super(TestNetworkConfigurationValidator, self).setUp()

        self.cluster = self.env.create(
            cluster_kwargs={
                "api": False,
                "net_provider": consts.CLUSTER_NET_PROVIDERS.neutron
            },
            nodes_kwargs=[
                {"api": False,
                 "pending_addition": True},
            ]
        )

        self.config = self.env.neutron_networks_get(self.cluster.id).json_body
        self.validator = NetworkConfigurationValidator

    def find_net_by_name(self, name):
        for net in self.config['networks']:
            if net['name'] == name:
                return net

    def get_context_of_validation_error(self):
        with self.assertRaises(errors.InvalidData) as exc_context:
            self.validator.validate_networks_data(jsonutils.dumps(self.config),
                                                  self.cluster)
        return exc_context

    def assertRaisesInvalidData(self, message):
        exc_context = self.get_context_of_validation_error()
        self.assertIn(message, exc_context.exception.message)

    def test_validate_networks_not_in_db(self):
        mgmt = self.find_net_by_name(consts.NETWORKS.management)
        sto = self.find_net_by_name(consts.NETWORKS.storage)

        mgmt_db = self.db.query(NetworkGroup).get(mgmt['id'])
        sto_db = self.db.query(NetworkGroup).get(sto['id'])
        self.db.delete(mgmt_db)
        self.db.delete(sto_db)
        self.db.flush()

        exc_context = self.get_context_of_validation_error()
        message = exc_context.exception.message

        self.assertEqual(
            "Networks with ID's [{0}, {1}] are not "
            "present in the database".format(
                *sorted([sto['id'], mgmt['id']])
            ),
            message
        )

    def test_validate_network_no_ip_ranges(self):
        mgmt = self.find_net_by_name(consts.NETWORKS.management)
        mgmt['meta']['notation'] = consts.NETWORK_NOTATION.ip_ranges
        mgmt['ip_ranges'] = []
        mgmt_db = self.db.query(NetworkGroup).get(mgmt['id'])
        mgmt_db.ip_ranges = []
        self.db.flush()

        self.assertRaisesInvalidData(
            "No IP ranges were specified for network {0}".format(mgmt['id']))

    def test_validate_network_no_cidr(self):
        mgmt = self.find_net_by_name(consts.NETWORKS.management)
        mgmt['meta']['notation'] = consts.NETWORK_NOTATION.cidr
        mgmt['cidr'] = None
        mgmt_db = self.db.query(NetworkGroup).get(mgmt['id'])
        mgmt_db.cidr = None
        self.db.flush()

        self.assertRaisesInvalidData(
            "No CIDR was specified for network {0}".format(mgmt['id']))

    def test_validate_network_no_gateway(self):
        mgmt = self.find_net_by_name(consts.NETWORKS.management)
        mgmt['meta']['use_gateway'] = True
        mgmt['gateway'] = None
        mgmt_db = self.db.query(NetworkGroup).get(mgmt['id'])
        mgmt_db.gateway = None
        self.db.flush()

        self.assertRaisesInvalidData(
            "'use_gateway' cannot be provided without gateway")

    def test_check_ip_conflicts(self):
        mgmt = self.find_net_by_name(consts.NETWORKS.management)

        # firstly check default IPs from management net assigned to nodes
        ips = NeutronManager.get_assigned_ips_by_network_id(mgmt['id'])
        self.assertListEqual(['192.168.0.1', '192.168.0.2'], sorted(ips),
                             "Default IPs were changed for some reason.")

        mgmt['cidr'] = '10.101.0.0/24'
        result = NetworkConfigurationValidator._check_for_ip_conflicts(
            mgmt, self.cluster, consts.NETWORK_NOTATION.cidr, False)
        self.assertTrue(result)

        mgmt['cidr'] = '192.168.0.0/28'
        result = NetworkConfigurationValidator._check_for_ip_conflicts(
            mgmt, self.cluster, consts.NETWORK_NOTATION.cidr, False)
        self.assertFalse(result)

        mgmt['ip_ranges'] = [['192.168.0.1', '192.168.0.15']]
        result = NetworkConfigurationValidator._check_for_ip_conflicts(
            mgmt, self.cluster, consts.NETWORK_NOTATION.ip_ranges, False)
        self.assertFalse(result)

        mgmt['ip_ranges'] = [['10.101.0.1', '10.101.0.255']]
        result = NetworkConfigurationValidator._check_for_ip_conflicts(
            mgmt, self.cluster, consts.NETWORK_NOTATION.ip_ranges, False)
        self.assertTrue(result)


class TestNovaNetworkConfigurationValidatorProtocol(
    BaseNetworkConfigurationValidatorProtocolTest
):

    validator = NovaNetworkConfigurationValidator.additional_network_validation

    def setUp(self):
        super(TestNovaNetworkConfigurationValidatorProtocol, self).setUp()
        self.nc = {
            "networking_parameters": {
                "dns_nameservers": ["8.8.4.4", "8.8.8.8"],
                "floating_ranges": [["172.16.0.130", "172.16.0.254"]],
                "fixed_network_size": 1,
                "fixed_networks_amount": 2,
                "fixed_networks_cidr": "192.168.111.0/24",
                "fixed_networks_vlan_start": 101,
                "net_manager": consts.NOVA_NET_MANAGERS.FlatDHCPManager
            }
        }

    def get_invalid_data_context(self, obj):
        with self.assertRaises(errors.InvalidData) as context:
            self.validator(obj, None)

        return context

    # networking parameters
    def test_networking_parameters_invalid_type(self):
        self.nc['networking_parameters'] = 1
        self.assertRaisesInvalidType(self.nc, "1", "'object'")

    def test_dns_nameservers_ip_range(self):
        self.nc['networking_parameters']['dns_nameservers'] = {}
        self.assertRaisesInvalidType(self.nc, "{}", "'array'")

        self.nc['networking_parameters']['dns_nameservers'] = [1, 2]
        self.assertRaisesInvalidType(self.nc, "1", "'string'")

        self.nc['networking_parameters']['dns_nameservers'] = \
            ["1.1.1.1", "1.1.1.2", "1.1.1.3"]
        self.assertRaisesTooLong(
            self.nc,
            "['1.1.1.1', '1.1.1.2', '1.1.1.3']")

        self.nc['networking_parameters']['dns_nameservers'] = ["1.1.1.1"]
        self.assertRaisesTooShort(self.nc, "['1.1.1.1']")

        self.nc['networking_parameters']['dns_nameservers'] =\
            ['1.2.3.4', '1.2.3.4']
        self.assertRaisesNonUnique(self.nc, "['1.2.3.4', '1.2.3.4']")

        self.nc['networking_parameters']['dns_nameservers'] = \
            ["1.1.1.1", "1.2.3.x"]
        self.assertRaisesInvalidAnyOf(
            self.nc,
            "'1.2.3.x'",
            "['networking_parameters']['dns_nameservers']")


class TestNeutronNetworkConfigurationValidatorProtocol(
    BaseNetworkConfigurationValidatorProtocolTest
):

    validator = \
        NeutronNetworkConfigurationValidator.additional_network_validation

    def get_invalid_data_context(self, obj):
        with self.assertRaises(errors.InvalidData) as context:
            self.validator(obj, None)

        return context

    def setUp(self):
        super(TestNeutronNetworkConfigurationValidatorProtocol, self).setUp()
        self.nc = {
            "networking_parameters": {
                "base_mac": "fa:16:3e:00:00:00",
                "configuration_template": None,
                "dns_nameservers": ["8.8.4.4", "8.8.8.8"],
                "floating_ranges": [["172.16.0.130", "172.16.0.254"]],
                "gre_id_range": [2, 65535],
                "internal_cidr": "192.168.111.0/24",
                "internal_gateway": "192.168.111.1",
                "net_l23_provider": consts.NEUTRON_L23_PROVIDERS.ovs,
                "segmentation_type": consts.NEUTRON_SEGMENT_TYPES.gre,
                "vlan_range": [1000, 1030]
            }
        }

    # networking parameters
    def test_networking_parameters_invalid_type(self):
        self.nc['networking_parameters'] = 1
        self.assertRaisesInvalidType(self.nc, "1", "'object'")

    def test_dns_nameservers_ip_range(self):
        self.nc['networking_parameters']['dns_nameservers'] = {}
        self.assertRaisesInvalidType(self.nc, "{}", "'array'")

        self.nc['networking_parameters']['dns_nameservers'] = [1, 2]
        self.assertRaisesInvalidType(self.nc, "1", "'string'")

        self.nc['networking_parameters']['dns_nameservers'] = \
            ["1.1.1.1", "1.1.1.2", "1.1.1.3"]
        self.assertRaisesTooLong(
            self.nc,
            "['1.1.1.1', '1.1.1.2', '1.1.1.3']")

        self.nc['networking_parameters']['dns_nameservers'] = ["1.1.1.1"]
        self.assertRaisesTooShort(self.nc, "['1.1.1.1']")

        self.nc['networking_parameters']['dns_nameservers'] =\
            ['1.2.3.4', '1.2.3.4']
        self.assertRaisesNonUnique(self.nc, "['1.2.3.4', '1.2.3.4']")

        self.nc['networking_parameters']['dns_nameservers'] = \
            ["1.1.1.1", "1.2.3.x"]
        self.assertRaisesInvalidAnyOf(
            self.nc,
            "'1.2.3.x'",
            "['networking_parameters']['dns_nameservers']")


class TestNeutronNetworkConfigurationValidator(base.BaseIntegrationTest):

    validator = NeutronNetworkConfigurationValidator

    def setUp(self):
        super(TestNeutronNetworkConfigurationValidator, self).setUp()

        self.cluster = self.env.create(
            cluster_kwargs={
                "api": False,
                "net_provider": consts.CLUSTER_NET_PROVIDERS.neutron
            }
        )
        self.config = self.env.neutron_networks_get(self.cluster.id).json_body

    def create_additional_node_group(self):
        node_group = NodeGroup(
            name="custom_group_name", cluster_id=self.cluster.id)
        self.env.db.add(node_group)
        self.env.db.flush()

        self.env.create_node(cluster_id=self.cluster.id,
                             roles=["controller"])
        self.env.create_node(cluster_id=self.cluster.id,
                             roles=["compute"],
                             group_id=node_group.id)

    def check_no_fuelweb_admin_network_in_validated_data(self):
        default_admin = self.db.query(
            NetworkGroup).filter_by(group_id=None).first()
        validated_data = self.validator.prepare_data(self.config)
        self.assertNotIn(
            default_admin.id,
            [ng['id'] for ng in validated_data['networks']]
        )

    def test_fuelweb_admin_removed(self):
        self.check_no_fuelweb_admin_network_in_validated_data()

    def test_fuelweb_admin_removed_w_additional_node_group(self):
        self.create_additional_node_group()
        self.check_no_fuelweb_admin_network_in_validated_data()
