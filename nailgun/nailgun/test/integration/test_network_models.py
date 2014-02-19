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

import json

from sqlalchemy.sql import not_

from nailgun.db.sqlalchemy.models import NetworkGroup
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import fake_tasks
from nailgun.test.base import reverse


class TestNetworkModels(BaseIntegrationTest):

    def tearDown(self):
        self._wait_for_threads()
        super(TestNetworkModels, self).tearDown()

    def test_network_group_size_of_1_creates_1_network(self):
        cluster = self.env.create_cluster(api=False)
        kw = {'release': cluster.release_id,
              'cidr': '10.0.0.0/24',
              'netmask': '255.255.255.0',
              'network_size': 256,
              'name': 'fixed',
              'vlan_start': 200,
              'cluster_id': cluster.id}
        ng = NetworkGroup(**kw)
        self.db.add(ng)
        self.db.commit()
        self.env.network_manager.cleanup_network_group(ng)
        nets_db = self.db.query(NetworkGroup).filter(
            not_(NetworkGroup.name == "fuelweb_admin")
        ).all()
        self.assertEquals(len(nets_db), 1)
        self.assertEquals(nets_db[0].vlan_start, kw['vlan_start'])
        self.assertEquals(nets_db[0].name, kw['name'])
        self.assertEquals(nets_db[0].cidr, kw['cidr'])

    @fake_tasks(godmode=True)
    def test_cluster_locking_after_deployment(self):
        self.env.create(
            cluster_kwargs={
                "mode": "ha_compact"
            },
            nodes_kwargs=[
                {"pending_addition": True},
                {"pending_addition": True},
                {"pending_deletion": True},
            ]
        )
        supertask = self.env.launch_deployment()
        self.env.wait_ready(supertask, 60)

        test_nets = json.loads(self.env.nova_networks_get(
            self.env.clusters[0].id
        ).body)

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
            json.dumps({
                'editable': {
                    "foo": "bar"
                }
            }),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEquals(resp_nova_net.status, 403)
        # it's 400 because we used Nova network
        self.assertEquals(resp_neutron_net.status, 400)
        self.assertEquals(resp_cluster.status, 403)

    def test_network_group_creates_several_networks(self):
        cluster = self.env.create_cluster(api=False)
        kw = {'release': cluster.release_id,
              'cidr': '10.0.0.0/8',
              'netmask': '255.0.0.0',
              'network_size': 256,
              'name': 'fixed',
              'vlan_start': 200,
              'amount': 25,
              'cluster_id': cluster.id}
        ng = NetworkGroup(**kw)
        self.db.add(ng)
        self.db.commit()
        self.env.network_manager.cleanup_network_group(ng)
        nets_db = self.db.query(NetworkGroup).filter(
            not_(NetworkGroup.name == "fuelweb_admin")
        ).all()
        self.assertEquals(nets_db[0].amount, kw['amount'])
        self.assertEquals(nets_db[0].vlan_start, kw['vlan_start'])
        self.assertEquals(all(x.name == kw['name'] for x in nets_db), True)

    def test_network_group_slices_cidr_for_networks(self):
        cluster = self.env.create_cluster(api=False)
        kw = {'release': cluster.release_id,
              'cidr': '10.0.0.0/16',
              'netmask': '255.255.0.0',
              'network_size': 128,
              'name': 'fixed',
              'vlan_start': 200,
              'amount': 2,
              'cluster_id': cluster.id}
        ng = NetworkGroup(**kw)
        self.db.add(ng)
        self.db.commit()
        self.env.network_manager.cleanup_network_group(ng)
        nets_db = self.db.query(NetworkGroup).filter(
            not_(NetworkGroup.name == "fuelweb_admin")
        ).all()
        self.assertEquals(nets_db[0].amount, kw['amount'])
        self.assertEquals(nets_db[0].cidr, '10.0.0.0/16')
        self.db.refresh(ng)
        self.assertEquals(ng.cidr, '10.0.0.0/16')

    def test_network_group_does_not_squeezes_base_cidr(self):
        cluster = self.env.create_cluster(api=False)
        kw = {'release': cluster.release_id,
              'cidr': '172.0.0.0/24',
              'netmask': '255.255.255.0',
              'network_size': 64,
              'name': 'fixed',
              'vlan_start': 200,
              'amount': 3,
              'cluster_id': cluster.id}
        ng = NetworkGroup(**kw)
        self.db.add(ng)
        self.db.commit()
        self.env.network_manager.cleanup_network_group(ng)
        self.db.refresh(ng)
        self.assertEquals(ng.cidr, "172.0.0.0/24")

    def test_network_group_does_not_squeezes_base_cidr_if_amount_1(self):
        cluster = self.env.create_cluster(api=False)
        kw = {'release': cluster.release_id,
              'cidr': '172.0.0.0/8',
              'netmask': '255.0.0.0',
              'network_size': 256,
              'name': 'public',
              'vlan_start': 200,
              'amount': 1,
              'cluster_id': cluster.id}
        ng = NetworkGroup(**kw)
        self.db.add(ng)
        self.db.commit()
        self.env.network_manager.cleanup_network_group(ng)
        self.db.refresh(ng)
        self.assertEquals(ng.cidr, "172.0.0.0/8")

    def test_network_group_sets_correct_gateway_for_few_nets(self):
        cluster = self.env.create_cluster(api=False)
        kw = {'release': cluster.release_id,
              'cidr': '10.0.0.0/8',
              'netmask': '255.0.0.0',
              'network_size': 128,
              'name': 'fixed',
              'vlan_start': 200,
              'amount': 2,
              'gateway': "10.0.0.5",
              'cluster_id': cluster.id}
        ng = NetworkGroup(**kw)
        self.db.add(ng)
        self.db.commit()
        self.env.network_manager.cleanup_network_group(ng)
        nets_db = self.db.query(NetworkGroup).filter(
            not_(NetworkGroup.name == "fuelweb_admin")
        ).all()
        self.assertEquals(nets_db[0].amount, kw['amount'])
        self.assertEquals(nets_db[0].gateway, "10.0.0.5")
