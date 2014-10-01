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


from nailgun.objects.serializers.network_configuration \
    import NeutronNetworkConfigurationSerializer
from nailgun.objects.serializers.network_configuration \
    import NovaNetworkConfigurationSerializer

from nailgun.db.sqlalchemy.models import NeutronConfig
from nailgun.db.sqlalchemy.models import NovaNetworkConfig
from nailgun.openstack.common import jsonutils
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import fake_tasks
from nailgun.test.base import reverse


class TestNetworkModels(BaseIntegrationTest):

    def tearDown(self):
        self._wait_for_threads()
        super(TestNetworkModels, self).tearDown()

    @fake_tasks(godmode=True)
    def test_cluster_locking_after_deployment(self):
        self.env.create(
            nodes_kwargs=[
                {"pending_addition": True},
                {"pending_addition": True},
                {"pending_deletion": True},
            ]
        )
        supertask = self.env.launch_deployment()
        self.env.wait_ready(supertask, 60)

        test_nets = self.env.nova_networks_get(
            self.env.clusters[0].id
        ).json_body

        resp_nova_net = self.env.nova_networks_put(
            self.env.clusters[0].id,
            test_nets,
            expect_errors=True
        )

        resp_neutron_net = self.env.neutron_networks_put(
            self.env.clusters[0].id,
            test_nets,
            expect_errors=True
        )

        resp_cluster = self.app.put(
            reverse('ClusterAttributesHandler',
                    kwargs={'cluster_id': self.env.clusters[0].id}),
            jsonutils.dumps({
                'editable': {
                    "foo": "bar"
                }
            }),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(resp_nova_net.status_code, 403)
        # it's 400 because we used Nova network
        self.assertEqual(resp_neutron_net.status_code, 400)
        self.assertEqual(resp_cluster.status_code, 403)

    def test_nova_net_networking_parameters(self):
        cluster = self.env.create_cluster(api=False)
        self.db.delete(cluster.network_config)
        kw = {
            "net_manager": "VlanManager",
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
        cluster = self.env.create_cluster(api=False,
                                          net_provider='neutron')
        self.db.delete(cluster.network_config)
        kw = {
            "net_l23_provider": "ovs",
            "segmentation_type": "gre",
            "vlan_range": [1000, 1030],
            "gre_id_range": [2, 65534],
            "base_mac": "fa:16:3e:00:00:00",
            "internal_cidr": "192.168.111.0/24",
            "internal_gateway": "192.168.111.1",
            "floating_ranges": [["172.16.0.130", "172.16.0.254"]],
            "dns_nameservers": ["8.8.4.4", "8.8.8.8"],
            "cluster_id": cluster.id
        }
        nc = NeutronConfig(**kw)
        self.db.add(nc)
        self.db.flush()
        self.db.refresh(cluster)

        nw_params = NeutronNetworkConfigurationSerializer. \
            serialize_network_params(cluster)

        kw.pop("cluster_id")
        self.assertEqual(nw_params, kw)
