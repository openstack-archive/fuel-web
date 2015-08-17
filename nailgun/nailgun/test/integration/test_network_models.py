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

from oslo_serialization import jsonutils

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

    def tearDown(self):
        self._wait_for_threads()
        super(TestNetworkModels, self).tearDown()

    def test_cluster_locking_during_deployment(self):
        self.env.create(
            cluster_kwargs={'status': consts.CLUSTER_STATUSES.deployment},
            nodes_kwargs=[
                {'pending_addition': False,
                 'status': consts.NODE_STATUSES.deploying},
                {'pending_addition': False,
                 'status': consts.NODE_STATUSES.deploying},
                {'pending_addition': False,
                 'status': consts.NODE_STATUSES.deploying}])

        test_nets = self.env.nova_networks_get(
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
                    "foo": "bar"
                }
            }),
            headers=self.default_headers,
            expect_errors=True)

        self.assertEqual(resp_nova_net.status_code, 403)
        # it's 400 because we used Nova network
        self.assertEqual(resp_neutron_net.status_code, 400)
        self.assertEqual(resp_cluster.status_code, 403)

    def test_networks_update_after_deployment(self):
        self.env.create(
            cluster_kwargs={
                'net_provider': consts.CLUSTER_NET_PROVIDERS.neutron,
                'net_segment_type': consts.NEUTRON_SEGMENT_TYPES.gre,
                'status': consts.CLUSTER_STATUSES.operational
            },
            nodes_kwargs=[
                {'pending_addition': False,
                 'status': consts.NODE_STATUSES.ready},
                {'pending_addition': False,
                 'status': consts.NODE_STATUSES.ready},
                {'pending_deletion': False,
                 'status': consts.NODE_STATUSES.ready}])

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
            self.env.clusters[0].id,
            test_nets)

        # Response for task submission handler is always 200,
        # the result of task should be checked by status of the task.
        # https://review.openstack.org/#/c/137642/15/nailgun/nailgun/
        #         api/v1/handlers/network_configuration.py
        self.assertEqual(200, resp_neutron_net.status_code)
        self.assertEqual(consts.TASK_STATUSES.error,
                         resp_neutron_net.json_body['status'])
        self.assertEqual(
            "New IP ranges for network '{0}' conflict "
            "with already allocated IPs.".format(test_network_name),
            resp_neutron_net.json_body['message'])

        mgmt_net['cidr'] = u'192.168.0.0/30'

        resp_neutron_net = self.env.neutron_networks_put(
            self.env.clusters[0].id,
            test_nets)

        self.assertEqual(200, resp_neutron_net.status_code)
        self.assertEqual(consts.TASK_STATUSES.ready,
                         resp_neutron_net.json_body['status'],
                         "Task error message: {0}".format(
                             resp_neutron_net.json_body['message']))

        new_nets = self.env.neutron_networks_get(
            self.env.clusters[0].id).json_body

        # test that network was changed
        modified_net = filter(lambda x: x['name'] == test_network_name,
                              new_nets['networks'])[0]
        self.assertEqual(u'192.168.0.0/30', modified_net['cidr'])

        # test that networking_parameters were not changed
        self.assertDictEqual(test_network_params,
                             new_nets['networking_parameters'])

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

    def test_neutron_networking_parameters(self):
        cluster = self.env.create_cluster(
            api=False,
            net_provider=consts.CLUSTER_NET_PROVIDERS.neutron)
        self.db.delete(cluster.network_config)
        kw = {
            "net_l23_provider": consts.NEUTRON_L23_PROVIDERS.ovs,
            "segmentation_type": consts.NEUTRON_SEGMENT_TYPES.gre,
            "vlan_range": [1000, 1030],
            "gre_id_range": [2, 65534],
            "base_mac": "fa:16:3e:00:00:00",
            "internal_cidr": "192.168.111.0/24",
            "internal_gateway": "192.168.111.1",
            "floating_ranges": [["172.16.0.130", "172.16.0.254"]],
            "dns_nameservers": ["8.8.4.4", "8.8.8.8"],
            "cluster_id": cluster.id,
            "configuration_template": {}
        }
        nc = NeutronConfig(**kw)
        self.db.add(nc)
        self.db.flush()
        self.db.refresh(cluster)

        nw_params = NeutronNetworkConfigurationSerializer. \
            serialize_network_params(cluster)

        kw.pop("cluster_id")
        self.assertEqual(nw_params, kw)
