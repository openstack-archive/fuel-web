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

import datetime
import mock

from nailgun import consts
from nailgun.db import db
from nailgun.db.sqlalchemy import models
from nailgun import errors
from nailgun.task.manager import DeploymentCheckMixin
from nailgun.task.task import ClusterTransaction

from nailgun.test.base import BaseTestCase


class TestDeploymentCheckMixin(BaseTestCase):

    def setUp(self):
        super(TestDeploymentCheckMixin, self).setUp()
        self.cluster = self.env.create()

    def test_fails_if_there_is_task(self):
        for task_name in DeploymentCheckMixin.deployment_tasks:
            task = models.Task(name=task_name, cluster_id=self.cluster.id)
            db.add(task)
            db.flush()
            self.assertRaisesWithMessage(
                errors.DeploymentAlreadyStarted,
                'Cannot perform the actions because there are '
                'running tasks {0}'.format([task]),
                DeploymentCheckMixin.check_no_running_deployment,
                self.cluster)

            db.query(models.Task).delete()

    def test_does_not_fail_if_there_is_deleted_task(self):
        for task_name in DeploymentCheckMixin.deployment_tasks:
            task = models.Task(name=task_name,
                               deleted_at=datetime.datetime.now(),
                               cluster_id=self.cluster.id)
            db.add(task)
            db.flush()
            self.addCleanup(db.query(models.Task).delete)

            self.assertNotRaises(
                errors.DeploymentAlreadyStarted,
                DeploymentCheckMixin.check_no_running_deployment,
                self.cluster)


class TestClusterTransaction(BaseTestCase):
    def test_get_cluster_state(self):
        deployments_info = {
            consts.MASTER_NODE_UID: {
                'uid': consts.MASTER_NODE_UID,
                'roles': [consts.TASK_ROLES.master],
                'key': 'value'
            }
        }
        self.assertEqual(
            {'key': 'value'},
            ClusterTransaction.get_cluster_state(deployments_info)
        )

        self.assertEqual({}, ClusterTransaction.get_cluster_state(None))
        self.assertEqual({}, ClusterTransaction.get_cluster_state({}))

    def test_is_node_for_redeploy(self):
        self.assertFalse(ClusterTransaction.is_node_for_redeploy(None))

        self.assertFalse(ClusterTransaction.is_node_for_redeploy(
            mock.MagicMock(status=consts.NODE_STATUSES.ready)
        ))
        self.assertTrue(ClusterTransaction.is_node_for_redeploy(
            mock.MagicMock(status=consts.NODE_STATUSES.provisioned)
        ))
        self.assertTrue(ClusterTransaction.is_node_for_redeploy(
            mock.MagicMock(status=consts.NODE_STATUSES.stopped)
        ))
        self.assertTrue(ClusterTransaction.is_node_for_redeploy(
            mock.MagicMock(status=consts.NODE_STATUSES.discover)
        ))

    @mock.patch('nailgun.objects.TransactionCollection')
    def test_get_current_state(self, trans_cls_mock):
        cluster = self.env.create(
            nodes_kwargs=[
                {"pending_addition": True,
                 'status': consts.NODE_STATUSES.ready},
                {"pending_addition": True,
                 'status': consts.NODE_STATUSES.ready},
                {"pending_addition": True,
                 'status': consts.NODE_STATUSES.provisioned},
            ],
            release_kwargs={
                'operating_system': consts.RELEASE_OS.ubuntu,
                'version': 'mitaka-9.0'
            },
        )

        nodes_ids = [n.uid for n in cluster.nodes]
        nodes_ids_with_master = nodes_ids + [consts.MASTER_NODE_UID]

        deployments_info = [
            {
                uid: {'uid': uid, 'version': version, 'roles': []}
                for uid in nodes_ids_with_master
            }
            for version in range(3)
        ]

        # delete info about node_ids[1] from deployment_info[1]
        # to check case when deployment_info for node does not found
        del deployments_info[1][nodes_ids[1]]

        transactions = [
            mock.MagicMock(deployment_info=x) for x in deployments_info
        ]
        tasks = [
            {'id': 'task1', 'type': consts.ORCHESTRATOR_TASK_TYPES.puppet},
            {'id': 'group1', 'type': consts.ORCHESTRATOR_TASK_TYPES.group},
            {'id': 'skipped1', 'type': consts.ORCHESTRATOR_TASK_TYPES.skipped},
            {'id': 'task2', 'type': consts.ORCHESTRATOR_TASK_TYPES.shell},
            {'id': 'task3', 'type': consts.ORCHESTRATOR_TASK_TYPES.reboot},
        ]

        trans_cls_mock.get_last_succeed_run.return_value = transactions[0]

        trans_cls_mock.get_successful_transactions_per_task.return_value = [
            (transactions[1], nodes_ids[0], tasks[0]['id']),
            (transactions[2], nodes_ids[2], tasks[3]['id']),
            (transactions[1], nodes_ids[1], tasks[0]['id']),
        ]

        state = ClusterTransaction.get_current_state(
            cluster, cluster.nodes, tasks
        )

        expected_state = {
            # cluster state from transaction[0]
            # it does not have info for node[1], see comment above
            tasks[0]['id']: {
                None: ClusterTransaction.get_cluster_state(
                    transactions[1].deployment_info
                ),
                nodes_ids[0]: transactions[1].deployment_info[nodes_ids[0]]
            },
            # cluster state from transaction[1]
            # the empty state for nodes[2], because it is provisioned
            tasks[3]['id']: {
                None: ClusterTransaction.get_cluster_state(
                    transactions[2].deployment_info
                ),
                nodes_ids[2]: {}
            },
            # contains only default state
            tasks[4]['id']: {
                None: ClusterTransaction.get_cluster_state(
                    transactions[0].deployment_info
                ),
            },
        }
        self.assertEqual(expected_state, state)
