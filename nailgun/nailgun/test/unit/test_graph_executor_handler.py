#    Copyright 2016 Mirantis, Inc.
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

from oslo_serialization import jsonutils

from nailgun import consts
from nailgun import errors

from nailgun.test import base
from nailgun.utils import reverse


@mock.patch("nailgun.api.v1.handlers.base.transactions.TransactionsManager")
class TestGraphExecutorHandler(base.BaseTestCase):

    def setUp(self):
        super(TestGraphExecutorHandler, self).setUp()
        self.cluster = self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"status": consts.NODE_STATUSES.discover},
                {"status": consts.NODE_STATUSES.provisioned},
                {"status": consts.NODE_STATUSES.ready}
            ],
            release_kwargs={
                'version': 'mitaka-9.0',
                'operating_system': consts.RELEASE_OS.ubuntu
            }
        )

    def test_execute_for_selected_nodes(self, tx_manager_mock):
        task = self.env.create_task(
            cluster_id=self.cluster.id, status=consts.TASK_STATUSES.pending
        )
        tx_manager_mock().execute.return_value = task

        resp = self.app.post(
            reverse('GraphsExecutorHandler'),
            params=jsonutils.dumps(
                {
                    "cluster": self.cluster.id,
                    "graphs": [{
                        "type": "graph1",
                        "nodes": [self.cluster.nodes[0].id],
                    }],
                    "dry_run": False,
                    "force": False
                }
            ),
            headers=self.default_headers
        )
        self.assertEqual(202, resp.status_code)
        self.assertEqual(task.id, resp.json_body['id'])
        tx_manager_mock.assert_called_with(self.cluster.id)
        tx_manager_mock().execute.assert_called_once_with(
            graphs=[{
                "type": "graph1",
                "nodes": [self.env.nodes[0].id]
            }],
            dry_run=False,
            force=False
        )

    def test_execute_for_all_nodes(self, tx_manager_mock):
        task = self.env.create_task(
            cluster_id=self.cluster.id, status=consts.TASK_STATUSES.pending
        )
        tx_manager_mock().execute.return_value = task

        resp = self.app.post(
            reverse('GraphsExecutorHandler'),
            params=jsonutils.dumps(
                {
                    "cluster": self.cluster.id,
                    "graphs": [{"type": "graph1"}],
                    "dry_run": True,
                    "force": True
                }
            ),
            headers=self.default_headers
        )
        self.assertEqual(202, resp.status_code)
        self.assertEqual(task.id, resp.json_body['id'])
        tx_manager_mock.assert_called_with(self.cluster.id)
        tx_manager_mock().execute.assert_called_once_with(
            graphs=[{"type": "graph1"}],
            dry_run=True,
            force=True
        )

    def test_execute_fail_if_nodes_not_in_same_cluster(self, _):
        node = self.env.create_node(
            api=False, status=consts.NODE_STATUSES.discover
        )
        resp = self.app.post(
            reverse('GraphsExecutorHandler'),
            params=jsonutils.dumps(
                {
                    "graphs": [{
                        "type": "graph1",
                        "nodes": [self.cluster.nodes[0].uid, node.uid],
                    }],
                    "dry_run": True,
                    "force": True
                }
            ),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(400, resp.status_code)

    def test_execute_handle_exception_of_transaction(self, tx_manager_mock):
        tx_manager_mock().execute.side_effect = [
            errors.ObjectNotFound, errors.DeploymentAlreadyStarted
        ]

        for expected_code in (404, 409):
            resp = self.app.post(
                reverse('GraphsExecutorHandler'),
                params=jsonutils.dumps(
                    {
                        "cluster": self.cluster.id,
                        "graphs": [{"type": "graph1"}],
                        "dry_run": True,
                        "force": True
                    }
                ),
                headers=self.default_headers,
                expect_errors=True
            )
            self.assertEqual(expected_code, resp.status_code)
