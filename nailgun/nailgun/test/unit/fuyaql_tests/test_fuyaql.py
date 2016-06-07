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
from __future__ import print_function

import mock

from nailgun.fuyaql import fuyaql

from nailgun.test import base


@mock.patch('nailgun.fuyaql.fuyaql.objects')
class TestFuyaqlController(base.BaseUnitTest):
    def setUp(self):
        self.controller = fuyaql.FuYaqlController()
        self.old_context = {
            1: {
                'uid': 1,
                'roles': ['primary-controller'],
                'debug': 'true',
                'cinder': {
                    'db_password': '9RkYPCQT9V3LerPsp0qvuzmh',
                    'fixed_key': 'f74ce7f535cb61fc0ee8ba77',
                    'user_password': 'n8BMurmecwUWcH52nbdxqPtz'
                }
            }
        }
        self.new_context = {
            1: {
                'uid': 1,
                'roles': ['primary-controller'],
                'debug': 'false',
                'cinder': {
                    'db_password': '9RkYPCQT9V3LerPsp0qvuzmh',
                    'fixed_key': 'f74ce7f535cb61fc0ee8ba77',
                    'user_password': '62493085e6cfcaa4638ec08'
                }
            }
        } 

    def test_set_cluster(self, obj_mock):
        obj_mock.Cluster.get_by_uid.return_value = None
        self.assertFalse(self.controller.set_cluster())
        obj_mock.Cluster.get_by_uid.assert_called_once_with(
            None,
            fail_if_not_found=False
        )

        obj_mock.Cluster.get_by_uid.return_value = 'cluster'
        self.assertTrue(self.controller.set_cluster())
        obj_mock.TransactionCollection.get_last_succeed_run.assert_called_once_with(
            'cluster'
        )

    def test_set_task(self, obj_mock):
        self.controller._cluster = 'cluster'
        obj_mock.Transaction.get_by_uid.return_value = False
        self.assertFalse(self.controller.set_task(None, 1))

    def test_set_node(self, _):
        self.controller._infos[1] = self.new_context
        self.assertTrue(self.controller.set_node(1))
        self.assertFalse(self.controller.set_node(2))

    def test_get_node(self, _):
        self.controller._infos[1] = self.new_context
        self.controller._node_id = 1
        self.assertEqual(self.controller.get_node(), self.new_context[1])

    def test_get_clusters(self, obj_mock):
        obj_mock.ClusterCollection.order_by.return_value = 'cluster'
        self.assertEqual(self.controller.get_clusters(), 'cluster')

    def test_get_tasks(self, obj_mock):
        self.controller._cluster = mock.MagicMock()
        obj_mock.TransactionCollection.order_by.return_value = 'tasks'
        self.assertEqual(self.controller.get_tasks(), 'tasks')

    def test_get_nodes(self, _):
        self.controller._infos[1] = self.new_context
        infos = []
        for info in self.controller.get_nodes():
            infos.append(info)
        self.assertEqual(infos, [(self.new_context[1])])

    def test_evaluate(self, _):
        self.controller._infos = [self.old_context, self.new_context]
        self.controller._node_id = 1
        self.controller._cluster = True
        self.assertTrue(self.controller.evaluate('changed($)'))
        self.assertRaises(self.controller.evaluate('changed($.roles)'))

    def test_get_task(self, obj_mock):
        self.assertEqual(self.controller._get_task(False), None)

        obj_mock.Transaction.get_by_uid.return_value = False
        self.assertFalse(self.controller._get_task(True))

        task = mock.MagicMock()
        task.cluster_id = 4
        self.controller._cluster = mock.MagicMock()
        self.controller._cluster.id = 4
        obj_mock.Transaction.get_by_uid.return_value = task
        self.assertEqual(self.controller._get_task(True), task)

    def test_set__task(self, _):
        self.controller._set_task(1, 'task')
        self.assertEqual(self.controller._tasks[1], 'task')

    @mock.patch(
        'nailgun.orchestrator.deployment_serializers.serialize_for_lcm')
    def test_set_info(self, serialized, obj_mock):
        self.controller._set_info(0, 'info')
        self.assertEqual(self.controller._infos[0], 'info')

        serialized.return_value = self.new_context.values()
        self.controller._set_info(1, None)
        self.assertEqual(self.controller._infos[1], self.new_context)


@mock.patch('__builtin__.print')
class TestFuyaqlInterpreter(base.BaseUnitTest):
    def setUp(self):
        self.controller = mock.MagicMock(spec=fuyaql.FuYaqlController)
        self.interpreter = fuyaql.FuyaqlInterpreter(controller=self.controller)

    def test_show_help(self, print_mock):
        self.interpreter.show_help()
        self.assertEqual(
            len(self.interpreter.COMMANDS), print_mock.call_count
        )
        print_mock.assert_any_call(
            ":help", "-", self.interpreter.show_help.__doc__
        )

    def test_show_clusters_if_cluster_selected(self, _):
        self.controller.get_clusters.return_value = [
            {'id': 1, 'name': 'test', 'status': 'error'},
            {'id': 2}
        ]
        self.controller.cluster = {'id': 2}
        with mock.patch.object(self.interpreter, 'print_list') as print_mock:
            self.interpreter.show_clusters()
        print_mock.assert_called_once_with(
            ('id', 'name', 'status'),
            self.controller.get_clusters.return_value,
            mock.ANY
        )
        self.assertEqual(0, print_mock.call_args[0][2]({'id': 2}))
        self.assertRaises(ValueError, print_mock.call_args[0][2], {'id': 1})

    def test_show_clusters_if_no_cluster_selected(self, _):
        self.controller.get_clusters.return_value = [
            {'id': 1, 'name': 'test', 'status': 'error'},
            {'id': 2}
        ]
        self.controller.cluster = None
        with mock.patch.object(self.interpreter, 'print_list') as print_mock:
            self.interpreter.show_clusters()

        print_mock.assert_called_once_with(
            ('id', 'name', 'status'),
            self.controller.get_clusters.return_value,
            mock.ANY
        )
        self.assertRaises(ValueError, print_mock.call_args[0][2], {'id': 1})
        self.assertRaises(ValueError, print_mock.call_args[0][2], {'id': 2})

    def test_show_tasks_if_no_cluster(self, print_mock):
        self.controller.cluster = None
        self.interpreter.show_tasks()
        print_mock.assert_called_once_with("Select cluster at first.")

    def test_show_tasks_if_tasks_selected(self, _):
        self.controller.cluster = {'id': 1}
        self.controller.get_tasks.return_value = [
            {'id': 1, 'status': 'error'},
            {'id': 2},
            {'id': 3}
        ]
        self.controller.selected_tasks = [{'id': 2}, {'id': 3}]
        with mock.patch.object(self.interpreter, 'print_list') as print_mock:
            self.interpreter.show_tasks()

        print_mock.assert_called_once_with(
            ('id', 'status'),
            self.controller.get_tasks.return_value,
            mock.ANY
        )
        self.assertEqual(0, print_mock.call_args[0][2]({'id': 2}))
        self.assertEqual(1, print_mock.call_args[0][2]({'id': 3}))
        self.assertRaises(ValueError, print_mock.call_args[0][2], {'id': 1})

    def test_show_tasks_if_no_all_tasks_selected(self, _):
        self.controller.get_tasks.return_value = [
            {'id': 1, 'status': 'error'},
            {'id': 2},
            {'id': 3}
        ]
        self.controller.selected_tasks = [None, {'id': 3}]
        with mock.patch.object(self.interpreter, 'print_list') as print_mock:
            self.interpreter.show_tasks()

        print_mock.assert_called_once_with(
            ('id', 'status'),
            self.controller.get_tasks.return_value,
            mock.ANY
        )
        self.assertEqual(1, print_mock.call_args[0][2]({'id': 3}))
        self.assertRaises(ValueError, print_mock.call_args[0][2], {'id': 1})
        self.assertRaises(ValueError, print_mock.call_args[0][2], {'id': 2})

    def test_show_nodes_if_no_cluster(self, print_mock):
        self.controller.cluster = None
        self.interpreter.show_tasks()
        print_mock.assert_called_once_with("Select cluster at first.")

    def test_show_nodes_if_node_selected(self, _):
        self.controller.cluster = {'id': 1}
        self.controller.get_nodes.return_value = [
            {'uid': '1', 'status': 'ready', 'roles': ['controller']},
            {'uid': '2'},
            {'uid': '3'}
        ]
        self.controller.node_id = '2'
        with mock.patch.object(self.interpreter, 'print_list') as print_mock:
            self.interpreter.show_nodes()

        print_mock.assert_called_once_with(
            ('uid', 'status', 'roles'),
            self.controller.get_nodes.return_value,
            mock.ANY
        )
        get_index_func = print_mock.call_args[0][2]
        self.assertEqual(0, get_index_func({'uid': '2'}))
        self.assertRaises(ValueError, get_index_func, {'uid': '1'})
        self.assertRaises(ValueError, get_index_func, {'uid': '3'})

    def test_show_nodes_if_no_node_selected(self, _):
        self.controller.cluster = {'id': 1}
        self.controller.get_nodes.return_value = [
            {'uid': '1', 'status': 'ready', 'roles': ['controller']},
            {'uid': '2'},
            {'uid': '3'}
        ]
        self.controller.node_id = None
        with mock.patch.object(self.interpreter, 'print_list') as print_mock:
            self.interpreter.show_nodes()

        print_mock.assert_called_once_with(
            ('uid', 'status', 'roles'),
            self.controller.get_nodes.return_value,
            mock.ANY
        )
        get_index_func = print_mock.call_args[0][2]
        self.assertRaises(ValueError, get_index_func, {'uid': '1'})
        self.assertRaises(ValueError, get_index_func, {'uid': '2'})
        self.assertRaises(ValueError, get_index_func, {'uid': '3'})

    def test_show_cluster_if_no_cluster(self, print_mock):
        self.controller.cluster = None
        self.interpreter.show_cluster()
        print_mock.assert_called_once_with("There is no cluster.")

    def test_show_cluster_if_cluster(self, _):
        self.controller.cluster = {'id': 1, 'status': 'error', 'name': 'test'}
        with mock.patch.object(self.interpreter, 'print_object') as print_mock:
            self.interpreter.show_cluster()
        print_mock.assert_called_once_with(
            'cluster', ('id', 'name', 'status'), self.controller.cluster
        )

    def test_show_task2(self, _):
        with mock.patch.object(self.interpreter, '_show_task') as show_mock:
            self.interpreter.show_task2()
        show_mock.assert_called_once_with(self.controller.EXPECTED)

    def test_show_task(self, _):
        with mock.patch.object(self.interpreter, '_show_task') as show_mock:
            self.interpreter.show_task1()
        show_mock.assert_called_once_with(self.controller.CURRENT)

    def test_show_node_if_no_node(self, print_mock):
        self.controller.node_id = None
        self.interpreter.show_node()
        print_mock.assert_called_once_with("Please select node at first.")
        self.assertEqual(0, self.controller.get_node.call_count)

    def test_show_node_if_node(self, _):
        self.controller.node_id = '2'
        self.controller.get_node_return_value = {'uid': 2}
        with mock.patch.object(self.interpreter, 'print_object') as print_mock:
            self.interpreter.show_node()
        print_mock.assert_called_once_with(
            'node',
            ('uid', 'status', 'roles'),
            self.controller.get_node.return_value
        )

    def test_set_cluster(self, print_mock):
        """Select the cluster."""
        self.controller.set_cluster.side_effect = [True, False]
        self.interpreter.set_cluster('1')
        self.interpreter.set_cluster('2')
        print_mock.assert_called_once_with(
            "There is no cluster with id:", "2"
        )

    def test_set_node_if_no_cluster(self, print_mock):
        self.controller.cluster = None
        self.interpreter.set_node('1')
        print_mock.assert_called_once_with("Select cluster at first.")

    def test_set_node_if_cluster(self, print_mock):
        """Select the cluster."""
        self.controller.cluster = {'id': 1}
        self.controller.set_node.side_effect = [True, False]
        self.interpreter.set_node('1')
        self.interpreter.set_node('2')
        print_mock.assert_called_once_with(
            "There is no node with id:", "2"
        )

    def test_set_task2(self, _):
        with mock.patch.object(self.interpreter, '_set_task') as set_mock:
            self.interpreter.set_task2('2')
        set_mock.assert_called_once_with(self.controller.EXPECTED, '2')

    def test_set_task1(self, _):
        with mock.patch.object(self.interpreter, '_set_task') as set_mock:
            self.interpreter.set_task1('1')
        set_mock.assert_called_once_with(self.controller.CURRENT, '1')

    def test_evaluate_expression_if_no_node(self, print_mock):
        self.controller.node_id = None
        self.interpreter.evaluate_expression("$.toYaml()")
        print_mock.assert_called_once_with("Select node at first.")

    def test_evaluate_expression_if_node(self, _):
        self.controller.node_id = {'uid': '1'}
        self.controller.evaluate.return_value = '1'
        self.assertEqual(
            '1',
            self.interpreter.evaluate_expression("$.uid")
        )
        self.controller.evaluate.assert_called_once_with('$.uid')

    def test_execute_command_if_invalid_command(self, print_mock):
        self.interpreter.execute_command(":helpme")
        print_mock.assert_has_calls(
            [mock.call("Unknown command:", ":helpme"),
             mock.call("Please use :help to see list of available commands")]
        )

    def test_execute_command_with_arguments(self, _):
        with mock.patch.object(self.interpreter, 'set_cluster') as set_mock:
            r = self.interpreter.execute_command(":use cluster 1")
        set_mock.assert_called_once_with('1')
        self.assertIs(set_mock.return_value, r)

    def test_execute_command_without_arguments(self, _):
        with mock.patch.object(self.interpreter, 'show_cluster') as show_mock:
            self.interpreter.execute_command(":show cluster")
        show_mock.assert_called_once_with()

    def test_show_task_if_no_task(self, print_mock):
        self.controller.selected_tasks = [None, 1]
        self.interpreter._show_task(0)
        print_mock.assert_called_once_with("Please select task at first.")

    def test_show_task_if_task(self, _):
        self.controller.selected_tasks = [None, {'id': 1}]
        with mock.patch.object(self.interpreter, 'print_object') as print_mock:
            self.interpreter._show_task(1)
        print_mock.assert_called_once_with('task', ('id', 'status'), {'id': 1})

    def test_set_task_if_no_cluster(self, print_mock):
        self.controller.cluster = None
        self.interpreter._set_task(0, 1)
        print_mock.assert_called_once_with("Select cluster at first.")
        self.assertEqual(0, self.controller.set_task.call_count)

    def test_set_task_check_task_order(self, print_mock):
        self.controller.cluster = {'id': 1}
        self.controller.selected_tasks = [{'id': 5}, {'id': 10}]
        self.interpreter._set_task(0, 20)
        print_mock.assert_called_with(
            "The task, which belongs to state old cannot be"
            " under than task which belongs to state new."
        )
        self.interpreter._set_task(1, 1)
        print_mock.assert_called_with(
            "The task, which belongs to state new cannot be"
            " older than task which belongs to state old."
        )
        self.assertEqual(0, self.controller.set_task.call_count)

    def test_set_task_successfully(self, _):
        self.controller.CURRENT = 0
        self.controller.EXPECTED = 1
        self.controller.cluster = {'id': 1}
        self.controller.selected_tasks = [{'id': 5}, {'id': 10}]
        self.interpreter._set_task(self.controller.CURRENT, '')
        self.controller.set_task.assert_called_with(
            self.controller.CURRENT, 0
        )
        self.interpreter._set_task(self.controller.EXPECTED, '')
        self.controller.set_task.assert_called_with(
            self.controller.EXPECTED, 0
        )
        self.controller.selected_tasks = [{'id': 5}, None]
        self.interpreter._set_task(self.controller.CURRENT, '10')
        self.controller.set_task.assert_called_with(
            self.controller.CURRENT, 10
        )
        self.controller.selected_tasks = [None, {'id': 5}]
        self.interpreter._set_task(self.controller.EXPECTED, '1')
        self.controller.set_task.assert_called_with(
            self.controller.EXPECTED, 1
        )

    def test_print_list(self, print_mock):
        self.interpreter.print_list(
            ('id', 'status'),
            [{'id': 1, 'status': 'ok'}, {'id': 2}, {'id': 3}],
            lambda x: [2, 3].index(x['id'])
        )
        print_mock.assert_has_calls([
            mock.call('id\t|\tstatus'),
            mock.call('-' * 18),
            mock.call('1\t|\tok'),
            mock.call('*', end=' '),
            mock.call('2\t|\t-'),
            mock.call('**', end=' '),
            mock.call('3\t|\t-')
        ], any_order=False)

    def test_print_object(self, print_mock):
        self.interpreter.print_object(
            'node',
            ('id', 'status'),
            {'id': 1},
        )
        print_mock.assert_has_calls([
            mock.call('Node:'),
            mock.call("\tid:\t1"),
            mock.call("\tstatus:\t-"),
        ], any_order=False)
