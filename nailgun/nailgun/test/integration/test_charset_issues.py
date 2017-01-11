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
from nailgun.rpc.receiver import NailgunReceiver
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import mock_rpc
from nailgun.utils import reverse


class TestCharsetIssues(BaseIntegrationTest):

    @mock_rpc()
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
        self.assertNotEqual(supertask.status, consts.TASK_STATUSES.error)
        # we have three subtasks here
        # repo connectivity check
        # deletion
        # provision
        # deployment
        self.assertEqual(len(supertask.subtasks), 3)

    @mock_rpc()
    def test_deletion_during_deployment(self):
        cluster = self.env.create(
            cluster_kwargs={
                "name": u"Вася"
            },
            nodes_kwargs=[
                {"status": "ready", "pending_addition": True},
            ]
        )
        resp = self.app.put(
            reverse(
                'ClusterChangesHandler',
                kwargs={'cluster_id': cluster.id}),
            headers=self.default_headers
        )
        deploy_uuid = resp.json_body['uuid']
        NailgunReceiver.provision_resp(
            task_uuid=deploy_uuid,
            status=consts.TASK_STATUSES.running,
            progress=50,
        )

        resp = self.app.delete(
            reverse(
                'ClusterHandler',
                kwargs={'obj_id': cluster.id}),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(400, resp.status_code)
