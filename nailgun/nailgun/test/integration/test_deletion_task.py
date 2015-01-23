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


import mock

from nailgun import consts
from nailgun.db import db
from nailgun.db.sqlalchemy import models
from nailgun.task.task import DeletionTask
from nailgun.test.base import BaseIntegrationTest


class TestDeletionTask(BaseIntegrationTest):

    def test_get_task_nodes(self):
        cluster = self.env.create_cluster(api=True)
        cluster_db = self.db.query(models.Cluster).get(cluster['id'])

        nodes = DeletionTask.get_nodes_for_cluster(cluster_db)

        self.assertEqual(len(nodes['nodes_to_delete']), 0)
        self.assertEqual(len(nodes['nodes_to_restore']), 0)

        self.env.create_node(
            api=False,
            cluster_id=cluster_db.id,
            pending_deletion=True,
            status='ready',
            meta=self.env.default_metadata())

        nodes = DeletionTask.get_nodes_for_cluster(cluster_db)

        self.assertEqual(len(nodes['nodes_to_delete']), 1)
        self.assertEqual(len(nodes['nodes_to_restore']), 0)

    def test_undeployed_node_removal(self):
        cluster = self.env.create_cluster(api=True)
        cluster_db = self.db.query(models.Cluster).get(cluster['id'])
        self.env.create_node(
            api=False,
            cluster_id=cluster_db.id,
            pending_deletion=True,
            status='discover',
            meta=self.env.default_metadata())

        nodes = DeletionTask.get_nodes_for_cluster(cluster_db)

        self.assertEqual(len(nodes['nodes_to_delete']), 1)
        self.assertEqual(len(nodes['nodes_to_restore']), 0)

        ret = DeletionTask.remove_undeployed_nodes_from_db(
            nodes['nodes_to_delete']
        )

        self.assertEqual(len(cluster_db.nodes), 0)
        self.assertEqual(len(ret), 0)

    @mock.patch('nailgun.task.task.rpc')
    @mock.patch('nailgun.task.task.make_astute_message')
    @mock.patch('nailgun.task.task.DeletionTask.'
                'remove_undeployed_nodes_from_db')
    def test_undeployed_node_called(
            self,
            mremove_undeployed_nodes_from_db,
            mmake_astute_message,
            mrpc):
        cluster = self.env.create_cluster(api=True)
        cluster_db = self.db.query(models.Cluster).get(cluster['id'])
        self.env.create_node(
            api=False,
            cluster_id=cluster_db.id,
            pending_deletion=True,
            status='discover',
            meta=self.env.default_metadata())

        nodes = DeletionTask.get_nodes_for_cluster(cluster_db)

        self.assertEqual(len(nodes['nodes_to_delete']), 1)
        self.assertEqual(len(nodes['nodes_to_restore']), 0)

        task = models.Task(
            name=consts.TASK_NAMES.cluster_deletion,
            cluster=cluster_db
        )
        db().add(task)
        db().commit()

        mremove_undeployed_nodes_from_db.return_value = []
        DeletionTask.execute(task, nodes=nodes)

        mremove_undeployed_nodes_from_db.assert_called_once_with(
            nodes['nodes_to_delete'])
        self.assertEqual(mmake_astute_message.call_count, 1)
        self.assertEqual(mrpc.cast.call_count, 1)

    @mock.patch('nailgun.task.task.rpc')
    @mock.patch('nailgun.task.task.make_astute_message')
    def test_astute_message_creation(self, mmake_astute_message, mrpc):
        cluster = self.env.create_cluster(api=True)
        cluster_db = self.db.query(models.Cluster).get(cluster['id'])
        # 'discover' node is not deployed yet -- it will be removed
        # immediately
        n_discover = self.env.create_node(
            api=False,
            cluster_id=cluster_db.id,
            pending_deletion=True,
            status='discover',
            meta=self.env.default_metadata())
        # 'ready' node is deployed -- astute will take care of it
        self.env.create_node(
            api=False,
            cluster_id=cluster_db.id,
            pending_deletion=True,
            status='ready',
            meta=self.env.default_metadata())
        # 'offline' node will also be passed to astute
        self.env.create_node(
            api=False,
            cluster_id=cluster_db.id,
            pending_deletion=True,
            online=False,
            status='ready',
            meta=self.env.default_metadata())

        nodes = DeletionTask.get_nodes_for_cluster(cluster_db)
        astute_nodes = [node for node in nodes['nodes_to_delete']
                        if node['id'] != n_discover.id]

        self.assertEqual(len(nodes['nodes_to_delete']), 3)
        self.assertEqual(len(nodes['nodes_to_restore']), 0)

        task = models.Task(
            name=consts.TASK_NAMES.cluster_deletion,
            cluster=cluster_db
        )
        db().add(task)
        db().commit()

        DeletionTask.execute(task, nodes=nodes)

        self.assertEqual(mmake_astute_message.call_count, 1)
        message = mmake_astute_message.call_args[0][3]

        self.assertIn('nodes', message)
        self.assertItemsEqual(message['nodes'], astute_nodes)

        self.assertEqual(mrpc.cast.call_count, 1)
