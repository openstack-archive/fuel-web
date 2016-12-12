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
from nailgun.db.sqlalchemy import models
from nailgun import errors
from nailgun import objects
from nailgun.orchestrator.task_based_deployment import TaskProcessor
from nailgun import rpc
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import fake_tasks
from nailgun.test.base import mock_rpc
from nailgun.utils import reverse


class TestTaskDeploy80(BaseIntegrationTest):

    def setUp(self):
        super(TestTaskDeploy80, self).setUp()
        self.cluster = self.env.create(
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
            deployment_tasks=deployment_tasks,
            tasks=tasks
        )
        self.db.flush()

    # idx=1 because we need to skip [0] - provision
    @mock_rpc(pass_mock=True)
    def get_deploy_message(self, rpc_cast, idx=1, **kwargs):
        task = self.env.launch_deployment(self.cluster.id, **kwargs)
        self.assertNotEqual(consts.TASK_STATUSES.error, task.status)
        args, kwargs = rpc_cast.call_args
        return args[1][idx]

    @mock.patch.object(TaskProcessor, "ensure_task_based_deploy_allowed")
    @mock.patch.object(objects.Release, "is_lcm_supported", return_value=False)
    def test_task_deploy_used_by_default(self, _, lcm_mock):
        message = self.get_deploy_message()
        self.assertEqual("task_deploy", message["method"])
        self.assertItemsEqual(
            ["task_uuid", "deployment_info",
             "tasks_directory", "tasks_graph", "debug"],
            message["args"]
        )

    @mock.patch.object(TaskProcessor, "ensure_task_based_deploy_allowed")
    @mock.patch.object(objects.Release, "is_lcm_supported", return_value=True)
    def test_task_deploy_dry_run(self, _, lcm_mock):
        # idx=0 because dry run skips provision subtask
        message = self.get_deploy_message(idx=0, dry_run=True)
        self.assertEqual("task_deploy", message["method"])
        self.assertIn('dry_run', message['args'])
        self.assertTrue(message["args"]['dry_run'])

    @mock.patch.object(TaskProcessor, "ensure_task_based_deploy_allowed")
    @mock.patch.object(objects.Release, "is_lcm_supported", return_value=True)
    def test_task_deploy_noop_run(self, _, lcm_mock):
        # idx=0 because noop run skips provision subtask
        message = self.get_deploy_message(idx=0, noop_run=True)
        self.assertEqual("task_deploy", message["method"])
        self.assertIn('noop_run', message['args'])
        self.assertTrue(message["args"]['noop_run'])

    @mock.patch.object(TaskProcessor, "ensure_task_based_deploy_allowed")
    def test_fallback_to_granular_deploy(self, ensure_allowed):
        ensure_allowed.side_effect = errors.TaskBaseDeploymentNotAllowed
        message = self.get_deploy_message()
        self.assertEqual("granular_deploy", message["method"])
        self.assertItemsEqual(
            ["task_uuid", "deployment_info",
             "pre_deployment", "post_deployment", "debug"],
            message["args"]
        )
        ensure_allowed.assert_called_once_with(mock.ANY)

    def test_granular_deploy_if_not_enabled(self):
        self.env.disable_task_deploy(self.cluster)
        message = self.get_deploy_message()
        self.assertEqual("granular_deploy", message["method"])
        self.assertItemsEqual(
            ["task_uuid", "deployment_info",
             "pre_deployment", "post_deployment", "debug"],
            message["args"]
        )

    @mock.patch.object(TaskProcessor, "ensure_task_based_deploy_allowed")
    def test_task_deploy_with_plugins(self, *_):
        self.add_plugin_with_tasks("plugin_deployment_task")
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
            objects.Task.get_by_uuid(
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
        task = self.env.launch_deployment(self.cluster.id)
        self.assertEqual(task.status, consts.TASK_STATUSES.ready)
        self.assertEqual(
            consts.CLUSTER_STATUSES.operational, self.cluster.status
        )
        self.env.create_node(
            api=False, cluster_id=self.cluster.id,
            roles=["compute"],
            pending_addition=True
        )
        self.check_reexecute_task_on_cluster_update()

    def test_deploy_check_failed_with_conflict_role(self):
        node = self.env.nodes[0]

        self.app.put(
            reverse(
                'NodeHandler',
                kwargs={'obj_id': node.id}
            ),
            jsonutils.dumps({'pending_roles': ['controller', 'compute']}),
            headers=self.default_headers
        )
        task = self.env.launch_deployment(self.cluster.id)

        self.assertEqual(consts.TASK_STATUSES.error, task.status)
        self.assertEqual(
            "Role 'controller' in conflict with role 'compute'.",
            task.message)

    def test_deploy_check_failed_with_incompatible_role(self):
        node = self.env.nodes[0]

        self.app.put(
            reverse(
                'NodeHandler',
                kwargs={'obj_id': node.id}
            ),
            jsonutils.dumps({'pending_roles': ['ceph-osd']}),
            headers=self.default_headers
        )
        task = self.env.launch_deployment(self.cluster.id)

        self.assertEqual(consts.TASK_STATUSES.error, task.status)
        self.assertEqual(
            "Role 'ceph-osd' restrictions mismatch: Ceph should"
            " be enabled in the environment settings.",
            task.message)

    def test_serialized_tasks(self):
        patcher = mock.patch('objects.Cluster.get_deployment_tasks')
        self.addCleanup(patcher.stop)

        self.mock_tasks = patcher.start()
        self.mock_tasks.return_value = [
            {
                'id': 'deploy_start',
                'type': 'stage',
            },
            {
                'id': 'deploy_end',
                'type': 'stage',
                'requires': ['deploy_start'],
            },
            {
                'id': 'compute', 'type': 'group', 'role': ['compute'],
            },
            {
                'id': 'task-a',
                'version': '2.0.0',
                'type': 'puppet',
                'groups': ['compute'],
                'condition': 'settings:public_ssl.horizon.value == false',
                'parameters': {},
            },
            {
                'id': 'task-b',
                'version': '2.0.0',
                'type': 'puppet',
                'groups': ['compute'],
                'parameters': {},
            }]

        compute = next(
            (x for x in self.env.nodes if 'compute' in x.roles), None
        )

        resp = self.app.get(
            reverse(
                'SerializedTasksHandler',
                kwargs={'cluster_id': self.cluster.id},
            ))

        self.assertEqual(resp.status_code, 200)

        graph = resp.json_body['tasks_graph']
        self.assertItemsEqual(
            ['task-a', 'task-b'],
            (task['id'] for task in graph[compute.uid]
             if task['type'] != consts.ORCHESTRATOR_TASK_TYPES.skipped)
        )


class TestTaskDeploy90(BaseIntegrationTest):

    def setUp(self):
        super(TestTaskDeploy90, self).setUp()
        self.cluster = self.env.create(
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
                'version': '2015.1.0-9.0',
            },
        )
        self.compute = next(
            (x for x in self.env.nodes if 'compute' in x.roles), None)

        patcher = mock.patch('objects.Cluster.get_deployment_tasks')
        self.addCleanup(patcher.stop)

        self.mock_tasks = patcher.start()
        self.mock_tasks.return_value = [
            {
                'id': 'compute', 'type': 'group', 'roles': ['compute']
            },
            {
                'id': 'task-a',
                'version': '2.1.0',
                'type': 'puppet',
                'roles': ['compute'],
                'condition': {
                    'yaql_exp': 'changedAny($.network_scheme, $.get(dpdk))',
                },
                'parameters': {},
            },
            {
                'id': 'task-b',
                'version': '2.1.0',
                'type': 'puppet',
                'roles': ['compute'],
                'condition': {
                    'yaql_exp': 'changedAny($.network_scheme, $.get(dpdk))',
                },
                'parameters': {},
            }]

    def test_serialized_tasks(self):
        resp = self.app.get(
            reverse(
                'SerializedTasksHandler',
                kwargs={'cluster_id': self.cluster.id},
            ))
        self.assertEqual(resp.status_code, 200)

        # all tasks must be in graph
        graph = resp.json_body['tasks_graph']
        self.assertItemsEqual(
            ['task-a', 'task-b'],
            (task['id'] for task in graph[self.compute.uid]
             if task['type'] != consts.ORCHESTRATOR_TASK_TYPES.skipped)
        )

    def test_serialized_tasks_w_tasks(self):
        resp = self.app.get(
            reverse(
                'SerializedTasksHandler',
                kwargs={'cluster_id': self.cluster.id},
            ) + '?tasks=task-a')
        self.assertEqual(resp.status_code, 200)

        # only task-a must be in graph
        graph = resp.json_body['tasks_graph']
        self.assertItemsEqual(
            ['task-a'],
            (task['id'] for task in graph[self.compute.uid]
             if task['type'] != consts.ORCHESTRATOR_TASK_TYPES.skipped)
        )

    @mock.patch("objects.Node.dpdk_enabled")
    def test_deploy_check_failed_with_dpdk_cpu_distribution(self, _):
        node = self.env.nodes[0]

        objects.Node.update_attributes(node, {
            'cpu_pinning': {
                'dpdk': {'value': 1}
            }
        })

        task = self.env.launch_deployment(self.cluster.id)

        self.assertEqual(consts.TASK_STATUSES.error, task.status)
        self.assertEqual(
            "Node '{}': DPDK CPUs distribution error: there is no"
            " configured DPDK interfaces.".format(node.id),
            task.message
        )


class TestTaskDeploy90AfterDeployment(BaseIntegrationTest):
    def setUp(self):
        super(TestTaskDeploy90AfterDeployment, self).setUp()
        self.cluster = self.env.create(
            api=False,
            nodes_kwargs=[
                {'roles': ['controller']},
                {'roles': ['compute']},
            ],
            release_kwargs={
                'operating_system': consts.RELEASE_OS.ubuntu,
                'version': '2015.1.0-9.0',
            },
        )

        # well, we can't change deployment_tasks.yaml fixture since it
        # must be compatible with granular deployment (and it doesn't support
        # yaql based condition). so the only choice - patch netconfig task
        # on fly.
        self.db.query(models.DeploymentGraphTask)\
            .filter_by(task_name='netconfig')\
            .update({
                'condition': {
                    'yaql_exp': 'changedAny($.network_scheme, $.get(dpdk))',
                }
            })

        with mock.patch('nailgun.task.task.rpc.cast'):
            task = self.env.launch_deployment()

            rpc.receiver.NailgunReceiver().deploy_resp(
                task_uuid=next((
                    t.uuid for t in task.subtasks
                    if t.name == consts.TASK_NAMES.deployment), None),
                status=consts.TASK_STATUSES.ready,
                progress=100,
                nodes=[
                    {'uid': n.uid, 'status': consts.NODE_STATUSES.ready}
                    for n in self.cluster.nodes
                ]
            )

            # in order to do not implement iterative responses for each
            # particular deployment task, let's mark them all as 'ready'
            self.db.query(objects.DeploymentHistory.model).update({
                'status': consts.HISTORY_TASK_STATUSES.ready,
            })

    @mock.patch('nailgun.task.task.rpc.cast')
    def test_task_deploy_specified_tasks(self, rpc_cast):
        compute = next(
            (x for x in self.env.nodes if 'compute' in x.roles), None
        )
        resp = self.app.put(
            reverse(
                'DeploySelectedNodesWithTasks',
                kwargs={'cluster_id': self.cluster.id}
            ) + '?nodes={0}'.format(compute.uid),
            params='["netconfig"]',
            headers=self.default_headers)
        self.assertNotEqual(
            consts.TASK_STATUSES.error,
            objects.Task.get_by_uuid(
                uuid=resp.json_body['uuid'], fail_if_not_found=True
            ).status)

        graph = rpc_cast.call_args[0][1][0]['args']['tasks_graph']

        # LCM: no changes - no tasks
        self.assertItemsEqual(
            [],
            (task['id'] for task in graph[compute.uid]
             if task['type'] != consts.ORCHESTRATOR_TASK_TYPES.skipped)
        )

    @mock.patch('nailgun.task.task.rpc.cast')
    def test_task_deploy_specified_tasks_force(self, rpc_cast):
        compute = next(
            (x for x in self.env.nodes if 'compute' in x.roles), None
        )
        resp = self.app.put(
            reverse(
                'DeploySelectedNodesWithTasks',
                kwargs={'cluster_id': self.cluster.id}
            ) + '?nodes={0}&force=1'.format(compute.uid),
            params='["netconfig"]',
            headers=self.default_headers)
        self.assertNotEqual(
            consts.TASK_STATUSES.error,
            objects.Task.get_by_uuid(
                uuid=resp.json_body['uuid'], fail_if_not_found=True
            ).status)

        graph = rpc_cast.call_args[0][1][0]['args']['tasks_graph']

        # due to 'force', task must be run anyway
        self.assertItemsEqual(
            ['netconfig'],
            (task['id'] for task in graph[compute.uid]
             if task['type'] != consts.ORCHESTRATOR_TASK_TYPES.skipped)
        )
