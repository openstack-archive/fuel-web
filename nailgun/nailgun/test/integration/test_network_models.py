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

import copy
from mock import patch

from oslo_serialization import jsonutils
import yaml

from nailgun.objects import Cluster
from nailgun.objects.serializers.network_configuration \
    import NeutronNetworkConfigurationSerializer
from nailgun.objects.serializers.network_configuration \
    import NovaNetworkConfigurationSerializer

from nailgun import consts
from nailgun.db.sqlalchemy.models import NeutronConfig
from nailgun.db.sqlalchemy.models import NovaNetworkConfig
from nailgun.test.base import BaseIntegrationTest
from nailgun.utils import reverse


class TestNetworkModels(BaseIntegrationTest):

    network_config = {
        "net_l23_provider": consts.NEUTRON_L23_PROVIDERS.ovs,
        "segmentation_type": consts.NEUTRON_SEGMENT_TYPES.gre,
        "vlan_range": [1000, 1030],
        "gre_id_range": [2, 65534],
        "base_mac": "fa:16:3e:00:00:00",
        "internal_cidr": "192.168.111.0/24",
        "internal_gateway": "192.168.111.1",
        "internal_name": "my_internal_name",
        "floating_name": "my_floating_name",
        "floating_ranges": [
            ["172.16.0.130", "172.16.0.150"],
            ["172.16.0.160", "172.16.0.254"]
        ],
        "dns_nameservers": ["8.8.4.4", "8.8.8.8"],
        "configuration_template": {}
    }

    def create_env_using_statuses(self, cluster_status, node_status):
        self.env.create(
            cluster_kwargs={
                'net_provider': consts.CLUSTER_NET_PROVIDERS.neutron,
                'net_segment_type': consts.NEUTRON_SEGMENT_TYPES.gre,
                'status': cluster_status
            },
            nodes_kwargs=[
                {'pending_addition': False, 'status': node_status},
                {'pending_addition': False, 'status': node_status},
                {'pending_deletion': False, 'status': node_status}])

    def test_cluster_locking_during_deployment(self):
        self.create_env_using_statuses(consts.CLUSTER_STATUSES.deployment,
                                       consts.NODE_STATUSES.deploying)

        test_nets = self.env.neutron_networks_get(
            self.env.clusters[0].id).json_body

        resp_nova_net = self.env.nova_networks_put(
            self.env.clusters[0].id,
            test_nets,
            expect_errors=True)

        resp_neutron_net = self.env.neutron_networks_put(
            self.env.clusters[0].id,
            test_nets,
            expect_errors=True)

        resp_cluster = self.app.put(
            reverse('ClusterAttributesHandler',
                    kwargs={'cluster_id': self.env.clusters[0].id}),
            jsonutils.dumps({
                'editable': {
                    "foo": {"bar": None}
                }
            }),
            headers=self.default_headers,
            expect_errors=True)

        self.assertEqual(resp_nova_net.status_code, 400)
        # it's 400 because we used Nova network
        self.assertEqual(resp_neutron_net.status_code, 403)
        self.assertEqual(resp_cluster.status_code, 403)

    def test_networks_update_after_deployment(self):
        self.create_env_using_statuses(consts.CLUSTER_STATUSES.operational,
                                       consts.NODE_STATUSES.ready)

        test_nets = self.env.neutron_networks_get(
            self.env.clusters[0].id).json_body

        test_network_params = copy.deepcopy(test_nets['networking_parameters'])
        # change something from 'networking_parameters'
        test_nets['networking_parameters']['dns_nameservers'] = \
            ['8.8.8.8', '8.8.4.4']

        # let's change for example management network
        test_network_name = consts.NETWORKS.management
        mgmt_net = filter(lambda x: x['name'] == test_network_name,
                          test_nets['networks'])[0]

        mgmt_net['cidr'] = u'1.1.1.0/24'

        resp_neutron_net = self.env.neutron_networks_put(
            self.env.clusters[0].id, test_nets, expect_errors=True)

        self.assertEqual(400, resp_neutron_net.status_code)
        self.assertEqual(
            "New IP ranges for network '{0}'({1}) do not cover already "
            "allocated IPs.".format(test_network_name, mgmt_net['id']),
            resp_neutron_net.json_body['message'])

        mgmt_net['cidr'] = u'192.168.0.0/30'

        resp_neutron_net = self.env.neutron_networks_put(
            self.env.clusters[0].id, test_nets)

        self.assertEqual(200, resp_neutron_net.status_code)

        new_nets = self.env.neutron_networks_get(
            self.env.clusters[0].id).json_body

        # test that network was changed
        modified_net = filter(lambda x: x['name'] == test_network_name,
                              new_nets['networks'])[0]
        self.assertEqual(u'192.168.0.0/30', modified_net['cidr'])

        # test that networking_parameters were not changed
        self.assertDictEqual(test_network_params,
                             new_nets['networking_parameters'])

    def test_admin_network_update_after_deployment(self):
        self.create_env_using_statuses(consts.CLUSTER_STATUSES.operational,
                                       consts.NODE_STATUSES.ready)

        test_nets = self.env.neutron_networks_get(
            self.env.clusters[0].id).json_body

        admin_net = filter(
            lambda x: x['name'] == consts.NETWORKS.fuelweb_admin,
            test_nets['networks'])[0]

        admin_net['cidr'] = u'191.111.0.0/26'
        admin_net['ip_ranges'] = [[u'191.111.0.5', u'191.111.0.62']]

        resp_neutron_net = self.env.neutron_networks_put(
            self.env.clusters[0].id, test_nets, expect_errors=True)
        self.assertEqual(400, resp_neutron_net.status_code)
        self.assertEqual(
            "New IP ranges for network '{0}'({1}) do not cover already "
            "allocated IPs.".format(admin_net['name'], admin_net['id']),
            resp_neutron_net.json_body['message'])

        for node in self.env.nodes:
            self.db.delete(node)
        self.db.commit()
        with patch('task.task.rpc.cast'):
            resp_neutron_net = self.env.neutron_networks_put(
                self.env.clusters[0].id, test_nets)
        self.assertEqual(200, resp_neutron_net.status_code)

    def test_nova_net_networking_parameters(self):
        cluster = self.env.create_cluster(api=False)
        self.db.delete(cluster.network_config)
        kw = {
            "net_manager": consts.NOVA_NET_MANAGERS.VlanManager,
            "fixed_networks_cidr": "10.0.0.0/16",
            "fixed_networks_vlan_start": 103,
            "fixed_network_size": 256,
            "fixed_networks_amount": 16,
            "floating_ranges": [["172.16.0.128", "172.16.0.254"]],
            "dns_nameservers": ["8.8.4.4", "8.8.8.8"],
            "cluster_id": cluster.id
        }
        nc = NovaNetworkConfig(**kw)
        self.db.add(nc)
        self.db.flush()
        self.db.refresh(cluster)

        nw_params = NovaNetworkConfigurationSerializer.\
            serialize_network_params(cluster)

        kw.pop("cluster_id")
        self.assertEqual(nw_params, kw)

    def check_neutron_networking_parameters(self, floating_ranges):
        cluster = self.env.create_cluster(
            api=False,
            net_provider=consts.CLUSTER_NET_PROVIDERS.neutron)
        self.db.delete(cluster.network_config)
        self.network_config['floating_ranges'] = floating_ranges
        self.network_config['cluster_id'] = cluster.id
        nc = NeutronConfig(**self.network_config)
        self.db.add(nc)
        self.db.flush()
        self.db.refresh(cluster)

        nw_params = NeutronNetworkConfigurationSerializer. \
            serialize_network_params(cluster)

        self.network_config.pop("cluster_id")
        self.assertItemsEqual(nw_params, self.network_config)

    def test_neutron_networking_parameters_w_single_floating_ranges(self):
        floating_ranges = [["172.16.0.130", "172.16.0.150"]]
        self.check_neutron_networking_parameters(floating_ranges)

    def test_neutron_networking_parameters_w_multiple_floating_ranges(self):
        floating_ranges = [
            ["172.16.0.130", "172.16.0.150"],
            ["172.16.0.160", "172.16.0.254"]]
        self.check_neutron_networking_parameters(floating_ranges)

    def test_neutron_has_internal_and_floating_names(self):
        cluster = self.env.create_cluster(
            api=False,
            net_provider=consts.CLUSTER_NET_PROVIDERS.neutron)

        self.assertEqual(
            "admin_internal_net", cluster.network_config.internal_name)
        self.assertEqual(
            "admin_floating_net", cluster.network_config.floating_name)

    def test_neutron_networking_parameters_baremetal(self):
        attributes_metadata = """
            editable:
                additional_components:
                    ironic:
                        value: %r
                        type: "checkbox"
        """
        cluster = self.env.create_cluster(
            api=False,
            net_provider=consts.CLUSTER_NET_PROVIDERS.neutron)
        # Ensure baremetal_* fields are not serialized when Ironic disabled
        nw_params = NeutronNetworkConfigurationSerializer. \
            serialize_network_params(cluster)
        self.assertNotIn('baremetal_gateway', nw_params)
        self.assertNotIn('baremetal_range', nw_params)
        # Ensure baremetal_* fields are serialized when Ironic enabled
        Cluster.patch_attributes(
            cluster, yaml.load(attributes_metadata % True))
        self.db.refresh(cluster)
        nw_params = NeutronNetworkConfigurationSerializer. \
            serialize_network_params(cluster)
        self.assertIn('baremetal_gateway', nw_params)
        self.assertIn('baremetal_range', nw_params)
