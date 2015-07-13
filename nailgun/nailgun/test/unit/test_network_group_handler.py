# -*- coding: utf-8 -*-

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

from oslo.serialization import jsonutils

from nailgun import objects
from nailgun.test.base import BaseIntegrationTest
from nailgun.utils import reverse


class TestHandlers(BaseIntegrationTest):

    def setUp(self):
        super(TestHandlers, self).setUp()
        self.cluster = self.env.create_cluster(api=False)

    def _create_network_group(self, **kwargs):
        ng = {
            "release": self.cluster.release.id,
            "name": "storage",
            "vlan_start": 50,
            "cidr": "10.3.0.0/24",
            "gateway": "10.3.0.3",
            "netmask": "255.255.255.0",
            "ip_start": "10.3.0.10",
            "ip_end": "10.3.0.254",
            "group_id": objects.Cluster.get_default_group(self.cluster).id
        }

        ng.update(kwargs)

        return ng

    def test_create_network_group(self):
        network_group = self._create_network_group()
        resp = self.app.post(
            reverse('NetworkGroupCollectionHandler'),
            jsonutils.dumps(network_group),
            headers=self.default_headers
        )
        self.assertEqual(201, resp.status_code)

    def test_delete_network_group(self):
        network_group = self._create_network_group()
        resp = self.app.post(
            reverse('NetworkGroupCollectionHandler'),
            jsonutils.dumps(network_group),
            headers=self.default_headers
        )

        self.assertEqual(201, resp.status_code)
        net_group = jsonutils.loads(resp.body)

        resp = self.app.delete(
            reverse(
                'NetworkGroupHandler',
                kwargs={'net_id': net_group['id']}
            ),
            jsonutils.dumps(network_group),
            headers=self.default_headers
        )
        self.assertEqual(204, resp.status_code)

    def test_create_network_group_non_default_name(self):
        network_group = self._create_network_group(name='test')
        resp = self.app.post(
            reverse('NetworkGroupCollectionHandler'),
            jsonutils.dumps(network_group),
            headers=self.default_headers
        )
        new_ng = jsonutils.loads(resp.body)
        self.assertEqual(201, resp.status_code)
        self.assertEqual('test', new_ng['name'])
