# -*- coding: utf-8 -*-

#    Copyright 2016 Mirantis, Inc.
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

import copy
import exceptions
import mock
import multiprocessing.dummy

from nailgun import consts
from nailgun import errors
from nailgun import lcm
from nailgun.lcm import TransactionContext
from nailgun.settings import settings
from nailgun.test.base import BaseTestCase
from nailgun.utils.resolvers import TagResolver


class TestTransactionSerializer(BaseTestCase):
    @classmethod
    def setUpClass(cls):
        super(TestTransactionSerializer, cls).setUpClass()
        cls.tasks = [
            {
                'id': 'task1', 'roles': ['controller'],
                'type': 'puppet', 'version': '2.0.0',
                'condition': {
                    'yaql_exp': '$.public_ssl.hostname = localhost'
                },
                'parameters': {},
                'requires': ['task3'],
                'required_for': ['task2'],
                'cross_depends': [{'name': 'task2', 'role': 'compute'}],
                'cross_depended_by': [{'name': 'task3', 'role': 'cinder'}]
            },
            {
                'id': 'task2', 'roles': ['compute', 'controller'],
                'type': 'puppet', 'version': '2.0.0',
                'condition': {
                    'yaql_exp': '$.public_ssl.hostname != localhost'
                },
                'parameters': {},
                'cross_depends': [{'name': 'task3', 'role': 'cinder'}]
            },
            {
                'id': 'task3', 'roles': ['cinder', 'controller'],
                'type': 'puppet', 'version': '2.0.0',
                'condition': 'settings:public_ssl.hostname != "localhost"',
                'parameters': {},
                'cross_depends': [{'name': 'task3', 'role': '/.*/'}],
                'cross_depended_by': [{'name': 'task2', 'role': 'self'}]
            },
            {
                'id': 'task4', 'roles': ['controller'],
                'type': 'puppet', 'version': '2.0.0',
                'parameters': {},
                'cross_depended_by': [{'name': 'task3'}]
            }
        ]

        cls.nodes = [
            mock.MagicMock(uid='1', roles=['controller']),
            mock.MagicMock(uid='2', roles=['compute']),
            mock.MagicMock(uid='3', roles=['cinder']),
            mock.MagicMock(uid='4', roles=['custom']),
        ]

        cls.context = lcm.TransactionContext({
            'common': {
                'cluster': {'id': 1},
                'release': {'version': 'liberty-9.0'},
                'openstack_version': 'liberty-9.0',
                'public_ssl': {'hostname': 'localhost'},
            },
            'nodes': {
                '1': {
                    'attributes': {
                        'a_str': 'text1',
                        'a_int': 1
                    }
                },
                '2': {
                    'attributes': {
                        'a_str': 'text2',
                        'a_int': 2
                    }
                },
                '3': {
                    'attributes': {
                        'a_str': 'text3',
                        'a_int': 3
                    }
                },
                '4': {
                    'attributes': {
                        'a_str': 'text3',
                        'a_int': 3
                    }
                }
            }
        })

        with mock.patch('nailgun.utils.resolvers.objects') as m_objects:
            m_objects.Node.all_tags = lambda x: x.roles
            cls.resolver = TagResolver(cls.nodes)

    def test_serialize_integration(self):
        serialized = lcm.TransactionSerializer.serialize(
            self.context, self.tasks, self.resolver
        )[1]
        # controller
        self.datadiff(
            [
                {
                    'id': 'task1', 'type': 'puppet', 'fail_on_error': True,
                    'parameters': {},
                    'requires': [
                        {'node_id': '1', 'name': 'task3'},
                        {'node_id': '2', 'name': 'task2'},
                    ],
                    'required_for': [
                        {'node_id': '1', 'name': 'task2'},
                        {'node_id': '3', 'name': 'task3'},
                    ]
                },
                {
                    'id': 'task2', 'type': 'skipped', 'fail_on_error': False,
                    'requires': [
                        {'node_id': '3', 'name': 'task3'},
                    ],
                },
                {
                    'id': 'task3', 'type': 'skipped', 'fail_on_error': False,
                    'requires': [
                        {'node_id': '3', 'name': 'task3'},
                    ],
                    'required_for': [
                        {'node_id': '1', 'name': 'task2'},
                    ]
                },
                {
                    'id': 'task4', 'type': 'puppet', 'fail_on_error': True,
                    'parameters': {},
                    'required_for': [
                        {'node_id': '1', 'name': 'task3'},
                        {'node_id': '3', 'name': 'task3'},
                    ]
                }

            ],
            serialized['1'],
            ignore_keys=['parameters', 'fail_on_error'],
            compare_sorted=True,
        )
        # compute
        self.datadiff(
            [
                {
                    'id': 'task2', 'type': 'skipped', 'fail_on_error': True,
                    'requires': [
                        {'node_id': '3', 'name': 'task3'},
                    ],
                }
            ],
            serialized['2'],
            ignore_keys=['parameters', 'fail_on_error'],
            compare_sorted=True,
        )
        # cinder
        self.datadiff(
            [
                {
                    'id': 'task3', 'type': 'skipped', 'fail_on_error': True,
                    'requires': [
                        {'node_id': '1', 'name': 'task3'},
                    ]
                }
            ],
            serialized['3'],
            ignore_keys=['parameters', 'fail_on_error'],
            compare_sorted=True,
        )

    def test_resolve_nodes(self):
        serializer = lcm.TransactionSerializer(
            self.context, self.resolver
        )
        self.assertEqual(
            [None],
            serializer.resolve_nodes(
                {'id': 'deploy_start',
                 'type': consts.ORCHESTRATOR_TASK_TYPES.stage}
            )
        )
        self.assertItemsEqual(
            ['2'],
            serializer.resolve_nodes(
                {'id': 'deploy_start',
                 'type': consts.ORCHESTRATOR_TASK_TYPES.skipped,
                 'groups': ['compute']},
            )
        )
        self.assertItemsEqual(
            ['1'],
            serializer.resolve_nodes(
                {'id': 'deploy_start',
                 'type': consts.ORCHESTRATOR_TASK_TYPES.skipped,
                 'roles': ['controller']}
            )
        )

    def test_dependencies_de_duplication(self):
        serializer = lcm.TransactionSerializer(
            self.context, self.resolver
        )
        serializer.tasks_graph = {
            None: {},
            '1': {
                'task1': {
                    'id': 'task1',
                    'requires': ['task2'],
                    'cross_depends': [
                        {'role': 'self', 'name': 'task2'},
                    ]
                },
                'task2': {
                    'id': 'task2',
                    'required_for': ['task1'],
                    'cross_depended_by': [{'role': 'self', 'name': 'task1'}]
                }
            }
        }
        serializer.resolve_dependencies()
        self.datadiff(
            {
                'task1': {
                    'id': 'task1',
                    'requires': [{'node_id': '1', 'name': 'task2'}],
                },
                'task2': {
                    'id': 'task2',
                    'required_for': [{'node_id': '1', 'name': 'task1'}],
                }
            },
            serializer.tasks_graph['1'],
            compare_sorted=True
        )

    def test_tasks_expand_groups(self):
        tasks = list(self.tasks)
        tasks.append({
            'id': 'task4', 'roles': ['/.*/'],
            'type': 'puppet', 'version': '2.0.0',
            'parameters': {},
            'cross_depends': [{'name': 'task2', 'role': 'self'}],
        })
        tasks.append({
            'id': 'custom', 'type': 'group', 'roles': 'custom',
            'fault_tolerance': '100%',
            'tasks': ['task4', 'task2']
        })
        tasks.append({
            'id': 'controller', 'type': 'group', 'roles': 'controller',
            'fault_tolerance': '0%',
            'tasks': ['task4', 'task2']
        })
        tasks.append({
            'id': 'compute', 'type': 'group', 'roles': 'compute',
            'tasks': ['task4', 'task2']
        })
        serialized = lcm.TransactionSerializer.serialize(
            self.context, tasks, self.resolver
        )
        tasks_per_node = serialized[1]
        self.datadiff(
            [
                {
                    'id': 'task2', 'type': 'skipped', 'fail_on_error': True,
                    'requires': [{'name': 'task3', 'node_id': '3'}]

                },
                {
                    'id': 'task4', 'type': 'puppet', 'fail_on_error': True,
                    'parameters': {},
                    'requires': [{'name': 'task2', 'node_id': '4'}]

                },
            ],
            tasks_per_node['4'],
            ignore_keys=['parameters', 'fail_on_error'],
            compare_sorted=True
        )

        tasks_metadata = serialized[2]
        self.datadiff(
            {
                'fault_tolerance_groups': [
                    {
                        'name': 'custom',
                        'node_ids': ['4'],
                        'fault_tolerance': 1
                    },
                    {
                        'name': 'controller',
                        'node_ids': ['1'],
                        'fault_tolerance': 0
                    },
                    {
                        'name': 'compute',
                        'node_ids': ['2'],
                        'fault_tolerance': 2
                    }
                ]
            },
            tasks_metadata,
            compare_sorted=True
        )

    def test_expand_dependencies(self):
        serializer = lcm.TransactionSerializer(
            self.context, self.resolver
        )
        serializer.tasks_graph = {
            '1': {'task1': {}},
            '2': {'task2': {}},
            None: {'deploy_start': {}, 'deploy_end': {}}
        }
        self.assertItemsEqual([], serializer.expand_dependencies('1', None))
        self.assertItemsEqual([], serializer.expand_dependencies('1', []))
        self.assertItemsEqual(
            [('deploy_start', None), ('task2', '2')],
            serializer.expand_dependencies('2', ['deploy_start', 'task2'])
        )

    def test_expand_cross_dependencies(self):
        serializer = lcm.TransactionSerializer(
            self.context, self.resolver
        )
        serializer.tasks_graph = {
            '1': {'task1': {}, 'task2': {}},
            '2': {'task3': {}, 'task2': {}, 'task1': {}},
            '3': {'task3': {}},
            None: {'deploy_start': {}, 'deploy_end': {}}
        }
        self.assertItemsEqual(
            [], serializer.expand_cross_dependencies('task1', '1', None)
        )
        self.assertItemsEqual(
            [], serializer.expand_cross_dependencies('task1', '1', [])
        )

        self.assertItemsEqual(
            [
                ('deploy_start', None), ('task2', '2'),
                ('task3', '2'), ('task3', '3')
            ],
            serializer.expand_cross_dependencies(
                'task2', '1',
                [{'name': 'deploy_start', 'role': None},
                 {'name': 'task2', 'role': '/.*/'},
                 {'name': 'task3', 'role': '/.*/'}]
            )
        )
        self.assertItemsEqual(
            [('task2', '2'), ('task1', '1')],
            serializer.expand_cross_dependencies(
                'task2', '1',
                [{'name': 'task2'},
                 {'name': 'task1', 'role': 'self'}]
            )
        )

    def test_need_update_task(self):
        serializer = lcm.TransactionSerializer(
            self.context, self.resolver
        )
        self.assertTrue(serializer.need_update_task(
            {}, {"id": "task1", "type": "puppet"}
        ))
        self.assertTrue(serializer.need_update_task(
            {"task1": {"type": "skipped"}}, {"id": "task1", "type": "puppet"}
        ))

        self.assertFalse(serializer.need_update_task(
            {"task1": {"type": "skipped"}}, {"id": "task1", "type": "skipped"}
        ))

        self.assertFalse(serializer.need_update_task(
            {"task1": {"type": "puppet"}}, {"id": "task1", "type": "skipped"}
        ))

    @mock.patch(
        'nailgun.lcm.transaction_serializer.settings.LCM_CHECK_TASK_VERSION',
        new=True
    )
    def test_ensure_task_based_deploy_allowed_raises_if_version_check(self):
        self.assertRaises(
            errors.TaskBaseDeploymentNotAllowed,
            lcm.TransactionSerializer.ensure_task_based_deploy_allowed,
            {'type': consts.ORCHESTRATOR_TASK_TYPES.puppet,
             'version': '1.0.0', 'id': 'test'}
        )

    @mock.patch(
        'nailgun.lcm.transaction_serializer.settings.LCM_CHECK_TASK_VERSION',
        new=False
    )
    def test_ensure_task_based_deploy_allowed_if_not_version_check(self):
        self.assertNotRaises(
            errors.TaskBaseDeploymentNotAllowed,
            lcm.TransactionSerializer.ensure_task_based_deploy_allowed,
            {'type': consts.ORCHESTRATOR_TASK_TYPES.puppet,
             'version': '1.0.0', 'id': 'test'}
        )

    @mock.patch(
        'nailgun.lcm.transaction_serializer.settings'
        '.LCM_SERIALIZERS_CONCURRENCY_FACTOR',
        new=2
    )
    @mock.patch(
        'nailgun.lcm.transaction_serializer.multiprocessing',
        new=multiprocessing.dummy
    )
    def test_multi_processing_serialization(self):
        self.test_serialize_integration()

    def test_get_fault_tolerance(self):
        self.assertEqual(
            11,
            lcm.TransactionSerializer.calculate_fault_tolerance(None, 10)
        )
        self.assertEqual(
            10,
            lcm.TransactionSerializer.calculate_fault_tolerance('10', 10)
        )
        self.assertEqual(
            10,
            lcm.TransactionSerializer.calculate_fault_tolerance(10, 10)
        )
        self.assertEqual(
            1,
            lcm.TransactionSerializer.calculate_fault_tolerance('10%', 10)
        )
        self.assertEqual(
            11,
            lcm.TransactionSerializer.calculate_fault_tolerance('a%', 10)
        )
        self.assertEqual(
            9,
            lcm.TransactionSerializer.calculate_fault_tolerance(' -10%', 10)
        )
        self.assertEqual(
            9,
            lcm.TransactionSerializer.calculate_fault_tolerance('-1 ', 10)
        )

    def _get_context_for_distributed_serialization(self):
        new = copy.deepcopy(self.context.new)
        new['common']['serialization_policy'] = \
            consts.SERIALIZATION_POLICY.distributed
        return TransactionContext(new)

    @mock.patch('nailgun.lcm.transaction_serializer.distributed.wait')
    @mock.patch('nailgun.lcm.transaction_serializer.distributed.as_completed')
    def test_distributed_serialization(self, _, as_completed):
        context = self._get_context_for_distributed_serialization()

        with mock.patch(
                'nailgun.lcm.transaction_serializer.distributed.Client'
        ) as job_cluster:
            job = mock.Mock()
            job.result.return_value = [
                (('1', {"id": "task1", "type": "skipped"}), None)
            ]

            submit = mock.Mock()
            submit.return_value = job

            as_completed.return_value = [job]

            job_cluster.return_value.submit = submit
            job_cluster.return_value.scheduler_info.return_value = \
                {'workers': {'tcp://worker': {}}}

            lcm.TransactionSerializer.serialize(
                context, self.tasks, self.resolver)
            self.assertTrue(submit.called)
            # 4 controller task + 1 compute + 1 cinder
            self.assertTrue(6, submit.call_count)

    @mock.patch('nailgun.lcm.transaction_serializer.distributed.wait')
    @mock.patch('nailgun.lcm.transaction_serializer.distributed.as_completed')
    @mock.patch('nailgun.lcm.transaction_serializer.'
                'DistributedProcessingPolicy._get_formatter_context')
    def test_distributed_serialization_workers_scope(self, formatter_context,
                                                     as_completed, _):
        context = self._get_context_for_distributed_serialization()

        node_id = '1'
        task = {
            'id': 'task1', 'roles': ['controller'],
            'type': 'puppet', 'version': '2.0.0'
        }

        with mock.patch(
                'nailgun.lcm.transaction_serializer.distributed.Client'
        ) as job_cluster:

            # Mocking job processing
            job = mock.Mock()
            job.result.return_value = [((node_id, task), None)]

            submit = mock.Mock()
            submit.return_value = job

            as_completed.return_value = [job]

            scatter = mock.Mock()
            job_cluster.return_value.scatter = scatter

            job_cluster.return_value.scatter.return_value = {}
            job_cluster.return_value.submit = submit

            formatter_context.return_value = {node_id: {}}

            # Configuring available workers
            job_cluster.return_value.scheduler_info.return_value = \
                {
                    'workers': {
                        'tcp://{0}'.format(settings.MASTER_IP): {},
                        'tcp://192.168.0.1:33334': {},
                        'tcp://127.0.0.2:33335': {},
                    }
                }

            # Performing serialization
            lcm.TransactionSerializer.serialize(
                context, [task], self.resolver
            )

            # Checking data is scattered only to expected workers
            scatter.assert_called_once()
            scatter.assert_called_with(
                {'context': context, 'settings_config': settings.config},
                broadcast=True,
                workers=[settings.MASTER_IP]
            )

            # Checking submit job only to expected workers
            submit.assert_called_once()
            serializer = lcm.transaction_serializer
            submit.assert_called_with(
                serializer._distributed_serialize_tasks_for_node,
                {node_id: formatter_context()},
                ((node_id, task),),
                job_cluster().scatter(),
                workers=set([settings.MASTER_IP])
            )

    def test_distributed_serialization_get_allowed_nodes_ips(self):
        policy = lcm.transaction_serializer.DistributedProcessingPolicy()

        context_data = {
            'common': {
                'serialization_policy':
                    consts.SERIALIZATION_POLICY.distributed,
                'ds_use_error': True,
                'ds_use_provisioned': True,
                'ds_use_discover': True,
                'ds_use_ready': False
            },
            'nodes': {
                '1': {'status': consts.NODE_STATUSES.error,
                      'ip': '10.20.0.3'},
                '2': {'status': consts.NODE_STATUSES.provisioned,
                      'ip': '10.20.0.4'},
                '3': {'status': consts.NODE_STATUSES.discover,
                      'ip': '10.20.0.5'},
                '4': {'status': consts.NODE_STATUSES.ready,
                      'ip': '10.20.0.6'},
            }
        }

        actual = policy._get_allowed_nodes_ips(
            TransactionContext(context_data))
        self.assertItemsEqual(
            [settings.MASTER_IP, '10.20.0.3', '10.20.0.4', '10.20.0.5'],
            actual
        )

    def test_distributed_serialization_get_allowed_nodes_statuses(self):
        policy = lcm.transaction_serializer.DistributedProcessingPolicy()
        context_data = {}
        actual = policy._get_allowed_nodes_statuses(
            TransactionContext(context_data))
        self.assertItemsEqual([], actual)

        context_data['common'] = {
            'ds_use_discover': False,
            'ds_use_provisioned': False,
            'ds_use_error': False,
            'ds_use_ready': False
        }
        actual = policy._get_allowed_nodes_statuses(
            TransactionContext(context_data))
        self.assertItemsEqual([], actual)

        context_data['common']['ds_use_discover'] = True
        actual = policy._get_allowed_nodes_statuses(
            TransactionContext(context_data))
        expected = [consts.NODE_STATUSES.discover]
        self.assertItemsEqual(expected, actual)

        context_data['common']['ds_use_provisioned'] = True
        actual = policy._get_allowed_nodes_statuses(
            TransactionContext(context_data))
        expected = [consts.NODE_STATUSES.discover,
                    consts.NODE_STATUSES.provisioned]
        self.assertItemsEqual(expected, actual)

        context_data['common']['ds_use_error'] = True
        actual = policy._get_allowed_nodes_statuses(
            TransactionContext(context_data))
        expected = [consts.NODE_STATUSES.discover,
                    consts.NODE_STATUSES.provisioned,
                    consts.NODE_STATUSES.error]
        self.assertItemsEqual(expected, actual)

        context_data['common']['ds_use_ready'] = True
        actual = policy._get_allowed_nodes_statuses(
            TransactionContext(context_data))
        expected = [consts.NODE_STATUSES.discover,
                    consts.NODE_STATUSES.provisioned,
                    consts.NODE_STATUSES.error,
                    consts.NODE_STATUSES.ready]
        self.assertItemsEqual(expected, actual)

    def test_distributed_serialization_get_allowed_workers(self):
        policy = lcm.transaction_serializer.DistributedProcessingPolicy()

        with mock.patch(
                'nailgun.lcm.transaction_serializer.distributed.Client'
        ) as job_cluster:
            job_cluster.scheduler_info.return_value = \
                {'workers': {
                    'tcp://10.20.0.2:1': {},
                    'tcp://10.20.0.2:2': {},
                    'tcp://10.20.0.3:1': {},
                    'tcp://10.20.0.3:2': {},
                    'tcp://10.20.0.3:3': {},
                    'tcp://10.20.0.4:1': {},
                    'tcp://10.20.0.5:1': {}
                }}
            allowed_ips = set(['10.20.0.2', '10.20.0.3', '10.20.0.5'])

            expected = ['10.20.0.2:1', '10.20.0.2:2', '10.20.0.3:1',
                        '10.20.0.3:2', '10.20.0.3:3', '10.20.0.5:1']
            actual = policy._get_allowed_workers(job_cluster, allowed_ips)
            self.assertItemsEqual(expected, actual)

    def test_distributed_serialization_serialize_task(self):
        task = {
            'id': 'task1', 'roles': ['controller'],
            'type': 'puppet', 'version': '2.0.0',
            'parameters': {
                'master_ip': '{MN_IP}',
                'host': {'yaql_exp': '$.public_ssl.hostname'},
                'attr': {'yaql_exp': '$node.attributes.a_str'}
            }
        }

        formatter_contexts_idx = {
            '1': {'MN_IP': '10.0.0.1'},
            '2': {}
        }
        scattered_data = {
            'settings_config': settings.config,
            'context': self.context
        }

        serializer = lcm.transaction_serializer
        actual = serializer._distributed_serialize_tasks_for_node(
            formatter_contexts_idx, [('1', task), ('2', task)], scattered_data)

        expected = [
            (
                (
                    '1',
                    {
                        'id': 'task1',
                        'type': 'puppet',
                        'parameters': {
                            'cwd': '/',
                            'master_ip': '10.0.0.1',
                            'host': 'localhost',
                            'attr': 'text1'
                        },
                        'fail_on_error': True
                    }
                ),
                None
            ),
            (
                (
                    '2',
                    {
                        'id': 'task1',
                        'type': 'puppet',
                        'parameters': {
                            'cwd': '/',
                            'master_ip': '{MN_IP}',
                            'host': 'localhost',
                            'attr': 'text2'
                        },
                        'fail_on_error': True
                    }
                ),
                None
            )
        ]

        self.assertItemsEqual(expected, actual)

    def test_distributed_serialization_serialize_task_failure(self):
        task = {
            'id': 'task1', 'roles': ['controller'],
            'type': 'puppet', 'version': '2.0.0',
            'parameters': {
                'fake': {'yaql_exp': '$.some.fake_param'}
            }
        }

        formatter_contexts_idx = {'2': {}}
        scattered_data = {
            'settings_config': settings.config,
            'context': self.context
        }

        serializer = lcm.transaction_serializer
        result = serializer._distributed_serialize_tasks_for_node(
            formatter_contexts_idx, [('2', task)], scattered_data)
        (_, __), err = result[0]
        self.assertIsInstance(err, exceptions.KeyError)


class TestConcurrencyPolicy(BaseTestCase):

    @mock.patch(
        'nailgun.lcm.transaction_serializer.multiprocessing.cpu_count',
        return_value=1
    )
    def test_one_cpu(self, cpu_count):
        policy = lcm.transaction_serializer.get_processing_policy(
            lcm.TransactionContext({}))
        self.assertIsInstance(
            policy,
            lcm.transaction_serializer.SingleWorkerConcurrencyPolicy
        )
        self.assertTrue(cpu_count.is_called)

    @mock.patch(
        'nailgun.lcm.transaction_serializer.multiprocessing.cpu_count',
        return_value=0
    )
    def test_zero_cpu(self, cpu_count):
        policy = lcm.transaction_serializer.get_processing_policy(
            lcm.TransactionContext({}))
        self.assertIsInstance(
            policy,
            lcm.transaction_serializer.SingleWorkerConcurrencyPolicy
        )
        self.assertTrue(cpu_count.is_called)

    @mock.patch(
        'nailgun.lcm.transaction_serializer.multiprocessing.cpu_count',
        side_effect=NotImplementedError
    )
    def test_cpu_count_not_implemented(self, cpu_count):
        policy = lcm.transaction_serializer.get_processing_policy(
            lcm.TransactionContext({}))
        self.assertIsInstance(
            policy,
            lcm.transaction_serializer.SingleWorkerConcurrencyPolicy
        )
        self.assertTrue(cpu_count.is_called)

    def test_distributed_serialization_enabled_in_cluster(self):
        context_data = {'common': {
            'serialization_policy': consts.SERIALIZATION_POLICY.distributed
        }}
        policy = lcm.transaction_serializer.get_processing_policy(
            lcm.TransactionContext(context_data))
        self.assertIsInstance(
            policy,
            lcm.transaction_serializer.DistributedProcessingPolicy
        )
