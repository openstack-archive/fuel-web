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
from nailgun.orchestrator import task_based_deploy
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
        self.serializer = task_based_deploy.TasksSerializer(
            self.env.clusters[-1], self.env.nodes
        )

    def test_expand_task_groups(self):
        node_ids = ['1', '2']
        with mock.patch.object(self.serializer, 'role_resolver') as m_resolve:
            m_resolve.resolve.return_value = node_ids
            self.serializer.expand_task_groups(
                {'role': ['task1', 'task2']},
                {
                    'task1': {'id': 'task1', 'type': 'skipped', 'role': '*'},
                    'task2': {'id': 'task2', 'type': 'skipped', 'role': '*'}
                }
            )
            self.assertIn('1', self.serializer.tasks_per_node)
            self.assertIn('2', self.serializer.tasks_per_node)
            self.assertItemsEqual(
                ['task1', 'task2'],
                self.serializer.tasks_per_node['1']
            )
            self.assertItemsEqual(
                self.serializer.tasks_per_node['1'],
                self.serializer.tasks_per_node['2']
            )

    def test_expand_dependencies_on_same_node(self):
        node_ids = ['1', '2']
        self.serializer.tasks_per_node = dict(
            (node_id, ['task_{0}'.format(node_id)])
            for node_id in node_ids
        )
        self.serializer.tasks_per_node[None] = ['sync_point']
        self.assertItemsEqual(
            [{'name': 'sync_point', 'node_id': None}],
            self.serializer.expand_dependencies('1', ['sync_point'], False)
        )
        self.assertItemsEqual(
            [{'name': 'task_1', 'node_id': '1'}],
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
        self.serializer.tasks_per_node = dict(
            (node_id, ['task_{0}'.format(node_id)])
            for node_id in node_ids
        )
        with mock.patch.object(self.serializer, 'role_resolver') as m_resolve:
            m_resolve.resolve.return_value = node_ids
            # the default role and policy
            self.assertItemsEqual(
                [{'name': 'task_1', 'node_id': '1'}],
                self.serializer.expand_cross_dependencies(
                    '2', [{'name': 'task_1'}], True
                )
            )
            m_resolve.resolve.assert_called_with(
                consts.ALL_ROLES, consts.NODE_RESOLVE_POLICY.all
            )
            # concrete role and policy
            self.assertItemsEqual(
                [{'name': 'task_2', 'node_id': '2'}],
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
                [{'name': 'task_1', 'node_id': '1'}],
                self.serializer.expand_cross_dependencies(
                    '1',
                    [{'name': 'task_1', 'role': 'self'}],
                    True
                )
            )
            self.assertFalse(m_resolve.resolve.called)

    def test_resolve_relation_when_no_chains(self):
        node_ids = ['1', '2', '3']
        self.serializer.tasks_per_node = dict(
            (node_id, ['task_{0}'.format(node_id)])
            for node_id in node_ids
        )
        self.assertItemsEqual(
            [{'node_id': '1', 'name': 'task_1'}],
            self.serializer.resolve_relation('task_1', node_ids, True)
        )
        self.assertItemsEqual(
            ({'node_id': i, 'name': 'task_{0}'.format(i)} for i in node_ids),
            self.serializer.resolve_relation('/task/', node_ids, True)
        )

    def test_resolve_relation_in_chain(self):
        node_ids = ['1', '2', '3']
        self.serializer.tasks_per_node = dict(
            (node_id, ['task_{0}'.format(node_id)])
            for node_id in node_ids
        )
        self.serializer.task_processor.origin_task_ids = {
            'task_1': 'task', 'task_2': 'task', 'task_3': 'task2'
        }
        self.serializer.tasks_per_node['1'].append('task_2')
        self.assertItemsEqual(
            [
                {'node_id': '1', 'name': 'task_start'},
                {'node_id': '2', 'name': 'task_start'},
            ],
            self.serializer.resolve_relation('task', node_ids, True)
        )
        self.assertItemsEqual(
            [
                {'node_id': '1', 'name': 'task_end'},
                {'node_id': '2', 'name': 'task_end'}
            ],
            self.serializer.resolve_relation('task', node_ids, False)
        )
        self.assertItemsEqual(
            [{'node_id': '1', 'name': 'task_1'}],
            self.serializer.resolve_relation('task_1', node_ids, False)
        )

    @mock.patch.object(task_based_deploy, 'logger')
    def test_resolve_relation_warn_if_not_found(self, m_logger):
        node_ids = ['1', '2', '3']
        self.serializer.tasks_per_node = dict(
            (node_id, ['task_{0}'.format(node_id)])
            for node_id in node_ids
        )
        self.assertItemsEqual(
            [],
            self.serializer.resolve_relation('not_exists', node_ids, False)
        )
        m_logger.warning.assert_called_once_with(
            "Dependency '%s' cannot be resolved: "
            "no candidates in nodes '%s'.",
            "not_exists", "1, 2, 3"
        )

    def test_ensure_task_based_deployment_allowed(self):
        self.assertRaises(
            task_based_deploy.errors.TaskBaseDeploymentNotAllowed,
            self.serializer.ensure_task_based_deploy_allowed,
            {'id': 'task'}
        )
        self.assertRaises(
            task_based_deploy.errors.TaskBaseDeploymentNotAllowed,
            self.serializer.ensure_task_based_deploy_allowed,
            {'id': 'task', 'version': '1.2.3'}
        )
        self.assertNotRaises(
            task_based_deploy.errors.TaskBaseDeploymentNotAllowed,
            self.serializer.ensure_task_based_deploy_allowed,
            {'id': 'task', 'version': consts.TASK_CROSS_DEPENDENCY}
        )


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
        serializer = task_based_deploy.NoopSerializer(
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
        serializer = task_based_deploy.NoopSerializer(
            {'id': 'deploy_start', 'type': 'stage'},
            self.env, self.env.nodes
        )
        tasks = list(serializer.serialize())
        self.assertEqual(1, len(tasks))
        task = tasks[0]

        self.assertEqual(
            {
                'type': consts.ORCHESTRATOR_TASK_TYPES.skipped,
                'uids': [None],
                'fail_on_error': False,
                'skipped': True
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
        factory = task_based_deploy.DeployTaskSerializer()
        self.assertIs(
            task_based_deploy.CreateVMsOnCompute,
            factory.get_stage_serializer(
                self.make_task('generate_vms')
            )
        )

        self.assertIs(
            task_based_deploy.NoopSerializer,
            factory.get_stage_serializer(
                self.make_task('post_deployment', type='stage')
            )
        )
        self.assertIs(
            task_based_deploy.NoopSerializer,
            factory.get_stage_serializer(
                self.make_task('pre_deployment', type='skipped')
            )
        )
        self.assertTrue(
            issubclass(
                factory.get_stage_serializer(
                    self.make_task('upload_repos')
                ),
                task_based_deploy.StandartConfigRolesHook
            )
        )


class TestTaskProcessor(BaseUnitTest):
    def setUp(self):
        self.processor = task_based_deploy.TaskProcessor()

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
            (
                {'name': 'test_task_start', 'node_id': n}
                for n in previous['uids']
            ),
            current['requires_ex']
        )
        current['requires_ex'] = [{'name': 'test_task_start', 'node_id': '0'}]
        self.processor._link_tasks(previous, current)
        self.assertItemsEqual(
            (
                {'name': 'test_task_start', 'node_id': n}
                for n in ['0'] + previous['uids']
            ),
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
            'id': 'task', 'requires': ['a'], 'cross-depends': [{'name': 'b'}],
            'required_for': ['c'], 'cross-depended-by': [{'name': 'd'}]
        }
        serialized = iter([{'type': 'puppet'}])

        tasks = self.processor.process_tasks(origin_task, serialized)
        self.assertItemsEqual(
            [dict(origin_task, type='puppet')],
            tasks
        )
        self.assertEqual('task', self.processor.get_origin('task'))

    def test_process_if_chain(self):
        origin_task = {
            'id': 'task', 'requires': ['a'], 'cross-depends': [{'name': 'b'}],
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
