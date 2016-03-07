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

from nailgun import consts
from nailgun.errors import errors
from nailgun.objects import Task
from nailgun.orchestrator.task_based_deployment import TaskProcessor
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import fake_tasks
from nailgun.utils import reverse


class TestTaskDeploy(BaseIntegrationTest):
    def setUp(self):
        super(TestTaskDeploy, self).setUp()
        self.env.create(
            api=False,
            nodes_kwargs=[
                {"name": "First",
                 "pending_addition": True},
                {"name": "Second",
                 "roles": ["compute"],
                 "pending_addition": True}
            ],
            release_kwargs={
                'operating_system': consts.RELEASE_OS.ubuntu,
                'version': '2015.1.0-8.0',
            },
        )
        self.cluster = self.env.clusters[-1]

    def add_plugin_with_tasks(self, task_id):
        deployment_tasks = self.env.get_default_plugin_deployment_tasks(
            id=task_id, type="skipped",
            role=["compute"]
        )
        tasks = self.env.get_default_plugin_tasks(
            role=["compute"]
        )
        tasks.extend(self.env.get_default_plugin_tasks(
            role=["compute"], stage="pre_deployment"
        ))
        self.env.create_plugin(
            cluster=self.cluster,
            enabled=True,
            package_version="4.0.0",
            deployment_tasks=deployment_tasks, tasks=tasks
        )
        self.db.flush()

    @fake_tasks(mock_rpc=True, fake_rpc=False)
    def get_deploy_message(self, rpc_cast):
        task = self.env.launch_deployment(self.cluster.id)
        self.assertNotEqual(consts.TASK_STATUSES.error, task.status)
        args, kwargs = rpc_cast.call_args
        return args[1][1]

    @mock.patch.object(TaskProcessor, "ensure_task_based_deploy_allowed")
    def test_task_deploy_used_by_default(self, _):
        message = self.get_deploy_message()
        self.assertEqual("task_deploy", message["method"])
        self.assertItemsEqual(
            ["task_uuid", "deployment_info",
             "tasks_directory", "tasks_graph"],
            message["args"]
        )

    @mock.patch.object(TaskProcessor, "ensure_task_based_deploy_allowed")
    def test_fallback_to_granular_deploy(self, ensure_allowed):
        ensure_allowed.side_effect = errors.TaskBaseDeploymentNotAllowed
        message = self.get_deploy_message()
        self.assertEqual("granular_deploy", message["method"])
        self.assertItemsEqual(
            ["task_uuid", "deployment_info",
             "pre_deployment", "post_deployment"],
            message["args"]
        )
        ensure_allowed.assert_called_once_with(mock.ANY)

    def test_granular_deploy_if_not_enabled(self):
        self.env.disable_task_deploy(self.cluster)
        message = self.get_deploy_message()
        self.assertEqual("granular_deploy", message["method"])
        self.assertItemsEqual(
            ["task_uuid", "deployment_info",
             "pre_deployment", "post_deployment"],
            message["args"]
        )

    @mock.patch.object(TaskProcessor, "ensure_task_based_deploy_allowed")
    @mock.patch('nailgun.plugins.adapters.os.path.exists', return_value=True)
    @mock.patch('nailgun.plugins.adapters.PluginAdapterBase._load_tasks')
    def test_task_deploy_with_plugins(self, load_tasks, *_):
        self.add_plugin_with_tasks("plugin_deployment_task")
        # There is bug[1] in PluginAdapters,
        # it always reads the tasks from local file sytem.
        # [1] https://bugs.launchpad.net/fuel/+bug/1527320
        load_tasks.return_value = self.env.plugins[-1].tasks
        message = self.get_deploy_message()
        compute_uid = next(
            (x.uid for x in self.env.nodes if 'compute' in x.roles), None
        )
        self.assertIsNotNone(compute_uid)
        compute_tasks = message['args']['tasks_graph'][compute_uid]

        expected_tasks = {
            consts.PLUGIN_PRE_DEPLOYMENT_HOOK + "_start",
            consts.PLUGIN_PRE_DEPLOYMENT_HOOK + "_end",
            consts.PLUGIN_POST_DEPLOYMENT_HOOK,
            "plugin_deployment_task"
        }

        for task in compute_tasks:
            expected_tasks.discard(task['id'])

        if len(expected_tasks):
            self.fail(
                "The following task is not found in tasks for deploy {0}."
                .format(sorted(expected_tasks))
            )

    @mock.patch.object(TaskProcessor, "ensure_task_based_deploy_allowed")
    @fake_tasks(mock_rpc=True, fake_rpc=False)
    def test_task_deploy_specified_tasks(self, rpc_cast, *_):
        compute = next(
            (x for x in self.env.nodes if 'compute' in x.roles), None
        )
        self.assertIsNotNone(compute)
        compute.status = consts.NODE_STATUSES.provisioned
        compute.pending_addition = False
        self.db.flush()

        resp = self.app.put(
            reverse(
                'DeploySelectedNodesWithTasks',
                kwargs={'cluster_id': self.cluster.id}
            ) + '?nodes={0}'.format(compute.uid),
            params='["deploy_legacy"]',
            headers=self.default_headers
        )
        self.assertNotEqual(
            consts.TASK_STATUSES.error,
            Task.get_by_uuid(
                uuid=resp.json_body['uuid'], fail_if_not_found=True
            ).status
        )

        links = rpc_cast.call_args[0][1]['args']['tasks_graph']
        self.assertItemsEqual(
            ["deploy_legacy"],
            (task["id"] for task in links[compute.uid]
             if task['type'] != consts.ORCHESTRATOR_TASK_TYPES.skipped)
        )

    @mock.patch.object(TaskProcessor, "ensure_task_based_deploy_allowed")
    def test_task_deploy_all_tasks(self, *_):
        compute = next(
            (x for x in self.env.nodes if 'compute' in x.roles), None
        )
        self.assertIsNotNone(compute)
        compute.status = consts.NODE_STATUSES.provisioned
        compute.pending_addition = False
        self.db.flush()

        message = self.get_deploy_message()
        deploy_tasks = message['args']['tasks_graph']
        self.assertIn(
            "netconfig",
            {task["id"] for task in deploy_tasks[compute.uid]
             if task['type'] != consts.ORCHESTRATOR_TASK_TYPES.skipped}
        )

    def check_reexecute_task_on_cluster_update(self):
        node = next(
            (n for n in self.env.nodes
             if n.status == consts.NODE_STATUSES.ready),
            None
        )
        self.assertIsNotNone(node)
        message = self.get_deploy_message()
        deploy_tasks = message['args']['tasks_graph']
        # netconfig has attribute reexecute_on
        self.assertIn(
            "netconfig",
            {task["id"] for task in deploy_tasks[node.uid]
             if task['type'] != consts.ORCHESTRATOR_TASK_TYPES.skipped}
        )
        self.db().refresh(self.cluster)

    @mock.patch.object(TaskProcessor, "ensure_task_based_deploy_allowed")
    @fake_tasks(mock_rpc=True, fake_rpc=True,
                override_state={'status': consts.NODE_STATUSES.ready})
    def test_task_executed_on_adding_node(self, *_):
        self.env.wait_ready(self.env.launch_deployment(self.cluster.id))
        self.db().refresh(self.cluster)
        self.assertEqual(
            consts.CLUSTER_STATUSES.operational, self.cluster.status
        )
        self.env.create_node(
            api=False, cluster_id=self.cluster.id,
            roles=["compute"],
            pending_addition=True
        )
        self.check_reexecute_task_on_cluster_update()
