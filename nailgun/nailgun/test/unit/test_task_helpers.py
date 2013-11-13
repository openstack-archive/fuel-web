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


from nailgun.api.models import Cluster
from nailgun.orchestrator.deployment_serializers \
    import DeploymentHASerializer
from nailgun.task.helpers import TaskHelper
from nailgun.test.base import BaseUnitTest


class TestTaskHelpersNodesSelectionInCaseOfFailedNodes(BaseUnitTest):

    def create_env(self, nodes):
        cluster = self.env.create(
            cluster_kwargs={
                'mode': 'ha_compact'},
            nodes_kwargs=nodes)

        cluster_db = self.db.query(Cluster).get(cluster['id'])
        TaskHelper.prepare_for_deployment(cluster_db.nodes)
        return cluster_db

    @property
    def serializer(self):
        return DeploymentHASerializer

    def filter_by_role(self, nodes, role):
        return filter(lambda node: role in node.all_roles, nodes)

    def test_redeploy_all_controller_if_single_controller_failed(self):
        cluster = self.create_env([
            {'roles': ['controller'], 'status': 'error'},
            {'roles': ['controller']},
            {'roles': ['controller', 'cinder']},
            {'roles': ['compute', 'cinder']},
            {'roles': ['compute']},
            {'roles': ['cinder']}])

        nodes = TaskHelper.nodes_to_deploy(cluster)
        self.assertEquals(len(nodes), 3)

        controllers = self.filter_by_role(nodes, 'controller')
        self.assertEquals(len(controllers), 3)

    def test_redeploy_only_compute_cinder(self):
        cluster = self.create_env([
            {'roles': ['controller']},
            {'roles': ['controller']},
            {'roles': ['controller', 'cinder']},
            {'roles': ['compute', 'cinder']},
            {'roles': ['compute'], 'status': 'error'},
            {'roles': ['cinder'], 'status': 'error'}])

        nodes = TaskHelper.nodes_to_deploy(cluster)
        self.assertEquals(len(nodes), 2)

        cinders = self.filter_by_role(nodes, 'cinder')
        self.assertEquals(len(cinders), 1)

        computes = self.filter_by_role(nodes, 'compute')
        self.assertEquals(len(computes), 1)

    def test_redeploy_all_controller_and_compute_cinder(self):
        cluster = self.create_env([
            {'roles': ['controller'], 'status': 'error'},
            {'roles': ['controller']},
            {'roles': ['controller', 'cinder']},
            {'roles': ['compute', 'cinder']},
            {'roles': ['compute'], 'status': 'error'},
            {'roles': ['cinder'], 'status': 'error'}])

        nodes = TaskHelper.nodes_to_deploy(cluster)
        self.assertEquals(len(nodes), 5)

        controllers = self.filter_by_role(nodes, 'controller')
        self.assertEquals(len(controllers), 3)

        cinders = self.filter_by_role(nodes, 'cinder')
        self.assertEquals(len(cinders), 2)

        computes = self.filter_by_role(nodes, 'compute')
        self.assertEquals(len(computes), 1)
