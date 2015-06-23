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

import mock

from oslo.serialization import jsonutils

from nailgun.db.sqlalchemy import models
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import fake_tasks
from nailgun.test.base import reverse


class TestPredeploymentDeployment(BaseIntegrationTest):

    @fake_tasks(recover_nodes=False)
    @mock.patch('nailgun.orchestrator.tasks_serializer.open', create=True)
    def test_predeployment(self, m_open):
        m_open.side_effect = lambda *args: mock.mock_open(
            read_data='<tag>{cluster_id}</tag><tag>{name}</tag>'
            '<tag>{empty_value}</tag>')()
        self.env.create(
            nodes_kwargs=[
                {"status": "ready", "pending_addition": True},
            ]
        )
        cluster = self.env.clusters[0]
        resp = self.app.put(
            reverse('NodeCollectionHandler'),
            jsonutils.dumps([{'id': cluster.nodes[0].id,
                              'roles': ['kvm-virt'],
                              'meta': {
                                  'vms_confs': [{
                                      'id': 1,
                                      'cluster_id': cluster.id}]}}]),
            headers=self.default_headers
        )
        self.assertEqual(resp.status_code, 200)

        resp = self.app.put(
            reverse(
                'PrepareDeployHandler',
                kwargs={'cluster_id': cluster.id}),
            headers=self.default_headers
        )
        deploy_uuid = resp.json_body['uuid']

        task_deploy = self.db.query(models.Task).filter_by(
            uuid=deploy_uuid
        ).first()
        self.assertTrue(task_deploy)
