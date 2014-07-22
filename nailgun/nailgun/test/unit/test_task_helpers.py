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


from nailgun.db.sqlalchemy.models import Cluster
from nailgun.db.sqlalchemy.models import Task

from nailgun import objects

from nailgun.orchestrator.deployment_serializers \
    import DeploymentHASerializer
from nailgun.task.helpers import TaskHelper
from nailgun.test.base import BaseTestCase


class TestTaskHelpers(BaseTestCase):

    def create_env(self, nodes):
        cluster = self.env.create(
            nodes_kwargs=nodes)

        cluster_db = self.db.query(Cluster).get(cluster['id'])
        objects.NodeCollection.prepare_for_deployment(cluster_db.nodes)
        self.db.flush()
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
        self.assertEqual(len(nodes), 3)

        controllers = self.filter_by_role(nodes, 'controller')
        self.assertEqual(len(controllers), 3)

    def test_redeploy_only_compute_cinder(self):
        cluster = self.create_env([
            {'roles': ['controller']},
            {'roles': ['controller']},
            {'roles': ['controller', 'cinder']},
            {'roles': ['compute', 'cinder']},
            {'roles': ['compute'], 'status': 'error'},
            {'roles': ['cinder'], 'status': 'error'}])

        nodes = TaskHelper.nodes_to_deploy(cluster)
        self.assertEqual(len(nodes), 2)

        cinders = self.filter_by_role(nodes, 'cinder')
        self.assertEqual(len(cinders), 1)

        computes = self.filter_by_role(nodes, 'compute')
        self.assertEqual(len(computes), 1)

    def test_redeploy_all_controller_and_compute_cinder(self):
        cluster = self.create_env([
            {'roles': ['controller'], 'status': 'error'},
            {'roles': ['controller']},
            {'roles': ['controller', 'cinder']},
            {'roles': ['compute', 'cinder']},
            {'roles': ['compute'], 'status': 'error'},
            {'roles': ['cinder'], 'status': 'error'}])

        nodes = TaskHelper.nodes_to_deploy(cluster)
        self.assertEqual(len(nodes), 5)

        controllers = self.filter_by_role(nodes, 'controller')
        self.assertEqual(len(controllers), 3)

        cinders = self.filter_by_role(nodes, 'cinder')
        self.assertEqual(len(cinders), 2)

        computes = self.filter_by_role(nodes, 'compute')
        self.assertEqual(len(computes), 1)

    def test_redeploy_with_critial_roles(self):
        cluster = self.create_env([
            {'roles': ['controller'], 'status': 'error'},
            {'roles': ['controller'], 'status': 'provisioned'},
            {'roles': ['controller'], 'status': 'provisioned'},
            {'roles': ['compute', 'cinder'], 'status': 'provisioned'},
            {'roles': ['compute'], 'status': 'provisioned'},
            {'roles': ['cinder'], 'status': 'provisioned'}])

        nodes = TaskHelper.nodes_to_deploy(cluster)
        self.assertEqual(len(nodes), 6)

        controllers = self.filter_by_role(nodes, 'controller')
        self.assertEqual(len(controllers), 3)

        cinders = self.filter_by_role(nodes, 'cinder')
        self.assertEqual(len(cinders), 2)

        computes = self.filter_by_role(nodes, 'compute')
        self.assertEqual(len(computes), 2)

    # TODO(aroma): move it to utils testing code
    def test_recalculate_deployment_task_progress(self):
        cluster = self.create_env([
            {'roles': ['controller'],
             'status': 'provisioned',
             'progress': 100},
            {'roles': ['compute'],
             'status': 'deploying',
             'progress': 100},
            {'roles': ['compute'],
             'status': 'ready',
             'progress': 0},
            {'roles': ['compute'],
             'status': 'discover',
             'progress': 0}])

        task = Task(name='deploy', cluster_id=cluster.id)
        self.db.add(task)
        self.db.commit()

        progress = TaskHelper.recalculate_deployment_task_progress(task)
        self.assertEqual(progress, 25)

    # TODO(aroma): move it to utils testing code
    def test_recalculate_provisioning_task_progress(self):
        cluster = self.create_env([
            {'roles': ['controller'],
             'status': 'provisioned',
             'progress': 100},
            {'roles': ['compute'],
             'status': 'provisioning',
             'progress': 0}])

        task = Task(name='provision', cluster_id=cluster.id)
        self.db.add(task)
        self.db.commit()

        progress = TaskHelper.recalculate_provisioning_task_progress(task)
        self.assertEqual(progress, 50)
