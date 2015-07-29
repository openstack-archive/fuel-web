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

from oslo_serialization import jsonutils

from nailgun import objects
from nailgun.test.base import BaseIntegrationTest
from nailgun.utils import reverse


class TestHandlers(BaseIntegrationTest):

    def setUp(self):
        super(TestHandlers, self).setUp()
        self.cluster = self.env.create_cluster(api=False)

    def _create_network_group(self, expect_errors=False, **kwargs):
        ng = {
            "release": self.cluster.release.id,
            "name": "external",
            "vlan_start": 50,
            "cidr": "10.3.0.0/24",
            "gateway": "10.3.0.1",
            "group_id": objects.Cluster.get_default_group(self.cluster).id,
            "meta": {"notation": "cidr"}
        }

        ng.update(kwargs)

        resp = self.app.post(
            reverse('NetworkGroupCollectionHandler'),
            jsonutils.dumps(ng),
            headers=self.default_headers,
            expect_errors=expect_errors,
        )

        return resp

    def test_create_network_group_w_cidr(self):
        resp = self._create_network_group()
        self.assertEqual(201, resp.status_code)
        ng_data = jsonutils.loads(resp.body)
        ng = objects.NetworkGroup.get_by_uid(ng_data['id'])
        self.assertEqual(len(ng.ip_ranges), 1)
        self.assertEqual(ng.ip_ranges[0].first, "10.3.0.2")
        self.assertEqual(ng.ip_ranges[0].last, "10.3.0.254")

    def test_create_network_group_w_ip_range(self):
        resp = self._create_network_group(
            meta={
                "notation": "ip_ranges",
                "ip_range": ["10.3.0.33", "10.3.0.158"]
            }
        )
        self.assertEqual(201, resp.status_code)
        ng_data = jsonutils.loads(resp.body)
        ng = objects.NetworkGroup.get_by_uid(ng_data['id'])
        self.assertEqual(len(ng.ip_ranges), 1)
        self.assertEqual(ng.ip_ranges[0].first, "10.3.0.33")
        self.assertEqual(ng.ip_ranges[0].last, "10.3.0.158")

    def test_create_network_group_wo_notation(self):
        resp = self._create_network_group(meta={"notation": None})
        self.assertEqual(201, resp.status_code)
        ng_data = jsonutils.loads(resp.body)
        ng = objects.NetworkGroup.get_by_uid(ng_data['id'])
        self.assertEqual(len(ng.ip_ranges), 0)

    def test_get_network_group(self):
        resp = self._create_network_group(name='test')
        self.assertEqual(201, resp.status_code)
        new_ng = jsonutils.loads(resp.body)

        net_group = jsonutils.loads(resp.body)

        resp = self.app.get(
            reverse(
                'NetworkGroupHandler',
                kwargs={'obj_id': net_group['id']}
            ),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        self.assertEqual(jsonutils.loads(resp.body), new_ng)

    def test_delete_network_group(self):
        resp = self._create_network_group(name='test')
        self.assertEqual(201, resp.status_code)

        net_group = jsonutils.loads(resp.body)

        resp = self.app.delete(
            reverse(
                'NetworkGroupHandler',
                kwargs={'obj_id': net_group['id']}
            ),
            headers=self.default_headers
        )
        self.assertEqual(204, resp.status_code)

    def test_cannot_delete_admin_network_group(self):
        admin = objects.Cluster.get_network_manager().get_admin_network_group()
        resp = self.app.delete(
            reverse(
                'NetworkGroupHandler',
                kwargs={'obj_id': admin.id}
            ),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(400, resp.status_code)
        self.assertRegexpMatches(resp.json_body["message"],
                                 'Default Admin-pxe network cannot be deleted')

    def test_create_network_group_non_default_name(self):
        resp = self._create_network_group(name='test')
        new_ng = jsonutils.loads(resp.body)
        self.assertEqual(201, resp.status_code)
        self.assertEqual('test', new_ng['name'])

    def test_modify_network_group(self):
        resp = self._create_network_group(name='test')
        new_ng = jsonutils.loads(resp.body)

        new_ng['name'] = 'test2'

        resp = self.app.put(
            reverse(
                'NetworkGroupHandler',
                kwargs={'obj_id': new_ng['id']}
            ),
            jsonutils.dumps(new_ng),
            headers=self.default_headers
        )
        updated_ng = jsonutils.loads(resp.body)

        self.assertEquals('test2', updated_ng['name'])

    def test_duplicate_network_name_on_creation(self):
        resp = self._create_network_group()
        self.assertEqual(201, resp.status_code)
        resp = self._create_network_group(expect_errors=True)
        self.assertEqual(409, resp.status_code)
        self.assertRegexpMatches(resp.json_body["message"],
                                 'Network with name .* already exists')

    def test_duplicate_network_name_on_change(self):
        resp = self._create_network_group(name='test')
        new_ng = jsonutils.loads(resp.body)

        new_ng['name'] = 'public'

        resp = self.app.put(
            reverse(
                'NetworkGroupHandler',
                kwargs={'obj_id': new_ng['id']}
            ),
            jsonutils.dumps(new_ng),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(409, resp.status_code)
        self.assertRegexpMatches(resp.json_body["message"],
                                 'Network with name .* already exists')

    def test_invalid_group_id_on_creation(self):
        resp = self._create_network_group(expect_errors=True, group_id=-1)
        self.assertEqual(400, resp.status_code)
        self.assertRegexpMatches(resp.json_body["message"],
                                 'Node group with ID -1 does not exist')

    def test_invalid_group_id_on_change(self):
        resp = self._create_network_group(name='test')
        new_ng = jsonutils.loads(resp.body)

        new_ng['group_id'] = -1

        resp = self.app.put(
            reverse(
                'NetworkGroupHandler',
                kwargs={'obj_id': new_ng['id']}
            ),
            jsonutils.dumps(new_ng),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(400, resp.status_code)
        self.assertRegexpMatches(resp.json_body["message"],
                                 'Node group with ID -1 does not exist')
