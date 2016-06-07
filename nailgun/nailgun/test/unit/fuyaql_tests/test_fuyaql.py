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

import mock
import pytest

from nailgun.fuyaql import fuyaql

from nailgun.test import base


@mock.patch('nailgun.fuyaql.fuyaql.objects')
class TestFuyaqlController(base.BaseUnitTest):
    @pytest.fixture
    def ctx(self):
        ctx = fuyaql.FuYaqlController()
        return ctx

    @pytest.fixture
    def old_context(self):
        return {
            '1': {
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

    @pytest.fixture
    def new_context(self):
        return {
            '1': {
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

    def test_init(self, ctx):
        assert ctx.cluster is None
        assert ctx.node_id is None
        assert ctx.task_to is None
        assert ctx.task_from is None
        assert ctx.state_to is None
        assert ctx.state_from is None
        assert ctx.yaql_context is not None
        assert ctx.yaql_engine is not None

    @mock.patch('nailgun.objects.TransactionCollection.get_last_succeed_run',
                return_value='task')
    @mock.patch('nailgun.objects.Cluster.get_by_uid', return_value='cluster')
    def test_load_cluster(self, lastrun, task, ctx):
        result = ctx.load_cluster()
        assert ctx.cluster == 'cluster'
        assert ctx.task_from == 'task'
        assert ctx.state_from is None
        assert result is True

    @mock.patch('nailgun.objects.Cluster.get_by_uid', return_value=None)
    def test_load_cluster_nonexistent(self, lastrun, ctx):
        result = ctx.load_cluster()
        assert ctx.cluster is None
        assert result is False

    @mock.patch('nailgun.objects.Transaction.get_deployment_info',
                return_value='deployment_info')
    def test_load_state_to(self, deployment_info, ctx):
        ctx.state_to = None
        ctx.task_to = True
        ctx.load_state_to()
        assert ctx.state_to == 'deployment_info'

    @mock.patch('nailgun.objects.Cluster.get_nodes_not_for_deletion',
                return_value=None)
    @mock.patch(
        'nailgun.orchestrator.deployment_serializers.serialize_for_lcm',
        return_value=[{
            'uid': 1,
            'name': 'node-1'
        }])
    def test_load_state_to_current_state(self, c_info, d_info, ctx):
        ctx.state_to = None
        ctx.task_to = False
        ctx.cluster = True
        ctx.load_state_to()
        assert ctx.state_to == {1: {
            'uid': 1,
            'name': 'node-1'
        }}

    @mock.patch('nailgun.objects.Transaction.get_deployment_info',
                return_value='deployment_info')
    def test_load_state_from(self, d_info, ctx):
        ctx.state_from = None
        ctx.task_from = False
        ctx.load_state_from()
        assert ctx.state_from == dict()
        ctx.state_from = None
        ctx.task_from = True
        ctx.load_state_from()
        assert ctx.state_from == 'deployment_info'

    @mock.patch('nailgun.fuyaql.fuyaql.FuYaqlContext.load_state_to')
    def test_set_node(self, state_to, ctx):
        ctx.state_to = {1: {'uid': 1}}
        result = ctx.set_node(1)
        assert result is True
        result = ctx.set_node(2)
        assert result is False

    @mock.patch('nailgun.fuyaql.fuyaql.FuYaqlContext._get_task',
                return_value=False)
    def test_set_task_to(self, task, ctx):
        ctx.cluster = True
        result = ctx.set_task_to(False)
        assert result is True
        assert ctx.task_to is None
        assert ctx.state_to is None
        assert ctx.node_id is None
        result = ctx.set_task_to(True)
        assert result is False

    @mock.patch('nailgun.fuyaql.fuyaql.FuYaqlContext._get_task',
                return_value='task')
    def test_set_task_to_with_existing_task(self, task, ctx):
        ctx.cluster = True
        result = ctx.set_task_to(True)
        assert result is True
        assert ctx.task_to == 'task'
        assert ctx.state_to is None
        assert ctx.node_id is None

    def test_set_task_from(self, ctx):
        ctx.cluster = True
        result = ctx.set_task_from(False)
        assert result is True
        assert ctx.task_from is None
        assert ctx.state_from is None

    @mock.patch('nailgun.fuyaql.fuyaql.FuYaqlContext._get_task',
                return_value='not_last_task')
    @mock.patch('nailgun.objects.TransactionCollection.get_last_succeed_run',
                return_value='last_task')
    def test_set_task_from_with_existing_task(self, not_last, last, ctx):
        ctx.cluster = True
        result = ctx.set_task_from('not last')
        assert result is True
        assert ctx.task_from == 'not_last_task'
        assert ctx.state_from is None
        result = ctx.set_task_from('last')
        assert result is True
        assert ctx.task_from == 'last_task'
        assert ctx.state_from is None

    @mock.patch('nailgun.objects.TransactionCollection.get_last_succeed_run',
                return_value=False)
    def test_set_task_from_with_existing_task(self, task, ctx):
        ctx.cluster = True
        result = ctx.set_task_from('last')
        assert result is False

    @mock.patch('nailgun.objects.Transaction.get_deployment_info',
                return_value={1: {
                    'uid': 1,
                    'name': 'node-1'
                }})
    def test_get_node(self, d_info, ctx):
        ctx.node_id = 1
        ctx.task_to = True
        result = ctx.get_node()
        assert result == {
            'uid': 1,
            'name': 'node-1'
        }

    @mock.patch('nailgun.objects.Transaction.get_deployment_info',
                return_value={1: {
                    'uid': 1,
                    'name': 'node-1'
                }})
    def test_get_node_without_new_state(self, d_info, ctx):
        ctx.node_id = 1
        ctx.state_from = None
        ctx.task_from = True
        result = ctx.get_node(new_state=False)
        assert result == {
            'uid': 1,
            'name': 'node-1'
        }
        ctx.node_id = 2
        result = ctx.get_node(new_state=False)
        assert result == dict()

    @mock.patch('nailgun.fuyaql.fuyaql.FuYaqlContext.load_state_to')
    @mock.patch('nailgun.fuyaql.fuyaql.FuYaqlContext.load_state_from')
    @mock.patch('nailgun.fuyaql.fuyaql.FuYaqlContext.get_node')
    def test_evaluate(self, g_node, s_from, s_to, ctx, old_context,
                      new_context):
        g_node.side_effect = [new_context, old_context]
        assert ctx.evaluate('changed($)')
        g_node.side_effect = [new_context, old_context]
        with pytest.raises(KeyError):
            assert ctx.evaluate('changed($.roles)') is False


@mock.patch('nailgun.fuyaql.fuyaql.print')
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
