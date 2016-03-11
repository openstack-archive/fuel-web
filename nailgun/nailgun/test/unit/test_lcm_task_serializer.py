# -*- coding: utf-8 -*-
#    Copyright 2016 Mirantis, Inc.
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

from nailgun import consts
from nailgun.errors import errors
from nailgun.lcm.context import TransactionContext
from nailgun.lcm import task_serializer

from nailgun.test.base import BaseUnitTest


class TestDefaultTaskSerializer(BaseUnitTest):
    @classmethod
    def setUpClass(cls):
        cls.serializer_class = task_serializer.DefaultTaskSerializer
        cls.context = TransactionContext({
            '1': {
                'environment': {'id': 1},
                'release': {'version': 'liberty-9.0'},
                'openstack_version': 'liberty-9.0',
                'public_ssl': {'hostname': 'localhost'},
                'attributes': {
                    'a_str': 'text1',
                    'a_int': 1
                }
            },
            '2': {
                'environment': {'id': 2},
                'release': {'version': 'liberty-9.0'},
                'openstack_version': 'liberty-9.0',
                'public_ssl': {'hostname': 'localhost'},
                'attributes': {
                    'a_str': 'text2',
                    'a_int': 2
                }
            }
        })

    def check_legacy_condition(self, condition, expected):
        task_template = {
            'id': 'test',
            'type': 'puppet',
            'parameters': {},
            'condition': condition
        }
        serializer = self.serializer_class(self.context, task_template)
        for node_id, result in expected:
            self.assertEqual(result, serializer.should_execute(node_id))

    def test_should_execute_condition_for_settings(self):
        self.check_legacy_condition(
            "settings:common.attributes.a_str.value == 'text1'",
            [('1', True), ('2', False)]
        )

    def test_should_execute_condition_for_cluster(self):
        self.check_legacy_condition(
            "cluster:id == 1",
            [('1', True), ('2', False)]
        )

    def should_execute_returns_true_if_no_condition(self):
        task_template = {
            'id': 'test',
            'type': 'puppet',
            'parameters': {},
        }
        serializer = self.serializer_class(self.context, task_template)
        self.assertTrue(serializer.should_execute('1'))
        self.assertTrue(serializer.should_execute('2'))

    def test_transform_legacy_condition(self):
        cases = [
            (
                'settings:additional_components.ceilometer.value == 1',
                'settings:ceilometer.enabled == 1',
            ),
            (
                'settings:common.vms_create.value == 1',
                'settings:vms_create == 1',
            ),
            (
                'settings:my.id.value == 2',
                'settings:my.id == 2',
            ),
            (
                'settings:common.value.id == 2',
                'settings:value.id == 2',
            ),
            (
                'cluster:id == 2',
                'cluster:id == 2'
            ),
            (
                'cluster:common.id.value == 2',
                'cluster:common.id.value == 2',
            ),
        ]
        for value, expected in cases:
            self.assertEqual(
                expected,
                self.serializer_class.transform_legacy_condition(value)
            )

    def test_serialize_with_format(self):
        task_template = {
            'id': 'test',
            'roles': ['controller'],
            'condition': '1',
            'type': 'upload_file',
            'parameters': {
                'data': {
                    'generator': 'from_deployment_info',
                    'generator_arg': 'environment',
                },
                'path': '/etc/{CLUSTER_ID}/astute.yaml'
            },
            'requires': ['deploy_start'],
            'required_for': ['deploy_end']
        }
        serializer = self.serializer_class(self.context, task_template)
        serialized = serializer.serialize('1')
        task_template['parameters']['data'] = \
            self.context.get_deployment_info('1')['environment']
        task_template['parameters']['path'] = '/etc/1/astute.yaml'
        task_template['parameters']['cwd'] = '/'
        task_template['fail_on_error'] = True
        del task_template['condition']
        del task_template['roles']
        self.assertEqual(task_template, serialized)

    def test_serialize_does_not_fail_if_format_fail(self):
        task_template = {
            'id': 'test',
            'type': 'upload_file',
            'parameters': {
                'cmd': "cat /etc/astute.yaml | awk '{ print $1 }'",
                'cwd': '/tmp/'
            },
            'fail_on_error': False
        }
        serializer = self.serializer_class(self.context, task_template)
        serialized = serializer.serialize('1')
        self.assertEqual(task_template, serialized)

    def test_serialize_skipped_task(self):
        task_template = {
            'id': 'test',
            'type': 'upload_file',
            'condition': '0',
            'parameters': {
                'cmd': "cat /etc/astute.yaml | awk '{ print $1 }'",
                'cwd': '/tmp/'
            },
            'fail_on_error': True,
            'requires': ['deploy_start'],
            'required_for': ['deploy_end'],
            'cross_depends': [{'roles': '*', 'name': 'task1'}],
            'cross_depended_by': [{'roles': '*', 'name': 'task1'}],
        }
        serializer = self.serializer_class(self.context, task_template)
        serialized = serializer.serialize('1')
        self.assertEqual(
            {
                'id': 'test',
                'type': consts.ORCHESTRATOR_TASK_TYPES.skipped,
                'fail_on_error': False,
                'requires': ['deploy_start'],
                'required_for': ['deploy_end'],
                'cross_depends': [{'roles': '*', 'name': 'task1'}],
                'cross_depended_by': [{'roles': '*', 'name': 'task1'}],
            },
            serialized
        )


class TestTasksSerializersFactory(BaseUnitTest):
    factory_class = task_serializer.TasksSerializersFactory

    def test_create_serializer_for_generic(self):
        common_task_types = set(consts.ORCHESTRATOR_TASK_TYPES)
        common_task_types.discard(consts.ORCHESTRATOR_TASK_TYPES.role)
        common_task_types.discard(consts.ORCHESTRATOR_TASK_TYPES.skipped)
        common_task_types.discard(consts.ORCHESTRATOR_TASK_TYPES.stage)
        common_task_types.discard(consts.ORCHESTRATOR_TASK_TYPES.group)

        factory = self.factory_class(TransactionContext({}))
        for task_type in common_task_types:
            task = {'id': 'test', 'type': task_type}
            self.assertIsInstance(
                factory.create_serializer(task),
                task_serializer.DefaultTaskSerializer
            )

    def test_create_noop_serializer(self):
        noop_task_types = [
            consts.ORCHESTRATOR_TASK_TYPES.skipped,
            consts.ORCHESTRATOR_TASK_TYPES.stage
        ]
        factory = self.factory_class(TransactionContext({}))
        for task_type in noop_task_types:
            task = {'id': 'test', 'type': task_type}
            self.assertIsInstance(
                factory.create_serializer(task),
                task_serializer.NoopTaskSerializer
            )

    def test_create_raise_error_if_unknown_type(self):
        unsupported_task_types = [
            consts.ORCHESTRATOR_TASK_TYPES.group,
            consts.ORCHESTRATOR_TASK_TYPES.role
        ]
        factory = self.factory_class(TransactionContext({}))
        for task_type in unsupported_task_types:
            task = {'id': 'test', 'type': task_type}
            with self.assertRaises(errors.SerializerNotSupported):
                factory.create_serializer(task)
