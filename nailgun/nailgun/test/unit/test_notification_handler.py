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

    def test_notification_get_without_cluster(self):
        notification = self.env.create_notification()
        resp = self.app.get(
            reverse(
                'NotificationHandler',
                kwargs={'obj_id': notification.id}
            ),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        self.assertIsNone(resp.json_body.get('cluster'))
        self.assertEqual(notification.status, 'unread')
        self.assertEqual(notification.id, resp.json_body['id'])
        self.assertEqual(notification.status, resp.json_body['status'])
        self.assertEqual(notification.topic, resp.json_body['topic'])
        self.assertEqual(notification.message, resp.json_body['message'])

    def test_notification_datetime(self):
        self.env.create_node(
            api=True,
            meta=self.env.default_metadata()
        )
        resp = self.app.get(
            reverse('NotificationCollectionHandler'),
            headers=self.default_headers
        )
        notif_api = resp.json_body[0]
        self.assertIn('date', notif_api)
        self.assertNotEqual(notif_api['date'], '')
        self.assertIn('time', notif_api)
        self.assertNotEqual(notif_api['time'], '')

    def test_notification_get_with_cluster(self):
        cluster = self.env.create_cluster(api=False)
        notification = self.env.create_notification(cluster_id=cluster.id)
        resp = self.app.get(
            reverse(
                'NotificationHandler',
                kwargs={'obj_id': notification.id}
            ),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        self.assertEqual(resp.json_body.get('cluster'), cluster.id)
        self.assertEqual(notification.status, 'unread')
        self.assertEqual(notification.id, resp.json_body['id'])
        self.assertEqual(notification.status, resp.json_body['status'])
        self.assertEqual(notification.topic, resp.json_body['topic'])
        self.assertEqual(notification.message, resp.json_body['message'])

    def test_notification_update(self):
        notification = self.env.create_notification()
        notification_update = {
            'status': 'read'
        }
        resp = self.app.put(
            reverse(
                'NotificationHandler',
                kwargs={'obj_id': notification.id}
            ),
            jsonutils.dumps(notification_update),
            headers=self.default_headers
        )
        self.assertEqual(notification.id, resp.json_body['id'])
        self.assertEqual('read', resp.json_body['status'])
        self.assertEqual(notification.topic, resp.json_body['topic'])
        self.assertEqual(notification.message, resp.json_body['message'])

    def test_notification_not_found(self):
        notification = self.env.create_notification()
        resp = self.app.get(
            reverse(
                'NotificationHandler',
                kwargs={'obj_id': notification.id + 1}
            ),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(404, resp.status_code)
