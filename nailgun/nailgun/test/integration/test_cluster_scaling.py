#    Copyright 2014 Mirantis, Inc.
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

from mock import patch

import nailgun

from nailgun.test.base import BaseIntegrationTest
from nailgun.db.sqlalchemy.models import Cluster
from nailgun.test.base import fake_tasks
from nailgun.task.helpers import TaskHelper
from nailgun.logger import logger

class TestClusterScaling(BaseIntegrationTest):
    '''
    Test Cases That are used to ensure that nailgun supports Scaling
     Operations
    '''

    def create_env(self, nodes_kwargs):
        cluster = self.env.create(
            nodes_kwargs=nodes_kwargs)

        cluster_db = self.db.query(Cluster).get(cluster['id'])
        return cluster_db

    def filter_by_role(self, nodes, role):
        return filter(lambda node: role in node.all_roles, nodes)

    @fake_tasks()
    def test_deploy_single_controller(self):
        self.create_env(
            nodes_kwargs=[
                {'roles': ['controller'], 'pending_addition': True}
                ]
            )

        supertask = self.env.launch_deployment()
        self.assertEquals(supertask.name, 'deploy')

        self.env.wait_ready(supertask)
        self.assertEquals(supertask.status, 'ready')

    @fake_tasks()
    def test_deploy_grow_controllers(self):
        cluster = self.create_env(
            nodes_kwargs=[
                {'roles': ['controller']},
                {'roles': ['controller'], 'pending_addition': True},
                {'roles': ['controller'], 'pending_addition': True}
                ]
            )

        # We have to build 2 new controllers
        n_nodes = TaskHelper.nodes_to_provision(cluster)
        self.assertEquals(len(n_nodes), 2)

        # All controllers must re-deploy (run puppet)
        r_nodes = TaskHelper.nodes_to_deploy(cluster)
        self.assertEquals(len(r_nodes), 3)

        supertask = self.env.launch_deployment()
        self.assertEquals(supertask.name, 'deploy')

        self.env.wait_ready(supertask)
        self.assertEquals(supertask.status, 'ready')

        controllers = self.filter_by_role(cluster.nodes, 'controller')
        self.assertEquals(len(controllers), 3)

    @fake_tasks()
    def test_deploy_shrink_controllers(self):
        cluster = self.create_env(
            nodes_kwargs=[
                {'roles': ['controller']},
                {'roles': ['controller'], 'pending_deletion': True},
                {'roles': ['controller'], 'pending_deletion': True}
                ]
            )

        # Check that we are deleting 2 controllers
        d_nodes = TaskHelper.nodes_to_delete(cluster)
        self.assertEquals(len(d_nodes), 2)

        supertask = self.env.launch_deployment()
        self.assertEquals(supertask.name, 'deploy')

        self.env.wait_ready(supertask)
        self.assertEquals(supertask.status, 'ready')

        controllers = self.filter_by_role(cluster.nodes, 'controller')
        self.assertEquals(len(controllers), 1)
