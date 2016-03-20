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

from nailgun import consts
from nailgun.db.sqlalchemy import models
from nailgun.rpc.receiver import NailgunReceiver
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import fake_tasks
from nailgun.utils import reverse


class TestCharsetIssues(BaseIntegrationTest):

    @fake_tasks(override_state={"progress": 100, "status": "ready"})
    # (mihgen): Can't we do unit tests instead.. ?
    def test_deployment_cyrillic_names(self):
        self.env.create(
            cluster_kwargs={"name": u"Тестовый кластер"},
            nodes_kwargs=[
                {"name": u"Контроллер", "pending_addition": True},
                {"name": u"Компьют", "pending_addition": True},
                {"pending_deletion": True},
            ]
        )
        supertask = self.env.launch_deployment()

        self.assertEqual(supertask.name, consts.TASK_NAMES.deploy)
        self.assertEqual(supertask.status, consts.TASK_STATUSES.ready)
        # we have three subtasks here
        # repo connectivity check
        # deletion
        # provision
        # deployment
        self.assertEqual(len(supertask.subtasks), 3)

    @fake_tasks(fake_rpc=False)
    def test_deletion_during_deployment(self, mock_rpc):
        self.env.create(
            cluster_kwargs={
                "name": u"Вася"
            },
            nodes_kwargs=[
                {"status": "ready", "pending_addition": True},
            ]
        )
        cluster_id = self.env.clusters[0].id
        resp = self.app.put(
            reverse(
                'ClusterChangesHandler',
                kwargs={'cluster_id': cluster_id}),
            headers=self.default_headers
        )
        deploy_uuid = resp.json_body['uuid']
        NailgunReceiver.provision_resp(
            task_uuid=deploy_uuid,
            status=consts.TASK_STATUSES.running,
            progress=50,
        )

        self.app.delete(
            reverse(
                'ClusterHandler',
                kwargs={'obj_id': cluster_id}),
            headers=self.default_headers
        )
        task_delete = self.db.query(models.Task).filter_by(
            cluster_id=cluster_id,
            name="cluster_deletion"
        ).first()
        NailgunReceiver.remove_cluster_resp(
            task_uuid=task_delete.uuid,
            status=consts.TASK_STATUSES.ready,
            progress=100,
        )

        cluster = self.db.query(models.Cluster).filter_by(
            id=cluster_id).first()
        self.assertIsNone(cluster)
