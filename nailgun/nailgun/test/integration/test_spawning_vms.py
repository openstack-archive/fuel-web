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

from oslo_serialization import jsonutils

from nailgun import consts
from nailgun import objects
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import mock_rpc
from nailgun.test.base import reverse


class TestSpawnVMs(BaseIntegrationTest):

    @mock_rpc()
    def test_spawn_vms(self):
        cluster = self.env.create(
            nodes_kwargs=[
                {"status": "ready", "pending_addition": True,
                 "roles": ["virt"]},
            ]
        )
        cluster.nodes[0].vms_conf = [{'id': 1, 'cluster_id': cluster.id}]

        resp = self.app.put(
            reverse(
                'SpawnVmsHandler',
                kwargs={'cluster_id': cluster.id}),
            headers=self.default_headers
        )
        deploy_uuid = resp.json_body['uuid']

        task_deploy = objects.Task.get_by_uuid(deploy_uuid)
        self.assertEqual(task_deploy.name, consts.TASK_NAMES.spawn_vms)
        self.assertNotEqual(task_deploy.status, consts.TASK_STATUSES.error)

        self.assertEqual(len(task_deploy.subtasks), 2)

    def test_spawn_vms_w_custom_graph(self):
        self.env.create(
            nodes_kwargs=[
                {"status": "ready", "pending_addition": True,
                 "pending_roles": ["virt"]},
            ]
        )
        cluster = self.env.clusters[0]
        objects.DeploymentGraph.create_for_model(
            {'tasks': [
                {
                    'id': 'generate_vms',
                    'version': '2.0.0',
                    'type': 'puppet',
                    'groups': ['virt'],
                    'parameters': {
                        'puppet_manifest': '/etc/puppet/modules/osnailyfacter/'
                                           'modular/cluster/generate_vms.pp',
                        'puppet_modules': '/etc/puppet/modules',
                        'timeout': '3600'
                    }
                },
                {
                    'id': 'custom-task',
                    'version': '2.0.0',
                    'type': 'puppet',
                    'requires': ['generate_vms'],
                    'groups': ['virt'],
                    'parameters': {
                        'puppet_manifest': '/etc/puppet/modules/osnailyfacter/'
                                           'modular/cluster/smth.pp',
                        'puppet_modules': '/etc/puppet/modules',
                    }
                }
            ]}, cluster.release, 'custom-graph')

        cluster.nodes[0].vms_conf = [{'id': 1, 'cluster_id': cluster.id}]

        resp = self.app.put(
            reverse(
                'SpawnVmsHandler',
                kwargs={'cluster_id': cluster.id}
            ) + '?graph_type=custom-graph',
            headers=self.default_headers
        )
        deploy_uuid = resp.json_body['uuid']

        supertask = objects.Task.get_by_uuid(deploy_uuid)
        deployment_task = next(
            t for t in supertask.subtasks
            if t.name == consts.TASK_NAMES.deployment
        )
        custom_task_found = bool(next(
            (dt for dt in deployment_task.deployment_history
             if dt.deployment_graph_task_name == 'custom-task'),
            False
        ))
        self.assertTrue(custom_task_found)

    def test_create_vms_conf(self):
        cluster = self.env.create(
            nodes_kwargs=[
                {"status": "ready", "pending_addition": True,
                 "roles": ["virt"]},
            ]
        )
        vms_conf = {"vms_conf": [
            {'id': 1, 'cpu': 1, 'mem': 1}]
        }
        self.app.put(
            reverse(
                'NodeVMsHandler',
                kwargs={'node_id': cluster.nodes[0].id}),
            jsonutils.dumps(vms_conf),
            headers=self.default_headers
        )
        spawning_nodes = self.app.get(
            reverse(
                'NodeVMsHandler',
                kwargs={'node_id': cluster.nodes[0].id}),
            headers=self.default_headers
        )
        self.assertEqual(spawning_nodes.json, vms_conf)

    def test_create_vms_conf_failure(self):
        cluster = self.env.create(
            nodes_kwargs=[
                {"status": "ready", "pending_addition": True,
                 "roles": ["virt"]},
            ]
        )
        vms_conf = {"vms_conf": [
            {'cpu': 1}
        ]}
        resp = self.app.put(
            reverse(
                'NodeVMsHandler',
                kwargs={'node_id': cluster.nodes[0].id}),
            jsonutils.dumps(vms_conf),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("'id' is a required property", resp.json_body['message'])

    def test_spawn_vms_error(self):
        cluster = self.env.create(
            nodes_kwargs=[
                {"pending_addition": True,
                 "roles": ["compute"]},
            ]
        )

        resp = self.app.put(
            reverse(
                'SpawnVmsHandler',
                kwargs={'cluster_id': cluster.id}),
            headers=self.default_headers,
            expect_errors=True
        )

        self.assertEqual(resp.status_code, 400)
