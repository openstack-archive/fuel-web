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

import uuid

from nailgun.db.sqlalchemy.models import Notification
from nailgun.db.sqlalchemy.models import Task
from nailgun.errors import errors
from nailgun import notifier
from nailgun.openstack.common import jsonutils
from nailgun.rpc import receiver as rcvr
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import reverse


class TestNotification(BaseIntegrationTest):

    def test_notification_deploy_done(self):
        cluster = self.env.create_cluster(api=False)
        receiver = rcvr.NailgunReceiver()

        task = Task(
            uuid=str(uuid.uuid4()),
            name="super",
            cluster_id=cluster.id
        )
        self.db.add(task)
        self.db.commit()

        kwargs = {
            'task_uuid': task.uuid,
            'status': 'ready',
        }

        receiver.deploy_resp(**kwargs)

        notifications = self.db.query(Notification).filter_by(
            cluster_id=cluster.id
        ).all()
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0].status, "unread")
        self.assertEqual(notifications[0].topic, "done")

    def test_notification_discover_no_node_fails(self):
        self.assertRaises(
            errors.CannotFindNodeIDForDiscovering,
            notifier.notify,
            "discover",
            "discover message")

    def test_notification_deploy_error(self):
        cluster = self.env.create_cluster(api=False)
        receiver = rcvr.NailgunReceiver()

        task = Task(
            uuid=str(uuid.uuid4()),
            name="super",
            cluster_id=cluster.id
        )
        self.db.add(task)
        self.db.commit()

        kwargs = {
            'task_uuid': task.uuid,
            'status': 'error',
        }

        receiver.deploy_resp(**kwargs)

        notifications = self.db.query(Notification).filter_by(
            cluster_id=cluster.id
        ).all()
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0].status, "unread")
        self.assertEqual(notifications[0].topic, "error")

    def test_notification_node_discover(self):

        resp = self.app.post(
            reverse('NodeCollectionHandler'),
            jsonutils.dumps({'mac': self.env.generate_random_mac(),
                             'meta': self.env.default_metadata(),
                             'status': 'discover'}),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 201)

        notifications = self.db.query(Notification).all()
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0].status, "unread")
        self.assertEqual(notifications[0].topic, "discover")

    def test_notification_delete_cluster_done(self):
        cluster = self.env.create_cluster(api=False)
        cluster_name = cluster.name
        receiver = rcvr.NailgunReceiver()

        task = Task(
            uuid=str(uuid.uuid4()),
            name="cluster_deletion",
            cluster_id=cluster.id
        )
        self.db.add(task)
        self.db.commit()

        kwargs = {
            'task_uuid': task.uuid,
            'status': 'ready',
        }

        receiver.remove_cluster_resp(**kwargs)

        notifications = self.db.query(Notification).all()
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0].status, "unread")
        self.assertEqual(notifications[0].topic, "done")
        self.assertEqual(
            notifications[0].message,
            "Environment '%s' and all its nodes "
            "are deleted" % cluster_name
        )

    def test_notification_delete_cluster_failed(self):
        cluster = self.env.create_cluster(api=False)
        receiver = rcvr.NailgunReceiver()

        task = Task(
            uuid=str(uuid.uuid4()),
            name="cluster_deletion",
            cluster_id=cluster.id
        )
        self.db.add(task)
        self.db.commit()

        kwargs = {
            'task_uuid': task.uuid,
            'status': 'error',
            'error': 'Cluster deletion fake error'
        }

        receiver.remove_cluster_resp(**kwargs)

        notifications = self.db.query(Notification).filter_by(
            cluster_id=cluster.id
        ).all()
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0].status, "unread")
        self.assertEqual(notifications[0].topic, "error")
        self.assertEqual(notifications[0].cluster_id, cluster.id)
        self.assertEqual(
            notifications[0].message,
            "Cluster deletion fake error"
        )
