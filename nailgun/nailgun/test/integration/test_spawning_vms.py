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

from oslo_serialization import jsonutils

from nailgun import consts
from nailgun import objects
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import fake_tasks
from nailgun.test.base import reverse


class TestSpawnVMs(BaseIntegrationTest):

    @fake_tasks(recover_nodes=False)
    def test_spawn_vms(self):
        self.env.create(
            nodes_kwargs=[
                {"status": "ready", "pending_addition": True,
                 "roles": ["virt"]},
            ]
        )
        cluster = self.env.clusters[0]
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
        self.assertEqual(task_deploy.status, consts.TASK_STATUSES.ready)

        self.assertEqual(len(task_deploy.subtasks), 2)

    def test_create_vms_conf(self):
        self.env.create(
            nodes_kwargs=[
                {"status": "ready", "pending_addition": True,
                 "roles": ["virt"]},
            ]
        )
        cluster = self.env.clusters[0]
        vms_conf = {"vms_conf": [{'id': 1, 'cluster_id': cluster.id}]}
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

    def test_spawn_vms_error(self):
        self.env.create(
            nodes_kwargs=[
                {"pending_addition": True,
                 "roles": ["compute"]},
            ]
        )
        cluster = self.env.clusters[0]

        resp = self.app.put(
            reverse(
                'SpawnVmsHandler',
                kwargs={'cluster_id': cluster.id}),
            headers=self.default_headers,
            expect_errors=True
        )

        self.assertEqual(resp.status_code, 400)

    @mock.patch("nailgun.task.manager.ApplyChangesTaskManager.execute")
    def test_openstack_config_call_apply_changes_if_lcm(self, execute_mock):
        self.env.create(
            release_kwargs={
                'version': 'liberty-9.0',
                'operating_system': consts.RELEASE_OS.ubuntu,
            },
            nodes_kwargs=[
                {"status": "ready", "roles": ["virt"]},
            ]
        )
        cluster = self.env.clusters[-1]
        cluster.nodes[0].vms_conf = [{'id': 1, 'cluster_id': cluster.id}]
        execute_mock.return_value = self.env.create_task(
            cluster_id=cluster.id,
            name=consts.TASK_NAMES.deployment,
            status=consts.TASK_STATUSES.ready
        )
        resp = self.app.put(
            reverse(
                'SpawnVmsHandler',
                kwargs={'cluster_id': cluster.id}),
            headers=self.default_headers,
        )
        self.assertEqual(200, resp.status_code)
        self.assertEqual(1, execute_mock.call_count)
