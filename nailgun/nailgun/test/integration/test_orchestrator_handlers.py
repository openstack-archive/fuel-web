# -*- coding: utf-8 -*-

#    Copyright 2013 Mirantis, Inc.
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

from mock import patch
from oslo_serialization import jsonutils
import six

from nailgun import consts
from nailgun import errors
from nailgun import objects
from nailgun.objects import DeploymentGraph
from nailgun.orchestrator.task_based_deployment import TaskProcessor

from nailgun.db.sqlalchemy.models import Cluster
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import fake_tasks
from nailgun.utils import reverse


def make_query(**kwargs):
    """Each value in kwargs should be iterable

    :returns: ?k1=1,2,3&k2=1,2,3
    """
    query = ''
    for key, value in six.iteritems(kwargs):
        if query:
            query += '&'
        query += '{}={}'.format(key, ','.join(value))
    return '?' + query if query else query


class TestDefaultOrchestratorInfoHandlers(BaseIntegrationTest):

    def setUp(self):
        super(TestDefaultOrchestratorInfoHandlers, self).setUp()

        cluster = self.env.create(
            nodes_kwargs=[
                {'roles': ['controller'], 'pending_addition': True},
                {'roles': ['compute'], 'pending_addition': True},
                {'roles': ['cinder'], 'pending_addition': True}])

        self.cluster = self.db.query(Cluster).get(cluster['id'])

    def customization_handler_helper(self, handler_name, get_info, facts):
        resp = self.app.put(
            reverse(handler_name,
                    kwargs={'cluster_id': self.cluster.id}),
            jsonutils.dumps(facts),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(self.cluster.is_customized)
        self.datadiff(get_info(), facts)

    def check_default_deployment_handler(self, release_version):
        self.env.create(
            nodes_kwargs=[
                {'roles': ['controller'], 'pending_addition': True},
                {'roles': ['compute'], 'pending_addition': True},
                {'roles': ['cinder'], 'pending_addition': True}],
            release_kwargs={
                'version': release_version,
                'operating_system': consts.RELEASE_OS.ubuntu
            }
        )
        cluster = self.env.clusters[-1]
        resp = self.app.get(
            reverse('DefaultDeploymentInfo',
                    kwargs={'cluster_id': cluster.id}),
            headers=self.default_headers)

        self.assertEqual(resp.status_code, 200)
        # for lcm the deployment info will contain master node too
        # and we check only that nodes are included to result
        expected_node_uids = {n.uid for n in cluster.nodes}
        actual_node_uids = {n['uid'] for n in resp.json_body}
        self.assertTrue(expected_node_uids.issubset(actual_node_uids))

    def test_default_deployment_handler(self):
        for release_ver in ('newton-10.0', 'mitaka-9.0', 'liberty-8.0'):
            self.check_default_deployment_handler(release_ver)

    def test_default_provisioning_handler(self):
        resp = self.app.get(
            reverse('DefaultProvisioningInfo',
                    kwargs={'cluster_id': self.cluster.id}),
            headers=self.default_headers)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(3, len(resp.json_body['nodes']))

    def test_400_if_node_not_assign_to_any_cluster(self):
        node = self.env.create_node()
        url = reverse(
            'DefaultProvisioningInfo',
            kwargs={'cluster_id': self.cluster.id}) + \
            make_query(nodes=[node['uid']])
        resp = self.app.get(
            url, headers=self.default_headers, expect_errors=True
        )

        self.assertEqual(resp.status_code, 400)
        self.assertIn("do not belong to any cluster", resp.body)

    def test_default_provisioning_handler_for_selected_nodes(self):
        node_ids = [node.uid for node in self.cluster.nodes][:2]
        url = reverse(
            'DefaultProvisioningInfo',
            kwargs={'cluster_id': self.cluster.id}) + \
            make_query(nodes=node_ids)
        resp = self.app.get(url, headers=self.default_headers)

        self.assertEqual(resp.status_code, 200)
        data = resp.json_body['nodes']
        self.assertEqual(2, len(data))
        actual_uids = [node['uid'] for node in data]
        self.assertItemsEqual(actual_uids, node_ids)

    def test_default_deployment_handler_for_selected_nodes(self):
        node_ids = [node.uid for node in self.cluster.nodes][:2]
        url = reverse(
            'DefaultDeploymentInfo',
            kwargs={'cluster_id': self.cluster.id}) + \
            make_query(nodes=node_ids)
        resp = self.app.get(url, headers=self.default_headers)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(2, len(resp.json_body))
        actual_uids = [node['uid'] for node in resp.json_body]
        self.assertItemsEqual(actual_uids, node_ids)

    def test_cluster_provisioning_customization(self):
        facts = {'engine': {'1': '2'}}
        nodes = []
        for node in self.env.nodes:
            nodes.append({"key": "value", "uid": node.uid})
        facts['nodes'] = nodes
        self.customization_handler_helper(
            'ProvisioningInfo',
            lambda: objects.Cluster.get_provisioning_info(self.cluster),
            facts
        )

    def test_cluster_deployment_customization(self):
        facts = []
        for node in self.env.nodes:
            facts.append({"key": "value", "uid": node.uid})
        self.customization_handler_helper(
            'DeploymentInfo',
            lambda: objects.Cluster.get_deployment_info(self.cluster),
            facts
        )

    def test_deployment_with_one_compute_node(self):
        cluster = self.env.create(
            nodes_kwargs=[
                {'roles': ['compute']}
            ]
        )

        response = self.app.get(
            reverse('DefaultDeploymentInfo',
                    kwargs={'cluster_id': cluster['id']}),
            headers=self.default_headers
        )
        self.assertEqual(response.status_code, 200)


class BaseSelectedNodesTest(BaseIntegrationTest):

    def setUp(self):
        super(BaseSelectedNodesTest, self).setUp()
        self.env.create(
            nodes_kwargs=[
                {'roles': ['controller'], 'pending_addition': True},
                {'roles': ['controller'], 'pending_addition': True},
                {'roles': ['controller'], 'pending_addition': True},
                {'roles': ['cinder'], 'pending_addition': True},
                {'roles': ['compute'], 'pending_addition': True},
                {'roles': ['mongo'], 'pending_addition': True},
                {'roles': ['mongo'], 'pending_addition': True},
                {'roles': ['cinder'], 'pending_addition': True}])

        self.cluster = self.env.clusters[0]
        self.nodes = [n for n in self.cluster.nodes][:3]
        self.node_uids = [n.uid for n in self.nodes]

    def send_put(self, url, data=None):
        return self.app.put(
            url, jsonutils.dumps(data),
            headers=self.default_headers, expect_errors=True)

    def make_action_url(self, handler_name, node_uids):
        return reverse(
            handler_name,
            kwargs={'cluster_id': self.cluster.id}) + \
            make_query(nodes=node_uids)

    def check_deployment_call_made(self, nodes_uids, mcast):
        args, kwargs = mcast.call_args
        deployed_uids = [n['uid'] for n in args[1]['args']['deployment_info']]
        self.assertEqual(len(nodes_uids), len(deployed_uids))
        self.assertItemsEqual(nodes_uids, deployed_uids)

    def check_resp_declined(self, resp):
        self.assertEqual(resp.status_code, 400)
        self.assertRegexpMatches(
            resp.body,
            "Deployment operation cannot be started.*"
        )


class TestSelectedNodesAction(BaseSelectedNodesTest):

    @fake_tasks(fake_rpc=False, mock_rpc=False)
    @patch('nailgun.task.task.rpc.cast')
    def test_start_provisioning_on_selected_nodes(self, mcast):
        action_url = self.make_action_url(
            "ProvisionSelectedNodes",
            self.node_uids
        )
        self.send_put(action_url)

        args, kwargs = mcast.call_args
        provisioned_uids = [
            n['uid'] for n in args[1]['args']['provisioning_info']['nodes']]

        self.assertEqual(3, len(provisioned_uids))
        self.assertItemsEqual(self.node_uids, provisioned_uids)

    def test_start_provisioning_is_unavailable(self):
        action_url = self.make_action_url(
            "ProvisionSelectedNodes",
            self.node_uids
        )

        self.env.releases[0].state = consts.RELEASE_STATES.unavailable

        resp = self.send_put(action_url)

        self.assertEqual(resp.status_code, 400)
        self.assertRegexpMatches(resp.body, 'Release .* is unavailable')

    @fake_tasks(fake_rpc=False, mock_rpc=False)
    @patch('nailgun.task.task.rpc.cast')
    def test_start_deployment_on_selected_nodes(self, mcast):
        controller_nodes = [
            n for n in self.cluster.nodes
            if "controller" in n.roles
        ]

        self.emulate_nodes_provisioning(controller_nodes)

        deploy_action_url = self.make_action_url(
            "DeploySelectedNodes",
            self.node_uids
        )
        self.send_put(deploy_action_url)

        self.check_deployment_call_made(self.node_uids, mcast)

    @fake_tasks(fake_rpc=False, mock_rpc=False)
    @patch('nailgun.task.task.rpc.cast')
    def test_start_deployment_on_selected_nodes_with_tasks(self, mcast):
        controller_nodes = [
            n for n in self.cluster.nodes
            if "controller" in n.roles
        ]

        self.emulate_nodes_provisioning(controller_nodes)

        nodes_uids = [n.uid for n in controller_nodes]

        controller_to_deploy = nodes_uids[0]

        deploy_action_url = self.make_action_url(
            "DeploySelectedNodesWithTasks",
            [controller_to_deploy]
        )
        self.send_put(deploy_action_url, ['deploy_legacy'])

        self.check_deployment_call_made([nodes_uids[0]], mcast)

    @patch('nailgun.task.task.rpc.cast')
    def test_start_sel_nodes_deployment_w_custom_graph(self, mcast):
        controller_nodes = [
            n for n in self.cluster.nodes
            if "controller" in n.roles
        ]
        objects.DeploymentGraph.create_for_model(
            {'tasks': [
                {
                    'id': 'custom-task',
                    'type': 'puppet',
                    'roles': '*',
                    'version': '2.0.0',
                    'requires': ['pre_deployment_start']
                }
            ]}, self.cluster, 'custom-graph')

        self.emulate_nodes_provisioning(controller_nodes)
        nodes_uids = [n.uid for n in controller_nodes]
        controller_to_deploy = nodes_uids[0]
        deploy_action_url = self.make_action_url(
            "DeploySelectedNodesWithTasks",
            [controller_to_deploy]
        ) + '&graph_type=custom-graph'
        self.send_put(deploy_action_url, ['custom-task'])

        executed_task_ids = [
            t['id'] for t in
            mcast.call_args[0][1]['args']['tasks_graph'][controller_to_deploy]
        ]
        self.check_deployment_call_made([controller_to_deploy], mcast)
        self.assertItemsEqual(['custom-task'], executed_task_ids)

    @patch('nailgun.task.task.rpc.cast')
    def test_validator_fail_on_deployment_w_custom_graph(self, mcast):
        objects.DeploymentGraph.create_for_model(
            {'tasks': [
                {
                    'id': 'custom-task',
                    'type': 'puppet',
                }
            ]}, self.cluster, 'custom-graph')

        deploy_action_url = self.make_action_url(
            "DeploySelectedNodesWithTasks",
            []
        ) + '&graph_type=custom-graph'

        response = self.send_put(
            deploy_action_url,
            ['upload_nodes_info']   # this task exists in default graph
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json_body,
            {
                "message": "Tasks upload_nodes_info are not present "
                           "in deployment graph",
                "errors": []
            }
        )

    @fake_tasks(fake_rpc=False, mock_rpc=False)
    @patch('nailgun.task.task.rpc.cast')
    def test_deployment_of_node_is_forbidden(self, mcast):
        # cluster is in ha mode so for the sanity of the check
        # lets operate on non-controller node
        node_to_deploy = [
            n for n in self.cluster.nodes if
            not
            set(["primary-controller", "controller"])
            &
            set(n.roles)
        ].pop()

        deploy_action_url = self.make_action_url(
            "DeploySelectedNodes",
            [node_to_deploy.uid]
        )

        resp = self.send_put(deploy_action_url)
        self.check_resp_declined(resp)

        self.emulate_nodes_provisioning([node_to_deploy])

        self.send_put(deploy_action_url)

        self.check_deployment_call_made([node_to_deploy.uid], mcast)

    @patch('nailgun.task.task.rpc.cast')
    def test_deployment_forbidden_on_pending_deletion(self, mcast):
        nodes_uids = [n.uid for n in self.cluster.nodes]
        self.emulate_nodes_provisioning(self.cluster.nodes)

        marked_for_deletion = self.cluster.nodes[-1]
        marked_for_deletion.pending_deletion = True
        self.db.flush()

        deploy_action_url = self.make_action_url(
            "DeploySelectedNodes", nodes_uids)

        resp = self.send_put(deploy_action_url)
        self.check_resp_declined(resp)
        self.assertNotIn(
            "{0} are not provisioned yet".format(nodes_uids), resp.body)
        self.assertIn(
            "[{0}] marked for deletion".format(marked_for_deletion.id),
            resp.body)

    @fake_tasks(fake_rpc=False, mock_rpc=False)
    @patch('nailgun.task.task.rpc.cast')
    def test_deployment_of_node_no_deployment_tasks(self, mcast):
        controller_nodes = [
            n for n in self.cluster.nodes
            if "controller" in n.roles
        ]

        self.emulate_nodes_provisioning(controller_nodes)

        node_to_deploy = self.cluster.nodes[0]

        deploy_action_url = self.make_action_url(
            "DeploySelectedNodes",
            [node_to_deploy.uid]
        )
        # overwriting default made in EnvironmentManager

        self.cluster.release.deployment_graphs_assoc.delete()
        self.db().flush()

        resp = self.send_put(deploy_action_url)
        resp_msg = jsonutils.loads(resp.body)['message']

        self.assertFalse(mcast.called)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Deployment tasks not found", resp_msg)
        self.assertIn(self.cluster.release.name, resp_msg)


class TestCustomGraphAction(BaseSelectedNodesTest):

    def setUp(self):
        super(TestCustomGraphAction, self).setUp()
        self.custom_tasks = [
            {
                'id': 'first-custom-task',
                'type': 'stage',
                'requires': ['pre_deployment_end']
            }, {
                'id': 'second-custom-task',
                'type': 'stage',
                'requires': ['deploy_start']
            }
        ]
        self.custom_graph = DeploymentGraph.create_for_model(
            {
                'name': 'custom-graph-name',
                'tasks': self.custom_tasks
            },
            self.cluster,
            graph_type='custom-graph'
        )
        self.env.db().commit()

    def make_action_url(self, handler_name, node_uids, graph_type=None):
        if graph_type is None:
            query = make_query(nodes=node_uids)
        else:
            query = make_query(graph_type=graph_type, nodes=node_uids)

        return reverse(
            handler_name,
            kwargs={'cluster_id': self.cluster.id}) + query

    def check_tasks_is_executed(self, tasks_graph, expected_taks):
        # check only ids of synchronization points
        # we can check only tasks on virtual node
        sync_point = consts.ORCHESTRATOR_TASK_TYPES.stage
        self.assertItemsEqual(
            [x['id'] for x in expected_taks if x['type'] == sync_point],
            [x['id'] for x in tasks_graph[None]]
        )

    @patch('nailgun.task.task.rpc.cast')
    @patch('nailgun.objects.Cluster.get_deployment_tasks')
    def test_default_graph(self, get_tasks, mcast):
        get_tasks.return_value = self.custom_tasks
        self.emulate_nodes_provisioning(self.nodes)

        deploy_action_url = self.make_action_url(
            "DeploySelectedNodes",
            self.node_uids
        )
        response = self.send_put(deploy_action_url)
        self.assertEqual(response.status_code, 202)
        self.check_tasks_is_executed(
            mcast.call_args[0][1]['args']['tasks_graph'],
            self.custom_tasks
        )
        # TODO(bgaifullin) need to remove graph validation
        # the get_deployment_tasks called 2 times
        # first in check_before deployment
        # second in deployement
        # in check before deployment, because for Task Deploy
        # it is useless
        get_tasks.assert_called_with(self.cluster, None)

    @patch('nailgun.task.task.rpc.cast')
    @patch('nailgun.objects.Cluster.get_deployment_tasks')
    def test_existing_custom_graph(self, get_tasks, mcast):
        get_tasks.return_value = self.custom_tasks
        self.emulate_nodes_provisioning(self.nodes)

        deploy_action_url = self.make_action_url(
            "DeploySelectedNodes",
            self.node_uids,
            ["custom-graph"]
        )
        response = self.send_put(deploy_action_url)
        self.assertEqual(response.status_code, 202)
        self.check_tasks_is_executed(
            mcast.call_args[0][1]['args']['tasks_graph'],
            self.custom_tasks
        )
        # TODO(bgaifullin) need to remove graph validation
        # the get_deployment_tasks called 2 times
        # first in check_before deployment
        # second in deployement
        # in check before deployment, because for Task Deploy
        # it is useless
        get_tasks.assert_called_with(self.cluster, "custom-graph")

    @patch('nailgun.task.task.rpc.cast')
    def test_not_existing_custom_graph(self, mcast):
        self.emulate_nodes_provisioning(self.nodes)

        deploy_action_url = self.make_action_url(
            "DeploySelectedNodes",
            self.node_uids,
            ["not-existing-custom-graph"]
        )

        response = self.send_put(deploy_action_url)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(0, mcast.call_count)


class TestDeploymentHandlerSkipTasks(BaseSelectedNodesTest):

    def setUp(self):
        super(TestDeploymentHandlerSkipTasks, self).setUp()
        self.tasks = ['deploy_legacy']
        self.non_existent = ['non_existent']

    @patch('nailgun.task.task.rpc.cast')
    def test_use_only_certain_tasks_in_granular_deploy(self, mcast):
        self.env.disable_task_deploy(self.cluster)
        self.emulate_nodes_provisioning(self.nodes)

        action_url = self.make_action_url(
            "DeploySelectedNodesWithTasks",
            self.node_uids
        )
        out = self.send_put(action_url, self.tasks)
        self.assertEqual(out.status_code, 202)

        args, kwargs = mcast.call_args
        deployed_uids = [n['uid'] for n in args[1]['args']['deployment_info']]
        deployment_data = args[1]['args']['deployment_info'][0]
        self.assertItemsEqual(deployed_uids, self.node_uids)
        self.assertEqual(len(deployment_data['tasks']), 1)

    def test_deployment_is_forbidden(self):
        action_url = self.make_action_url(
            "DeploySelectedNodesWithTasks",
            self.node_uids
        )
        resp = self.send_put(action_url, self.tasks)
        self.check_resp_declined(resp)

    def test_error_raised_on_non_existent_tasks(self):
        action_url = self.make_action_url(
            "DeploySelectedNodesWithTasks",
            self.node_uids
        )
        out = self.send_put(action_url, self.non_existent)
        self.assertEqual(out.status_code, 400)

    def test_error_on_empty_list_tasks(self):
        action_url = self.make_action_url(
            "DeploySelectedNodesWithTasks",
            self.node_uids
        )
        out = self.send_put(action_url, [])
        self.assertEqual(out.status_code, 400)


class TestDeployMethodVersioning(BaseSelectedNodesTest):

    def assert_deployment_method(self, version, method, mcast):
        self.cluster.release.version = version
        self.db.flush()

        self.emulate_nodes_provisioning(self.nodes)

        action_url = self.make_action_url(
            "DeploySelectedNodes",
            self.node_uids
        )
        self.send_put(action_url)
        deployment_method = mcast.call_args_list[0][0][1]['method']
        self.assertEqual(deployment_method, method)

    @patch('nailgun.task.task.rpc.cast')
    def test_deploy_is_used_before_61(self, mcast):
        self.env.disable_task_deploy(self.cluster)
        self.assert_deployment_method('2014.2-6.0', 'deploy', mcast)

    @patch('nailgun.task.task.rpc.cast')
    def test_granular_is_used_in_61(self, mcast):
        self.env.disable_task_deploy(self.cluster)
        self.assert_deployment_method('2014.2-6.1', 'granular_deploy', mcast)


class TestSerializedTasksHandler(BaseIntegrationTest):

    def setUp(self):
        super(TestSerializedTasksHandler, self).setUp()
        self.env.create(
            nodes_kwargs=[
                {'roles': ['controller'], 'pending_addition': True},
                {'roles': ['compute'], 'pending_addition': True}])
        self.cluster = self.env.clusters[-1]
        self.nodes = self.cluster.nodes
        objects.Cluster.prepare_for_deployment(
            self.cluster, self.cluster.nodes)

    def get_serialized_tasks(self, cluster_id, **kwargs):
        uri = reverse(
            "SerializedTasksHandler",
            kwargs={'cluster_id': cluster_id}) + \
            make_query(**kwargs)
        return self.app.get(uri, expect_errors=True)

    def previous(self, obj):
        return str(obj.id - 1)

    @patch.object(TaskProcessor, 'ensure_task_based_deploy_allowed')
    def test_serialized_tasks_returned(self, _):
        nodes_uids = [n.uid for n in self.nodes]
        resp = self.get_serialized_tasks(
            self.cluster.id, nodes=nodes_uids)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('tasks_graph', resp.json)
        self.assertIn('tasks_directory', resp.json)
        tasks_graph = resp.json['tasks_graph']
        self.assertItemsEqual(nodes_uids + ['null'], tasks_graph.keys())
        expected_tasks = ['netconfig', 'globals', 'deploy_legacy',
                          'upload_nodes_info', 'update_hosts']
        for n in nodes_uids:
            self.assertItemsEqual(
                [t['id'] for t in tasks_graph[n]], expected_tasks)
        virtual_tasks = ['post_deployment_start', 'post_deployment_end',
                         'deploy_start', 'deploy_end',
                         'pre_deployment_start', 'pre_deployment_end']
        self.assertItemsEqual(
            [t['id'] for t in tasks_graph['null']], virtual_tasks)
        # sanity check that it returns dictionary with tasks metadata
        for task_name, task in six.iteritems(resp.json['tasks_directory']):
            self.assertIn(task['type'], consts.ORCHESTRATOR_TASK_TYPES)

    @patch.object(TaskProcessor, 'ensure_task_based_deploy_allowed')
    def test_custom_serialized_tasks_returned(self, _):
        objects.DeploymentGraph.create_for_model(
            {'tasks': [
                {
                    'id': 'first-custom-task',
                    'type': 'stage',
                    'requires': ['pre_deployment_end']
                }, {
                    'id': 'second-custom-task',
                    'type': 'stage',
                    'requires': ['deploy_start']
                }
            ]}, self.cluster, 'custom-graph')

        resp = self.get_serialized_tasks(
            self.cluster.id, graph_type=['custom-graph'])
        self.assertEqual(resp.status_code, 200)
        self.assertIn('tasks_graph', resp.json)
        self.assertIn('tasks_directory', resp.json)
        tasks_graph = resp.json['tasks_graph']
        expected_tasks = ['first-custom-task', 'second-custom-task']
        self.assertItemsEqual(
            [t['id'] for t in tasks_graph['null']], expected_tasks)

    @patch.object(TaskProcessor, 'ensure_task_based_deploy_allowed')
    def test_query_nodes_and_tasks(self, _):
        not_skipped = ['globals']
        resp = self.get_serialized_tasks(
            self.cluster.id,
            nodes=[self.nodes[0].uid],
            tasks=not_skipped)
        for t in resp.json['tasks_graph'][self.nodes[0].uid]:
            if t['id'] in not_skipped:
                self.assertNotEqual(
                    t['type'], consts.ORCHESTRATOR_TASK_TYPES.skipped)
            else:
                self.assertEqual(
                    t['type'], consts.ORCHESTRATOR_TASK_TYPES.skipped)

    @patch.object(TaskProcessor, 'ensure_task_based_deploy_allowed')
    def test_pending_nodes_serialized(self, _):
        resp = self.get_serialized_tasks(self.cluster.id)
        self.assertEqual(resp.status_code, 200)
        expected = set((n.uid for n in self.nodes))
        expected.add('null')
        self.assertTrue(expected, resp.json['tasks_graph'].keys())

    def test_404_if_cluster_doesnt_exist(self):
        resp = self.get_serialized_tasks(self.previous(self.cluster))
        self.assertEqual(resp.status_code, 404)
        self.assertIn("Cluster not found", resp.body)

    def test_404_if_node_doesnt_exist(self):
        resp = self.get_serialized_tasks(self.cluster.id,
                                         nodes=[self.previous(self.nodes[0])])
        self.assertEqual(resp.status_code, 404)
        self.assertIn("NodeCollection not found", resp.body)

    def test_400_if_node_not_in_this_cluster(self):
        node = self.env.create_node()
        resp = self.get_serialized_tasks(self.cluster.id,
                                         nodes=[node['uid']])
        self.assertEqual(resp.status_code, 400)
        self.assertIn("do not belong to cluster", resp.body)

    @patch.object(TaskProcessor, 'ensure_task_based_deploy_allowed')
    def test_400_if_task_based_not_allowed(self, check_task_mock):
        check_task_mock.side_effect = errors.TaskBaseDeploymentNotAllowed()
        resp = self.get_serialized_tasks(self.cluster.id)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("The task-based deployment is not allowed", resp.body)
