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

from mock import patch

from nailgun import consts
from nailgun.db.sqlalchemy.models import DeploymentGraphTask
from nailgun.orchestrator.tasks_templates import make_generic_task
from nailgun.task.manager import OpenstackConfigTaskManager
from nailgun.test import base
from nailgun.test.base import fake_tasks


class TestOpenstackConfigTaskManager80(base.BaseIntegrationTest):

    env_version = "liberty-8.0"

    def setUp(self):
        super(TestOpenstackConfigTaskManager80, self).setUp()

        self.env.create(
            cluster_kwargs={'net_provider': 'neutron',
                            'net_segment_type': 'gre'},
            release_kwargs={'version': self.env_version,
                            'operating_system': consts.RELEASE_OS.ubuntu},
            nodes_kwargs=[
                {'roles': ['controller'], 'status': 'ready'},
                {'roles': ['compute'], 'status': 'ready'},
                {'roles': ['compute'], 'status': 'ready'},
                {'roles': ['compute'], 'pending_addition': True},
            ]
        )

        self.release = self.env.releases[0]
        self.cluster = self.env.clusters[0]
        self.nodes = self.env.nodes

        # this mock configuration is used to insert into DB
        self.refreshable_task = {
            'task_name': 'test_task',
            'type': 'puppet',
            'groups': ['primary-controller', 'controller'],
            'refresh_on': ['keystone_config'],
            'parameters': {},
        }

        # add refreshable deployment task
        task = DeploymentGraphTask(**self.refreshable_task)
        deployment_graph_assoc = self.release.deployment_graphs.first()
        deployment_graph_assoc.deployment_graph.tasks.append(task)

        self.db().flush()
        # this field is expected to be added for compatibility
        self.refreshable_task['id'] = 'test_task'
        self.env.create_openstack_config(
            cluster_id=self.cluster.id,
            configuration={
                'keystone_config': {'param_a': 'cluster'},
            })
        self.env.create_openstack_config(
            cluster_id=self.cluster.id,
            node_id=self.env.nodes[0].id,
            configuration={
                'keystone_config': {'param_a': 'node_1'},
                'nova_config': {'param_a': 'node_1'},
            })
        self.env.create_openstack_config(
            cluster_id=self.cluster.id,
            node_role='compute',
            configuration={
                'keystone_config': {},
            })

    @fake_tasks(fake_rpc=False, mock_rpc=False)
    @patch('nailgun.rpc.cast')
    def test_configuration_execute(self, mocked_rpc):
        task_manager = OpenstackConfigTaskManager(self.cluster.id)
        task = task_manager.execute({'cluster_id': self.cluster.id})

        self.assertEqual(task.status, consts.TASK_STATUSES.pending)

        all_node_ids = [n.id for n in self.env.nodes[:3]]
        self.assertItemsEqual(task.cache['nodes'], all_node_ids)

        tasks = mocked_rpc.call_args[0][1]['args']['tasks']
        # 3 tasks for all ready nodes with cluster config
        # 1 task for node[0] with node specific config
        # 2 tasks (1 per each compute node)
        # 1 deployment task
        self.assertEqual(len(tasks), 7)

        cluster_uids = []
        role_uids = []
        node_uids = []
        deployment_tasks = []
        for task in tasks:
            if task['type'] == 'upload_file':
                if '/cluster' in task['parameters']['path']:
                    cluster_uids.extend(task['uids'])
                if '/role' in task['parameters']['path']:
                    role_uids.extend(task['uids'])
                if '/node' in task['parameters']['path']:
                    node_uids.extend(task['uids'])
            else:
                deployment_tasks.append(task)

        self.assertItemsEqual(cluster_uids, map(str, all_node_ids))
        self.assertItemsEqual(role_uids,
                              [self.nodes[1].uid, self.nodes[2].uid])
        self.assertItemsEqual([self.nodes[0].uid], node_uids)
        self.assertItemsEqual(deployment_tasks, [
            make_generic_task([self.nodes[0].uid], self.refreshable_task)])


class TestOpenstackConfigTaskManager90(TestOpenstackConfigTaskManager80):
    env_version = "liberty-8.0"
