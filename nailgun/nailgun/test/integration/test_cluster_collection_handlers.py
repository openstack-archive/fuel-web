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

from mock import patch
from sqlalchemy.sql import not_

from nailgun import objects

from nailgun.db.sqlalchemy.models import Cluster
from nailgun.db.sqlalchemy.models import NetworkGroup
from nailgun.db.sqlalchemy.models import Release
from nailgun.network.nova_network import NovaNetworkManager
from nailgun.openstack.common import jsonutils
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import reverse


class TestHandlers(BaseIntegrationTest):

    def _get_cluster_networks(self, cluster_id):
        nets = self.app.get(
            reverse('NovaNetworkConfigurationHandler',
                    {"cluster_id": cluster_id}),
            headers=self.default_headers,
        ).json_body["networks"]
        return nets

    def test_cluster_list_empty(self):
        resp = self.app.get(
            reverse('ClusterCollectionHandler'),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        self.assertEqual([], resp.json_body)

    def test_cluster_create(self):
        release_id = self.env.create_release(api=False).id
        resp = self.app.post(
            reverse('ClusterCollectionHandler'),
            jsonutils.dumps({
                'name': 'cluster-name',
                'release': release_id,
            }),
            headers=self.default_headers
        )
        self.assertEqual(201, resp.status_code)

    def test_cluster_create_no_ip_addresses(self):
        """In this test we check that no error is occured
        if two clusters will have same networks updated to use
        full CIDR
        """
        cluster = self.env.create_cluster(api=True)
        cluster_db = self.db.query(Cluster).get(cluster["id"])
        cluster2 = self.env.create_cluster(api=True,
                                           release_id=cluster_db.release.id)
        cluster2_db = self.db.query(Cluster).get(cluster2["id"])

        for clstr in (cluster_db, cluster2_db):
            management_net = self.db.query(NetworkGroup).filter_by(
                name="management",
                group_id=objects.Cluster.get_default_group(clstr).id
            ).first()
            NovaNetworkManager.update(
                clstr,
                {
                    "networks": [
                        {
                            "name": "management",
                            "ip_ranges": [
                                ["192.168.0.2", "192.168.255.254"]
                            ],
                            "id": management_net.id,
                            "cluster_id": clstr.id,
                            "vlan_start": 101,
                            "cidr": "192.168.0.0/16",
                            "gateway": "192.168.0.1"
                        }
                    ]
                }
            )

        cluster1_nets = self._get_cluster_networks(cluster["id"])
        cluster2_nets = self._get_cluster_networks(cluster2["id"])

        for net1, net2 in zip(cluster1_nets, cluster2_nets):
            for f in ('group_id', 'id'):
                del net1[f]
                del net2[f]

        cluster1_nets = sorted(cluster1_nets, key=lambda n: n['name'])
        cluster2_nets = sorted(cluster2_nets, key=lambda n: n['name'])

        self.assertEquals(cluster1_nets, cluster2_nets)

    def test_cluster_creation_same_networks(self):
        cluster1_id = self.env.create_cluster(api=True)["id"]
        cluster2_id = self.env.create_cluster(api=True)["id"]
        cluster1_nets = self._get_cluster_networks(cluster1_id)
        cluster2_nets = self._get_cluster_networks(cluster2_id)

        for net1, net2 in zip(cluster1_nets, cluster2_nets):
            for f in ('group_id', 'id'):
                del net1[f]
                del net2[f]

        cluster1_nets = sorted(cluster1_nets, key=lambda n: n['name'])
        cluster2_nets = sorted(cluster2_nets, key=lambda n: n['name'])

        self.assertEqual(cluster1_nets, cluster2_nets)

    def test_if_cluster_creates_correct_networks(self):
        release = Release()
        release.version = "1.1.1"
        release.name = u"release_name_" + str(release.version)
        release.description = u"release_desc" + str(release.version)
        release.operating_system = "CentOS"
        release.networks_metadata = self.env.get_default_networks_metadata()
        release.attributes_metadata = {
            "editable": {
                "keystone": {
                    "admin_tenant": "admin"
                }
            },
            "generated": {
                "mysql": {
                    "root_password": ""
                }
            }
        }
        self.db.add(release)
        self.db.commit()
        resp = self.app.post(
            reverse('ClusterCollectionHandler'),
            jsonutils.dumps({
                'name': 'cluster-name',
                'release': release.id,
            }),
            headers=self.default_headers
        )
        self.assertEqual(201, resp.status_code)
        nets = self.db.query(NetworkGroup).filter(
            not_(NetworkGroup.name == "fuelweb_admin")
        ).all()
        obtained = []
        for net in nets:
            obtained.append({
                'release': net.release,
                'name': net.name,
                'vlan_id': net.vlan_start,
                'cidr': net.cidr,
                'gateway': net.gateway
            })
        expected = [
            {
                'release': release.id,
                'name': u'public',
                'vlan_id': None,
                'cidr': '172.16.0.0/24',
                'gateway': '172.16.0.1'
            },
            {
                'release': release.id,
                'name': u'fixed',
                'vlan_id': None,
                'cidr': None,
                'gateway': None
            },
            {
                'release': release.id,
                'name': u'storage',
                'vlan_id': 102,
                'cidr': '192.168.1.0/24',
                'gateway': None
            },
            {
                'release': release.id,
                'name': u'management',
                'vlan_id': 101,
                'cidr': '192.168.0.0/24',
                'gateway': None
            }
        ]
        self.assertItemsEqual(expected, obtained)

    @patch('nailgun.rpc.cast')
    def test_verify_networks(self, mocked_rpc):
        cluster = self.env.create_cluster(api=True)
        nets = self.env.nova_networks_get(cluster['id']).json_body

        resp = self.env.nova_networks_put(cluster['id'], nets)
        self.assertEqual(202, resp.status_code)
        self.assertEqual(resp.json_body['status'], 'ready')
