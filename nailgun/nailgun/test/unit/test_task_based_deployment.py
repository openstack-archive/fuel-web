# -*- coding: utf-8 -*-

#    Copyright 2015 Mirantis, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the 'License'); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an 'AS IS' BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import mock

from nailgun import consts
from nailgun.orchestrator import task_based_deployment
from nailgun.test.base import BaseTestCase
from nailgun.test.base import BaseUnitTest


class TestTaskSerializers(BaseTestCase):
    def setUp(self):
        super(TestTaskSerializers, self).setUp()
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {'name': 'First',
                 'roles': ['controller']},
                {'name': 'Second',
                 'roles': ['compute']}
            ]
        )
        self.serializer = task_based_deployment.TasksSerializer(
            self.env.clusters[-1], self.env.nodes
        )

    def test_serialize_result(self):
        tasks = [
            {
                "id": "task1", "role": ["controller"],
                "type": "shell", "version": "2.0.0",
                "parameters": {"cmd": "bash -c 'echo 1'"},
                "cross-depends": [{"name": "task3", "role": ["compute"]}]
            },
            {
                "id": "task2", "role": ["controller"],
                "type": "shell", "version": "2.0.0",
                "parameters": {"cmd": "bash -c 'echo 1'"},
                "requires": ["task1"]
            },
            {
                "id": "task3", "role": ["compute"],
                "type": "shell", "version": "2.0.0",
                "parameters": {"cmd": "bash -c 'echo 2'"},
                "cross-depended-by": [{"name": "task2", "role": "*"}]
            },
        ]
        tasks, connections = self.serializer.serialize(
            self.env.clusters[-1], self.env.nodes, tasks
        )
        controllers = [
            n.uid for n in self.env.nodes if "controller" in n.roles
        ]
        computes = [
            n.uid for n in self.env.nodes if "compute" in n.roles
        ]

        self.assertEqual(1, len(controllers))
        self.assertEqual(1, len(computes))
        self.assertItemsEqual(
            [
                {
                    "id": "task1",
                    "type": "shell",
                    "requires": [{"name": "task3", "node_id": computes[0]}]
                },
                {
                    "id": "task2",
                    "type": "shell",
                    "requires": [{"name": "task1", "node_id": controllers[0]}],
                },
            ],
            connections[controllers[0]]
        )
        self.assertItemsEqual(
            [{
                "id": "task3",
                "type": "shell",
                "required_for": [{"name": "task2", "node_id": controllers[0]}]
            }],
            connections[computes[0]]
        )

    def test_serialize_fail_if_all_task_have_not_version_2(self):
        tasks = [
            {
                "id": "test1", "role": ["controller"],
                "type": "puppet", "version": "2.0.0", "parameters": {}
            },
            {
                "id": "test2", "role": ["compute"], "type": "puppet",
                "parameters": {}
            },
        ]
        self.assertRaises(
            task_based_deployment.errors.TaskBaseDeploymentNotAllowed,
            self.serializer.serialize,
            self.env.clusters[-1], self.env.nodes, tasks
        )

    def _check_run_selected_tasks(self, ids, controller_tasks, compute_tasks):
        tasks = [
            {
                "id": "task1", "tasks": ["task2", "task3"], "type": "group",
                "version": "2.0.0", "role": ["controller"]
            },
            {
                "id": "task2", "role": ["controller"],
                "type": "puppet", "version": "2.0.0", "parameters": {}
            },
            {
                "id": "task3", "role": ["compute"],
                "type": "puppet", "version": "2.0.0", "parameters": {}
            },
        ]
        serialized = self.serializer.serialize(
            self.env.clusters[-1], self.env.nodes, tasks, ids
        )[1]
        controllers = [
            n.uid for n in self.env.nodes if "controller" in n.roles
        ]
        computes = [
            n.uid for n in self.env.nodes if "compute" in n.roles
        ]
        self.assertEqual(1, len(controllers))
        self.assertEqual(1, len(computes))
        self.assertItemsEqual(
            ["task2", "task3"],
            (x["id"] for x in serialized[controllers[0]])
        )
        self.assertItemsEqual(
            ["task3"],
            (x["id"] for x in serialized[computes[0]])
        )
        for expected_tasks, node in ((controller_tasks, controllers[0]),
                                     (compute_tasks, computes[0])):

            self.assertItemsEqual(
                expected_tasks,
                (x["id"] for x in serialized[node]
                 if x["type"] != consts.ORCHESTRATOR_TASK_TYPES.skipped)
            )

    def test_process_with_selected_group_id(self):
        self._check_run_selected_tasks(["task1"], ["task2", "task3"], [])

    def test_process_with_selected_task_id(self):
        self._check_run_selected_tasks(["task3"], ["task3"], ["task3"])

    def test_serialize_success_if_all_applicable_task_has_version_2(self):
        tasks = [
            {
                "id": "test1", "role": ["controller"],
                "type": "puppet", "version": "2.0.0", "parameters": {}
            },
            {
                "id": "test2", "role": ["cinder"], "type": "puppet",
                "parameters": {}
            },
        ]
        self.assertNotRaises(
            task_based_deployment.errors.TaskBaseDeploymentNotAllowed,
            self.serializer.serialize,
            self.env.clusters[-1], self.env.nodes, tasks
        )

    def test_process_task_de_duplication(self):
        task = {
            "id": "test", "type": "puppet", "parameters": {},
            "version": "2.0.0"
        }
        self.serializer.process_task(
            task, ["1"], task_based_deployment.NullResolver
        )
        # check de-duplication
        self.serializer.process_task(
            task, ["1"], task_based_deployment.NullResolver
        )
        self.assertItemsEqual(["1"], self.serializer.tasks_connections)
        self.assertItemsEqual(["test"], self.serializer.tasks_connections["1"])
        self.assertEqual(
            "test", self.serializer.tasks_connections["1"]["test"]["id"]
        )
        self.assertEqual(
            "puppet", self.serializer.tasks_connections["1"]["test"]["type"]
        )
        self.assertNotIn(
            "skipped", self.serializer.tasks_connections["1"]["test"]["type"]
        )

    def test_process_skipped_task(self):
        task = {
            "id": "test", "type": "puppet", "version": "2.0.0",
            "parameters": {}, 'skipped': True,
        }
        self.serializer.process_task(
            task, ["1"], task_based_deployment.NullResolver
        )
        self.assertItemsEqual(["1"], self.serializer.tasks_connections)
        self.assertItemsEqual(["test"], self.serializer.tasks_connections["1"])
        self.assertEqual(
            "test", self.serializer.tasks_connections["1"]["test"]["id"]
        )
        self.assertEqual(
            "skipped", self.serializer.tasks_connections["1"]["test"]["type"]
        )
        self.assertNotIn(
            "skipped", self.serializer.tasks_connections["1"]["test"]
        )

    def test_process_noop_task(self):
        task = {"id": "test", "type": "stage", "role": "*"}
        self.serializer.process_task(
            task, ["1"], task_based_deployment.NullResolver
        )
        self.assertItemsEqual(["1"], self.serializer.tasks_connections)
        self.assertItemsEqual(["test"], self.serializer.tasks_connections["1"])
        self.assertEqual(
            "test", self.serializer.tasks_connections["1"]["test"]["id"]
        )
        self.assertEqual(
            "skipped", self.serializer.tasks_connections["1"]["test"]["type"]
        )
        self.assertNotIn(
            "skipped", self.serializer.tasks_connections["1"]["test"]
        )

    def test_expand_task_groups(self):
        node_ids = ['1', '2']
        with mock.patch.object(self.serializer, 'role_resolver') as m_resolve:
            m_resolve.resolve.return_value = node_ids
            self.serializer.expand_task_groups(
                [
                    {"type": "group", "id": "group1", "role": "compute",
                     "tasks": ["task1", "task2"]}
                ],
                {
                    'task1': {'id': 'task1', 'version': '2.0.0',
                              'type': 'skipped', 'role': '*'},
                    'task2': {'id': 'task2', 'version': '2.0.0',
                              'type': 'skipped', 'role': '*'}
                }
            )
            self.assertIn('1', self.serializer.tasks_connections)
            self.assertIn('2', self.serializer.tasks_connections)
            self.assertItemsEqual(
                ['task1', 'task2'],
                self.serializer.tasks_connections['1']
            )
            self.assertItemsEqual(
                self.serializer.tasks_connections['1'],
                self.serializer.tasks_connections['2']
            )

    def test_expand_dependencies_on_same_node(self):
        node_ids = ['1', '2']
        self.serializer.tasks_connections = dict(
            (node_id, ['task_{0}'.format(node_id)])
            for node_id in node_ids
        )
        self.serializer.tasks_connections[None] = ['sync_point']
        self.assertItemsEqual(
            [('sync_point', None)],
            self.serializer.expand_dependencies('1', ['sync_point'], False)
        )
        self.assertItemsEqual(
            [('task_1', '1')],
            self.serializer.expand_dependencies('1', ['/task/'], False)
        )

    def test_expand_dependencies_does_not_raise_if_none_arg(self):
        self.assertNotRaises(
            Exception,
            self.serializer.expand_cross_dependencies,
            '1', None, True
        )
        self.assertNotRaises(
            Exception,
            self.serializer.expand_cross_dependencies,
            '1', None, True
        )

    def test_expand_cross_dependencies(self):
        node_ids = ['1', '2', '3']
        self.serializer.tasks_connections = dict(
            (node_id, ['task_{0}'.format(node_id)])
            for node_id in node_ids
        )
        with mock.patch.object(self.serializer, 'role_resolver') as m_resolve:
            m_resolve.resolve.return_value = node_ids
            # the default role and policy
            self.assertItemsEqual(
                [('task_1', '1')],
                self.serializer.expand_cross_dependencies(
                    '2', [{'name': 'task_1'}], True
                )
            )
            m_resolve.resolve.assert_called_with(
                consts.TASK_ROLES.all, consts.NODE_RESOLVE_POLICY.all
            )
            # concrete role and policy
            self.assertItemsEqual(
                [('task_2', '2')],
                self.serializer.expand_cross_dependencies(
                    '2',
                    [{'name': 'task_2', 'role': ['role'], 'policy': 'any'}],
                    True
                )
            )
            m_resolve.resolve.assert_called_with(
                ['role'], 'any'
            )
            m_resolve.resolve.reset_mock()
            # use self as role
            self.assertItemsEqual(
                [('task_1', '1')],
                self.serializer.expand_cross_dependencies(
                    '1',
                    [{'name': 'task_1', 'role': 'self'}],
                    True
                )
            )
            self.assertFalse(m_resolve.resolve.called)

    def test_resolve_relation_when_no_chains(self):
        node_ids = ['1', '2', '3']
        self.serializer.tasks_connections = dict(
            (node_id, ['task_{0}'.format(node_id)])
            for node_id in node_ids
        )
        self.assertItemsEqual(
            [('task_1', '1')],
            self.serializer.resolve_relation('task_1', node_ids, True)
        )
        self.assertItemsEqual(
            (('task_{0}'.format(i), i) for i in node_ids),
            self.serializer.resolve_relation('/task/', node_ids, True)
        )

    def test_resolve_relation_in_chain(self):
        node_ids = ['1', '2', '3']
        self.serializer.tasks_connections = dict(
            (node_id, ['task_{0}'.format(node_id)])
            for node_id in node_ids
        )
        self.serializer.task_processor.origin_task_ids = {
            'task_1': 'task', 'task_2': 'task', 'task_3': 'task2'
        }
        self.serializer.tasks_connections['1'].append('task_2')
        self.assertItemsEqual(
            [('task_start', '1'), ('task_start', '2')],
            self.serializer.resolve_relation('task', node_ids, True)
        )
        self.assertItemsEqual(
            [('task_end', '1'), ('task_end', '2')],
            self.serializer.resolve_relation('task', node_ids, False)
        )
        self.assertItemsEqual(
            [('task_1', '1')],
            self.serializer.resolve_relation('task_1', node_ids, False)
        )

    def test_need_update_task(self):
        self.assertTrue(self.serializer.need_update_task(
            {}, {"id": "task1", "type": "puppet"}
        ))
        self.assertTrue(self.serializer.need_update_task(
            {"task1": {"type": "skipped"}}, {"id": "task1", "type": "puppet"}
        ))

        self.assertFalse(self.serializer.need_update_task(
            {"task1": {"type": "skipped"}}, {"id": "task1", "type": "skipped"}
        ))

        self.assertFalse(self.serializer.need_update_task(
            {"task1": {"type": "puppet"}}, {"id": "task1", "type": "skipped"}
        ))


class TestNoopSerializer(BaseTestCase):
    def setUp(self):
        super(TestNoopSerializer, self).setUp()
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {'name': 'First',
                 'roles': ['controller']},
                {'name': 'Second',
                 'roles': ['compute']}
            ]
        )

    def test_get_uids(self):
        serializer = task_based_deployment.NoopSerializer(
            {'id': 'deploy_start', 'type': 'stage'},
            self.env, self.env.nodes
        )
        self.assertEqual([None], serializer.get_uids())
        serializer.task['groups'] = ['compute']
        self.assertItemsEqual(
            [n.uid for n in self.env.nodes if 'compute' in n.roles],
            serializer.get_uids()
        )

    def test_serialize(self):
        serializer = task_based_deployment.NoopSerializer(
            {'id': 'deploy_start', 'type': 'stage'},
            self.env, self.env.nodes
        )
        tasks = list(serializer.serialize())
        self.assertEqual(1, len(tasks))
        task = tasks[0]

        self.assertEqual(
            {
                'id': 'deploy_start',
                'type': consts.ORCHESTRATOR_TASK_TYPES.skipped,
                'uids': [None],
                'fail_on_error': False
            },
            task
        )


class TestDeploymentTaskSerializer(BaseUnitTest):
    def make_task(self, task_id, **kwargs):
        task = kwargs
        task.setdefault('type', 'puppet')
        task['id'] = task_id
        return task

    def test_get_stage_serializer(self):
        factory = task_based_deployment.DeployTaskSerializer()
        self.assertIs(
            task_based_deployment.CreateVMsOnCompute,
            factory.get_stage_serializer(
                self.make_task('generate_vms')
            )
        )

        self.assertIs(
            task_based_deployment.NoopSerializer,
            factory.get_stage_serializer(
                self.make_task('post_deployment', type='stage')
            )
        )
        self.assertIs(
            task_based_deployment.NoopSerializer,
            factory.get_stage_serializer(
                self.make_task('pre_deployment', type='skipped')
            )
        )
        self.assertTrue(
            issubclass(
                factory.get_stage_serializer(
                    self.make_task('upload_repos')
                ),
                task_based_deployment.StandartConfigRolesHook
            )
        )

    def test_get_stage_serializer_for_plugins(self):
        factory = task_based_deployment.DeployTaskSerializer()
        self.assertIs(
            task_based_deployment.PluginPostDeploymentSerializer,
            factory.get_stage_serializer(
                {"type": consts.PLUGIN_POST_DEPLOYMENT_HOOK}
            )
        )
        self.assertIs(
            task_based_deployment.PluginPreDeploymentSerializer,
            factory.get_stage_serializer(
                {"type": consts.PLUGIN_PRE_DEPLOYMENT_HOOK}
            )
        )


class TestTaskProcessor(BaseTestCase):
    def setUp(self):
        super(TestTaskProcessor, self).setUp()
        self.processor = task_based_deployment.TaskProcessor()

    def test_link_tasks_on_same_node(self):
        previous = {
            'id': 'test_task_start',
            'uids': ['1', '2']
        }
        current = {
            'id': 'test_task_end',
            'uids': ['1', '2']
        }
        self.processor._link_tasks(previous, current)
        self.assertEqual(
            ['test_task_start'],
            current['requires']
        )
        current['requires'] = ['task2']
        self.processor._link_tasks(previous, current)
        self.assertEqual(
            ['task2', 'test_task_start'],
            current['requires']
        )

    def test_link_tasks_on_different_nodes(self):
        previous = {
            'id': 'test_task_start',
            'uids': ['1']
        }
        current = {
            'id': 'test_task_end',
            'uids': ['1', '2']
        }
        self.processor._link_tasks(previous, current)
        self.assertItemsEqual(
            (('test_task_start', n) for n in previous['uids']),
            current['requires_ex']
        )
        current['requires_ex'] = [('test_task_start', '0')]
        self.processor._link_tasks(previous, current)
        self.assertItemsEqual(
            (('test_task_start', n) for n in ['0'] + previous['uids']),
            current['requires_ex']
        )

    def test_convert_task(self):
        origin_task = {'id': 'task', 'requires': '*', 'required_for': '*'}
        serialized = {'type': 'puppet'}
        self.processor._convert_task(
            serialized, origin_task, 'task_start',
            ['requires', 'cross-depends']
        )

        self.assertEqual(
            {'id': 'task_start', 'type': 'puppet', 'requires': '*'},
            serialized
        )
        serialized = {'type': 'puppet'}
        self.processor._convert_task(
            serialized, origin_task
        )
        self.assertEqual(
            {'id': 'task', 'type': 'puppet',
             'requires': '*', 'required_for': '*'},
            serialized
        )

    def test_patch_first_task_in_chain(self):
        origin_task = {
            'id': 'task', 'requires': [], 'cross-depends': [],
            'required_for': [], 'cross-depended-by': []
        }
        serialized = {'type': 'puppet'}
        self.processor._convert_first_task(serialized, origin_task)
        self.assertEqual(
            {
                'id': 'task_start',
                'type': 'puppet',
                'requires': [],
                'cross-depends': []
            },
            serialized
        )

    def test_patch_last_task_in_chain(self):
        origin_task = {
            'id': 'task', 'requires': [], 'cross-depends': [],
            'required_for': [], 'cross-depended-by': []
        }
        serialized = {'type': 'puppet'}
        self.processor._convert_last_task(serialized, origin_task)
        self.assertEqual(
            {
                'id': 'task_end',
                'type': 'puppet',
                'required_for': [],
                'cross-depended-by': []
            },
            serialized
        )

    def test_process_if_no_tasks(self):
        tasks = self.processor.process_tasks({'id': 'test'}, iter([]))
        self.assertItemsEqual(
            [],
            tasks
        )

    def test_process_tasks_if_not_chain(self):
        origin_task = {
            'id': 'task', 'version': '2.0.0',
            'requires': ['a'], 'cross-depends': [{'name': 'b'}],
            'required_for': ['c'], 'cross-depended-by': [{'name': 'd'}]
        }
        serialized = iter([{'type': 'puppet'}])

        tasks = list(self.processor.process_tasks(origin_task, serialized))
        del origin_task['version']
        self.assertItemsEqual(
            [dict(origin_task, type='puppet')],
            tasks
        )
        self.assertEqual('task', self.processor.get_origin('task'))

    def test_process_if_chain(self):
        origin_task = {
            'id': 'task', 'version': '2.0.0',
            'requires': ['a'], 'cross-depends': [{'name': 'b'}],
            'required_for': ['c'], 'cross-depended-by': [{'name': 'd'}]
        }
        serialized = iter([
            {'type': 'puppet', 'uids': [None]},
            {'type': 'shell', 'uids': [None]},
            {'type': 'skipped', 'uids': [None]}
        ])

        tasks = self.processor.process_tasks(origin_task, serialized)
        self.assertItemsEqual(
            [
                {
                    'id': 'task_start', 'type': 'puppet', 'uids': [None],
                    'requires': ['a'],
                    'cross-depends': [{'name': 'b'}],
                },
                {
                    'id': 'task#1', 'type': 'shell', 'uids': [None],
                    'requires': ['task_start'],
                },
                {
                    'id': 'task_end', 'type': 'skipped', 'uids': [None],
                    'requires': ['task#1'],
                    'required_for': ['c'],
                    'cross-depended-by': [{'name': 'd'}],
                },
            ],
            tasks
        )
        self.assertEqual('task', self.processor.get_origin('task_start'))
        self.assertEqual('task', self.processor.get_origin('task#1'))
        self.assertEqual('task', self.processor.get_origin('task_end'))

    def test_ensure_task_based_deployment_allowed(self):
        self.assertRaises(
            task_based_deployment.errors.TaskBaseDeploymentNotAllowed,
            self.processor.ensure_task_based_deploy_allowed,
            {'id': 'task'}
        )
        self.assertRaises(
            task_based_deployment.errors.TaskBaseDeploymentNotAllowed,
            self.processor.ensure_task_based_deploy_allowed,
            {'id': 'task', 'version': '1.2.3'}
        )
        self.assertNotRaises(
            task_based_deployment.errors.TaskBaseDeploymentNotAllowed,
            self.processor.ensure_task_based_deploy_allowed,
            {'id': 'task', 'version': consts.TASK_CROSS_DEPENDENCY}
        )
        self.assertNotRaises(
            task_based_deployment.errors.TaskBaseDeploymentNotAllowed,
            self.processor.ensure_task_based_deploy_allowed,
            {'id': 'task', 'type': consts.ORCHESTRATOR_TASK_TYPES.stage}
        )
