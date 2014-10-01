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

from nailgun.openstack.common import jsonutils
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import reverse


class TestHandlers(BaseIntegrationTest):

    def test_empty(self):
        resp = self.app.get(
            reverse('NotificationCollectionHandler'),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        self.assertEqual([], resp.json_body)

    def test_not_empty(self):
        c = self.env.create_cluster(api=False)
        n0 = self.env.create_notification()
        n1 = self.env.create_notification(cluster_id=c.id)
        resp = self.app.get(
            reverse('NotificationCollectionHandler'),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        self.assertEqual(len(resp.json_body), 2)
        if resp.json_body[0]['id'] == n0.id:
            rn0 = resp.json_body[0]
            rn1 = resp.json_body[1]
        else:
            rn0 = resp.json_body[1]
            rn1 = resp.json_body[0]
        self.assertEqual(rn1['cluster'], n1.cluster_id)
        self.assertIsNone(rn0.get('cluster', None))

    def test_update(self):
        c = self.env.create_cluster(api=False)
        n0 = self.env.create_notification()
        n1 = self.env.create_notification(cluster_id=c.id)
        notification_update = [
            {
                'id': n0.id,
                'status': 'read'
            },
            {
                'id': n1.id,
                'status': 'read'
            }
        ]
        resp = self.app.put(
            reverse('NotificationCollectionHandler'),
            jsonutils.dumps(notification_update),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        self.assertEqual(len(resp.json_body), 2)
        if resp.json_body[0]['id'] == n0.id:
            rn0 = resp.json_body[0]
            rn1 = resp.json_body[1]
        else:
            rn0 = resp.json_body[1]
            rn1 = resp.json_body[0]
        self.assertEqual(rn1['cluster'], n1.cluster_id)
        self.assertEqual(rn1['status'], 'read')
        self.assertIsNone(rn0.get('cluster', None))
        self.assertEqual(rn0['status'], 'read')
