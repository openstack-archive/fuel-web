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

from contextlib import nested

from mock import Mock
from mock import patch

from nailgun.db.sqlalchemy.models import Cluster
from nailgun.task.task import DeletionTask
from nailgun.test.base import BaseIntegrationTest


class TestDeletionTask(BaseIntegrationTest):

    def test_get_task_nodes(self):
        cluster = self.env.create_cluster(api=True)
        cluster_db = self.db.query(Cluster).get(cluster['id'])

        nodes = DeletionTask.get_task_nodes(
            DeletionTask.get_nodes_for_cluster(cluster_db))

        self.assertEqual(len(nodes['nodes_to_delete']), 0)
        self.assertEqual(len(nodes['nodes_to_restore']), 0)

        node = self.env.create_node(
            api=False,
            cluster=cluster,
            pending_deletion=True)

        nodes = DeletionTask.get_task_nodes(
            DeletionTask.get_nodes_for_cluster(cluster_db))

        self.assertEqual(len(nodes['nodes_to_delete']), 1)
        self.assertEqual(len(nodes['nodes_to_restore']), 0)
