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

import exceptions
import mock
import multiprocessing.dummy
import pickle
import tempfile
import yaml

from nailgun import consts
from nailgun import errors
from nailgun import lcm
from nailgun import objects
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

    def setUp(self):
        super(TestTransactionSerializer, self).setUp()
        self.cluster = self.env.create_cluster(api=False)
        self.transaction = objects.Transaction.create(
            {'cluster_id': self.cluster.id})

    def test_serialize_integration(self):
        serialized = lcm.TransactionSerializer.serialize(
            self.transaction, self.context, self.tasks, self.resolver
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
            self.transaction, self.context, self.resolver
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
            self.transaction, self.context, self.resolver
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
            self.transaction, self.context, tasks, self.resolver
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
            self.transaction, self.context, self.resolver
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
            self.transaction, self.context, self.resolver
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
            self.transaction, self.context, self.resolver
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

    @mock.patch('nailgun.lcm.transaction_serializer.settings.LCM_DS_ENABLED',
                new=True)
    @mock.patch('nailgun.lcm.transaction_serializer.'
                'DistributedProcessingPolicy._save_context')
    @mock.patch('nailgun.lcm.transaction_serializer.'
                'DistributedProcessingPolicy._save_settings')
    def test_distributed_serialization(self, save_settings, save_context):
        with mock.patch(
                'nailgun.lcm.transaction_serializer.dispy.JobCluster'
        ) as job_cluster:
            submit = mock.Mock()
            job_cluster.return_value.submit = submit
            lcm.TransactionSerializer.serialize(
                self.transaction, self.context,
                self.tasks, self.resolver)
            self.assertTrue(submit.called)
            # 4 controller task + 1 compute + 1 cinder
            self.assertTrue(6, submit.call_count)

            self.assertTrue(save_context.called)
            self.assertTrue(save_settings.called)

    @mock.patch('nailgun.lcm.transaction_serializer.'
                'DistributedProcessingPolicy._save_context')
    @mock.patch('nailgun.lcm.transaction_serializer.'
                'DistributedProcessingPolicy._save_settings')
    def test_distributed_serialization_create_job_cluster(self, _, __):
        policy = lcm.transaction_serializer.DistributedProcessingPolicy(
            self.transaction)

        self.env.create_node(api=False, cluster_id=self.cluster.id)
        self.env.create_node(api=False, cluster_id=self.cluster.id)
        self.env.create_node(api=False)

        another_cluster = self.env.create_cluster(api=False)
        self.env.create_node(api=False, cluster_id=another_cluster.id)

        expected_nodes = [node.ip for node in self.cluster.nodes]
        expected_nodes.append('localhost')

        with mock.patch('nailgun.lcm.transaction_serializer.dispy.'
                        'JobCluster') as job_cluster:
            policy._create_job_cluster(self.context)
            nodes = job_cluster.call_args[1]['nodes']
            self.assertItemsEqual(expected_nodes, nodes)

    @mock.patch('nailgun.lcm.transaction_serializer.settings.LCM_DS_NODES',
                new=['xx'])
    @mock.patch('nailgun.lcm.transaction_serializer.'
                'DistributedProcessingPolicy._save_context')
    @mock.patch('nailgun.lcm.transaction_serializer.'
                'DistributedProcessingPolicy._save_settings')
    def test_distributed_serialization_nodes_list_set_in_config(self, _, __):
        policy = lcm.transaction_serializer.DistributedProcessingPolicy(
            self.transaction)

        self.env.create_node(api=False, cluster_id=self.cluster.id)
        self.env.create_node(api=False, cluster_id=self.cluster.id)
        self.env.create_node(api=False)

        with mock.patch('nailgun.lcm.transaction_serializer.dispy.'
                        'JobCluster') as job_cluster:
            policy._create_job_cluster(self.context)
            nodes = job_cluster.call_args[1]['nodes']
            self.assertItemsEqual(['xx'], nodes)

    def test_distributed_serialization_rpc_serialize_task(self):
        task = {
            'id': 'task1', 'roles': ['controller'],
            'type': 'puppet', 'version': '2.0.0',
            'parameters': {
                'master_ip': '{MN_IP}',
                'host': {'yaql_exp': '$.public_ssl.hostname'},
                'attr': {'yaql_exp': '$node.attributes.a_str'}
            }
        }

        with tempfile.NamedTemporaryFile() as context_file:
            pickle.dump(self.context, context_file)
            context_file.flush()
            with tempfile.NamedTemporaryFile() as settings_file:
                yaml.safe_dump(settings.config, settings_file)
                settings_file.flush()

                lcm.transaction_serializer._dispy_setup_computation_node(
                    context_file.name, settings_file.name)

                # Checking node 1 serialization
                (node_id, serialized), _ = lcm.transaction_serializer.\
                    _dispy_serialize_task_for_node({'MN_IP': '10.0.0.1',
                                                    'SETTINGS': {}},
                                                   ('1', task))

                expected = {
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
                self.assertEqual('1', node_id)
                self.assertEqual(expected, serialized)

                # Checking node 2 serialization
                (node_id, serialized), _ = lcm.transaction_serializer.\
                    _dispy_serialize_task_for_node({'SETTINGS': {}},
                                                   ('2', task))
                expected = {
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
                self.assertEqual('2', node_id)
                self.assertEqual(expected, serialized)

                lcm.transaction_serializer._dispy_cleanup_computation_node()

    def test_distributed_serialization_rpc_serialize_task_failure(self):
        task = {
            'id': 'task1', 'roles': ['controller'],
            'type': 'puppet', 'version': '2.0.0',
            'parameters': {
                'fake': {'yaql_exp': '$.some.fake_param'}
            }
        }
        with tempfile.NamedTemporaryFile() as context_file:
            pickle.dump(self.context, context_file)
            context_file.flush()
            with tempfile.NamedTemporaryFile() as settings_file:
                yaml.safe_dump(settings.config, settings_file)
                settings_file.flush()

                lcm.transaction_serializer._dispy_setup_computation_node(
                    context_file.name, settings_file.name)

                (_, __), err = lcm.transaction_serializer.\
                    _dispy_serialize_task_for_node({'SETTINGS': {}},
                                                   ('2', task))
                self.assertIsInstance(err, exceptions.KeyError)

                lcm.transaction_serializer._dispy_cleanup_computation_node()

    @mock.patch('nailgun.lcm.transaction_serializer.'
                'DistributedProcessingPolicy._save_context')
    @mock.patch('nailgun.lcm.transaction_serializer.'
                'DistributedProcessingPolicy._save_settings')
    def test_distributed_serialization_resubmit_in_job_callback(
            self, save_settings, save_context):
        policy = lcm.transaction_serializer.DistributedProcessingPolicy(
            self.transaction)

        with tempfile.NamedTemporaryFile() as context_file:
            pickle.dump(self.context, context_file)
            context_file.flush()
            save_context.return_value = context_file.name

            with tempfile.NamedTemporaryFile() as settings_file:
                yaml.safe_dump(settings.config, settings_file)
                settings_file.flush()
                save_settings.return_value = settings_file.name

                policy._create_job_cluster(self.context)

                job = mock.Mock()
                job.id = 'xx'
                policy.pending_jobs[job.id] = ()

                # Checking job is resubmitted if job.id is set
                for status in policy.resubmit_statuses:
                    submit = mock.Mock()
                    policy.job_cluster.submit = submit
                    job.status = status

                    policy._job_callback(job)

                    self.assertTrue(submit.called)
                    self.assertEqual(1, submit.call_count)

                # Checking job is not resubmitted if job.id is None
                job.id = None
                for status in policy.resubmit_statuses:
                    submit = mock.Mock()
                    policy.job_cluster.submit = submit
                    job.status = status

                    policy._job_callback(job)

                    self.assertFalse(submit.called)

    @mock.patch('nailgun.lcm.transaction_serializer.'
                'DistributedProcessingPolicy._create_job_cluster')
    def test_distributed_serialization_resubmit_in_execute(self, _):
        policy = lcm.transaction_serializer.DistributedProcessingPolicy(
            self.transaction)

        tasks = [
            ('1', {'id': 'task1', 'roles': ['controller'],
                   'type': 'puppet', 'version': '2.0.0'})
        ]

        for status in policy.resubmit_statuses:

            job_cluster = mock.Mock()
            policy.job_cluster = job_cluster

            job = mock.Mock()
            job.status = status

            submit = mock.Mock()
            submit.return_value = job

            job_cluster.submit = submit

            for _ in policy.execute(self.context, None, tasks):
                pass

            # Task with status Cancelled, Abandoned or Terminated
            # must be called twice
            self.assertEqual(2, submit.call_count)


class TestConcurrencyPolicy(BaseTestCase):

    def setUp(self, *args, **kwargs):
        super(TestConcurrencyPolicy, self).setUp(*args, **kwargs)
        self.cluster = self.env.create_cluster(api=False)
        self.transaction = objects.Transaction.create(
            {'cluster_id': self.cluster.id})

    @mock.patch(
        'nailgun.lcm.transaction_serializer.multiprocessing.cpu_count',
        return_value=1
    )
    def test_one_cpu(self, cpu_count):
        policy = lcm.transaction_serializer.get_processing_policy(
            self.transaction)
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
            self.transaction)
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
            self.transaction)
        self.assertIsInstance(
            policy,
            lcm.transaction_serializer.SingleWorkerConcurrencyPolicy
        )
        self.assertTrue(cpu_count.is_called)

    @mock.patch(
        'nailgun.lcm.transaction_serializer.settings.LCM_DS_ENABLED',
        new=True
    )
    def test_distributed_serialization_enabled_in_settings(self):
        policy = lcm.transaction_serializer.get_processing_policy(
            self.transaction)
        self.assertIsInstance(
            policy,
            lcm.transaction_serializer.DistributedProcessingPolicy
        )

    def test_distributed_serialization_enabled_in_cluster(self):
        cluster = self.env.create_cluster(api=False)
        transaction = objects.Transaction.create(
            {'cluster_id': cluster.id})

        # Checking distributed is not enabled in settings
        policy = lcm.transaction_serializer.get_processing_policy(
            transaction)
        self.assertNotIsInstance(
            policy,
            lcm.transaction_serializer.DistributedProcessingPolicy
        )

        # Checking distributed serialization policy is used after
        # enabling in cluster settings
        attrs = objects.Cluster.get_editable_attributes(cluster)
        policy = attrs['common']['serialization_policy']
        policy['value'] = consts.SERIALIZATION_POLICY.distributed
        objects.Cluster.update_attributes(cluster, {'editable': attrs})
        policy = lcm.transaction_serializer.get_processing_policy(
            transaction)
        self.assertIsInstance(
            policy,
            lcm.transaction_serializer.DistributedProcessingPolicy
        )
