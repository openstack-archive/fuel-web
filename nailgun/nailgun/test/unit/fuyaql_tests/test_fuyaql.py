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


from nailgun.fuyaql import fuyaql
import mock
import pytest


class TestFuyaqlContext(object):
    @pytest.fixture
    def ctx(self):
        ctx = fuyaql.FuYaqlContext()
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
    @mock.patch('nailgun.orchestrator.deployment_serializers.serialize_for_lcm',
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

#class TestFuyaql(object):
#    def test_internal_show_command(self, interpret, new_context):
#        result = interpret.run_internal_command(':show cluster')
#        assert result is True
#
#    def test_internal_use_command(self, interpret, new_context):
#        result = interpret.run_internal_command(':use cluster 1')
#        assert result is True
#
#    def test_internal_context_commands(self, interpret, new_context):
#        result = interpret.run_internal_command(':loadprevious task 5')
#        assert result is True
#        result = interpret.run_internal_command(':loadcurrent task 10')
#        assert result is True
#
#    def test_unknown_internal_command(self, interpret, new_context):
#        result = interpret.run_internal_command(':some unknown command')
#        assert result is False
